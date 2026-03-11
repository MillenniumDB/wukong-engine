"""Implements entity extraction from text documents.

This module defines functions to extract and process entities from unstructured text documents.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from wukong_engine.core.enums import ContentLevel
from wukong_engine.core.graph_model import EntityType, GraphModel
from wukong_engine.infra.config.config import Config
from wukong_engine.infra.llm.client import process_prompt
from wukong_engine.utils.file_utils import delete_dir_contents, load_json_data, load_text_data, save_json_data

from .data_processing import clean_entities, merge_duplicate_entities, merge_hybrid_entities

# Logging
logger = logging.getLogger(__name__)


# TODO: Refactor
def extract_entities(
    entity_types: list[EntityType],
    docs_dir: Path,
    prompts_dir: Path,
    results_dir: Path,
    *,
    metadata_dir: Path | None = None,
    clear_results: bool = False,
) -> None:
    """Extract all entities contained in the input documents, in accordance with the given entity types.

    Gathers prompts for each entity type, processes them in parallel using LLMs,
    and saves the results in a structured manner.

    Args:
        entity_types: A list of all entity types from the graph model.
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

    # Get the graph model
    graph_model = GraphModel()

    # Extract info for each entity type and source
    for entity in entity_types:
        for level in ContentLevel:  # TODO: Iterate over Content levels from entity type
            partial_entity_dir = partial_entities_dir / entity.name / level.name
            partial_entity_dir.mkdir(parents=True, exist_ok=True)

            # Get prompts and process them with the LLM
            # TODO: See if it's better with a get_extraction_properties(source) method or with the @property.get(source)
            if entity.extraction_properties.get(source, {}):
                prompt_data = get_entity_prompts(entity.name, docs_dir, prompts_dir)

                # Execute the LLM prompt processing in parallel, since API calls are slow
                with ThreadPoolExecutor(max_workers=Config().get('max_worker_threads', None)) as executor:
                    futures = [executor.submit(process_prompt, prompt_info) for prompt_info in prompt_data]
                    for future in as_completed(futures):
                        try:
                            results = future.result()  # Wait for the API call to complete
                            process_extracted_entities(
                                results,
                                entity_types,
                                partial_entities_dir,
                            )  # Process the partial results
                        except Exception:
                            logger.exception('An unexpected error occurred during entity extraction.')

            # TODO: Change to external_properties
            # Load metadata if available
            if graph_model.get_entity_metadata(entity_name) and metadata_dir:
                load_entity_metadata(entity_name, metadata_dir, docs_dir, partial_entities_dir)


def process_entities(entity_types: list[EntityType], results_dir: Path) -> None:
    """Process extracted entities to merge duplicates and remove invalid objects, saving the final results.

    Consolidates the results of entity extraction, cleans the entities, merges duplicates,
    and saves the final entities into a single file for each entity type.

    Args:
        entity_model: A dictionary containing entity types from the graph model and their relevant information.
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
    for document_set in sorted(GraphModel().get_entity_sets(entity_name)):
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
        entity_model: A dictionary containing entity types from the graph model and their relevant information.
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
    graph_model = GraphModel()
    for document_set in sorted(graph_model.get_entity_sets(entity_name)):
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
            entity_data: dict[str, Any] = dict.fromkeys(graph_model.get_entity_metadata(entity_name), 'NULL')
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
    for entity, entity_info in GraphModel().hybrid_entities.items():
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
