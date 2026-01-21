# Deep Insights Platform Architecture

## 1) High-Level System Diagram

```
+-----------------+      +-----------------+      +-------------------+
|  External Data  | ---> |  Ingestion Bus  | ---> |  Raw Source Store |
|  APIs/Feeds     |      |  + Schedulers   |      |  (docs + files)   |
+-----------------+      +-----------------+      +-------------------+
                                   |
                                   v
                         +-------------------+
                         |  Normalize + ETL  |
                         |  Entity Resolver  |
                         +-------------------+
                                   |
                                   v
                         +-------------------+
                         | Knowledge Graph   |
                         | + Metrics Store   |
                         +-------------------+
                                   |
                                   v
+-----------------+      +-------------------+      +-------------------+
|  Agent Swarm    | <--> | Orchestrator/API  | <--> |   Product UI      |
| (planner/judge) |      | + Task Queue      |      |  Web + Alerts     |
+-----------------+      +-------------------+      +-------------------+
                                   |
                                   v
                         +-------------------+
                         | Memo + Evidence   |
                         | Store + Scoring   |
                         +-------------------+

Observability: logging, tracing, evaluation, cost controls across all services.
```

## 2) Core Components

### 2.1 Ingestion Layer
- Connectors for market, macro, policy/regulatory, filings, earnings, supply-chain, and alt data.
- Scheduler for daily cadence plus event-driven triggers.
- Raw source store for immutable inputs.

### 2.2 Normalization and Entity Resolution
- Deduplicate entities across sources (ticker, LEI, subsidiaries).
- Standardize timestamps and time zones.
- Tag records to themes, verticals, aspects, and macro categories.

### 2.3 Knowledge Graph + Metrics Store
- Graph: entities and relationships with versioned ontology.
- Metrics store: time-series signals, KPIs, and derived indicators.
- Lineage: every derived metric linked to raw sources.

### 2.4 Agent Swarm Runtime
- Planner: decomposes research tasks into work units.
- Workers: collect evidence, build causal maps, draft memos.
- Judge: enforces quality gates, evidence sufficiency, and rubric compliance.
- Red-team: seeks disconfirming evidence.
- Model router: selects models based on task type (planning vs extraction vs synthesis).

### 2.5 Orchestrator + Task Queue
- Append-only task queue with explicit ownership.
- Optimistic concurrency and retries for long-running tasks.
- Periodic re-planning to avoid drift.

### 2.6 Memo, Evidence, and Scoring Store
- Evidence pack with corroboration count and confidence labels.
- Memo versions with diffs and change logs.
- Scoring records per analyst agent and aggregated score.

### 2.7 Product Layer
- Web UI: dashboards, theme pages, company pages, macro maps.
- Alerts: Slack/email/webhook for catalysts and confidence changes.

## 3) Swarm Coordination Principles
- Hierarchical worker pattern (planner -> sub-planners -> workers -> judge).
- Minimal coordination structure: avoid heavy locking and fragile global state.
- Model specialization by role to reduce cost and improve quality.
- Regular resets and re-planning checkpoints to reduce drift.

## 4) Data Flow (Daily Cycle)
1) Ingest new sources and update raw store.
2) Normalize, resolve entities, and update graph/metrics.
3) Generate hypotheses and evidence packs for key themes.
4) Run swarm memo production and scoring.
5) Publish daily AI landscape brief and trigger alerts.

## 5) Reliability + Cost Controls
- Budget per theme/memo to cap token usage.
- Caching of evidence packs and repeated extractions.
- Retry policy for source failures and partial data.

## 6) Security + Compliance
- Licensing metadata for all sources.
- Immutable audit trail for published memos.
- Role-based access for internal vs external views.

## References
- https://simonwillison.net/2026/Jan/19/scaling-long-running-autonomous-coding/
- https://cursor.com/blog/scaling-agents

