# Ontology v0 (MVP)

## 1) Purpose
Provide a stable, versioned taxonomy for themes, verticals, aspects, and entities so that ingestion, memoing, and scoring are consistent and traceable.

## 2) Versioning
- ontology_version: v0
- owner: research_ops
- change_log: tracked in git + memo metadata

## 3) Core Entity Types
- Theme
- Vertical
- Aspect
- Company
- Product
- MacroIndicator
- PolicyEvent
- Signal
- Evidence

## 4) ID Conventions
- theme: THM-<slug>
- vertical: VRT-<slug>
- aspect: ASP-<slug>
- company: CMP-<ticker>
- product: PRD-<company>-<slug>
- macro_indicator: MAC-<slug>
- policy_event: POL-<yyyymmdd>-<region>-<slug>

## 5) Theme Hierarchy (Draft)

### AI Platform Stack
- THM-ai-compute
- THM-ai-infrastructure
- THM-ai-foundation-models
- THM-ai-mlops
- THM-ai-edge

### AI Adoption by Industry
- THM-ai-healthcare
- THM-ai-finance
- THM-ai-manufacturing
- THM-ai-retail
- THM-ai-public-sector

### Macro-Linked Themes
- THM-ai-capex-cycle
- THM-ai-energy-demand
- THM-ai-regulatory-risk

## 6) Verticals (Draft)
- VRT-compute-semiconductors
- VRT-hyperscalers-cloud
- VRT-data-platforms
- VRT-model-providers
- VRT-mlops-tooling
- VRT-edge-devices
- VRT-applications
- VRT-cybersecurity-safety
- VRT-robotics-automation
- VRT-networking-interconnect

## 7) Aspects (Cross-Cutting)
- ASP-compute-efficiency
- ASP-inference-cost
- ASP-data-quality
- ASP-model-performance
- ASP-distribution
- ASP-regulation-policy
- ASP-capital-intensity
- ASP-supply-chain-constraints
- ASP-competitive-moat
- ASP-talent-signals

## 8) Mapping Rules
- Theme -> Vertical: 1..n
- Theme -> Aspect: 1..n
- Company -> Theme: exposure_strength in [0..1]
- PolicyEvent -> MacroIndicator: impact_strength in [0..1]

## 9) MVP Source Mappings

### Filings (SEC EDGAR)
- Entities: Company, Product, Evidence
- Usage: risk factors, segment performance, capex guidance
- Mapping: evidence -> company -> theme

### Macro Releases (FRED / BLS / BEA)
- Entities: MacroIndicator, Evidence
- Usage: rates, inflation, labor, productivity
- Mapping: macro_indicator -> theme (via causal edges)

### Market Data (Yahoo / Alpha Vantage)
- Entities: Signal
- Usage: price/volume, valuation proxies
- Mapping: signal -> company -> theme

### News (NewsAPI / RSS)
- Entities: Evidence, PolicyEvent
- Usage: catalysts, competitive moves
- Mapping: policy_event -> macro_indicator -> theme

### Optional MVP+ Sources
- Hiring signals (LinkedIn-style data)
- Patent filings
- Cloud spend proxies
- GPU shipment and lead-time data

## 10) Governance
- Changes to ontology require:
  - version bump
  - updated theme mappings
  - memo backfill where impacted

## 11) Mappings
- Seed mappings and source field mappings are maintained in: docs/spec/ONTOLOGY_MAPPINGS.md
