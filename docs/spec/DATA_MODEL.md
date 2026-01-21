# Deep Insights Data Model

## 1) Core Entities (Conceptual)

### Theme
- id, name, description, status, version
- parent_theme_id (optional)
- tags

### Vertical
- id, name, description, version
- mapped_themes[]

### Aspect
- id, name, description, version
- mapped_themes[]

### Company
- id, name, ticker, lei, country, sector
- parent_company_id (optional)
- products[]

### Product
- id, name, company_id
- category, description

### MacroIndicator
- id, name, category (rates, inflation, credit, FX, commodities)
- unit, frequency

### PolicyEvent
- id, name, region, policy_type
- decision_date, effective_date
- summary

### Signal
- id, signal_type, source_id
- entity_type + entity_id
- timestamp, value, unit
- derived (bool)

### Evidence
- id, source_id, entity_type + entity_id
- excerpt, summary, timestamp
- reliability_score, corroboration_count

### Hypothesis
- id, theme_id, summary
- created_at, status

### CausalEdge
- id, from_entity, to_entity
- effect_type (first/second/third order)
- sign (+/-), confidence

### Scenario
- id, hypothesis_id, title
- assumptions, triggers, outcomes

### Memo
- id, theme_id, author_agent_id
- version, status, created_at
- thesis, mechanism, effects, catalysts, risks

### Score
- id, memo_id, agent_id
- rubric_scores (json), aggregate_score

### Agent
- id, name, role, model

### Source
- id, name, license, url, type

### Watchlist
- id, user_id, entity_type + entity_id

### Alert
- id, watchlist_id, trigger, severity, status

## 2) Graph Relationships (Examples)
- Theme -> Vertical (belongs_to)
- Theme -> Aspect (has_aspect)
- Theme -> Company (exposed_to)
- Company -> Product (produces)
- Company -> Company (supplier_of / competitor_of)
- PolicyEvent -> MacroIndicator (impacts)
- MacroIndicator -> Theme (transmits_to)
- Signal -> Entity (measured_for)
- Evidence -> Hypothesis (supports/contradicts)
- Hypothesis -> Memo (documented_by)
- Memo -> Theme (analyzes)

## 3) Relational Schema (MVP)

### themes
- theme_id (pk)
- name
- description
- parent_theme_id
- version

### verticals
- vertical_id (pk)
- name
- description
- version

### aspects
- aspect_id (pk)
- name
- description
- version

### companies
- company_id (pk)
- name
- ticker
- lei
- country

### products
- product_id (pk)
- company_id (fk)
- name
- category

### macro_indicators
- indicator_id (pk)
- name
- category
- unit
- frequency

### policy_events
- policy_event_id (pk)
- name
- region
- policy_type
- decision_date
- effective_date

### signals
- signal_id (pk)
- source_id (fk)
- entity_type
- entity_id
- timestamp
- value
- unit
- derived

### evidence
- evidence_id (pk)
- source_id (fk)
- entity_type
- entity_id
- timestamp
- summary
- reliability_score
- corroboration_count

### hypotheses
- hypothesis_id (pk)
- theme_id (fk)
- summary
- status

### causal_edges
- edge_id (pk)
- from_entity_type
- from_entity_id
- to_entity_type
- to_entity_id
- effect_type
- sign
- confidence

### scenarios
- scenario_id (pk)
- hypothesis_id (fk)
- title
- assumptions
- triggers
- outcomes

### memos
- memo_id (pk)
- theme_id (fk)
- author_agent_id (fk)
- version
- status
- created_at
- thesis
- mechanism
- effects
- catalysts
- risks

### scores
- score_id (pk)
- memo_id (fk)
- agent_id (fk)
- rubric_scores
- aggregate_score

### agents
- agent_id (pk)
- name
- role
- model

### sources
- source_id (pk)
- name
- license
- url
- type

### watchlists
- watchlist_id (pk)
- user_id
- entity_type
- entity_id

### alerts
- alert_id (pk)
- watchlist_id (fk)
- trigger
- severity
- status

## 4) Indexing and Performance Notes
- Composite indexes: (entity_type, entity_id, timestamp) for signals/evidence.
- Full-text indexes for memo sections and evidence summaries.
- Graph store for causal_edges and relationship queries.

## 5) Versioning and Auditability
- Versioned memo records with diffs.
- Immutable raw source storage.
- Ontology versioning for themes/verticals/aspects.

