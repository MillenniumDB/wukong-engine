"""Result materializers for extraction tasks."""

from wukong_engine.app.data_extraction.dtos import ExtractionResult
from wukong_engine.app.data_extraction.ports import PKNormalizer
from wukong_engine.core.graph.elements import Entity


# TODO: Implement
class EntityMaterializer:
    """Materializer that converts raw extraction results into entity instances."""

    def __init__(self, pk_normalizer: PKNormalizer) -> None:
        """Initialize the materializer with necessary dependencies."""
        self._pk_normalizer = pk_normalizer

    def materialize(self, result: ExtractionResult) -> tuple[Entity, ...]:
        """Materialize the extraction result into entity instances."""
        print('materializing result')
        return ()
