#!/usr/bin/env python3
"""Agent brainstorm session to identify optimal data sources."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import anthropic


AGENTS = {
    "alpha": {
        "name": "Alex Chen",
        "focus": "AI Hardware & Semiconductors",
        "covers": "GPUs, chips, foundries, memory, networking infrastructure"
    },
    "beta": {
        "name": "Sarah Rodriguez",
        "focus": "AI Software & Cloud",
        "covers": "Hyperscalers, MLOps, SaaS platforms, cloud infrastructure"
    },
    "gamma": {
        "name": "Michael Park",
        "focus": "AI Applications",
        "covers": "Enterprise AI, healthcare AI, robotics, autonomous systems"
    },
    "delta": {
        "name": "Dr. James Liu",
        "focus": "Fundamental Analysis",
        "covers": "Financial statements, valuation, earnings quality, balance sheets"
    },
    "epsilon": {
        "name": "Maya Thompson",
        "focus": "Technical & Momentum",
        "covers": "Price action, institutional flows, options activity, short interest"
    },
    "zeta": {
        "name": "David Okonkwo",
        "focus": "Risk & Contrarian",
        "covers": "Bear cases, stress tests, sentiment extremes, positioning"
    },
}

BRAINSTORM_PROMPT = """You are {name}, a senior equity research analyst specializing in {focus}.
Your coverage universe includes: {covers}

We're improving our research data infrastructure. Think creatively about what data sources would make you SIGNIFICANTLY more effective at identifying alpha.

For each data source you recommend, provide:
1. **Source Name**: What is it?
2. **Data Type**: What specific data does it provide?
3. **Why Critical**: Why is this essential for YOUR specific focus area?
4. **Signal Value**: What actionable signals can you extract?
5. **Freshness Need**: Real-time, daily, weekly?
6. **Free/Paid**: Is there a free tier or API?

Think beyond traditional sources. Consider:
- Industry-specific data (e.g., semiconductor shipment data, cloud spending surveys)
- Alternative data (satellite imagery, job postings, web traffic)
- Social signals (FinTwit, Reddit, Discord servers)
- Insider signals (Form 4 filings, executive interviews)
- Supply chain signals (supplier announcements, inventory data)
- Conference calls, investor days, analyst day transcripts
- Patent filings, research papers
- Regulatory filings beyond 10-K/10-Q

List your TOP 5 most impactful data sources, ranked by alpha potential."""


async def brainstorm_agent(client: anthropic.Anthropic, agent_id: str, agent_info: dict) -> str:
    """Get data source recommendations from one agent."""
    prompt = BRAINSTORM_PROMPT.format(**agent_info)

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        temperature=0.8,  # Higher creativity
        messages=[{"role": "user", "content": prompt}]
    )

    return response.content[0].text


async def run_brainstorm(api_key: str):
    """Run brainstorm session with all agents."""
    client = anthropic.Anthropic(api_key=api_key)

    print("=" * 70)
    print("AGENT DATA SOURCE BRAINSTORM SESSION")
    print("=" * 70)
    print()

    all_recommendations = {}

    for agent_id, agent_info in AGENTS.items():
        print(f"\n{'='*70}")
        print(f"Agent: {agent_info['name']} ({agent_info['focus']})")
        print("=" * 70)

        response = await brainstorm_agent(client, agent_id, agent_info)
        all_recommendations[agent_id] = response
        print(response)
        print()

    # Now synthesize common themes
    print("\n" + "=" * 70)
    print("SYNTHESIZING COMMON THEMES & PRIORITIES")
    print("=" * 70)

    synthesis_prompt = f"""You are the Chief Data Officer reviewing data source recommendations from 6 research analysts.

Here are their recommendations:

{chr(10).join(f"### {AGENTS[aid]['name']} ({AGENTS[aid]['focus']}):{chr(10)}{rec}" for aid, rec in all_recommendations.items())}

---

Synthesize these into:

1. **TOP 10 DATA SOURCES TO IMPLEMENT** (ranked by impact across all analysts)
   - For each: Name, what it provides, which agents benefit, implementation difficulty (Easy/Medium/Hard), free tier available?

2. **QUICK WINS** (can implement in <1 day with free APIs)

3. **HIGH-VALUE INVESTMENTS** (worth paying for or building scrapers)

4. **INNOVATIVE IDEAS** (creative/unconventional sources mentioned)

5. **IMPLEMENTATION ROADMAP** (suggested order of implementation)

Be specific and actionable."""

    synthesis = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=3000,
        messages=[{"role": "user", "content": synthesis_prompt}]
    )

    print(synthesis.content[0].text)

    # Save results
    output_path = Path("data/brainstorm_results.md")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        f.write("# Agent Data Source Brainstorm Results\n\n")
        for agent_id, rec in all_recommendations.items():
            f.write(f"## {AGENTS[agent_id]['name']} ({AGENTS[agent_id]['focus']})\n\n")
            f.write(rec)
            f.write("\n\n---\n\n")
        f.write("## Synthesis\n\n")
        f.write(synthesis.content[0].text)

    print(f"\n\nResults saved to: {output_path}")


def main():
    import os
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Set ANTHROPIC_API_KEY environment variable")
        sys.exit(1)

    asyncio.run(run_brainstorm(api_key))


if __name__ == "__main__":
    main()
