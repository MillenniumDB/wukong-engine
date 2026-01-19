import json
from pathlib import Path

from wukong_engine.app.blueprints.ports import DataModelProvider
from wukong_engine.core.data_model import DataModel

from .mappers import to_data_model
from .schemas import DataModelSchema


class LocalDataModelProvider(DataModelProvider):
    def get(self, path: Path) -> DataModel | None:
        # TODO: See if file_utils is used as a helper in infra
        # TODO: Errors from file reading
        raw = json.load(path.open())
        # TODO: Validate with pydantic
        # TODO: Catch pydantic errors and raise DataModelLoadError or similar
        # validated = DataModelSchema.model_validate(raw)
        # TODO: Convert to domain model (DataModel) (do not handle any errors here, instead on app)
        # return to_data_model(validated)
        return None
