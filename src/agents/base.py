"""Base class for all research agents."""

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AgentLayer(Enum):
    """Agent layer classification."""

    LAYER1_PRIMARY = 1
    LAYER2_SECONDARY = 2
    LAYER3_FUND_MANAGER = 3
    LAYER4_CEO = 4
    HIERARCHICAL_PLANNER = 10
    HIERARCHICAL_WORKER = 11
    HIERARCHICAL_JUDGE = 12


class StockPick(BaseModel):
    """A single stock pick with analysis."""

    ticker: str = Field(..., description="Stock ticker symbol")
    company_name: str = Field(..., description="Company name")
    conviction_score: float = Field(..., ge=0, le=100, description="Conviction score 0-100")
    thesis: str = Field(..., description="Investment thesis")
    key_risks: list[str] = Field(default_factory=list, description="Key risks")
    catalysts: list[str] = Field(default_factory=list, description="Upcoming catalysts")
    target_price_rationale: Optional[str] = Field(None, description="Target price rationale")

    # Layer 2 specific fields
    fundamental_score: Optional[float] = Field(None, description="Fundamental quality score")
    technical_score: Optional[float] = Field(None, description="Technical/momentum score")
    risk_score: Optional[float] = Field(None, description="Risk assessment score")
    valuation_summary: Optional[str] = Field(None, description="Valuation analysis")
    position_size_recommendation: Optional[float] = Field(None, description="Position size 1-5%")
    bear_case: Optional[str] = Field(None, description="Bear case scenario")


class AgentOutput(BaseModel):
    """Output from an agent's analysis."""

    agent_id: str = Field(..., description="Agent identifier")
    agent_name: str = Field(..., description="Agent display name")
    layer: AgentLayer = Field(..., description="Agent layer")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    picks: list[StockPick] = Field(default_factory=list, description="Stock picks")
    reasoning: str = Field("", description="Overall reasoning")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class CEODecision(BaseModel):
    """CEO's KEEP/SWAP decision for a position."""

    position: int = Field(..., description="Position number (1-3)")
    previous_pick: Optional[StockPick] = Field(None, description="Previous loop's pick")
    proposed_pick: StockPick = Field(..., description="New proposed pick")
    decision: str = Field(..., pattern="^(KEEP|SWAP)$", description="KEEP or SWAP")
    rationale: str = Field(..., description="Rationale for decision")
    final_pick: StockPick = Field(..., description="Final confirmed pick")


class CEOOutput(BaseModel):
    """Output from CEO's review."""

    agent_id: str = "ceo"
    agent_name: str = "Robert Hayes"
    layer: AgentLayer = AgentLayer.LAYER4_CEO
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    decisions: list[CEODecision] = Field(default_factory=list)
    final_top3: list[StockPick] = Field(default_factory=list)
    stability_score: float = Field(..., description="0-1 score of how stable picks are")
    loop_number: int = Field(..., description="Current loop number")


class HierarchicalTask(BaseModel):
    """A task in the hierarchical agent flow."""

    task_id: str = Field(..., description="Unique task identifier")
    component: str = Field(..., description="Parent component")
    description: str = Field(..., description="Task description")
    inputs: dict[str, Any] = Field(default_factory=dict, description="Task inputs")
    expected_output: str = Field(..., description="Expected output description")
    dependencies: list[str] = Field(default_factory=list, description="Task IDs this depends on")


class HierarchicalArtifact(BaseModel):
    """Output artifact from a hierarchical worker."""

    task_id: str = Field(..., description="Task this artifact is for")
    worker_id: str = Field(..., description="Worker that produced this")
    content: dict[str, Any] = Field(..., description="Artifact content")
    status: str = Field(..., description="success or failed")
    error: Optional[str] = Field(None, description="Error message if failed")


class JudgeEvaluation(BaseModel):
    """Evaluation from the hierarchical judge."""

    complete: bool = Field(..., description="Whether project is complete")
    quality_score: float = Field(..., ge=0, le=1, description="Quality score 0-1")
    gaps: list[str] = Field(default_factory=list, description="Identified gaps")
    recommendations: list[str] = Field(default_factory=list, description="Recommendations")


class BaseResearchAgent(ABC):
    """Abstract base class for all research agents."""

    def __init__(
        self,
        agent_id: str,
        name: str,
        layer: AgentLayer,
        system_prompt: str,
    ):
        """Initialize the agent.

        Args:
            agent_id: Unique identifier for the agent
            name: Display name of the agent
            layer: Which layer this agent belongs to
            system_prompt: System prompt for the LLM
        """
        self.agent_id = agent_id
        self.name = name
        self.layer = layer
        self.system_prompt = system_prompt

    @abstractmethod
    async def analyze(
        self,
        data: dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentOutput:
        """Perform analysis and return picks.

        Args:
            data: Market data and information for analysis
            context: Optional context from previous analyses

        Returns:
            AgentOutput containing picks and reasoning
        """
        pass

    def get_output_schema(self) -> dict[str, Any]:
        """Get the JSON schema for this agent's output."""
        return AgentOutput.model_json_schema()


class Layer1Agent(BaseResearchAgent):
    """Base class for Layer 1 primary research analysts."""

    def __init__(
        self,
        agent_id: str,
        name: str,
        system_prompt: str,
        sectors: list[str],
    ):
        super().__init__(
            agent_id=agent_id,
            name=name,
            layer=AgentLayer.LAYER1_PRIMARY,
            system_prompt=system_prompt,
        )
        self.sectors = sectors


class Layer2Agent(BaseResearchAgent):
    """Base class for Layer 2 secondary analysts."""

    def __init__(
        self,
        agent_id: str,
        name: str,
        system_prompt: str,
        specialties: list[str],
    ):
        super().__init__(
            agent_id=agent_id,
            name=name,
            layer=AgentLayer.LAYER2_SECONDARY,
            system_prompt=system_prompt,
        )
        self.specialties = specialties


class FundManagerAgent(BaseResearchAgent):
    """Fund Manager agent (Layer 3)."""

    def __init__(self, system_prompt: str):
        super().__init__(
            agent_id="fund_manager",
            name="Victoria Chen",
            layer=AgentLayer.LAYER3_FUND_MANAGER,
            system_prompt=system_prompt,
        )


class CEOAgent(BaseResearchAgent):
    """CEO agent (Layer 4)."""

    def __init__(self, system_prompt: str):
        super().__init__(
            agent_id="ceo",
            name="Robert Hayes",
            layer=AgentLayer.LAYER4_CEO,
            system_prompt=system_prompt,
        )

    @abstractmethod
    async def review(
        self,
        previous_top3: Optional[List[StockPick]],
        proposed_top3: list[StockPick],
        loop_number: int,
    ) -> CEOOutput:
        """Review and make KEEP/SWAP decisions.

        Args:
            previous_top3: Previous loop's Top 3 (None for loop 1)
            proposed_top3: New proposed Top 3 from Fund Manager
            loop_number: Current loop iteration number

        Returns:
            CEOOutput with decisions and final Top 3
        """
        pass


class HierarchicalAgent(ABC):
    """Base class for hierarchical flow agents."""

    def __init__(self, agent_id: str, name: str, system_prompt: str):
        self.agent_id = agent_id
        self.name = name
        self.system_prompt = system_prompt


class MainPlannerAgent(HierarchicalAgent):
    """Main Planner in hierarchical flow."""

    @abstractmethod
    async def plan(
        self,
        project_description: str,
        context_docs: dict[str, Any],
        previous_gaps: Optional[List[str]] = None,
    ) -> list[str]:
        """Create high-level component breakdown.

        Args:
            project_description: Description of research project
            context_docs: Reference documentation
            previous_gaps: Gaps from previous cycle

        Returns:
            List of components to research
        """
        pass


class SubPlannerAgent(HierarchicalAgent):
    """Sub-Planner in hierarchical flow."""

    @abstractmethod
    async def decompose(
        self,
        component: str,
        relevant_docs: dict[str, Any],
    ) -> list[HierarchicalTask]:
        """Break component into atomic tasks.

        Args:
            component: Component to break down
            relevant_docs: Relevant documentation

        Returns:
            List of tasks for workers
        """
        pass


class WorkerAgent(HierarchicalAgent):
    """Worker in hierarchical flow."""

    @abstractmethod
    async def execute(
        self,
        task: HierarchicalTask,
        relevant_docs: dict[str, Any],
    ) -> HierarchicalArtifact:
        """Execute a single task.

        Args:
            task: Task to execute
            relevant_docs: Relevant documentation

        Returns:
            Artifact produced by task
        """
        pass


class JudgeAgent(HierarchicalAgent):
    """Judge in hierarchical flow."""

    @abstractmethod
    async def evaluate(
        self,
        artifacts: list[HierarchicalArtifact],
        requirements: dict[str, Any],
    ) -> JudgeEvaluation:
        """Evaluate all output.

        Args:
            artifacts: All artifacts from workers
            requirements: Project requirements

        Returns:
            Evaluation with completion status and gaps
        """
        pass
