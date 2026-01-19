from pathlib import Path

from wukong_engine.app.blueprints.ports import DataModelProvider
from wukong_engine.core.schema import DataModel


class GetDataModel:
    def __init__(self, provider: DataModelProvider) -> None:
        self._provider = provider

    def execute(self, data_model_path: Path) -> DataModel:
        return self._provider.get(data_model_path)
