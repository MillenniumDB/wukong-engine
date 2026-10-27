"""Composition root that wires the CLI application together."""

import logging
from functools import partial
from pathlib import Path

from wukong_engine.app.config import ApplicationConfig
from wukong_engine.app.config.chunking import ChunkingConfig
from wukong_engine.app.config.exceptions import ConfigurationError
from wukong_engine.app.data_extraction.model.values import ExecutionMode
from wukong_engine.app.data_extraction.services import (
    BatchExtractionEngine,
    ConcurrentExtractionBatchCanceller,
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
from wukong_engine.app.data_extraction.use_cases import ExtractEntities, ExtractRelationships, ResetExtraction
from wukong_engine.app.document_ingestion.use_cases import IngestDocuments, ResetDocumentIngestion
from wukong_engine.app.knowledge_export.model.values import KnowledgeExportFormat
from wukong_engine.app.knowledge_export.ports import KnowledgeExporter
from wukong_engine.app.knowledge_export.services import KnowledgeRepository
from wukong_engine.app.knowledge_export.use_cases import ExportKnowledge, ResetKnowledgeExport
from wukong_engine.app.llm.elements import LLMClientFactory
from wukong_engine.app.model_ingestion.use_cases import GetDocumentRegistry, GetKnowledgeModel
from wukong_engine.app.staging.ports import UnitOfWork
from wukong_engine.app.workflows import GetPipelineStatus, KnowledgeConstructionPipeline, ResetPipeline
from wukong_engine.app.workspace import Workspace
from wukong_engine.core.extraction.model.values import ExtractionTask
from wukong_engine.infrastructure.chunking import ChunkingPlan, RecursiveDocumentChunker
from wukong_engine.infrastructure.chunking.tokenization import HuggingFaceTokenizer, TextTokenizer
from wukong_engine.infrastructure.config import ConfigProvider
from wukong_engine.infrastructure.definitions.documents import LocalDocumentRegistryProvider
from wukong_engine.infrastructure.definitions.knowledge import LocalKnowledgeModelProvider
from wukong_engine.infrastructure.export.graph import MillenniumDBKnowledgeExporter, Neo4jKnowledgeExporter
from wukong_engine.infrastructure.llm.factory import EnvLLMClientFactory
from wukong_engine.infrastructure.logging import set_logger_verbosity
from wukong_engine.infrastructure.normalization.primary_key import DefaultPKNormalizer
from wukong_engine.infrastructure.persistence.sqlite import (
    SQLiteSessionFactory,
    SQLiteUnitOfWork,
    initialize_sqlite_database,
)
from wukong_engine.infrastructure.storage.filesystem import LocalExportCleaner, LocalInputSnapshotStore
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

    Attributes:
        config: Application configuration the workflows were built with.
        knowledge_construction: Fully wired knowledge construction pipeline.
        reset_pipeline: Fully wired workflow resetting the results of the pipeline steps.
    """

    def __init__(
        self,
        config: ApplicationConfig,
        knowledge_construction_pipeline: KnowledgeConstructionPipeline,
        reset_pipeline: ResetPipeline,
    ) -> None:
        """Initialize the CLI application with its already composed workflows.

        Args:
            config: Application configuration the workflows were built with.
            knowledge_construction_pipeline: Fully wired knowledge construction pipeline.
            reset_pipeline: Fully wired workflow resetting the results of the pipeline steps.
        """
        self.config = config
        self.knowledge_construction = knowledge_construction_pipeline
        self.reset_pipeline = reset_pipeline


def _format_to_exporter(export_format: KnowledgeExportFormat, repository: KnowledgeRepository) -> KnowledgeExporter:
    """Map an export format to its corresponding KnowledgeExporter implementation.

    Args:
        export_format: Configured export format.
        repository: Repository the exporter reads the staged knowledge from.

    Returns:
        The exporter for the given format.

    Raises:
        ValueError: If the export format is not supported.
    """
    match export_format:
        case KnowledgeExportFormat.MDB:
            return MillenniumDBKnowledgeExporter(repository)
        case KnowledgeExportFormat.NEO4J:
            return Neo4jKnowledgeExporter(repository)
        case _:
            raise ValueError(f'Unsupported export format: {export_format}')


def _build_document_chunker(chunking: ChunkingConfig, tokenizer: TextTokenizer) -> RecursiveDocumentChunker:
    """Build the document chunker for given chunking settings.

    Args:
        chunking: Chunking settings, with their derived token budgets resolved.
        tokenizer: Tokenizer measuring chunk sizes, shared across chunkers so it's only loaded once.

    Returns:
        The chunker splitting documents according to the settings.
    """
    return RecursiveDocumentChunker(
        plan=ChunkingPlan(
            target_size=chunking.target_tokens,
            overlap_size=chunking.overlap_tokens if chunking.overlap_tokens is not None else 0,
            max_size=chunking.max_tokens if chunking.max_tokens is not None else 0,
            tokenizer=tokenizer,
        ),
    )


def _build_reset_pipeline(
    workspace: Workspace,
    staging_uow: UnitOfWork,
    llm_client_factory: LLMClientFactory,
) -> ResetPipeline:
    """Build the workflow resetting the results of the pipeline steps, which needs no configuration.

    Args:
        workspace: Workspace whose input snapshots and export directory are reset.
        staging_uow: Unit of work over the workspace's staging database.
        llm_client_factory: Factory of the LLM client of each provider, used to cancel the batches still active there.

    Returns:
        The workflow resetting the pipeline steps.
    """
    entity_extraction_repository = EntityExtractionRepository(uow=staging_uow)
    relationship_extraction_repository = RelationshipExtractionRepository(uow=staging_uow)
    return ResetPipeline(
        uow=staging_uow,
        input_snapshots=LocalInputSnapshotStore(directory=workspace.paths.snapshots),
        reset_document_ingestion=ResetDocumentIngestion(uow=staging_uow),
        reset_entity_extraction=ResetExtraction(
            task=ExtractionTask.ENTITY_EXTRACTION,
            repository=entity_extraction_repository,
            batch_canceller=ConcurrentExtractionBatchCanceller(entity_extraction_repository, llm_client_factory),
        ),
        reset_relationship_extraction=ResetExtraction(
            task=ExtractionTask.RELATIONSHIP_EXTRACTION,
            repository=relationship_extraction_repository,
            batch_canceller=ConcurrentExtractionBatchCanceller(relationship_extraction_repository, llm_client_factory),
        ),
        reset_knowledge_export=ResetKnowledgeExport(
            cleaner=LocalExportCleaner(),
            export_uri=str(workspace.paths.exports),
        ),
    )


def build_application(workspace: Workspace, config_path: Path, verbosity: int) -> CLIApplication:
    """Build the CLI application.

    Sets the logging verbosity, loads the configuration, initializes the staging database and wires every service,
    use case and workflow.

    Args:
        workspace: Workspace whose staging database and export directory are used.
        config_path: Path to the TOML configuration file.
        verbosity: Logging verbosity level (0 for WARNING, 1 for INFO, 2 or more for DEBUG).

    Returns:
        The composed CLI application.

    Raises:
        ConfigurationError: If the verbosity, environment or configuration file cannot be loaded, or the LLM client
            cannot be configured for the model.
    """
    # Configuration
    try:
        set_logger_verbosity(verbosity)
        app_config = ConfigProvider().get(config_path)
        llm_client_factory = EnvLLMClientFactory(model=app_config.llm.model)
        llm_client = llm_client_factory.get_client(app_config.llm.model.provider)
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
    input_snapshots = LocalInputSnapshotStore(directory=workspace.paths.snapshots)
    staging_uow = SQLiteUnitOfWork(connection_factory=session_factory)
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
        reasoning_effort=app_config.llm.reasoning_effort,
    )
    entity_result_materializer = EntityExtractionResultMaterializer(
        repository=entity_extraction_repository,
        pk_normalizer=pk_normalizer,
    )
    entity_batch_synchronizer = ConcurrentExtractionBatchSynchronizer(
        repository=entity_extraction_repository,
        llm_client_factory=llm_client_factory,
        batch_canceller=ConcurrentExtractionBatchCanceller(entity_extraction_repository, llm_client_factory),
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
    relationship_request_builder = RelationshipExtractionRequestBuilder(
        repository=relationship_extraction_repository,
        reasoning_effort=app_config.llm.reasoning_effort,
    )
    relationship_result_materializer = RelationshipExtractionResultMaterializer(
        repository=relationship_extraction_repository,
        pk_normalizer=pk_normalizer,
    )
    relationship_batch_synchronizer = ConcurrentExtractionBatchSynchronizer(
        repository=relationship_extraction_repository,
        llm_client_factory=llm_client_factory,
        batch_canceller=ConcurrentExtractionBatchCanceller(relationship_extraction_repository, llm_client_factory),
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
        chunker_factory=partial(_build_document_chunker, tokenizer=HuggingFaceTokenizer()),
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
    reset_pipeline = _build_reset_pipeline(workspace, staging_uow, llm_client_factory)
    knowledge_construction = KnowledgeConstructionPipeline(
        app_config=app_config,
        uow=staging_uow,
        input_snapshots=input_snapshots,
        get_document_registry=get_document_registry,
        get_knowledge_model=get_knowledge_model,
        ingest_documents=ingest_documents,
        extract_entities=extract_entities,
        extract_relationships=extract_relationships,
        export_knowledge=export_knowledge,
        reset_pipeline=reset_pipeline,
    )
    return CLIApplication(
        config=app_config,
        knowledge_construction_pipeline=knowledge_construction,
        reset_pipeline=reset_pipeline,
    )


def build_reset_pipeline(workspace: Workspace, verbosity: int) -> ResetPipeline:
    """Build the workflow resetting the results of the pipeline steps, which needs no configuration.

    The API key of each provider is read from the environment only when one of its batches is cancelled, so a missing
    key only fails the cancellation of that provider's batches, which is logged.

    Args:
        workspace: Workspace whose staging database, input snapshots and export directory are reset.
        verbosity: Logging verbosity level (0 for WARNING, 1 for INFO, 2 or more for DEBUG).

    Returns:
        The workflow resetting the pipeline steps.
    """
    set_logger_verbosity(verbosity)
    session_factory = SQLiteSessionFactory(db_path=workspace.paths.staging_db)
    initialize_sqlite_database(db_path=workspace.paths.staging_db, connection_factory=session_factory)
    return _build_reset_pipeline(
        workspace,
        SQLiteUnitOfWork(connection_factory=session_factory),
        EnvLLMClientFactory(),
    )


def build_pipeline_status(workspace: Workspace) -> GetPipelineStatus:
    """Build the use case reading the pipeline status of a workspace, which needs no configuration or API key.

    Args:
        workspace: Workspace whose staging database is read; it is created if missing, like on a run.

    Returns:
        The use case reading the pipeline status.
    """
    session_factory = SQLiteSessionFactory(db_path=workspace.paths.staging_db)
    initialize_sqlite_database(db_path=workspace.paths.staging_db, connection_factory=session_factory)
    staging_uow = SQLiteUnitOfWork(connection_factory=session_factory)
    return GetPipelineStatus(
        uow=staging_uow,
        input_snapshots=LocalInputSnapshotStore(directory=workspace.paths.snapshots),
        entity_repository=EntityExtractionRepository(uow=staging_uow),
        relationship_repository=RelationshipExtractionRepository(uow=staging_uow),
    )
