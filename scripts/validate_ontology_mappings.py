#!/usr/bin/env python3
"""Validate ontology mappings JSON for basic consistency.

Usage:
  python scripts/validate_ontology_mappings.py docs/spec/ONTOLOGY_MAPPINGS.json
"""

import json
import re
import sys
from typing import Any, Dict, List

ID_PATTERNS = {
    "theme": re.compile(r"^THM-[a-z0-9-]+$"),
    "vertical": re.compile(r"^VRT-[a-z0-9-]+$"),
    "aspect": re.compile(r"^ASP-[a-z0-9-]+$"),
    "company": re.compile(r"^CMP-[A-Z0-9-]+$"),
}


def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def assert_in_range(value: float, name: str) -> None:
    if not (0.0 <= value <= 1.0):
        raise ValueError(f"{name} must be between 0 and 1, got {value}")


def check_ids(id_list: List[str], pattern: re.Pattern, label: str) -> None:
    for item in id_list:
        if not pattern.match(item):
            raise ValueError(f"Invalid {label} id: {item}")


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: python scripts/validate_ontology_mappings.py <path>")
        return 2

    data = load_json(sys.argv[1])
    id_sets = data.get("id_sets", {})

    check_ids(id_sets.get("themes", []), ID_PATTERNS["theme"], "theme")
    check_ids(id_sets.get("verticals", []), ID_PATTERNS["vertical"], "vertical")
    check_ids(id_sets.get("aspects", []), ID_PATTERNS["aspect"], "aspect")
    check_ids(id_sets.get("companies", []), ID_PATTERNS["company"], "company")

    theme_ids = set(id_sets.get("themes", []))
    vertical_ids = set(id_sets.get("verticals", []))
    aspect_ids = set(id_sets.get("aspects", []))
    company_ids = set(id_sets.get("companies", []))

    for row in data.get("theme_vertical_aspect", []):
        if row["theme_id"] not in theme_ids:
            raise ValueError(f"Unknown theme_id in theme_vertical_aspect: {row['theme_id']}")
        if row["vertical_id"] not in vertical_ids:
            raise ValueError(f"Unknown vertical_id in theme_vertical_aspect: {row['vertical_id']}")
        if row["aspect_id"] not in aspect_ids:
            raise ValueError(f"Unknown aspect_id in theme_vertical_aspect: {row['aspect_id']}")

    for row in data.get("theme_company_exposure", []):
        if row["theme_id"] not in theme_ids:
            raise ValueError(f"Unknown theme_id in theme_company_exposure: {row['theme_id']}")
        if row["company_id"] not in company_ids:
            raise ValueError(f"Unknown company_id in theme_company_exposure: {row['company_id']}")
        assert_in_range(row["exposure_strength"], "exposure_strength")

    for row in data.get("vertical_company_exposure", []):
        if row["vertical_id"] not in vertical_ids:
            raise ValueError(f"Unknown vertical_id in vertical_company_exposure: {row['vertical_id']}")
        if row["company_id"] not in company_ids:
            raise ValueError(f"Unknown company_id in vertical_company_exposure: {row['company_id']}")
        assert_in_range(row["exposure_strength"], "exposure_strength")

    for row in data.get("aspect_theme_weighting", []):
        if row["aspect_id"] not in aspect_ids:
            raise ValueError(f"Unknown aspect_id in aspect_theme_weighting: {row['aspect_id']}")
        if row["theme_id"] not in theme_ids:
            raise ValueError(f"Unknown theme_id in aspect_theme_weighting: {row['theme_id']}")
        assert_in_range(row["weight"], "weight")

    print("Ontology mappings validation: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
