from pathlib import Path

from wukong_engine.app.data_extraction.use_cases import ExtractEntityType
from wukong_engine.app.document_ingestion.use_cases import ValidateDocumentSources
from wukong_engine.app.model_ingestion.use_cases import GetDocumentRegistry, GetGraphModel
from wukong_engine.app.workflows import GraphConstructionPipeline
from wukong_engine.infrastructure.config import ConfigProvider, load_env_config
from wukong_engine.infrastructure.definitions.documents import LocalDocumentRegistryProvider
from wukong_engine.infrastructure.definitions.graph import LocalGraphModelProvider
from wukong_engine.infrastructure.llm.openai import OpenAIClient, OpenAIConfig
from wukong_engine.infrastructure.logging import configure_logging
from wukong_engine.infrastructure.storage.filesystem.documents import (
    LocalDocumentSourceValidator,
    LocalDocumentStreamProvider,
)


class CLIApplication:
    """Composition root for the CLI.

    Owns infrastructure and ready-to-use workflows and use cases.
    """

    def __init__(self, graph_construction_pipeline: GraphConstructionPipeline) -> None:
        """Initialize the CLI application, composing all dependencies."""
        self.graph_construction = graph_construction_pipeline


def build_application(config_path: Path, verbosity: int) -> CLIApplication:
    """Build the CLI application."""
    # Configuration
    configure_logging(verbosity)
    env_config = load_env_config()
    app_config = ConfigProvider().get(config_path)

    # Infrastructure
    graph_model_provider = LocalGraphModelProvider()
    document_registry_provider = LocalDocumentRegistryProvider()
    document_source_validator = LocalDocumentSourceValidator()
    document_stream_provider = LocalDocumentStreamProvider()
    llm_config = OpenAIConfig(api_key=env_config.openai_api_key, model=app_config.llm.model.name)
    llm_client = OpenAIClient(config=llm_config)

    # Use cases
    get_graph_model = GetGraphModel(provider=graph_model_provider)
    get_document_registry = GetDocumentRegistry(provider=document_registry_provider)
    validate_document_sources = ValidateDocumentSources(validator=document_source_validator)
    extract_entity_type = ExtractEntityType(stream_provider=document_stream_provider, llm_client=llm_client)

    # Workflows
    graph_construction = GraphConstructionPipeline(
        app_config=app_config,
        get_graph_model=get_graph_model,
        get_document_registry=get_document_registry,
        validate_document_sources=validate_document_sources,
        extract_entity_type=extract_entity_type,
    )
    return CLIApplication(graph_construction_pipeline=graph_construction)
