import json
from pathlib import Path

from wukong_engine.core.schema import DataModel

from .schemas import DataSchema


class JsonFileDataModelSource:
    def get(self, path: Path) -> DataModel | None:
        raw = json.load(path.open())
        validated = DataSchema.model_validate(raw)
        return None
