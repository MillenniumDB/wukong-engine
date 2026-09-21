import logging
from pathlib import Path

from wukong_engine.app.config.exceptions import ConfigurationError
from wukong_engine.app.data_extraction.model.values import ExecutionMode
from wukong_engine.app.data_extraction.services import (
    BatchExtractionEngine,
    ConcurrentExtractionBatchSubmitter,
    ConcurrentExtractionBatchSynchronizer,
    ConcurrentExtractionExecutor,
    EntityExtractionRepository,
    EntityExtractionRequestBuilder,
    EntityExtractionResultMaterializer,
    ExtractionMetricsTracker,
    RealtimeExtractionEngine,
    RelationshipExtractionRepository,
    RelationshipExtractionRequestBuilder,
    RelationshipExtractionResultMaterializer,
)
from wukong_engine.app.data_extraction.use_cases import ExtractEntities, ExtractRelationships
from wukong_engine.app.document_ingestion.use_cases import IngestDocuments
from wukong_engine.app.knowledge_export.model.values import KnowledgeExportFormat
from wukong_engine.app.knowledge_export.ports import KnowledgeExporter
from wukong_engine.app.knowledge_export.services import KnowledgeRepository
from wukong_engine.app.knowledge_export.use_cases import ExportKnowledge
from wukong_engine.app.model_ingestion.use_cases import GetDocumentRegistry, GetKnowledgeModel
from wukong_engine.app.workflows import KnowledgeConstructionPipeline
from wukong_engine.app.workspace import Workspace
from wukong_engine.infrastructure.chunking import ChunkingPlan, RecursiveDocumentChunker
from wukong_engine.infrastructure.config import ConfigProvider, load_env_config
from wukong_engine.infrastructure.definitions.documents import LocalDocumentRegistryProvider
from wukong_engine.infrastructure.definitions.knowledge import LocalKnowledgeModelProvider
from wukong_engine.infrastructure.export.graph import MillenniumDBKnowledgeExporter, Neo4jKnowledgeExporter
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

    def __init__(self, knowledge_construction_pipeline: KnowledgeConstructionPipeline) -> None:
        """Initialize the CLI application, composing all dependencies."""
        self.knowledge_construction = knowledge_construction_pipeline


def _format_to_exporter(export_format: KnowledgeExportFormat, repository: KnowledgeRepository) -> KnowledgeExporter:
    """Map an export format to its corresponding KnowledgeExporter implementation."""
    match export_format:
        case KnowledgeExportFormat.MDB:
            return MillenniumDBKnowledgeExporter(repository)
        case KnowledgeExportFormat.NEO4J:
            return Neo4jKnowledgeExporter(repository)
        case _:
            raise ValueError(f'Unsupported export format: {export_format}')


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
    knowledge_model_provider = LocalKnowledgeModelProvider()
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
    knowledge_repository = KnowledgeRepository(uow=staging_uow)
    knowledge_exporter = _format_to_exporter(app_config.export.format, knowledge_repository)

    # Common services
    extraction_executor = ConcurrentExtractionExecutor(
        llm_client=llm_client,
        max_concurrency=app_config.llm.max_concurrency,
    )
    batch_submitter = ConcurrentExtractionBatchSubmitter(llm_client=llm_client)

    # Entity extraction services
    entity_extraction_repository = EntityExtractionRepository(uow=staging_uow)
    entity_metrics_tracker = ExtractionMetricsTracker(
        repository=entity_extraction_repository,
        execution_mode=app_config.llm.execution_mode,
    )
    entity_request_builder = EntityExtractionRequestBuilder(
        repository=entity_extraction_repository,
        document_loader=document_loader,
    )
    entity_result_materializer = EntityExtractionResultMaterializer(
        repository=entity_extraction_repository,
        pk_normalizer=pk_normalizer,
    )
    entity_batch_synchronizer = ConcurrentExtractionBatchSynchronizer(
        repository=entity_extraction_repository,
        llm_client=llm_client,
        result_materializer=entity_result_materializer,
        metrics_tracker=entity_metrics_tracker,
    )

    # Assign the appropriate entity extraction engine based on the execution mode
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

    # Relationship extraction services
    relationship_extraction_repository = RelationshipExtractionRepository(uow=staging_uow)
    relationship_metrics_tracker = ExtractionMetricsTracker(
        repository=relationship_extraction_repository,
        execution_mode=app_config.llm.execution_mode,
    )
    relationship_request_builder = RelationshipExtractionRequestBuilder(repository=relationship_extraction_repository)
    relationship_result_materializer = RelationshipExtractionResultMaterializer(
        repository=relationship_extraction_repository,
        pk_normalizer=pk_normalizer,
    )
    relationship_batch_synchronizer = ConcurrentExtractionBatchSynchronizer(
        repository=relationship_extraction_repository,
        llm_client=llm_client,
        result_materializer=relationship_result_materializer,
        metrics_tracker=relationship_metrics_tracker,
    )

    # Assign the appropriate relationship extraction engine based on the execution mode
    if app_config.llm.execution_mode == ExecutionMode.BATCH:
        relationship_extraction_engine = BatchExtractionEngine(
            repository=relationship_extraction_repository,
            request_builder=relationship_request_builder,
            submitter=batch_submitter,
            metrics_tracker=relationship_metrics_tracker,
        )
    else:
        relationship_extraction_engine = RealtimeExtractionEngine(
            repository=relationship_extraction_repository,
            request_builder=relationship_request_builder,
            executor=extraction_executor,
            result_materializer=relationship_result_materializer,
            metrics_tracker=relationship_metrics_tracker,
        )

    # Use cases
    get_document_registry = GetDocumentRegistry(
        provider=document_registry_provider,
        validator=document_source_validator,
    )
    get_knowledge_model = GetKnowledgeModel(provider=knowledge_model_provider)
    ingest_documents = IngestDocuments(
        stream_provider=document_stream_provider,
        loader=document_loader,
        chunker=document_chunker,
        uow=staging_uow,
    )
    extract_entities = ExtractEntities(
        uow=staging_uow,
        repository=entity_extraction_repository,
        extraction_engine=entity_extraction_engine,
        batch_synchronizer=entity_batch_synchronizer,
        metrics_tracker=entity_metrics_tracker,
    )
    extract_relationships = ExtractRelationships(
        uow=staging_uow,
        repository=relationship_extraction_repository,
        extraction_engine=relationship_extraction_engine,
        batch_synchronizer=relationship_batch_synchronizer,
        metrics_tracker=relationship_metrics_tracker,
    )
    export_knowledge = ExportKnowledge(
        uow=staging_uow,
        exporter=knowledge_exporter,
        export_uri=str(workspace.paths.exports),
    )

    # Workflows
    knowledge_construction = KnowledgeConstructionPipeline(
        app_config=app_config,
        uow=staging_uow,
        get_document_registry=get_document_registry,
        get_knowledge_model=get_knowledge_model,
        ingest_documents=ingest_documents,
        extract_entities=extract_entities,
        extract_relationships=extract_relationships,
        export_knowledge=export_knowledge,
    )
    return CLIApplication(knowledge_construction_pipeline=knowledge_construction)
