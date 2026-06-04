"""Prompt renderer for extraction requests."""

from wukong_engine.app.data_extraction.dtos import ExtractionContext
from wukong_engine.app.llm.elements import LLMRequest

# Constants
KG_EXTRACTION_SYSTEM_PROMPT = """
You are a knowledge graph extraction engine.
Extract only information explicitly supported by the source text.
If information is ambiguous, omit it rather than guessing.
Preserve extracted values exactly as expressed in the source text.
Produce output that conforms exactly to the provided response schema.
""".strip()
KG_EXTRACTION_BASE_USER_PROMPT = """
Document Context

{DOCUMENT_CONTEXT}

Task

{TASK}

Definitions

{DEFINITIONS}

Source Text

<text>
{SOURCE_TEXT}
</text>
""".strip()


class PromptRenderer:
    """Prompt renderer for extraction requests."""

    def render(self, context: ExtractionContext) -> LLMRequest:
        """Render the prompt and build an LLM request."""
        system_prompt = KG_EXTRACTION_SYSTEM_PROMPT
        user_prompt = KG_EXTRACTION_BASE_USER_PROMPT.format(
            TASK=context.task,
            DOCUMENT_CONTEXT=context.document_context,
            DEFINITIONS=context.definitions,
            SOURCE_TEXT=context.source_text,
        )
        return LLMRequest(user_prompt=user_prompt, system_prompt=system_prompt, response_schema=context.response_schema)
