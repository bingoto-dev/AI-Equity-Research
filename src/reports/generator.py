"""Report generation for research results."""

from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from jinja2 import Environment, FileSystemLoader

from src.orchestration.loop_controller import ResearchRun


class ReportGenerator:
    """Generates reports from research run results."""

    def __init__(self, templates_dir: Path, output_dir: Path):
        """Initialize the report generator.

        Args:
            templates_dir: Directory containing Jinja2 templates
            output_dir: Directory for generated reports
        """
        self.templates_dir = templates_dir
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self._env = Environment(
            loader=FileSystemLoader(str(templates_dir)),
            autoescape=False,
        )

    def generate_report(
        self,
        run: ResearchRun,
        template_name: str = "research_report.md.j2",
    ) -> str:
        """Generate a report from a research run.

        Args:
            run: Completed research run
            template_name: Template file name

        Returns:
            Path to generated report
        """
        template = self._env.get_template(template_name)

        # Prepare context
        context = self._build_context(run)

        # Render report
        report_content = template.render(**context)

        # Save report
        report_filename = f"report_{run.run_id}.md"
        report_path = self.output_dir / report_filename

        with open(report_path, "w") as f:
            f.write(report_content)

        return str(report_path)

    def _build_context(self, run: ResearchRun) -> dict[str, Any]:
        """Build template context from research run.

        Args:
            run: Research run

        Returns:
            Template context dict
        """
        context = {
            "run_id": run.run_id,
            "report_date": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            "status": run.status,
            "total_loops": len(run.iterations),
            "total_tokens": run.total_tokens,
            "duration_seconds": run.total_duration_seconds,
            "estimated_cost": self._estimate_cost(run.total_tokens),
        }

        # Final picks
        context["final_picks"] = run.final_picks

        # Convergence info
        if run.convergence_result:
            context["convergence_reason"] = run.convergence_result.get("reason", "Unknown")
            context["convergence_loop"] = run.convergence_result.get("loop_number", 0)
        else:
            context["convergence_reason"] = "Not converged"
            context["convergence_loop"] = 0

        # Iterations summary
        iterations = []
        for iteration in run.iterations:
            iter_data = {
                "loop_number": iteration.loop_number,
                "proposed_tickers": [p.get("ticker", "") for p in iteration.proposed_top3],
                "final_tickers": [p.get("ticker", "") for p in iteration.final_top3],
                "stability_score": iteration.stability_score,
            }
            iterations.append(iter_data)
        context["iterations"] = iterations

        # Layer summaries from last iteration
        if run.iterations:
            last_iter = run.iterations[-1]

            # Layer 1 summary
            layer1_summary = {}
            for agent_id, picks in last_iter.layer1_picks.items():
                layer1_summary[agent_id] = [p.get("ticker", "") for p in picks]
            context["layer1_summary"] = layer1_summary

            # Layer 2 summary
            layer2_summary = {}
            for agent_id, picks in last_iter.layer2_picks.items():
                layer2_summary[agent_id] = [p.get("ticker", "") for p in picks]
            context["layer2_summary"] = layer2_summary

        return context

    def _estimate_cost(self, tokens: int) -> float:
        """Estimate API cost based on token usage.

        Args:
            tokens: Total tokens used

        Returns:
            Estimated cost in USD
        """
        # Claude Sonnet pricing (approximate)
        # Input: $3/1M tokens, Output: $15/1M tokens
        # Assume 60% input, 40% output
        input_tokens = tokens * 0.6
        output_tokens = tokens * 0.4

        input_cost = (input_tokens / 1_000_000) * 3
        output_cost = (output_tokens / 1_000_000) * 15

        return input_cost + output_cost

    def generate_summary(self, run: ResearchRun) -> str:
        """Generate a short summary for notifications.

        Args:
            run: Research run

        Returns:
            Summary text
        """
        if not run.final_picks:
            return f"Research run {run.run_id} completed with no picks."

        picks_text = ", ".join(
            f"{p.get('ticker', 'N/A')} ({p.get('conviction_score', 0):.0f}%)"
            for p in run.final_picks[:3]
        )

        return (
            f"🎯 AI Research Complete\n"
            f"Top 3: {picks_text}\n"
            f"Loops: {len(run.iterations)} | "
            f"Convergence: {run.convergence_result.get('reason', 'N/A')}"
        )

    def generate_html_report(
        self,
        run: ResearchRun,
        template_name: str = "research_report.html.j2",
    ) -> Optional[str]:
        """Generate an HTML report if template exists.

        Args:
            run: Research run
            template_name: HTML template name

        Returns:
            Path to HTML report or None if template doesn't exist
        """
        try:
            template = self._env.get_template(template_name)
        except Exception:
            return None

        context = self._build_context(run)
        report_content = template.render(**context)

        report_filename = f"report_{run.run_id}.html"
        report_path = self.output_dir / report_filename

        with open(report_path, "w") as f:
            f.write(report_content)

        return str(report_path)

    def get_recent_reports(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get list of recent reports.

        Args:
            limit: Maximum number of reports

        Returns:
            List of report info dicts
        """
        reports = []
        for report_file in sorted(
            self.output_dir.glob("report_*.md"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[:limit]:
            reports.append({
                "filename": report_file.name,
                "path": str(report_file),
                "created": datetime.fromtimestamp(report_file.stat().st_mtime),
                "size": report_file.stat().st_size,
            })
        return reports
