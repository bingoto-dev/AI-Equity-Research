# Deep Insights Platform PRD

## 1) Vision
Build the highest-depth, one-stop research hub for thematic equity investing and global macro trading. The platform continuously produces daily and long-form memos with first-principles reasoning, explicit second/third-order effects, and quantified conviction. It serves as a living map of the AI landscape and adjacent themes, with transparent evidence trails and analyst-swarm scoring.

## 2) Problem Statement
Today, thematic research is fragmented across reports, news, and ad-hoc notes. Analysts spend disproportionate time collecting data rather than forming causal views. Macro-to-micro transmission is rarely formalized, and second/third-order impacts are inconsistently tracked. The AI landscape changes daily, making historical context and current deltas hard to maintain.

## 3) Goals
- Centralize thematic research into a single, searchable hub.
- Provide daily landscape updates with explicit deltas and catalysts.
- Produce high-quality memos with causal chains and uncertainty tracking.
- Use agent swarms to scale research volume without sacrificing rigor.
- Score memos via multi-analyst consensus and track outcome accuracy.

## 4) Non-Goals (MVP)
- Automated trade execution or portfolio optimization.
- Personalized client reporting or regulatory filings.
- Real-time tick-level trading signals.

## 5) Target Users and Jobs-to-be-Done
- Buy-side analyst: build/refresh thematic theses faster and with better evidence.
- Macro trader: map policy/credit/flows into asset-level implications.
- Research lead: track analyst output quality and evidence consistency.
- Strategy team: monitor AI landscape shifts and competitive dynamics.

## 6) Core User Journeys
1) Daily AI landscape brief
   - See top verticals/aspects/companies with reasons for movement.
   - Click into evidence packs and memo summaries.
2) Theme deep-dive
   - Review hypothesis, causal map, scenarios, and catalysts.
   - Inspect evidence, counter-arguments, and uncertainty.
3) Macro transmission map
   - Start at policy/credit/flows and trace to assets/themes.
   - Evaluate second/third-order effects and signposts.
4) Watchlist and alerts
   - Subscribe to themes/companies and receive updates on catalysts.

## 7) Functional Requirements
### 7.1 Research Ingestion
- Collect structured and unstructured data from market, macro, policy, and company sources.
- Normalize entities across sources (tickers, subsidiaries, products).
- Tag signals to themes, verticals, and aspects.

### 7.2 Evidence Packs
- Multi-source corroboration with recency and reliability scoring.
- Extract key datapoints with provenance.
- Attach counter-evidence and uncertainty flags.

### 7.3 Memo Production
- Standard template with thesis, mechanism, evidence, effects, catalysts, risks, and signposts.
- Versioned updates when new evidence arrives.
- Explicit confidence scoring and probability ranges.

### 7.4 Analyst Swarm Scoring
- Multi-agent scoring rubric with weighted consensus.
- Calibration against historical outcomes.
- Red-team checks for disconfirming evidence.

### 7.5 Knowledge Graph
- Entities: themes, verticals, aspects, companies, products, policies, macro indicators.
- Relationships: causal links, exposure links, supply-chain links, and competitive links.
- Versioned ontology to prevent drift.

### 7.6 Hub UX
- Home dashboard with daily landscape and top memos.
- Theme and company pages with causal maps and evidence packs.
- Macro dashboard linking policy/flows to themes.
- Alerts and watchlists.

## 8) Non-Functional Requirements
- Freshness: daily updates for core landscape, event-driven updates for breaking catalysts.
- Auditability: every claim traceable to a source or derived computation.
- Reliability: scheduler resiliency and task retries.
- Cost control: token budgets, caching, and reuse of evidence packs.
- Security: role-based access and source licensing compliance.

## 9) Success Metrics
- Time-to-memo: median hours from catalyst to published memo.
- Evidence quality: average corroboration count per key claim.
- Analyst agreement: variance in scoring across swarm.
- Outcome calibration: confidence vs realized impact accuracy.
- User engagement: daily active analysts and memo read-through rate.

## 10) Risks and Mitigations
- Hallucination risk: enforce evidence-only claims with provenance checks.
- Source bias: diversify sources and add counter-thesis agents.
- Drift in taxonomy: versioned ontology and periodic review.
- Swarm coordination failure: explicit task ownership and judge gating.

## 11) MVP Scope
- Daily AI landscape brief (top verticals/aspects/companies).
- Memo template + scoring rubric + evidence packs.
- Knowledge graph v1 with theme/company/policy links.
- Alerts, watchlists, and memo refresh workflow.

## 12) Out-of-Scope (Phase 1)
- Automated trade execution.
- Full personalization or client segmentation.
- Advanced portfolio analytics.

