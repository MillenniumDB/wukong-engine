import json
from pathlib import Path

from wukong_engine.app.model_ingestion.ports import GraphModelProvider
from wukong_engine.core.graph.model import GraphModel

from .mapper import GraphModelMapper
from .schemas import GraphModelSchema


class LocalGraphModelProvider(GraphModelProvider):
    """Loads graph models from local JSON files."""

    def get(self, source_uri: str) -> GraphModel:
        """Load a graph model from a local JSON file."""
        path = Path(source_uri)
        raw = json.load(path.open())
        schema = GraphModelSchema.model_validate(raw)
        return GraphModelMapper().map_graph_model(schema)
