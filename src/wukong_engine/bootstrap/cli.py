from wukong_engine.app.configuration import LoadDataModel
from wukong_engine.app.workflows import GraphConstruction

# from wukong_engine.app.extraction import ExtractEntities, ExtractRelationships
# from wukong_engine.app.graph import ExportGraph

# from wukong_engine.infrastructure.adapters.filesystem.file_loader import file_loader
# from wukong_engine.infrastructure.adapters.llm.openai_client import process_prompt
# from wukong_engine.infrastructure.config import config


class CLIApplication:
    """Composition root for the CLI.

    Owns infrastructure and exposes ready-to-use workflows and use cases.
    """

    def __init__(self):
        # Infrastructure
        # schema_repo = FileSystemSchemaRepository()
        # graph_exporter = FileSystemGraphExporter()

        # Use cases
        self.load_data_model = LoadDataModel()
        # self.export_graph = ExportGraph(graph_exporter)

        # Workflows
        self.graph_construction = GraphConstruction(
            load_data_model=self.load_data_model,
            # export_graph=self.export_graph,
        )
