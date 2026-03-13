from wukong_engine.app.data_extraction.use_cases import ExtractEntityType
from wukong_engine.app.document_ingestion.use_cases import ValidateDocumentSources
from wukong_engine.app.model_ingestion.use_cases import GetDocumentRegistry, GetGraphModel
from wukong_engine.app.workflows import GraphConstructionPipeline
from wukong_engine.infrastructure.definitions.documents import LocalDocumentRegistryProvider
from wukong_engine.infrastructure.definitions.graph import LocalGraphModelProvider
from wukong_engine.infrastructure.storage.filesystem.documents import (
    LocalDocumentSourceValidator,
    LocalDocumentStreamProvider,
)

# from wukong_engine.app.extraction import ExtractEntities, ExtractRelationships
# from wukong_engine.app.graph import ExportGraph

# from wukong_engine.infrastructure.adapters.filesystem.file_loader import file_loader
# from wukong_engine.infrastructure.adapters.llm.openai_client import process_prompt
# from wukong_engine.infrastructure.config import config


class CLIApplication:
    """Composition root for the CLI.

    Owns infrastructure and exposes ready-to-use workflows, services and use cases.
    """

    def __init__(self) -> None:
        """Initialize the CLI application, composing all dependencies."""
        # Infrastructure
        graph_model_provider = LocalGraphModelProvider()
        document_registry_provider = LocalDocumentRegistryProvider()
        document_source_validator = LocalDocumentSourceValidator()
        document_stream_provider = LocalDocumentStreamProvider()

        # Use cases
        get_graph_model = GetGraphModel(graph_model_provider)
        get_document_registry = GetDocumentRegistry(document_registry_provider)
        validate_document_sources = ValidateDocumentSources(document_source_validator)
        extract_entity_type = ExtractEntityType(document_stream_provider)

        # Workflows
        self.graph_construction = GraphConstructionPipeline(
            get_graph_model=get_graph_model,
            get_document_registry=get_document_registry,
            validate_document_sources=validate_document_sources,
            extract_entity_type=extract_entity_type,
        )
