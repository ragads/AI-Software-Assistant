# theme.py
"""Clean modern SaaS theme.

All visual tokens live in TOKENS. The stylesheet is emitted once and every rule
reads from a CSS custom property, so light and dark come from the same source.

mode="auto"  -> light :root + a prefers-color-scheme:dark override (follows OS)
mode="light" -> light :root only
mode="dark"  -> dark :root only
"""
import streamlit as st

TOKENS = {
    "light": {
        "bg": "#F7F8FA",
        "surface": "#FFFFFF",
        "surface-2": "#F1F5F9",
        "border": "#E2E8F0",
        "border-strong": "#CBD5E1",
        "text-primary": "#0F172A",
        "text-secondary": "#475569",
        "text-muted": "#94A3B8",
        "accent": "#4F46E5",
        "accent-hover": "#4338CA",
        "accent-soft": "#EEF2FF",
        "accent-rgb": "79,70,229",
        "focus-ring": "rgba(79,70,229,0.35)",
        # severity / semantic
        "critical": "#DC2626",
        "critical-soft": "#FEE2E2",
        "high": "#EA580C",
        "high-soft": "#FFEDD5",
        "medium": "#D97706",
        "medium-soft": "#FEF3C7",
        "low": "#2563EB",
        "low-soft": "#DBEAFE",
        "info": "#475569",
        "info-soft": "#F1F5F9",
        "success": "#16A34A",
        "success-soft": "#DCFCE7",
        # elevation
        "shadow-xs": "0 1px 2px rgba(16,24,40,.05)",
        "shadow-sm": "0 1px 3px rgba(16,24,40,.06), 0 1px 2px rgba(16,24,40,.04)",
        "shadow-md": "0 4px 12px rgba(16,24,40,.08)",
        "shadow-lg": "0 12px 24px rgba(16,24,40,.10)",
        "bg-image": "none",
        "card-blur": "0px",
    },
    "dark": {
        "bg": "#0B0F1A",
        "surface": "#131926",
        "surface-2": "#1A2233",
        "border": "#232B3D",
        "border-strong": "#33405A",
        "text-primary": "#E6EAF2",
        "text-secondary": "#9BA6BC",
        "text-muted": "#6B7688",
        "accent": "#6366F1",
        "accent-hover": "#818CF8",
        "accent-soft": "rgba(99,102,241,0.14)",
        "accent-rgb": "99,102,241",
        "focus-ring": "rgba(99,102,241,0.45)",
        "critical": "#F87171",
        "critical-soft": "rgba(248,113,113,0.14)",
        "high": "#FB923C",
        "high-soft": "rgba(251,146,60,0.14)",
        "medium": "#FBBF24",
        "medium-soft": "rgba(251,191,36,0.14)",
        "low": "#60A5FA",
        "low-soft": "rgba(96,165,250,0.14)",
        "info": "#94A3B8",
        "info-soft": "rgba(148,163,184,0.14)",
        "success": "#4ADE80",
        "success-soft": "rgba(74,222,128,0.14)",
        "shadow-xs": "0 1px 2px rgba(0,0,0,.3)",
        "shadow-sm": "0 1px 2px rgba(0,0,0,.4)",
        "shadow-md": "0 6px 16px rgba(0,0,0,.5)",
        "shadow-lg": "0 16px 32px rgba(0,0,0,.55)",
        "bg-image": "none",
        "card-blur": "0px",
    },
}

# Non-color tokens are theme-independent.
STATIC_TOKENS = {
    "radius-sm": "6px",
    "radius-md": "10px",
    "radius-lg": "14px",
    "radius-full": "9999px",
    "font-ui": "'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    "font-mono": "'JetBrains Mono', 'SFMono-Regular', Consolas, monospace",
}

SEVERITY_LEVELS = ("critical", "high", "medium", "low", "info", "success")


def _vars(mode: str) -> str:
    """Render a token dict as CSS custom property declarations."""
    pairs = {**STATIC_TOKENS, **TOKENS[mode]}
    return "\n".join(f"    --{k}: {v};" for k, v in pairs.items())


def _token_layer(mode: str) -> str:
    if mode == "light":
        return f":root {{\n{_vars('light')}\n}}"
    if mode == "dark":
        return f":root {{\n{_vars('dark')}\n}}"
    # auto: light default + OS dark override
    return (
        f":root {{\n{_vars('light')}\n}}\n\n"
        f"@media (prefers-color-scheme: dark) {{\n"
        f"  :root {{\n{_vars('dark')}\n  }}\n}}"
    )


_STYLES = """
/* ── Motion system ────────────────────────────────────── */
:root {
    --ease-out: cubic-bezier(0.16, 1, 0.3, 1);
    --ease-in-out: cubic-bezier(0.4, 0, 0.2, 1);
    --dur-fast: 150ms;
    --dur-base: 240ms;
    --dur-slow: 420ms;
}
@keyframes dp-fade-up {
    from { opacity: 0; transform: translateY(10px); }
    to   { opacity: 1; transform: translateY(0); }
}
@keyframes dp-fade-in {
    from { opacity: 0; }
    to   { opacity: 1; }
}
@keyframes dp-panel-in {
    from { opacity: 0; transform: translateY(16px) scale(.97); }
    to   { opacity: 1; transform: translateY(0) scale(1); }
}
@keyframes dp-pulse-ring {
    0%   { box-shadow: 0 0 0 0 rgba(var(--accent-rgb), .40); }
    70%  { box-shadow: 0 0 0 14px rgba(var(--accent-rgb), 0); }
    100% { box-shadow: 0 0 0 0 rgba(var(--accent-rgb), 0); }
}
@keyframes dp-shimmer {
    0%   { background-position: -300% 0; }
    100% { background-position: 300% 0; }
}
@keyframes dp-float {
    0%, 100% { transform: translateY(0); }
    50%      { transform: translateY(-6px); }
}
/* Respect the OS-level reduced-motion preference — everything above becomes
   an instant cut instead of a forced animation. */
@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
        animation-duration: 0.001ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.001ms !important;
        scroll-behavior: auto !important;
    }
}

/* ── Base ─────────────────────────────────────────────── */
.stApp {
    background-color: var(--bg) !important;
    background-image: var(--bg-image) !important;
    background-attachment: fixed !important;
    background-size: cover !important;
    color: var(--text-primary) !important;
    font-family: var(--font-ui) !important;
}
.block-container {
    max-width: 1160px !important;
    padding-top: 1.25rem !important;
    padding-bottom: 3rem !important;
}
#MainMenu, footer, [data-testid="stDecoration"], [data-testid="stStatusWidget"],
[data-testid="stMainMenuButton"], [data-testid="stToolbarActions"],
[data-testid="stAppDeployButton"], [data-testid="stAppViewBlockSpacer"] {
    display: none !important;
}
/* Keep the header AND toolbar mounted. Streamlit renders the sidebar expand
   button (stExpandSidebarButton) inside stToolbar; display:none-ing the toolbar
   makes it 0x0, so a collapsed sidebar can never be reopened. Collapse the
   header to zero height instead and let the expand button escape via position:fixed. */
header[data-testid="stHeader"] {
    background: transparent !important;
    height: 0 !important;
    min-height: 0 !important;
    overflow: visible !important;
}
[data-testid="stToolbar"] {
    background: transparent !important;
    padding: 0 !important;
    right: auto !important;
}
body:has(section[data-testid="stSidebar"][aria-expanded="false"])
    [data-testid="stExpandSidebarButton"]:hover { background: var(--surface-2) !important; }
/* The glyph is a Material Symbols ligature, but this button sits in <header>,
   outside .stApp, so it falls back to Inter and renders as an empty box. Draw
   the chevron with CSS instead — no icon-font dependency. */
[data-testid="stExpandSidebarButton"] span { display: none !important; }
[data-testid="stExpandSidebarButton"]::after {
    content: "»";
    color: var(--text-secondary);
    font-size: 17px; font-weight: 700; line-height: 1;
}
/* Streamlit reserves a tall empty header row for the collapse control. Kill that
   space so the logo sits at the very top, and ride the collapse toggle on the
   sidebar's right border line instead of floating above the logo. */
[data-testid="stSidebarHeader"] {
    height: 0 !important; min-height: 0 !important;
    padding: 0 !important; margin: 0 !important;
}
[data-testid="stSidebarCollapseButton"] {
    position: absolute !important;
    top: 14px !important;
    right: -11px !important;    /* offsets the sidebar's inner padding so the… */
    transform: translateX(50%) !important;   /* …button centers on the border line */
    z-index: 1200 !important;
    visibility: visible !important; opacity: 1 !important;
}
[data-testid="stSidebarCollapseButton"] button {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
    width: 26px !important; height: 26px !important; min-height: 26px !important;
    padding: 0 !important;
    box-shadow: var(--shadow-sm) !important;
}
[data-testid="stSidebarCollapseButton"] button:hover { background: var(--surface-2) !important; }
[data-testid="stSidebarCollapseButton"] button span { display: none !important; }
[data-testid="stSidebarCollapseButton"] button::after {
    content: "«"; color: var(--text-secondary);
    font-size: 15px; font-weight: 700; line-height: 1;
}
[data-testid="stSidebarCollapseButton"] button:hover::after { color: var(--text-primary); }

/* Trim the dead space Streamlit leaves above the first element. */
h1 { margin-top: 0 !important; padding-top: 0 !important; }
.block-container > div:first-child { padding-top: 0 !important; }
div[data-testid="stVerticalBlock"] { gap: 0.6rem; }

/* ── Typography ───────────────────────────────────────── */
h1, h2, h3, h4, h5, h6 {
    font-family: var(--font-ui) !important;
    color: var(--text-primary) !important;
    font-weight: 600 !important;
}
h1 { font-size: 1.75rem !important; font-weight: 700 !important;
     letter-spacing: -0.02em !important; line-height: 1.2 !important; }
h2 { font-size: 1.25rem !important; letter-spacing: -0.01em !important; }
h3 { font-size: 1.0625rem !important; }
p, li, span, label, div[data-testid="stMarkdownContainer"] p {
    color: var(--text-secondary);
    font-size: 0.9375rem;
    line-height: 1.6;
}
.stCaption, [data-testid="stCaptionContainer"] p {
    color: var(--text-muted) !important;
    font-size: 0.8125rem !important;
}
.dp-overline {
    display: block;
    font-size: 0.6875rem; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.06em; color: var(--text-muted);
    line-height: 1.5; margin: 8px 0 12px;
}
.dp-subtitle { color: var(--text-muted); font-size: 0.8125rem; margin: 2px 0 0; }

/* ── Sidebar (Hidden) ─────────────────────────────────── */
section[data-testid="stSidebar"] {
    display: none !important;
}
[data-testid="stSidebarCollapseButton"] {
    display: none !important;
}
[data-testid="stExpandSidebarButton"] {
    display: none !important;
}
/* Center the dashboard and limit width on ultra-wide screens */
div[data-testid="stAppViewBlockContainer"] {
    max-width: 1400px !important;
    margin: 0 auto !important;
    padding-top: 2.5rem !important;
    padding-left: 2rem !important;
    padding-right: 2rem !important;
}

/* ── Buttons ──────────────────────────────────────────── */
button[data-testid="stBaseButton-primary"] {
    background: var(--accent) !important;
    color: #FFFFFF !important;
    border: 1px solid var(--accent) !important;
    border-radius: var(--radius-md) !important;
    font-weight: 600 !important; font-size: 0.9rem !important;
    padding: 8px 16px !important;
    box-shadow: var(--shadow-xs) !important;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
}
button[data-testid="stBaseButton-primary"]:hover {
    background: var(--accent-hover) !important;
    border-color: var(--accent-hover) !important;
    box-shadow: 0 4px 14px var(--focus-ring) !important;
    transform: translateY(-1px) !important;
}
button[data-testid="stBaseButton-primary"]:active {
    transform: translateY(1px) !important;
}
button[data-testid="stBaseButton-secondary"] {
    background: var(--surface) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-md) !important;
    font-weight: 500 !important; font-size: 0.9rem !important;
    padding: 8px 16px !important;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
}
button[data-testid="stBaseButton-secondary"]:hover {
    background: var(--surface-2) !important;
    border-color: var(--border-strong) !important;
    color: var(--text-primary) !important;
    transform: translateY(-1px) !important;
    box-shadow: var(--shadow-xs) !important;
}
button[data-testid="stBaseButton-secondary"]:active {
    transform: translateY(1px) !important;
}
button:focus-visible { outline: 3px solid var(--focus-ring) !important; outline-offset: 1px; }

/* Form submit buttons (Streamlit's default is a WHITE box in every theme — used
   here for the Login / Register CTAs). Make them solid accent so the label reads. */
button[data-testid="stBaseButton-primaryFormSubmit"],
button[data-testid="stBaseButton-secondaryFormSubmit"] {
    background: var(--accent) !important;
    border: 1px solid var(--accent) !important;
    border-radius: var(--radius-md) !important;
    box-shadow: var(--shadow-xs) !important;
    padding: 8px 20px !important;
}
button[data-testid="stBaseButton-primaryFormSubmit"]:hover,
button[data-testid="stBaseButton-secondaryFormSubmit"]:hover {
    background: var(--accent-hover) !important; border-color: var(--accent-hover) !important;
}

/* Streamlit wraps button labels in <p>, which would otherwise inherit the
   global paragraph color and wash out the label. */
button[data-testid="stBaseButton-primary"] p,
button[data-testid="stBaseButton-primary"] span,
button[data-testid="stBaseButton-primaryFormSubmit"] p,
button[data-testid="stBaseButton-primaryFormSubmit"] span,
button[data-testid="stBaseButton-secondaryFormSubmit"] p,
button[data-testid="stBaseButton-secondaryFormSubmit"] span {
    color: #FFFFFF !important; font-weight: 600 !important;
}
button[data-testid="stBaseButton-secondary"] p,
button[data-testid="stBaseButton-secondary"] span,
button[data-testid="stBaseButton-minimal"] p {
    color: var(--text-primary) !important;
}
button[disabled] p, button[disabled] span { color: var(--text-muted) !important; }
div[data-testid="stDownloadButton"] button p { color: var(--text-primary) !important; }

/* Tabs shouldn't get the boxy focus outline — the underline already marks active. */
button[role="tab"]:focus-visible { outline: none !important; }
button[role="tab"] { border-radius: var(--radius-sm) var(--radius-sm) 0 0 !important; }

/* ── Inputs ───────────────────────────────────────────── */
.stTextInput input, .stTextArea textarea, .stNumberInput input {
    background: var(--surface) !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-md) !important;
    font-size: 0.9rem !important;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
}
.stTextInput input:hover, .stTextArea textarea:hover {
    border-color: var(--border-strong) !important;
}
/* The input's root wrapper defaults to the light secondaryBackground; on password
   fields it shows as a white box behind the reveal-eye. Match it to the surface. */
[data-testid="stTextInputRootElement"] {
    background: var(--surface) !important;
    border-radius: var(--radius-md) !important;
}
/* Streamlit overlays a "Press Enter to submit form" hint on the last form input;
   it overlaps the field content. Hide it. */
[data-testid="InputInstructions"] { display: none !important; }
/* Password show/hide eye + stepper buttons default to a white box in dark mode. */
.stTextInput button, .stNumberInput button {
    background: transparent !important;
    border: none !important;
    color: var(--text-muted) !important;
}
.stTextInput button:hover, .stNumberInput button:hover {
    background: var(--surface-2) !important; color: var(--text-primary) !important;
}
.stTextInput button svg, .stNumberInput button svg { fill: var(--text-muted) !important; }
.stTextInput input::placeholder, .stTextArea textarea::placeholder {
    color: var(--text-muted) !important;
}
.stTextInput input:focus, .stTextArea textarea:focus {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px var(--focus-ring) !important;
    transform: scale(1.005) !important;
}
/* Selectbox / multiselect. The visible control is div[role="group"] (selectbox) or
   the baseweb select container (multiselect); without this they keep config.toml's
   light secondaryBackgroundColor even in dark mode. */
div[data-testid="stSelectbox"] div[role="group"],
div[data-testid="stMultiSelect"] div[role="group"],
div[data-testid="stMultiSelect"] div[data-baseweb="select"] > div {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-md) !important;
}
div[data-testid="stSelectbox"] div[role="group"]:focus-within,
div[data-testid="stMultiSelect"] div[role="group"]:focus-within {
    border-color: var(--accent) !important;
    box-shadow: 0 0 0 3px var(--focus-ring) !important;
}
div[data-testid="stSelectbox"] input,
div[data-testid="stMultiSelect"] input,
div[data-testid="stSelectbox"] div[role="group"] > div {
    color: var(--text-primary) !important;
    background: transparent !important;
}
div[data-testid="stSelectbox"] svg,
div[data-testid="stMultiSelect"] svg { fill: var(--text-muted) !important; }

/* Dropdown menu — rendered in a portal outside .stApp, so :root vars still apply. */
div[role="listbox"] {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-md) !important;
    box-shadow: var(--shadow-md) !important;
}
div[role="listbox"] [role="option"], div[role="listbox"] li {
    color: var(--text-primary) !important;
    background: transparent !important;
}
div[role="listbox"] [role="option"]:hover, div[role="listbox"] li:hover {
    background: var(--surface-2) !important;
}
div[role="listbox"] [aria-selected="true"] {
    background: var(--accent-soft) !important; color: var(--accent) !important;
}

/* ── Alerts (restyled natively; no call-site changes) ────
   The painted element is stAlertContainer, which carries Streamlit's own tint and
   a dark-blue text color. stAlert is a transparent wrapper; the stAlertContent*
   nodes only identify the variant. */
div[data-testid="stAlert"] { background: transparent !important; box-shadow: none !important; }
div[data-testid="stAlertContainer"] {
    background: var(--info-soft) !important;
    border: 1px solid var(--border) !important;
    border-left: 3px solid var(--info) !important;
    border-radius: var(--radius-lg) !important;
    padding: 12px 16px !important;
}
div[data-testid="stAlertContainer"]:has([data-testid="stAlertContentSuccess"]) {
    background: var(--success-soft) !important; border-left-color: var(--success) !important; }
div[data-testid="stAlertContainer"]:has([data-testid="stAlertContentInfo"]) {
    background: var(--accent-soft) !important; border-left-color: var(--accent) !important; }
div[data-testid="stAlertContainer"]:has([data-testid="stAlertContentWarning"]) {
    background: var(--medium-soft) !important; border-left-color: var(--medium) !important; }
div[data-testid="stAlertContainer"]:has([data-testid="stAlertContentError"]) {
    background: var(--critical-soft) !important; border-left-color: var(--critical) !important; }
div[data-testid="stAlertContainer"],
div[data-testid="stAlertContainer"] div,
div[data-testid="stAlertContainer"] p,
div[data-testid="stAlertContainer"] li,
div[data-testid="stAlertContainer"] strong {
    color: var(--text-primary) !important;
}
div[data-testid="stAlertContainer"] p { font-size: 0.875rem !important; }
div[data-testid="stAlertContainer"] [data-testid^="stAlertContent"] {
    background: transparent !important;
}
div[data-testid="stAlertContainer"] code {
    background: transparent !important; color: var(--text-primary) !important;
    font-weight: 600 !important;
}

/* ── Code ─────────────────────────────────────────────── */
code {
    background: var(--accent-soft) !important;
    color: var(--accent) !important;
    font-family: var(--font-mono) !important;
    font-size: 0.85rem !important;
    padding: 2px 6px !important;
    border-radius: var(--radius-sm) !important;
}
pre, .stCodeBlock, div[data-testid="stCode"] > pre {
    background: var(--surface-2) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-md) !important;
}
pre code {
    background: transparent !important;
    color: var(--text-primary) !important;
    padding: 0 !important;
}

/* ── Expander ─────────────────────────────────────────── */
div[data-testid="stExpander"] {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-lg) !important;
    box-shadow: none !important;
}
/* Streamlit paints the summary header with its own light secondaryBackgroundColor
   (from .streamlit/config.toml) regardless of our tokens — force it transparent so
   the parent stExpander's --surface shows through in dark mode too. */
div[data-testid="stExpander"] summary {
    background: transparent !important;
    color: var(--text-primary) !important;
    font-size: 0.9rem;
    border-radius: var(--radius-lg) !important;
    transition: color var(--dur-fast) var(--ease-in-out) !important;
}
div[data-testid="stExpander"] summary:hover { color: var(--accent) !important; background: var(--surface-2) !important; }
div[data-testid="stExpander"] summary p { color: inherit !important; }
div[data-testid="stExpander"] svg, div[data-testid="stExpander"] [data-testid="stIconMaterial"] {
    color: var(--text-secondary) !important;
}

/* ── Tabs (used only for in-section sub-nav) ──────────── */
button[data-baseweb="tab"] { color: var(--text-secondary) !important; }
button[data-baseweb="tab"][aria-selected="true"] { color: var(--accent) !important; }
div[data-baseweb="tab-highlight"] { background: var(--accent) !important; }

/* ── File uploader ────────────────────────────────────── */
section[data-testid="stFileUploaderDropzone"] {
    background: var(--surface-2) !important;
    border: 1px dashed var(--border-strong) !important;
    border-radius: var(--radius-lg) !important;
}

/* ── Cards / panels / KPI ─────────────────────────────── */
.dp-card {
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--radius-lg);
    padding: 24px;
    box-shadow: var(--shadow-sm);
}
.dp-kpi { display: flex; flex-direction: column; gap: 8px; }
.dp-kpi-icon {
    width: 36px; height: 36px; display: flex; align-items: center; justify-content: center;
    border-radius: var(--radius-sm); font-size: 1.05rem;
}
.dp-kpi-value { font-size: 1.75rem; font-weight: 700; color: var(--text-primary); line-height: 1.1; }
.dp-empty {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--radius-lg); padding: 48px 24px; text-align: center;
}

/* ── Glassmorphism (frosted cards) ─────────────────────
   card-blur is 0px for solid palettes (no visual change) and a real blur
   for gradient-mesh palettes (e.g. Nebula Glass), so the colorful backdrop
   shows through the translucent --surface / --surface-2 colors. */
.dp-card,
.dp-empty,
div[data-testid="stExpander"],
div[class*="st-key-ingest_card"],
div[class*="st-key-details_card"],
.st-key-dp_chat_panel,
.st-key-auth_card,
div[data-testid="stAlertContainer"],
[data-testid="stPopoverBody"] {
    backdrop-filter: blur(var(--card-blur)) saturate(160%);
    -webkit-backdrop-filter: blur(var(--card-blur)) saturate(160%);
}

/* ── Badges / chips ───────────────────────────────────── */
.dp-badge {
    display: inline-block; border-radius: var(--radius-full);
    padding: 2px 10px; font-size: 0.75rem; font-weight: 600;
    font-family: var(--font-ui);
}
.dp-chip {
    display: inline-block; border-radius: var(--radius-full);
    padding: 2px 10px; font-size: 0.72rem; font-weight: 500;
    border: 1px solid var(--border); color: var(--text-secondary);
    background: var(--surface-2);
}

/* ── Table rows ───────────────────────────────────────── */
.dp-th {
    display: flex; padding-bottom: 8px; border-bottom: 1px solid var(--border);
    font-size: 0.6875rem; font-weight: 600; text-transform: uppercase;
    letter-spacing: 0.06em; color: var(--text-muted);
}
table { border-color: var(--border) !important; }
thead th { color: var(--text-muted) !important; border-color: var(--border) !important; }
tbody td { color: var(--text-primary) !important; border-color: var(--border) !important; }

/* ── Popover (e.g. audit score explainer) ─────────────── */
[data-testid="stPopoverBody"],
div:has(> [data-testid="stPopoverBody"]) {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-lg) !important;
    box-shadow: var(--shadow-lg) !important;
}
button[data-testid="stPopoverButton"] {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-md) !important;
    color: var(--text-secondary) !important;
}
button[data-testid="stPopoverButton"]:hover {
    background: var(--surface-2) !important; color: var(--text-primary) !important;
}
button[data-testid="stPopoverButton"] p { color: inherit !important; }

/* ── Auth sign-in card ────────────────────────────────── */
.st-key-auth_card {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 16px !important;
    padding: 10px 24px 22px !important;
    box-shadow: var(--shadow-md) !important;
}
/* streamlit-authenticator wraps fields in a bordered form; flatten it inside the
   card so there's no box-in-a-box. */
.st-key-auth_card div[data-testid="stForm"] {
    border: none !important; padding: 0 !important; box-shadow: none !important;
}

/* ── Floating chat widget ─────────────────────────────── */
/* Streamlit tags keyed containers with a .st-key-<key> class; we pin those. */
.st-key-dp_chat_launcher {
    position: fixed !important;
    right: 24px !important; bottom: 24px !important;
    width: 56px !important; z-index: 1000001 !important;
}
.st-key-dp_chat_launcher button {
    width: 56px !important; height: 56px !important; min-height: 56px !important;
    border-radius: 50% !important;
    background-color: var(--accent) !important; border: none !important;
    box-shadow: 0 6px 20px rgba(79,70,229,.45) !important;
    background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32' fill='none'%3E%3Cpath d='M5 16 H10 L13 9 L17 23 L20 13 L22 16 H27' stroke='white' stroke-width='2.6' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E") !important;
    background-repeat: no-repeat !important;
    background-position: center !important;
    background-size: 30px 30px !important;
    transition: transform .12s ease, box-shadow .12s ease !important;
}
/* Hide the button's text label so only the logo shows. */
.st-key-dp_chat_launcher button * {
    font-size: 0 !important; color: transparent !important;
    width: 0 !important; height: 0 !important; overflow: hidden !important;
}
.st-key-dp_chat_launcher button:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 10px 26px rgba(79,70,229,.55) !important;
    background-color: var(--accent-hover) !important;
}

.st-key-dp_chat_panel {
    position: fixed !important;
    right: 24px !important; bottom: 92px !important;
    width: 370px !important; max-width: calc(100vw - 32px) !important;
    z-index: 1000001 !important;
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: 16px !important;
    box-shadow: var(--shadow-lg) !important;
    padding: 14px 16px !important;
    display: flex !important;
    flex-direction: column !important;
    height: 520px !important;
}
.st-key-dp_chat_panel {
    gap: 0px !important;
}
/* Streamlit wraps each st.container(key=...) child in an unclassed
   [data-testid="stLayoutWrapper"] div, not the .element-container this
   used to target. That wrapper is what needs flex-grow so the scroll
   area fills the panel and pushes the chat input down to the bottom
   edge instead of leaving it stranded above empty space. */
.st-key-dp_chat_panel > *:has(.st-key-dp_chat_scroll) {
    flex-grow: 1 !important;
    display: flex !important;
    flex-direction: column !important;
    min-height: 0 !important;
}
.st-key-dp_chat_scroll {
    flex-grow: 1 !important;
    display: flex !important;
    flex-direction: column !important;
    overflow-y: auto !important;
    margin: 6px -4px 8px; padding: 0 4px;
    min-height: 0 !important;
}
.st-key-dp_chat_close button, .st-key-dp_chat_size button {
    background: transparent !important; border: none !important;
    color: var(--text-muted) !important; padding: 0 !important;
    width: 28px !important;
    height: 28px !important;
    min-height: 28px !important;
    min-width: 28px !important;
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    line-height: 1 !important;
    font-size: 14px !important;
}
.st-key-dp_chat_close button:hover, .st-key-dp_chat_size button:hover { color: var(--text-primary) !important; }
.st-key-dp_chat_panel [data-testid="stChatInput"] {
    background: var(--surface-2) !important; border-color: var(--border) !important;
}
.st-key-dp_chat_panel [data-testid="stChatInput"] textarea {
    background: transparent !important; color: var(--text-primary) !important;
}

/* Custom Chat Bubble Styling */
.st-key-dp_chat_panel [data-testid="stChatMessage"] {
    background-color: var(--surface-2) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-lg) !important;
    padding: 12px 16px !important;
    margin-bottom: 8px !important;
    box-shadow: var(--shadow-xs) !important;
}
.st-key-dp_chat_panel [data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatar"] [data-testid="stChatMessageAvatarUser"]) {
    background-color: var(--accent-soft) !important;
    border-color: var(--focus-ring) !important;
}

/* ── Images (guide screenshots) ───────────────────────── */
div[data-testid="stImage"] img {
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-lg) !important;
    box-shadow: var(--shadow-sm) !important;
}
div[data-testid="stImage"] figcaption,
div[data-testid="stImageCaption"] {
    color: var(--text-muted) !important;
    font-size: 0.8125rem !important;
    text-align: left !important;
}

/* ── Progress / spinner ───────────────────────────────── */
div[data-testid="stProgress"] > div > div > div { background: var(--accent) !important; }

/* ── Scrollbar ────────────────────────────────────────── */
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb {
    background: var(--border-strong); border-radius: var(--radius-full);
    border: 2px solid var(--bg);
}
::-webkit-scrollbar-thumb:hover { background: var(--text-muted); }

/* ── Misc ─────────────────────────────────────────────── */
hr { border-color: var(--border) !important; }
a { color: var(--accent) !important; }
div[data-testid="column"] > div { gap: 0.75rem; }

/* ── Custom Micro-interactions ───────────────────────── */
.dp-lang-row {
    display: flex !important;
    justify-content: space-between !important;
    padding: 6px 8px !important;
    border-bottom: 1px solid var(--border) !important;
    border-radius: var(--radius-sm) !important;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
}
.dp-lang-row:hover {
    background: var(--surface-2) !important;
    padding-left: 14px !important;
    color: var(--accent) !important;
}
div[class*="st-key-ingest_card"], div[class*="st-key-details_card"] {
    background: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-lg) !important;
    padding: 24px !important;
    box-shadow: var(--shadow-sm) !important;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
}
div[class*="st-key-ingest_card"]:hover, div[class*="st-key-details_card"]:hover {
    transform: translateY(-2px) !important;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.12) !important;
    border-color: var(--border-strong) !important;
}
div[class*="st-key-ingest_card"] { animation: dp-fade-up var(--dur-slow) var(--ease-out) both; }
div[class*="st-key-details_card"] { animation: dp-fade-up var(--dur-slow) var(--ease-out) 60ms both; }

/* ── App header ───────────────────────────────────────── */
.st-key-app_header {
    position: relative;
    padding: 18px 4px 20px !important;
    margin-bottom: 4px;
    border-bottom: 1px solid var(--border);
    animation: dp-fade-in var(--dur-slow) var(--ease-out) both;
}
.st-key-app_header::before {
    content: "";
    position: absolute; inset: -20px -2rem auto -2rem; height: 140px;
    background: radial-gradient(60% 100% at 18% 0%, var(--accent-soft) 0%, transparent 70%);
    pointer-events: none;
    z-index: -1;
}
.dp-logo-text {
    background: linear-gradient(135deg, var(--text-primary) 35%, var(--accent) 120%) !important;
    -webkit-background-clip: text !important; background-clip: text !important;
    -webkit-text-fill-color: transparent !important; color: transparent !important;
}
.dp-logo-mark svg { transition: transform var(--dur-base) var(--ease-out); }
.st-key-app_header:hover .dp-logo-mark svg { transform: rotate(-6deg) scale(1.05); }

/* ── Segmented control (appearance mode) ─────────────────
   st.segmented_control renders a stButtonGroup of individual buttons
   (kind="segmented_control" / "segmented_controlActive"), not a label-based
   radio group. Restyle the group as one pill with a highlighted active
   button so it reads as a single toggle rather than three loose buttons. */
div[data-testid="stButtonGroup"] div[data-baseweb="button-group"] {
    background: var(--surface-2) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--radius-full) !important;
    padding: 3px !important;
    gap: 2px !important;
}
button[data-testid="stBaseButton-segmented_control"],
button[data-testid="stBaseButton-segmented_controlActive"] {
    border-radius: var(--radius-full) !important;
    border: none !important;
    background: transparent !important;
    min-height: 28px !important;
    padding: 4px 12px !important;
    box-shadow: none !important;
    transform: none !important;
    transition: all var(--dur-fast) var(--ease-in-out) !important;
}
button[data-testid="stBaseButton-segmented_controlActive"] {
    background: var(--surface) !important;
    box-shadow: var(--shadow-xs) !important;
}
button[data-testid="stBaseButton-segmented_controlActive"] p {
    color: var(--accent) !important; font-weight: 600 !important;
}
button[data-testid="stBaseButton-segmented_control"] p {
    color: var(--text-muted) !important; font-weight: 500 !important;
}
button[data-testid="stBaseButton-segmented_control"]:hover {
    background: transparent !important; transform: none !important; box-shadow: none !important;
}
button[data-testid="stBaseButton-segmented_control"]:hover p { color: var(--text-primary) !important; }
div[data-testid="stButtonGroup"] p { font-size: 0.8rem !important; }

/* ── Primary button shine sweep ───────────────────────── */
button[data-testid="stBaseButton-primary"] { position: relative; overflow: hidden; }
button[data-testid="stBaseButton-primary"]::after {
    content: "";
    position: absolute; top: 0; left: -75%; width: 40%; height: 100%;
    background: linear-gradient(120deg, transparent, rgba(255,255,255,.32), transparent);
    transform: skewX(-20deg);
    transition: left var(--dur-slow) var(--ease-out);
    pointer-events: none;
}
button[data-testid="stBaseButton-primary"]:hover::after { left: 130%; }

/* ── KPI stat row ─────────────────────────────────────── */
.st-key-stats_row div[data-testid="stColumn"] { animation: dp-fade-up var(--dur-base) var(--ease-out) both; }
.st-key-stats_row div[data-testid="stColumn"]:nth-of-type(1) { animation-delay: 0ms; }
.st-key-stats_row div[data-testid="stColumn"]:nth-of-type(2) { animation-delay: 60ms; }
.st-key-stats_row div[data-testid="stColumn"]:nth-of-type(3) { animation-delay: 120ms; }
.st-key-stats_row div[data-testid="stColumn"]:nth-of-type(4) { animation-delay: 180ms; }
.dp-kpi-icon { transition: transform var(--dur-base) var(--ease-out); }
.dp-card:hover .dp-kpi-icon { transform: scale(1.12) rotate(-4deg); }
.dp-card {
    transition: transform var(--dur-base) var(--ease-out), box-shadow var(--dur-base) var(--ease-out),
                border-color var(--dur-base) var(--ease-out);
}
.dp-card:hover {
    transform: translateY(-3px);
    box-shadow: var(--shadow-md);
    border-color: var(--border-strong);
}

/* ── Empty state ──────────────────────────────────────── */
.dp-empty { animation: dp-fade-up var(--dur-slow) var(--ease-out) both; }
.dp-empty > div:first-child { display: inline-block; animation: dp-float 3.2s var(--ease-in-out) infinite; }

/* ── Skeleton loaders ─────────────────────────────────── */
.dp-skeleton {
    height: 40px; border-radius: var(--radius-md); margin-bottom: 8px;
    background: linear-gradient(90deg, var(--surface-2) 25%, var(--border) 37%, var(--surface-2) 63%);
    background-size: 400% 100%;
    animation: dp-shimmer 1.4s ease-in-out infinite;
}

/* ── Progress bar shimmer ─────────────────────────────── */
div[data-testid="stProgress"] > div > div > div {
    background: linear-gradient(90deg, var(--accent) 0%, var(--accent-hover) 50%, var(--accent) 100%) !important;
    background-size: 300% 100% !important;
    animation: dp-shimmer 1.6s linear infinite !important;
    transition: width var(--dur-base) var(--ease-out) !important;
}

/* ── Data rows (file browser, recent queries) ─────────── */
.dp-row {
    display: flex; align-items: center; justify-content: space-between; gap: 10px;
    padding: 10px 12px; border-radius: var(--radius-md);
    border: 1px solid transparent;
    transition: all var(--dur-fast) var(--ease-in-out);
    animation: dp-fade-up var(--dur-base) var(--ease-out) both;
}
.dp-row:hover { background: var(--surface-2); border-color: var(--border); }

/* ── Chat widget motion ───────────────────────────────── */
.st-key-dp_chat_launcher button {
    animation: dp-pulse-ring 2.6s var(--ease-in-out) infinite;
}
.st-key-dp_chat_launcher button:hover { animation: none; }
.st-key-dp_chat_panel { animation: dp-panel-in var(--dur-base) var(--ease-out) both; }
.st-key-dp_chat_panel [data-testid="stChatMessage"] {
    animation: dp-fade-up var(--dur-base) var(--ease-out) both;
    transition: transform var(--dur-fast) var(--ease-in-out);
}
.st-key-dp_chat_scroll div[class*="st-key-sug_btn_"] {
    animation: dp-fade-up var(--dur-base) var(--ease-out) both;
}
.st-key-dp_chat_scroll div[class*="st-key-sug_btn_0"] { animation-delay: 0ms; }
.st-key-dp_chat_scroll div[class*="st-key-sug_btn_1"] { animation-delay: 60ms; }
.st-key-dp_chat_scroll div[class*="st-key-sug_btn_2"] { animation-delay: 120ms; }
"""

_FONTS = (
    "@import url('https://fonts.googleapis.com/css2?"
    "family=Inter:wght@400;500;600;700"
    "&family=JetBrains+Mono:wght@400;500&display=swap');"
)


PALETTES = {
    "Nebula Glass": {
        "light-accent": "#9333EA", "light-accent-hover": "#7E22CE", "light-accent-soft": "rgba(147,51,234,0.12)",
        "dark-accent": "#F472B6", "dark-accent-hover": "#FB7185", "dark-accent-soft": "rgba(244,114,182,0.18)",
        "light-bg": "#F3E8FF", "dark-bg": "#120B1F",
        "light-surface": "rgba(255,255,255,0.55)", "dark-surface": "rgba(30,20,50,0.55)",
        "light-surface-2": "rgba(255,255,255,0.35)", "dark-surface-2": "rgba(255,255,255,0.06)",
        "light-border": "rgba(255,255,255,0.6)", "dark-border": "rgba(255,255,255,0.12)",
        "light-border-strong": "rgba(255,255,255,0.85)", "dark-border-strong": "rgba(255,255,255,0.22)",
        "light-bg-image": (
            "radial-gradient(60% 50% at 15% 10%, rgba(196,132,252,0.55) 0%, transparent 60%),"
            "radial-gradient(55% 45% at 85% 15%, rgba(244,114,182,0.45) 0%, transparent 60%),"
            "radial-gradient(60% 55% at 50% 100%, rgba(129,140,248,0.45) 0%, transparent 65%)"
        ),
        "dark-bg-image": (
            "radial-gradient(60% 50% at 15% 10%, rgba(147,51,234,0.38) 0%, transparent 60%),"
            "radial-gradient(55% 45% at 85% 15%, rgba(219,39,119,0.32) 0%, transparent 60%),"
            "radial-gradient(60% 55% at 50% 100%, rgba(79,70,229,0.38) 0%, transparent 65%)"
        ),
        "card-blur": "18px",
    },
}

def hex_to_rgb_str(hex_color: str) -> str:
    hex_color = hex_color.lstrip('#')
    if len(hex_color) == 6:
        r, g, b = tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        return f"{r},{g},{b}"
    return "99,102,241"

def inject_theme(mode: str = "auto", palette_name: str = "Nebula Glass") -> None:
    """Inject the full stylesheet with dynamic palette tokens."""
    if mode not in ("auto", "light", "dark"):
        mode = "auto"
    if palette_name not in PALETTES:
        palette_name = "Nebula Glass"
        
    p = PALETTES[palette_name]
    
    # Generate light and dark tokens dynamically
    light_tokens = {
        "bg": p["light-bg"],
        "surface": p["light-surface"],
        "surface-2": p["light-surface-2"],
        "border": p["light-border"],
        "border-strong": p["light-border-strong"],
        "text-primary": "#0F172A",
        "text-secondary": "#475569",
        "text-muted": "#94A3B8",
        "accent": p["light-accent"],
        "accent-hover": p["light-accent-hover"],
        "accent-soft": p["light-accent-soft"],
        "accent-rgb": hex_to_rgb_str(p["light-accent"]),
        "focus-ring": f"rgba({hex_to_rgb_str(p['light-accent'])},0.35)",
        "critical": "#DC2626",
        "critical-soft": "#FEE2E2",
        "high": "#EA580C",
        "high-soft": "#FFEDD5",
        "medium": "#D97706",
        "medium-soft": "#FEF3C7",
        "low": "#2563EB",
        "low-soft": "#DBEAFE",
        "info": "#475569",
        "info-soft": "#F1F5F9",
        "success": "#16A34A",
        "success-soft": "#DCFCE7",
        "shadow-xs": "0 1px 2px rgba(16,24,40,.05)",
        "shadow-sm": "0 1px 3px rgba(16,24,40,.06), 0 1px 2px rgba(16,24,40,.04)",
        "shadow-md": "0 4px 12px rgba(16,24,40,.08)",
        "shadow-lg": "0 12px 24px rgba(16,24,40,.10)",
        "bg-image": p.get("light-bg-image", "none"),
        "card-blur": p.get("card-blur", "0px"),
    }

    dark_tokens = {
        "bg": p["dark-bg"],
        "surface": p["dark-surface"],
        "surface-2": p["dark-surface-2"],
        "border": p["dark-border"],
        "border-strong": p["dark-border-strong"],
        "text-primary": "#E6EAF2",
        "text-secondary": "#9BA6BC",
        "text-muted": "#6B7688",
        "accent": p["dark-accent"],
        "accent-hover": p["dark-accent-hover"],
        "accent-soft": p["dark-accent-soft"],
        "accent-rgb": hex_to_rgb_str(p["dark-accent"]),
        "focus-ring": f"rgba({hex_to_rgb_str(p['dark-accent'])},0.45)",
        "critical": "#F87171",
        "critical-soft": "rgba(248,113,113,0.14)",
        "high": "#FB923C",
        "high-soft": "rgba(251,146,60,0.14)",
        "medium": "#FBBF24",
        "medium-soft": "rgba(251,191,36,0.14)",
        "low": "#60A5FA",
        "low-soft": "rgba(96,165,250,0.14)",
        "info": "#94A3B8",
        "info-soft": "rgba(148,163,184,0.14)",
        "success": "#4ADE80",
        "success-soft": "rgba(74,222,128,0.14)",
        "shadow-xs": "0 1px 2px rgba(0,0,0,.3)",
        "shadow-sm": "0 1px 2px rgba(0,0,0,.4)",
        "shadow-md": "0 6px 16px rgba(0,0,0,.5)",
        "shadow-lg": "0 16px 32px rgba(0,0,0,.55)",
        "bg-image": p.get("dark-bg-image", "none"),
        "card-blur": p.get("card-blur", "0px"),
    }

    global TOKENS
    TOKENS["light"] = light_tokens
    TOKENS["dark"] = dark_tokens
    
    st.markdown(
        f"<style>\n{_FONTS}\n\n{_token_layer(mode)}\n{_STYLES}\n</style>",
        unsafe_allow_html=True,
    )

