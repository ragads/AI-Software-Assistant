# components/chat_widget.py
import streamlit as st
import services.chat_service as chat_service

def render_chat_widget():
    """Renders the AI Codebase Chat as a custom floating panel in the bottom-right corner."""
    from pages.dashboard import parse_github_url
    from services.database_service import get_setting, get_file_count

    url = st.session_state.get("ingest_url", "").strip()
    if not url:
        return

    entered_repo = parse_github_url(url)
    indexed_repo = parse_github_url(get_setting("active_repo_url", ""))
    
    if not entered_repo or not indexed_repo or entered_repo != indexed_repo:
        return

    # Check if there are files in database
    if get_file_count() == 0:
        return

    # Initialize chat state
    if "chat_open" not in st.session_state:
        st.session_state["chat_open"] = False
        
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    if "chat_maximized" not in st.session_state:
        st.session_state["chat_maximized"] = False

    # Sanitize chat history to only contain strings
    st.session_state["chat_history"] = [
        m for m in st.session_state["chat_history"]
        if isinstance(m, dict)
        and isinstance(m.get("role"), str)
        and isinstance(m.get("content"), str)
    ]

    # ── Launcher (round floating pulse button, bottom-right) ───────────────────
    with st.container(key="dp_chat_launcher"):
        if st.button("chat", key="dp_chat_toggle", help="Toggle AI Codebase Assistant"):
            st.session_state["chat_open"] = not st.session_state["chat_open"]
            st.rerun()

    if not st.session_state["chat_open"]:
        return

    # ── Floating Panel ────────────────────────────────────────────────────────
    with st.container(key="dp_chat_panel"):
        if st.session_state.get("chat_maximized", False):
            st.markdown(
                """
                <style>
                html body div.st-key-dp_chat_panel {
                    width: 750px !important;
                    height: 700px !important;
                    max-height: calc(100vh - 120px) !important;
                }
                .st-key-dp_chat_scroll {
                    flex-grow: 1 !important;
                    height: auto !important;
                }
                </style>
                """,
                unsafe_allow_html=True
            )

        # Header
        col_title, col_size, col_close = st.columns([12, 1, 1])
        with col_title:
            st.markdown(
                """
                <div style="padding-top: 2px;">
                    <div style="font-weight: 700; font-size: 0.95rem; color: var(--text-primary); line-height: 1.2;">AI Codebase Assistant</div>
                    <div style="font-size: 0.72rem; color: var(--text-muted);">Grounded in your repository index</div>
                </div>
                """,
                unsafe_allow_html=True
            )
        with col_size:
            with st.container(key="dp_chat_size"):
                if st.session_state.get("chat_maximized", False):
                    if st.button("⤨", key="dp_chat_size_btn", help="Minimize/Restore"):
                        st.session_state["chat_maximized"] = False
                        st.rerun()
                else:
                    if st.button("⤢", key="dp_chat_size_btn", help="Maximize"):
                        st.session_state["chat_maximized"] = True
                        st.rerun()
        with col_close:
            with st.container(key="dp_chat_close"):
                if st.button("✕", key="dp_chat_close_btn", help="Close chat"):
                    st.session_state["chat_open"] = False
                    st.rerun()

        # Messages Scroll Area
        with st.container(key="dp_chat_scroll"):
            if not st.session_state["chat_history"]:
                st.caption("Ask questions about the repository files, libraries, or architecture.")
                
                st.markdown(
                    """
                    <div style="font-size: 0.8rem; font-weight: 600; margin-bottom: 6px; color: var(--text-secondary);">Suggested Questions:</div>
                    """,
                    unsafe_allow_html=True
                )
                
                sugs = [
                    "Explain the project architecture",
                    "What languages are used in this codebase?",
                    "Can you summarize the main components?"
                ]
                for idx, sug in enumerate(sugs):
                    if st.button(sug, key=f"sug_btn_{idx}", use_container_width=True):
                        st.session_state["chat_history"].append({"role": "user", "content": sug})
                        st.rerun()
            else:
                for msg in st.session_state["chat_history"]:
                    with st.chat_message(msg["role"]):
                        st.markdown(msg["content"])

                # If last message is from user, generate response
                if st.session_state["chat_history"][-1]["role"] == "user":
                    user_prompt = st.session_state["chat_history"][-1]["content"]
                    with st.chat_message("assistant"):
                        with st.spinner("Analyzing codebase..."):
                            try:
                                response = chat_service.ask_question(user_prompt)
                                if not isinstance(response, str):
                                    response = str(response)
                            except Exception as e:
                                response = f"Failed to get response: {e}"
                            st.markdown(response)
                    st.session_state["chat_history"].append({"role": "assistant", "content": response})
                    st.rerun()

        # Input Field (styled inline inside the panel)
        prompt = st.chat_input("Ask about this codebase...", key="dp_chat_input")
        if prompt:
            st.session_state["chat_history"].append({"role": "user", "content": prompt.strip()})
            st.rerun()

        # Export / Clear
        if st.session_state["chat_history"]:
            col_export, col_clear = st.columns(2)
            with col_export:
                transcript = "\n\n".join(
                    f"**{'You' if m['role'] == 'user' else 'Assistant'}:** {m['content']}"
                    for m in st.session_state["chat_history"]
                )
                st.download_button(
                    "Export", data=transcript, file_name="repolens_chat.md",
                    mime="text/markdown", key="export_chat_panel_btn", use_container_width=True,
                )
            with col_clear:
                if st.button("Clear Chat", key="clear_chat_panel_btn", use_container_width=True):
                    st.session_state["chat_history"] = []
                    st.rerun()

