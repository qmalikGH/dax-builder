"""
anonymizer.py
=============
Loads mapping.json and provides:

    anonymize(text)   → replaces real names with aliases
    deanonymize(text) → replaces aliases back with real names
    build_system_prompt() → builds a detailed system prompt for the AI
                             using the anonymized model description

This keeps real business names out of the AI request, improving privacy
and making it possible to use the same setup with external/cloud models.
"""

import json
import re
from pathlib import Path
from typing import Optional

MAPPING_PATH = Path("mapping.json")


# ---------------------------------------------------------------------------
# Loader
# ---------------------------------------------------------------------------

def load_mapping(path: Optional[str] = None) -> dict:
    p = Path(path) if path else MAPPING_PATH
    if not p.exists():
        raise FileNotFoundError(
            f"mapping.json not found at {p.resolve()}. "
            "Run: python mapping_generator.py"
        )
    return json.loads(p.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Build replacement tables
# ---------------------------------------------------------------------------

def _build_replacements(mapping: dict) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    """
    Returns:
        real_to_alias  – sorted longest-first so longer names are replaced first
        alias_to_real  – for deanonymization
    """
    real_to_alias: list[tuple[str, str]] = []
    alias_to_real: list[tuple[str, str]] = []

    # Tables
    for real, info in mapping.get("tables", {}).items():
        alias = info["alias"]
        real_to_alias.append((real, alias))
        alias_to_real.append((alias, real))

    # Columns  (key format: "TableName.ColumnName")
    for key, info in mapping.get("columns", {}).items():
        real_col = info["real_column"]
        alias    = info["alias"]
        real_to_alias.append((real_col, alias))
        alias_to_real.append((alias, real_col))

    # Measures
    for real, info in mapping.get("measures", {}).items():
        alias = info["alias"]
        real_to_alias.append((real, alias))
        alias_to_real.append((alias, real))

    # Sort longest first to avoid partial replacements
    real_to_alias.sort(key=lambda x: len(x[0]), reverse=True)
    alias_to_real.sort(key=lambda x: len(x[0]), reverse=True)

    return real_to_alias, alias_to_real


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------

def anonymize(text: str, mapping: dict) -> str:
    """Replace real names with aliases in text."""
    real_to_alias, _ = _build_replacements(mapping)
    for real, alias in real_to_alias:
        # Word-boundary replacement (case-sensitive)
        pattern = r'\b' + re.escape(real) + r'\b'
        text = re.sub(pattern, alias, text)
    return text


def deanonymize(text: str, mapping: dict) -> str:
    """Replace aliases back with real names in text."""
    _, alias_to_real = _build_replacements(mapping)
    for alias, real in alias_to_real:
        pattern = r'\b' + re.escape(alias) + r'\b'
        text = re.sub(pattern, real, text)
    return text


# ---------------------------------------------------------------------------
# System prompt builder
# ---------------------------------------------------------------------------

def build_system_prompt(mapping: dict) -> str:
    """
    Build a comprehensive system prompt that describes the anonymized data model
    so the AI can generate correct DAX measures.
    """
    lines: list[str] = []

    # Header
    lines.append(
        "You are an expert Power BI / DAX developer. "
        "Your job is to generate correct, efficient DAX measures based on the user's "
        "natural-language description and the data model described below.\n"
    )

    # Fiscal year
    fy = mapping.get("fiscal_year", {})
    if fy:
        lines.append(
            f"FISCAL YEAR: starts in month {fy.get('start_month')} "
            f"({fy.get('start_month_name', '')}). "
            "Use this when generating time intelligence calculations.\n"
        )

    # Tables
    lines.append("## DATA MODEL (anonymized)\n")
    lines.append("### Tables\n")
    for real_name, info in mapping.get("tables", {}).items():
        alias   = info["alias"]
        t_type  = info.get("type", "unknown")
        lines.append(f"- **{alias}** ({t_type}) — original name hidden for privacy")

        # List columns belonging to this table
        cols_for_table = [
            v for k, v in mapping.get("columns", {}).items()
            if v["real_table"] == real_name
        ]
        if cols_for_table:
            col_str = ", ".join(
                f"{c['alias']}" for c in cols_for_table
            )
            lines.append(f"  Columns: {col_str}")
    lines.append("")

    # Measures
    if mapping.get("measures"):
        lines.append("### Measures\n")
        for real_name, info in mapping["measures"].items():
            lines.append(f"- **{info['alias']}**")
        lines.append("")

    # Relationships
    if mapping.get("relationships"):
        lines.append("### Relationships\n")
        for rel in mapping["relationships"]:
            from_t = rel.get("from_table_alias", rel.get("from_alias", "?"))
            to_t   = rel.get("to_table_alias",   rel.get("to_alias",   "?"))
            from_c = rel.get("from_alias", "?")
            to_c   = rel.get("to_alias",   "?")
            card   = rel.get("cardinality", "")
            lines.append(
                f"- {from_t}[{from_c}] → {to_t}[{to_c}]  ({card})"
            )
        lines.append("")

    # Output instructions
    lines.append(
        "## OUTPUT FORMAT\n"
        "Always respond with two clearly separated sections:\n\n"
        "1. **DAX MEASURE** – the complete DAX code inside a fenced code block "
        "marked with ```dax\n"
        "2. **EXPLANATION** – a plain-language explanation of what the measure does, "
        "which tables/columns it uses, and any important caveats.\n\n"
        "Use the anonymized table/column/measure names in your DAX code. "
        "The application will replace them with the real names automatically.\n"
        "Keep the DAX clean, well-formatted, and efficient."
    )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mapping = load_mapping()

    print("=== System Prompt (first 40 lines) ===")
    sp = build_system_prompt(mapping)
    for i, line in enumerate(sp.splitlines()[:40]):
        print(line)

    sample = "Erstelle ein Measure für Umsatz_netto nach Kostenstellen gefiltert auf Status aktiv."
    anon   = anonymize(sample, mapping)
    back   = deanonymize(anon, mapping)

    print("\n=== Anonymize / Deanonymize Test ===")
    print(f"Original : {sample}")
    print(f"Anon     : {anon}")
    print(f"DeAnon   : {back}")
    print(f"Round-trip OK: {sample == back}")
