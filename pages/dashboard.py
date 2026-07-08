# pages/dashboard.py
import streamlit as st
import urllib.request
import urllib.error
import zipfile
import io
import json
import logging
import os
import subprocess
import queue
import threading
import time
import sys
import shlex
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

def read_output_stream(process, q):
    try:
        while True:
            char = process.stdout.read(1)
            if not char:
                break
            q.put(char)
    except Exception:
        pass
    finally:
        try:
            process.stdout.close()
        except Exception:
            pass

def extract_indexed_files_to_disk(repo_url: str, files: list) -> str:
    repo_path = parse_github_url(repo_url)
    if not repo_path:
        return None
    safe_dir_name = repo_path.replace("/", "_")
    target_dir = os.path.join("cloned_runs", safe_dir_name)
    os.makedirs(target_dir, exist_ok=True)
    
    for f in files:
        path = f["path"]
        content = f["content"]
        out_path = os.path.join(target_dir, path)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        
        # Write content (either as bytes or text string)
        if isinstance(content, str):
            with open(out_path, "w", encoding="utf-8", errors="ignore") as file_out:
                file_out.write(content)
        else:
            with open(out_path, "wb") as file_out:
                file_out.write(content)
                
    return target_dir

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
        # Extract files to disk for Live Runner execution
        try:
            extract_indexed_files_to_disk(repo_url, files)
        except Exception as e:
            logger.error(f"Failed to extract files to disk: {e}")
            
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

def render_ingestion_section():
    st.markdown("### 🐙  GitHub Repository Ingestion")
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

def detect_run_command(cloned_dir: str) -> dict:
    res = {
        "file": "",
        "command": "",
        "needs_setup": False,
        "setup_command": ""
    }
    if not os.path.exists(cloned_dir):
        return res
        
    has_reqs = os.path.exists(os.path.join(cloned_dir, "requirements.txt"))
    if has_reqs:
        res["needs_setup"] = True
        res["setup_command"] = "python -m pip install -r requirements.txt"
        
    # Scan files
    files = []
    for root, dirs, filenames in os.walk(cloned_dir):
        for f in filenames:
            ext = f.split(".")[-1].lower() if "." in f else ""
            if ext in ["py", "js", "bat", "sh"]:
                rel_path = os.path.relpath(os.path.join(root, f), cloned_dir)
                files.append((rel_path, ext))
                
    if not files:
        return res
        
    # Prioritize app.py, main.py, index.js, etc.
    priority_files = ["app.py", "main.py", "index.js", "app.js", "main.js"]
    selected_file = None
    selected_ext = None
    
    for pf in priority_files:
        for f, ext in files:
            if f.lower() == pf or f.lower().endswith("/" + pf):
                selected_file = f
                selected_ext = ext
                break
        if selected_file:
            break
            
    if not selected_file:
        non_setup_files = [x for x in files if "setup" not in x[0].lower() and "install" not in x[0].lower()]
        if non_setup_files:
            selected_file, selected_ext = non_setup_files[0]
        else:
            selected_file, selected_ext = files[0]
            
    res["file"] = selected_file
    
    # Determine command
    if selected_ext == "py":
        file_abs = os.path.join(cloned_dir, selected_file)
        is_streamlit = False
        try:
            with open(file_abs, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
                if "import streamlit" in content or "from streamlit" in content:
                    is_streamlit = True
        except Exception:
            pass
            
        if is_streamlit:
            res["command"] = f"python -m streamlit run {selected_file} --server.port 8501"
        else:
            res["command"] = f"python -u {selected_file}"
    elif selected_ext == "js":
        res["command"] = f"node {selected_file}"
    else:
        res["command"] = f"./{selected_file}" if os.name != "nt" else selected_file
        
    return res

def render_live_runner():
    st.markdown("### ⚡ Live Runner")
    st.write("Execute runnable files (.py, .js, .bat, .sh) from the analyzed repository locally.")
    
    last_exit = st.session_state.get("last_exit_code")
    if last_exit is not None:
        if last_exit == 0:
            st.success("✓ Process finished successfully (exit code 0)")
        elif last_exit == -1:
            st.warning("⚠️ Process terminated by user")
        else:
            st.error(f"✗ Process failed (exit code {last_exit})")
        st.session_state["last_exit_code"] = None
        
    last_repo = st.session_state.get('last_repo_name')
    if not last_repo:
        st.info("No repository has been analyzed yet. Please ingest a repository first.")
        return
        
    repo_path = parse_github_url(last_repo)
    if not repo_path:
        st.error("Invalid repository URL stored.")
        return
        
    safe_dir_name = repo_path.replace("/", "_")
    cloned_dir = os.path.join("cloned_runs", safe_dir_name)
    
    if not os.path.exists(cloned_dir):
        st.info("Local repository files do not exist on disk. Please re-analyze the repository to extract files.")
        return
        
    # Scan for executable files
    exec_files = []
    for root, dirs, files in os.walk(cloned_dir):
        for f in files:
            ext = f.split(".")[-1].lower() if "." in f else ""
            if ext in ["py", "js", "bat", "sh"]:
                rel_path = os.path.relpath(os.path.join(root, f), cloned_dir)
                exec_files.append(rel_path)
                
    if not exec_files:
        st.warning("No runnable files (.py, .js, .bat, .sh) found in the repository.")
        return
        
    # Detect default commands for auto-setup/run
    detected = detect_run_command(cloned_dir)
    
    st.markdown("#### 🤖 Automated Project Setup & Execution")
    st.write("Let the system automatically setup and launch the repository for you.")
    
    cols_auto = st.columns([3, 1])
    with cols_auto[0]:
        st.markdown(f"**Detected Runner Target:** `{detected['file']}`")
        if detected['needs_setup']:
            st.markdown(f"**Setup Command:** `{detected['setup_command']}` ➔ **Run Command:** `{detected['command']}`")
        else:
            st.markdown(f"**Run Command:** `{detected['command']}`")
            
    running_process = st.session_state.get("running_process")
    pending_commands = st.session_state.get("pending_commands", [])
    
    with cols_auto[1]:
        auto_btn = st.button("🚀 Auto-Setup & Run", disabled=(running_process is not None), use_container_width=True)
        
    if auto_btn:
        st.session_state["pending_commands"] = []
        if detected['needs_setup']:
            setup_cmd = detected['setup_command']
            st.session_state["pending_commands"] = [detected['command']]
            cmd_to_run = setup_cmd
        else:
            cmd_to_run = detected['command']
            
        cmd = shlex.split(cmd_to_run.strip())
        if cmd:
            if cmd[0] in ["python", "python3", "python.exe"]:
                cmd[0] = sys.executable
            elif cmd[0] == "streamlit":
                cmd = [sys.executable, "-m", "streamlit"] + cmd[1:]
                
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                errors="replace",
                cwd=cloned_dir
            )
            q = queue.Queue()
            t = threading.Thread(target=read_output_stream, args=(process, q))
            t.daemon = True
            t.start()
            
            st.session_state["running_process"] = process
            st.session_state["process_queue"] = q
            st.session_state["console_logs"] = [f"$ {cmd_to_run.strip()}\n"]
            st.rerun()
        except Exception as e:
            st.error(f"Failed to auto-start process: {e}")
            
    st.markdown("---")
    st.markdown("#### ⚙️ Manual Configuration")
    
    selected_file = st.selectbox("Select File to Run", exec_files)
    
    # Check for empty/incomplete duckdb file
    db_file_path = os.path.join(cloned_dir, "instacart.duckdb")
    if os.path.exists(db_file_path):
        size_mb = os.path.getsize(db_file_path) / (1024 * 1024)
        if size_mb < 50:
            st.warning(f"⚠️ **Empty/Incomplete Database Detected:** An empty database file `{db_file_path}` of size {size_mb:.2f} MB was found (probably created by running setup_db.py without CSV files). This will block `app.py` from automatically downloading the pre-built 1.2GB database from Google Drive.")
            if st.button("🗑️ Delete Empty Database File"):
                try:
                    os.remove(db_file_path)
                    st.success("✓ Deleted instacart.duckdb successfully! You can now run app.py to auto-download the database.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to delete database: {e}")
                    
    # Auto-generate default command based on selection
    default_cmd = ""
    if selected_file:
        ext = selected_file.split(".")[-1].lower()
        if ext == "py":
            # Check if file imports streamlit
            file_abs = os.path.join(cloned_dir, selected_file)
            is_streamlit = False
            try:
                with open(file_abs, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    if "import streamlit" in content or "from streamlit" in content:
                        is_streamlit = True
            except Exception:
                pass
                
            if is_streamlit:
                default_cmd = f"python -m streamlit run {selected_file} --server.port 8501"
            else:
                default_cmd = f"python -u {selected_file}"
        elif ext == "js":
            default_cmd = f"node {selected_file}"
        else:
            default_cmd = f"./{selected_file}" if os.name != "nt" else selected_file

    run_cmd_input = st.text_input("Command to Execute", value=default_cmd)
    
    if "streamlit" in run_cmd_input.lower():
        st.info("💡 **Streamlit Application Detected:** Running this command will start a Streamlit server in the background. If you are running locally, you can open the app in your browser (usually at http://localhost:8501). If running on Render, the server port is isolated but you will see the logs below.")
        
    has_reqs = os.path.exists(os.path.join(cloned_dir, "requirements.txt"))
    
    col_actions = st.columns([1, 1, 2])
    
    with col_actions[0]:
        run_btn = st.button("⚡ Run Code", disabled=(running_process is not None), use_container_width=True)
    with col_actions[1]:
        terminate_btn = st.button("🛑 Terminate", disabled=(running_process is None), use_container_width=True)
    with col_actions[2]:
        if has_reqs:
            install_btn = st.button("📦 Install Dependencies (pip)", disabled=(running_process is not None), use_container_width=True)
        else:
            install_btn = False
            
    if run_btn:
        st.session_state["pending_commands"] = []
        cmd = shlex.split(run_cmd_input.strip())
        if cmd:
            # Map python/streamlit to environment executable
            if cmd[0] in ["python", "python3", "python.exe"]:
                cmd[0] = sys.executable
            elif cmd[0] == "streamlit":
                cmd = [sys.executable, "-m", "streamlit"] + cmd[1:]
                
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                errors="replace",
                cwd=cloned_dir
            )
            q = queue.Queue()
            t = threading.Thread(target=read_output_stream, args=(process, q))
            t.daemon = True
            t.start()
            
            st.session_state["running_process"] = process
            st.session_state["process_queue"] = q
            st.session_state["console_logs"] = [f"$ {run_cmd_input.strip()}\n"]
            st.rerun()
        except Exception as e:
            st.error(f"Failed to start process: {e}")
            
    if install_btn:
        st.session_state["pending_commands"] = []
        cmd = [sys.executable, "-m", "pip", "install", "-r", "requirements.txt"]
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                errors="replace",
                cwd=cloned_dir
            )
            q = queue.Queue()
            t = threading.Thread(target=read_output_stream, args=(process, q))
            t.daemon = True
            t.start()
            
            st.session_state["running_process"] = process
            st.session_state["process_queue"] = q
            st.session_state["console_logs"] = [f"$ {' '.join(cmd)}\n"]
            st.rerun()
        except Exception as e:
            st.error(f"Failed to start dependency installation: {e}")
            
    if terminate_btn and running_process:
        running_process.terminate()
        st.session_state["running_process"] = None
        st.session_state["process_queue"] = None
        st.session_state["pending_commands"] = []
        st.session_state["last_exit_code"] = -1
        st.success("Process terminated by user.")
        st.rerun()
        
    q = st.session_state.get("process_queue")
    logs = st.session_state.get("console_logs", [])
    
    if logs:
        st.markdown("**Console Output:**")
        log_placeholder = st.empty()
        
        if q:
            while not q.empty():
                try:
                    line = q.get_nowait()
                    logs.append(line)
                except queue.Empty:
                    break
                    
        log_text = "".join(logs)
        log_placeholder.code(log_text, language="bash")
        
        if running_process:
            if running_process.poll() is None:
                time.sleep(0.1)
                st.rerun()
            else:
                if q:
                    while not q.empty():
                        try:
                            line = q.get_nowait()
                            logs.append(line)
                        except queue.Empty:
                            break
                    log_placeholder.code("".join(logs), language="bash")
                exit_code = running_process.returncode
                
                # Check for pending chained commands (like auto-setup transitioning to run)
                pending = st.session_state.get("pending_commands", [])
                if exit_code == 0 and pending:
                    next_cmd_str = pending.pop(0)
                    st.session_state["pending_commands"] = pending
                    
                    cmd = shlex.split(next_cmd_str.strip())
                    if cmd:
                        if cmd[0] in ["python", "python3", "python.exe"]:
                            cmd[0] = sys.executable
                        elif cmd[0] == "streamlit":
                            cmd = [sys.executable, "-m", "streamlit"] + cmd[1:]
                            
                    try:
                        next_process = subprocess.Popen(
                            cmd,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT,
                            text=True,
                            errors="replace",
                            cwd=cloned_dir
                        )
                        next_q = queue.Queue()
                        next_t = threading.Thread(target=read_output_stream, args=(next_process, next_q))
                        next_t.daemon = True
                        next_t.start()
                        
                        st.session_state["running_process"] = next_process
                        st.session_state["process_queue"] = next_q
                        st.session_state["console_logs"].append(f"\n$ {next_cmd_str.strip()}\n")
                        st.rerun()
                    except Exception as e:
                        st.session_state["running_process"] = None
                        st.session_state["process_queue"] = None
                        st.session_state["pending_commands"] = []
                        st.session_state["last_exit_code"] = -1
                        st.session_state["console_logs"].append(f"\nFailed to auto-start next command {next_cmd_str}: {e}\n")
                        st.rerun()
                else:
                    st.session_state["running_process"] = None
                    st.session_state["process_queue"] = None
                    st.session_state["pending_commands"] = []
                    st.session_state["last_exit_code"] = exit_code
                    st.rerun()

def render():
    inject_theme()
    st.markdown("### Dashboard")
    
    # Auto-load state if DB already has files
    ensure_readme_or_explanation()
    
    tab_ingest, tab_readme, tab_run, tab_files = st.tabs([
        '📥  Repository Ingestion',
        '📖  README & Explanation',
        '⚡  Live Runner',
        '🗄️  Indexed Files'
    ])
    
    with tab_ingest:
        render_ingestion_section()
        
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
            
    with tab_run:
        render_live_runner()
        
    with tab_files:
        render_files_table()
