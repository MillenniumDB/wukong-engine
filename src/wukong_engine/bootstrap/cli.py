from wukong_engine.app.blueprints import GetDataModel
from wukong_engine.app.workflows import GraphConstruction
from wukong_engine.infrastructure.blueprints.data_model import LocalDataModelProvider

# from wukong_engine.app.extraction import ExtractEntities, ExtractRelationships
# from wukong_engine.app.graph import ExportGraph

# from wukong_engine.infrastructure.adapters.filesystem.file_loader import file_loader
# from wukong_engine.infrastructure.adapters.llm.openai_client import process_prompt
# from wukong_engine.infrastructure.config import config


class CliApplication:
    """Composition root for the CLI.

    Owns infrastructure and exposes ready-to-use workflows and use cases.
    """

    def __init__(self):
        # Infrastructure
        data_model_provider = LocalDataModelProvider()

        # Use cases
        self.get_data_model = GetDataModel(data_model_provider)

        # Workflows
        self.graph_construction = GraphConstruction(get_data_model=self.get_data_model)
