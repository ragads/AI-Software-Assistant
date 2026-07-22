# pages/dashboard.py
"""UI sections for RepoLens.

Contains GitHub ingestion, repository overview, and AI Codebase Chat.
"""
import base64
import io
import logging
import os
import posixpath
import re
import zipfile

import streamlit as st

from components.cards import empty_state, file_type_chip, metric_card, section_header
from services import llm_service
from services import chat_service
from services.github_service import (
    check_repo_private,
    fetch_branch_zip_bytes,
    parse_github_url,
)
from services.database_service import (
    LANGUAGE_MAPPING,
    delete_file,
    get_all_files,
    get_chunk_count,
    get_file_content,
    get_file_count,
    get_language_breakdown,
    get_query_count,
    get_recent_queries,
    get_storage_label,
    insert_file_with_chunks,
    wipe_all,
    get_setting,
    set_setting,
)

logger = logging.getLogger("pages_dashboard")


# ══════════════════════════════════════════════════════════════════════
# GitHub Ingestion
# ══════════════════════════════════════════════════════════════════════
# parse_github_url / check_repo_private / fetch_branch_zip_bytes live in
# services.github_service (pure helpers shared with ingestion).


def download_and_filter_repo(repo_url: str, branch: str) -> list:
    repo_path = parse_github_url(repo_url)
    if not repo_path:
        raise ValueError("Invalid GitHub URL. Use https://github.com/owner/repository")

    zip_data = fetch_branch_zip_bytes(repo_path, branch)

    allowed_exts = set(LANGUAGE_MAPPING) | {
        "yml", "toml", "sql", "sh", "bat", "ini", "cfg", "properties", "xml", "csv",
    }
    allowed_names = {"dockerfile", "license", "procfile", "gemfile", "makefile"}

    files_list = []
    with zipfile.ZipFile(io.BytesIO(zip_data)) as z:
        for name in z.namelist():
            if name.endswith("/"):
                continue
            parts = name.split("/", 1)
            clean_name = parts[1] if len(parts) > 1 else name

            if (
                any(p.startswith(".") for p in clean_name.split("/"))
                or "node_modules/" in clean_name
                or "venv/" in clean_name
                or "__pycache__/" in clean_name
            ):
                continue

            ext = clean_name.rsplit(".", 1)[-1].lower() if "." in clean_name else ""
            base_name = clean_name.split("/")[-1].lower()
            if ext not in allowed_exts and base_name not in allowed_names:
                continue

            try:
                if z.getinfo(name).file_size > 300 * 1024:
                    continue
            except Exception:
                pass

            try:
                files_list.append({"path": clean_name, "content": z.read(name)})
            except Exception:
                pass
    return files_list


def clone_and_index(repo_url: str, branch: str):
    if not parse_github_url(repo_url):
        st.error("Invalid GitHub URL. Use https://github.com/owner/repository")
        return

    try:
        with st.spinner(f"Loading repository {repo_url}…"):
            if check_repo_private(repo_url):
                st.error("This repository is private, so it can't be accessed.")
                return
            files = download_and_filter_repo(repo_url, branch)

        if not files:
            st.warning("No indexable text files found in that repository.")
            return

        progress = st.progress(0)
        status = st.empty()

        # Wipe existing database rows and old state
        wipe_all()
        st.session_state["last_repo_readme"] = None
        st.session_state["last_repo_explanation"] = None
        st.session_state["chat_history"] = []

        for i, f in enumerate(files):
            status.markdown(f"`Indexing {f['path']}`")
            insert_file_with_chunks(f)
            progress.progress((i + 1) / len(files))

        progress.empty()
        status.success(f"Indexed {len(files)} files from {repo_url}")

        readme = next(
            (
                f
                for f in files
                if f["path"].lower() in ("readme.md", "readme.txt")
                or f["path"].lower().endswith(("/readme.md", "/readme.txt"))
            ),
            None,
        )
        if readme:
            content = readme["content"]
            if isinstance(content, bytes):
                content = content.decode("utf-8", errors="ignore")
            st.session_state["last_repo_readme"] = content
            st.session_state["last_repo_explanation"] = None
        else:
            st.session_state["last_repo_readme"] = None
            st.session_state["last_repo_explanation"] = generate_project_explanation(files)

        st.session_state["last_repo_name"] = repo_url
        set_setting("active_repo_url", repo_url)
        set_setting("active_branch", branch)
        st.rerun()
    except Exception as ex:  # noqa: BLE001
        st.error(f"Failed to clone and index repository: {ex}")


# ══════════════════════════════════════════════════════════════════════
# LLM-backed project explanation
# ══════════════════════════════════════════════════════════════════════
def call_gemini(prompt: str, system_instruction: str = "") -> str:
    return llm_service.generate(system_instruction, prompt)


def generate_project_explanation(files: list) -> str:
    paths = [f["path"] for f in files]
    file_structure = "\n".join(paths[:100])
    if len(paths) > 100:
        file_structure += f"\n... and {len(paths) - 100} more files."

    key_files = ["app.py", "main.py", "index.js", "package.json",
                 "requirements.txt", "setup.py", "cargo.toml", "go.mod"]
    contexts = []
    for f in files:
        if len(contexts) >= 5:
            break
        if any(k in f["path"].lower() for k in key_files):
            content = f["content"]
            if isinstance(content, bytes):
                content = content.decode("utf-8", errors="ignore")
            contexts.append(f"File: {f['path']}\nContent:\n{content[:1500]}")

    prompt = f"""A user uploaded a GitHub repository that has no README.
Generate a clear explanation of the project covering:
1. **Purpose** — what is this project for?
2. **Structure** — outline the folder and file layout.
3. **Design** — architecture, patterns, and libraries used.

Use professional markdown formatting.

File structure:
```
{file_structure}
```

Key file contents:
{chr(10).join(contexts)}
"""
    try:
        return call_gemini(prompt, "You are an expert software architect.")
    except llm_service.LLMNotConfigured as e:
        return f"_{e}_"
    except Exception as e:  # noqa: BLE001
        return f"Failed to generate project explanation: {e}"


def ensure_readme_or_explanation():
    if st.session_state.get("last_repo_readme") or st.session_state.get(
        "last_repo_explanation"
    ):
        return

    files = get_all_files()
    if not files:
        return

    readme_id = next(
        (
            f["id"]
            for f in files
            if f["filename"].lower() in ("readme.md", "readme.txt", "readme.markdown", "readme")
            or f["filename"].lower().endswith(("/readme.md", "/readme.txt"))
        ),
        None,
    )

    st.session_state["last_repo_name"] = st.session_state.get(
        "last_repo_name", get_setting("active_repo_url", "Currently Indexed Workspace")
    )

    if readme_id:
        st.session_state["last_repo_readme"] = get_file_content(readme_id).get("content")
        st.session_state["last_repo_explanation"] = None
    else:
        st.session_state["last_repo_readme"] = None
        db_files = [
            {"path": f["filename"], "content": get_file_content(f["id"]).get("content", "")}
            for f in files[:50]
        ]
        st.session_state["last_repo_explanation"] = generate_project_explanation(db_files)


# ══════════════════════════════════════════════════════════════════════
# Dashboard Sections
# ══════════════════════════════════════════════════════════════════════


def render_app_overview():
    """Static, technical explanation of RepoLens itself (not the ingested repo)."""
    st.markdown(
        """
**Purpose** — RepoLens ingests a public GitHub repository (branch ZIP download,
no `git clone`, nothing executed) and lets you browse and ask questions about
its codebase through a local index and an LLM-powered chat assistant.

**Architecture** — A single-page Streamlit app backed by a local SQLite file
(`assistant.db`). Ingested files are chunked and stored, then optionally
embedded (Gemini `gemini-embedding-001`) for semantic search — falling back to
SQLite keyword search when no Gemini key is configured. Chat answers are
generated by a pluggable LLM provider (Gemini, Anthropic, or OpenAI), selected
via environment variables.

**Key components**
- `pages/dashboard.py` — ingestion, repository overview, KPIs, file browser
- `components/chat_widget.py` — floating RAG chat panel
- `services/llm_service.py` — multi-provider LLM interface
- `services/chat_service.py` — retrieval + prompt assembly for Q&A
- `services/sqlite_service.py` / `database_service.py` — storage and indexing
        """
    )


def render_repo_details():
    st.markdown('<div class="dp-overline">Repository Info</div>', unsafe_allow_html=True)
    repo = st.session_state.get("last_repo_name", "—")
    st.markdown(
        f'<div style="color:var(--text-primary);font-size:0.9rem;padding:6px 0;border-bottom:1px solid var(--border);">'
        f'<span style="font-weight:600;">Active Repository:</span> {repo}'
        f'</div>',
        unsafe_allow_html=True,
    )
    
    st.markdown('<div class="dp-overline" style="margin-top:16px;">Languages</div>', unsafe_allow_html=True)
    langs = get_language_breakdown()
    if langs:
        for lang, count in langs.items():
            st.markdown(
                f'<div class="dp-lang-row">'
                f'<span style="color:var(--text-primary);font-size:0.875rem;font-weight:500;">{lang}</span>'
                f'<span style="color:var(--text-muted);font-size:0.875rem;">{count} files</span>'
                f"</div>",
                unsafe_allow_html=True,
            )
    else:
        st.caption("No language breakdown available.")

    if not llm_service.embeddings_available():
        st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)
        st.info(
            "No Gemini key found. Chunks are stored without embeddings. "
            "Set `GEMINI_API_KEY` to enable semantic search."
        )


def render_ingestion_section():
    st.markdown('<div class="dp-overline">WORKSPACE INGESTION</div>', unsafe_allow_html=True)
    
    st.session_state.setdefault("ingest_url", "")
    st.session_state.setdefault("ingest_branch", "main")

    def reset_workspace():
        wipe_all()
        st.session_state["ingest_url"] = ""
        st.session_state["ingest_branch"] = "main"
        st.session_state["last_repo_name"] = None
        st.session_state["last_repo_readme"] = None
        st.session_state["last_repo_explanation"] = None
        st.session_state["chat_history"] = []

    repo_url = st.text_input("GitHub URL", key="ingest_url",
                             placeholder="https://github.com/owner/repo")
    branch = st.text_input("Branch", key="ingest_branch")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Analyze Repository", key="analyze_repo_btn", type="primary", use_container_width=True):
            if repo_url:
                clone_and_index(repo_url, branch)
            else:
                st.error("Enter a repository URL first.")
    with col2:
        st.button("Refresh Repository", key="refresh_repo_btn", type="secondary",
                  use_container_width=True, on_click=reset_workspace)


def render_project_overview():
    section_header("Project Overview", "README, or an AI-generated explanation if none exists.", level=2)

    # Validate active repository presence
    active_url = st.session_state.get("ingest_url", "").strip()
    if not active_url:
        empty_state("◇", "No repository analyzed",
                    "Ingest a repository to see its overview here.")
        return

    ensure_readme_or_explanation()
    repo = st.session_state.get("last_repo_name")
    if not repo:
        empty_state("◇", "No repository analyzed",
                    "Ingest a repository to see its overview here.")
        return

    st.caption(f"Showing analysis for {repo}")
    readme = st.session_state.get("last_repo_readme")
    explanation = st.session_state.get("last_repo_explanation")

    if readme:
        st.success("README detected in repository")
        st.markdown("---")
        st.markdown(readme)
    elif explanation:
        st.warning("No README found — showing an AI-generated explanation")
        st.markdown("---")
        st.markdown(explanation)
    else:
        empty_state("◇", "Nothing to show", "No README or explanation available.")


def render_stats_row():
    with st.container(key="stats_row"):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            metric_card("◧", "Files Indexed", get_file_count(), tone="accent")
        with c2:
            metric_card("◫", "Chunks Stored", get_chunk_count(), tone="low")
        with c3:
            metric_card("◨", "Storage Used", get_storage_label(), tone="success")
        with c4:
            metric_card("◪", "Questions Asked", get_query_count(), tone="medium")


def render_files_browser():
    files = get_all_files()
    if not files:
        empty_state("◇", "No files indexed", "Ingest a repository to browse its files here.")
        return

    search = st.text_input(
        "Search files", key="files_search", placeholder="Filter by filename…",
        label_visibility="collapsed",
    )
    filtered = [f for f in files if search.lower() in f["filename"].lower()] if search else files

    shown = filtered[:150]
    caption = f"{len(filtered)} of {len(files)} files"
    if len(filtered) > len(shown):
        caption += f" — showing first {len(shown)}, refine your search to see more"
    st.caption(caption)

    for f in shown:
        with st.container(key=f"file_row_{f['id']}"):
            st.markdown(
                f'<div class="dp-row">'
                f'<div style="display:flex;align-items:center;gap:10px;overflow:hidden;min-width:0;">'
                f'<span style="font-family:var(--font-mono);font-size:0.8125rem;color:var(--text-primary);'
                f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{f["filename"]}</span>'
                f'{file_type_chip(f["language"] or "text")}'
                f'</div>'
                f'<span style="color:var(--text-muted);font-size:0.75rem;white-space:nowrap;flex:0 0 auto;">'
                f'{f["size_bytes"] / 1024:.1f} KB</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
            with st.expander("Preview / delete", expanded=False):
                content = get_file_content(f["id"]).get("content", "") or ""
                st.code(content[:5000], language=f["language"] or "text", line_numbers=True)
                if len(content) > 5000:
                    st.caption(f"Showing first 5,000 of {len(content):,} characters.")
                if st.button("Delete file", key=f"del_file_{f['id']}", type="secondary"):
                    delete_file(f["id"])
                    st.rerun()


def render_recent_queries():
    queries = get_recent_queries(8)
    if not queries:
        empty_state("◇", "No questions yet", "Ask the AI Codebase Assistant a question to see history here.")
        return

    for idx, q in enumerate(queries):
        with st.container(key=f"query_row_{idx}"):
            st.markdown(
                f'<div class="dp-row" style="flex-direction:column;align-items:flex-start;gap:4px;">'
                f'<span style="color:var(--text-primary);font-size:0.875rem;font-weight:500;">{q["question"]}</span>'
                f'<span style="color:var(--text-muted);font-size:0.75rem;">{q["created_at"]}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
            with st.expander("Answer", expanded=False):
                st.markdown(q.get("answer") or "_No answer recorded._")


# ══════════════════════════════════════════════════════════════════════
# Main Entry Point
# ══════════════════════════════════════════════════════════════════════
def render_unified_dashboard():
    st.markdown('<div style="height: 10px;"></div>', unsafe_allow_html=True)

    with st.expander("◆  Project Overview", expanded=False):
        render_app_overview()

    if "ingest_url" not in st.session_state:
        st.session_state["ingest_url"] = ""
    if "ingest_branch" not in st.session_state:
        st.session_state["ingest_branch"] = "main"

    files = get_all_files()

    db_url = get_setting("active_repo_url", "")
    entered_url = st.session_state.get("ingest_url", "").strip()
    
    entered_repo = parse_github_url(entered_url)
    indexed_repo = parse_github_url(db_url)
    
    is_active = bool(entered_repo and indexed_repo and entered_repo == indexed_repo and files)
    
    if is_active:
        # Sync last_repo_name
        st.session_state["last_repo_name"] = db_url
        
        # 1. Ingestion & Repository details side-by-side
        col_left, col_right = st.columns([1.1, 0.9])
        with col_left:
            with st.container(key="ingest_card"):
                render_ingestion_section()
        with col_right:
            with st.container(key="details_card"):
                render_repo_details()

        st.markdown("---")

        # 2. Workspace KPIs
        render_stats_row()

        st.markdown("---")

        # 3. Repo Overview (README / AI Explanation)
        with st.expander("◇  Repository Overview & Architecture", expanded=True):
            render_project_overview()

        # 4. Indexed file browser
        with st.expander("🗂  Indexed Files", expanded=False):
            render_files_browser()

        # 5. Past questions asked via the AI Codebase Assistant
        with st.expander("🕐  Recent Questions", expanded=False):
            render_recent_queries()
    else:
        # Centered ingestion section when no active repository is entered/loaded
        col_left, col_mid, col_right = st.columns([0.2, 0.6, 0.2])
        with col_mid:
            with st.container(key="ingest_card"):
                render_ingestion_section()

