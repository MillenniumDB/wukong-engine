import json
from pathlib import Path

from wukong_engine.app.model_ingestion.ports import GraphModelProvider
from wukong_engine.core.graph import GraphModel

from .mappers import schema_to_graph_model
from .schemas import GraphModelSchema


class LocalGraphModelProvider(GraphModelProvider):
    def get(self, path: Path) -> GraphModel | None:
        # TODO: See if file_utils is used as a helper in infra
        # TODO: Errors from file reading
        raw = json.load(path.open())
        # TODO: Validate with pydantic
        # TODO: Catch pydantic errors and raise DataModelLoadError or similar
        validated = GraphModelSchema.model_validate(raw)
        # TODO: Convert to domain model (DataModel) (do not handle any errors here, instead on app)
        # return to_data_model(validated)
        return None
