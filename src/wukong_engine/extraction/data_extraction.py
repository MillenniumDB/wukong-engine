"""Implements data extraction from text documents.

This module defines functions to extract and process entities/relations
from unstructured text documents.
"""

import json
import logging
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from wukong_engine.config.config import Config
from wukong_engine.core.data_model import DataModel
from wukong_engine.llm.llm_client import process_prompt
from wukong_engine.utils.file_utils import delete_dir_contents, load_json_data, load_text_data, save_json_data

from .data_processing import (
    clean_entities,
    clean_relations,
    merge_duplicate_entities,
    merge_duplicate_relations,
    merge_hybrid_entities,
)

# Logging
logger = logging.getLogger(__name__)


def find_entities(
    entity_model: dict[str, Any],
    docs_dir: Path,
    prompts_dir: Path,
    results_dir: Path,
    *,
    metadata_dir: Path | None = None,
    clear_results: bool = False,
) -> None:
    """Find all entities contained in the input documents, in accordance with the given entity model.

    Gathers prompts for each entity type, processes them in parallel using LLMs,
    and saves the results in a structured manner.

    Args:
        entity_model: A dictionary containing entity types from the data model and their relevant information.
        docs_dir: The path to the directory containing the document sets.
        prompts_dir: The path to the directory containing the prompts for the LLM.
        results_dir: The path to the directory where the results are stored.
        metadata_dir: The path to the directory containing metadata files for the documents, if available.
        clear_results: Whether to clear the partial results directory before starting the procedure.
    """
    # Path to partial entity results
    partial_results_dir = results_dir / 'partials/'
    partial_results_dir.mkdir(parents=True, exist_ok=True)
    if clear_results:
        delete_dir_contents(partial_results_dir)
    partial_entities_dir = partial_results_dir / 'entities/'
    partial_entities_dir.mkdir(parents=True, exist_ok=True)

    # Get the data model
    data_model = DataModel()

    # Extract info for each entity type
    for entity_name in entity_model:
        partial_entity_dir = partial_entities_dir / entity_name
        partial_entity_dir.mkdir(parents=True, exist_ok=True)

        # Get prompts and process them with the LLM
        if data_model.get_entity_data(entity_name):
            prompt_data = get_entity_prompts(entity_name, docs_dir, prompts_dir)

            # Execute the LLM prompt processing in parallel, since API calls are slow
            with ThreadPoolExecutor(max_workers=Config().get('max_worker_threads', None)) as executor:
                futures = [executor.submit(process_prompt, prompt_info) for prompt_info in prompt_data]
                for future in as_completed(futures):
                    try:
                        results = future.result()  # Wait for the API call to complete
                        process_extracted_entities(
                            results,
                            entity_model,
                            partial_entities_dir,
                        )  # Process the partial results
                    except Exception:
                        logger.exception('An unexpected error occurred during entity extraction.')

        # Load metadata if available
        if data_model.get_entity_metadata(entity_name) and metadata_dir:
            load_entity_metadata(entity_name, metadata_dir, docs_dir, partial_entities_dir)


def find_relations(
    relation_model: dict[str, Any],
    docs_dir: Path,
    prompts_dir: Path,
    results_dir: Path,
    *,
    clear_results: bool = False,
) -> None:
    """Find all relations contained in the input documents, in accordance with the given relation model.

    Gathers prompts for each relation type, processes them in parallel using LLMs (unless bypassed),
    and saves the results in a structured manner.

    Args:
        relation_model: A dictionary containing relation types from the data model and their relevant information.
        docs_dir: The path to the directory containing the document sets.
        prompts_dir: The path to the directory containing the prompts for the LLM.
        results_dir: The path to the directory where the results are stored.
        clear_results: Whether to clear the partial results directory before starting the procedure.
    """
    # Path to partial relation results
    partial_relations_dir = results_dir / 'partials/relations/'
    partial_relations_dir.mkdir(parents=True, exist_ok=True)
    if clear_results:
        delete_dir_contents(partial_relations_dir)

    # Extract info for each relation type
    for relation_name, relation_info in relation_model.items():
        partial_relation_dir = partial_relations_dir / relation_name
        partial_relation_dir.mkdir(parents=True, exist_ok=True)

        # Process relation without the LLM (only available when one of the entities is a core entity)
        core_entity_relation = relation_info.get('core_origin', False) or relation_info.get('core_target', False)
        if core_entity_relation and relation_info.get('bypass_LLM', False):
            for results in bypass_ai_processing(relation_name, relation_info, docs_dir, results_dir):
                process_extracted_relations(results, relation_model, partial_relations_dir)
            continue

        # Process relation with the LLM
        prompt_data = get_relation_prompts(relation_name, relation_info, docs_dir, prompts_dir, results_dir)

        # Execute the LLM prompt processing in parallel, since API calls are slow
        with ThreadPoolExecutor(max_workers=Config().get('max_worker_threads', None)) as executor:
            futures = [executor.submit(process_prompt, prompt_info) for prompt_info in prompt_data]
            for future in as_completed(futures):
                try:
                    results = future.result()  # Wait for the API call to complete
                    process_extracted_relations(
                        results,
                        relation_model,
                        partial_relations_dir,
                    )  # Process the partial results
                except Exception:
                    logger.exception('An unexpected error occurred during relation extraction.')


def process_entities(entity_model: dict[str, Any], results_dir: Path) -> None:
    """Process extracted entities to merge duplicates and remove invalid objects, saving the final results.

    Consolidates the results of entity extraction, cleans the entities, merges duplicates,
    and saves the final entities into a single file for each entity type.

    Args:
        entity_model: A dictionary containing entity types from the data model and their relevant information.
        results_dir: The path to the directory where the results are stored.

    Raises:
        FileNotFoundError: If the necessary result directories do not exist,
            indicating that the initial entity extraction process was not completed successfully or has not been run yet.
    """
    # Paths to partial and final results
    partial_entities_dir = results_dir / 'partials/entities/'
    entities_dir = results_dir / 'entities/'
    delete_dir_contents(entities_dir, items_to_keep=['Document.json', 'Chunk.json'])
    relations_dir = results_dir / 'relations/'
    delete_dir_contents(relations_dir, items_to_keep=['ChunkOf.json'])

    # If the result directories do not exist, abort the process
    required_paths = (partial_entities_dir, entities_dir, relations_dir)
    if not all(required_path.exists() for required_path in required_paths):
        raise FileNotFoundError(
            'Entity Processing failed. Some necessary files are missing. Please run the program again including the previous steps.',
        )

    # Initialize the document references file
    references_path = relations_dir / 'ExtractedFrom.json'
    save_json_data([], references_path)

    # Iterate over all entity types and consolidate their results
    for entity_name, entity_info in entity_model.items():
        # If the partial entity results directory does not exist, skip this entity type
        entity_results_dir = partial_entities_dir / entity_name
        if not entity_results_dir.exists():
            logger.error(f'Entity processing failed. No partial results found for entity type "{entity_name}".')
            continue

        # Gather all entities found in the documents
        entities = []
        entity_results_paths = [
            results_path
            for results_path in entity_results_dir.iterdir()
            if results_path.is_file() and results_path.suffix == '.json'
        ]
        for entity_results_path in entity_results_paths:
            results = load_json_data(entity_results_path)
            entities.extend(results)

        # Clean entities and remove invalid ones
        entities = clean_entities(entities, entity_name, entity_info)

        # Merge duplicate entities
        entities = merge_duplicate_entities(entities, entity_name, entity_info)

        # Create global ID mapping for entities
        entity_mapping, object_mapping = build_global_entity_mapping(
            entities,
            entity_name,
            core_entity=entity_info.get('core_entity', False),
        )

        # Create relations between final entities and their source documents (skip hybrid entities)
        if not entity_name.startswith('@'):
            build_entity_references(entities, references_path, core_entity=entity_info.get('core_entity', False))

        # Save all final entities into a single file
        entities_path = entities_dir / f'{entity_name}.json'
        save_json_data(entities, entities_path)

        # Iterate over all partial entities and update them with values from the final entities
        for entity_results_path in entity_results_paths:
            # Remove invalid partial entities
            results = [
                result for result in load_json_data(entity_results_path) if result['_ReferenceIds'][0] in entity_mapping
            ]

            # Update values for valid partial entities
            for result in results:
                temp_id = result['_ReferenceIds'][0]  # Partial entities should have exactly one ReferenceId here
                result['_ObjectId'] = entity_mapping[temp_id]  # Apply mapping from ReferenceId to ObjectId
            results = list({result['_ObjectId']: result for result in results}.values())  # Remove duplicates
            results.sort(key=lambda result: result['_ObjectId'])
            update_partial_entities(results, entities, object_mapping)  # Update with values from the final entities
            save_json_data(results, entity_results_path)

    # Process hybrid entities
    process_hybrid_entities(results_dir)


def process_relations(relation_model: dict[str, Any], results_dir: Path) -> None:
    """Process extracted relations to merge duplicates and remove invalid objects, saving the final results.

    Consolidates the results of relation extraction, cleans the relations, merges duplicates,
    and saves the final relations into a single file for each relation type.

    Args:
        relation_model: A dictionary containing relation types from the data model and their relevant information.
        results_dir: The path to the directory where the results are stored.

    Raises:
        FileNotFoundError: If the necessary result directories do not exist,
            indicating that either the entity processing step or the initial relation extraction process was not completed successfully or has not been run yet.
    """
    # Paths to partial and final results
    partial_relations_dir = results_dir / 'partials/relations/'
    relations_dir = results_dir / 'relations/'
    delete_dir_contents(relations_dir, items_to_keep=['ChunkOf.json', 'ExtractedFrom.json'])

    # If the result directories do not exist, abort the process
    required_paths = (partial_relations_dir, relations_dir)
    if not all(required_path.exists() for required_path in required_paths):
        raise FileNotFoundError(
            'Relation Processing failed. Some necessary files are missing. Please run the program again including the previous steps.',
        )

    # Initialize the final relations file for each relation type
    relation_names = {relation_info['relation_name'] for relation_info in relation_model.values()}
    for relation_name in relation_names:
        relations_path = relations_dir / f'{relation_name}.json'
        save_json_data([], relations_path)

    # Iterate over all relation types and consolidate their results
    for materialized_relation_name, relation_info in relation_model.items():
        # If the partial relation results directory does not exist, skip this relation type
        relation_results_dir = partial_relations_dir / materialized_relation_name
        if not relation_results_dir.exists():
            logger.error(
                f'Relation processing failed. No partial results found for relation type "{materialized_relation_name}".',
            )
            continue

        # Gather all relations found in the documents
        relations = []
        relation_results_paths = [
            results_path
            for results_path in relation_results_dir.iterdir()
            if results_path.is_file() and results_path.suffix == '.json'
        ]
        for relation_results_path in relation_results_paths:
            results = load_json_data(relation_results_path)
            relations.extend(results)

        # Clean relations and remove invalid ones
        relations = clean_relations(relations, relation_info['relation_name'], relation_info)

        # Merge duplicate relations
        relations = merge_duplicate_relations(relations, relation_info['relation_name'], relation_info)

        # Store reference between final relations and their source documents
        build_relation_references(relations)

        # Save all final relations into a single file, appending materialized relation data
        general_relations = []
        relations_path = relations_dir / f'{relation_info["relation_name"]}.json'
        stored_relations = load_json_data(relations_path)
        general_relations.extend(stored_relations)
        general_relations.extend(relations)
        save_json_data(general_relations, relations_path)

    # Process relations that contain hybrid entities
    process_hybrid_relations(results_dir)


def get_entity_prompts(entity_name: str, docs_dir: Path, prompts_dir: Path) -> list[dict[str, Any]]:
    """Generate a list of dictionaries containing the prompt data for the given entity type and documents.

    Args:
        entity_name: The name of the entity type to process.
        docs_dir: The path to the directory containing the document sets.
        prompts_dir: The path to the directory containing the prompts for the LLM.

    Returns:
        A list of dictionaries, each containing the prompt data necessary for extracting
        the given entity type from a specific document.
    """
    # Get the prompt for this entity type
    prompt_path = prompts_dir / f'entities/{entity_name}.txt'
    prompt = load_text_data(prompt_path)

    # If the prompt or documents are not found, discard this entity type
    if prompt is None or not docs_dir.exists():
        logger.error(f'Entity extraction failed. No prompt or documents found for entity type "{entity_name}".')
        return []

    # Prepare prompt data for each document, gathering documents from all sets
    document_paths = []
    prompt_data = []
    for document_set in sorted(DataModel().get_entity_sets(entity_name)):
        set_dir = docs_dir / document_set

        # If the document set directory does not exist, abort the process
        if not set_dir.exists():
            raise FileNotFoundError(
                f'Entity extraction failed. The directory for the document set "{document_set}" does not exist at path "{set_dir}".',
            )

        # Gather plain text files for this set
        document_paths = sorted(
            [doc_path for doc_path in set_dir.iterdir() if doc_path.is_file() and doc_path.suffix == '.txt'],
        )

        # Prepare prompt data for each document
        for document_path in document_paths:
            # Document to analyze
            document_name = document_path.stem
            document = load_text_data(document_path)

            # LLM Prompt Information
            prompt_data.append(
                {
                    'document_name': document_name,
                    'document_set': document_set,
                    'object_name': entity_name,
                    'user_role': document,
                    'system_role': prompt,
                },
            )

    return prompt_data


def process_extracted_entities(
    results: dict[str, Any],
    entity_model: dict[str, Any],
    partial_entities_dir: Path,
) -> None:
    """Process partial entities extracted by the LLM and save them to a partial results directory.

    Args:
        results: A dictionary containing the results of the LLM entity extraction process.
        entity_model: A dictionary containing entity types from the data model and their relevant information.
        partial_entities_dir: The path to the directory where the partial entities are stored.
    """
    # Get entity and document names
    entity_name = results['object_name']
    document_info = results['document_name'].split('_')

    # Core Entity: Single object
    if entity_model[entity_name].get('core_entity', False):
        core_entity = results['response']

        # Add ObjectId and single reference to document
        *_, document_id = document_info
        core_entity['_ObjectId'] = f'{entity_name}_{document_id}'
        core_entity['_ReferenceIds'] = [f'{document_id}']
        partial_entities = [core_entity]  # Convert to list for consistency
    else:  # Regular Entity: List of objects
        partial_entities = results['response']['results']

        # Make unique ID that references the document, chunk and object
        *_, document_id, chunk_id = document_info
        for idx, entity in enumerate(partial_entities, start=1):
            entity['_ReferenceIds'] = [f'{document_id}_{chunk_id}_{idx}']

    # Save entities to partial results file
    entity_results_dir = partial_entities_dir / entity_name
    results_file_path = entity_results_dir / f'{results["document_name"]}.json'
    save_json_data(partial_entities, results_file_path)


def load_entity_metadata(entity_name: str, metadata_dir: Path, docs_dir: Path, partial_entities_dir: Path) -> None:
    """Load metadata for a given entity type and save it to the partial results.

    Args:
        entity_name: The name of the entity type to load metadata for.
        metadata_dir: The path to the directory containing metadata files for the documents.
        docs_dir: The path to the directory containing the document sets.
        partial_entities_dir: The path to the directory where the partial entities are stored.

    Raises:
        FileNotFoundError: If the necessary document set directories do not exist.
    """
    # Gather documents from all sets
    data_model = DataModel()
    for document_set in sorted(data_model.get_entity_sets(entity_name)):
        set_dir = docs_dir / document_set

        # If the document set directory does not exist, abort the process
        if not set_dir.exists():
            raise FileNotFoundError(
                f'Entity extraction failed. The directory for the document set "{document_set}" does not exist at path "{set_dir}".',
            )

        # Gather plain text files for this set
        document_paths = sorted(
            [doc_path for doc_path in set_dir.iterdir() if doc_path.is_file() and doc_path.suffix == '.txt'],
        )

        # Extract metadata for each document
        for document_path in document_paths:
            document_name = document_path.stem
            full_document_name = f'{document_set}/{document_name}'
            logger.info(
                f'Processing metadata for type "{entity_name}" and document "{full_document_name}"',
            )

            # Load metadata file if it exists
            metadata_path = metadata_dir / document_set / f'{document_name}.json'
            if metadata_path.exists():
                metadata = load_json_data(metadata_path)
                if metadata is None or not isinstance(metadata, dict):
                    metadata = {}
                    logger.warning(f'Invalid metadata file at path "{metadata_path}". Filling with NULL values.')
            else:
                metadata = {}
                logger.warning(f'No metadata file found at path "{metadata_path}". Filling with NULL values.')

            # Add metadata values
            entity_data: dict[str, Any] = dict.fromkeys(data_model.get_entity_metadata(entity_name), 'NULL')
            entity_data.update({k: v for k, v in metadata.items() if k in entity_data})

            # Add ObjectId and single reference to document (core entity)
            *_, document_id = document_name.split('_')
            entity_data['_ObjectId'] = f'{entity_name}_{document_id}'
            entity_data['_ReferenceIds'] = [f'{document_id}']

            # Save entities to partial results file for the core entity
            entity_results_dir = partial_entities_dir / entity_name
            results_file_path = entity_results_dir / f'{document_name}.json'
            if results_file_path.exists():
                stored_data = load_json_data(results_file_path)[0]
                entity_data.update(stored_data)
            entity_result = [entity_data]  # Convert to list for consistency
            save_json_data(entity_result, results_file_path)


def get_relation_prompts(
    relation_name: str,
    relation_info: dict[str, Any],
    docs_dir: Path,
    prompts_dir: Path,
    results_dir: Path,
) -> list[dict[str, Any]]:
    """Generate a list of dictionaries containing the prompt data for the given relation type and documents.

    Args:
        relation_name: The name of the relation type to process.
        relation_info: A dictionary containing information about the relation type, following the data model specifications.
        docs_dir: The path to the directory containing the document sets.
        prompts_dir: The path to the directory containing the prompts for the LLM.
        results_dir: The path to the directory where the results are stored.

    Returns:
        A list of dictionaries, each containing the prompt data necessary for extracting
        the given relation type from a specific document.
    """
    # Get the prompt for this relation type
    prompt_path = prompts_dir / f'relations/{relation_name}.txt'
    prompt = load_text_data(prompt_path)

    # If the prompt or documents are not found, discard this relation type
    if prompt is None or not docs_dir.exists():
        logger.error(f'Relation extraction failed. No prompt or documents found for relation type "{relation_name}".')
        return []

    # Path to partial entity results
    partial_results_dir = results_dir / 'partials/'
    partial_entities_dir = partial_results_dir / 'entities/'

    # Path to partial results for this relation type
    relation_results_dir = partial_results_dir / 'relations' / relation_name

    # Prepare prompt data for each document, gathering documents from all sets
    document_paths = []
    prompt_data = []
    data_model = DataModel()
    origin_sets = data_model.get_entity_sets(relation_info['origin'])
    target_sets = data_model.get_entity_sets(relation_info['target'])
    for document_set in sorted(origin_sets & target_sets):
        set_dir = docs_dir / document_set

        # If the document set directory does not exist, abort the process
        if not set_dir.exists():
            raise FileNotFoundError(
                f'Entity extraction failed. The directory for the document set "{document_set}" does not exist at path "{set_dir}".',
            )

        # Gather plain text files for this set
        document_paths = sorted(
            [doc_path for doc_path in set_dir.iterdir() if doc_path.is_file() and doc_path.suffix == '.txt'],
        )

        # Prepare prompt data for each document
        for document_path in document_paths:
            # Path to partial results for this document
            document_name = document_path.stem
            results_file_path = relation_results_dir / f'{document_name}.json'

            # Load potential origin entities (if the origin is not a core entity)
            origin_entities = []
            if not relation_info.get('core_origin', False):
                # Only load partial entities if their processed version is available
                origin_entity_name = relation_info['origin'].removeprefix('@')
                final_origin_entities_path = results_dir / 'entities' / f'{origin_entity_name}.json'
                if not final_origin_entities_path.exists():
                    logger.error(
                        f'Relation extraction failed. No processed entities found for origin type "{origin_entity_name}".',
                    )
                    continue

                # Load partial origin entities for this document
                origin_entities_path = partial_entities_dir / relation_info['origin'] / f'{document_name}.json'
                origin_entities = load_json_data(origin_entities_path)
                if not origin_entities:
                    save_json_data([], results_file_path)
                    continue

            # Load potential target entities (if the target is not a core entity)
            target_entities = []
            if not relation_info.get('core_target', False):
                # Only load partial entities if their processed version is available
                target_entity_name = relation_info['target'].removeprefix('@')
                final_target_entities_path = results_dir / 'entities' / f'{target_entity_name}.json'
                if not final_target_entities_path.exists():
                    logger.error(
                        f'Relation extraction failed. No processed entities found for target type "{target_entity_name}".',
                    )
                    continue

                # Load partial target entities for this document
                target_entities_path = partial_entities_dir / relation_info['target'] / f'{document_name}.json'
                target_entities = load_json_data(target_entities_path)
                if not target_entities:
                    save_json_data([], results_file_path)
                    continue

            # Remove ReferenceIds since they are not needed for the prompt
            for entity in origin_entities + target_entities:
                del entity['_ReferenceIds']

            # Document to analyze
            document = load_text_data(document_path)

            ### LLM Prompt Information ###

            # Relation between different entity types, none of which are core entities (default)
            user_role = (
                f'\n\n==LIST 1 START==\n{json.dumps({relation_info["origin"]: origin_entities})}\n==LIST 1 END=='
                f'\n\n==LIST 2 START==\n{json.dumps({relation_info["target"]: target_entities})}\n==LIST 2 END=='
                f'\n\n==DOCUMENT START==\n{document}\n==DOCUMENT END=='
            )

            # Relation with core entities, or between the same entity type
            entity_name = relation_info['origin']
            entities = origin_entities
            if not origin_entities:
                entity_name = relation_info['target']
                entities = target_entities
            if (relation_info['origin'] == relation_info['target']) or (not origin_entities) or (not target_entities):
                user_role = (
                    f'\n\n==LIST START==\n{json.dumps({entity_name: entities})}\n==LIST END=='
                    f'\n\n==DOCUMENT START==\n{document}\n==DOCUMENT END=='
                )

            # Append the prompt data
            prompt_data.append(
                {
                    'document_name': document_name,
                    'document_set': document_set,
                    'object_name': relation_name,
                    'user_role': user_role,
                    'system_role': prompt,
                },
            )

    return prompt_data


def bypass_ai_processing(
    relation_name: str,
    relation_info: dict[str, Any],
    docs_dir: Path,
    results_dir: Path,
) -> Iterator[dict[str, Any]]:
    """Extract relations directly without using the LLM.

    Available only when one of the entity types is a core entity. Extracts relations
    by loading all the partial entities that are found in each document for the non-core entity type of the relation, and then assuming that
    the relation always exists between these partial entities and the core entity that represents their respective document.

    Args:
        relation_name: The name of the relation type to process.
        relation_info: A dictionary containing information about the relation type, following the data model specifications.
        docs_dir: The path to the directory containing the document sets.
        results_dir: The path to the directory where the results are stored.

    Yields:
        A dictionary containing the results of the relation extraction process for each document.
    """
    # If the documents are not found, discard this relation type
    if not docs_dir.exists():
        logger.error(f'Relation extraction failed. No documents found for relation type "{relation_name}".')
        return []

    # Path to partial entity results
    partial_results_dir = results_dir / 'partials/'
    partial_entities_dir = partial_results_dir / 'entities/'

    # Path to partial results for this relation type
    relation_results_dir = partial_results_dir / 'relations' / relation_name

    # Prepare results for each document, gathering documents from all sets
    document_paths = []
    data_model = DataModel()
    origin_sets = data_model.get_entity_sets(relation_info['origin'])
    target_sets = data_model.get_entity_sets(relation_info['target'])
    for document_set in sorted(origin_sets & target_sets):
        set_dir = docs_dir / document_set

        # If the document set directory does not exist, abort the process
        if not set_dir.exists():
            raise FileNotFoundError(
                f'Entity extraction failed. The directory for the document set "{document_set}" does not exist at path "{set_dir}".',
            )

        # Gather plain text files for this set
        document_paths = sorted(
            [doc_path for doc_path in set_dir.iterdir() if doc_path.is_file() and doc_path.suffix == '.txt'],
        )

        # Prepare results for each document
        for document_path in document_paths:
            # Path to partial results for this document
            document_name = document_path.stem
            results_file_path = relation_results_dir / f'{document_name}.json'

            # Load origin entities (if the core entity is the target)
            origin_entities = []
            if relation_info.get('core_target', False):
                # Only load partial entities if their processed version is available
                origin_entity_name = relation_info['origin'].removeprefix('@')
                final_origin_entities_path = results_dir / 'entities' / f'{origin_entity_name}.json'
                if not final_origin_entities_path.exists():
                    logger.error(
                        f'Relation extraction failed. No processed entities found for origin type "{origin_entity_name}".',
                    )
                    continue

                # Load partial origin entities for this document
                origin_entities_path = partial_entities_dir / relation_info['origin'] / f'{document_name}.json'
                origin_entities = load_json_data(origin_entities_path)
                if not origin_entities:
                    save_json_data([], results_file_path)
                    continue

                # Only keep the ObjectId of the origin entity, since the bypass relation is supposed to have no properties
                origin_entities = [{'_OriginId': entity['_ObjectId']} for entity in origin_entities]

            # Load target entities (if the core entity is the origin)
            target_entities = []
            if relation_info.get('core_origin', False):
                # Only load partial entities if their processed version is available
                target_entity_name = relation_info['target'].removeprefix('@')
                final_target_entities_path = results_dir / 'entities' / f'{target_entity_name}.json'
                if not final_target_entities_path.exists():
                    logger.error(
                        f'Relation extraction failed. No processed entities found for target type "{target_entity_name}".',
                    )
                    continue

                # Load partial target entities for this document
                target_entities_path = partial_entities_dir / relation_info['target'] / f'{document_name}.json'
                target_entities = load_json_data(target_entities_path)
                if not target_entities:
                    save_json_data([], results_file_path)
                    continue

                # Only keep the ObjectId of the target entity, since the bypass relation is supposed to have no properties
                target_entities = [{'_TargetId': entity['_ObjectId']} for entity in target_entities]

            # Generate results for this document
            full_document_name = f'{document_set}/{document_name}'
            logger.info(f'Processing type "{relation_name}" and document "{full_document_name}" without using the LLM')
            results = {
                'document_name': document_name,
                'document_set': document_set,
                'object_name': relation_name,
                'response': [],
            }
            results['response'] = {
                'results': origin_entities + target_entities,  # Either origin or target will be empty here
            }
            yield results


def process_extracted_relations(
    results: dict[str, Any],
    relation_model: dict[str, Any],
    partial_relations_dir: Path,
) -> None:
    """Process partial relations extracted by the LLM and save them to a partial results directory.

    Args:
        results: A dictionary containing the results of the LLM relation extraction process.
        relation_model: A dictionary containing relation types from the data model and their relevant information.
        partial_relations_dir: The path to the directory where the partial relations are stored.
    """
    # Get relation and document names
    relation_name = results['object_name']
    document_info = results['document_name'].split('_')
    partial_relations = results['response']['results']

    # Make unique ID that references the document, chunk and object
    *_, document_id, chunk_id = document_info
    for idx, relation in enumerate(partial_relations, start=1):
        relation['_ReferenceIds'] = [f'{document_id}_{chunk_id}_{idx}']

    # If origin is a Core Entity, complete with the Core Entity ID
    if relation_model[relation_name].get('core_origin', False):
        core_entity_name = relation_model[relation_name]['origin']
        core_entity_id = f'{core_entity_name}_{document_id}'
        for relation in partial_relations:
            relation['_OriginId'] = core_entity_id

    # If target is a Core Entity, complete with the Core Entity ID
    if relation_model[relation_name].get('core_target', False):
        core_entity_name = relation_model[relation_name]['target']
        core_entity_id = f'{core_entity_name}_{document_id}'
        for relation in partial_relations:
            relation['_TargetId'] = core_entity_id

    # Save relations to partial results file
    relation_results_dir = partial_relations_dir / relation_name
    results_file_path = relation_results_dir / f'{results["document_name"]}.json'
    save_json_data(partial_relations, results_file_path)


def build_global_entity_mapping(
    entities: list[dict[str, Any]],
    entity_name: str,
    *,
    core_entity: bool = False,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Create mappings to link partial entities of a given type to their final instances and identifiers.

    Args:
        entities: A list of dictionaries representing fully processed entities.
        entity_name: The name of the given entity type.
        core_entity: Whether the entity type is a core entity.

    Returns:
        A tuple containing two dictionaries
            - A mapping from ReferenceIds (representing partial entities) to ObjectIds (representing fully processed entities).
            - A mapping from ObjectIds to the index of the corresponding entities in the final entities list.
    """
    # Initialize mappings
    entity_id = 1
    entity_id_mapping = {}
    object_id_mapping = {}

    # Iterate through entities and assign both mappings
    for idx, entity in enumerate(entities):
        # Global ObjectId for each entity in the graph
        if not core_entity:  # Core entities are already assigned an ObjectId
            global_id = f'{entity_name.removeprefix("@")}_{entity_id}'
            entity['_ObjectId'] = global_id

        # Special ID to differentiate hybrid entities
        if entity_name.startswith('@'):
            entity['_ObjectId'] += 'A'

        # Assign mapping from ReferenceIds to ObjectIds
        for temp_id in entity['_ReferenceIds']:
            entity_id_mapping[temp_id] = entity['_ObjectId']

        # Assign mapping from ObjectIds to EntityIdx (their index in the entities list)
        object_id_mapping[entity['_ObjectId']] = idx

        entity_id += 1

    return entity_id_mapping, object_id_mapping


def build_entity_references(
    entities: list[dict[str, Any]],
    references_path: Path,
    *,
    core_entity: bool = False,
) -> None:
    """Build special relations to represent references between entities and their source documents.

    Args:
        entities: A list of dictionaries representing fully processed entities.
        references_path: The path to the file where the reference relations are stored.
        core_entity: Whether the entities are core entities.
    """
    # Iterate through entities and assign their source document references
    reference_relations = []
    for entity in entities:
        entity_references = []

        # Core entities are extracted from full documents
        if core_entity:
            document_number = entity['_ReferenceIds'][0]
            reference_relation = {'_OriginId': entity['_ObjectId'], '_TargetId': f'Document_{document_number}'}
            entity_references.append(reference_relation)
        else:  # Regular entities are extracted from document chunks
            for reference_id in entity['_ReferenceIds']:
                document_number, chunk_number, _ = reference_id.split('_')
                reference_relation = {
                    '_OriginId': entity['_ObjectId'],
                    '_TargetId': f'Chunk_{document_number}_{chunk_number}',
                }
                entity_references.append(reference_relation)

        # Gather all reference relations for the entity and remove ReferenceIds
        reference_relations.extend(entity_references)
        del entity['_ReferenceIds']

    # Append all reference relations to the same file
    general_references = []
    stored_references = load_json_data(references_path)
    general_references.extend(stored_references)
    general_references.extend(reference_relations)
    save_json_data(general_references, references_path)


def update_partial_entities(
    partial_entities: list[dict[str, Any]],
    final_entities: list[dict[str, Any]],
    object_mapping: dict[str, int],
) -> None:
    """Update partial entities with values from their corresponding final instances.

    Args:
        partial_entities: A list of dictionaries representing partial entities.
        final_entities: A list of dictionaries representing fully processed entities.
        object_mapping: A dictionary that allows mapping the partial entities to their final instances.
    """
    for partial_entity in partial_entities:
        source_entity = final_entities[object_mapping[partial_entity['_ObjectId']]]
        for key in source_entity:
            if key != '_ReferenceIds':  # Keep original ReferenceIds for partial entities
                # Some values here could be passed as references, so make sure to not modify them
                partial_entity[key] = source_entity[key]


def process_hybrid_entities(results_dir: Path) -> None:
    """Process hybrid entities by merging them with their corresponding core entities and updating references."""
    # Paths to partial and final results
    partial_entities_dir = results_dir / 'partials/entities/'
    entities_dir = results_dir / 'entities/'

    # Path to reference relations
    relations_dir = results_dir / 'relations/'
    references_path = relations_dir / 'ExtractedFrom.json'

    # Merge hybrid entities
    for entity, entity_info in DataModel().hybrid_entities.items():
        entity_name = entity.removeprefix('@')
        core_path = entities_dir / f'{entity_name}.json'
        hybrid_path = entities_dir / f'@{entity_name}.json'
        partial_results_dir = partial_entities_dir / f'@{entity_name}'

        # Merge the hybrid entity with the corresponding core entity
        core_entities = load_json_data(core_path)
        hybrid_entities = load_json_data(hybrid_path)
        unique_entities, hybrid_mapping = merge_hybrid_entities(core_entities, hybrid_entities, entity_info)

        # Create relations between hybrid entities and their source documents
        build_entity_references(unique_entities, references_path)

        # Save all final hybrid entities into a single file
        save_json_data(core_entities + unique_entities, core_path)
        hybrid_path.unlink(missing_ok=True)

        # Update partial hybrid entities with final ObjectIds after merging
        partial_results_paths = [
            results_path
            for results_path in partial_results_dir.iterdir()
            if results_path.is_file() and results_path.suffix == '.json'
        ]
        for partial_results_path in partial_results_paths:
            results = load_json_data(partial_results_path)
            for result in results:
                current_id = result['_ObjectId']
                result['_ObjectId'] = hybrid_mapping.get(current_id, current_id)  # Apply mapping to final ObjectId
            results = list({result['_ObjectId']: result for result in results}.values())  # Remove duplicates
            results.sort(key=lambda result: result['_ObjectId'])
            save_json_data(results, partial_results_path)


def build_relation_references(relations: list[dict[str, Any]]) -> None:
    """Create references between relations and their source documents using a special property.

    Args:
        relations: A list of dictionaries representing fully processed relations.
    """
    # Iterate through relations and assign their source document references
    for relation in relations:
        # Relations are extracted from document chunks
        relation_references = []
        for reference_id in relation['_ReferenceIds']:
            document_number, chunk_number, _ = reference_id.split('_')
            relation_references.append(f'Chunk_{document_number}_{chunk_number}')

        # Gather all references for the relation and remove ReferenceIds
        relation['extracted_from'] = relation_references
        del relation['_ReferenceIds']


def process_hybrid_relations(results_dir: Path) -> None:
    """Process hybrid relations by deduplicating those that contain hybrid entities."""
    # Path to final results
    relations_dir = results_dir / 'relations/'

    # Deduplicate relations that contain hybrid entities
    data_model = DataModel()
    hybrid_names = {entity.removeprefix('@') for entity in data_model.hybrid_entities}
    for relation, rel_info in data_model.relations.items():
        # Skip relation types that do not involve hybrid entities
        if not (hybrid_names & set(rel_info['origin'] + rel_info['target'])):
            continue

        # Load the full set of processed relations from this type
        relations_dir = results_dir / 'relations/'
        hybrid_relation_path = relations_dir / f'{relation}.json'
        processed_relations = load_json_data(hybrid_relation_path)

        # Gather all relations that contain hybrid entities
        unique_relations = []
        hybrid_groups = {}
        for rel in processed_relations:
            rel_origin = rel['_OriginId'].split('_')[0]
            rel_target = rel['_TargetId'].split('_')[0]
            rel_components = f'{rel_origin}_{rel_target}'

            # Group relations that contain hybrid entities
            if rel_origin in hybrid_names or rel_target in hybrid_names:
                if rel_components not in hybrid_groups:
                    hybrid_groups[rel_components] = []
                hybrid_groups[rel_components].append(rel)
                continue

            # Relation does not contain hybrid entities, add directly to the unique list
            unique_relations.append(rel)

        # Deduplicate relation groups that contain hybrid entities
        for rel_group in hybrid_groups.values():
            deduplicated_group = merge_duplicate_relations(rel_group, relation, rel_info)
            unique_relations.extend(deduplicated_group)

        # Save the final list of unique relations back to the relations JSON file
        save_json_data(unique_relations, hybrid_relation_path)
