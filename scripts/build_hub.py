#!/usr/bin/env python3
"""Build static HTML hub from daily JSON outputs."""

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from jinja2 import Environment, FileSystemLoader

try:
    import markdown
except ImportError as exc:
    raise SystemExit("Missing dependency: markdown. Run `pip install markdown`.") from exc


def _find_latest_report(reports_dir: Path) -> str:
    candidates = sorted(reports_dir.glob("landscape_*.json"))
    if not candidates:
        raise SystemExit("No landscape JSON files found. Run scripts/run_hub_daily.py first.")
    latest = candidates[-1]
    return latest.stem.replace("landscape_", "")


def _find_previous_report(reports_dir: Path, report_date: str) -> Optional[str]:
    candidates = sorted(reports_dir.glob("landscape_*.json"))
    dates = [c.stem.replace("landscape_", "") for c in candidates]
    if report_date not in dates:
        return None
    idx = dates.index(report_date)
    if idx == 0:
        return None
    return dates[idx - 1]


def _add_rank_deltas(current: List[Dict[str, Any]], previous: List[Dict[str, Any]], key: str) -> List[Dict[str, Any]]:
    prev_rank = {item[key]: idx for idx, item in enumerate(previous, start=1)}
    updated = []
    for idx, item in enumerate(current, start=1):
        delta = None
        prev = prev_rank.get(item[key])
        if prev is not None:
            delta = prev - idx
        updated.append({**item, "delta": delta})
    return updated


def _load_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def build_hub(report_date: str, reports_dir: Path, templates_dir: Path, output_dir: Path) -> None:
    landscape_path = reports_dir / f"landscape_{report_date}.json"
    memos_path = reports_dir / f"memos_{report_date}.json"

    landscape = _load_json(landscape_path)
    memos = _load_json(memos_path) if memos_path.exists() else {"memos": []}

    prev_date = _find_previous_report(reports_dir, report_date)
    prev_landscape = _load_json(reports_dir / f"landscape_{prev_date}.json") if prev_date else None

    top_verticals = landscape.get("top_verticals", [])
    top_aspects = landscape.get("top_aspects", [])
    top_companies = landscape.get("top_companies", [])

    if prev_landscape:
        top_verticals = _add_rank_deltas(top_verticals, prev_landscape.get("top_verticals", []), "id")
        top_aspects = _add_rank_deltas(top_aspects, prev_landscape.get("top_aspects", []), "id")
        top_companies = _add_rank_deltas(top_companies, prev_landscape.get("top_companies", []), "ticker")

    env = Environment(loader=FileSystemLoader(str(templates_dir)), autoescape=False)

    memo_dir = output_dir / "memos"
    memo_dir.mkdir(parents=True, exist_ok=True)

    memo_entries = []
    memo_template = env.get_template("hub_memo.html.j2")
    for memo in memos.get("memos", []):
        memo_md_path = Path(memo["path"])
        memo_html = ""
        if memo_md_path.exists():
            memo_html = markdown.markdown(memo_md_path.read_text(encoding="utf-8"))
        memo_output = memo_dir / f"{memo['theme_id']}_{report_date}.html"
        memo_content = memo_template.render(
            theme_id=memo["theme_id"],
            date=report_date,
            aggregate_score=memo.get("aggregate_score", 0),
            top_companies=memo.get("top_companies", []),
            memo_html=memo_html,
        )
        memo_output.write_text(memo_content, encoding="utf-8")
        memo_entries.append({
            "theme_id": memo["theme_id"],
            "aggregate_score": memo.get("aggregate_score", 0),
            "summary": memo.get("summary", ""),
            "link": f"memos/{memo_output.name}",
            "verticals": memo.get("verticals", []),
            "aspects": memo.get("aspects", []),
        })

    memo_entries.sort(key=lambda x: x["aggregate_score"], reverse=True)

    index_template = env.get_template("hub_index.html.j2")
    index_content = index_template.render(
        report_date=report_date,
        memos=memo_entries,
        top_verticals=top_verticals,
        top_aspects=top_aspects,
        top_companies=top_companies,
        prev_date=prev_date,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "index.html").write_text(index_content, encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Build static hub HTML")
    parser.add_argument("--reports-dir", default="data/reports", help="Reports directory")
    parser.add_argument("--templates-dir", default="src/reports/templates", help="Templates directory")
    parser.add_argument("--output-dir", default="data/hub", help="Output directory")
    parser.add_argument("--date", default=None, help="Report date YYYY-MM-DD")

    args = parser.parse_args()
    report_date = args.date or _find_latest_report(Path(args.reports_dir))

    build_hub(
        report_date=report_date,
        reports_dir=Path(args.reports_dir),
        templates_dir=Path(args.templates_dir),
        output_dir=Path(args.output_dir),
    )

    print(f"Hub built for {report_date} in {args.output_dir}")


if __name__ == "__main__":
    main()
