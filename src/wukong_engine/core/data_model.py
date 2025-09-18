"""Provides a data model interface for the engine.

This module defines the `DataModel` class, responsible for loading,
validating, and providing access to the user-defined data model required by the engine.

Classes:
    DataModel: A singleton class that manages the data model for the engine.

Example:
    from wukong_engine.core.data_model import DataModel

    data_model = DataModel()
    entities = data_model.entities
"""

import json
import logging
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

from wukong_engine.utils.patterns import Singleton

# Logging
logger = logging.getLogger(__name__)

# Paths
DATA_MODEL_PATH = Path('./data_model.json')


class DataModel(Singleton):
    """The data model manager for the WUKONG engine.

    Loads and validates the data model, providing access to its components as properties.
    The data model is loaded once and is assumed to be immutable for the duration of the program.
    """

    def __init__(self, data_dir: Path = Path()) -> None:
        """Initialize the data model manager.

        Loads the data model and processes it to store each relevant component.

        Args:
            data_dir: The path to the data directory where the data model file is located.
        """
        # Components of the data model
        self._parameters = {}
        self._entities = {}
        self._relations = {}
        self._materialized_relations = {}
        self._entity_sets = {}

        # Initialize the data model
        self._load_model(data_dir / DATA_MODEL_PATH)
        self._process_model()

    def __repr__(self) -> str:
        """Return a string representation of the data model manager."""
        entity_model = self.core_entities | self.entities | self.special_entities
        simplified_entities = {entity: {} for entity in entity_model}
        for entity, entity_info in entity_model.items():
            simplified_entities[entity] = {
                'description': entity_info['description'],
                'properties': {k: v['description'] for k, v in entity_info.get('properties', {}).items()},
            }
            for k, v in entity_info.get('properties', {}).items():
                if 'options' in v:
                    simplified_entities[entity]['properties'][k] += f' Possible Values: {v["options"]}.'
        relation_model = self.relations | self.special_relations
        simplified_relations = {relation: {} for relation in relation_model}
        for relation, relation_info in relation_model.items():
            simplified_relations[relation] = {
                'source_target': relation_info['origin_target'],
                'description': relation_info['description'],
                'properties': {k: v['description'] for k, v in relation_info.get('properties', {}).items()},
            }
        simplified_model = {
            'entities': simplified_entities,
            'relations': simplified_relations,
        }
        return f'```json\n{json.dumps(simplified_model, indent=2, ensure_ascii=False)}\n```'

    def _load_model(self, data_model_path: Path) -> None:
        """Load the data model from a JSON file, making sure it has a valid format.

        Args:
            data_model_path: The path to the JSON data model file.

        Raises:
            FileNotFoundError: If the data model file does not exist.
            ValueError: If the data model file has an invalid structure or contents.
        """
        # Check if the data model file exists
        if not data_model_path.exists():
            raise FileNotFoundError(f'Data model file "{data_model_path}" not found')

        # Load the data model
        try:
            data_model = json.loads(
                data_model_path.read_text(encoding='utf-8'),
                object_pairs_hook=self._no_duplicate_keys_hook,
            )
        except json.JSONDecodeError as error:
            raise ValueError(f'Invalid structure for the data model in "{data_model_path}"') from error

        # Validate the data model
        self._validate_model(data_model)

        # Store the valid data model
        self._parameters = data_model['parameters']
        self._entities = data_model['entities']
        self._relations = data_model['relations']
        logger.info(f'Data model loaded successfully from: "{data_model_path}"')

    @staticmethod
    def _no_duplicate_keys_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        """Validate that the provided key/value pairs do not contain duplicate keys.

        Args:
            pairs: A list of key/value pairs to validate.

        Returns:
            A dictionary containing the key/value pairs if no duplicate keys are found.

        Raises:
            ValueError: If duplicate keys are found in the provided pairs.
        """
        seen = set()
        for key, _ in pairs:
            if key in seen:
                raise ValueError(f'Data model contains duplicate key "{key}"')
            seen.add(key)
        return dict(pairs)

    def _validate_model(self, data_model: dict[str, Any]) -> None:
        """Validate the data model to ensure it meets all requirements.

        Args:
            data_model: The data model to validate, containing definitions for entity/relation types and their properties.

        Raises:
            ValueError: If any entity/relation type or property does not meet all requirements.
            TypeError: If any fields have invalid types.
        """
        # Validate top-level structure
        if 'parameters' not in data_model or not isinstance(data_model['parameters'], dict):
            raise ValueError('Data model must have a valid "parameters" section')
        if 'entities' not in data_model or not isinstance(data_model['entities'], dict):
            raise ValueError('Data model must have a valid "entities" section')
        if 'relations' not in data_model or not isinstance(data_model['relations'], dict):
            raise ValueError('Data model must have a valid "relations" section')

        # Validate entities
        self._validate_entities(data_model['entities'])

        # Validate relations
        self._validate_relations(data_model['relations'], data_model['entities'])

        # Validate properties
        self._validate_properties(data_model['entities'] | data_model['relations'])

    @staticmethod
    def _validate_entities(entities: dict[str, Any]) -> None:
        """Validate data model entities to ensure they meet all requirements.

        Args:
            entities: The data model entities to validate.

        Raises:
            ValueError: If any entity type does not meet all requirements.
        """
        # Validate entity naming conventions
        for entity_name in entities:
            if not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9]*', entity_name):
                raise ValueError(
                    f'Invalid entity name "{entity_name}". Entity names must start with a letter and contain only alphanumeric characters.',
                )
            if entity_name.lower() in ('document', 'chunk'):
                raise ValueError(f'Entity name "{entity_name}" is reserved for special entities and cannot be used')

        # Validate entity definitions
        for entity_name, entity_info in entities.items():
            if 'description' not in entity_info:
                raise ValueError(f'Entity type "{entity_name}" must have a valid "description" field')
            if 'primary_key' not in entity_info:
                raise ValueError(f'Entity type "{entity_name}" must have a valid "primary_key" field')
            if entity_info['primary_key'] not in entity_info.get('properties', {}):
                raise ValueError(
                    f'The specified primary key property "{entity_info["primary_key"]}" for entity type "{entity_name}" does not exist.',
                )
            if not entity_info['properties'][entity_info['primary_key']].get('required', True):
                raise ValueError(
                    f'The primary key property "{entity_info["primary_key"]}" for entity type "{entity_name}" must have the "required" field set to true.',
                )

    @staticmethod
    def _validate_relations(relations: dict[str, Any], entities: dict[str, Any]) -> None:
        """Validate data model relations to ensure they meet all requirements.

        Args:
            relations: The data model relations to validate.
            entities: The data model entities to consider for origin/target validation.

        Raises:
            ValueError: If any relation type does not meet all requirements.
            TypeError: If any relation type has an invalid type for the origin/target fields.
        """
        # Validate relation naming conventions
        for relation_name in relations:
            if not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9]*', relation_name):
                raise ValueError(
                    f'Invalid relation name "{relation_name}". Relation names must start with a letter and contain only alphanumeric characters.',
                )
            if relation_name.lower() in ('chunkof', 'extractedfrom'):
                raise ValueError(
                    f'Relation name "{relation_name}" is reserved for special relations and cannot be used',
                )

        # Validate relation definitions
        for relation_name, relation_info in relations.items():
            if 'origin_target' not in relation_info and not ('origin' in relation_info and 'target' in relation_info):
                raise ValueError(
                    f'Relation type "{relation_name}" must have valid "origin" and "target" array fields or an "origin_target" dictionary field',
                )
            if 'description' not in relation_info:
                raise ValueError(f'Relation type "{relation_name}" must have a valid "description" field')
            if 'primary_key' in relation_info:
                if relation_info['primary_key'] not in relation_info.get('properties', {}):
                    raise ValueError(
                        f'The specified primary key property "{relation_info["primary_key"]}" for relation type "{relation_name}" does not exist.',
                    )
                if not relation_info['properties'][relation_info['primary_key']].get('required', True):
                    raise ValueError(
                        f'The primary key property "{relation_info["primary_key"]}" for relation type "{relation_name}" must have the "required" field set to true.',
                    )

        # Validate origin/target entity types
        for relation_name, relation_info in relations.items():
            # Validate origin/target fields from dictionary format
            if 'origin_target' in relation_info:
                if not isinstance(relation_info['origin_target'], dict):
                    raise TypeError(
                        f'Relation type "{relation_name}" must have valid "origin" and "target" array fields or an "origin_target" dictionary field',
                    )
                for origin, targets in relation_info['origin_target'].items():
                    if origin not in entities:
                        raise ValueError(
                            f'Relation type "{relation_name}" has an invalid "origin_target" field. The specified origin entity type "{origin}" does not exist.',
                        )
                    if not isinstance(targets, list):
                        raise TypeError(
                            f'Relation type "{relation_name}" must have a valid "origin_target" field where the dictionary values are lists of target entity types',
                        )
                    for target in targets:
                        if target not in entities:
                            raise ValueError(
                                f'Relation type "{relation_name}" has an invalid "origin_target" field. The specified target entity type "{target}" does not exist.',
                            )
                continue

            # Validate origin/target fields from lists format
            if not (isinstance(relation_info['origin'], list) and isinstance(relation_info['target'], list)):
                raise TypeError(
                    f'Relation type "{relation_name}" must have valid "origin" and "target" array fields or an "origin_target" dictionary field',
                )
            for origin in relation_info['origin']:
                if origin not in entities:
                    raise ValueError(
                        f'Relation type "{relation_name}" has an invalid "origin" field. The specified origin entity type "{origin}" does not exist.',
                    )
            for target in relation_info['target']:
                if target not in entities:
                    raise ValueError(
                        f'Relation type "{relation_name}" has an invalid "target" field. The specified target entity type "{target}" does not exist.',
                    )

    @staticmethod
    def _validate_properties(objects: dict[str, Any]) -> None:
        """Validate data model properties to ensure they meet all requirements.

        Args:
            objects: The data model entities and relations to validate properties from.

        Raises:
            ValueError: If any property does not meet all requirements.
        """
        # Validate property naming conventions
        for object_name, object_info in objects.items():
            for prop_name in object_info.get('properties', {}):
                if not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_]*', prop_name):
                    raise ValueError(
                        f'Invalid property name "{prop_name}" from "{object_name}". Property names must start with a letter and contain only alphanumeric characters and underscores.',
                    )
                if prop_name.lower() == 'extracted_from':
                    raise ValueError(
                        f'Property name "{prop_name}" from "{object_name}" is reserved for special properties and cannot be used',
                    )

        # Validate property definitions
        for object_name, object_info in objects.items():
            for prop_name, prop_info in object_info.get('properties', {}).items():
                if 'description' not in prop_info:
                    raise ValueError(
                        f'Property "{prop_name}" from "{object_name}" must have a valid "description" field',
                    )

    def _process_model(self) -> None:
        """Process the data model to prepare entity and relation types for use in the engine."""
        # Keep only the included entities
        included_entities = self._parameters.get('included_entities', list(self._entities.keys()))
        self._entities = {k: v for k, v in self._entities.items() if k in included_entities}

        # Add all included document sets to entities that do not specify them
        included_documents = self._parameters.get('included_documents', [])
        for entity_info in self._entities.values():
            if 'documents' not in entity_info:
                entity_info['documents'] = included_documents
            if 'documents_hybrid' not in entity_info:
                entity_info['documents_hybrid'] = included_documents

        # Materialize hybrid entities
        hybrid_entities = {}
        for entity, info in self._entities.items():
            if info.get('hybrid_entity', False):
                # Mark the original entity as a core entity
                info['core_entity'] = True

                # Create the hybrid version of the entity
                hybrid_info = deepcopy(info)
                hybrid_info['documents'] = info['documents_hybrid']
                del hybrid_info['core_entity']
                del hybrid_info['hybrid_entity']
                del hybrid_info['documents_hybrid']
                hybrid_entities[f'@{entity}'] = hybrid_info

                # Handle property descriptions for hybrid entities
                for prop_info in hybrid_info.get('properties', {}).values():
                    if 'description_hybrid' in prop_info:
                        prop_info['description'] = prop_info['description_hybrid']
                        del prop_info['description_hybrid']
        self._entities.update(hybrid_entities)

        # Store document sets for each entity
        self._entity_sets = {
            entity: set(info['documents']) & set(included_documents) for entity, info in self._entities.items()
        }

        # Keep only the included relations
        included_relations = self._parameters.get('included_relations', list(self._relations.keys()))
        self._relations = {k: v for k, v in self._relations.items() if k in included_relations}

        # Process origin/target schemas
        self._build_relation_schemas()

        # Materialize relations
        self._materialize_relation_model()

        # Add special entities
        special_entities = {
            'Document': {
                'special_entity': True,
                'description': 'Represents a document that was used for the construction of the knowledge graph.',
                'properties': {
                    'name': {
                        'type': 'string',
                        'description': 'The name of the original document.',
                    },
                    'document_set': {
                        'type': 'string',
                        'description': 'The name of the document set where the original document is contained.',
                    },
                },
            },
            'Chunk': {
                'special_entity': True,
                'description': 'Represents a fragment of a document used for the construction of the knowledge graph.',
                'properties': {
                    'text': {
                        'type': 'string',
                        'description': 'The text contained in the document chunk.',
                    },
                },
            },
        }
        self._entities.update(special_entities)

        # Add special relations
        special_relations = {
            'ChunkOf': {
                'special_relation': True,
                'origin_target': {'Chunk': ['Document']},
                'description': 'Connects each chunk to the respective document from which it was extracted.',
                'properties': {
                    'chunk_number': {
                        'type': 'integer',
                        'description': 'The number of the chunk within the document (ordered from beginning to end).',
                    },
                },
            },
            'ExtractedFrom': {
                'special_relation': True,
                'origin_target': {'ALL': ['Chunk', 'Document']},
                'description': 'Connects each entity to the respective chunk from which it was extracted.',
            },
        }
        self._relations.update(special_relations)

    def _build_relation_schemas(self) -> None:
        """Build schemas that represent all combinations for each relation type in the data model."""
        # Iterate over the relation model and build the schemas
        for relation_info in self._relations.values():
            # Skip if schema is already present
            if 'origin_target' not in relation_info:
                # Build schema from origin/target lists
                relation_info['origin_target'] = {
                    origin: list(relation_info['target']) for origin in relation_info['origin']
                }

            # Filter out any origin/target entities that are not included in the data model
            final_schema = {}
            for origin, targets in relation_info['origin_target'].items():
                valid_targets = list(set(targets) & set(self._entities))
                if origin not in self._entities or not valid_targets:
                    continue
                final_schema[origin] = valid_targets

            # Add final schema to relation info
            relation_info['origin_target'] = final_schema
            relation_info['origin'] = list(final_schema.keys())
            relation_info['target'] = list({t for targets in final_schema.values() for t in targets})

        # Only keep relations that have valid origin/target pairs
        self._relations = {k: v for k, v in self._relations.items() if v['origin_target']}

    def _materialize_relation_model(self) -> None:
        """Materialize the relation model to create specific relation types between entity type pairs."""
        # Add hybrid entities to the origin/target schemas
        final_schemas = {relation: {} for relation in self._relations}
        for relation, info in self._relations.items():
            for origin, targets in info['origin_target'].items():
                final_schemas[relation][origin] = list(targets)
                if f'@{origin}' in self.hybrid_entities:
                    final_schemas[relation][f'@{origin}'] = list(targets)
            for targets in final_schemas[relation].values():
                for target in list(targets):
                    if f'@{target}' in self.hybrid_entities:
                        targets.append(f'@{target}')

        # Iterate over the relation model and build materialized relations
        for relation_name, relation_info in self._relations.items():
            relation_info['properties'] = relation_info.get('properties', {})
            for origin, targets in final_schemas[relation_name].items():
                # Create a materialized relation for each combination of origin and target
                for target in targets:
                    # Materialize relation info
                    materialized_relation_info = dict(relation_info)
                    materialized_relation_info['origin'] = origin
                    materialized_relation_info['target'] = target
                    materialized_relation_info['relation_name'] = relation_name
                    materialized_relation_name = f'{origin}_{relation_name}_{target}'

                    # Check if the origin/target are Core Entities
                    origin_core_entity = origin in self.core_entities
                    target_core_entity = target in self.core_entities

                    # Special Case: No relations allowed between Core Entities
                    if origin_core_entity and target_core_entity:
                        continue

                    # Special Case: Relations with Core Entities
                    if origin_core_entity:
                        materialized_relation_info['core_origin'] = True
                    elif target_core_entity:
                        materialized_relation_info['core_target'] = True

                    # Store materialized relation info
                    del materialized_relation_info['origin_target']
                    self._materialized_relations[materialized_relation_name] = materialized_relation_info

    @property
    def parameters(self) -> dict[str, Any]:
        """A dictionary containing the parameters of the data model."""
        return self._parameters

    @property
    def entities(self) -> dict[str, Any]:
        """A dictionary containing all regular entity types in the data model (core/hybrid/special entities are excluded)."""
        return {
            k: v
            for k, v in self._entities.items()
            if not v.get('core_entity', False) and not v.get('special_entity', False) and not k.startswith('@')
        }

    @property
    def core_entities(self) -> dict[str, Any]:
        """A dictionary containing all core entity types in the data model."""
        return {k: v for k, v in self._entities.items() if v.get('core_entity', False)}

    @property
    def hybrid_entities(self) -> dict[str, Any]:
        """A dictionary containing all hybrid entity types in the data model."""
        return {k: v for k, v in self._entities.items() if k.startswith('@')}

    @property
    def special_entities(self) -> dict[str, Any]:
        """A dictionary containing all special entity types in the data model."""
        return {k: v for k, v in self._entities.items() if v.get('special_entity', False)}

    @property
    def relations(self) -> dict[str, Any]:
        """A dictionary containing all regular relation types in the data model (special relations are excluded)."""
        return {k: v for k, v in self._relations.items() if not v.get('special_relation', False)}

    @property
    def special_relations(self) -> dict[str, Any]:
        """A dictionary containing all special relation types in the data model."""
        return {k: v for k, v in self._relations.items() if v.get('special_relation', False)}

    @property
    def materialized_relations(self) -> dict[str, Any]:
        """A dictionary containing all materialized relation types between entity type pairs."""
        return self._materialized_relations

    @property
    def document_sets(self) -> list[str]:
        """A list of all document sets present in the data model."""
        return self._parameters.get('included_documents', [])

    def get_entity_sets(self, entity_name: str) -> set[str]:
        """Get the document datasets associated with a specific entity type.

        Args:
            entity_name: The name of the entity type.

        Returns:
            A set of document dataset names associated with the entity type.
        """
        return self._entity_sets.get(entity_name, set())

    def get_entity_data(self, entity_name: str) -> dict[str, Any]:
        """Get the data properties of a specific entity type.

        Data properties are those meant to be extracted from the documents.

        Args:
            entity_name: The name of the entity type.

        Returns:
            A dictionary containing all data properties of the entity type.
        """
        entity_info = self._entities.get(entity_name, {})
        entity_pk = entity_info.get('primary_key', '')
        entity_props = entity_info.get('properties', {})

        # Hybrid entities keep the primary key and any property marked as hybrid
        if entity_name in self.hybrid_entities:
            return {k: v for k, v in entity_props.items() if k == entity_pk or v.get('hybrid', False)}

        # Other entities keep all properties meant for the LLM
        return {k: v for k, v in entity_props.items() if k not in self.get_entity_metadata(entity_name)}

    def get_entity_metadata(self, entity_name: str) -> dict[str, Any]:
        """Get the metadata properties of a specific entity type.

        Args:
            entity_name: The name of the entity type.

        Returns:
            A dictionary containing all metadata properties of the entity type.
        """
        entity_info = self.core_entities.get(entity_name, {})  # Only core entities have metadata
        return {k: v for k, v in entity_info.get('properties', {}).items() if v.get('metadata', False)}

    def get_entity_properties(self, entity_name: str) -> dict[str, Any]:
        """Get the full properties of a specific entity type.

        Args:
            entity_name: The name of the entity type.

        Returns:
            A dictionary containing all properties of the entity type.
        """
        return self._entities.get(entity_name, {}).get('properties', {})

    def get_relation_data(self, relation_name: str) -> dict[str, Any]:
        """Get the data properties of a specific relation type.

        Data properties are those meant to be extracted from the documents.

        Args:
            relation_name: The name of the relation type.

        Returns:
            A dictionary containing all data properties of the relation type.
        """
        relation_info = self._relations.get(relation_name, {})
        return {k: v for k, v in relation_info.get('properties', {}).items() if k not in []}

    def get_relation_properties(self, relation_name: str) -> dict[str, Any]:
        """Get the full properties of a specific relation type.

        Args:
            relation_name: The name of the relation type.

        Returns:
            A dictionary containing all properties of the relation type.
        """
        return self._relations.get(relation_name, {}).get('properties', {})
