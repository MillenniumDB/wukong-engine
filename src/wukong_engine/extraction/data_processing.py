import logging
from pathlib import Path
from typing import Any

from datasketch import MinHash, MinHashLSH
from fuzzywuzzy import fuzz, process

from wukong_engine.utils.file_utils import load_json_data
from wukong_engine.utils.text_utils import normalize_text

# Logging
logger = logging.getLogger(__name__)

# Configuration
DEBUG_DUPLICATE_MATCHER = True  # Set to True to enable debug mode for duplicate matching


class BasicDuplicateMatcher:
    """Match exact duplicates using basic string normalization"""

    def __init__(self) -> None:
        """_summary_"""
        # Set of element keys in the index
        self._element_keys = set()

        # Inverted mapping: Element -> Key
        self._element_index = {}

    def __contains__(self, element_key: str) -> bool:
        """Check if an element key is in the index

        Args:
            element_key: _description_

        Returns:
            _description_
        """
        return element_key in self._element_keys

    def __repr__(self) -> str:
        """String representation of the object

        Returns:
            _description_
        """
        str_repr = 'BasicDuplicateMatcher:\n\n{'
        for element, key in self._element_index.items():
            str_repr += f"'{key}': '{element}', "
        if str_repr[-2:] == ', ':
            str_repr = str_repr[:-2]
        return str_repr + '}\n'

    def insert(self, element_key: str, element: str) -> None:
        """Insert a new element into the index

        Args:
            element_key: _description_
            element: _description_
        """
        # Insert the new element into the inverted mapping
        self._element_index[normalize_text(element)] = element_key

        # Insert the element key into the set of keys
        self._element_keys.add(element_key)

    def query(self, element: str) -> str | None:
        """Query the index for exact matches

        Args:
            element: _description_

        Returns:
            _description_
        """
        # Look for the exact element in the inverted mapping
        return self._element_index.get(normalize_text(element), None)

    def clear(self) -> None:
        """Remove all elements from the index"""
        # Clear the inverted mapping and the set of keys
        self._element_index.clear()
        self._element_keys.clear()


class FuzzyDuplicateMatcher:
    """Match near-duplicates based on LSH and fuzzy matching"""

    def __init__(
        self,
        *,
        confident_threshold: float = 0.7,
        potential_threshold: float = 0.4,
        similarity_cutoff: int = 90,
        num_perm: int = 128,
        debug: bool = DEBUG_DUPLICATE_MATCHER,
    ) -> None:
        """_summary_

        Args:
            confident_threshold: _description_. Defaults to 0.7.
            potential_threshold: _description_. Defaults to 0.4.
            similarity_cutoff: _description_. Defaults to 90.
            num_perm: _description_. Defaults to 128.
            debug: _description_. Defaults to DEBUG_DUPLICATE_MATCHER.
        """
        # Mapping for Key -> Element in the index
        self._element_mapping = {}

        # Locality Sensitive Hashing (LSH) index for text deduplication
        # Confident LSH (threshold=0.7), Potential LSH (threshold=0.4)
        self._similarity_cutoff = similarity_cutoff
        self._num_permutations = num_perm
        self._lsh_confident = MinHashLSH(threshold=confident_threshold, num_perm=num_perm)
        self._lsh_potential = MinHashLSH(threshold=potential_threshold, num_perm=num_perm)

        # Parameter for debugging duplicate matching
        self._debug = debug

    def __contains__(self, element_key: str) -> bool:
        """Check if an element key is in the index

        Args:
            element_key: _description_

        Returns:
            _description_
        """
        return element_key in self._element_mapping

    def __repr__(self) -> str:
        """String representation of the object

        Returns:
            _description_
        """
        str_repr = 'FuzzyDuplicateMatcher:\n\n{'
        for key, element in self._element_mapping.items():
            str_repr += f"'{key}': '{element}', "
        if str_repr[-2:] == ', ':
            str_repr = str_repr[:-2]
        return str_repr + '}\n'

    @staticmethod
    def _calculate_text_similarity(value_a: str, value_b: str) -> int:
        """Calculate similarity between two string values

        Args:
            value_a: _description_
            value_b: _description_

        Returns:
            _description_
        """
        # Calculate similarity ratios based on Levenshtein distance
        ratio = fuzz.ratio(value_a, value_b)
        token_set_ratio = fuzz.token_set_ratio(value_a, value_b)

        # Combine the ratios and return the final similarity score
        # Good Ratios (Normal/Token Set): (0.5|0.5) >= 93, (0.6|0.4) >= 92, (0.7|0.3) >= 91, (0.8|0.2) >= 90
        # Tested and fine-tuned with different examples to work well with name-like values
        return round(ratio * 0.8 + token_set_ratio * 0.2)

    def insert(self, element_key: str, element: str) -> None:
        """Insert a new element into the LSH

        Args:
            element_key: _description_
            element: _description_
        """
        # Insert the new element into the internal mapping
        clean_value = normalize_text(element)
        self._element_mapping[element_key] = clean_value

        # Apply MinHash to the element
        element_hash = MinHash(num_perm=self._num_permutations)
        for word in clean_value.split():
            element_hash.update(word.encode('utf-8'))

        # Insert the hash into the LSH
        self._lsh_confident.insert(element_key, element_hash)
        self._lsh_potential.insert(element_key, element_hash)

    def query(self, element: str) -> str | None:
        """Query the LSH for potential near-duplicate matches

        Args:
            element: _description_

        Returns:
            _description_
        """
        # Apply MinHash to the element
        clean_value = normalize_text(element)
        element_hash = MinHash(num_perm=self._num_permutations)
        for word in clean_value.split():
            element_hash.update(word.encode('utf-8'))

        # Query the LSH for confident near-duplicate matches
        duplicate_matches = self._lsh_confident.query(element_hash)

        # Confident near-duplicates found
        if duplicate_matches:
            # If there are multiple matches, look for the best one by checking similarity with fuzzy matching
            match_key = str(duplicate_matches[0])
            if len(duplicate_matches) > 1:
                matches = {match_key: self._element_mapping[match_key] for match_key in duplicate_matches}
                *_, match_key = process.extractOne(clean_value, matches, scorer=self._calculate_text_similarity) or (
                    match_key,
                )

            # Return key for the best match
            if self._debug:
                match_value = self._element_mapping[match_key]
                if match_value != clean_value:
                    logger.debug(f'Confident Duplicate Match: "{match_value}", "{clean_value}"')
            return match_key

        # Query the LSH for potential near-duplicate matches
        duplicate_matches = self._lsh_potential.query(element_hash)

        # Potential near-duplicates found
        if duplicate_matches:
            # Look for the best match by checking similarity with fuzzy matching
            # The cut-off score was tested with different examples to work well with name-like values
            matches = {match_key: self._element_mapping[match_key] for match_key in duplicate_matches}
            best_match = process.extractOne(
                clean_value,
                matches,
                scorer=self._calculate_text_similarity,
                score_cutoff=self._similarity_cutoff,
            )

            # Near-duplicate with enough similarity was detected
            if best_match:
                *_, match_key = best_match

                # Return key for the best match
                if self._debug:
                    match_value = self._element_mapping[match_key]
                    if match_value != clean_value:
                        logger.debug(f'Potential Duplicate Match: "{match_value}", "{clean_value}"')
                return match_key

        # No duplicates found
        return None

    def clear(self) -> None:
        """Remove all elements from the LSH"""
        # Remove all elements from the LSH and clear the mapping
        for key in self._element_mapping:
            self._lsh_confident.remove(key)
            self._lsh_potential.remove(key)
        self._element_mapping.clear()


def clean_entities(entities: list[dict[str, Any]], entity_info: dict[str, Any]) -> list[dict[str, Any]]:
    """Clean entities and remove invalid ones

    Args:
        entities: _description_
        entity_info: _description_

    Returns:
        _description_
    """
    # Iterate over all entities and their properties
    cleaned_entities = []  # List to store cleaned entities
    for entity in entities:
        valid_entity = True
        for property_name, property_data in entity_info.get('properties', {}).items():
            # Get the property value and convert it to a string
            property_value = str(entity.get(property_name, 'NULL'))  # Get the property value
            if property_data.get('type', 'string') in ('integer', 'float', 'bool'):
                property_value = str(property_value)

            # Make sure all null/invalid values are detected
            if not is_valid_value(property_value, property_data):
                entity[property_name] = 'NULL'

                # Core entities are always valid, no matter the property values
                if entity_info.get('core_entity', False):
                    continue

                # If a required property is invalid, the entire entity is not valid
                if property_name == entity_info['primary_key'] or property_data.get('required', False):
                    valid_entity = False
                    break

        # Keep all valid entities
        if valid_entity:
            cleaned_entities.append(entity)

    # Return the list of cleaned entities
    return cleaned_entities


def clean_relations(
    relations: list[dict[str, Any]],
    relation_info: dict[str, Any],
    entity_stats_path: Path,
) -> list[dict[str, Any]]:
    """Clean relations and remove invalid ones

    Args:
        relations: _description_
        relation_info: _description_
        entity_stats_path: _description_

    Returns:
        _description_
    """
    # Iterate over all relations and their properties
    cleaned_relations = []  # List to store cleaned relations
    for relation in relations:
        valid_required_properties = True
        for property_name, property_data in relation_info.get('properties', {}).items():
            # Get the property value and convert it to a string
            property_value = str(relation.get(property_name, 'NULL'))  # Get the property value
            if property_data.get('type', 'string') in ('integer', 'float', 'bool'):
                property_value = str(property_value)

            # Make sure all null/invalid values are detected
            if not is_valid_value(property_value, property_data):
                relation[property_name] = 'NULL'

                # If a required property is invalid, the entire relation is not valid
                primary_key = relation_info.get('primary_key', '')
                if property_name == primary_key or property_data.get('required', False):
                    valid_required_properties = False
                    break

        # Only keep valid relations that contain valid required properties
        if valid_required_properties and is_valid_relation(relation, relation_info, entity_stats_path):
            cleaned_relations.append(relation)

    # Return the list of cleaned relations
    return cleaned_relations


def remove_duplicate_entities(entities: list[dict[str, Any]], entity_info: dict[str, Any]) -> list[dict[str, Any]]:
    """Remove duplicate entities

    Args:
        entities: _description_
        entity_info: _description_

    Returns:
        _description_
    """
    # Special Case: Core entities are always unique
    if entity_info.get('core_entity', False):
        return entities

    # Special Case: Duplicate detection is disabled
    if not entity_info.get('detect_duplicates', True):
        return entities

    # Choose duplicate matcher based on data model option
    duplicate_matcher = BasicDuplicateMatcher()
    duplicates_to_find = entity_info.get('duplicates', 'all').lower().strip()
    if duplicates_to_find in ('all', 'near', 'similar'):
        duplicate_matcher = FuzzyDuplicateMatcher()

    # Iterate over all entities and look for duplicates
    unique_entities = []  # List to store unique entities
    for idx, entity in enumerate(entities):
        # Query the duplicate matcher to find duplicates for the primary key
        pk_value = entity[entity_info['primary_key']]
        match_idx = duplicate_matcher.query(pk_value)

        # No duplicates found, consider the entity unique
        if match_idx is None:
            duplicate_matcher.insert(str(idx), pk_value)
            unique_entities.append(entity)
            continue  # Next entity

        # Duplicate found, merge with the existing entity
        original_entity = entities[int(match_idx)]  # Original entity that is a duplicate match

        # Merge the new entity with the original one
        for key in entity_info.get('properties', {}):
            original_entity[key] = merge_property_values(
                original_entity[key],
                entity[key],
                entity_info.get('properties', {})[key],
            )

        # Gather all references to partial entities
        original_entity['_ReferenceIds'].extend(entity['_ReferenceIds'])

    # Return the list of unique entities
    return unique_entities


def remove_duplicate_relations(relations: list[dict[str, Any]], relation_info: dict[str, Any]) -> list[dict[str, Any]]:
    """Remove duplicate relations

    Args:
        relations: _description_
        relation_info: _description_

    Returns:
        _description_
    """
    # Important parameters

    # Used for deduplication, if defined
    primary_key = relation_info.get('primary_key')

    # If force_unique is True, relations with the same RelationId are considered instant duplicates
    force_unique = relation_info.get('force_unique', False)

    # Special Case: Duplicate detection is disabled (and force_unique is False)
    if not relation_info.get('detect_duplicates', True) and not force_unique:
        return relations

    # Choose duplicate matcher based on data model option
    duplicate_matcher = BasicDuplicateMatcher()
    duplicates_to_find = relation_info.get('duplicates', 'all').lower().strip()
    if duplicates_to_find in ('all', 'near', 'similar'):
        duplicate_matcher = FuzzyDuplicateMatcher()

    # Group relations by their origin and target entities
    grouped_relations = group_relations(relations)

    # Iterate over all relation groups and look for duplicates
    unique_relations = []  # List to store unique relations
    for group_keys in grouped_relations.values():
        # Initial relation for the group
        initial_idx = group_keys[0]
        relation = relations[initial_idx]
        unique_relations.append(relation)  # Initial relation is always unique

        # If these conditions are met, setup the duplicate matcher for the group
        if primary_key and not force_unique:
            # Clear the duplicate matcher to start fresh for the new group
            duplicate_matcher.clear()

            # Store the initial primary key in the duplicate matcher
            pk_value = relation[primary_key]
            duplicate_matcher.insert(str(initial_idx), pk_value)

        # Iterate over current group of relations sharing the same OriginId and TargetId
        for idx in group_keys[1:]:
            # Current relation from the group
            relation = relations[idx]
            match_idx = initial_idx  # Initial relation is the default duplicate match

            # Check these conditions before deciding to merge
            if not force_unique:
                # Primary key is not defined: do not deduplicate
                if not primary_key:
                    # Consider the relation unique if at least one property is not NULL
                    if any(relation[prop] != 'NULL' for prop in relation_info.get('properties', {})):
                        unique_relations.append(relation)
                    continue  # Next relation

                # Primary key is defined: deduplicate
                # Query the duplicate matcher to find duplicates inside the potential duplicates group
                pk_value = relation[primary_key]
                match_idx = duplicate_matcher.query(pk_value)

                # No duplicates found, consider the relation unique
                if match_idx is None:
                    duplicate_matcher.insert(str(idx), pk_value)
                    unique_relations.append(relation)
                    continue  # Next relation

            # Duplicate found, merge with the existing relation
            original_relation = relations[int(match_idx)]  # Original relation that is a duplicate match

            # Merge the new relation with the original one
            for key in relation_info.get('properties', {}):
                original_relation[key] = merge_property_values(
                    original_relation[key],
                    relation[key],
                    relation_info.get('properties', {})[key],
                )

            # Gather all references to partial relations
            # (Skip if there are no properties, as no new information is provided by the duplicates)
            if len(relation_info.get('properties', {})) > 0:
                original_relation['_ReferenceIds'].extend(relation['_ReferenceIds'])

    # Return the list of unique relations
    return unique_relations


def is_null_value(value: str) -> bool:
    """Check if a property value is null

    Args:
        value: _description_

    Returns:
        _description_
    """
    return normalize_text(value) in ('null', 'none', 'nan', 'n/a', '')


def is_valid_value(value: str, property_info: dict[str, Any]) -> bool:
    """Check if a property value is valid

    Args:
        value: _description_
        property_info: _description_

    Returns:
        _description_
    """
    # Check if the value is null
    if is_null_value(value):
        return False

    # Check if the value is restricted to certain options
    value_options = property_info.get('options', [])
    if value_options and value not in value_options:
        logger.debug(f'Invalid Property Value: "{value}". Must be one of {value_options}.')
        return False

    return True


def is_valid_relation(relation: dict[str, Any], relation_info: dict[str, Any], entity_stats_path: Path) -> bool:
    """Check if a relation between two entities is valid

    Args:
        relation: _description_
        relation_info: _description_
        entity_stats_path: _description_

    Returns:
        _description_
    """
    # Check if OriginId and TargetId are defined
    if relation['_OriginId'] == 'NULL' or relation['_TargetId'] == 'NULL':
        return False

    # Check if OriginId and TargetId are properly formatted
    origin_id_split = relation['_OriginId'].split('_')
    target_id_split = relation['_TargetId'].split('_')
    n_components = 2
    if len(origin_id_split) != n_components or len(target_id_split) != n_components:
        return False

    # Check if OriginId and TargetId contain valid components
    rel_origin_name, rel_origin_number = origin_id_split
    rel_target_name, rel_target_number = target_id_split
    if rel_origin_name != relation_info['origin'] or rel_target_name != relation_info['target']:
        return False  # Entity name is not correct
    if not rel_origin_number.isdigit() or not rel_target_number.isdigit():
        return False  # Entity number is not a valid integer

    # Check if OriginId and TargetId are in the range of valid entities
    entity_stats = load_json_data(entity_stats_path)
    n_origin_entities = entity_stats[relation_info['origin']]['final_entities']
    n_target_entities = entity_stats[relation_info['target']]['final_entities']
    valid_origin_range = 1 <= int(rel_origin_number) <= n_origin_entities
    valid_target_range = 1 <= int(rel_target_number) <= n_target_entities
    return valid_origin_range and valid_target_range


def merge_property_values(current_value: Any, new_value: Any, property_info: dict[str, Any]) -> Any:
    """Decide a new property value based on the existing ones from duplicate objects

    Args:
        current_value: _description_
        new_value: _description_
        property_info: _description_

    Returns:
        _description_
    """
    property_value = str(current_value)
    candidate_value = str(new_value)
    data_type = property_info.get('type', 'string')  # Default to string if type is not specified
    if data_type in ('integer', 'float', 'bool'):
        pass

    # If both values are equal, return any of them
    if property_value == candidate_value:
        return property_value

    # If a value is 'NULL', keep the other one
    if property_value == 'NULL':
        return candidate_value
    if candidate_value == 'NULL':
        return property_value

    # If an example is present, keep the value that is most similar to it
    example_value = property_info.get('example')
    if example_value:
        # Choose best match based on Levenshtein distance similarity
        candidates = [property_value, candidate_value]
        closest_value, *_ = process.extractOne(example_value, candidates, scorer=fuzz.ratio) or (current_value,)
        return closest_value

    # If no example, keep the longest value (since it may be more descriptive)
    if len(candidate_value) > len(property_value):
        return candidate_value
    return property_value


def group_relations(relations: list[dict[str, Any]]) -> dict[str, list[int]]:
    """Group relations by their origin and target entities

    Args:
        relations: _description_

    Returns:
        _description_
    """
    grouped_relations = {}
    for idx, relation in enumerate(relations):
        relation_id = f'{relation["_OriginId"]}_{relation["_TargetId"]}'  # RelationId: (OriginId, TargetId)
        if relation_id not in grouped_relations:
            grouped_relations[relation_id] = []
        grouped_relations[relation_id].append(idx)
    return grouped_relations
