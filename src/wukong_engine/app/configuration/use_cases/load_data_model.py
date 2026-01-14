from pathlib import Path

# from app.ports.schema_repository import SchemaRepository
from wukong_engine.core.schema import DataModel


class LoadDataModel:
    def __init__(self):
        # self._repository = repository
        pass

    def execute(self, path: Path) -> DataModel:
        # TODO: Load schema definition from repository (pydantic model in the repository exports definition)
        # schema_definition = self._repository.load(path)
        schema_definition = {}  # Placeholder
        return DataModel.from_definition(schema_definition)
