import json
import logging
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from wukong_engine.config.config import Config
from wukong_engine.llm.llm_client import process_prompt
from wukong_engine.utils.file_utils import delete_dir_contents, load_json_data, load_text_data, save_json_data

from .data_processing import clean_entities, clean_relations, remove_duplicate_entities, remove_duplicate_relations

# Logging
logger = logging.getLogger(__name__)


def find_entities(
    entity_model: dict[str, Any],
    docs_dir: Path,
    prompts_dir: Path,
    results_dir: Path,
    *,
    clear_results: bool = False,
) -> None:
    """Find all entities contained in the input documents, in accordance with the given entity model.

    Gathers prompts for each entity type, processes them in parallel using LLMs,
    and saves the results in a structured manner.

    Args:
        entity_model: A dictionary containing entity types from the data model and their relevant information.
        docs_dir: The path to the directory containing the input documents.
        prompts_dir: The path to the directory containing the prompts for the LLM.
        results_dir: The path to the directory where the results are stored.
        clear_results: Whether to clear the partial results directory before starting the procedure.
    """
    # Path to partial entity results
    partial_results_dir = results_dir / 'partials/'
    partial_results_dir.mkdir(parents=True, exist_ok=True)
    if clear_results:
        delete_dir_contents(partial_results_dir)
    partial_entities_dir = partial_results_dir / 'entities/'
    partial_entities_dir.mkdir(parents=True, exist_ok=True)

    # Gather prompt data for each entity type
    prompts_data = []
    for entity_name in entity_model:
        entity_prompts_data = get_entity_prompts(entity_name, docs_dir, prompts_dir)
        prompts_data.extend(entity_prompts_data)

    # Execute the LLM prompt processing in parallel, since API calls are slow
    with ThreadPoolExecutor(max_workers=Config().get('max_worker_threads', None)) as executor:
        futures = [executor.submit(process_prompt, prompt_data) for prompt_data in prompts_data]
        for future in as_completed(futures):
            try:
                results = future.result()  # Wait for the API call to complete
                process_partial_entities(results, entity_model, partial_entities_dir)  # Process the partial results
            except Exception:
                logger.exception('An unexpected error occurred during entity extraction.')


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
        docs_dir: The path to the directory containing the input documents.
        prompts_dir: The path to the directory containing the prompts for the LLM.
        results_dir: The path to the directory where the results are stored.
        clear_results: Whether to clear the partial results directory before starting the procedure.
    """
    # Path to partial relation results
    partial_relations_dir = results_dir / 'partials/relations/'
    partial_relations_dir.mkdir(parents=True, exist_ok=True)
    if clear_results:
        delete_dir_contents(partial_relations_dir)

    # Gather prompt data for each relation type
    prompts_data = []
    for relation_name, relation_info in relation_model.items():
        # Process relation without the LLM (only available when one of the entities is a core entity)
        core_entity_relation = relation_info.get('core_origin', False) or relation_info.get('core_target', False)
        if core_entity_relation and relation_info.get('bypass_LLM', False):
            for results in bypass_ai_processing(relation_name, relation_info, docs_dir, results_dir):
                process_partial_relations(results, relation_model, partial_relations_dir)
            continue

        # Process relation with the LLM
        relation_prompts_data = get_relation_prompts(relation_name, relation_info, docs_dir, prompts_dir, results_dir)
        prompts_data.extend(relation_prompts_data)

    # Execute the LLM prompt processing in parallel, since API calls are slow
    with ThreadPoolExecutor(max_workers=Config().get('max_worker_threads', None)) as executor:
        futures = [executor.submit(process_prompt, prompt_data) for prompt_data in prompts_data]
        for future in as_completed(futures):
            try:
                results = future.result()  # Wait for the API call to complete
                process_partial_relations(results, relation_model, partial_relations_dir)  # Process the partial results
            except Exception:
                logger.exception('An unexpected error occurred during relation extraction.')


def process_entities(entity_model: dict[str, Any], results_dir: Path) -> None:
    """Process extracted entities to remove duplicates and invalid objects, saving the final results.

    Consolidates the results of entity extraction, cleans the entities, removes duplicates,
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
    stats_dict = {entity: {} for entity in entity_model}  # Entity statistics
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
        stats_dict[entity_name]['original_entities'] = len(entities)

        # Clean entities and remove invalid ones
        entities = clean_entities(entities, entity_info)
        stats_dict[entity_name]['cleaned_entities'] = len(entities)

        # Remove duplicate entities
        entities = remove_duplicate_entities(entities, entity_info)
        stats_dict[entity_name]['final_entities'] = len(entities)

        # Create global ID mapping for entities
        entity_mapping, object_mapping = build_global_entity_mapping(
            entities,
            entity_name,
            core_entity=entity_info.get('core_entity', False),
        )

        # Create relations between final entities and their source documents
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

    # Save stats for all entities
    stats_path = entities_dir / '_stats.json'
    save_json_data(stats_dict, stats_path)


def process_relations(relation_model: dict[str, Any], results_dir: Path) -> None:
    """Process extracted relations to remove duplicates and invalid objects, saving the final results.

    Consolidates the results of relation extraction, cleans the relations, removes duplicates,
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
    entity_stats_path = results_dir / 'entities/_stats.json'

    # If the result directories do not exist, abort the process
    required_paths = (partial_relations_dir, relations_dir, entity_stats_path)
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
    stats_dict = {materialized_relation: {} for materialized_relation in relation_model}  # Relation statistics
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
        stats_dict[materialized_relation_name]['original_relations'] = len(relations)

        # Clean relations and remove invalid ones
        relations = clean_relations(relations, relation_info, entity_stats_path)
        stats_dict[materialized_relation_name]['cleaned_relations'] = len(relations)

        # Remove duplicate relations
        relations = remove_duplicate_relations(relations, relation_info)
        stats_dict[materialized_relation_name]['final_relations'] = len(relations)

        # Store reference between final relations and their source documents
        build_relation_references(relations)

        # Save all final relations into a single file, appending materialized relation data
        general_relations = []
        relations_path = relations_dir / f'{relation_info["relation_name"]}.json'
        stored_relations = load_json_data(relations_path)
        general_relations.extend(stored_relations)
        general_relations.extend(relations)
        save_json_data(general_relations, relations_path)

    # Save stats for all relations
    stats_path = relations_dir / '_stats.json'
    save_json_data(stats_dict, stats_path)


def get_entity_prompts(entity_name: str, docs_dir: Path, prompts_dir: Path) -> list[dict[str, Any]]:
    """Generate a list of dictionaries containing the prompt data for the given entity type and documents.

    Args:
        entity_name: The name of the entity type to process.
        docs_dir: The path to the directory containing the input documents.
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

    # Prepare prompt data for each document
    prompts_data = []
    document_paths = [doc_path for doc_path in docs_dir.iterdir() if doc_path.is_file() and doc_path.suffix == '.txt']
    for document_path in document_paths:
        # Document to analyze
        document_name = document_path.stem
        document = load_text_data(document_path)

        # LLM Prompt Information
        prompts_data.append(
            {'document_name': document_name, 'object_name': entity_name, 'user_role': document, 'system_role': prompt},
        )

    return prompts_data


def process_partial_entities(results: dict[str, Any], entity_model: dict[str, Any], partial_entities_dir: Path) -> None:
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
        core_entity['_ObjectId'] = f'{entity_name}_{document_info[1]}'
        core_entity['_ReferenceIds'] = [f'{document_info[1]}']
        partial_entities = [core_entity]  # Convert to list for consistency
    else:  # Regular Entity: List of objects
        partial_entities = results['response']['results']

        # Make unique ID that references the document, chunk and object
        _, document_id, chunk_id = document_info
        for idx, entity in enumerate(partial_entities, start=1):
            entity['_ReferenceIds'] = [f'{document_id}_{chunk_id}_{idx}']

    # Path to partial results for this entity type
    entity_results_dir = partial_entities_dir / entity_name
    entity_results_dir.mkdir(parents=True, exist_ok=True)

    # Save entities to partial results file
    results_file_path = entity_results_dir / f'{results["document_name"]}.json'
    save_json_data(partial_entities, results_file_path)


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
        docs_dir: The path to the directory containing the input documents.
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
    relation_results_dir.mkdir(parents=True, exist_ok=True)

    # Prepare prompt data for each document
    prompts_data = []
    document_paths = [doc_path for doc_path in docs_dir.iterdir() if doc_path.is_file() and doc_path.suffix == '.txt']
    for document_path in document_paths:
        # Path to partial results for this document
        document_name = document_path.stem
        results_file_path = relation_results_dir / f'{document_name}.json'

        # Load potential origin entities (if the origin is not a core entity)
        origin_entities = []
        if not relation_info.get('core_origin', False):
            # Only load partial entities if their processed version is available
            final_origin_entities_path = results_dir / 'entities' / f'{relation_info["origin"]}.json'
            if not final_origin_entities_path.exists():
                logger.error(
                    f'Relation extraction failed. No processed entities found for origin type "{relation_info["origin"]}".',
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
            final_target_entities_path = results_dir / 'entities' / f'{relation_info["target"]}.json'
            if not final_target_entities_path.exists():
                logger.error(
                    f'Relation extraction failed. No processed entities found for target type "{relation_info["target"]}".',
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
        prompts_data.append(
            {
                'document_name': document_name,
                'object_name': relation_name,
                'user_role': user_role,
                'system_role': prompt,
            },
        )

    return prompts_data


def bypass_ai_processing(
    relation_name: str,
    relation_info: dict[str, Any],
    docs_dir: Path,
    results_dir: Path,
) -> Iterator[dict[str, Any]]:
    """Extract relations directly without using the LLM.

    Available only when one of the entity types is a core entity. Extracts relations
    by loading all the partial entities that are found in each document for the non-core entity type of the relation, and assuming that
    the relation always exists between these partial entities and the core entity that represents their respective document.

    Args:
        relation_name: The name of the relation type to process.
        relation_info: A dictionary containing information about the relation type, following the data model specifications.
        docs_dir: The path to the directory containing the input documents.
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
    relation_results_dir.mkdir(parents=True, exist_ok=True)

    # Prepare results for each document (assuming that the relation is always valid)
    document_paths = [doc_path for doc_path in docs_dir.iterdir() if doc_path.is_file() and doc_path.suffix == '.txt']
    for document_path in document_paths:
        # Path to partial results for this document
        document_name = document_path.stem
        results_file_path = relation_results_dir / f'{document_name}.json'

        # Load origin entities (if the core entity is the target)
        origin_entities = []
        if relation_info.get('core_target', False):
            # Only load partial entities if their processed version is available
            final_origin_entities_path = results_dir / 'entities' / f'{relation_info["origin"]}.json'
            if not final_origin_entities_path.exists():
                logger.error(
                    f'Relation extraction failed. No processed entities found for origin type "{relation_info["origin"]}".',
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
            final_target_entities_path = results_dir / 'entities' / f'{relation_info["target"]}.json'
            if not final_target_entities_path.exists():
                logger.error(
                    f'Relation extraction failed. No processed entities found for target type "{relation_info["target"]}".',
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
        logger.info(f'Processing type "{relation_name}" and document "{document_name}" without using the LLM')
        results = {'document_name': document_name, 'object_name': relation_name, 'response': []}
        results['response'] = {
            'results': origin_entities + target_entities,  # Either origin or target will be empty here
        }
        yield results


def process_partial_relations(
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
    _, document_id, chunk_id = document_info
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
    """Create mappings to link partial entities of a given type to their final instances and ObjectIds.

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
            global_id = f'{entity_name}_{entity_id}'
            entity['_ObjectId'] = global_id

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
