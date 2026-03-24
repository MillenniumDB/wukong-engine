from dataclasses import dataclass

from .task import EntityExtractionTask


# TODO: ExtractionSpec vs PromptSpec vs TaskSpec for the name
@dataclass(frozen=True)
class EntityExtractionPromptSpec:
    """Required prompt specification for entity extraction."""

    # task: EntityExtractionTask
    # template: str
    # required_fields: tuple[str, ...]
    # output_instructions: str
