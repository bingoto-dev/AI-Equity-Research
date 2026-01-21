# Ontology Mappings v0 (Seed)

## 1) Versioning
- ontology_version: v0
- mapping_version: v0.1
- owner: research_ops
- update_cadence: monthly or on major theme shifts

## 2) Theme ↔ Vertical ↔ Aspect (Seed Map)

Each row links a theme to one or more verticals and aspects. This is a seed map and will be refined based on evidence packs.

| Theme ID | Theme Name | Vertical ID | Aspect ID | Rationale (short) |
|---|---|---|---|---|
| THM-ai-compute | AI Compute | VRT-compute-semiconductors | ASP-compute-efficiency | Perf/watt and scaling constraints |
| THM-ai-compute | AI Compute | VRT-networking-interconnect | ASP-capital-intensity | Cluster capex + networking bottlenecks |
| THM-ai-infrastructure | AI Infrastructure | VRT-hyperscalers-cloud | ASP-inference-cost | Unit economics of AI workloads |
| THM-ai-infrastructure | AI Infrastructure | VRT-data-platforms | ASP-data-quality | Data pipelines as core input |
| THM-ai-foundation-models | Foundation Models | VRT-model-providers | ASP-model-performance | Frontier model progress |
| THM-ai-mlops | MLOps | VRT-mlops-tooling | ASP-distribution | Deployment and lifecycle tooling |
| THM-ai-edge | Edge AI | VRT-edge-devices | ASP-compute-efficiency | On-device inference constraints |
| THM-ai-applications | AI Applications | VRT-applications | ASP-competitive-moat | Workflow lock-in and data flywheel |
| THM-ai-regulatory-risk | AI Regulatory Risk | VRT-cybersecurity-safety | ASP-regulation-policy | Policy headwinds or tailwinds |
| THM-ai-capex-cycle | AI Capex Cycle | VRT-hyperscalers-cloud | ASP-capital-intensity | Hyperscaler capex cycles |
| THM-ai-energy-demand | AI Energy Demand | VRT-compute-semiconductors | ASP-supply-chain-constraints | Power and grid limits |

## 3) Theme ↔ Company (Seed Exposure Map)

Notes:
- Exposure strength is a 0-1 heuristic seed; must be validated by evidence packs.
- Companies listed are examples to bootstrap research; not exhaustive.

| Theme ID | Company ID | Exposure Strength | Evidence Required |
|---|---|---|---|
| THM-ai-compute | CMP-NVDA | 0.9 | GPU revenue mix, datacenter segment growth |
| THM-ai-compute | CMP-AMD | 0.6 | AI accelerator roadmap, DC revenue split |
| THM-ai-compute | CMP-TSM | 0.8 | Advanced node utilization and AI demand |
| THM-ai-compute | CMP-ASML | 0.7 | EUV demand, foundry capex signals |
| THM-ai-infrastructure | CMP-MSFT | 0.8 | Azure AI workload share and capex |
| THM-ai-infrastructure | CMP-AMZN | 0.7 | AWS AI/ML workload growth |
| THM-ai-infrastructure | CMP-GOOGL | 0.7 | GCP AI workload growth |
| THM-ai-foundation-models | CMP-OPENAI | 0.8 | Model releases and usage metrics |
| THM-ai-mlops | CMP-DATA | 0.5 | MLOps adoption metrics |
| THM-ai-edge | CMP-AAPL | 0.5 | On-device inference features |
| THM-ai-applications | CMP-META | 0.6 | AI feature usage and engagement impact |
| THM-ai-regulatory-risk | CMP-ANY | 0.4 | Jurisdictional compliance exposure |

## 4) Vertical ↔ Company (Seed Exposure Map)

| Vertical ID | Company ID | Exposure Strength | Evidence Required |
|---|---|---|---|
| VRT-compute-semiconductors | CMP-NVDA | 0.9 | DC GPU share, pricing power |
| VRT-compute-semiconductors | CMP-TSM | 0.8 | AI node demand and capacity |
| VRT-networking-interconnect | CMP-AVGO | 0.6 | Networking silicon demand |
| VRT-hyperscalers-cloud | CMP-MSFT | 0.8 | AI capex and utilization |
| VRT-hyperscalers-cloud | CMP-AMZN | 0.7 | AI service revenue mix |
| VRT-model-providers | CMP-OPENAI | 0.8 | Model launches + usage |
| VRT-mlops-tooling | CMP-DATA | 0.5 | Tool adoption and enterprise spend |
| VRT-edge-devices | CMP-AAPL | 0.6 | On-device AI feature rollout |
| VRT-applications | CMP-ADBE | 0.6 | AI feature monetization |

## 5) Aspect ↔ Theme (Seed Weighting)

| Aspect ID | Theme ID | Weight | Notes |
|---|---|---|---|
| ASP-compute-efficiency | THM-ai-compute | 0.35 | Perf/watt drives scaling |
| ASP-inference-cost | THM-ai-infrastructure | 0.25 | Unit economics gating adoption |
| ASP-data-quality | THM-ai-infrastructure | 0.20 | Data gravity limits |
| ASP-regulation-policy | THM-ai-regulatory-risk | 0.50 | Policy risk dominates |
| ASP-capital-intensity | THM-ai-capex-cycle | 0.40 | Capex cycles drive supply |
| ASP-supply-chain-constraints | THM-ai-energy-demand | 0.30 | Power limits and lead-times |

## 6) Source Field Mappings (Concrete)

### SEC EDGAR (Filings)
- source_type: sec_edgar
- fields:
  - cik
  - company_name
  - ticker (if available)
  - form_type (10-K, 10-Q, 8-K)
  - filing_date
  - accession
  - filing_url
  - section (risk_factors, md&a, segments)
  - excerpt
- mapping:
  - company_id = CMP-<ticker>
  - evidence.entity_type = company
  - evidence.summary = excerpt

### Macro Releases (FRED/BLS/BEA)
- source_type: macro_release
- fields:
  - series_id
  - indicator_name
  - observation_date
  - value
  - unit
  - frequency
- mapping:
  - macro_indicator_id = MAC-<slug>
  - signal.entity_type = macro_indicator

### Market Data (Yahoo/Alpha Vantage)
- source_type: market_data
- fields:
  - ticker
  - date
  - open
  - high
  - low
  - close
  - volume
- mapping:
  - company_id = CMP-<ticker>
  - signal.entity_type = company

### News (NewsAPI/RSS)
- source_type: news
- fields:
  - source_name
  - title
  - description
  - published_at
  - url
- mapping:
  - evidence.entity_type = theme or company
  - policy_event_id = POL-<yyyymmdd>-<region>-<slug> (if applicable)

## 7) Governance Rules
- All seed mappings must be validated by at least 2 evidence sources before being marked as “confirmed.”
- Exposure strengths are updated only by evidence pack outcomes or analyst override with justification.
- A mapping change must log:
  - prior value
  - new value
  - evidence sources
  - reviewer

