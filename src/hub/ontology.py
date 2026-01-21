"""Ontology loader and mapping helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Tuple


@dataclass
class OntologyMapping:
    """Load and manage ontology mappings from JSON."""

    raw: Dict[str, Any]
    theme_company: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    theme_vertical_aspect: List[Dict[str, Any]] = field(default_factory=list)
    vertical_company: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    aspect_theme_weighting: List[Dict[str, Any]] = field(default_factory=list)

    @classmethod
    def load(cls, path: Path) -> "OntologyMapping":
        with open(path, "r", encoding="utf-8") as handle:
            raw = json.load(handle)
        mapping = cls(raw=raw)
        mapping._index()
        return mapping

    def _index(self) -> None:
        self.theme_vertical_aspect = self.raw.get("theme_vertical_aspect", [])
        self.aspect_theme_weighting = self.raw.get("aspect_theme_weighting", [])

        self.theme_company = {}
        for row in self.raw.get("theme_company_exposure", []):
            self.theme_company.setdefault(row["theme_id"], []).append(row)

        self.vertical_company = {}
        for row in self.raw.get("vertical_company_exposure", []):
            self.vertical_company.setdefault(row["vertical_id"], []).append(row)

    @property
    def theme_ids(self) -> List[str]:
        return list(self.raw.get("id_sets", {}).get("themes", []))

    @property
    def vertical_ids(self) -> List[str]:
        return list(self.raw.get("id_sets", {}).get("verticals", []))

    @property
    def aspect_ids(self) -> List[str]:
        return list(self.raw.get("id_sets", {}).get("aspects", []))

    @property
    def company_ids(self) -> List[str]:
        return list(self.raw.get("id_sets", {}).get("companies", []))

    def company_id_to_ticker(self, company_id: str) -> str:
        if company_id.startswith("CMP-"):
            return company_id.replace("CMP-", "")
        return company_id

    def ticker_to_company_id(self, ticker: str) -> str:
        if ticker.startswith("CMP-"):
            return ticker
        return f"CMP-{ticker}"

    def get_theme_companies(self, theme_id: str) -> List[Tuple[str, float]]:
        companies = []
        for row in self.theme_company.get(theme_id, []):
            companies.append((row["company_id"], float(row.get("exposure_strength", 0))))
        return companies

    def get_theme_verticals(self, theme_id: str) -> List[str]:
        return [
            row["vertical_id"]
            for row in self.theme_vertical_aspect
            if row["theme_id"] == theme_id
        ]

    def get_theme_aspects(self, theme_id: str) -> List[str]:
        return [
            row["aspect_id"]
            for row in self.theme_vertical_aspect
            if row["theme_id"] == theme_id
        ]

    def get_vertical_companies(self, vertical_id: str) -> List[Tuple[str, float]]:
        companies = []
        for row in self.vertical_company.get(vertical_id, []):
            companies.append((row["company_id"], float(row.get("exposure_strength", 0))))
        return companies

