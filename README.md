# AI Equity Research Multi-Agent System

A Python-based multi-agent system with 8 specialized AI analysts that research AI value chain companies in a convergence loop until the Top 3 investment picks stabilize.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  LOOP START                                                  │
│                                                              │
│  Layer 1: 3 Primary Analysts (parallel)                     │
│  ├── Alpha (AI Hardware/Chips) → Top 5                      │
│  ├── Beta (AI Software/Cloud) → Top 5                       │
│  └── Gamma (AI Applications) → Top 5                        │
│                    ↓                                         │
│            Combined Pool: ~15 companies                      │
│                    ↓                                         │
│  Layer 2: 3 Secondary Analysts (parallel)                   │
│  ├── Delta (Fundamentals) → Top 5                           │
│  ├── Epsilon (Technicals) → Top 5                           │
│  └── Zeta (Risk/Contrarian) → Top 5                         │
│                    ↓                                         │
│  Layer 3: Fund Manager                                      │
│  └── Reviews 3 Top 5s → Creates Top 3                       │
│                    ↓                                         │
│  Layer 4: CEO (loop 2+)                                     │
│  └── Compares new vs previous → KEEP/SWAP decisions         │
│                    ↓                                         │
│  CONVERGENCE CHECK → Loop or Finish                         │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Install Dependencies

```bash
cd ai-equity-research
pip install -e .
```

### 2. Configure Environment

```bash
cp config/.env.example .env
# Edit .env and add your ANTHROPIC_API_KEY
```

### 3. Run Analysis

```bash
python scripts/run_once.py
```

## Configuration

Create a `.env` file in the project root:

```bash
# Required
ANTHROPIC_API_KEY=sk-ant-...

# Optional data sources
DATA_NEWS_API_KEY=...
DATA_ALPHA_VANTAGE_KEY=...
DATA_FRED_API_KEY=...
DATA_GITHUB_TOKEN=...

# Notifications (optional)
NOTIFY_SLACK_WEBHOOK_URL=...
NOTIFY_DISCORD_WEBHOOK_URL=...

# Scheduling
SCHEDULER_CRON_EXPRESSION=0 6 * * 1-5
```

## Agent Personalities

### Layer 1 - Primary Research Analysts
| Agent | Name | Focus |
|-------|------|-------|
| Alpha | Alex Chen | AI Hardware (GPUs, chips, foundries) |
| Beta | Sarah Rodriguez | AI Software/Cloud (hyperscalers, MLOps) |
| Gamma | Michael Park | AI Applications (healthcare, robotics) |

### Layer 2 - Secondary Analysts
| Agent | Name | Focus |
|-------|------|-------|
| Delta | Dr. James Liu | Fundamental Analysis |
| Epsilon | Maya Thompson | Technical/Momentum Analysis |
| Zeta | David Okonkwo | Risk/Contrarian Analysis |

### Layer 3 & 4
| Agent | Name | Role |
|-------|------|------|
| Fund Manager | Victoria Chen | Synthesizes into final Top 3 |
| CEO | Robert Hayes | KEEP/SWAP decisions for stability |

## Convergence Criteria

The loop stops when ANY of these conditions are met:
1. **Perfect Match**: Same 3 tickers in same order for 2 consecutive loops
2. **Set Stability**: Same 3 tickers (any order) for 3 consecutive loops
3. **Score Convergence**: All conviction scores change <5% between loops
4. **Max Loops**: Safety limit of 5 iterations reached

## Hierarchical Agent Flow

The system also supports a Cursor-style hierarchical worker pattern for parallel research:

```
Main Planner → Sub-Planners → Workers (parallel) → Judge
```

This allows for scaling up to many concurrent worker agents for intensive research tasks.

## Data Sources

| Source | Data Type | API Key Required |
|--------|-----------|------------------|
| SEC EDGAR | 10-K, 10-Q, 8-K filings | No |
| Yahoo Finance | Prices, financials | No |
| Alpha Vantage | Fundamentals, technicals | Yes (free tier) |
| NewsAPI | Recent news | Yes (free tier) |
| Web Search | Analysis, reports | No |

## Scheduling

### macOS (launchd)

```bash
python scripts/install_service.py install
```

### Docker

```bash
cd deploy/docker
docker-compose up -d
```

### Manual cron

```bash
0 6 * * 1-5 cd /path/to/ai-equity-research && python scripts/run_once.py
```

## Output

- **Reports**: Generated in `data/reports/` as Markdown
- **Database**: SQLite at `data/research_history.db`
- **Notifications**: Email, Slack, or Discord (if configured)

## Daily Landscape + Theme Memos

Generate the AI landscape brief and theme memos using the ontology mappings:

```bash
python scripts/run_hub_daily.py
```

Outputs:
- `data/reports/landscape_YYYY-MM-DD.md`
- `data/reports/memos/<theme_id>_YYYY-MM-DD.md`

## Project Structure

```
ai-equity-research/
├── config/
│   ├── settings.py          # Pydantic Settings
│   ├── agent_prompts.yaml   # Agent personalities
│   └── .env.example
├── src/
│   ├── agents/              # 8 research agents
│   ├── data_sources/        # Data source plugins
│   ├── orchestration/       # Loop controller
│   ├── storage/             # Database & state
│   ├── reports/             # Report generation
│   ├── notifications/       # Email, Slack, Discord
│   └── llm/                 # Claude API client
├── scheduler/               # APScheduler setup
├── scripts/                 # CLI scripts
├── deploy/                  # Docker & launchd
└── data/                    # Output directory
```

## Estimated Costs

Per full run (3-5 loops):
- ~110,000-185,000 tokens
- ~$0.50-$1.00 (Claude Sonnet pricing)

## License

MIT
