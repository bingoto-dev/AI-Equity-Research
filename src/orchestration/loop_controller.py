"""Main loop controller for the research system."""

import logging
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field

from config.settings import Settings
from src.agents.base import StockPick
from src.agents.registry import AgentRegistry
from src.data_sources.aggregator import DataAggregator
from src.data_sources.registry import DataSourceRegistry
from src.llm.client import AgentLLMClient
from src.orchestration.convergence_detector import ConvergenceDetector, ConvergenceResult
from src.orchestration.layer_executor import LayerExecutor

logger = logging.getLogger(__name__)


class LoopIteration(BaseModel):
    """Record of a single loop iteration."""

    loop_number: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    layer1_picks: dict[str, list[dict]] = Field(default_factory=dict)
    layer2_picks: dict[str, list[dict]] = Field(default_factory=dict)
    proposed_top3: list[dict] = Field(default_factory=list)
    final_top3: list[dict] = Field(default_factory=list)
    ceo_decisions: list[dict] = Field(default_factory=list)
    stability_score: float = 0.0
    duration_seconds: float = 0.0
    token_usage: dict[str, int] = Field(default_factory=dict)


class ResearchRun(BaseModel):
    """Complete research run record."""

    run_id: str
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    iterations: list[LoopIteration] = Field(default_factory=list)
    convergence_result: dict[str, Any] = Field(default_factory=dict)
    final_picks: list[dict] = Field(default_factory=list)
    total_duration_seconds: float = 0.0
    total_tokens: int = 0
    status: str = "running"


class LoopController:
    """Controls the main research convergence loop."""

    def __init__(
        self,
        settings: Settings,
        agent_registry: AgentRegistry,
        data_registry: DataSourceRegistry,
    ):
        """Initialize the loop controller.

        Args:
            settings: Application settings
            agent_registry: Registry of research agents
            data_registry: Registry of data sources
        """
        self.settings = settings
        self.agent_registry = agent_registry
        self.data_registry = data_registry

        # Initialize components
        self.llm_client = AgentLLMClient(settings.anthropic)
        self.data_aggregator = DataAggregator(data_registry)
        self.layer_executor = LayerExecutor(self.llm_client, self.data_aggregator)
        self.convergence_detector = ConvergenceDetector(
            perfect_match_loops=settings.loop.perfect_match_loops,
            set_stability_loops=settings.loop.set_stability_loops,
            score_threshold=settings.loop.convergence_threshold,
            max_loops=settings.loop.max_iterations,
        )

        self._current_run: Optional[ResearchRun] = None

    async def run(self) -> ResearchRun:
        """Execute the full research loop until convergence.

        Returns:
            ResearchRun with all results
        """
        import uuid
        run_id = f"run_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

        logger.info(f"Starting research run: {run_id}")

        self._current_run = ResearchRun(run_id=run_id)
        self.convergence_detector.reset()

        # Get agents
        layer1_agents = self.agent_registry.get_layer1_agents()
        layer2_agents = self.agent_registry.get_layer2_agents()
        fund_manager = self.agent_registry.get_fund_manager()
        ceo = self.agent_registry.get_ceo()
        ceo.reset()

        # Initialize data sources
        await self.data_registry.initialize_all()

        previous_top3: Optional[list[StockPick]] = None
        loop_number = 0
        total_tokens = 0

        try:
            while True:
                loop_number += 1
                logger.info(f"=== Starting Loop {loop_number} ===")

                # Execute full layer sequence
                result = await self.layer_executor.execute_full_layer_sequence(
                    layer1_agents=layer1_agents,
                    layer2_agents=layer2_agents,
                    fund_manager=fund_manager,
                    ceo=ceo,
                    previous_top3=previous_top3,
                    loop_number=loop_number,
                )

                # Record iteration
                iteration = self._record_iteration(result, loop_number)
                self._current_run.iterations.append(iteration)

                # Update token count
                for output in result["layer1_outputs"]:
                    total_tokens += output.metadata.get("input_tokens", 0)
                    total_tokens += output.metadata.get("output_tokens", 0)
                for output in result["layer2_outputs"]:
                    total_tokens += output.metadata.get("input_tokens", 0)
                    total_tokens += output.metadata.get("output_tokens", 0)
                total_tokens += result["layer3_output"].metadata.get("input_tokens", 0)
                total_tokens += result["layer3_output"].metadata.get("output_tokens", 0)

                # Add to convergence detector
                self.convergence_detector.add_result(result["final_top3"])

                # Check convergence
                convergence = self.convergence_detector.check()
                logger.info(
                    f"Convergence check: {convergence.reason.value} "
                    f"(converged={convergence.converged})"
                )

                if convergence.converged:
                    self._current_run.convergence_result = {
                        "converged": True,
                        "reason": convergence.reason.value,
                        "details": convergence.details,
                        "loop_number": convergence.loop_number,
                    }
                    self._current_run.final_picks = [
                        p.model_dump() for p in result["final_top3"]
                    ]
                    break

                # Update previous top 3 for next iteration
                previous_top3 = result["final_top3"]

            # Finalize run
            self._current_run.completed_at = datetime.utcnow()
            self._current_run.total_duration_seconds = (
                self._current_run.completed_at - self._current_run.started_at
            ).total_seconds()
            self._current_run.total_tokens = total_tokens
            self._current_run.status = "completed"

            logger.info(
                f"Research run complete: {loop_number} loops, "
                f"{total_tokens} tokens, "
                f"{self._current_run.total_duration_seconds:.1f}s"
            )

            return self._current_run

        except Exception as e:
            logger.error(f"Research run failed: {e}")
            if self._current_run:
                self._current_run.status = "failed"
                self._current_run.completed_at = datetime.utcnow()
            raise

        finally:
            await self.data_registry.close_all()

    def _record_iteration(
        self,
        result: dict[str, Any],
        loop_number: int,
    ) -> LoopIteration:
        """Record a loop iteration.

        Args:
            result: Layer execution result
            loop_number: Current loop number

        Returns:
            LoopIteration record
        """
        layer1_picks = {
            output.agent_id: [p.model_dump() for p in output.picks]
            for output in result["layer1_outputs"]
        }

        layer2_picks = {
            output.agent_id: [p.model_dump() for p in output.picks]
            for output in result["layer2_outputs"]
        }

        proposed = [p.model_dump() for p in result["layer3_output"].picks]
        final = [p.model_dump() for p in result["final_top3"]]

        ceo_output = result["layer4_output"]
        decisions = [d.model_dump() for d in ceo_output.decisions]

        # Calculate token usage
        tokens = {"input": 0, "output": 0}
        for output in result["layer1_outputs"]:
            tokens["input"] += output.metadata.get("input_tokens", 0)
            tokens["output"] += output.metadata.get("output_tokens", 0)
        for output in result["layer2_outputs"]:
            tokens["input"] += output.metadata.get("input_tokens", 0)
            tokens["output"] += output.metadata.get("output_tokens", 0)
        tokens["input"] += result["layer3_output"].metadata.get("input_tokens", 0)
        tokens["output"] += result["layer3_output"].metadata.get("output_tokens", 0)

        return LoopIteration(
            loop_number=loop_number,
            layer1_picks=layer1_picks,
            layer2_picks=layer2_picks,
            proposed_top3=proposed,
            final_top3=final,
            ceo_decisions=decisions,
            stability_score=ceo_output.stability_score,
            duration_seconds=result["duration_seconds"],
            token_usage=tokens,
        )

    def get_current_run(self) -> Optional[ResearchRun]:
        """Get the current run if in progress.

        Returns:
            Current ResearchRun or None
        """
        return self._current_run

    def get_convergence_progress(self) -> dict[str, Any]:
        """Get current convergence progress.

        Returns:
            Progress dict from convergence detector
        """
        result = self.convergence_detector.check()
        return {
            "converged": result.converged,
            "reason": result.reason.value,
            "details": result.details,
            "loop_number": result.loop_number,
            "history": [
                [p.ticker for p in picks]
                for picks in self.convergence_detector.get_history()
            ],
            "ticker_frequency": self.convergence_detector.get_ticker_frequency(),
        }
