from pathlib import Path

from wukong_engine.app.model_ingestion.ports import GraphModelSchemaProvider
from wukong_engine.core.graph import GraphModel


class GetGraphModel:
    def __init__(self, provider: GraphModelSchemaProvider) -> None:
        self._provider = provider

    # TODO: Return GraphModel
    def execute(self, graph_model_path: Path) -> GraphModel | None:
        graph_model_schema = self._provider.get(graph_model_path)
        # graph_model_schema.to_domain()
        return
