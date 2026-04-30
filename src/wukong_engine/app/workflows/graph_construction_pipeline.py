"""Implements the engine pipeline.

This module provides functions to execute the complete engine pipeline,
extracting data from unstructured text documents, processing it,
and then exporting the results to various knowledge graph formats.

Functions:
    execute_pipeline: Runs the full engine pipeline over a given data directory.
"""

import logging

from wukong_engine.app.config import ApplicationConfig
from wukong_engine.app.data_extraction.use_cases import ExtractEntityType
from wukong_engine.app.document_ingestion.use_cases import IngestDocuments
from wukong_engine.app.model_ingestion.use_cases import GetDocumentRegistry, GetGraphModel
from wukong_engine.app.staging.ports import UnitOfWork
from wukong_engine.app.workspace import Workspace
from wukong_engine.core.pipeline.model.values import PipelineStep

"""
from wukong_engine.documents.text_processing import (
    generate_chunks,
    process_metadata_documents,
    process_text_documents,
    trim_large_documents,
)
"""
# from wukong_engine.extraction.entities import extract_entities, process_entities
# from wukong_engine.extraction.relations import extract_relations, process_relations
# from wukong_engine.graph.export import export_stats, export_to_json, export_to_mdb, export_to_neo4j
# from wukong_engine.llm.prompting import generate_prompts

# Logging
logger = logging.getLogger(__name__)


class GraphConstructionPipeline:
    """Pipeline to build a knowledge graph from unstructured documents."""

    def __init__(
        self,
        app_config: ApplicationConfig,
        uow: UnitOfWork,
        get_document_registry: GetDocumentRegistry,
        get_graph_model: GetGraphModel,
        ingest_documents: IngestDocuments,
        extract_entity_type: ExtractEntityType,
        # extract_relationships: ExtractRelationships,
        # export_graph: ExportGraph,
    ) -> None:
        """Initialize the graph construction workflow with its use cases."""
        self._app_config = app_config
        self._uow = uow
        self._get_document_registry = get_document_registry
        self._get_graph_model = get_graph_model
        self._ingest_documents = ingest_documents
        self._extract_entity_type = extract_entity_type
        # self._extract_relationships = extract_relationships
        # self._export_graph = export_graph

    def execute(self, workspace: Workspace, *, should_reset: bool = True) -> None:
        """Execute the WUKONG engine pipeline.

        Orchestrates the entire pipeline, which includes:

        1. Ingest documents
        2. Extract entities
        3. Extract relationships
        4. Export knowledge graph

        Args:
            workspace: The user workspace containing key files and directories for the pipeline execution.
            should_reset: If True, clears existing data on each pipeline step. If False, keeps existing data and appends any new results.

        Raises:
            FileNotFoundError: If any paths to necessary information (configuration/data/documents/results) do not exist.
            ValueError: If the configuration or graph model is invalid, or environment variables are missing.
            TypeError: If the graph model has invalid types for certain fields.
        """
        # Get document registry and validate document sources
        document_registry = self._get_document_registry.execute(str(workspace.paths.document_registry))
        logger.info(
            f'Document collections obtained successfully from "{workspace.paths.document_registry}"\n\n{document_registry}',
        )

        # Get graph model and validate selected document collections
        graph_model = self._get_graph_model.execute(str(workspace.paths.graph_model))
        unique_collections = set()
        for entity_type in graph_model.entity_types.values():
            for collections in entity_type.document_collections.values():
                unique_collections.update(collections)
        document_registry.validate_collections(frozenset(unique_collections))
        logger.info(f'Graph model obtained successfully from "{workspace.paths.graph_model}"\n\n{graph_model}')

        # Document ingestion
        if self._app_config.pipeline.is_active(PipelineStep.INGEST_DOCUMENTS):
            if should_reset:
                with self._uow as tx:
                    tx.documents.clear()
                    # TODO: Clear downstream steps
                    # tx.entities.clear()
                    # tx.relationships.clear()
                    # tx.extraction.clear()
                logger.warning('Removing existing documents...')
            logger.info('Starting document ingestion...')
            self._ingest_documents.execute(document_registry)
            logger.info('Document ingestion completed successfully!')
        return

        # TODO: Entity extraction
        # TODO: If should_reset is True, clear all existing entities before this step
        if self._app_config.pipeline.is_active(PipelineStep.EXTRACT_ENTITIES):
            for entity_type in graph_model.active_entity_types.values():
                logger.info(f'Extracting entities for EntityType "{entity_type.name}"')
                self._extract_entity_type.execute(entity_type, document_registry)
                break

        # TODO: Pipeline
        # TODO: Relationship extraction
        # TODO: If should_reset is True, clear all existing relationships before this step
        """
        # Process input documents
        if document_processing:
            logger.info('Processing Input Documents...')
            process_text_documents(original_docs_dir, docs_dir, results_dir)
            generate_chunks(docs_dir, chunks_dir, results_dir)
            trim_large_documents(docs_dir)
            if original_metadata_dir.exists():
                process_metadata_documents(original_metadata_dir, metadata_dir, results_dir)

        # Generate prompts from graph model
        if prompt_generation:
            logger.info('Generating Prompts...')
            generate_prompts(prompts_dir)

        # Extract entities from the documents
        if entity_extraction:
            logger.info('Extracting Core Entities...')
            extract_entities(
                graph_model.core_entities,
                docs_dir,
                prompts_dir,
                results_dir,
                metadata_dir=metadata_dir,
                clear_results=True,
            )
            logger.info('Extracting Entities...')
            extract_entities(graph_model.hybrid_entities + graph_model.entities, chunks_dir, prompts_dir, results_dir)

        # Process extracted entities
        if entity_processing:
            logger.info('Processing Entities...')
            process_entities(graph_model.core_entities + graph_model.hybrid_entities + graph_model.entities, results_dir)

        # Extract relations from the documents
        if relation_extraction:
            logger.info('Extracting Relations...')
            extract_relations(graph_model.materialized_relations, chunks_dir, prompts_dir, results_dir, clear_results=True)

        # Process extracted relations
        if relation_processing:
            logger.info('Processing Relations...')
            process_relations(graph_model.materialized_relations, results_dir)

        # Export Knowledge Graph to various formats
        if export_graph:
            export_formats = config.get('export_formats', ['mdb'])
            if 'mdb' in export_formats:
                logger.info('Exporting Knowledge Graph to MillenniumDB...')
                export_to_mdb(results_dir, exports_dir / 'mdb')
            if 'neo4j' in export_formats:
                logger.info('Exporting Knowledge Graph to Neo4j...')
                export_to_neo4j(results_dir, exports_dir / 'neo4j')
            if 'json' in export_formats:
                logger.info('Exporting Knowledge Graph to JSON...')
                export_to_json(results_dir, exports_dir / 'json')
            export_stats(results_dir, exports_dir)
        """
