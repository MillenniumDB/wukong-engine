from pathlib import Path

from wukong_engine.app.data_extraction.use_cases import ExtractEntities
from wukong_engine.app.document_ingestion.use_cases import IngestDocuments
from wukong_engine.app.model_ingestion.use_cases import GetDocumentRegistry, GetGraphModel
from wukong_engine.app.workflows import GraphConstructionPipeline
from wukong_engine.app.workspace import Workspace
from wukong_engine.infrastructure.chunking import ChunkingPlan, RecursiveDocumentChunker
from wukong_engine.infrastructure.config import ConfigProvider, load_env_config
from wukong_engine.infrastructure.definitions.documents import LocalDocumentRegistryProvider
from wukong_engine.infrastructure.definitions.graph import LocalGraphModelProvider
from wukong_engine.infrastructure.llm.openai import OpenAIClient, OpenAIConfig
from wukong_engine.infrastructure.logging import configure_logging
from wukong_engine.infrastructure.normalization.primary_key import DefaultPKNormalizer
from wukong_engine.infrastructure.persistence.sqlite import (
    SQLiteSessionFactory,
    SQLiteUnitOfWork,
    initialize_sqlite_database,
)
from wukong_engine.infrastructure.storage.filesystem.documents import (
    LocalDocumentLoader,
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


def build_application(workspace: Workspace, config_path: Path, verbosity: int) -> CLIApplication:
    """Build the CLI application."""
    # Configuration
    configure_logging(verbosity)
    env_config = load_env_config()
    app_config = ConfigProvider().get(config_path)

    # Database Initialization
    session_factory = SQLiteSessionFactory(db_path=workspace.paths.staging_db)
    initialize_sqlite_database(db_path=workspace.paths.staging_db, connection_factory=session_factory)

    # Infrastructure
    graph_model_provider = LocalGraphModelProvider()
    document_registry_provider = LocalDocumentRegistryProvider()
    document_source_validator = LocalDocumentSourceValidator()
    document_stream_provider = LocalDocumentStreamProvider()
    staging_uow = SQLiteUnitOfWork(connection_factory=session_factory)
    llm_config = OpenAIConfig(api_key=env_config.openai_api_key, model=app_config.llm.model.name)
    llm_client = OpenAIClient(config=llm_config)
    pk_normalizer = DefaultPKNormalizer()

    # Use cases
    get_document_registry = GetDocumentRegistry(
        provider=document_registry_provider,
        validator=document_source_validator,
    )
    get_graph_model = GetGraphModel(provider=graph_model_provider)
    ingest_documents = IngestDocuments(
        stream_provider=document_stream_provider,
        loader=LocalDocumentLoader(),
        chunker=RecursiveDocumentChunker(
            plan=ChunkingPlan(
                target_size=app_config.chunking.target_tokens,
                overlap_size=app_config.chunking.overlap_tokens
                if app_config.chunking.overlap_tokens is not None
                else 0,
                max_size=app_config.chunking.max_tokens if app_config.chunking.max_tokens is not None else 0,
            ),
        ),
        uow=staging_uow,
    )
    extract_entities = ExtractEntities(
        uow=staging_uow,
        llm_client=llm_client,
        pk_normalizer=pk_normalizer,
    )

    # Workflows
    graph_construction = GraphConstructionPipeline(
        app_config=app_config,
        uow=staging_uow,
        get_document_registry=get_document_registry,
        get_graph_model=get_graph_model,
        ingest_documents=ingest_documents,
        extract_entities=extract_entities,
    )
    return CLIApplication(graph_construction_pipeline=graph_construction)
