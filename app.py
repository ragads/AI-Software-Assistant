# app.py
import importlib

import streamlit as st
from dotenv import load_dotenv

st.set_page_config(
    page_title="RepoLens",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# .env is the local fallback; on Render the real env vars are already present.
load_dotenv()

# Keep page-local widget values alive across navigation. Streamlit purges a
# widget-keyed session value when its page isn't rendered; re-touching these
# before the widgets are recreated preserves the theme and the ingest URL/branch
# when switching sections.
for _k in ("ui_theme", "ui_theme_palette", "ingest_url", "ingest_branch"):
    if _k in st.session_state:
        st.session_state[_k] = st.session_state[_k]

# Sanitize chat_history — remove any entries whose content/role is not a plain str.
# This cleans up corrupted state from older versions that accidentally stored
# Streamlit DeltaGenerator objects inside the history list.
if "chat_history" in st.session_state:
    st.session_state["chat_history"] = [
        m for m in st.session_state["chat_history"]
        if isinstance(m, dict)
        and isinstance(m.get("role"), str)
        and isinstance(m.get("content"), str)
    ]

import theme
importlib.reload(theme)
from theme import inject_theme  # noqa: E402

# Ensure defaults are only ever set once — session state, not clobbered every rerun.
if "ui_theme" not in st.session_state:
    st.session_state["ui_theme"] = "light"
st.session_state.setdefault("ui_theme_palette", "Nebula Glass")

# Palette must be resolved before inject_theme() runs the stylesheet.
inject_theme(st.session_state["ui_theme"], st.session_state["ui_theme_palette"])

# ── Unified Dashboard Header ───────────────────────────────────────────
with st.container(key="app_header"):
    col_logo, col_palette, col_mode, col_badge = st.columns([1.25, 0.55, 0.85, 0.35])
    with col_logo:
        st.markdown(
            """
            <div class="dp-logo-wrap" style="display: flex; align-items: center; gap: 12px; padding: 0;">
              <div class="dp-logo-mark" style="flex: 0 0 auto; line-height: 0;">
                <svg width="34" height="34" viewBox="0 0 32 32" fill="none"
                     xmlns="http://www.w3.org/2000/svg" aria-label="RepoLens">
                   <defs>
                     <linearGradient id="dpg" x1="4" y1="2" x2="28" y2="30"
                         gradientUnits="userSpaceOnUse">
                       <stop stop-color="#818CF8"/><stop offset="1" stop-color="#4F46E5"/>
                     </linearGradient>
                   </defs>
                   <path d="M16 1.8 L28.3 9 L28.3 23 L16 30.2 L3.7 23 L3.7 9 Z"
                         fill="url(#dpg)"/>
                   <path d="M6.5 16.5 H10 L12.3 10.5 L15.8 22 L18.6 13.5 L20.2 16.5 H25.5"
                         stroke="#fff" stroke-width="1.9"
                         stroke-linecap="round" stroke-linejoin="round"/>
                 </svg>
              </div>
              <div class="dp-logo-text" style="font-size: 1.4rem; font-weight: 700;">RepoLens</div>
            </div>""",
            unsafe_allow_html=True,
        )
    with col_palette:
        st.selectbox(
            "Palette",
            options=list(theme.PALETTES.keys()),
            key="ui_theme_palette",
            label_visibility="collapsed",
        )
    with col_mode:
        st.segmented_control(
            "Appearance Mode",
            options=["auto", "light", "dark"],
            format_func=lambda o: {"auto": "Auto", "light": "Light", "dark": "Dark"}[o],
            key="ui_theme",
            label_visibility="collapsed",
            required=True,
        )
    with col_badge:
        st.markdown('<div style="display: flex; justify-content: flex-end; align-items: center; height: 100%; padding-top: 6px;">', unsafe_allow_html=True)
        from components.status import connection_badge
        connection_badge("SQLite Connected")
        st.markdown('</div>', unsafe_allow_html=True)

st.markdown('<div style="height: 15px;"></div>', unsafe_allow_html=True)

try:
    from pages.dashboard import render_unified_dashboard
    render_unified_dashboard()
except Exception as exc:  # noqa: BLE001 - top-level UI boundary
    st.error(f"Failed to render dashboard: {exc}")
    st.exception(exc)

from components.chat_widget import render_chat_widget
render_chat_widget()
