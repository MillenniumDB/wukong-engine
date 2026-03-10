import json
from pathlib import Path

from wukong_engine.app.model_ingestion.ports import GraphModelProvider
from wukong_engine.core.graph.model import GraphModel

from .mappers import GraphModelMapper
from .schemas import GraphModelSchema


# TODO: Catch pydantic errors and raise GraphModelLoadError or similar
# TODO: See if file_utils is used as a helper in infra
# TODO: Errors from file reading
class LocalGraphModelProvider(GraphModelProvider):
    """Loads graph models from local JSON files."""

    def get(self, path: Path) -> GraphModel:
        """Load a graph model from a local JSON file."""
        raw = json.load(path.open())
        schema = GraphModelSchema.model_validate(raw)
        return GraphModelMapper().map_graph_model(schema)
