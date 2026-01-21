"""Agent factory and registry."""

from pathlib import Path
from typing import Any

import yaml

from src.agents.base import (
    AgentLayer,
    BaseResearchAgent,
    CEOAgent,
    FundManagerAgent,
    HierarchicalAgent,
    JudgeAgent,
    Layer1Agent,
    Layer2Agent,
    MainPlannerAgent,
    SubPlannerAgent,
    WorkerAgent,
)


class AgentRegistry:
    """Registry and factory for research agents."""

    def __init__(self, prompts_path: Path):
        """Initialize the registry.

        Args:
            prompts_path: Path to agent_prompts.yaml
        """
        self.prompts_path = prompts_path
        self._prompts: dict[str, Any] = {}
        self._agents: dict[str, BaseResearchAgent] = {}
        self._hierarchical_agents: dict[str, HierarchicalAgent] = {}
        self._load_prompts()

    def _load_prompts(self) -> None:
        """Load agent prompts from YAML."""
        with open(self.prompts_path) as f:
            self._prompts = yaml.safe_load(f)

    def reload_prompts(self) -> None:
        """Reload prompts from file."""
        self._load_prompts()
        self._agents.clear()
        self._hierarchical_agents.clear()

    def get_layer1_agents(self) -> list[Layer1Agent]:
        """Get all Layer 1 agents."""
        from src.agents.layer1.alpha import AlphaAgent
        from src.agents.layer1.beta import BetaAgent
        from src.agents.layer1.gamma import GammaAgent

        agents = []
        layer1_prompts = self._prompts.get("layer1", {})

        if "alpha" in layer1_prompts:
            config = layer1_prompts["alpha"]
            agents.append(
                AlphaAgent(
                    name=config["name"],
                    system_prompt=config["system_prompt"],
                    sectors=config.get("sectors", []),
                )
            )

        if "beta" in layer1_prompts:
            config = layer1_prompts["beta"]
            agents.append(
                BetaAgent(
                    name=config["name"],
                    system_prompt=config["system_prompt"],
                    sectors=config.get("sectors", []),
                )
            )

        if "gamma" in layer1_prompts:
            config = layer1_prompts["gamma"]
            agents.append(
                GammaAgent(
                    name=config["name"],
                    system_prompt=config["system_prompt"],
                    sectors=config.get("sectors", []),
                )
            )

        return agents

    def get_layer2_agents(self) -> list[Layer2Agent]:
        """Get all Layer 2 agents."""
        from src.agents.layer2.delta import DeltaAgent
        from src.agents.layer2.epsilon import EpsilonAgent
        from src.agents.layer2.zeta import ZetaAgent

        agents = []
        layer2_prompts = self._prompts.get("layer2", {})

        if "delta" in layer2_prompts:
            config = layer2_prompts["delta"]
            agents.append(
                DeltaAgent(
                    name=config["name"],
                    system_prompt=config["system_prompt"],
                    specialties=config.get("specialties", []),
                )
            )

        if "epsilon" in layer2_prompts:
            config = layer2_prompts["epsilon"]
            agents.append(
                EpsilonAgent(
                    name=config["name"],
                    system_prompt=config["system_prompt"],
                    specialties=config.get("specialties", []),
                )
            )

        if "zeta" in layer2_prompts:
            config = layer2_prompts["zeta"]
            agents.append(
                ZetaAgent(
                    name=config["name"],
                    system_prompt=config["system_prompt"],
                    specialties=config.get("specialties", []),
                )
            )

        return agents

    def get_fund_manager(self) -> FundManagerAgent:
        """Get the Fund Manager agent."""
        from src.agents.layer3.fund_manager import FundManagerAgentImpl

        config = self._prompts.get("layer3", {}).get("fund_manager", {})
        return FundManagerAgentImpl(system_prompt=config.get("system_prompt", ""))

    def get_ceo(self) -> CEOAgent:
        """Get the CEO agent."""
        from src.agents.layer4.ceo import CEOAgentImpl

        config = self._prompts.get("layer4", {}).get("ceo", {})
        return CEOAgentImpl(system_prompt=config.get("system_prompt", ""))

    def get_main_planner(self) -> MainPlannerAgent:
        """Get the Main Planner for hierarchical flow."""
        from src.agents.layer1.hierarchical import MainPlannerAgentImpl

        config = self._prompts.get("hierarchical", {}).get("main_planner", {})
        return MainPlannerAgentImpl(
            agent_id="main_planner",
            name=config.get("name", "Strategic Planner"),
            system_prompt=config.get("system_prompt", ""),
        )

    def get_sub_planner(self, component: str) -> SubPlannerAgent:
        """Get a Sub-Planner for a specific component."""
        from src.agents.layer1.hierarchical import SubPlannerAgentImpl

        config = self._prompts.get("hierarchical", {}).get("sub_planner", {})
        return SubPlannerAgentImpl(
            agent_id=f"sub_planner_{component}",
            name=config.get("name", "Component Planner"),
            system_prompt=config.get("system_prompt", ""),
            component=component,
        )

    def get_worker(self, worker_id: str) -> WorkerAgent:
        """Get a Worker agent."""
        from src.agents.layer1.hierarchical import WorkerAgentImpl

        config = self._prompts.get("hierarchical", {}).get("worker", {})
        return WorkerAgentImpl(
            agent_id=worker_id,
            name=config.get("name", "Research Worker"),
            system_prompt=config.get("system_prompt", ""),
        )

    def get_judge(self) -> JudgeAgent:
        """Get the Judge agent."""
        from src.agents.layer1.hierarchical import JudgeAgentImpl

        config = self._prompts.get("hierarchical", {}).get("judge", {})
        return JudgeAgentImpl(
            agent_id="judge",
            name=config.get("name", "Quality Judge"),
            system_prompt=config.get("system_prompt", ""),
            quality_criteria=config.get("quality_criteria", {}),
        )

    def get_all_agents_by_layer(self) -> dict[AgentLayer, list[BaseResearchAgent]]:
        """Get all agents organized by layer."""
        return {
            AgentLayer.LAYER1_PRIMARY: self.get_layer1_agents(),
            AgentLayer.LAYER2_SECONDARY: self.get_layer2_agents(),
            AgentLayer.LAYER3_FUND_MANAGER: [self.get_fund_manager()],
            AgentLayer.LAYER4_CEO: [self.get_ceo()],
        }
