# Sprint Backlog (Draft)

Assume 2-week sprints. Adjust as needed.

## Sprint 0: Foundations

### Epic: Repo + Architecture Baseline
- Story: Define core repo structure for services and docs.
  - Acceptance: directories for ingestion, orchestration, storage, and UI exist with placeholders; spec docs referenced in top-level README or SPEC.md.
- Story: Establish environment config and secrets pattern.
  - Acceptance: .env.example includes keys for data sources, LLM providers, and notification channels.

### Epic: Ontology v0
- Story: Create v0 ontology and mappings.
  - Acceptance: ontology file with themes/verticals/aspects and ID conventions exists; mapping rules described.

## Sprint 1: Ingestion + Normalization

### Epic: Ingestion MVP
- Story: Ingest SEC filings.
  - Acceptance: filings are fetched daily and stored in raw source store with metadata.
- Story: Ingest macro releases.
  - Acceptance: indicators are stored with timestamps and units.
- Story: Ingest market data.
  - Acceptance: daily price/volume signals stored for tracked companies.
- Story: Ingest news.
  - Acceptance: news items stored with source and timestamp.

### Epic: Entity Resolution
- Story: Normalize company identities across sources.
  - Acceptance: tickers map to a canonical company ID; duplicates flagged.
- Story: Theme tagging rules for evidence.
  - Acceptance: evidence records include theme tags or confidence scores.

## Sprint 2: Evidence Packs + Memo Drafting

### Epic: Evidence Pack Generation
- Story: Create evidence packs with provenance.
  - Acceptance: evidence pack includes sources, recency, and corroboration count.
- Story: Counter-evidence capture.
  - Acceptance: at least one counter-evidence field per memo.

### Epic: Memo Drafting
- Story: Generate memo drafts from evidence packs.
  - Acceptance: memos follow template and include first/second/third-order effects.
- Story: Memo versioning and updates.
  - Acceptance: new evidence creates a new memo version with change log.

## Sprint 3: Swarm Scoring + Daily Brief

### Epic: Swarm Scoring
- Story: Analyst agents score memos via rubric.
  - Acceptance: multiple agent scores stored; aggregate score computed.
- Story: Red-team check.
  - Acceptance: disconfirming evidence is required before publishing.

### Epic: Daily Landscape Brief
- Story: Generate daily AI landscape summary.
  - Acceptance: output includes top verticals, aspects, companies, and deltas.
- Story: Publish to hub.
  - Acceptance: daily brief is saved and retrievable via API/UI.

## Sprint 4: Product Layer + Alerts

### Epic: Theme/Company Pages
- Story: Theme page with causal map and evidence pack.
  - Acceptance: theme page renders memo summary, causal edges, and key evidence.
- Story: Company page with theme exposure.
  - Acceptance: company page shows exposure list and key signals.

### Epic: Alerts
- Story: Watchlists with catalyst triggers.
  - Acceptance: alerts fire on defined events or confidence changes.

