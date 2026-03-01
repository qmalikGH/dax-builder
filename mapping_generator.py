"""
mapping_generator.py
====================
Reads a PBIP model and generates a mapping.json with anonymized aliases.
Tables get aliases like Table_A, Table_B; columns like Col_A1, Col_A2;
measures like Measure_X, Measure_Y.

Supported sources:
  - Dummy model (hardcoded financial model)
  - model.bim (TMSL/JSON format)
  - TMDL definition/ folder (PBIP TMDL format)

Usage:
    python mapping_generator.py                              # generates dummy mapping.json
    python mapping_generator.py --source model.bim           # reads a .bim file
    python mapping_generator.py --source-tmdl path/to/definition/  # reads TMDL folder
"""

import json
import re
import string
import argparse
from pathlib import Path


# ---------------------------------------------------------------------------
# Alias generators
# ---------------------------------------------------------------------------

def _table_alias(index: int) -> str:
    """Table_A, Table_B, …, Table_Z, Table_AA, …"""
    letters = string.ascii_uppercase
    result = ""
    while True:
        result = letters[index % 26] + result
        index = index // 26 - 1
        if index < 0:
            break
    return f"Table_{result}"


def _col_alias(table_letter: str, col_index: int) -> str:
    """Col_A1, Col_A2, … Col_B1, …"""
    return f"Col_{table_letter}{col_index + 1}"


def _measure_alias(index: int) -> str:
    """Measure_X, Measure_Y, Measure_Z, Measure_AA, …"""
    letters = string.ascii_uppercase
    result = ""
    idx = index
    while True:
        result = letters[idx % 26] + result
        idx = idx // 26 - 1
        if idx < 0:
            break
    return f"Measure_{result}"


# ---------------------------------------------------------------------------
# Dummy mapping (financial model)
# ---------------------------------------------------------------------------

DUMMY_MODEL = {
    "tables": [
        {
            "real_name": "Finanzdaten",
            "type": "fact",
            "columns": ["Buchungsdatum", "Betrag_netto", "Kostenstelle_ID"],
        },
        {
            "real_name": "Kostenstellen",
            "type": "dimension",
            "columns": ["ID", "Name", "Status"],
        },
        {
            "real_name": "Kalender",
            "type": "dimension",
            "columns": ["Datum", "Jahr", "Monat", "Quartal"],
        },
    ],
    "measures": [
        {"real_name": "Umsatz_netto"},
        {"real_name": "Budget_gesamt"},
        {"real_name": "Kosten_gesamt"},
    ],
    "relationships": [
        {
            "from_table": "Finanzdaten",
            "from_column": "Buchungsdatum",
            "to_table": "Kalender",
            "to_column": "Datum",
            "cardinality": "many-to-one",
        },
        {
            "from_table": "Finanzdaten",
            "from_column": "Kostenstelle_ID",
            "to_table": "Kostenstellen",
            "to_column": "ID",
            "cardinality": "many-to-one",
        },
    ],
    "fiscal_year": {
        "start_month": 10,
        "start_month_name": "Oktober",
    },
}


def generate_dummy_mapping() -> dict:
    """Build a mapping dict from the hardcoded DUMMY_MODEL."""
    mapping: dict = {
        "tables": {},
        "columns": {},
        "measures": {},
        "relationships": [],
        "fiscal_year": DUMMY_MODEL["fiscal_year"],
    }

    # --- Tables & Columns ---
    for t_idx, table in enumerate(DUMMY_MODEL["tables"]):
        t_alias = _table_alias(t_idx)
        t_letter = t_alias.replace("Table_", "")
        real_t = table["real_name"]

        mapping["tables"][real_t] = {
            "alias": t_alias,
            "type": table["type"],
        }

        for c_idx, col in enumerate(table["columns"]):
            c_alias = _col_alias(t_letter, c_idx)
            mapping["columns"][f"{real_t}.{col}"] = {
                "alias": c_alias,
                "table_alias": t_alias,
                "real_table": real_t,
                "real_column": col,
            }

    # --- Measures ---
    for m_idx, measure in enumerate(DUMMY_MODEL["measures"]):
        m_alias = _measure_alias(m_idx)
        mapping["measures"][measure["real_name"]] = {"alias": m_alias}

    # --- Relationships ---
    for rel in DUMMY_MODEL["relationships"]:
        from_key = f"{rel['from_table']}.{rel['from_column']}"
        to_key   = f"{rel['to_table']}.{rel['to_column']}"
        mapping["relationships"].append(
            {
                "from_alias": mapping["columns"][from_key]["alias"],
                "from_table_alias": mapping["tables"][rel["from_table"]]["alias"],
                "to_alias": mapping["columns"][to_key]["alias"],
                "to_table_alias": mapping["tables"][rel["to_table"]]["alias"],
                # Keep real names for human-readable debugging
                "from_real": from_key,
                "to_real": to_key,
                "cardinality": rel["cardinality"],
            }
        )

    return mapping


# ---------------------------------------------------------------------------
# BIM file reader (real model)
# ---------------------------------------------------------------------------

def generate_mapping_from_bim(bim_path: str) -> dict:
    """
    Parse a Power BI model.bim (TMSL JSON) and build the same mapping structure.
    Currently supports the 'model.tables' structure from PBIP/TMDL exports.
    """
    bim = json.loads(Path(bim_path).read_text(encoding="utf-8"))
    model = bim.get("model", bim)  # some exports wrap in {"model": ...}
    raw_tables = model.get("tables", [])

    dummy_tables = []
    dummy_measures = []

    for tbl in raw_tables:
        name = tbl.get("name", "Unknown")
        cols = [c["name"] for c in tbl.get("columns", []) if c.get("type") != "calculatedTableColumn"]
        dummy_tables.append({"real_name": name, "type": "unknown", "columns": cols})
        for m in tbl.get("measures", []):
            dummy_measures.append({"real_name": m["name"]})

    raw_rels = model.get("relationships", [])

    model_def = {
        "tables": dummy_tables,
        "measures": dummy_measures,
        "relationships": raw_rels,
        "fiscal_year": {"start_month": 1, "start_month_name": "Januar"},
    }

    # Re-use the same alias logic
    mapping: dict = {
        "tables": {},
        "columns": {},
        "measures": {},
        "relationships": [],
        "fiscal_year": model_def["fiscal_year"],
    }

    for t_idx, table in enumerate(model_def["tables"]):
        t_alias = _table_alias(t_idx)
        t_letter = t_alias.replace("Table_", "")
        real_t = table["real_name"]
        mapping["tables"][real_t] = {"alias": t_alias, "type": table["type"]}
        for c_idx, col in enumerate(table["columns"]):
            c_alias = _col_alias(t_letter, c_idx)
            mapping["columns"][f"{real_t}.{col}"] = {
                "alias": c_alias,
                "table_alias": t_alias,
                "real_table": real_t,
                "real_column": col,
            }

    for m_idx, measure in enumerate(model_def["measures"]):
        m_alias = _measure_alias(m_idx)
        mapping["measures"][measure["real_name"]] = {"alias": m_alias}

    for rel in raw_rels:
        mapping["relationships"].append(rel)

    return mapping


# ---------------------------------------------------------------------------
# TMDL folder reader (real PBIP model)
# ---------------------------------------------------------------------------

# Auto-generated internal tables that Power BI adds – skip them
_AUTO_TABLE_RE = re.compile(r'^(DateTableTemplate_|LocalDateTable_)')


def _parse_tmdl_table(path: Path) -> dict | None:
    """Parse a single table .tmdl file. Returns None for auto-generated tables."""
    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()

    # First line: table 'Name' or table Name
    if not lines:
        return None
    m = re.match(r"^table\s+'(.+)'|^table\s+(\S+)", lines[0])
    if not m:
        return None
    table_name = m.group(1) or m.group(2)

    if _AUTO_TABLE_RE.match(table_name):
        return None

    columns: list[str] = []
    measures: list[str] = []

    for line in lines[1:]:
        # Exactly one leading tab = top-level member (column / measure)
        m = re.match(r"^\t(column|measure)\s+'(.+)'$|^\t(column|measure)\s+(\S+)$", line)
        if m:
            kind = m.group(1) or m.group(3)
            name = m.group(2) or m.group(4)
            if kind == "column":
                columns.append(name)
            elif kind == "measure":
                measures.append(name)

    return {"real_name": table_name, "type": "unknown", "columns": columns, "measures": measures}


def _parse_tmdl_relationships(path: Path) -> list[dict]:
    """Parse relationships.tmdl and return a list of relationship dicts."""
    if not path.exists():
        return []

    content = path.read_text(encoding="utf-8")
    rels: list[dict] = []

    def _split_ref(ref: str) -> tuple[str, str]:
        """'Table Name'.Col  or  TableName.Col  →  (table, col)"""
        ref = ref.strip()
        m = re.match(r"'(.+)'\.(.+)|(\S+)\.(\S+)", ref)
        if m:
            return (m.group(1) or m.group(3)), (m.group(2) or m.group(4))
        return ref, ""

    # Split on each "relationship <id>" line
    blocks = re.split(r'\nrelationship\s+\S+', "\n" + content)
    for block in blocks[1:]:
        fc = re.search(r'fromColumn:\s+(.+)', block)
        tc = re.search(r'toColumn:\s+(.+)', block)
        card = re.search(r'cardinality:\s+(.+)', block)
        if not (fc and tc):
            continue
        ft, fc_name = _split_ref(fc.group(1))
        tt, tc_name = _split_ref(tc.group(1))
        rels.append({
            "from_table": ft,
            "from_column": fc_name,
            "to_table": tt,
            "to_column": tc_name,
            "cardinality": card.group(1).strip() if card else "many-to-one",
        })
    return rels


def generate_mapping_from_tmdl(definition_dir: str) -> dict:
    """
    Parse a PBIP TMDL definition/ folder and build the mapping structure.

    Expected layout:
        definition/
            model.tmdl
            relationships.tmdl
            tables/
                TableName.tmdl
                ...
    """
    definition_path = Path(definition_dir)
    tables_dir = definition_path / "tables"

    # --- Parse tables ---
    parsed_tables: list[dict] = []
    for tmdl_file in sorted(tables_dir.glob("*.tmdl")):
        result = _parse_tmdl_table(tmdl_file)
        if result:
            parsed_tables.append(result)

    # --- Parse relationships ---
    parsed_rels = _parse_tmdl_relationships(definition_path / "relationships.tmdl")

    # --- Build mapping ---
    mapping: dict = {
        "tables": {},
        "columns": {},
        "measures": {},
        "relationships": [],
        "fiscal_year": {"start_month": 1, "start_month_name": "Januar"},
    }

    measure_global_idx = 0

    for t_idx, table in enumerate(parsed_tables):
        t_alias = _table_alias(t_idx)
        t_letter = t_alias.replace("Table_", "")
        real_t = table["real_name"]

        mapping["tables"][real_t] = {"alias": t_alias, "type": table["type"]}

        for c_idx, col in enumerate(table["columns"]):
            c_alias = _col_alias(t_letter, c_idx)
            mapping["columns"][f"{real_t}.{col}"] = {
                "alias": c_alias,
                "table_alias": t_alias,
                "real_table": real_t,
                "real_column": col,
            }

        for measure_name in table["measures"]:
            m_alias = _measure_alias(measure_global_idx)
            mapping["measures"][measure_name] = {"alias": m_alias, "table": real_t}
            measure_global_idx += 1

    # --- Relationships with aliases where both sides are in user tables ---
    for rel in parsed_rels:
        from_key = f"{rel['from_table']}.{rel['from_column']}"
        to_key = f"{rel['to_table']}.{rel['to_column']}"

        entry: dict = {
            "from_real": from_key,
            "to_real": to_key,
            "cardinality": rel["cardinality"],
        }

        if from_key in mapping["columns"] and to_key in mapping["columns"]:
            entry["from_alias"] = mapping["columns"][from_key]["alias"]
            entry["from_table_alias"] = mapping["tables"][rel["from_table"]]["alias"]
            entry["to_alias"] = mapping["columns"][to_key]["alias"]
            entry["to_table_alias"] = mapping["tables"][rel["to_table"]]["alias"]

        mapping["relationships"].append(entry)

    return mapping


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate mapping.json from a PBIP model.")
    parser.add_argument("--source", help="Path to model.bim file", default=None)
    parser.add_argument("--source-tmdl", help="Path to PBIP definition/ folder (TMDL format)", default=None)
    parser.add_argument("--output", help="Output path for mapping.json", default="mapping.json")
    args = parser.parse_args()

    if args.source_tmdl:
        print(f"Reading TMDL definition folder: {args.source_tmdl}")
        mapping = generate_mapping_from_tmdl(args.source_tmdl)
    elif args.source:
        print(f"Reading BIM file: {args.source}")
        mapping = generate_mapping_from_bim(args.source)
    else:
        print("No source file given – generating dummy mapping.json")
        mapping = generate_dummy_mapping()

    out_path = Path(args.output)
    out_path.write_text(json.dumps(mapping, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"mapping.json written to: {out_path.resolve()}")

    # Human-readable summary
    print(f"\n  Tables   : {len(mapping['tables'])}")
    print(f"  Columns  : {len(mapping['columns'])}")
    print(f"  Measures : {len(mapping['measures'])}")
    print(f"  Relations: {len(mapping['relationships'])}")


if __name__ == "__main__":
    main()
