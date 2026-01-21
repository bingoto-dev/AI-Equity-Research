# Mapping Review Workflow

## Purpose
Ensure ontology mappings are evidence-backed, auditable, and consistently applied across memos and dashboards.

## Roles
- Reviewer: validates evidence and approves mapping changes.
- Editor: proposes changes with supporting evidence.
- Auditor: periodically checks change logs and evidence sufficiency.

## Change Rules
- All seed mappings require confirmation with at least two independent sources before being marked confirmed.
- Exposure strengths must be updated only when evidence packs change or a reviewer approves an override.
- Each change must include:
  - prior value
  - new value
  - evidence sources (links or IDs)
  - reviewer name
  - date

## Change Log Format (Markdown)
```
- date: YYYY-MM-DD
  item: theme_company_exposure
  key: THM-ai-compute -> CMP-NVDA
  prior: 0.80
  new: 0.90
  evidence: [source_id_1, source_id_2]
  reviewer: name
```

## Evidence Requirements
- At least one primary source (filing, transcript, or official release).
- At least one corroborating source (independent report or dataset).

## Review Cadence
- Monthly review of top 20 most-impactful mappings.
- Quarterly review of full theme-to-vertical-to-aspect map.

