import logging
from pathlib import Path

from wukong_engine.app.config.exceptions import ConfigurationError
from wukong_engine.app.data_extraction.model.values import ExecutionMode
from wukong_engine.app.data_extraction.services import (
    BatchExtractionEngine,
    ConcurrentExtractionBatchSubmitter,
    ConcurrentExtractionExecutor,
    EntityExtractionMetricsTracker,
    EntityExtractionRepository,
    EntityExtractionRequestBuilder,
    EntityExtractionResultMaterializer,
    RealtimeExtractionEngine,
)
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
from wukong_engine.infrastructure.logging import set_logger_verbosity
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

# Logging
logger = logging.getLogger(__name__)


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
    try:
        set_logger_verbosity(verbosity)
        env_config = load_env_config()
        app_config = ConfigProvider().get(config_path)
    except Exception as exc:
        error = f'Failed to load configuration: {exc}'
        logger.error(error)
        raise ConfigurationError(error) from exc

    # Database Initialization
    session_factory = SQLiteSessionFactory(db_path=workspace.paths.staging_db)
    initialize_sqlite_database(db_path=workspace.paths.staging_db, connection_factory=session_factory)

    # Infrastructure
    graph_model_provider = LocalGraphModelProvider()
    document_registry_provider = LocalDocumentRegistryProvider()
    document_source_validator = LocalDocumentSourceValidator()
    document_stream_provider = LocalDocumentStreamProvider()
    document_loader = LocalDocumentLoader()
    document_chunker = RecursiveDocumentChunker(
        plan=ChunkingPlan(
            target_size=app_config.chunking.target_tokens,
            overlap_size=app_config.chunking.overlap_tokens if app_config.chunking.overlap_tokens is not None else 0,
            max_size=app_config.chunking.max_tokens if app_config.chunking.max_tokens is not None else 0,
        ),
    )
    staging_uow = SQLiteUnitOfWork(connection_factory=session_factory)
    llm_config = OpenAIConfig(api_key=env_config.openai_api_key, model=app_config.llm.model)
    llm_client = OpenAIClient(config=llm_config)
    pk_normalizer = DefaultPKNormalizer()

    # Common services
    extraction_executor = ConcurrentExtractionExecutor(
        llm_client=llm_client,
        max_concurrency=app_config.llm.max_concurrency,
    )
    batch_submitter = ConcurrentExtractionBatchSubmitter(llm_client=llm_client)

    # Entity extraction services
    entity_extraction_repository = EntityExtractionRepository(uow=staging_uow)
    entity_request_builder = EntityExtractionRequestBuilder(document_loader=document_loader)
    entity_result_materializer = EntityExtractionResultMaterializer(pk_normalizer=pk_normalizer)
    entity_metrics_tracker = EntityExtractionMetricsTracker(
        uow=staging_uow,
        execution_mode=app_config.llm.execution_mode,
    )

    # Assign the appropriate extraction engine based on the execution mode
    if app_config.llm.execution_mode == ExecutionMode.BATCH:
        entity_extraction_engine = BatchExtractionEngine(
            repository=entity_extraction_repository,
            request_builder=entity_request_builder,
            submitter=batch_submitter,
            metrics_tracker=entity_metrics_tracker,
        )
    else:
        entity_extraction_engine = RealtimeExtractionEngine(
            repository=entity_extraction_repository,
            request_builder=entity_request_builder,
            executor=extraction_executor,
            result_materializer=entity_result_materializer,
            metrics_tracker=entity_metrics_tracker,
        )

    # TODO: Relationship extraction services

    # Use cases
    get_document_registry = GetDocumentRegistry(
        provider=document_registry_provider,
        validator=document_source_validator,
    )
    get_graph_model = GetGraphModel(provider=graph_model_provider)
    ingest_documents = IngestDocuments(
        stream_provider=document_stream_provider,
        loader=document_loader,
        chunker=document_chunker,
        uow=staging_uow,
    )
    extract_entities = ExtractEntities(
        uow=staging_uow,
        extraction_engine=entity_extraction_engine,
        metrics_tracker=entity_metrics_tracker,
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
