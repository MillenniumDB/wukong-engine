"""Provides data processing utilities for data extraction.

This module defines functions and classes to clean, validate,
and deduplicate data that represents entities and relations.
"""

import logging
from typing import Any

from datasketch import MinHash, MinHashLSH
from fuzzywuzzy import fuzz, process

from wukong_engine.utils.text_utils import normalize_text

# Logging
logger = logging.getLogger(__name__)

# Configuration
DEBUG_STRING_MATCHER = True  # Set to True to enable debug mode for string matching


class BasicStringMatcher:
    """A basic string similarity index that matches identical elements.

    Matches normalized elements based on exact string equality.

    Attributes:
        _element_keys: A set of all element keys contained in the index.
        _element_index: A mapping of elements to their keys, allowing for quick element lookups.
    """

    def __init__(self) -> None:
        """Initialize the index as an empty structure."""
        # Set of element keys in the index
        self._element_keys = set()

        # Inverted mapping: Element -> Key
        self._element_index = {}

    def __contains__(self, element_key: str) -> bool:
        """Check if an element key is in the index.

        Args:
            element_key: The element key to check for.

        Returns:
            True if the element key is present, False otherwise.
        """
        return element_key in self._element_keys

    def __repr__(self) -> str:
        """Get a string representation of the index.

        Returns:
            A string representation of the index, showing all elements and their keys.
        """
        str_repr = 'BasicStringMatcher:\n\n{'
        for element, key in self._element_index.items():
            str_repr += f"'{key}': '{element}', "
        if str_repr[-2:] == ', ':
            str_repr = str_repr[:-2]
        return str_repr + '}\n'

    def insert(self, element_key: str, element: str) -> None:
        """Insert an element into the index.

        Args:
            element_key: A unique key that identifies the element to insert.
            element: The element to insert into the index.
        """
        # Insert the new element into the inverted mapping
        self._element_index[normalize_text(element)] = element_key

        # Insert the element key into the set of keys
        self._element_keys.add(element_key)

    def query(self, element: str) -> str | None:
        """Query the index for an element match.

        Args:
            element: The element to query in the index.

        Returns:
            The matching element key if a match was found, otherwise None.
        """
        # Look for the exact element in the inverted mapping
        return self._element_index.get(normalize_text(element), None)

    def clear(self) -> None:
        """Clear the index by removing all elements and keys."""
        # Clear the inverted mapping and the set of keys
        self._element_index.clear()
        self._element_keys.clear()


class FuzzyStringMatcher:
    """A string similarity index that matches similar elements using MinHashLSH and fuzzy matching.

    Matches normalized elements considering two levels of similarity:

    1. Confident Match: Elements that are very similar. Found by using a hash-based index (MinHashLSH) with a high threshold.
    2. Potential Match: Elements that are somewhat similar. Found by using a hash-based index (MinHashLSH) with a lower threshold.

    The matching process works as follows:

    1. When an element is inserted, it is first normalized and hashed using the MinHash algorithm.
    2. The inserted element is added to two separate MinHashLSH indices, one for confident matches and the other for potential matches.
    3. When querying, the element to query is also normalized and hashed.
    4. The MinHashLSH index for confident matches is queried first, returning the best confident match if found.
    5. The best confident match is determined by comparing the similarity scores of all confident matches using a fuzzy matching algorithm.
    6. If no confident matches are found, the MinHashLSH index for potential matches is queried.
    7. The best potential match is determined in the same way as with confident matches.
    8. If no potential matches are found, the index returns None.

    Attributes:
        _element_mapping: A mapping of element keys to their corresponding elements.
        _lsh_confident: A MinHashLSH index used to query for confident string matches.
        _lsh_potential: A MinHashLSH index used to query for potential string matches.
    """

    def __init__(
        self,
        *,
        confident_threshold: float = 0.7,
        potential_threshold: float = 0.4,
        similarity_cutoff: int = 90,
        num_perm: int = 128,
        debug: bool = DEBUG_STRING_MATCHER,
    ) -> None:
        """Initialize the index with the specified parameters.

        Args:
            confident_threshold: The similarity threshold for confident matches. The higher the threshold, the more similar the elements must be to be considered a confident match.
            potential_threshold: The similarity threshold for potential matches. The higher the threshold, the more similar the elements must be to be considered a potential match.
            similarity_cutoff: The minimum similarity score to consider for potential matches. Any potential match below this score will be ignored.
            num_perm: The number of permutation functions used in the MinHash algorithm for the MinHashLSH indices.
            debug: Whether to enable debug mode for string matching. If active, all non-exact matches will be logged as debug information.
        """
        # Mapping for Key -> Element in the index
        self._element_mapping = {}

        # Locality Sensitive Hashing (LSH) index for string matching
        # Confident LSH (threshold=0.7), Potential LSH (threshold=0.4)
        self._similarity_cutoff = similarity_cutoff
        self._num_permutations = num_perm
        self._lsh_confident = MinHashLSH(threshold=confident_threshold, num_perm=num_perm)
        self._lsh_potential = MinHashLSH(threshold=potential_threshold, num_perm=num_perm)

        # Parameter for debugging string matching
        self._debug = debug

    def __contains__(self, element_key: str) -> bool:
        """Check if an element key is in the index.

        Args:
            element_key: The element key to check for.

        Returns:
            True if the element key is present, False otherwise.
        """
        return element_key in self._element_mapping

    def __repr__(self) -> str:
        """Get a string representation of the index.

        Returns:
            A string representation of the index, showing all elements and their keys.
        """
        str_repr = 'FuzzyStringMatcher:\n\n{'
        for key, element in self._element_mapping.items():
            str_repr += f"'{key}': '{element}', "
        if str_repr[-2:] == ', ':
            str_repr = str_repr[:-2]
        return str_repr + '}\n'

    @staticmethod
    def _calculate_text_similarity(value_a: str, value_b: str) -> int:
        """Calculate the similarity score between two strings.

        Uses the Levenshtein Distance metric to calculate different string similarity ratios,
        and then combines them using a weighted average to obtain a final string similarity score.
        The final score ranges from 0 to 100, where higher scores indicate more similar strings.

        Args:
            value_a: The first string to compare.
            value_b: The second string to compare.

        Returns:
            The final similarity score between the two strings.
        """
        # Calculate similarity ratios based on Levenshtein distance
        ratio = fuzz.ratio(value_a, value_b)
        token_set_ratio = fuzz.token_set_ratio(value_a, value_b)

        # Combine the ratios and return the final similarity score
        # Good Ratios (Normal/Token Set): (0.5|0.5) >= 93, (0.6|0.4) >= 92, (0.7|0.3) >= 91, (0.8|0.2) >= 90
        # Tested and fine-tuned with different examples to work well with name-like values
        return round(ratio * 0.8 + token_set_ratio * 0.2)

    def insert(self, element_key: str, element: str) -> None:
        """Insert an element into the index.

        Args:
            element_key: A unique key that identifies the element to insert.
            element: The element to insert into the index.
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
        """Query the index for an element match.

        Args:
            element: The element to query in the index.

        Returns:
            The matching element key if a match was found, otherwise None.
        """
        # Apply MinHash to the element
        clean_value = normalize_text(element)
        element_hash = MinHash(num_perm=self._num_permutations)
        for word in clean_value.split():
            element_hash.update(word.encode('utf-8'))

        # Query the LSH for confident matches
        matches = self._lsh_confident.query(element_hash)

        # Confident matches found
        if matches:
            # If there are multiple matches, look for the best one by checking similarity with fuzzy matching
            match_key = str(matches[0])
            if len(matches) > 1:
                matches = {match_key: self._element_mapping[match_key] for match_key in matches}
                *_, match_key = process.extractOne(clean_value, matches, scorer=self._calculate_text_similarity) or (
                    match_key,
                )

            # Return key for the best match
            if self._debug:
                match_value = self._element_mapping[match_key]
                if match_value != clean_value:
                    logger.debug(f'Confident String Match: "{match_value}", "{clean_value}"')
            return match_key

        # Query the LSH for potential matches
        matches = self._lsh_potential.query(element_hash)

        # Potential matches found
        if matches:
            # Look for the best match by checking similarity with fuzzy matching
            # The cut-off score was tested with different examples to work well with name-like values
            matches = {match_key: self._element_mapping[match_key] for match_key in matches}
            best_match = process.extractOne(
                clean_value,
                matches,
                scorer=self._calculate_text_similarity,
                score_cutoff=self._similarity_cutoff,
            )

            # String match with enough similarity was detected
            if best_match:
                *_, match_key = best_match

                # Return key for the best match
                if self._debug:
                    match_value = self._element_mapping[match_key]
                    if match_value != clean_value:
                        logger.debug(f'Potential String Match: "{match_value}", "{clean_value}"')
                return match_key

        # No matches found
        return None

    def clear(self) -> None:
        """Clear the index by removing all elements and keys."""
        # Remove all elements from the LSH and clear the mapping
        for key in self._element_mapping:
            self._lsh_confident.remove(key)
            self._lsh_potential.remove(key)
        self._element_mapping.clear()


def clean_entities(entities: list[dict[str, Any]], entity_info: dict[str, Any]) -> list[dict[str, Any]]:
    """Clean entities and remove invalid ones.

    Cleans entities by checking their properties and validating them against the data model specifications.

    Args:
        entities: A list of dictionaries representing entities of a specific type.
        entity_info: A dictionary containing information about the entity type, following the data model specifications.

    Returns:
        A list of dictionaries representing all the valid entities remaining after the cleaning process.
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


def clean_relations(relations: list[dict[str, Any]], relation_info: dict[str, Any]) -> list[dict[str, Any]]:
    """Clean relations and remove invalid ones.

    Cleans relations by checking their origin/target entities as well as their properties,
    validating them against the data model specifications.

    Args:
        relations: A list of dictionaries representing relations of a specific type between entities.
        relation_info: A dictionary containing information about the relation type, following the data model specifications.

    Returns:
        A list of dictionaries representing all the valid relations remaining after the cleaning process.
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
        if valid_required_properties and is_valid_relation(relation, relation_info):
            cleaned_relations.append(relation)

    # Return the list of cleaned relations
    return cleaned_relations


def merge_duplicate_entities(entities: list[dict[str, Any]], entity_info: dict[str, Any]) -> list[dict[str, Any]]:
    """Detect duplicate entities and merge them together.

    Deduplicates entities based on their primary key, by making use of a string similarity index.
    The specific behavior of this process is managed through the data model specifications.

    Args:
        entities: A list of dictionaries representing entities of a specific type.
        entity_info: A dictionary containing information about the entity type, following the data model specifications.

    Returns:
        A list of dictionaries representing all the unique entities remaining after the deduplication process.
    """
    # Special Case: Core entities are always unique
    if entity_info.get('core_entity', False):
        return entities

    # Special Case: Duplicate detection is disabled
    if not entity_info.get('detect_duplicates', True):
        return entities

    # Choose duplicate matcher based on data model option
    duplicate_matcher = BasicStringMatcher()
    duplicates_to_find = entity_info.get('duplicates', 'all').lower().strip()
    if duplicates_to_find in ('all', 'near', 'similar'):
        duplicate_matcher = FuzzyStringMatcher()

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
            original_entity[key] = choose_property_value(
                original_entity[key],
                entity[key],
                entity_info.get('properties', {})[key],
            )

        # Gather all references to partial entities
        original_entity['_ReferenceIds'].extend(entity['_ReferenceIds'])

    # Return the list of unique entities
    return unique_entities


def merge_hybrid_entities(
    core_entities: list[dict[str, Any]],
    entities: list[dict[str, Any]],
    entity_info: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Merge hybrid entities with their corresponding core entity, deduplicating them where necessary.

    Deduplication is performed over the primary key, by making use of a string similarity index.
    The specific behavior of this process is managed through the data model specifications.

    Args:
        core_entities: A list of dictionaries representing core entities of a specific hybrid type.
        entities: A list of dictionaries representing entities of a specific hybrid type.
        entity_info: A dictionary containing information about the hybrid entity type, following the data model specifications.

    Returns:
        A tuple containing two elements
            - A list of dictionaries representing all the unique hybrid entities remaining after the merging process.
            - A mapping from old to new ObjectIds for the hybrid entities that were duplicated with a core entity.
    """
    # Special Case: Duplicate detection is disabled
    if not entity_info.get('detect_duplicates', True):
        return entities, {}

    # Choose duplicate matcher based on data model option
    duplicate_matcher = BasicStringMatcher()
    duplicates_to_find = entity_info.get('duplicates', 'all').lower().strip()
    if duplicates_to_find in ('all', 'near', 'similar'):
        duplicate_matcher = FuzzyStringMatcher()

    # Insert all core entities into the duplicate matcher
    for idx, entity in enumerate(core_entities):
        pk_value = entity[entity_info['primary_key']]
        duplicate_matcher.insert(str(idx), pk_value)

    # Iterate over all hybrid entities and look for duplicates with the core entities
    unique_entities = []  # List to store unique hybrid entities
    hybrid_mapping = {}  # Mapping from old to new ObjectIds for hybrid entities
    for entity in entities:
        # Query the duplicate matcher to find duplicates for the primary key
        pk_value = entity[entity_info['primary_key']]
        match_idx = duplicate_matcher.query(pk_value)

        # No duplicates found, consider the hybrid entity unique
        if match_idx is None:
            unique_entities.append(entity)
            continue  # Next entity

        # Duplicate found, add mapping to the ObjectId from the original core entity
        hybrid_mapping[entity['_ObjectId']] = core_entities[int(match_idx)]['_ObjectId']

    # Return the list of unique hybrid entities and the hybrid mapping
    return unique_entities, hybrid_mapping


def merge_duplicate_relations(relations: list[dict[str, Any]], relation_info: dict[str, Any]) -> list[dict[str, Any]]:
    """Detect duplicate relations and merge them together.

    Deduplicates relations with the same pair of origin/target entities,
    by making use of a string similarity index applied over their primary keys (if present).
    The specific behavior of this process is managed through the data model specifications.

    Args:
        relations: A list of dictionaries representing relations of a specific type between entities.
        relation_info: A dictionary containing information about the relation type, following the data model specifications.

    Returns:
        A list of dictionaries representing all the unique relations remaining after the deduplication process.
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
    duplicate_matcher = BasicStringMatcher()
    duplicates_to_find = relation_info.get('duplicates', 'all').lower().strip()
    if duplicates_to_find in ('all', 'near', 'similar'):
        duplicate_matcher = FuzzyStringMatcher()

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
                original_relation[key] = choose_property_value(
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


def is_null_value(property_value: str) -> bool:
    """Check whether a property value is considered null/empty.

    Args:
        property_value: The property value to check.

    Returns:
        True if the property value is null/empty, False otherwise.
    """
    return normalize_text(property_value) in ('null', 'none', 'nan', 'n/a', '')


def is_valid_value(property_value: str, property_info: dict[str, Any]) -> bool:
    """Check whether a property value is valid, according to the data model specifications.

    Args:
        property_value: The property value to check.
        property_info: A dictionary containing information about the property, following the data model specifications.

    Returns:
        True if the property value is valid, False otherwise.
    """
    # Check if the value is null
    if is_null_value(property_value):
        return False

    # Check if the value is restricted to certain options
    value_options = property_info.get('options', [])
    if value_options and property_value not in value_options:
        logger.debug(f'Invalid Property Value: "{property_value}". Must be one of {value_options}.')
        return False

    return True


def is_valid_relation(relation: dict[str, Any], relation_info: dict[str, Any]) -> bool:
    """Check whether a relation is valid, according to the data model specifications and available entities.

    Args:
        relation: A dictionary representing a relation of a specific type between a pair of entities.
        relation_info: A dictionary containing information about the relation type, following the data model specifications.

    Returns:
        True if the relation is valid, False otherwise.
    """
    # Check if OriginId and TargetId are defined
    if relation['_OriginId'] == 'NULL' or relation['_TargetId'] == 'NULL':
        return False

    # Check if OriginId and TargetId are properly formatted
    origin_id_split = relation['_OriginId'].removesuffix('A').split('_')
    target_id_split = relation['_TargetId'].removesuffix('A').split('_')
    n_components = 2
    if len(origin_id_split) != n_components or len(target_id_split) != n_components:
        return False

    # Check if OriginId and TargetId contain valid components
    rel_origin_name, rel_origin_number = origin_id_split
    rel_target_name, rel_target_number = target_id_split
    origin_entity_name = relation_info['origin'].removeprefix('@')
    target_entity_name = relation_info['target'].removeprefix('@')
    if rel_origin_name != origin_entity_name or rel_target_name != target_entity_name:
        return False  # Entity name is not correct
    return rel_origin_number.isdigit() and rel_target_number.isdigit()  # Entity number is a valid integer


def choose_property_value(current_value: Any, new_value: Any, property_info: dict[str, Any]) -> Any:
    """Choose the best fitting property value between the current one and a potential new value.

    Args:
        current_value: The current value of the property.
        new_value: The new value to consider for the property.
        property_info: A dictionary containing information about the property, following the data model specifications.

    Returns:
        The best fitting property value between the current one and the new value, according to the data model specifications.
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
    """Group relations by their origin/target entity pair.

    Args:
        relations: A list of dictionaries representing relations of a specific type between entities.

    Returns:
        A dictionary where the keys are relation IDs (OriginId_TargetId) and the values are lists of indices of relations
        that share the same origin and target entities.
    """
    grouped_relations = {}
    for idx, relation in enumerate(relations):
        relation_id = f'{relation["_OriginId"]}_{relation["_TargetId"]}'  # RelationId: (OriginId, TargetId)
        if relation_id not in grouped_relations:
            grouped_relations[relation_id] = []
        grouped_relations[relation_id].append(idx)
    return grouped_relations
