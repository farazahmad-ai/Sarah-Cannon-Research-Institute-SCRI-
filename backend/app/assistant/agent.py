"""PydanticAI agent definition for SCRI Oncology Copilot.

Configures:
- Agent instance with typed OncologyAgentDeps
- Clinical oncology system prompt
- Dynamic context injection from retrieved protocol passages
"""

import logging

from pydantic_ai import Agent, RunContext
from pydantic_ai.models.openai import OpenAIModel

from app.assistant.deps import OncologyAgentDeps
from app.assistant.prompts import SYSTEM_PROMPT, format_protocol_context
from app.config import settings

logger = logging.getLogger(__name__)


def get_agent_model() -> OpenAIModel:
    """Instantiate OpenAIModel configured for OpenAI or OpenRouter."""
    return OpenAIModel(
        model_name=settings.OPENAI_CHAT_MODEL,
        base_url=settings.effective_base_url,
        api_key=settings.effective_api_key,
    )


def create_oncology_agent() -> Agent[OncologyAgentDeps, str]:
    """Factory creating the clinical screening PydanticAI agent."""
    model = get_agent_model()
    agent: Agent[OncologyAgentDeps, str] = Agent(
        model=model,
        deps_type=OncologyAgentDeps,
        system_prompt=SYSTEM_PROMPT,
    )

    @agent.system_prompt
    async def add_protocol_context(ctx: RunContext[OncologyAgentDeps]) -> str:
        """Dynamically inject retrieved protocol passages into agent context."""
        return format_protocol_context(ctx.deps.retrieved_passages)

    return agent


# Default singleton agent instance
oncology_agent = create_oncology_agent()
