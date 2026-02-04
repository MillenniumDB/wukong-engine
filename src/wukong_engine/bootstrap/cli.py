from wukong_engine.app.model_ingestion.use_cases import GetGraphModel
from wukong_engine.app.workflows import GraphConstructionPipeline
from wukong_engine.infrastructure.model_providers.graph_model import LocalGraphModelProvider

# from wukong_engine.app.extraction import ExtractEntities, ExtractRelationships
# from wukong_engine.app.graph import ExportGraph

# from wukong_engine.infrastructure.adapters.filesystem.file_loader import file_loader
# from wukong_engine.infrastructure.adapters.llm.openai_client import process_prompt
# from wukong_engine.infrastructure.config import config


class CLIApplication:
    """Composition root for the CLI.

    Owns infrastructure and exposes ready-to-use workflows, services and use cases.
    """

    def __init__(self):
        # Infrastructure
        graph_model_provider = LocalGraphModelProvider()

        # Use cases
        get_graph_model = GetGraphModel(graph_model_provider)

        # Workflows
        self.graph_construction = GraphConstructionPipeline(get_graph_model=get_graph_model)
