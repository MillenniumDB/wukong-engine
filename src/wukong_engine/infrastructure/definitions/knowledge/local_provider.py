"""Knowledge model provider backed by a local JSON file."""

from pathlib import Path

from wukong_engine.app.model_ingestion.ports import KnowledgeModelProvider
from wukong_engine.core.knowledge.model import KnowledgeModel
from wukong_engine.infrastructure.storage.filesystem import load_json_file

from .mapper import KnowledgeModelMapper
from .schemas import KnowledgeModelSchema


class LocalKnowledgeModelProvider(KnowledgeModelProvider):
    """Loads knowledge models from local JSON files."""

    def get(self, source_uri: str) -> KnowledgeModel:
        """Load a knowledge model from a local JSON file.

        Args:
            source_uri: Path to the JSON file defining the knowledge model.

        Returns:
            The validated knowledge model.
        """
        path = Path(source_uri)
        raw = load_json_file(path)
        schema = KnowledgeModelSchema.model_validate(raw)
        return KnowledgeModelMapper().map_knowledge_model(schema)
