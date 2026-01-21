#!/usr/bin/env python3
"""Export ontology mappings JSON to CSV files.

Usage:
  python3 scripts/export_ontology_mappings_csv.py docs/spec/ONTOLOGY_MAPPINGS.json docs/spec/mappings
"""

import csv
import json
import os
import sys
from typing import Any, Dict, List


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def write_csv(path: str, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    if len(sys.argv) != 3:
        print("Usage: python3 scripts/export_ontology_mappings_csv.py <json_path> <out_dir>")
        return 2

    json_path = sys.argv[1]
    out_dir = sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)

    data = load_json(json_path)

    write_csv(os.path.join(out_dir, "theme_vertical_aspect.csv"), data.get("theme_vertical_aspect", []))
    write_csv(os.path.join(out_dir, "theme_company_exposure.csv"), data.get("theme_company_exposure", []))
    write_csv(os.path.join(out_dir, "vertical_company_exposure.csv"), data.get("vertical_company_exposure", []))
    write_csv(os.path.join(out_dir, "aspect_theme_weighting.csv"), data.get("aspect_theme_weighting", []))

    print("Ontology mapping CSV export: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
