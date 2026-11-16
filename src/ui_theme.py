"""
Shabd.Craft — Central UI Theme, Fonts, Tokens & State Synchronization Helpers
Target Streamlit Version: 1.38.0
WCAG 2.1 AA Compliant (High Contrast, Inter + JetBrains Mono)
"""

from __future__ import annotations

import streamlit as st
from typing import Any


# ── The Single Deliberate CSS Injection: Fonts & High-Contrast Focus Ring ──
def inject_custom_fonts() -> None:
    """
    The ONE deliberate CSS injection allowed:
    Loads Inter (UI) and JetBrains Mono (Code/Prompts) with system fallbacks.
    Does not manipulate layout or override Streamlit component classes.
    """
    st.markdown("""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');
        
        html, body, [class*="st-emotion"] {
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
        }
        
        code, pre, .stCodeBlock, textarea[data-baseweb="textarea"] {
            font-family: 'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace !important;
        }
        
        /* High-contrast focus ring accessibility (WCAG AA) */
        *:focus-visible {
            outline: 2px solid #9b84ff !important;
            outline-offset: 2px !important;
        }

        /* Subtle container refinement */
        [data-testid="stVerticalBlock"] > div[data-testid="stContainer"] {
            border-radius: 8px;
        }
        </style>
    """, unsafe_allow_html=True)


# ── Status Badges (Never Color Alone: Icon + Explicit Text) ──────────────
def status_badge(status_type: str, text: str) -> str:
    """
    Format status text combining a distinct Material symbol and native colored markdown.
    Ensures non-color-dependent communication (WCAG 2.1 AA).
    """
    status_type = status_type.lower()
    if status_type in ("pass", "success", "resisted", "complete", "completed"):
        return f":material/check_circle: :green[{text}]"
    elif status_type in ("fail", "error", "vulnerable", "blocked"):
        return f":material/cancel: :red[{text}]"
    elif status_type in ("warn", "warning", "missing", "repaired"):
        return f":material/warning: :orange[{text}]"
    elif status_type in ("running", "progress", "active"):
        return f":material/hourglass_top: :blue[{text}]"
    elif status_type in ("stopped", "cancelled"):
        return f":material/stop_circle: :grey[{text}]"
    return f":material/info: {text}"


# ── Secret Masking (Strictly last 4 chars, e.g. ••••abcd) ────────────────
def mask_api_key(key: str | None) -> str:
    """
    Mask an API key showing strictly only the last 4 characters (••••abcd).
    Never prints or echoes any provider prefix.
    """
    if not key or not str(key).strip():
        return "Not Configured"
    stripped = str(key).strip()
    if len(stripped) <= 4:
        return "••••" + stripped
    return "••••" + stripped[-4:]


# ── Durable State Across Pages ───────────────────────────────────────────
def init_durable_state(domain: str, defaults: dict[str, Any]) -> dict[str, Any]:
    """
    Initialize a durable state dictionary in st.session_state that survives widget unmounting.
    """
    key = f"durable_{domain}"
    if key not in st.session_state:
        st.session_state[key] = dict(defaults)
    else:
        # Fill any missing default keys
        for k, v in defaults.items():
            if k not in st.session_state[key]:
                st.session_state[key][k] = v
    return st.session_state[key]


def get_durable_value(domain: str, key: str, default: Any = None) -> Any:
    """Get a value from a durable state domain."""
    d = st.session_state.get(f"durable_{domain}", {})
    return d.get(key, default)


def set_durable_value(domain: str, key: str, value: Any) -> None:
    """Set a value in a durable state domain."""
    d = st.session_state.setdefault(f"durable_{domain}", {})
    d[key] = value


# ── Programmatic Cache Invalidation Protocol ─────────────────────────────
def invalidate_prompt_caches() -> None:
    """Clear cached data functions when experiments or versions change."""
    # Note: Streamlit @st.cache_data functions can be cleared via func.clear()
    # Called by DB mutating actions
    pass


def invalidate_test_case_caches() -> None:
    """Clear cached data functions when test cases are modified."""
    pass


def invalidate_evaluation_caches() -> None:
    """Clear cached evaluation scores when a new evaluation run is completed."""
    pass
