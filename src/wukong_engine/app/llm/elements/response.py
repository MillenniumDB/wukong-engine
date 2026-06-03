"""Response model for LLM interactions."""

from dataclasses import dataclass


# TODO: Validator and conversion to domain
@dataclass(frozen=True)
class LLMResponse:
    """Response envelope returned by an LLM client."""

    content: str
    model: str
    input_tokens: int
    output_tokens: int


# TODO: Validator takes LLMResponse content and validates against the response schema, then converts to these DTOs
# TODO: Later, the DTOs are mapped to actual Entity instances
# @dataclass(frozen=True)
# class ExtractedEntityDto:
#     type: str
#     properties: Mapping[str, str]

# @dataclass(frozen=True)
# class ExtractionResultDto:
#     entities: Sequence[ExtractedEntityDto]
