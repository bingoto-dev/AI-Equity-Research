# Implementation Guide (MVP)

## 1) Environment Setup
- Install dependencies: `pip install -e .`
- Create `.env` from `config/.env.example`
- Provide API keys for optional sources:
  - DATA_NEWS_API_KEY
  - DATA_ALPHA_VANTAGE_KEY
  - DATA_FRED_API_KEY
  - DATA_GITHUB_TOKEN

## 2) Daily Landscape + Memos
Run the daily pipeline:

```bash
python scripts/run_hub_daily.py
```

Outputs:
- `data/reports/landscape_YYYY-MM-DD.md`
- `data/reports/memos/<theme_id>_YYYY-MM-DD.md`

## 3) Ontology Updates
- Update `docs/spec/ONTOLOGY_MAPPINGS.json`
- Validate mappings:

```bash
python scripts/validate_ontology_mappings.py docs/spec/ONTOLOGY_MAPPINGS.json
```

- Export CSVs:

```bash
python scripts/export_ontology_mappings_csv.py docs/spec/ONTOLOGY_MAPPINGS.json docs/spec/mappings
```

## 4) Operational Cadence
- Daily run before market open (default 6 AM ET)
- Weekly mapping review for top themes
- Monthly ontology review

