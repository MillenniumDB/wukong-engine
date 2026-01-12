"""Implements the engine pipeline.

This module provides functions to execute the complete engine pipeline,
extracting data from unstructured text documents, processing it,
and then exporting the results to various knowledge graph formats.

Functions:
    execute_pipeline: Runs the full engine pipeline over a given data directory.
"""

import logging
from pathlib import Path

from nltk import download as nltk_download
from wukong_engine.config.config import Config
from wukong_engine.documents.text_processing import (
    generate_chunks,
    process_metadata_documents,
    process_text_documents,
    trim_large_documents,
)
from wukong_engine.extraction.entities import extract_entities, process_entities
from wukong_engine.extraction.relations import extract_relations, process_relations
from wukong_engine.graph.export import export_stats, export_to_json, export_to_mdb, export_to_neo4j
from wukong_engine.llm.prompting import generate_prompts

from .data_model import DataModel

# Logging
logger = logging.getLogger(__name__)

# Load NLTK data for NLP
nltk_download('stopwords', quiet=True)

# Paths
ORIGINAL_DOCS_DIR = Path('./docs/text/')
ORIGINAL_METADATA_DIR = Path('./docs/metadata/')
DOCS_DIR = Path('./docs/processed/full/')
CHUNKS_DIR = Path('./docs/processed/chunks/')
METADATA_DIR = Path('./docs/processed/metadata/')
PROMPTS_DIR = Path('./prompts/')
RESULTS_DIR = Path('./results/')
EXPORTS_DIR = Path('./exports/')


def execute_pipeline(data_dir: Path, config_path: Path) -> None:
    """Execute the WUKONG engine pipeline.

    Orchestrates the entire pipeline, which includes:

    1. Document processing
    2. Entity extraction
    3. Relation extraction
    4. Knowledge graph export

    Args:
        data_dir: The path to the data directory containing the documents and data model.
        config_path: The path to the engine configuration file.

    Raises:
        FileNotFoundError: If any paths to necessary information (configuration/data/documents/results) do not exist.
        ValueError: If the configuration or data model is invalid, or environment variables are missing.
        TypeError: If the data model has invalid types for certain fields.
    """
    # Define relevant paths
    original_docs_dir = data_dir / ORIGINAL_DOCS_DIR
    original_metadata_dir = data_dir / ORIGINAL_METADATA_DIR
    docs_dir = data_dir / DOCS_DIR
    chunks_dir = data_dir / CHUNKS_DIR
    metadata_dir = data_dir / METADATA_DIR
    prompts_dir = data_dir / PROMPTS_DIR
    results_dir = data_dir / RESULTS_DIR
    exports_dir = data_dir / EXPORTS_DIR

    # Get configuration
    config = Config(config_path)

    # Get data model
    data_model = DataModel(data_dir=data_dir)

    # Pipeline configuration

    # Document processing
    document_processing = config.is_enabled('document_processing')

    # Data extraction
    entity_extraction = config.is_enabled('entity_extraction')
    entity_processing = config.is_enabled('entity_extraction')
    relation_extraction = config.is_enabled('relation_extraction')
    relation_processing = config.is_enabled('relation_extraction')
    prompt_generation = entity_extraction or relation_extraction

    # Knowledge graph export
    export_graph = config.is_enabled('export_graph')

    # Pipeline execution
    logger.info('Executing WUKONG Engine Pipeline...')

    # Process input documents
    if document_processing:
        logger.info('Processing Input Documents...')
        process_text_documents(original_docs_dir, docs_dir, results_dir)
        generate_chunks(docs_dir, chunks_dir, results_dir)
        trim_large_documents(docs_dir)
        if original_metadata_dir.exists():
            process_metadata_documents(original_metadata_dir, metadata_dir, results_dir)

    # Generate prompts from data model
    if prompt_generation:
        logger.info('Generating Prompts...')
        generate_prompts(prompts_dir)

    # Extract entities from the documents
    if entity_extraction:
        logger.info('Extracting Core Entities...')
        extract_entities(
            data_model.core_entities,
            docs_dir,
            prompts_dir,
            results_dir,
            metadata_dir=metadata_dir,
            clear_results=True,
        )
        logger.info('Extracting Entities...')
        extract_entities(data_model.hybrid_entities + data_model.entities, chunks_dir, prompts_dir, results_dir)

    # Process extracted entities
    if entity_processing:
        logger.info('Processing Entities...')
        process_entities(data_model.core_entities + data_model.hybrid_entities + data_model.entities, results_dir)

    # Extract relations from the documents
    if relation_extraction:
        logger.info('Extracting Relations...')
        extract_relations(data_model.materialized_relations, chunks_dir, prompts_dir, results_dir, clear_results=True)

    # Process extracted relations
    if relation_processing:
        logger.info('Processing Relations...')
        process_relations(data_model.materialized_relations, results_dir)

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

    # Final message
    logger.info('WUKONG Engine Pipeline Execution Completed!')
