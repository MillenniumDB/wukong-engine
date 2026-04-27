from wukong_engine.app.model_ingestion.ports import GraphModelProvider
from wukong_engine.core.graph.model import GraphModel


class GetGraphModel:
    """Use case for retrieving the graph model from a specified URI."""

    def __init__(self, provider: GraphModelProvider) -> None:
        """Initialize the use case with its dependencies."""
        self._provider = provider

    def execute(self, graph_model_uri: str) -> GraphModel:
        """Retrieve the graph model from the specified URI."""
        return self._provider.get(graph_model_uri)
