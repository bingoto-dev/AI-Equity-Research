# Service Interfaces (Draft)

## 1) Services

### Ingestion (ingestion-service)
- Responsibilities: fetch sources, store raw docs, emit ingestion events.
- Interfaces:
  - POST /ingest/filings
  - POST /ingest/macro
  - POST /ingest/market
  - POST /ingest/news
- Emits:
  - ingest.completed

### Normalization + Entity Resolution (entity-service)
- Responsibilities: canonicalize entities, tag themes, update graph links.
- Interfaces:
  - POST /entities/resolve
  - POST /themes/tag
- Emits:
  - entities.resolved
  - themes.tagged

### Evidence Pack Service (evidence-service)
- Responsibilities: build evidence packs with provenance.
- Interfaces:
  - POST /evidence/build
  - GET /evidence/{theme_id}/{date}
- Emits:
  - evidence.ready

### Memo Service (memo-service)
- Responsibilities: draft memos, manage versions.
- Interfaces:
  - POST /memos/draft
  - POST /memos/publish
  - GET /memos/{memo_id}
- Emits:
  - memo.draft
  - memo.published

### Scoring Service (scoring-service)
- Responsibilities: run analyst swarm scoring.
- Interfaces:
  - POST /scores/run
  - GET /scores/{memo_id}
- Emits:
  - scoring.completed

### Landscape Service (landscape-service)
- Responsibilities: daily AI landscape brief.
- Interfaces:
  - POST /landscape/generate
  - GET /landscape/{date}
- Emits:
  - landscape.published

### Alerts Service (alerts-service)
- Responsibilities: watchlists and triggers.
- Interfaces:
  - POST /alerts/subscribe
  - POST /alerts/trigger
  - GET /alerts/{user_id}
- Emits:
  - alert.sent

## 2) Event Topics (Pub/Sub)
- ingest.completed
- entities.resolved
- themes.tagged
- evidence.ready
- memo.draft
- scoring.completed
- memo.published
- landscape.published
- alert.sent

## 3) Core Payload Schemas (JSON)

### ingest.completed
```
{
  "source": "sec|macro|market|news",
  "batch_id": "uuid",
  "started_at": "iso8601",
  "ended_at": "iso8601",
  "raw_count": 123
}
```

### entities.resolved
```
{
  "batch_id": "uuid",
  "resolved_entities": 456,
  "unresolved_entities": 12
}
```

### evidence.ready
```
{
  "theme_id": "THM-ai-compute",
  "date": "YYYY-MM-DD",
  "evidence_pack_id": "uuid",
  "corroboration_avg": 2.4
}
```

### memo.published
```
{
  "memo_id": "uuid",
  "theme_id": "THM-ai-compute",
  "version": 3,
  "confidence": 78,
  "score": 4.1
}
```

### landscape.published
```
{
  "date": "YYYY-MM-DD",
  "top_verticals": ["VRT-compute-semiconductors", "VRT-model-providers"],
  "top_companies": ["CMP-NVDA", "CMP-MSFT"],
  "delta_summary": "string"
}
```

## 4) Service Dependencies
- ingestion-service -> entity-service -> evidence-service -> memo-service -> scoring-service -> landscape-service -> alerts-service

## 5) Failure Handling
- Retries on transient errors.
- Dead-letter queue for repeated failures.
- Partial pipeline allowed; memo publish requires evidence + scoring.
