"""PydanticAI agent definition for SCRI Oncology Copilot.

Configures:
- Agent instance with typed OncologyAgentDeps
- Clinical oncology system prompt
- Dynamic context injection from retrieved protocol passages
"""

import logging

from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from app.assistant.deps import OncologyAgentDeps
from app.assistant.prompts import (
    SYSTEM_PROMPT,
    format_corpus_manifest,
    format_protocol_context,
)
from app.config import settings

logger = logging.getLogger(__name__)


def get_agent_model() -> OpenAIChatModel:
    """Instantiate OpenAIChatModel configured for OpenAI or OpenRouter."""
    provider = OpenAIProvider(
        api_key=settings.effective_api_key,
        base_url=settings.effective_base_url,
    )
    return OpenAIChatModel(
        model_name=settings.OPENAI_CHAT_MODEL,
        provider=provider,
    )


def create_oncology_agent() -> Agent[OncologyAgentDeps, str]:
    """Factory creating the clinical screening PydanticAI agent."""
    model = get_agent_model()
    agent: Agent[OncologyAgentDeps, str] = Agent(
        model=model,
        deps_type=OncologyAgentDeps,
        system_prompt=SYSTEM_PROMPT,
    )

    @agent.system_prompt(dynamic=True)
    async def add_protocol_context(ctx: RunContext[OncologyAgentDeps]) -> str:
        """Dynamically inject retrieved protocol passages into agent context.

        Also injects the corpus manifest so the model knows which disease areas
        this system actually covers and can refuse off-corpus topics instead of
        guessing (audit finding C3).
        """
        parts: list[str] = []
        if ctx.deps.corpus_manifest:
            manifest_str = format_corpus_manifest(ctx.deps.corpus_manifest)
            if manifest_str:
                parts.append(manifest_str)
        parts.append(format_protocol_context(ctx.deps.retrieved_passages))
        return "\n\n".join(parts)

    return agent


# Default singleton agent instance
oncology_agent = create_oncology_agent()
