"""
dax_builder.py
==============
Streamlit web application for AI-powered DAX measure generation.

Run with:
    streamlit run dax_builder.py

Modes:
    Demo   – uses the built-in dummy financial model (no upload required)
    Upload – user uploads a definition.zip (PBIP TMDL export)
"""

import io
import json
import re
import tempfile
import zipfile
from pathlib import Path

import streamlit as st

from anonymizer import build_system_prompt, anonymize, deanonymize
from ai_client import get_client, AI_PROVIDER, AI_MODEL
from mapping_generator import generate_dummy_mapping, generate_mapping_from_tmdl


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
    .sidebar-section-header {
        font-size: 0.75rem;
        font-weight: 700;
        color: #888;
        text-transform: uppercase;
        letter-spacing: 0.08em;
        margin-top: 1rem;
        margin-bottom: 0.25rem;
    }
    .demo-badge {
        display: inline-block;
        background: #7a4f00;
        color: #ffd580;
        border-radius: 4px;
        padding: 2px 10px;
        font-size: 0.75rem;
        font-weight: 600;
    }
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
        "demo_mode":        True,
        "conversation":     [],
        "history":          [],
        "last_dax":         "",
        "last_explanation": "",
        "last_description": "",
        "generating":       False,
        "std_results":      [],
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()

# Default: load dummy mapping on first run
if st.session_state["mapping"] is None:
    dummy = generate_dummy_mapping()
    st.session_state["mapping"]       = dummy
    st.session_state["system_prompt"] = build_system_prompt(dummy)
    st.session_state["demo_mode"]     = True


# ---------------------------------------------------------------------------
# Helper: process uploaded ZIP → mapping dict
# ---------------------------------------------------------------------------

def _process_zip(uploaded_file) -> dict:
    """
    Extract a definition.zip and generate a mapping dict from the TMDL folder.
    The temp directory is cleaned up automatically after extraction.
    """
    zip_bytes = uploaded_file.read()

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            zf.extractall(tmp_path)

        # Locate the definition/ folder (may be at root or one level deep)
        definition_dir: Path | None = None
        for candidate in sorted(tmp_path.rglob("definition")):
            if candidate.is_dir() and (candidate / "tables").is_dir():
                definition_dir = candidate
                break

        if definition_dir is None:
            raise ValueError(
                "Kein 'definition/' Ordner mit 'tables/' Unterordner in der ZIP gefunden.\n"
                "Erwartete Struktur: definition/tables/*.tmdl"
            )

        return generate_mapping_from_tmdl(str(definition_dir))


# ---------------------------------------------------------------------------
# Helper: parse AI response
# ---------------------------------------------------------------------------

def _parse_response(raw: str) -> tuple[str, str]:
    dax_match = re.search(r"```(?:dax|DAX)\s*(.*?)```", raw, re.DOTALL)
    dax = dax_match.group(1).strip() if dax_match else ""

    if dax_match:
        explanation = raw[dax_match.end():].strip()
        explanation = re.sub(r"^\s*#+\s*EXPLANATION\s*", "", explanation, flags=re.IGNORECASE).strip()
        explanation = re.sub(r"^\s*\*\*EXPLANATION\*\*\s*", "", explanation, flags=re.IGNORECASE).strip()
    else:
        explanation = raw.strip()
        dax = ""

    if not explanation and dax_match:
        explanation = raw[: dax_match.start()].strip()

    return dax, explanation


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

mapping = st.session_state["mapping"]

with st.sidebar:
    st.title("📊 DAX Builder")

    col_a, col_b = st.columns([3, 2])
    with col_a:
        st.markdown(
            f'<span class="provider-badge">{AI_PROVIDER} · {AI_MODEL}</span>',
            unsafe_allow_html=True,
        )
    with col_b:
        if st.session_state["demo_mode"]:
            st.markdown('<span class="demo-badge">Demo</span>', unsafe_allow_html=True)

    st.divider()

    # --- Tables ---
    st.markdown('<div class="sidebar-section-header">Tabellen</div>', unsafe_allow_html=True)
    for real_name, info in mapping.get("tables", {}).items():
        t_type = info.get("type", "")
        icon   = "⭐" if t_type == "fact" else "📋"
        with st.expander(f"{icon} {real_name}", expanded=False):
            cols = [
                v for v in mapping.get("columns", {}).values()
                if v["real_table"] == real_name
            ]
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

    if st.button("Verlauf löschen", use_container_width=True):
        st.session_state["conversation"]     = []
        st.session_state["history"]          = []
        st.session_state["last_dax"]         = ""
        st.session_state["last_explanation"] = ""
        st.session_state["last_description"] = ""
        st.rerun()


# ---------------------------------------------------------------------------
# Setup section – ZIP upload (always visible at the top)
# ---------------------------------------------------------------------------

st.header("Datenmodell hochladen")

if st.session_state["demo_mode"]:
    st.info(
        "**Demo-Modus aktiv** – Es wird ein Dummy-Datenmodell (fiktive Finanzdaten) verwendet.  \n"
        "Lade dein eigenes TMDL Modell als ZIP hoch, um mit deinen echten Daten zu arbeiten."
    )
else:
    t_loaded = len(st.session_state["mapping"].get("tables", {}))
    m_loaded = len(st.session_state["mapping"].get("measures", {}))
    st.success(
        f"Eigenes Modell aktiv – {t_loaded} Tabellen, {m_loaded} Measures.  \n"
        "Neues ZIP hochladen, um das Modell zu wechseln."
    )

st.markdown(
    "**ZIP erstellen:** Power BI Desktop → *File → Save As → Power BI Project (.pbip)*"
    " → `definition/` Ordner als ZIP packen."
)

uploaded_zip = st.file_uploader(
    "Lade dein TMDL Modell als ZIP hoch",
    type="zip",
    help="Enthält den TMDL 'definition/' Ordner mit tables/*.tmdl und relationships.tmdl",
    label_visibility="visible",
)

col1, col2 = st.columns([2, 3])
with col1:
    load_btn = st.button(
        "Modell laden",
        type="primary",
        disabled=uploaded_zip is None,
        use_container_width=True,
    )
with col2:
    if not st.session_state["demo_mode"]:
        if st.button("Zurück zum Demo-Modus", use_container_width=True):
            dummy = generate_dummy_mapping()
            st.session_state["mapping"]          = dummy
            st.session_state["system_prompt"]    = build_system_prompt(dummy)
            st.session_state["demo_mode"]        = True
            st.session_state["conversation"]     = []
            st.session_state["history"]          = []
            st.session_state["last_dax"]         = ""
            st.session_state["last_explanation"] = ""
            st.session_state["last_description"] = ""
            st.rerun()

if load_btn and uploaded_zip is not None:
    with st.spinner("ZIP wird entpackt und Modell analysiert..."):
        try:
            new_mapping = _process_zip(uploaded_zip)
            st.session_state["mapping"]          = new_mapping
            st.session_state["system_prompt"]    = build_system_prompt(new_mapping)
            st.session_state["demo_mode"]        = False
            st.session_state["conversation"]     = []
            st.session_state["history"]          = []
            st.session_state["last_dax"]         = ""
            st.session_state["last_explanation"] = ""
            st.session_state["last_description"] = ""
            t_count = len(new_mapping.get("tables", {}))
            m_count = len(new_mapping.get("measures", {}))
            st.success(f"Modell geladen: {t_count} Tabellen, {m_count} Measures.")
            st.rerun()
        except Exception as exc:
            st.error(f"Fehler beim Laden der ZIP: {exc}")

st.divider()


# ---------------------------------------------------------------------------
# Main area – DAX Generator
# ---------------------------------------------------------------------------

# Refresh mapping from session state (may have changed above)
mapping = st.session_state["mapping"]

st.header("DAX Measure Generator")
if st.session_state["demo_mode"]:
    st.caption("Demo-Modus · Dummy Datenmodell · Beschreibe das gewünschte Measure in natürlicher Sprache.")
else:
    st.caption("Beschreibe das gewünschte Measure in natürlicher Sprache – der AI erledigt den Rest.")

# ---------------------------------------------------------------------------
# Standard-Measures definitions
# ---------------------------------------------------------------------------

STANDARD_MEASURES = [
    {
        "key":     "ytd",
        "label":   "YTD (Jahr bis heute)",
        "default": True,
        "prompt": (
            "Erstelle ein DAX-Measure für den kumulierten Umsatz vom Beginn des "
            "Geschäftsjahres bis zur aktuellen Periode (YTD = Year-to-Date). "
            "Nutze TOTALYTD oder DATESYTD und berücksichtige das konfigurierte Geschäftsjahr."
        ),
    },
    {
        "key":     "py",
        "label":   "Vorjahr (gleiche Periode letztes Jahr)",
        "default": True,
        "prompt": (
            "Erstelle ein DAX-Measure für den Umsatz der gleichen kumulierten Periode "
            "im Vorjahr (Prior Year – SPLY). Berücksichtige das konfigurierte Geschäftsjahr. "
            "Nutze SAMEPERIODLASTYEAR oder DATEADD."
        ),
    },
    {
        "key":     "ytd_vs_py_abs",
        "label":   "YTD vs Vorjahr (Abweichung absolut)",
        "default": True,
        "prompt": (
            "Erstelle ein DAX-Measure für die absolute Abweichung des aktuellen "
            "Geschäftsjahres-YTD-Umsatzes gegenüber dem Vorjahres-YTD-Umsatz "
            "(Differenz: aktuelles YTD minus Vorjahres-YTD)."
        ),
    },
    {
        "key":     "ytd_vs_py_pct",
        "label":   "YTD vs Vorjahr % (Abweichung prozentual)",
        "default": True,
        "prompt": (
            "Erstelle ein DAX-Measure für die prozentuale Veränderung des "
            "Geschäftsjahres-YTD-Umsatzes gegenüber dem Vorjahres-YTD. "
            "Nutze DIVIDE für sichere Division durch Null. Ergebnis als Dezimalzahl (0.12 = 12%)."
        ),
    },
    {
        "key":     "budget_vs_actual",
        "label":   "Budget vs Actual (Plan/Ist Vergleich)",
        "default": False,
        "prompt": (
            "Erstelle ein DAX-Measure für den Plan/Ist-Vergleich: Actual (Kosten oder Umsatz) "
            "minus Budget-Measure. Nutze die vorhandenen Measures im Modell. "
            "Berechne die absolute Abweichung und nutze DIVIDE für die prozentuale Abweichung."
        ),
    },
    {
        "key":     "rolling_12",
        "label":   "Rolling 12 Months (letzte 12 Monate)",
        "default": False,
        "prompt": (
            "Erstelle ein DAX-Measure für den rollierenden 12-Monats-Umsatz "
            "(gleitende Summe der letzten 12 Monate bis zur aktuellen Periode). "
            "Nutze DATESINPERIOD mit LASTDATE und -12 als Versatz in Monaten."
        ),
    },
]


# ---------------------------------------------------------------------------
# Standard-Measures UI (above normal input form)
# ---------------------------------------------------------------------------

st.subheader("📦 Standard-Measures")

_cb_col1, _cb_col2 = st.columns(2)
_selected_std: list[dict] = []
for _i, _m in enumerate(STANDARD_MEASURES):
    _col = _cb_col1 if _i % 2 == 0 else _cb_col2
    with _col:
        _checked = st.checkbox(
            _m["label"],
            value=_m["default"],
            key=f"std_cb_{_m['key']}",
        )
        if _checked:
            _selected_std.append(_m)

_gen_std_btn = st.button(
    "Ausgewählte Measures generieren",
    type="primary",
    key="gen_std_btn",
)

if _gen_std_btn:
    if not _selected_std:
        st.warning("Bitte mindestens ein Measure auswählen.")
    else:
        _std_results: list[dict] = []
        _progress_bar = st.progress(0.0, text="Starte Generierung…")
        for _idx, _measure in enumerate(_selected_std):
            _progress_bar.progress(
                _idx / len(_selected_std),
                text=f"Generiere '{_measure['label']}' ({_idx + 1}/{len(_selected_std)})…",
            )
            with st.spinner(f"Generiere '{_measure['label']}'…"):
                _anon_prompt = anonymize(_measure["prompt"], mapping)
                try:
                    _client = get_client()
                    _raw = _client.chat(
                        messages=[{"role": "user", "content": _anon_prompt}],
                        system_prompt=st.session_state["system_prompt"],
                    )
                    _raw_deanon = deanonymize(_raw, mapping)
                    _dax, _expl = _parse_response(_raw_deanon)
                    _std_results.append({
                        "name":        _measure["label"],
                        "dax":         _dax,
                        "explanation": _expl,
                        "error":       None,
                    })
                except Exception as _exc:
                    _std_results.append({
                        "name":        _measure["label"],
                        "dax":         "",
                        "explanation": "",
                        "error":       str(_exc),
                    })
        _progress_bar.progress(1.0, text="Fertig!")
        _progress_bar.empty()
        st.session_state["std_results"] = _std_results

if st.session_state["std_results"]:
    st.markdown("#### Generierte Standard-Measures")
    for _result in st.session_state["std_results"]:
        with st.expander(f"**{_result['name']}**", expanded=True):
            if _result["error"]:
                st.error(f"Fehler: {_result['error']}")
            else:
                st.code(_result["dax"], language="sql")
                _dax_esc = _result["dax"].replace("`", "\\`").replace("\\", "\\\\")
                _btn_html = f"""
                <button onclick="navigator.clipboard.writeText(`{_dax_esc}`).then(()=>{{
                    this.innerText='✓ Kopiert!';
                    setTimeout(()=>this.innerText='Kopieren', 2000);
                }})"
                style="
                    background:#1f4e79; color:white; border:none; border-radius:5px;
                    padding:4px 14px; cursor:pointer; font-size:0.82rem; margin-bottom:8px;
                ">
                Kopieren
                </button>
                """
                st.components.v1.html(_btn_html, height=38)
                if _result["explanation"]:
                    st.markdown(_result["explanation"])

st.markdown(
    "<div style='text-align:center; color:#888; font-size:0.9rem; "
    "margin:1.5rem 0; letter-spacing:0.05em;'>"
    "─── oder eigenes Measure beschreiben ───</div>",
    unsafe_allow_html=True,
)


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


# ---------------------------------------------------------------------------
# AI call
# ---------------------------------------------------------------------------

if submitted and description.strip():
    st.session_state["generating"]       = True
    st.session_state["last_description"] = description.strip()

    anon_description = anonymize(description.strip(), mapping)

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
            st.session_state["conversation"].pop()
            st.stop()

    raw_deanon = deanonymize(raw_response, mapping)
    dax, explanation = _parse_response(raw_deanon)

    st.session_state["conversation"].append(
        {"role": "assistant", "content": raw_response}
    )

    st.session_state["last_dax"]         = dax
    st.session_state["last_explanation"] = explanation
    st.session_state["generating"]       = False

    st.session_state["history"].insert(0, {
        "description": description.strip(),
        "dax":         dax,
        "explanation": explanation,
    })

elif submitted and description.strip() == "":
    st.warning("Bitte gib eine Beschreibung ein.")


# ---------------------------------------------------------------------------
# Result display
# ---------------------------------------------------------------------------

if st.session_state["last_dax"]:
    st.divider()
    st.subheader("Generierter DAX-Code")

    st.code(st.session_state["last_dax"], language="sql")

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

    if st.session_state["last_explanation"]:
        with st.expander("Erklärung", expanded=True):
            st.markdown(st.session_state["last_explanation"])


# ---------------------------------------------------------------------------
# Conversation history
# ---------------------------------------------------------------------------

if len(st.session_state["history"]) > 1:
    st.divider()
    st.subheader("Vorherige Measures")

    for i, entry in enumerate(st.session_state["history"][1:], start=1):
        label = f"#{i} — {entry['description'][:80]}{'…' if len(entry['description']) > 80 else ''}"
        with st.expander(label, expanded=False):
            st.code(entry["dax"], language="sql")

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
