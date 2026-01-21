"""Layer executor for parallel agent execution."""

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from src.agents.base import AgentOutput, Layer1Agent, Layer2Agent, StockPick
from src.agents.layer3.fund_manager import FundManagerAgentImpl
from src.agents.layer4.ceo import CEOAgentImpl
from src.data_sources.aggregator import AggregatedCompanyData, DataAggregator
from src.llm.client import AgentLLMClient

logger = logging.getLogger(__name__)


class LayerExecutor:
    """Executes agent layers with parallel processing."""

    def __init__(
        self,
        llm_client: AgentLLMClient,
        data_aggregator: DataAggregator,
    ):
        """Initialize the layer executor.

        Args:
            llm_client: LLM client for agent calls
            data_aggregator: Data aggregator for market data
        """
        self.llm_client = llm_client
        self.data_aggregator = data_aggregator

    async def execute_layer1(
        self,
        agents: list[Layer1Agent],
        context: Optional[Dict[str, Any]] = None,
    ) -> list[AgentOutput]:
        """Execute Layer 1 agents in parallel.

        Args:
            agents: List of Layer 1 agents
            context: Optional context from previous loops

        Returns:
            List of agent outputs
        """
        logger.info(f"Executing Layer 1 with {len(agents)} agents")

        # Collect all tickers to fetch
        all_tickers = set()
        for agent in agents:
            all_tickers.update(agent.get_coverage_universe())

        # Fetch data for all tickers
        logger.info(f"Fetching data for {len(all_tickers)} tickers")
        company_data = await self.data_aggregator.get_batch_data(list(all_tickers))

        # Build data dict with summaries
        data = {
            "companies": {
                ticker: self.data_aggregator.get_data_summary(data)
                for ticker, data in company_data.items()
            },
            "market_context": self._get_market_context(),
        }

        # Execute agents in parallel
        tasks = []
        for agent in agents:
            agent.set_llm_client(self.llm_client)
            tasks.append(agent.analyze(data, context))

        outputs = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle exceptions
        results = []
        for i, output in enumerate(outputs):
            if isinstance(output, Exception):
                logger.error(f"Agent {agents[i].agent_id} failed: {output}")
                # Create empty output for failed agent
                results.append(
                    AgentOutput(
                        agent_id=agents[i].agent_id,
                        agent_name=agents[i].name,
                        layer=agents[i].layer,
                        picks=[],
                        reasoning=f"Error: {str(output)}",
                    )
                )
            else:
                results.append(output)

        logger.info(f"Layer 1 complete: {sum(len(o.picks) for o in results)} total picks")
        return results

    async def execute_layer2(
        self,
        agents: list[Layer2Agent],
        layer1_outputs: list[AgentOutput],
        context: Optional[Dict[str, Any]] = None,
    ) -> list[AgentOutput]:
        """Execute Layer 2 agents in parallel.

        Args:
            agents: List of Layer 2 agents
            layer1_outputs: Outputs from Layer 1
            context: Optional context

        Returns:
            List of agent outputs
        """
        logger.info(f"Executing Layer 2 with {len(agents)} agents")

        # Collect candidate pool from Layer 1
        candidate_tickers = set()
        for output in layer1_outputs:
            for pick in output.picks:
                candidate_tickers.add(pick.ticker)

        logger.info(f"Layer 2 analyzing {len(candidate_tickers)} candidates")

        # Fetch detailed data for candidates
        company_data = await self.data_aggregator.get_batch_data(list(candidate_tickers))

        # Build data dict with Layer 1 context
        data = {
            "layer1_outputs": [
                {
                    "agent_id": o.agent_id,
                    "agent_name": o.agent_name,
                    "picks": [p.model_dump() for p in o.picks],
                    "reasoning": o.reasoning,
                }
                for o in layer1_outputs
            ],
            "companies": {
                ticker: {
                    "summary": self.data_aggregator.get_data_summary(data),
                    "financial_data": data.financial_data.model_dump() if data.financial_data else {},
                    "price_data": data.price_data.model_dump() if data.price_data else {},
                }
                for ticker, data in company_data.items()
            },
        }

        # Execute agents in parallel
        tasks = []
        for agent in agents:
            agent.set_llm_client(self.llm_client)
            tasks.append(agent.analyze(data, context))

        outputs = await asyncio.gather(*tasks, return_exceptions=True)

        # Handle exceptions
        results = []
        for i, output in enumerate(outputs):
            if isinstance(output, Exception):
                logger.error(f"Agent {agents[i].agent_id} failed: {output}")
                results.append(
                    AgentOutput(
                        agent_id=agents[i].agent_id,
                        agent_name=agents[i].name,
                        layer=agents[i].layer,
                        picks=[],
                        reasoning=f"Error: {str(output)}",
                    )
                )
            else:
                results.append(output)

        logger.info(f"Layer 2 complete: {sum(len(o.picks) for o in results)} total picks")
        return results

    async def execute_layer3(
        self,
        fund_manager: FundManagerAgentImpl,
        layer2_outputs: list[AgentOutput],
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentOutput:
        """Execute Layer 3 (Fund Manager).

        Args:
            fund_manager: Fund Manager agent
            layer2_outputs: Outputs from Layer 2
            context: Optional context (portfolio constraints)

        Returns:
            Fund Manager's output with Top 3
        """
        logger.info("Executing Layer 3 (Fund Manager)")

        fund_manager.set_llm_client(self.llm_client)

        data = {
            "layer2_outputs": [
                {
                    "agent_id": o.agent_id,
                    "agent_name": o.agent_name,
                    "picks": [p.model_dump() for p in o.picks],
                    "reasoning": o.reasoning,
                }
                for o in layer2_outputs
            ],
        }

        try:
            output = await fund_manager.analyze(data, context)
            logger.info(f"Layer 3 complete: Top 3 = {[p.ticker for p in output.picks]}")
            return output
        except Exception as e:
            logger.error(f"Fund Manager failed: {e}")
            raise

    async def execute_layer4(
        self,
        ceo: CEOAgentImpl,
        previous_top3: Optional[List[StockPick]],
        proposed_top3: list[StockPick],
        loop_number: int,
    ) -> Any:
        """Execute Layer 4 (CEO).

        Args:
            ceo: CEO agent
            previous_top3: Previous loop's Top 3
            proposed_top3: Proposed Top 3 from Fund Manager
            loop_number: Current loop number

        Returns:
            CEO's output with decisions
        """
        logger.info(f"Executing Layer 4 (CEO) - Loop {loop_number}")

        ceo.set_llm_client(self.llm_client)

        try:
            output = await ceo.review(previous_top3, proposed_top3, loop_number)
            logger.info(
                f"Layer 4 complete: Stability={output.stability_score:.2f}, "
                f"Final Top 3 = {[p.ticker for p in output.final_top3]}"
            )
            return output
        except Exception as e:
            logger.error(f"CEO failed: {e}")
            raise

    def _get_market_context(self) -> str:
        """Get current market context summary.

        Returns:
            Market context string
        """
        # In production, this would fetch real market data
        return f"""
Market Context (as of {datetime.utcnow().strftime('%Y-%m-%d')}):
- Focus: AI and technology sector analysis
- Key themes: AI infrastructure, cloud computing, enterprise AI adoption
- Consider: Recent earnings, guidance, competitive positioning
"""

    async def execute_full_layer_sequence(
        self,
        layer1_agents: list[Layer1Agent],
        layer2_agents: list[Layer2Agent],
        fund_manager: FundManagerAgentImpl,
        ceo: CEOAgentImpl,
        previous_top3: Optional[List[StockPick]],
        loop_number: int,
    ) -> dict[str, Any]:
        """Execute full layer sequence for one loop iteration.

        Args:
            layer1_agents: Layer 1 agents
            layer2_agents: Layer 2 agents
            fund_manager: Fund Manager agent
            ceo: CEO agent
            previous_top3: Previous loop's Top 3
            loop_number: Current loop number

        Returns:
            Dict with all layer outputs
        """
        start_time = datetime.utcnow()

        # Layer 1
        layer1_outputs = await self.execute_layer1(layer1_agents)

        # Layer 2
        layer2_outputs = await self.execute_layer2(layer2_agents, layer1_outputs)

        # Layer 3
        layer3_output = await self.execute_layer3(fund_manager, layer2_outputs)

        # Layer 4
        layer4_output = await self.execute_layer4(
            ceo,
            previous_top3,
            layer3_output.picks,
            loop_number,
        )

        end_time = datetime.utcnow()
        duration = (end_time - start_time).total_seconds()

        return {
            "loop_number": loop_number,
            "layer1_outputs": layer1_outputs,
            "layer2_outputs": layer2_outputs,
            "layer3_output": layer3_output,
            "layer4_output": layer4_output,
            "final_top3": layer4_output.final_top3,
            "duration_seconds": duration,
            "timestamp": end_time,
        }
