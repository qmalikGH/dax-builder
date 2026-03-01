"""
dax_builder.py
==============
Streamlit web application for AI-powered DAX measure generation.

Run with:
    streamlit run dax_builder.py
"""

import re
import json
import streamlit as st
from pathlib import Path

from mapping_generator import generate_dummy_mapping
from anonymizer import load_mapping, anonymize, deanonymize, build_system_prompt
from ai_client import get_client, AI_PROVIDER, AI_MODEL


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="DAX Builder",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# Custom CSS
# ---------------------------------------------------------------------------

st.markdown(
    """
    <style>
    /* Sidebar header */
    .sidebar-section-header {
        font-size: 0.75rem;
        font-weight: 700;
        color: #888;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-top: 1rem;
        margin-bottom: 0.25rem;
    }
    /* Measure pill */
    .measure-pill {
        display: inline-block;
        background: #1f4e79;
        color: white;
        border-radius: 4px;
        padding: 2px 8px;
        font-size: 0.78rem;
        margin: 2px;
    }
    /* History card */
    .history-card {
        background: #1e1e2e;
        border-left: 3px solid #4e8cff;
        border-radius: 4px;
        padding: 0.75rem 1rem;
        margin-bottom: 0.75rem;
    }
    /* Provider badge */
    .provider-badge {
        background: #0e3460;
        color: #7ec8e3;
        border-radius: 12px;
        padding: 2px 10px;
        font-size: 0.75rem;
        font-weight: 600;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Session state defaults
# ---------------------------------------------------------------------------

def _init_state():
    defaults = {
        "mapping":          None,
        "system_prompt":    None,
        "conversation":     [],   # list of {"role": str, "content": str}
        "history":          [],   # list of {"description": str, "dax": str, "explanation": str}
        "last_dax":         "",
        "last_explanation": "",
        "last_description": "",
        "generating":       False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()


# ---------------------------------------------------------------------------
# Load / generate mapping
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner="Lade Datenmodell...")
def _load_mapping_cached():
    if Path("mapping.json").exists():
        return load_mapping()
    # Generate and persist dummy mapping
    m = generate_dummy_mapping()
    Path("mapping.json").write_text(
        json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    return m

mapping = _load_mapping_cached()
if st.session_state["mapping"] is None:
    st.session_state["mapping"]       = mapping
    st.session_state["system_prompt"] = build_system_prompt(mapping)


# ---------------------------------------------------------------------------
# Helper: extract DAX and explanation from AI response
# ---------------------------------------------------------------------------

def _parse_response(raw: str) -> tuple[str, str]:
    """
    Extract DAX code block and explanation from the AI response.
    Returns (dax_code, explanation).
    """
    # Try to find ```dax ... ``` block
    dax_match = re.search(r"```(?:dax|DAX)\s*(.*?)```", raw, re.DOTALL)
    dax = dax_match.group(1).strip() if dax_match else ""

    # Explanation: everything after the code block, or full text if no block
    if dax_match:
        explanation = raw[dax_match.end():].strip()
        # Remove leading section headers
        explanation = re.sub(r"^\s*#+\s*EXPLANATION\s*", "", explanation, flags=re.IGNORECASE).strip()
        # Also remove ** bold headers
        explanation = re.sub(r"^\s*\*\*EXPLANATION\*\*\s*", "", explanation, flags=re.IGNORECASE).strip()
    else:
        explanation = raw.strip()
        dax = ""

    if not explanation:
        # Fallback: take text before the code block
        explanation = raw[: dax_match.start()].strip() if dax_match else raw.strip()

    return dax, explanation


# ---------------------------------------------------------------------------
# Sidebar: model overview
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("📊 DAX Builder")
    st.markdown(
        f'<span class="provider-badge">{AI_PROVIDER} · {AI_MODEL}</span>',
        unsafe_allow_html=True,
    )
    st.divider()

    # --- Tables ---
    st.markdown('<div class="sidebar-section-header">Tabellen</div>', unsafe_allow_html=True)
    for real_name, info in mapping.get("tables", {}).items():
        t_type  = info.get("type", "")
        icon    = "⭐" if t_type == "fact" else "📋"
        with st.expander(f"{icon} {real_name}", expanded=False):
            cols = [
                v for v in mapping.get("columns", {}).values()
                if v["real_table"] == real_name
            ]
            if cols:
                for c in cols:
                    st.markdown(f"  `{c['real_column']}`")

    # --- Measures ---
    st.markdown('<div class="sidebar-section-header">Measures</div>', unsafe_allow_html=True)
    for real_name in mapping.get("measures", {}):
        st.markdown(f"  `{real_name}`")

    # --- Relationships ---
    st.markdown('<div class="sidebar-section-header">Beziehungen</div>', unsafe_allow_html=True)
    for rel in mapping.get("relationships", []):
        from_r = rel.get("from_real", "")
        to_r   = rel.get("to_real",   "")
        card   = rel.get("cardinality", "")
        st.markdown(f"  `{from_r}` → `{to_r}`")
        if card:
            st.caption(f"  {card}")

    # --- Fiscal year ---
    fy = mapping.get("fiscal_year", {})
    if fy:
        st.markdown('<div class="sidebar-section-header">Geschäftsjahr</div>', unsafe_allow_html=True)
        st.caption(f"Beginnt: {fy.get('start_month_name', '')} (Monat {fy.get('start_month', '')})")

    st.divider()

    # --- Clear history ---
    if st.button("Verlauf löschen", use_container_width=True):
        st.session_state["conversation"] = []
        st.session_state["history"]      = []
        st.session_state["last_dax"]         = ""
        st.session_state["last_explanation"] = ""
        st.session_state["last_description"] = ""
        st.rerun()


# ---------------------------------------------------------------------------
# Main area
# ---------------------------------------------------------------------------

st.header("DAX Measure Generator")
st.caption("Beschreibe das gewünschte Measure in natürlicher Sprache – der AI erledigt den Rest.")

# Input form
with st.form("dax_form", clear_on_submit=False):
    description = st.text_area(
        "Measure-Beschreibung",
        placeholder=(
            "Beispiel: Berechne den Nettoumsatz für das aktuelle Geschäftsjahr, "
            "aufgeteilt nach Kostenstellen, nur für aktive Kostenstellen."
        ),
        height=130,
        key="user_input",
    )
    col_btn1, col_btn2 = st.columns([1, 5])
    with col_btn1:
        submitted = st.form_submit_button("DAX generieren", type="primary", use_container_width=True)
    with col_btn2:
        st.empty()


# ---------------------------------------------------------------------------
# AI call
# ---------------------------------------------------------------------------

if submitted and description.strip():
    st.session_state["generating"]       = True
    st.session_state["last_description"] = description.strip()

    anon_description = anonymize(description.strip(), mapping)

    # Build conversation history for context
    st.session_state["conversation"].append(
        {"role": "user", "content": anon_description}
    )

    with st.spinner("Generiere DAX-Measure..."):
        try:
            client = get_client()
            raw_response = client.chat(
                messages=st.session_state["conversation"],
                system_prompt=st.session_state["system_prompt"],
            )
        except Exception as exc:
            st.error(f"AI-Fehler: {exc}")
            st.session_state["conversation"].pop()  # revert
            st.stop()

    # Deanonymize
    raw_deanon = deanonymize(raw_response, mapping)

    # Parse
    dax, explanation = _parse_response(raw_deanon)

    # Store assistant reply in conversation (anonymized version for context)
    st.session_state["conversation"].append(
        {"role": "assistant", "content": raw_response}
    )

    st.session_state["last_dax"]         = dax
    st.session_state["last_explanation"] = explanation
    st.session_state["generating"]       = False

    # Save to history
    st.session_state["history"].insert(0, {
        "description": description.strip(),
        "dax":         dax,
        "explanation": explanation,
    })


# ---------------------------------------------------------------------------
# Result display
# ---------------------------------------------------------------------------

if st.session_state["last_dax"]:
    st.divider()
    st.subheader("Generierter DAX-Code")

    # DAX with syntax highlighting
    st.code(st.session_state["last_dax"], language="sql")

    # Clipboard copy button (Streamlit workaround via JS)
    dax_escaped = st.session_state["last_dax"].replace("`", "\\`").replace("\\", "\\\\")
    clipboard_html = f"""
    <button onclick="navigator.clipboard.writeText(`{dax_escaped}`).then(()=>{{
        this.innerText='✓ Kopiert!';
        setTimeout(()=>this.innerText='In Clipboard kopieren', 2000);
    }})"
    style="
        background:#1f4e79; color:white; border:none; border-radius:5px;
        padding:6px 16px; cursor:pointer; font-size:0.85rem; margin-bottom:12px;
    ">
    In Clipboard kopieren
    </button>
    """
    st.components.v1.html(clipboard_html, height=45)

    # Explanation
    if st.session_state["last_explanation"]:
        with st.expander("Erklärung", expanded=True):
            st.markdown(st.session_state["last_explanation"])

elif submitted and description.strip() == "":
    st.warning("Bitte gib eine Beschreibung ein.")


# ---------------------------------------------------------------------------
# Conversation history
# ---------------------------------------------------------------------------

if len(st.session_state["history"]) > 1:
    st.divider()
    st.subheader("Vorherige Measures")

    for i, entry in enumerate(st.session_state["history"][1:], start=1):
        with st.expander(f"#{i} — {entry['description'][:80]}{'…' if len(entry['description'])>80 else ''}", expanded=False):
            st.code(entry["dax"], language="sql")

            # Small copy button for history items
            dax_esc = entry["dax"].replace("`", "\\`").replace("\\", "\\\\")
            btn_html = f"""
            <button onclick="navigator.clipboard.writeText(`{dax_esc}`).then(()=>{{
                this.innerText='✓ Kopiert!';
                setTimeout(()=>this.innerText='Kopieren', 2000);
            }})"
            style="
                background:#333; color:white; border:none; border-radius:4px;
                padding:4px 12px; cursor:pointer; font-size:0.8rem;
            ">
            Kopieren
            </button>
            """
            st.components.v1.html(btn_html, height=38)

            if entry["explanation"]:
                st.markdown(entry["explanation"])
