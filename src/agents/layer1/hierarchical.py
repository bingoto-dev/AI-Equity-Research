"""Hierarchical agents for Cursor-style parallel worker pattern."""

from typing import Any, List, Optional
import asyncio
import uuid

from src.agents.base import (
    HierarchicalArtifact,
    HierarchicalTask,
    JudgeAgent,
    JudgeEvaluation,
    MainPlannerAgent,
    SubPlannerAgent,
    WorkerAgent,
)
from src.llm.client import LLMClient


class MainPlannerAgentImpl(MainPlannerAgent):
    """Main Planner implementation for hierarchical research flow."""

    def __init__(
        self,
        agent_id: str,
        name: str,
        system_prompt: str,
        llm_client: Optional[LLMClient] = None,
    ):
        super().__init__(agent_id, name, system_prompt)
        self.llm_client = llm_client

    def set_llm_client(self, client: LLMClient) -> None:
        """Set the LLM client."""
        self.llm_client = client

    async def plan(
        self,
        project_description: str,
        context_docs: dict[str, Any],
        previous_gaps: Optional[list[str]] = None,
    ) -> list[str]:
        """Create high-level component breakdown.

        Args:
            project_description: Description of research project
            context_docs: Reference documentation
            previous_gaps: Gaps from previous cycle

        Returns:
            List of components to research
        """
        if not self.llm_client:
            raise RuntimeError("LLM client not set")

        gap_context = ""
        if previous_gaps:
            gap_context = f"\n\nPrevious cycle identified these gaps to address:\n" + \
                         "\n".join(f"- {gap}" for gap in previous_gaps)

        user_message = f"""Project: {project_description}

Available context/documentation:
{list(context_docs.keys())}
{gap_context}

Break this research project into major components. Each component should be:
1. Independently researchable
2. Suitable for delegation to a sub-planner
3. Clear in scope

Return a JSON list of component names (strings)."""

        response = await self.llm_client.complete(
            system_prompt=self.system_prompt,
            user_message=user_message,
            temperature=0.5,
        )

        # Parse components from response
        import json
        try:
            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            components = json.loads(content)
            return components if isinstance(components, list) else []
        except json.JSONDecodeError:
            # Fallback: extract bullet points
            lines = response.content.strip().split("\n")
            components = []
            for line in lines:
                line = line.strip()
                if line.startswith("- ") or line.startswith("* "):
                    components.append(line[2:].strip())
                elif line and not line.startswith("#"):
                    components.append(line)
            return components[:10]  # Limit to 10 components


class SubPlannerAgentImpl(SubPlannerAgent):
    """Sub-Planner implementation for breaking components into tasks."""

    def __init__(
        self,
        agent_id: str,
        name: str,
        system_prompt: str,
        component: str,
        llm_client: Optional[LLMClient] = None,
    ):
        super().__init__(agent_id, name, system_prompt)
        self.component = component
        self.llm_client = llm_client

    def set_llm_client(self, client: LLMClient) -> None:
        """Set the LLM client."""
        self.llm_client = client

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
        if not self.llm_client:
            raise RuntimeError("LLM client not set")

        user_message = f"""Component: {component}

Available data/context:
{list(relevant_docs.keys())}

Break this component into atomic, executable tasks. Each task should:
1. Be completable by a single worker
2. Have clear inputs and expected outputs
3. Be specific and actionable

Return a JSON array of tasks with this structure:
[
  {{
    "description": "Task description",
    "inputs": {{"key": "value"}},
    "expected_output": "What the task should produce",
    "dependencies": []
  }}
]"""

        response = await self.llm_client.complete(
            system_prompt=self.system_prompt,
            user_message=user_message,
            temperature=0.5,
        )

        # Parse tasks from response
        import json
        try:
            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            tasks_data = json.loads(content)

            tasks = []
            for i, task_data in enumerate(tasks_data):
                task = HierarchicalTask(
                    task_id=f"{component.lower().replace(' ', '_')}_{i}_{uuid.uuid4().hex[:6]}",
                    component=component,
                    description=task_data.get("description", ""),
                    inputs=task_data.get("inputs", {}),
                    expected_output=task_data.get("expected_output", ""),
                    dependencies=task_data.get("dependencies", []),
                )
                tasks.append(task)

            return tasks

        except json.JSONDecodeError:
            # Fallback: create single task
            return [
                HierarchicalTask(
                    task_id=f"{component.lower().replace(' ', '_')}_0",
                    component=component,
                    description=f"Research and analyze {component}",
                    inputs={"component": component},
                    expected_output=f"Analysis of {component}",
                    dependencies=[],
                )
            ]


class WorkerAgentImpl(WorkerAgent):
    """Worker implementation for executing research tasks."""

    def __init__(
        self,
        agent_id: str,
        name: str,
        system_prompt: str,
        llm_client: Optional[LLMClient] = None,
    ):
        super().__init__(agent_id, name, system_prompt)
        self.llm_client = llm_client

    def set_llm_client(self, client: LLMClient) -> None:
        """Set the LLM client."""
        self.llm_client = client

    async def execute(
        self,
        task: HierarchicalTask,
        relevant_docs: dict[str, Any],
    ) -> HierarchicalArtifact:
        """Execute a single task.

        Args:
            task: Task to execute
            relevant_docs: Relevant documentation/data

        Returns:
            Artifact produced by task
        """
        if not self.llm_client:
            raise RuntimeError("LLM client not set")

        # Build context from relevant docs
        context_summary = ""
        for key, doc in relevant_docs.items():
            if isinstance(doc, str):
                context_summary += f"\n## {key}\n{doc[:2000]}"  # Truncate long docs
            else:
                context_summary += f"\n## {key}\n{str(doc)[:2000]}"

        user_message = f"""Task: {task.description}

Component: {task.component}
Expected Output: {task.expected_output}

Task Inputs:
{task.inputs}

Relevant Context:
{context_summary}

Complete this task and provide your analysis/output as JSON."""

        try:
            response = await self.llm_client.complete(
                system_prompt=self.system_prompt,
                user_message=user_message,
                temperature=0.7,
            )

            # Try to parse as JSON, otherwise wrap in content field
            import json
            try:
                content = response.content.strip()
                if content.startswith("```"):
                    content = content.split("```")[1]
                    if content.startswith("json"):
                        content = content[4:]
                result = json.loads(content)
            except json.JSONDecodeError:
                result = {"content": response.content, "raw": True}

            return HierarchicalArtifact(
                task_id=task.task_id,
                worker_id=self.agent_id,
                content=result,
                status="success",
            )

        except Exception as e:
            return HierarchicalArtifact(
                task_id=task.task_id,
                worker_id=self.agent_id,
                content={},
                status="failed",
                error=str(e),
            )


class JudgeAgentImpl(JudgeAgent):
    """Judge implementation for evaluating research output."""

    def __init__(
        self,
        agent_id: str,
        name: str,
        system_prompt: str,
        quality_criteria: dict[str, str],
        llm_client: Optional[LLMClient] = None,
    ):
        super().__init__(agent_id, name, system_prompt)
        self.quality_criteria = quality_criteria
        self.llm_client = llm_client

    def set_llm_client(self, client: LLMClient) -> None:
        """Set the LLM client."""
        self.llm_client = client

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
        if not self.llm_client:
            raise RuntimeError("LLM client not set")

        # Summarize artifacts
        artifacts_summary = []
        failed_tasks = []
        for artifact in artifacts:
            if artifact.status == "failed":
                failed_tasks.append(artifact.task_id)
            else:
                artifacts_summary.append({
                    "task_id": artifact.task_id,
                    "worker": artifact.worker_id,
                    "content_keys": list(artifact.content.keys()) if artifact.content else [],
                })

        criteria_text = "\n".join(
            f"- {name}: {desc}" for name, desc in self.quality_criteria.items()
        )

        user_message = f"""Evaluate the following research output:

## Artifacts Summary
{artifacts_summary}

## Failed Tasks
{failed_tasks}

## Requirements
{requirements}

## Quality Criteria
{criteria_text}

Evaluate against the criteria and provide:
1. Whether the project is complete (boolean)
2. A quality score (0-1)
3. List of gaps that need to be addressed
4. Recommendations for improvement

Return as JSON:
{{
  "complete": true/false,
  "quality_score": 0.0-1.0,
  "gaps": ["gap1", "gap2"],
  "recommendations": ["rec1", "rec2"]
}}"""

        try:
            response = await self.llm_client.complete(
                system_prompt=self.system_prompt,
                user_message=user_message,
                temperature=0.3,  # Lower temperature for consistent evaluation
            )

            import json
            content = response.content.strip()
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]

            result = json.loads(content)

            return JudgeEvaluation(
                complete=result.get("complete", False),
                quality_score=float(result.get("quality_score", 0.5)),
                gaps=result.get("gaps", []),
                recommendations=result.get("recommendations", []),
            )

        except Exception as e:
            # Fallback evaluation
            success_rate = len([a for a in artifacts if a.status == "success"]) / max(len(artifacts), 1)

            return JudgeEvaluation(
                complete=success_rate > 0.8 and not failed_tasks,
                quality_score=success_rate,
                gaps=[f"Failed task: {t}" for t in failed_tasks],
                recommendations=[f"Evaluation error: {str(e)}"],
            )


class HierarchicalOrchestrator:
    """Orchestrator for running hierarchical agent flow."""

    def __init__(
        self,
        main_planner: MainPlannerAgentImpl,
        llm_client: LLMClient,
        max_workers: int = 10,
        max_cycles: int = 5,
    ):
        self.main_planner = main_planner
        self.llm_client = llm_client
        self.max_workers = max_workers
        self.max_cycles = max_cycles

    async def run(
        self,
        project_description: str,
        context_docs: dict[str, Any],
        requirements: dict[str, Any],
    ) -> dict[str, Any]:
        """Run the hierarchical agent flow.

        Args:
            project_description: Description of the research project
            context_docs: Reference documentation
            requirements: Project requirements

        Returns:
            Final results including all artifacts
        """
        all_artifacts = []
        gaps = []

        for cycle in range(self.max_cycles):
            # 1. Plan phase
            components = await self.main_planner.plan(
                project_description=project_description,
                context_docs=context_docs,
                previous_gaps=gaps if gaps else None,
            )

            # 2. Decompose phase
            all_tasks = []
            for component in components:
                sub_planner = SubPlannerAgentImpl(
                    agent_id=f"sub_planner_{component}",
                    name="Component Planner",
                    system_prompt="You are a research planner. Break components into specific tasks.",
                    component=component,
                    llm_client=self.llm_client,
                )
                tasks = await sub_planner.decompose(component, context_docs)
                all_tasks.extend(tasks)

            # 3. Execute phase (parallel workers)
            cycle_artifacts = await self._execute_tasks_parallel(all_tasks, context_docs)
            all_artifacts.extend(cycle_artifacts)

            # 4. Evaluate phase
            judge = JudgeAgentImpl(
                agent_id="judge",
                name="Quality Judge",
                system_prompt="You evaluate research quality and completeness.",
                quality_criteria={
                    "completeness": "All required analysis completed",
                    "consistency": "Results are internally consistent",
                    "actionability": "Recommendations are actionable",
                },
                llm_client=self.llm_client,
            )

            evaluation = await judge.evaluate(cycle_artifacts, requirements)

            # 5. Check completion
            if evaluation.complete:
                return {
                    "status": "complete",
                    "cycles": cycle + 1,
                    "quality_score": evaluation.quality_score,
                    "artifacts": all_artifacts,
                    "recommendations": evaluation.recommendations,
                }

            gaps = evaluation.gaps

        return {
            "status": "max_cycles_reached",
            "cycles": self.max_cycles,
            "quality_score": evaluation.quality_score if evaluation else 0,
            "artifacts": all_artifacts,
            "remaining_gaps": gaps,
        }

    async def _execute_tasks_parallel(
        self,
        tasks: list[HierarchicalTask],
        context_docs: dict[str, Any],
    ) -> list[HierarchicalArtifact]:
        """Execute tasks in parallel using worker pool.

        Args:
            tasks: Tasks to execute
            context_docs: Context documentation

        Returns:
            List of artifacts from all tasks
        """
        semaphore = asyncio.Semaphore(self.max_workers)

        async def execute_with_limit(task: HierarchicalTask) -> HierarchicalArtifact:
            async with semaphore:
                worker = WorkerAgentImpl(
                    agent_id=f"worker_{task.task_id}",
                    name="Research Worker",
                    system_prompt="You execute specific research tasks efficiently.",
                    llm_client=self.llm_client,
                )
                return await worker.execute(task, context_docs)

        artifacts = await asyncio.gather(
            *[execute_with_limit(task) for task in tasks],
            return_exceptions=True,
        )

        # Convert exceptions to failed artifacts
        results = []
        for i, artifact in enumerate(artifacts):
            if isinstance(artifact, Exception):
                results.append(
                    HierarchicalArtifact(
                        task_id=tasks[i].task_id,
                        worker_id="error",
                        content={},
                        status="failed",
                        error=str(artifact),
                    )
                )
            else:
                results.append(artifact)

        return results
