# pages/dashboard.py
import streamlit as st
import urllib.request
import urllib.error
import zipfile
import io
import json
import logging
import os
import google.genai as genai
from google.genai import types
from theme import inject_theme
from services.database_service import (
    get_all_files,
    save_file,
    delete_file,
    get_file_content,
    insert_file_with_chunks,
    wipe_all,
    LANGUAGE_MAPPING
)

logger = logging.getLogger("pages_dashboard")

def parse_github_url(repo_url: str) -> str:
    url = repo_url.strip()
    if not url:
        return None
    if url.endswith(".git"):
        url = url[:-4]
    
    # Extract path portion
    if "git@github.com:" in url:
        path = url.split("git@github.com:")[-1]
    elif "github.com/" in url:
        path = url.split("github.com/")[-1]
    else:
        path = url
        
    path = path.strip("/")
    parts = path.split("/")
    if len(parts) >= 2:
        return f"{parts[0]}/{parts[1]}"
    return None

def check_repo_private(repo_url: str) -> bool:
    repo_path = parse_github_url(repo_url)
    if not repo_path:
        return False
        
    api_url = f"https://api.github.com/repos/{repo_path}"
    req = urllib.request.Request(
        api_url,
        headers={"User-Agent": "Mozilla/5.0"}
    )
    try:
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode())
            if data.get("private", False):
                return True
            return False
    except urllib.error.HTTPError as e:
        if e.code == 403:
            # Check for API rate limiting
            rate_remaining = e.headers.get("X-RateLimit-Remaining")
            if rate_remaining == "0":
                return False  # Rate limited, assume public to allow ZIP download attempt
            try:
                body = e.read().decode("utf-8", errors="ignore")
                if "rate limit" in body.lower():
                    return False
            except Exception:
                pass
            return True
        elif e.code in [404, 401]:
            # Private or non-existent
            return True
        return False
    except Exception:
        return False

def call_gemini(prompt: str, system_instruction: str = "") -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY is not configured in your .env file.")
    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction
        )
    )
    return response.text

def generate_project_explanation(files: list) -> str:
    paths = [f["path"] for f in files]
    file_structure = "\n".join(paths[:100])
    if len(paths) > 100:
        file_structure += f"\n... and {len(paths) - 100} more files."
        
    top_contexts = []
    important_keywords = ["app.py", "main.py", "index.js", "package.json", "requirements.txt", "setup.py", "cargo.toml", "go.mod"]
    count = 0
    for f in files:
        path = f["path"]
        if any(keyword in path.lower() for keyword in important_keywords):
            content_str = f["content"]
            if isinstance(content_str, bytes):
                content_str = content_str.decode("utf-8", errors="ignore")
            top_contexts.append(f"File: {path}\nContent:\n{content_str[:1500]}")
            count += 1
            if count >= 5:
                break
                
    key_files_content = "\n\n".join(top_contexts)
    
    prompt = f"""
You are an expert software architect. A user has uploaded a GitHub repository but it does not contain a README file.
Please generate a simple, easy-to-understand explanation of the project.
Include:
1. **Purpose**: What is this project likely for?
2. **Structure**: Outline the folder and file structure.
3. **Design**: Describe the architecture, design patterns, or libraries utilized based on the file contents.

Use beautiful, professional formatting with markdown.

Here is the file structure:
```
{file_structure}
```

Here is the content of key files:
{key_files_content}
"""
    try:
        explanation = call_gemini(prompt, "You are a software architecture explanation generator.")
        return explanation
    except Exception as e:
        return f"Failed to generate project explanation: {e}"

def ensure_readme_or_explanation():
    if st.session_state.get('last_repo_readme') or st.session_state.get('last_repo_explanation'):
        return
        
    files = get_all_files()
    if not files:
        return
        
    readme_id = None
    for f in files:
        fname = f["filename"].lower()
        if fname in ["readme.md", "readme.txt", "readme.markdown", "readme"] or fname.endswith("/readme.md") or fname.endswith("/readme.txt") or fname.endswith("/readme.markdown") or fname.endswith("/readme"):
            readme_id = f["id"]
            break
            
    if readme_id:
        file_data = get_file_content(readme_id)
        st.session_state['last_repo_readme'] = file_data.get("content")
        st.session_state['last_repo_explanation'] = None
        st.session_state['last_repo_name'] = "Currently Indexed Workspace"
    else:
        st.session_state['last_repo_readme'] = None
        db_files = []
        for f in files[:50]:
            file_data = get_file_content(f["id"])
            db_files.append({
                "path": f["filename"],
                "content": file_data.get("content", "")
            })
        
        explanation = generate_project_explanation(db_files)
        st.session_state['last_repo_explanation'] = explanation
        st.session_state['last_repo_name'] = "Currently Indexed Workspace"

def process_single_file(uploaded, file_type):
    try:
        content = uploaded.read().decode("utf-8", errors="ignore")
        filename = uploaded.name
        ext = filename.split(".")[-1].lower() if "." in filename else ""
        lang = LANGUAGE_MAPPING.get(ext, "text")
        save_file(filename, file_type, content, lang, len(content))
        st.success(f"✓ Indexed {filename}")
        st.rerun()
    except Exception as e:
        st.error(f"Failed to process file: {e}")

def process_pasted_text(raw_text, filename, paste_type):
    try:
        ext = filename.split(".")[-1].lower() if "." in filename else ""
        lang = LANGUAGE_MAPPING.get(ext, "text")
        save_file(filename, paste_type, raw_text, lang, len(raw_text))
        st.success(f"✓ Indexed {filename}")
        st.rerun()
    except Exception as e:
        st.error(f"Failed to process pasted text: {e}")

def download_and_filter_repo(repo_url: str, branch: str) -> list:
    repo_path = parse_github_url(repo_url)
    if not repo_path:
        raise ValueError("Invalid GitHub URL. Must be like https://github.com/username/repository")
        
    zip_url = f"https://github.com/{repo_path}/archive/refs/heads/{branch}.zip"
    
    req = urllib.request.Request(
        zip_url,
        headers={"User-Agent": "Mozilla/5.0"}
    )
    try:
        with urllib.request.urlopen(req) as response:
            zip_data = response.read()
    except Exception as e:
        if branch == "main":
            fallback_url = f"https://github.com/{repo_path}/archive/refs/heads/master.zip"
            req = urllib.request.Request(
                fallback_url,
                headers={"User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req) as response:
                zip_data = response.read()
        else:
            raise e
            
    files_list = []
    with zipfile.ZipFile(io.BytesIO(zip_data)) as z:
        for name in z.namelist():
            if name.endswith("/"):
                continue
            parts = name.split("/", 1)
            clean_name = parts[1] if len(parts) > 1 else name
            
            if any(p.startswith(".") for p in clean_name.split("/")) or "node_modules/" in clean_name or "venv/" in clean_name or "__pycache__/" in clean_name:
                continue
                
            # Filter out non-text/binary files using extension whitelist
            ext = clean_name.split(".")[-1].lower() if "." in clean_name else ""
            allowed_exts = set(list(LANGUAGE_MAPPING.keys()) + ["yml", "toml", "sql", "sh", "bat", "ini", "cfg", "properties", "xml", "csv"])
            base_name = clean_name.split("/")[-1].lower()
            
            is_allowed = ext in allowed_exts or base_name in ["dockerfile", "license", "procfile", "gemfile", "makefile"]
            if not is_allowed:
                continue
                
            # Skip files larger than 300KB to prevent indexing massive scripts/assets
            try:
                info = z.getinfo(name)
                if info.file_size > 300 * 1024:
                    continue
            except Exception:
                pass
                
            try:
                content = z.read(name)
                files_list.append({
                    "path": clean_name,
                    "content": content
                })
            except Exception:
                pass
    return files_list

def clone_and_index(repo_url: str, branch: str):
    repo_path = parse_github_url(repo_url)
    if not repo_path:
        st.error("Invalid GitHub URL. Must be like https://github.com/username/repository")
        return
        
    if check_repo_private(repo_url):
        st.error("This repository is private, so I can't access it.")
        return
        
    try:
        progress = st.progress(0)
        status   = st.empty()
        files    = download_and_filter_repo(repo_url, branch)
        if not files:
            st.warning("No valid text files found.")
            progress.empty()
            return
            
        for i, f in enumerate(files):
            status.markdown(f'`Indexing {f["path"]}...`')
            insert_file_with_chunks(f)
            progress.progress((i + 1) / len(files))
        progress.empty()
        status.success(f'✓  Indexed {len(files)} files from {repo_url}')
        
        # Check README
        readme_file = None
        for f in files:
            p = f["path"].lower()
            if p == "readme.md" or p.endswith("/readme.md") or p == "readme.txt" or p.endswith("/readme.txt"):
                readme_file = f
                break
                
        if readme_file:
            content_str = readme_file["content"]
            if isinstance(content_str, bytes):
                content_str = content_str.decode("utf-8", errors="ignore")
            st.session_state['last_repo_readme'] = content_str
            st.session_state['last_repo_explanation'] = None
        else:
            st.session_state['last_repo_readme'] = None
            explanation = generate_project_explanation(files)
            st.session_state['last_repo_explanation'] = explanation
            
        st.session_state['last_repo_name'] = repo_url
        st.rerun()
    except Exception as ex:
        st.error(f"Failed to clone and index repository: {ex}")

def render_ingestion_tabs():
    tab_upload, tab_github, tab_paste = st.tabs([
        '📄  Upload File',
        '🐙  GitHub Repo',
        '✍️  Paste Text',
    ])
 
    with tab_upload:
        uploaded = st.file_uploader(
            'Drop a source file, API doc, or design doc',
            type=['py','js','ts','tsx','md','txt','json','yaml','html','css','java','go','rs']
        )
        file_type = st.selectbox('File Type',
            ['source_code', 'api_doc', 'design_doc'])
        if st.button('⬆  Ingest File') and uploaded:
            process_single_file(uploaded, file_type)
 
    with tab_github:
        repo_url = st.text_input('GitHub URL',
            placeholder='https://github.com/owner/repo')
        branch = st.text_input('Branch', value='main')
        col_clone, col_info = st.columns([2,1])
        with col_clone:
            if st.button('⬇  Analyze Repository', use_container_width=True):
                if repo_url:
                    clone_and_index(repo_url, branch)
                else:
                    st.error("Please enter a repository URL.")
                    
        with st.expander("ℹ️  Limitations & Technical Notes"):
            st.markdown("""
            * **Private Repositories:** Private repositories cannot be accessed because the application operates without GitHub API credentials (Personal Access Tokens). Attempts to clone them will be automatically detected and blocked with a warning message.
            * **API Rate Limits:** Unauthenticated requests to GitHub's REST API and ZIP download endpoints share public rate limits. Excessive requests may trigger temporary blocks.
            * **Repository Size:** Extremely large codebases may hit container execution limits (512MB RAM on free-tier hosting) or timeout during vector embedding generation.
            * **Binary/Boilerplate Filtering:** Media files, zip files, and build/dependency folders (like `node_modules/`, `venv/`, `.git/`) are automatically excluded from indexing to optimize performance.
            """)
 
    with tab_paste:
        raw_text = st.text_area('Paste code or text', height=240)
        filename = st.text_input('Filename', placeholder='snippet.py')
        paste_type = st.selectbox('Type', ['source_code','api_doc','design_doc'])
        if st.button('⬆  Ingest Text') and raw_text and filename:
            process_pasted_text(raw_text, filename, paste_type)

def render_files_table():
    st.markdown('#### 🗄️  Indexed Files')
    
    col_search, col_wipe = st.columns([5, 1])
    with col_search:
        search = st.text_input('', placeholder='🔍  Filter by filename...',
            label_visibility='collapsed')
    with col_wipe:
        if st.button('🗑️ Wipe DB', use_container_width=True):
            wipe_all()
            if 'last_repo_readme' in st.session_state:
                del st.session_state['last_repo_readme']
            if 'last_repo_explanation' in st.session_state:
                del st.session_state['last_repo_explanation']
            if 'last_repo_name' in st.session_state:
                del st.session_state['last_repo_name']
            if 'chat_history' in st.session_state:
                st.session_state['chat_history'] = []
            st.success("Database wiped successfully!")
            st.rerun()
            
    files = get_all_files()
    if search:
        files = [f for f in files if search.lower() in f['filename'].lower()]
    if not files:
        st.info('No files indexed yet.')
        return
        
    st.markdown('''
    <div style="display:flex; font-weight:700; color:#00f0ff; padding-bottom:8px; border-bottom:1px solid rgba(0,240,255,0.25); font-size:0.8rem; font-family:'Space Grotesk',sans-serif;">
        <div style="flex: 3.5;">FILENAME</div>
        <div style="flex: 1.5;">TYPE</div>
        <div style="flex: 1;">LANGUAGE</div>
        <div style="flex: 1;">SIZE</div>
        <div style="flex: 0.7; text-align: center;">DEL</div>
    </div>
    ''', unsafe_allow_html=True)
    
    for f in files:
        c1,c2,c3,c4,c5 = st.columns([3.5, 1.5, 1, 1, 0.7])
        c1.write(f['filename'])
        c2.caption(f['file_type'])
        c3.caption(f['language'] or '—')
        size_kb = f"{f['size_bytes']//1024} KB" if f.get('size_bytes') else '0 KB'
        c4.caption(size_kb)
        if c5.button('🗑️', key=f"d_{f['id']}", use_container_width=True):
            delete_file(f['id'])
            # Reset explanation if database becomes empty
            remaining = get_all_files()
            if not remaining:
                if 'last_repo_readme' in st.session_state:
                    del st.session_state['last_repo_readme']
                if 'last_repo_explanation' in st.session_state:
                    del st.session_state['last_repo_explanation']
                if 'last_repo_name' in st.session_state:
                    del st.session_state['last_repo_name']
            st.rerun()

def render():
    inject_theme()
    st.markdown("### 📂  Dashboard")
    
    # Auto-load state if DB already has files
    ensure_readme_or_explanation()
    
    tab_ingest, tab_readme, tab_qa, tab_files = st.tabs([
        '📥  Ingestion & Repository',
        '📖  README & Explanation',
        '💬  Project Q&A',
        '🗄️  Indexed Files'
    ])
    
    with tab_ingest:
        render_ingestion_tabs()
        
    with tab_readme:
        st.markdown("### 📖  Project Overview")
        last_repo = st.session_state.get('last_repo_name')
        if last_repo:
            st.info(f"Showing analysis for: **{last_repo}**")
            readme_content = st.session_state.get('last_repo_readme')
            explanation_content = st.session_state.get('last_repo_explanation')
            
            if readme_content:
                st.success("✓ README.md file detected in repository")
                st.markdown("---")
                st.markdown(readme_content)
            elif explanation_content:
                st.warning("⚠️ No README.md file found. AI-Generated Project Explanation:")
                st.markdown("---")
                st.markdown(explanation_content)
        else:
            st.info("No repository has been analyzed yet. Ingest a repository to view its overview.")
            
    with tab_qa:
        st.markdown("### 💬  Project Q&A")
        st.write("Ask questions about the indexed codebase. The agent swarm will retrieve code context to answer.")
        
        if "chat_history" not in st.session_state:
            st.session_state["chat_history"] = []
            
        # Display chat history
        for chat in st.session_state["chat_history"]:
            with st.chat_message(chat["role"]):
                st.markdown(chat["content"])
                
        user_question = st.chat_input("Ask a question about the repository...")
        if user_question:
            with st.chat_message("user"):
                st.markdown(user_question)
            st.session_state["chat_history"].append({"role": "user", "content": user_question})
            
            with st.chat_message("assistant"):
                status_placeholder = st.empty()
                with st.spinner("Agent Swarm is analyzing code..."):
                    from agent_orchestrator import AgentOrchestrator
                    from services.database_service import DatabaseManager
                    
                    db_manager = DatabaseManager()
                    orchestrator = AgentOrchestrator(db_manager)
                    
                    steps_log = []
                    def show_step(step_name, data):
                        steps_log.append(f"🤖 **{step_name}**: {data.get('message', '')}")
                        status_placeholder.markdown("\n".join(steps_log))
                        
                    try:
                        result = orchestrator.run_workflow(user_question, on_step_callback=show_step)
                        status_placeholder.empty()
                        
                        with st.expander("🔍 Show Agent Execution Steps"):
                            for log in result.get("logs", []):
                                st.markdown(f"**{log['step']}** ({log['status'].upper()}): {log['message']}")
                                
                        st.markdown(result["answer"])
                        st.session_state["chat_history"].append({"role": "assistant", "content": result["answer"]})
                    except Exception as e:
                        status_placeholder.empty()
                        st.error(f"Failed to get answer: {e}")
                        
    with tab_files:
        render_files_table()
