"""Prompt renderer for extraction requests."""

from wukong_engine.app.data_extraction.elements import ExtractionSpec
from wukong_engine.app.llm.elements.values import LLMPrompt

# Constants
KG_EXTRACTION_INSTRUCTIONS = """
You are a knowledge graph extraction engine.
Extract only information explicitly supported by the source text.
If information is ambiguous, omit it rather than guessing.
Preserve extracted values exactly as expressed in the source text.
Produce output that conforms exactly to the provided response schema.
""".strip()
KG_EXTRACTION_CONTENT = """
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

    def render(self, spec: ExtractionSpec) -> LLMPrompt:
        """Render the prompt from the extraction specification."""
        prompt_instructions = KG_EXTRACTION_INSTRUCTIONS
        prompt_content = KG_EXTRACTION_CONTENT.format(
            DOCUMENT_CONTEXT=spec.document_context,
            TASK=spec.task,
            DEFINITIONS=spec.definitions,
            SOURCE_TEXT=spec.source_text,
        )
        return LLMPrompt(content=prompt_content, instructions=prompt_instructions, schema=spec.response_schema)
