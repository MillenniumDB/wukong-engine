from wukong_engine.app.model_ingestion.ports import GraphModelProvider
from wukong_engine.core.graph.model import GraphModel


class GetGraphModel:
    def __init__(self, provider: GraphModelProvider) -> None:
        self._provider = provider

    def execute(self, graph_model_uri: str) -> GraphModel:
        return self._provider.get(graph_model_uri)
