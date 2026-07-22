# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

RepoLens: a single-page **Streamlit** app (Python) that ingests a public GitHub repo (branch ZIP download, no `git clone`), indexes every text file into a local **SQLite** file (`assistant.db`), shows a technical Project Overview plus the README (or an LLM-generated explanation if there isn't one), shows KPI stats + a searchable indexed-file browser + recent-question history, and answers questions about the indexed codebase via a floating RAG chat widget (with transcript export). The ingestion path never executes anything from the repo.

**⚠️ The README.md and walkthrough.md in this repo are stale — read them skeptically.** They describe a much larger app (CWE-tagged security-audit engine with Markdown/PDF export, Supabase-backed auth, a static HTML/CSS/JS preview sandbox, an in-app screenshot guide, and a separate multi-agent Planner/CodeSearch/DocSearch/Generator orchestrator). Commit `64d210e` ("Update code with latest changes") deleted ~2,360 lines that implemented all of that (`agent_orchestrator.py`, `components/auth_gate.py`, `pages/security_audit.py`, `services/audit_service.py`, `services/report_service.py`, `services/auth_store.py`, `pages/guide.py`, `assets/guide/*.png`). None of it exists in the working tree today. If asked to work on "the security audit" or "auth" or "the guide page," confirm first whether the goal is to restore that code (recoverable via `git show <commit>:<path>` from `4b1f8cb` or `d5716b8`, the parents of the deleting commit) or to build fresh.

Related stale detail: `assistant_audits` table and `save_audit`/`get_latest_audit`/`get_audit_history` still exist in `services/sqlite_service.py` and `services/database_service.py`, but nothing calls them anymore (the audit feature that wrote to them was deleted). `.env` also has live `SUPABASE_URL`/`SUPABASE_SERVICE_KEY`/`AUTH_COOKIE_KEY` values for an auth system that no longer exists in code.

**Note on Live Run:** commits `e3fbe09`..`c38f26c` added a "Live Runner" that pip-installed and executed a cloned repo's code *in-process*, tunneled publicly via `localtunnel`/Cloudflare Quick Tunnel; commit `4b1f8cb` deleted it as "fragile". A from-scratch, Docker-sandboxed "Live Run" feature was later prototyped (`services/runner_service.py`, `components/live_run.py`) but has since been removed at the user's request — don't re-add either version unless explicitly asked to build one fresh.

## Commands

```bash
# setup
python -m venv venv
venv\Scripts\activate            # Windows
source venv/bin/activate         # macOS/Linux
pip install -r requirements.txt

# run (dev)
streamlit run app.py --server.port 8505
# open http://localhost:8505

# run (deploy / prod-style, binds $PORT)
streamlit run app.py --server.port $PORT --server.address 0.0.0.0

# docker
docker compose up --build
```

There is no test suite, no linter config, and no build step — `requirements.txt` lists `streamlit`, `python-dotenv`, `google-genai`, `anthropic`, `openai`. Nothing in this repo's own image is TypeScript/JS or needs Docker-in-Docker; the Dockerfile is a plain `python:3.11-slim` build for running RepoLens itself.

## Configuration

All LLM configuration is **environment-variable only** — there is no in-app Settings page or key-entry UI in the current code (`README.md` claims otherwise; it's describing the deleted version). Copy `.env.example` to `.env`:

- `LLM_PROVIDER` — `gemini` | `openai` | `anthropic` (default `gemini`)
- `LLM_MODEL` — any model id for that provider (default is the provider's first entry in `services/llm_service.py::PROVIDERS`)
- `GEMINI_API_KEY` / `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` — only the one matching `LLM_PROVIDER` is required
- Semantic search (embeddings) is **Gemini-only** (`gemini-embedding-001`) regardless of chat provider — without `GEMINI_API_KEY`, `services/llm_service.py::embeddings_available()` returns `False` and everything falls back to SQLite keyword `LIKE` search (see `services/chat_service.py::ask_question` and `services/sqlite_service.py::keyword_search_chunks`). Nothing breaks; it just degrades.
- `SUPABASE_URL` / `SUPABASE_SERVICE_KEY` / `AUTH_COOKIE_KEY` are dead config — no code reads them currently.

## Architecture

```
app.py                      page config, .env load, session_state sanitation, header/theme, renders
                             pages.dashboard.render_unified_dashboard() then components.chat_widget.render_chat_widget()
theme.py                    TOKENS dict (light/dark) + PALETTES (single "Nebula Glass" entry) → one injected
                             <style> block; single source of visual truth, everything else styles via CSS custom
                             properties (var(--accent) etc.). There is no in-app theme/palette switcher.

pages/dashboard.py          the only page. GitHub URL parsing/private-repo check/ZIP download+filtering
                             (download_and_filter_repo), ingestion orchestration (clone_and_index, wrapped in a
                             loading spinner while the repo is fetched), LLM project explanation
                             (generate_project_explanation), a static technical Project Overview of RepoLens itself
                             (render_app_overview), and the render_* section functions composed by
                             render_unified_dashboard(): ingestion, repo details, a KPI stat row
                             (render_stats_row), the README/AI overview, an indexed-file browser with inline
                             preview + delete (render_files_browser), and a recent-questions log
                             (render_recent_queries).

components/
  cards.py                  presentational: metric_card (KPI tiles), severity_badge, section_header, empty_state,
                             file_type_chip (language/type pill, used by the file browser)
  chat_widget.py            floating bottom-right chat panel; gates on an actively-indexed repo matching the
                             ingest_url field; delegates Q&A to services.chat_service.ask_question; suggested-
                             question buttons track a single pending index in session state so only the clicked
                             suggestion shows its own spinner (others are disabled, not loading) while it resolves;
                             also renders chat transcript export (download_button) and clear
  status.py                 connection_badge, skeleton, error_boundary (still unused — available for future
                             error-boundary wiring)

services/                   pure Python, NO Streamlit imports (this boundary is intentional and currently honored —
                             preserve it; it's what keeps the ingestion/RAG/LLM logic reusable/testable outside the UI)
  llm_service.py            provider registry (PROVIDERS dict) behind one generate()/test_connection() interface;
                             env-driven only (active_provider/active_model/resolve_key all read os.getenv)
  chat_service.py           RAG: embeddings_available() ? vector search : keyword search → build prompt → generate()
  database_service.py       facade over sqlite_service + embedding orchestration (save_file chunks + embeds text,
                             chunk_text_by_lines does 40-line/5-line-overlap chunking)
  sqlite_service.py         owns the sqlite3 connection, schema (init_sqlite() runs at import time), and every raw
                             query; DB path is always <repo_root>/assistant.db
  embedding_service.py      get_embedding() — Gemini's gemini-embedding-001 model only
  similarity_service.py     cosine_similarity()
  github_service.py         pure GitHub helpers used by ingestion: parse_github_url, check_repo_private,
                             fetch_branch_zip_bytes (branch ZIP download w/ main→master fallback)
```

**Data flow for ingestion**: `render_ingestion_section` (dashboard.py) → `clone_and_index` → `download_and_filter_repo` (ZIP fetch, extension/size/path allowlist filtering, no execution) → `wipe_all()` (SQLite is single-repo-at-a-time — indexing a new repo replaces everything) → `insert_file_with_chunks` per file → `database_service.save_file` chunks the text and calls `embedding_service.get_embedding` per chunk → rows land in `assistant_files` / `assistant_file_chunks`.

**Data flow for chat**: `chat_widget.render_chat_widget` → `chat_service.ask_question` → vector or keyword chunk search → prompt assembly with `SYSTEM_PROMPT` → `llm_service.generate` → answer rendered + logged to `assistant_queries` via `database_service.insert_query_log`.

**Single-repo model**: the app only ever holds one indexed repository at a time (`wipe_all()` on every new ingest); "is a repo active" is determined by comparing the `ingest_url` text field against the `active_repo_url` setting row (`pages/dashboard.py::render_unified_dashboard`), not by a persistent selection concept.

**SQLite schema** (`services/sqlite_service.py::init_sqlite`, auto-created on import): `assistant_files`, `assistant_file_chunks` (embedding stored as JSON-encoded float array in a TEXT column), `assistant_queries`, `assistant_settings` (key/value), and the now-unused `assistant_audits`.

**Theming**: `theme.py::inject_theme(mode, palette_name)` is called once per run from `app.py`, before any other UI renders. Mode is `auto`/`light`/`dark` (auto = light `:root` + `@media (prefers-color-scheme: dark)` override), chosen via a `st.segmented_control` in the header (session key `ui_theme`). `PALETTES` holds a single locked-in entry, `"Nebula Glass"` — there is no in-app theme/palette picker; `app.py` always calls `inject_theme(st.session_state["ui_theme"], "Nebula Glass")`. Never hardcode colors in component code — add/read a CSS variable instead. If asked to add more palettes back, that's a deliberate reversal of a user decision — confirm first.

**Motion system** (`theme.py`): a small set of CSS custom properties (`--ease-out`, `--ease-in-out`, `--dur-fast/base/slow`) and keyframes (`dp-fade-up`, `dp-fade-in`, `dp-panel-in`, `dp-pulse-ring`, `dp-shimmer`, `dp-float`) drive all animation — entrance transitions on cards/KPI tiles/chat messages, a pulse ring on the idle chat launcher, a shimmer sweep on the ingestion progress bar and `.dp-skeleton` loaders, and a shine sweep on primary buttons. Everything is wrapped in a `prefers-reduced-motion` guard that collapses durations to ~0. Add new motion by reusing these tokens/keyframes rather than inventing ad hoc transitions.

**Streamlit version footgun — CSS selectors that assume DOM shape go stale silently across Streamlit versions.** This app targets Streamlit 1.58, whose DOM for `st.container(key=...)` changed from whatever version the original CSS was written against: children are wrapped in an unclassed `div[data-testid="stLayoutWrapper"]`, not the `.element-container` older selectors expected. This broke the chat panel's "pin input to bottom" flex CSS (the wrapper never got `flex-grow`, leaving the input stranded above dead space whenever the panel got taller) — fixed by targeting `.st-key-dp_chat_panel > *:has(.st-key-dp_chat_scroll)` instead of the old `.element-container` selector. If a layout/CSS rule silently stops working after any Streamlit upgrade, don't guess — dump the live DOM (`page.evaluate` in a headless browser) rather than trust old selectors. Separately, all interactive widgets in this codebase now have explicit `key=` values (a few `st.button()` calls didn't originally); that's just good practice for a multi-widget app like this, not a confirmed fix for anything specific.
