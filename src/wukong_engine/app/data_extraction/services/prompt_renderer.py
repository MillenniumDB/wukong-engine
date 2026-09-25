"""Prompt renderer for extraction requests."""

from wukong_engine.app.data_extraction.elements import ExtractionSpec
from wukong_engine.app.llm.elements.values import LLMPrompt

# Constants
KG_EXTRACTION_INSTRUCTIONS = """
You are a knowledge extraction engine.
Extract only information explicitly supported by the source text.
If information is ambiguous, omit it rather than guessing.
Preserve extracted values exactly as expressed in the source text.
Produce output that conforms exactly to the provided response schema.
""".strip()
KG_EXTRACTION_SHARED_CONTENT = """
Document Context
================

{DOCUMENT_CONTEXT}

Task
====

{TASK}

Definitions
===========

{DEFINITIONS}
""".strip()
KG_EXTRACTION_CONTENT = """
Source Text
===========

<text>
{SOURCE_TEXT}
</text>
""".strip()
SECTION_SEPARATOR = '\n\n'


class PromptRenderer:
    """Prompt renderer for extraction requests."""

    def render(self, spec: ExtractionSpec) -> LLMPrompt:
        """Render the prompt from the extraction specification.

        Everything shared by jobs extracting the same types goes into the shared content, so that it forms a
        reusable prefix, and everything specific to the job's source goes after it.
        """
        shared_content = (
            KG_EXTRACTION_SHARED_CONTENT.format(
                DOCUMENT_CONTEXT=spec.document_context,
                TASK=spec.task,
                DEFINITIONS=spec.definitions,
            )
            + SECTION_SEPARATOR
        )
        content = KG_EXTRACTION_CONTENT.format(SOURCE_TEXT=spec.source_text)
        if spec.source_definitions:
            content = spec.source_definitions + SECTION_SEPARATOR + content
        return LLMPrompt(
            content=content,
            instructions=KG_EXTRACTION_INSTRUCTIONS,
            schema=spec.response_schema,
            shared_content=shared_content,
        )
