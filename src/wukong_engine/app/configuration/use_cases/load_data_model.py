from pathlib import Path

from wukong_engine.core.schema import DataModel


class LoadDataModel:
    def __init__(self):
        # self._repository = repository
        pass

    def execute(self, data_model_path: Path) -> DataModel:
        # TODO: Load schema definition from repository, then use validator port for pydantic validation
        # schema_definition = self._repository.load(path)
        schema_definition = {}  # Placeholder
        # return DataModel.from_definition(schema_definition)
        return DataModel([])  # Placeholder
