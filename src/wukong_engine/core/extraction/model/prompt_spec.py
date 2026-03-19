from dataclasses import dataclass

from .task import EntityExtractionTask


@dataclass(frozen=True)
class EntityExtractionPromptSpec:
    """Required prompt specification for entity extraction."""

    # task: EntityExtractionTask
    # template: str
    # required_fields: tuple[str, ...]
    # output_instructions: str
