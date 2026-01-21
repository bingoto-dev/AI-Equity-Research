"""Claude API client wrapper with structured output support."""

import json
import logging
from typing import Any, Dict, Optional, TypeVar

import anthropic
from pydantic import BaseModel

from config.settings import AnthropicSettings

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class LLMResponse(BaseModel):
    """Response from LLM call."""

    content: str
    model: str
    input_tokens: int
    output_tokens: int
    stop_reason: Optional[str] = None
    raw_response: Optional[Dict[str, Any]] = None


class LLMClient:
    """Client for Claude API with structured output support."""

    def __init__(self, settings: AnthropicSettings):
        """Initialize the LLM client.

        Args:
            settings: Anthropic API settings
        """
        if not settings.api_key:
            raise ValueError("Anthropic API key is required to use the LLM client")
        self.settings = settings
        self._client = anthropic.Anthropic(
            api_key=settings.api_key.get_secret_value(),
        )

    async def complete(
        self,
        system_prompt: str,
        user_message: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """Make a completion request.

        Args:
            system_prompt: System prompt for the model
            user_message: User message
            temperature: Override temperature
            max_tokens: Override max tokens

        Returns:
            LLMResponse with completion
        """
        try:
            response = self._client.messages.create(
                model=self.settings.model,
                max_tokens=max_tokens or self.settings.max_tokens,
                temperature=temperature if temperature is not None else self.settings.temperature,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_message}
                ],
            )

            content = ""
            for block in response.content:
                if block.type == "text":
                    content += block.text

            return LLMResponse(
                content=content,
                model=response.model,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                stop_reason=response.stop_reason,
            )

        except anthropic.APIError as e:
            logger.error(f"Anthropic API error: {e}")
            raise

    async def complete_structured(
        self,
        system_prompt: str,
        user_message: str,
        output_model: type[T],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> tuple[T, LLMResponse]:
        """Make a completion request with structured output.

        Args:
            system_prompt: System prompt for the model
            user_message: User message
            output_model: Pydantic model for output parsing
            temperature: Override temperature
            max_tokens: Override max tokens

        Returns:
            Tuple of (parsed model, raw response)
        """
        # Add JSON schema to system prompt
        schema = output_model.model_json_schema()
        enhanced_system = f"""{system_prompt}

IMPORTANT: You must respond with valid JSON that matches this schema:
```json
{json.dumps(schema, indent=2)}
```

Respond ONLY with the JSON object, no other text."""

        response = await self.complete(
            system_prompt=enhanced_system,
            user_message=user_message,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        # Parse the response
        try:
            # Try to extract JSON from the response
            content = response.content.strip()

            # Handle markdown code blocks
            if content.startswith("```json"):
                content = content[7:]
            if content.startswith("```"):
                content = content[3:]
            if content.endswith("```"):
                content = content[:-3]

            content = content.strip()

            parsed = output_model.model_validate_json(content)
            return parsed, response

        except Exception as e:
            logger.error(f"Failed to parse structured output: {e}")
            logger.debug(f"Raw content: {response.content}")
            raise ValueError(f"Failed to parse LLM response as {output_model.__name__}: {e}")

    async def complete_with_retry(
        self,
        system_prompt: str,
        user_message: str,
        max_retries: int = 3,
        **kwargs: Any,
    ) -> LLMResponse:
        """Make a completion request with retry logic.

        Args:
            system_prompt: System prompt
            user_message: User message
            max_retries: Maximum retry attempts
            **kwargs: Additional arguments for complete()

        Returns:
            LLMResponse
        """
        last_error = None

        for attempt in range(max_retries):
            try:
                return await self.complete(
                    system_prompt=system_prompt,
                    user_message=user_message,
                    **kwargs,
                )
            except anthropic.RateLimitError as e:
                logger.warning(f"Rate limited, attempt {attempt + 1}/{max_retries}")
                last_error = e
                if attempt < max_retries - 1:
                    import asyncio
                    await asyncio.sleep(2 ** attempt)  # Exponential backoff
            except anthropic.APIError as e:
                logger.error(f"API error on attempt {attempt + 1}: {e}")
                last_error = e
                if attempt < max_retries - 1:
                    import asyncio
                    await asyncio.sleep(1)

        raise last_error or Exception("Max retries exceeded")

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text.

        Args:
            text: Text to estimate

        Returns:
            Estimated token count
        """
        # Rough estimation: ~4 characters per token for English
        return len(text) // 4

    def get_usage_stats(self) -> dict[str, Any]:
        """Get usage statistics (placeholder).

        Returns:
            Dict with usage stats
        """
        return {
            "model": self.settings.model,
            "max_tokens": self.settings.max_tokens,
            "temperature": self.settings.temperature,
        }


class AgentLLMClient(LLMClient):
    """Specialized LLM client for research agents."""

    async def get_top_picks(
        self,
        system_prompt: str,
        data_summary: str,
        num_picks: int = 5,
    ) -> tuple[list[dict[str, Any]], LLMResponse]:
        """Get top stock picks from an agent.

        Args:
            system_prompt: Agent's system prompt
            data_summary: Market data summary
            num_picks: Number of picks to request

        Returns:
            Tuple of (list of picks, raw response)
        """
        from src.agents.base import StockPick

        class TopPicksResponse(BaseModel):
            picks: list[StockPick]
            reasoning: str

        user_message = f"""Based on the following market data and your expertise, provide your top {num_picks} stock picks.

{data_summary}

Analyze the data and provide your picks with conviction scores, thesis, risks, and catalysts."""

        parsed, response = await self.complete_structured(
            system_prompt=system_prompt,
            user_message=user_message,
            output_model=TopPicksResponse,
            temperature=0.7,
        )

        return [pick.model_dump() for pick in parsed.picks], response

    async def get_ceo_decisions(
        self,
        system_prompt: str,
        previous_picks: Optional[list[dict[str, Any]]],
        proposed_picks: list[dict[str, Any]],
        loop_number: int,
    ) -> tuple[list[dict[str, Any]], LLMResponse]:
        """Get CEO KEEP/SWAP decisions.

        Args:
            system_prompt: CEO's system prompt
            previous_picks: Previous loop's picks (None for loop 1)
            proposed_picks: New proposed picks
            loop_number: Current loop number

        Returns:
            Tuple of (list of decisions, raw response)
        """
        from src.agents.base import CEODecision

        class CEODecisionsResponse(BaseModel):
            decisions: list[CEODecision]
            stability_assessment: str

        if loop_number == 1 or not previous_picks:
            # First loop - just accept the picks
            user_message = f"""This is loop {loop_number} (first loop).

Proposed Top 3:
{json.dumps(proposed_picks, indent=2)}

Since this is the first loop, please confirm these picks as the baseline."""
        else:
            user_message = f"""This is loop {loop_number}.

Previous Top 3:
{json.dumps(previous_picks, indent=2)}

Proposed Top 3:
{json.dumps(proposed_picks, indent=2)}

For each position, decide whether to KEEP the previous pick or SWAP to the new proposed pick.
Remember: Only SWAP if there's a compelling reason (>15 point conviction delta or material new information)."""

        parsed, response = await self.complete_structured(
            system_prompt=system_prompt,
            user_message=user_message,
            output_model=CEODecisionsResponse,
            temperature=0.5,  # Lower temperature for more consistent decisions
        )

        return [dec.model_dump() for dec in parsed.decisions], response

    async def synthesize_picks(
        self,
        system_prompt: str,
        layer2_outputs: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], LLMResponse]:
        """Synthesize Layer 2 outputs into final Top 3.

        Args:
            system_prompt: Fund Manager's system prompt
            layer2_outputs: Outputs from Layer 2 agents

        Returns:
            Tuple of (final top 3 picks, raw response)
        """
        from src.agents.base import StockPick

        class FundManagerResponse(BaseModel):
            top3: list[StockPick]
            synthesis_reasoning: str
            excluded_companies: list[str]
            exclusion_reasons: dict[str, str]

        user_message = f"""Synthesize the following inputs from your analysts into a final Top 3.

Layer 2 Analyst Outputs:
{json.dumps(layer2_outputs, indent=2)}

Create your final Top 3 picks, explaining:
1. Why each made the cut
2. What was excluded and why
3. Suggested position sizing"""

        parsed, response = await self.complete_structured(
            system_prompt=system_prompt,
            user_message=user_message,
            output_model=FundManagerResponse,
            temperature=0.6,
        )

        return [pick.model_dump() for pick in parsed.top3], response
