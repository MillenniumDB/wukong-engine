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
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .entity_type import EntityType

# Logging
logger = logging.getLogger(__name__)

# Paths
DATA_MODEL_PATH = Path('./data_model.json')


@dataclass
class DataModel:
    entities: list[EntityType]


# TODO: Refactor
class DataModel(Singleton):
    """The data model manager for the WUKONG engine.

    Loads and validates the data model, providing easy access to its components.
    The data model is loaded once and assumed to be immutable for the duration of the program.
    """

    def __init__(self, data_dir: Path = Path()) -> None:
        """Initialize the data model manager.

        Loads the data model and processes it to store each relevant component.

        Args:
            data_dir: The path to the data directory where the data model file is located.
        """
        # Components of the data model
        self._parameters = {}
        self._entities = []
        self._relations = {}  # TODO: Change to list
        self._materialized_relations = {}  # TODO: Refactor

        # Initialize the data model
        self._load_model(data_dir / DATA_MODEL_PATH)

    # TODO: Refactor
    def __repr__(self) -> str:
        """Return a string representation of the data model manager."""
        entities = self.core_entities + self.entities + self.special_entities
        simplified_entities = {entity: {} for entity in entities}
        for entity in entities:
            simplified_entities[entity] = {
                'description': entity.parameters['description'],
                'properties': {k: v['description'] for k, v in entity.fields.items()},
            }
            for k, v in entity.fields.items():
                if 'options' in v:
                    simplified_entities[entity]['properties'][k] += f' Possible Values: {v["options"]}.'
        relation_model = self.relations | self.special_relations
        simplified_relations = {relation: {} for relation in relation_model}
        for relation, relation_info in relation_model.items():
            simplified_origin_target = {}
            for origin, targets in relation_info['origin_target'].items():
                simplified_origin = origin.replace('@', '')
                simplified_targets = list({target.replace('@', '') for target in targets})
                if simplified_origin not in simplified_origin_target:
                    simplified_origin_target[simplified_origin] = simplified_targets
                current_targets = simplified_origin_target[simplified_origin]
                simplified_origin_target[simplified_origin] = list(set(current_targets + simplified_targets))
            simplified_relations[relation] = {
                'source_target': simplified_origin_target,
                'description': relation_info['description'],
                'properties': {k: v['description'] for k, v in relation_info.get('fields', {}).items()},
            }
            for k, v in relation_info.get('fields', {}).items():
                if 'options' in v:
                    simplified_relations[relation]['properties'][k] += f' Possible Values: {v["options"]}.'
        simplified_model = {
            'entities': simplified_entities,
            'relations': simplified_relations,
        }
        return f'```json\n{json.dumps(simplified_model, indent=2, ensure_ascii=False)}\n```'

    def _load_model(self, data_model_path: Path) -> None:
        """Load the data model from a JSON file, making sure it has a valid format and satisfies all requirements.

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

        # Validate the general data model structure
        self._validate_structure(data_model)

        # Store the general parameters
        self._parameters = data_model['parameters']

        # Load and validate entity types
        self._load_entity_types(data_model['entities'])

        # Load and validate relation types
        self._load_relation_types(data_model['relations'])

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

    @staticmethod
    def _validate_structure(data_model: dict[str, Any]) -> None:
        """Validate the general data model structure to ensure it contains all required fields.

        Args:
            data_model: The data model to validate.

        Raises:
            ValueError: If the general data model structure is invalid.
        """
        # Validate top-level structure
        general_fields = ['parameters', 'entities', 'relations']
        for field in general_fields:
            if field not in data_model or not isinstance(data_model[field], dict):
                raise ValueError(f'Data model must have a valid "{field}" section')

    # TODO: Complete
    def _load_entity_types(self, entity_types: dict[str, Any]) -> None:
        """Load and validate data model entity types.

        Args:
            entity_types: The data model entity types to load.

        Raises:
            ValueError: If any entity type does not meet all requirements.
        """
        # Keep only the included entities
        included_entity_types = self._parameters.get('included_entities', list(entity_types.keys()))

        # Instantiate objects for each entity type
        self._entities = [
            EntityType(entity_name, entity_data)
            for entity_name, entity_data in entity_types.items()
            if entity_name in included_entity_types
        ]

        # TODO: Replace with the code above
        # Materialize hybrid entities
        """
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
                for prop_info in hybrid_info.get('fields', {}).values():
                    if 'description_hybrid' in prop_info:
                        prop_info['description'] = prop_info['description_hybrid']
                        del prop_info['description_hybrid']
        self._entities.update(hybrid_entities)
        """

        # Add special entities
        special_entities = {
            'Document': {
                'parameters': {
                    'special_entity': True,
                    'description': 'Represents a document that was used for the construction of the knowledge graph.',
                },
                'fields': {
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
                'parameters': {
                    'special_entity': True,
                    'description': 'Represents a fragment of a document used for the construction of the knowledge graph.',
                },
                'fields': {
                    'text': {
                        'type': 'string',
                        'description': 'The text contained in the document chunk.',
                    },
                },
            },
        }
        for entity_name, entity_data in special_entities.items():
            special_entity_type = EntityType(entity_name, entity_data)
            self._entities.append(special_entity_type)

        # TODO: Remove
        for entity in self._entities:
            print(entity)

    # TODO: Refactor
    def _load_relation_types(self, relation_types: dict[str, Any]) -> None:
        """Load and validate data model relations."""
        # Validate relations
        # self._validate_relations(data_model['relations'], data_model['entities'])

        # Validate fields
        # self._validate_fields(data_model['entities'] | data_model['relations'])

        # Keep only the included relations
        included_relations = self._parameters.get('included_relations', list(self._relations.keys()))
        self._relations = {k: v for k, v in self._relations.items() if k in included_relations}

        # Process origin/target schemas
        self._build_relation_schemas()

        # Materialize relations
        self._materialize_relation_model()

        # Add special relations
        special_relations = {
            'ChunkOf': {
                'special_relation': True,
                'origin_target': {'Chunk': ['Document']},
                'description': 'Connects each chunk to the respective document from which it was extracted.',
                'fields': {
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

    # TODO: Move to RelationType class
    @staticmethod
    def _validate_relations(relations: dict[str, Any], entities: dict[str, Any]) -> None:
        """Validate data model relations to ensure they meet all requirements.

        Args:
            relations: The data model relations to validate.
            entities: The data model entities to consider for origin/target validation.

        Raises:
            ValueError: If any relation type does not meet all requirements.
            TypeError: If any relation type has an invalid type for the origin/target attributes.
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
                    f'Relation type "{relation_name}" must have valid "origin" and "target" array attributes or an "origin_target" dictionary attribute',
                )
            if 'description' not in relation_info:
                raise ValueError(f'Relation type "{relation_name}" must have a valid "description" attribute')
            if 'primary_key' in relation_info:
                if relation_info['primary_key'] not in relation_info.get('fields', {}):
                    raise ValueError(
                        f'The specified primary key field "{relation_info["primary_key"]}" for relation type "{relation_name}" does not exist.',
                    )
                if not relation_info['fields'][relation_info['primary_key']].get('required', True):
                    raise ValueError(
                        f'The primary key field "{relation_info["primary_key"]}" for relation type "{relation_name}" must have the "required" attribute set to true.',
                    )

        # Validate origin/target entity types
        hybrid_entities = [f'@{entity}' for entity, data in entities.items() if data.get('hybrid_entity', False)]
        full_entities = list(entities.keys()) + hybrid_entities
        for relation_name, relation_info in relations.items():
            # Validate origin/target fields from dictionary format
            if 'origin_target' in relation_info:
                if not isinstance(relation_info['origin_target'], dict):
                    raise TypeError(
                        f'Relation type "{relation_name}" must have valid "origin" and "target" array attributes or an "origin_target" dictionary attribute',
                    )
                for origin, targets in relation_info['origin_target'].items():
                    if origin not in full_entities:
                        raise ValueError(
                            f'Relation type "{relation_name}" has an invalid "origin_target" attribute. The specified origin entity type "{origin}" does not exist.',
                        )
                    if not isinstance(targets, list):
                        raise TypeError(
                            f'Relation type "{relation_name}" must have a valid "origin_target" attribute where the dictionary values are lists of target entity types',
                        )
                    for target in targets:
                        if target not in full_entities:
                            raise ValueError(
                                f'Relation type "{relation_name}" has an invalid "origin_target" attribute. The specified target entity type "{target}" does not exist.',
                            )
                continue

            # Validate origin/target fields from lists format
            if not (isinstance(relation_info['origin'], list) and isinstance(relation_info['target'], list)):
                raise TypeError(
                    f'Relation type "{relation_name}" must have valid "origin" and "target" array attributes or an "origin_target" dictionary attribute',
                )
            for origin in relation_info['origin']:
                if origin not in full_entities:
                    raise ValueError(
                        f'Relation type "{relation_name}" has an invalid "origin" attribute. The specified origin entity type "{origin}" does not exist.',
                    )
            for target in relation_info['target']:
                if target not in full_entities:
                    raise ValueError(
                        f'Relation type "{relation_name}" has an invalid "target" attribute. The specified target entity type "{target}" does not exist.',
                    )

    # TODO: Move to RelationType class
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

    # TODO: Move to RelationType class
    def _materialize_relation_model(self) -> None:
        """Materialize the relation model to create specific relation types between entity type pairs."""
        # Iterate over the relation model and build materialized relations
        for relation_name, relation_info in self._relations.items():
            relation_info['fields'] = relation_info.get('fields', {})
            for origin, targets in relation_info['origin_target'].items():
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

    # TODO: Refactor
    @property
    def entities(self) -> list[EntityType]:
        """A list of all regular entity types in the data model (core/hybrid/special entities are excluded)."""
        return [
            entity
            for entity in self._entities
            if not entity.has_source('document') and not entity.is_special_entity() and not entity.name.startswith('@')
        ]

    # TODO: Refactor
    @property
    def core_entities(self) -> list[EntityType]:
        """A list of all core entity types in the data model."""
        return [entity for entity in self._entities if entity.has_source('document')]

    # TODO: Refactor
    @property
    def hybrid_entities(self) -> list[EntityType]:
        """A list of all hybrid entity types in the data model."""
        return [entity for entity in self._entities if entity.has_source('chunk') and entity.has_source('document')]

    # TODO: Refactor
    @property
    def special_entities(self) -> list[EntityType]:
        """A list of all special entity types in the data model."""
        return [entity for entity in self._entities if entity.is_special_entity()]

    # TODO: Refactor
    @property
    def relations(self) -> dict[str, Any]:
        """A dictionary containing all regular relation types in the data model (special relations are excluded)."""
        return {k: v for k, v in self._relations.items() if not v.get('special_relation', False)}

    # TODO: Refactor
    @property
    def special_relations(self) -> dict[str, Any]:
        """A dictionary containing all special relation types in the data model."""
        return {k: v for k, v in self._relations.items() if v.get('special_relation', False)}

    # TODO: Refactor
    @property
    def materialized_relations(self) -> dict[str, Any]:
        """A dictionary containing all materialized relation types between entity type pairs."""
        return self._materialized_relations

    # TODO: Refactor
    def get_relation_data(self, relation_name: str) -> dict[str, Any]:
        """Get the data fields of a specific relation type.

        Data fields are those meant to be extracted from the documents.

        Args:
            relation_name: The name of the relation type.

        Returns:
            A dictionary containing all data fields of the relation type.
        """
        relation_info = self._relations.get(relation_name, {})
        return {
            k: v
            for k, v in relation_info.get('fields', {}).items()
            if k not in self.get_relation_placeholders(relation_name)
        }

    # TODO: Refactor
    def get_relation_placeholders(self, relation_name: str) -> dict[str, Any]:
        """Get the placeholder fields of a specific relation type.

        Args:
            relation_name: The name of the relation type.

        Returns:
            A dictionary containing all placeholder fields of the relation type.
        """
        relation_info = self._relations.get(relation_name, {})
        relation_pk = relation_info.get('primary_key', '')
        relation_props = relation_info.get('fields', {})
        return {k: v for k, v in relation_props.items() if 'placeholder' in v and k != relation_pk}

    # TODO: Refactor
    def get_relation_fields(self, relation_name: str) -> dict[str, Any]:
        """Get the full fields of a specific relation type.

        Args:
            relation_name: The name of the relation type.

        Returns:
            A dictionary containing all fields of the relation type.
        """
        return self._relations.get(relation_name, {}).get('fields', {})
