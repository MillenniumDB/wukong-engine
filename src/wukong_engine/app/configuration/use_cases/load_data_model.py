from pathlib import Path

from wukong_engine.app.configuration.ports.sources import DataModelSource
from wukong_engine.core.schema import DataModel


class LoadDataModel:
    def __init__(self, source: DataModelSource) -> None:
        self._source = source

    def execute(self, data_model_path: Path) -> DataModel:
        return self._source.get(data_model_path)
