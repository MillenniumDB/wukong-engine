"""Implements a knowledge graph export functionality.

This module provides functions to export available entities and relations
to various knowledge graph formats.
"""

import logging
from pathlib import Path
from typing import Any

from wukong_engine.core.data_model import DataModel
from wukong_engine.utils.file_utils import delete_dir_contents, load_json_data, save_json_data, save_text_data

# Logging
logger = logging.getLogger(__name__)

# Data Type Names
STR_NAMES = ('str', 'char', 'varchar', 'character', 'text', 'byte', 'bytes')
INT_NAMES = ('int', 'int8', 'int16', 'int32', 'int64', 'short int', 'long int', 'short', 'long')
FLOAT_NAMES = ('float32', 'float64', 'double', 'long double', 'decimal')
BOOL_NAMES = ('boolean',)


def export_to_mdb(results_dir: Path, export_dir: Path) -> None:
    """Export entities and relations to a knowledge graph in the MillenniumDB format.

    Args:
        results_dir: The path to the directory containing the entities and relations.
        export_dir: The path to the directory where the knowledge graph files will be exported.
    """
    # Prepare directories
    export_dir.mkdir(parents=True, exist_ok=True)
    delete_dir_contents(export_dir)
    entities_dir = results_dir / 'entities/'
    relations_dir = results_dir / 'relations/'

    # Get data model
    data_model = DataModel()

    # Entity model (including core & special entities)
    entity_model = data_model.core_entities | data_model.entities | data_model.special_entities

    # Convert entities to the MillenniumDB format
    entity_names = list(entity_model.keys())
    for entity_name in entity_names:
        entity_path = entities_dir / f'{entity_name}.json'

        # If entity file does not exist, skip it
        if not entity_path.exists():
            logger.error(
                f'MDB export failed. Results file for "{entity_name}" entity does not exist. Skipping this entity.',
            )
            continue

        # Load entity data and export to the MillenniumDB format
        entities = load_json_data(entity_path)
        entity_data = data_model.get_entity_properties(entity_name)
        object_to_mdb(entities, entity_name, entity_data, 'entity', export_dir)

    # Relation model (including special relations)
    relation_model = data_model.relations | data_model.special_relations

    # Convert relations to the MillenniumDB format
    relation_names = list(relation_model.keys())
    for relation_name in relation_names:
        relation_path = relations_dir / f'{relation_name}.json'

        # If relation file does not exist, skip it
        if not relation_path.exists():
            logger.error(
                f'MDB export failed. Results file for "{relation_name}" relation does not exist. Skipping this relation.',
            )
            continue

        # Load relation data and export to the MillenniumDB format
        relations = load_json_data(relation_path)
        relation_data = dict(data_model.get_relation_properties(relation_name))
        if relation_name not in data_model.special_relations:  # Add extracted_from property to relations
            relation_data['extracted_from'] = {'type': 'string'}
        object_to_mdb(relations, relation_name, relation_data, 'relation', export_dir)


def export_to_neo4j(results_dir: Path, export_dir: Path) -> None:
    """Export entities and relations to a knowledge graph in the Neo4j format.

    Args:
        results_dir: The path to the directory containing the entities and relations.
        export_dir: The path to the directory where the knowledge graph files will be exported.
    """
    # Prepare directories
    export_dir.mkdir(parents=True, exist_ok=True)
    delete_dir_contents(export_dir)
    entities_export_dir = export_dir / 'entities/'
    entities_export_dir.mkdir(parents=True, exist_ok=True)
    relations_export_dir = export_dir / 'relations/'
    relations_export_dir.mkdir(parents=True, exist_ok=True)
    entities_dir = results_dir / 'entities/'
    relations_dir = results_dir / 'relations/'

    # Get data model
    data_model = DataModel()

    # Entity model (including core & special entities)
    entity_model = data_model.core_entities | data_model.entities | data_model.special_entities

    # Convert entities to the Neo4j format
    entity_names = list(entity_model.keys())
    for entity_name in entity_names:
        entity_path = entities_dir / f'{entity_name}.json'

        # If entity file does not exist, skip it
        if not entity_path.exists():
            logger.error(
                f'Neo4j export failed. Results file for "{entity_name}" entity does not exist. Skipping this entity.',
            )
            continue

        # Load entity data and export to the Neo4j format
        entities = load_json_data(entity_path)
        entity_data = data_model.get_entity_properties(entity_name)
        object_to_neo4j(entities, entity_name, entity_data, 'entity', entities_export_dir)

    # Relation model (including special relations)
    relation_model = data_model.relations | data_model.special_relations

    # Convert relations to the Neo4j format
    relation_names = list(relation_model.keys())
    for relation_name in relation_names:
        relation_path = relations_dir / f'{relation_name}.json'

        # If relation file does not exist, skip it
        if not relation_path.exists():
            logger.error(
                f'Neo4j export failed. Results file for "{relation_name}" relation does not exist. Skipping this relation.',
            )
            continue

        # Load relation data and export to the Neo4j format
        relations = load_json_data(relation_path)
        relation_data = dict(data_model.get_relation_properties(relation_name))
        if relation_name not in data_model.special_relations:  # Add extracted_from property to relations
            relation_data['extracted_from'] = {'type': 'string'}
        object_to_neo4j(relations, relation_name, relation_data, 'relation', relations_export_dir)


def export_to_json(results_dir: Path, export_dir: Path) -> None:
    """Export entities and relations to a knowledge graph in JSON format.

    Args:
        results_dir: The path to the directory containing the entities and relations.
        export_dir: The path to the directory where the knowledge graph files will be exported.
    """
    # Prepare directories
    export_dir.mkdir(parents=True, exist_ok=True)
    delete_dir_contents(export_dir)
    entities_export_dir = export_dir / 'entities/'
    entities_export_dir.mkdir(parents=True, exist_ok=True)
    relations_export_dir = export_dir / 'relations/'
    relations_export_dir.mkdir(parents=True, exist_ok=True)
    entities_dir = results_dir / 'entities/'
    relations_dir = results_dir / 'relations/'

    # Get data model
    data_model = DataModel()

    # Entity model (including core & special entities)
    entity_model = data_model.core_entities | data_model.entities | data_model.special_entities

    # Export entities to JSON
    entity_names = list(entity_model.keys())
    for entity_name in entity_names:
        entity_path = entities_dir / f'{entity_name}.json'

        # If entity file does not exist, skip it
        if not entity_path.exists():
            logger.error(
                f'JSON export failed. Results file for "{entity_name}" entity does not exist. Skipping this entity.',
            )
            continue

        # Load entity data and export to JSON
        entities = load_json_data(entity_path)
        entity_data = data_model.get_entity_properties(entity_name)
        object_to_json(entities, entity_name, entity_data, 'entity', entities_export_dir)

    # Relation model (including special relations)
    relation_model = data_model.relations | data_model.special_relations

    # Export relations to JSON
    relation_names = list(relation_model.keys())
    for relation_name in relation_names:
        relation_path = relations_dir / f'{relation_name}.json'

        # If relation file does not exist, skip it
        if not relation_path.exists():
            logger.error(
                f'JSON export failed. Results file for "{relation_name}" relation does not exist. Skipping this relation.',
            )
            continue

        # Load relation data and export to JSON
        relations = load_json_data(relation_path)
        relation_data = dict(data_model.get_relation_properties(relation_name))
        if relation_name not in data_model.special_relations:  # Add extracted_from property to relations
            relation_data['extracted_from'] = {'type': 'string'}
        object_to_json(relations, relation_name, relation_data, 'relation', relations_export_dir)


def export_stats(results_dir: Path, export_dir: Path) -> None:
    """Export final graph statistics.

    Args:
        results_dir: The path to the directory containing the entities and relations.
        export_dir: The path to the directory where the knowledge graph files will be exported.
    """
    # Prepare directories
    export_dir.mkdir(parents=True, exist_ok=True)
    entities_dir = results_dir / 'entities/'
    relations_dir = results_dir / 'relations/'

    # Get data model
    data_model = DataModel()

    # Entity model (including core & special entities)
    entity_model = data_model.core_entities | data_model.entities | data_model.special_entities

    # Gather all entity stats
    entity_stats = {}
    entity_names = list(entity_model.keys())
    for entity_name in entity_names:
        entity_path = entities_dir / f'{entity_name}.json'

        # If entity file does not exist, skip it
        if not entity_path.exists():
            logger.error(
                f'Statistics export failed. Results file for "{entity_name}" entity does not exist. Skipping this entity.',
            )
            continue

        # Load entity data and gather stats
        entities = load_json_data(entity_path)
        entity_stats[entity_name] = len(entities)

    # Relation model (including special relations)
    relation_model = data_model.relations | data_model.special_relations

    # Gather all relation stats
    relation_stats = {}
    relation_names = list(relation_model.keys())
    for relation_name in relation_names:
        relation_path = relations_dir / f'{relation_name}.json'

        # If relation file does not exist, skip it
        if not relation_path.exists():
            logger.error(
                f'Statistics export failed. Results file for "{relation_name}" relation does not exist. Skipping this relation.',
            )
            continue

        # Load relation data and gather stats
        relations = load_json_data(relation_path)
        relation_stats[relation_name] = len(relations)

    # Calculate total stats
    total_entities = sum(entity_stats.values())
    total_relations = sum(relation_stats.values())
    stats_text = '***Statistics***\n\n'
    stats_text += f'Total Entities: {total_entities}\n'
    for entity_name, count in entity_stats.items():
        stats_text += f'  - {entity_name}: {count}\n'
    stats_text += f'\nTotal Relations: {total_relations}\n'
    for relation_name, count in relation_stats.items():
        stats_text += f'  - {relation_name}: {count}\n'

    # Export stats to a text file
    stats_path = export_dir / 'stats.txt'
    save_text_data(stats_text, stats_path)


def object_to_mdb(
    data: list[dict[str, Any]],
    object_label: str,
    object_data: dict[str, Any],
    object_type: str,
    object_export_dir: Path,
) -> None:
    """Convert a specific entity/relation type to the MillenniumDB format and export it to a Quad Model file.

    Args:
        data: A list of dictionaries representing instances of the entity/relation type.
        object_label: The name of the entity/relation type.
        object_data: A dictionary containing information about all properties from the entity/relation type, following the data model specifications.
        object_type: The type of each object inside `data`, either 'entity' or 'relation'.
        object_export_dir: The path to the directory where the MillenniumDB Quad Model file will be exported.
    """
    # Properties for entities and relations
    property_names = list(object_data)

    # Create data type mapping
    data_type_mapping = build_data_type_mapping()

    # Write to QM file
    export_path = object_export_dir / 'knowledge_graph.qm'
    with export_path.open('a', encoding='utf-8') as qm_file:
        for obj in data:
            # Add ID fields
            row = ''
            if object_type == 'entity':
                row += f'{obj["_ObjectId"]} :{object_label}'
            elif object_type == 'relation':
                row += f'{obj["_OriginId"]}->{obj["_TargetId"]} :{object_label}'

            # Add property fields
            for field in property_names:
                property_type = object_data[field].get('type', 'string').lower()
                property_type = data_type_mapping.get(property_type, property_type)
                match property_type:
                    case 'string':  # Remove line breaks and replace double quotes, add quotes to represent the string
                        field_value = str(obj.get(field, '')).replace('\n', ' ').replace('\r', ' ')
                        field_value = f'"{field_value.replace('"', "'")}"'
                    case 'integer':  # Convert to int
                        field_value = int(obj.get(field, 0))
                    case 'float':  # Convert to float
                        field_value = float(obj.get(field, 0.0))
                    case 'bool':  # Convert to bool in general format
                        field_value = str(obj.get(field, False)).lower()
                    case _:  # Unknown type, print a warning and convert to string
                        logger.warning(
                            f'Unknown type for property "{field}" of "{object_label}": {property_type}. Converting to string instead.',
                        )
                        field_value = str(obj.get(field, '')).replace('\n', ' ').replace('\r', ' ')
                        field_value = f'"{field_value.replace('"', "'")}"'
                row += f' {field}:{field_value}'

            # Write the row
            qm_file.write(row + '\n')


def object_to_neo4j(
    data: list[dict[str, Any]],
    object_label: str,
    object_data: dict[str, Any],
    object_type: str,
    object_export_dir: Path,
) -> None:
    """Convert a specific entity/relation type to the Neo4j format and export it to a CSV file.

    Args:
        data: A list of dictionaries representing instances of the entity/relation type.
        object_label: The name of the entity/relation type.
        object_data: A dictionary containing information about all properties from the entity/relation type, following the data model specifications.
        object_type: The type of each object inside `data`, either 'entity' or 'relation'.
        object_export_dir: The path to the directory where the Neo4j CSV file will be exported.
    """
    # Neo4j Headers for entities and relations
    headers = ['ObjectId:ID']
    if object_type == 'relation':
        headers = [':START_ID', ':END_ID']
    headers.extend(list(object_data))
    label_field_name = ':LABEL'
    if object_type == 'relation':
        label_field_name = ':TYPE'
    headers.append(label_field_name)

    # Create data type mapping
    data_type_mapping = build_data_type_mapping()

    # Write to CSV file
    object_export_path = object_export_dir / f'{object_label}.csv'
    with object_export_path.open('w', encoding='utf-8') as csv_file:
        # Write headers
        csv_file.write(','.join(headers) + '\n')

        # Write data
        for obj in data:
            # Add ID fields
            row = ''
            if object_type == 'entity':
                row += obj['_ObjectId']
            elif object_type == 'relation':
                row += f'{obj["_OriginId"]},{obj["_TargetId"]}'

            # Add property fields
            property_headers = headers[1:-1]
            if object_type == 'relation':
                property_headers = headers[2:-1]
            for field in property_headers:
                property_type = object_data[field].get('type', 'string').lower()
                property_type = data_type_mapping.get(property_type, property_type)
                match property_type:
                    case 'string':  # Remove line breaks and replace double quotes, add quotes to represent the string
                        field_value = str(obj.get(field, '')).replace('\n', ' ').replace('\r', ' ')
                        field_value = f'"{field_value.replace('"', "'")}"'
                    case 'integer':  # Convert to int
                        field_value = int(obj.get(field, 0))
                    case 'float':  # Convert to float
                        field_value = float(obj.get(field, 0.0))
                    case 'bool':  # Convert to bool in general format
                        field_value = str(obj.get(field, False)).lower()
                    case _:  # Unknown type, print a warning and convert to string
                        logger.warning(
                            f'Unknown type for property "{field}" of "{object_label}": {property_type}. Converting to string instead.',
                        )
                        field_value = str(obj.get(field, '')).replace('\n', ' ').replace('\r', ' ')
                        field_value = f'"{field_value.replace('"', "'")}"'
                row += f',{field_value}'

            # Add label field and write the row
            row += f',{object_label}\n'
            csv_file.write(row)


def object_to_json(
    data: list[dict[str, Any]],
    object_label: str,
    object_data: dict[str, Any],
    object_type: str,
    object_export_dir: Path,
) -> None:
    """Process a specific entity/relation type in JSON format and export it to a JSON file.

    Args:
        data: A list of dictionaries representing instances of the entity/relation type.
        object_label: The name of the entity/relation type.
        object_data: A dictionary containing information about all properties from the entity/relation type, following the data model specifications.
        object_type: The type of each object inside `data`, either 'entity' or 'relation'.
        object_export_dir: The path to the directory where the JSON file will be exported.
    """
    # Properties for entities and relations
    property_names = list(object_data)

    # Create data type mapping
    data_type_mapping = build_data_type_mapping()

    # Process data from objects
    for obj in data:
        # Remove keys that are not necessary
        extra_keys = []
        if object_type == 'entity':
            extra_keys = ['_ObjectId']
        elif object_type == 'relation':
            extra_keys = ['_OriginId', '_TargetId']
        for key in list(obj):
            if key not in property_names + extra_keys:
                del obj[key]

        # Process property fields
        for field in property_names:
            property_type = object_data[field].get('type', 'string').lower()
            property_type = data_type_mapping.get(property_type, property_type)
            match property_type:
                case 'string':  # Remove line breaks and replace double quotes, add quotes to represent the string
                    field_value = str(obj.get(field, '')).replace('\n', ' ').replace('\r', ' ')
                    field_value = f'"{field_value.replace('"', "'")}"'
                case 'integer':  # Convert to int
                    field_value = int(obj.get(field, 0))
                case 'float':  # Convert to float
                    field_value = float(obj.get(field, 0.0))
                case 'bool':  # Convert to bool in general format
                    field_value = str(obj.get(field, False)).lower()
                case _:  # Unknown type, print a warning and convert to string
                    logger.warning(
                        f'Unknown type for property "{field}" of "{object_label}": {property_type}. Converting to string instead.',
                    )
                    field_value = str(obj.get(field, '')).replace('\n', ' ').replace('\r', ' ')
                    field_value = f'"{field_value.replace('"', "'")}"'

            # Update the field
            obj[field] = field_value

    # Write processed data to JSON file
    object_export_path = object_export_dir / f'{object_label}.json'
    save_json_data(data, object_export_path)


def build_data_type_mapping() -> dict[str, str]:
    """Build a mapping of data type names to their corresponding supported type name.

    Returns:
        A dictionary mapping potential data type names to their corresponding supported type name.
        The supported type names are: `string`, `integer`, `float`, and `bool`.
    """
    data_type_groups = (STR_NAMES, INT_NAMES, FLOAT_NAMES, BOOL_NAMES)
    final_data_types = ('string', 'integer', 'float', 'bool')
    data_type_mapping = {}
    for idx, data_type_group in enumerate(data_type_groups):
        for data_type in data_type_group:
            data_type_mapping[data_type] = final_data_types[idx]
    return data_type_mapping
