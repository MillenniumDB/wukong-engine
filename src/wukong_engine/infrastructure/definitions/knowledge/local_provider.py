import json
from pathlib import Path

from wukong_engine.app.model_ingestion.ports import KnowledgeModelProvider
from wukong_engine.core.knowledge.model import KnowledgeModel

from .mapper import KnowledgeModelMapper
from .schemas import KnowledgeModelSchema


class LocalKnowledgeModelProvider(KnowledgeModelProvider):
    """Loads knowledge models from local JSON files."""

    def get(self, source_uri: str) -> KnowledgeModel:
        """Load a knowledge model from a local JSON file."""
        path = Path(source_uri)
        raw = json.load(path.open())
        schema = KnowledgeModelSchema.model_validate(raw)
        return KnowledgeModelMapper().map_knowledge_model(schema)
