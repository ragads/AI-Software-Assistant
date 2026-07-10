# services/llm_service.py
"""Provider-agnostic LLM access.

Pure Python: no Streamlit imports outside the thin session-state accessors, so the
adapters remain reusable if the UI is ever replaced.

Key resolution order per provider: session state (set in Settings) -> env var.
`app.py` exports session keys into os.environ on every rerun, so any consumer that
calls os.getenv() at call time (e.g. embedding_service) also picks them up.

Each SDK is imported lazily inside its adapter, so a provider whose package is not
installed only fails when that provider is actually selected.
"""
import os
import logging

import streamlit as st

logger = logging.getLogger("llm_service")


# ── Adapters ────────────────────────────────────────────────────────────
def _gemini_generate(model, system, prompt, key):
    import google.genai as genai
    from google.genai import types

    client = genai.Client(api_key=key)
    resp = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(system_instruction=system or None),
    )
    return resp.text or ""


def _gemini_test(key):
    import google.genai as genai

    client = genai.Client(api_key=key)
    list(client.models.list())


def _anthropic_generate(model, system, prompt, key):
    import anthropic

    resp = anthropic.Anthropic(api_key=key).messages.create(
        model=model,
        max_tokens=16000,
        system=system or "",
        messages=[{"role": "user", "content": prompt}],
    )
    return next((b.text for b in resp.content if b.type == "text"), "")


def _anthropic_test(key):
    import anthropic

    anthropic.Anthropic(api_key=key).models.list()


def _openai_generate(model, system, prompt, key):
    from openai import OpenAI

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    resp = OpenAI(api_key=key).chat.completions.create(model=model, messages=messages)
    return resp.choices[0].message.content or ""


def _openai_test(key):
    from openai import OpenAI

    OpenAI(api_key=key).models.list()


# ── Registry ────────────────────────────────────────────────────────────
PROVIDERS = {
    "gemini": {
        "label": "Google Gemini",
        "env": "GEMINI_API_KEY",
        "models": ["gemini-2.5-flash", "gemini-2.5-pro"],
        "keys_url": "https://aistudio.google.com/apikey",
        "generate": _gemini_generate,
        "test": _gemini_test,
    },
    "anthropic": {
        "label": "Anthropic (Claude)",
        "env": "ANTHROPIC_API_KEY",
        "models": ["claude-opus-4-8", "claude-sonnet-5", "claude-haiku-4-5"],
        "keys_url": "https://console.anthropic.com/settings/keys",
        "generate": _anthropic_generate,
        "test": _anthropic_test,
    },
    "openai": {
        "label": "OpenAI (GPT)",
        "env": "OPENAI_API_KEY",
        "models": ["gpt-4o", "gpt-4o-mini"],
        "keys_url": "https://platform.openai.com/api-keys",
        "generate": _openai_generate,
        "test": _openai_test,
    },
}

DEFAULT_PROVIDER = "gemini"

# Embeddings are Gemini-only (text-embedding-004) and independent of the chat
# provider. Without a Gemini key, get_embedding() returns None and search
# degrades to keyword-only. See EMBEDDING_PROVIDER usage in Settings.
EMBEDDING_PROVIDER = "gemini"


# ── Session accessors ───────────────────────────────────────────────────
def active_provider() -> str:
    prov = st.session_state.get("llm_provider", DEFAULT_PROVIDER)
    return prov if prov in PROVIDERS else DEFAULT_PROVIDER


def active_model(provider: str = None) -> str:
    provider = provider or active_provider()
    models = PROVIDERS[provider]["models"]
    chosen = st.session_state.get("llm_model")
    return chosen if chosen in models else models[0]


def resolve_key(provider: str = None):
    """Return (key, source) where source is 'session', 'env', or 'none'."""
    provider = provider or active_provider()
    session_key = st.session_state.get(f"api_key_{provider}")
    if session_key:
        return session_key, "session"
    env_key = os.getenv(PROVIDERS[provider]["env"])
    if env_key:
        return env_key, "env"
    return None, "none"


def mask_key(key: str) -> str:
    if not key:
        return "not set"
    return "•" * 8 + key[-4:] if len(key) > 4 else "•" * 8


def export_keys_to_env() -> None:
    """Push session-state keys into os.environ so os.getenv() consumers see them.

    Called once per rerun from app.py. A provider with no session key is left
    alone, preserving any value already set in the environment (e.g. on Render).
    """
    for provider, meta in PROVIDERS.items():
        session_key = st.session_state.get(f"api_key_{provider}")
        if session_key:
            os.environ[meta["env"]] = session_key


# ── Public API ──────────────────────────────────────────────────────────
class LLMNotConfigured(RuntimeError):
    """Raised when the selected provider has no usable API key."""


def generate(system: str, prompt: str) -> str:
    """Run a completion against the currently selected provider + model."""
    provider = active_provider()
    key, _ = resolve_key(provider)
    if not key:
        raise LLMNotConfigured(
            f"No API key configured for {PROVIDERS[provider]['label']}. "
            f"Open Settings, choose your provider, and paste your key."
        )
    model = active_model(provider)
    logger.info("LLM call provider=%s model=%s", provider, model)
    return PROVIDERS[provider]["generate"](model, system, prompt, key)


def test_connection(provider: str, key: str):
    """Return (ok, message). Never raises, never echoes the key."""
    if not key:
        return False, "No key provided."
    try:
        PROVIDERS[provider]["test"](key)
        return True, f"{PROVIDERS[provider]['label']} connection OK"
    except ImportError as e:
        return False, f"Package not installed: {e}. Run: pip install -r requirements.txt"
    except Exception as e:  # noqa: BLE001 - surface any auth/network failure verbatim
        return False, f"Failed: {e}"


def embeddings_available() -> bool:
    """True when a Gemini key exists (session or env) to power vector search."""
    key, _ = resolve_key(EMBEDDING_PROVIDER)
    return bool(key)
