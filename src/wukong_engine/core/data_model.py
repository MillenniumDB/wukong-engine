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

        # Initialize the data model
        self._load_model(data_dir / DATA_MODEL_PATH)
        self._process_model()

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

    @staticmethod
    def _validate_model(data_model: dict[str, Any]) -> None:
        """Validate the data model to ensure it follows the required naming conventions.

        Args:
            data_model: The data model to validate, containing definitions for entity/relation types and their properties.

        Raises:
            ValueError: If any entity/relation type or property name does not follow the naming conventions.
        """
        # Validate entity naming conventions
        for entity_name in data_model['entities']:
            if not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9]*', entity_name):
                raise ValueError(
                    f'Invalid entity name "{entity_name}". Entity names must start with a letter and contain only alphanumeric characters.',
                )
            if entity_name.lower() in ('document', 'chunk'):
                raise ValueError(f'Entity name "{entity_name}" is reserved for special entities and cannot be used')

        # Validate relation naming conventions
        for relation_name in data_model['relations']:
            if not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9]*', relation_name):
                raise ValueError(
                    f'Invalid relation name "{relation_name}". Relation names must start with a letter and contain only alphanumeric characters.',
                )
            if relation_name.lower() in ('chunkof', 'extractedfrom'):
                raise ValueError(
                    f'Relation name "{relation_name}" is reserved for special relations and cannot be used',
                )

        # Validate property naming conventions
        for object_name, object_info in (data_model['entities'] | data_model['relations']).items():
            for prop_name in object_info.get('properties', {}):
                if not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_]*', prop_name):
                    raise ValueError(
                        f'Invalid property name "{prop_name}" from "{object_name}". Property names must start with a letter and contain only alphanumeric characters and underscores.',
                    )
                if prop_name.lower() == 'extracted_from':
                    raise ValueError(
                        f'Property name "{prop_name}" from "{object_name}" is reserved for special properties and cannot be used',
                    )

    def _process_model(self) -> None:
        """Process the data model to prepare entity and relation types for use in the engine."""
        # Keep only the included entities and relations
        included_entities = self._parameters.get('included_entities', list(self._entities.keys()))
        self._entities = {key: value for key, value in self._entities.items() if key in included_entities}
        included_relations = self._parameters.get('included_relations', list(self._relations.keys()))
        self._relations = {key: value for key, value in self._relations.items() if key in included_relations}

        # Materialize relations
        self._materialize_relation_model()

        # Add special entities
        special_entities = {
            'Document': {'special_entity': True, 'properties': {'name': {'type': 'string'}}},
            'Chunk': {'special_entity': True, 'properties': {'text': {'type': 'string'}}},
        }
        self._entities.update(special_entities)

        # Add special relations
        special_relations = {
            'ChunkOf': {'special_relation': True, 'properties': {'chunk_number': {'type': 'integer'}}},
            'ExtractedFrom': {'special_relation': True},
        }
        self._relations.update(special_relations)

    def _materialize_relation_model(self) -> None:
        """Materialize the relation model to create specific relation types between entity type pairs."""
        # Iterate over the relation model and build materialized relations
        core_entities = list(self.core_entities.keys())
        for relation_name, relation_info in self._relations.items():
            origin_entities = relation_info['origin']
            target_entities = relation_info['target']
            relation_info['properties'] = relation_info.get('properties', {})

            # Create a materialized relation for each combination of origin and target
            for origin in origin_entities:
                for target in target_entities:
                    # Materialize relation info
                    materialized_relation_info = dict(relation_info.items())
                    materialized_relation_info['origin'] = origin
                    materialized_relation_info['target'] = target
                    materialized_relation_info['relation_name'] = relation_name
                    materialized_relation_name = f'{origin}_{relation_name}_{target}'

                    # Check if the origin/target are Core Entities
                    origin_core_entity = origin in core_entities
                    target_core_entity = target in core_entities

                    # Special Case: No relations allowed between Core Entities
                    if origin_core_entity and target_core_entity:
                        continue

                    # Special Case: Relations with Core Entities
                    if origin_core_entity:
                        materialized_relation_info['core_origin'] = True
                    elif target_core_entity:
                        materialized_relation_info['core_target'] = True

                    # Store materialized relation info
                    self._materialized_relations[materialized_relation_name] = materialized_relation_info

    @property
    def parameters(self) -> dict[str, Any]:
        """A dictionary containing the parameters of the data model."""
        return self._parameters

    @property
    def document_sets(self) -> list[str]:
        """A list of all document sets present in the data model."""
        return self._parameters.get('included_documents', [])

    @property
    def entities(self) -> dict[str, Any]:
        """A dictionary containing all regular entity types in the data model (core/special entities are excluded)."""
        return {
            key: value
            for key, value in self._entities.items()
            if not value.get('core_entity', False) and not value.get('special_entity', False)
        }

    @property
    def core_entities(self) -> dict[str, Any]:
        """A dictionary containing all core entity types in the data model."""
        return {key: value for key, value in self._entities.items() if value.get('core_entity', False)}

    @property
    def special_entities(self) -> dict[str, Any]:
        """A dictionary containing all special entity types in the data model."""
        return {key: value for key, value in self._entities.items() if value.get('special_entity', False)}

    @property
    def relations(self) -> dict[str, Any]:
        """A dictionary containing all regular relation types in the data model (special relations are excluded)."""
        return {key: value for key, value in self._relations.items() if not value.get('special_relation', False)}

    @property
    def special_relations(self) -> dict[str, Any]:
        """A dictionary containing all special relation types in the data model."""
        return {key: value for key, value in self._relations.items() if value.get('special_relation', False)}

    @property
    def materialized_relations(self) -> dict[str, Any]:
        """A dictionary containing all materialized relation types between entity type pairs."""
        return self._materialized_relations
