"""Implements prompt generation for data extraction tasks.

This module provides functions to generate prompts for extracting entities/relations from text.
"""

from pathlib import Path
from typing import Any

from wukong_engine.core.data_model import DataModel
from wukong_engine.utils.file_utils import delete_dir_contents, save_text_data

# Prompt templates for entity and relation extraction

# Entity extraction
ENTITY_PROMPT = """You are {ROLE}.
You will receive a document related to {CONTEXT}.
{NAME} is defined as an entity that satisfies the following description: {DESCRIPTION}.
Your goal is to identify all the {NAME} entities present in the document, where each entity satisfies the previously mentioned description.
The output must be a new JSON object that contains all the identified {NAME} entities and their respective properties, using the following structure:

{{
    "results": [ // a list of all the valid {NAME} entities found in the document
        {{{PROPERTIES}
        }}
    ]
}}

Please respect the above JSON structure, since it will be parsed automatically later.
Make sure that all mentioned properties are present in the output object.
Do not use the example property values as placeholders. If you cannot identify a property for an entity, consider that property's value as "NULL" instead.
Make sure that each {NAME} entity found has a value different from "NULL" for the "{PRIMARY_KEY}" property, otherwise remove the entity from the output.
Make sure that each {NAME} entity found satisfies the provided description, otherwise remove the entity from the output.
Use the {LANGUAGE} language for the output."""

# Core Entity extraction
CORE_ENTITY_PROMPT = """You are {ROLE}.
You will receive a document related to {CONTEXT}.
{NAME} is defined as an entity that satisfies the following description: {DESCRIPTION}.
The given document can be modeled as a {NAME} entity, which represents the information contained in it.
Your goal is to identify and extract relevant information present in the document about the {NAME} entity.
The output must be a new JSON object that contains all the identified properties for the {NAME} entity, using the following structure:

{{{PROPERTIES}
}}

Please respect the above JSON structure, since it will be parsed automatically later.
Make sure that all mentioned properties are present in the output object.
Do not use the example property values as placeholders. If you cannot identify a property, consider that property's value as "NULL" instead.
Use the {LANGUAGE} language for the output."""

# Relation extraction
RELATION_PROMPT = """You are {ROLE}.
You will be given:
- A JSON with a list of entities of type {ORIGIN} (denoted between tags '==LIST 1 START==' and '==LIST 1 END==').
- A JSON with a list of entities of type {TARGET} (denoted between tags '==LIST 2 START==' and '==LIST 2 END==').
- A document (denoted between tags '==DOCUMENT START==' and '==DOCUMENT END=='). This document is related to {CONTEXT}.

{NAME} is defined as a relation that satisfies the following description: {DESCRIPTION}.
Your goal is to identify all the {NAME} relations present in the document between the entities of both lists.
For each origin {ORIGIN} entity 'E1' from the first list, and each target {TARGET} entity 'E2' from the second list, check if the document is stating a {NAME} relation between E1 and E2, where the relation satisfies the previously mentioned description.
The output must be a new JSON object that contains all the identified {NAME} relations and their respective properties, using the following structure:

{{
    "results": [ // a list of all the {NAME} relations between {ORIGIN} and {TARGET} entities
        {{
            "_OriginId": Value of type 'string'. // The "_ObjectId" property of the origin entity from the first list. If not found, this value must be "NULL".
            "_TargetId": Value of type 'string'. // The "_ObjectId" property of the target entity from the second list. If not found, this value must be "NULL".{PROPERTIES}
        }}
    ]
}}

Please respect the above JSON structure, since it will be parsed automatically later.
Make sure that all mentioned properties are present in the output object.
Do not use the example property values as placeholders. If you cannot identify a property for a relation, consider that property's value as "NULL" instead.
Make sure that each {NAME} relation found contains values different from "NULL" for the "_OriginId" and "_TargetId" properties, otherwise remove the relation from the output.
Make sure that each {NAME} relation found satisfies the provided description, otherwise remove the relation from the output.
Use the {LANGUAGE} language."""

# Relation extraction, when the origin and target are the same
SINGLE_ENTITY_RELATION_PROMPT = """You are {ROLE}.
You will be given:
- A JSON with a list of entities of type {ORIGIN} (denoted between tags '==LIST START==' and '==LIST END==').
- A document (denoted between tags '==DOCUMENT START==' and '==DOCUMENT END=='). This document is related to {CONTEXT}.

{NAME} is defined as a relation that satisfies the following description: {DESCRIPTION}.
Your goal is to identify all the {NAME} relations present in the document between the entities from the list.
For each origin {ORIGIN} entity 'E1' and each target {TARGET} entity 'E2' from the list, check if the document is stating a {NAME} relation between E1 and E2, where the relation satisfies the previously mentioned description.
The output must be a new JSON object that contains all the identified {NAME} relations and their respective properties, using the following structure:

{{
    "results": [ // a list of all the {NAME} relations between {ORIGIN} and {TARGET} entities
        {{
            "_OriginId": Value of type 'string'. // The "_ObjectId" property of the origin entity from the list. If not found, this value must be "NULL".
            "_TargetId": Value of type 'string'. // The "_ObjectId" property of the target entity from the list. If not found, this value must be "NULL".{PROPERTIES}
        }}
    ]
}}

Please respect the above JSON structure, since it will be parsed automatically later.
Make sure that all mentioned properties are present in the output object.
Do not use the example property values as placeholders. If you cannot identify a property for a relation, consider that property's value as "NULL" instead.
Make sure that each {NAME} relation found contains values different from "NULL" for the "_OriginId" and "_TargetId" properties, otherwise remove the relation from the output.
Make sure that each {NAME} relation found satisfies the provided description, otherwise remove the relation from the output.
Use the {LANGUAGE} language."""

# Relation extraction, when the origin is a Core Entity
CORE_ENTITY_ORIGIN_RELATION_PROMPT = """You are {ROLE}.
You will be given:
- A JSON with a list of entities of type {TARGET} (denoted between tags '==LIST START==' and '==LIST END==').
- A document (denoted between tags '==DOCUMENT START==' and '==DOCUMENT END=='). This document is related to {CONTEXT}.

{ORIGIN} is defined as an entity that satisfies the following description: {CORE_ENTITY_DESCRIPTION}.
The given document can be modeled as a {ORIGIN} entity, which represents the information contained in it.
{NAME} is defined as a relation that satisfies the following description: {DESCRIPTION}.
Your goal is to identify all the {NAME} relations present in the document between the {ORIGIN} entity that represents the contents from the document and the {TARGET} entities from the list.
With 'E1' as the origin {ORIGIN} entity, and for each target {TARGET} entity 'E2' from the list, check if the document is stating a {NAME} relation between E1 and E2, where the relation satisfies the previously mentioned description.
The output must be a new JSON object that contains all the identified {NAME} relations and their respective properties, using the following structure:

{{
    "results": [ // a list of all the {NAME} relations between the {ORIGIN} entity and the {TARGET} entities
        {{
            "_TargetId": Value of type 'string'. // The "_ObjectId" property of the target entity from the list. If not found, this value must be "NULL".{PROPERTIES}
        }}
    ]
}}

Please respect the above JSON structure, since it will be parsed automatically later.
Make sure that all mentioned properties are present in the output object.
Do not use the example property values as placeholders. If you cannot identify a property for a relation, consider that property's value as "NULL" instead.
Make sure that each {NAME} relation found has a value different from "NULL" for the "_TargetId" property, otherwise remove the relation from the output.
Make sure that each {NAME} relation found satisfies the provided description, otherwise remove the relation from the output.
Use the {LANGUAGE} language."""

# Relation extraction, when the target is a Core Entity
CORE_ENTITY_TARGET_RELATION_PROMPT = """You are {ROLE}.
You will be given:
- A JSON with a list of entities of type {ORIGIN} (denoted between tags '==LIST START==' and '==LIST END==').
- A document (denoted between tags '==DOCUMENT START==' and '==DOCUMENT END=='). This document is related to {CONTEXT}.

{TARGET} is defined as an entity that satisfies the following description: {CORE_ENTITY_DESCRIPTION}.
The given document can be modeled as a {TARGET} entity, which represents the information contained in it.
{NAME} is defined as a relation that satisfies the following description: {DESCRIPTION}.
Your goal is to identify all the {NAME} relations present in the document between the {ORIGIN} entities from the list and the {TARGET} entity that represents the contents from the document.
For each origin {ORIGIN} entity 'E1' from the list, and with 'E2' as the target {TARGET} entity, check if the document is stating a {NAME} relation between E1 and E2, where the relation satisfies the previously mentioned description.
The output must be a new JSON object that contains all the identified {NAME} relations and their respective properties, using the following structure:

{{
    "results": [ // a list of all the {NAME} relations between {ORIGIN} entities and the {TARGET} entity
        {{
            "_OriginId": Value of type 'string'. // The "_ObjectId" property of the origin entity from the list. If not found, this value must be "NULL".{PROPERTIES}
        }}
    ]
}}

Please respect the above JSON structure, since it will be parsed automatically later.
Make sure that all mentioned properties are present in the output object.
Do not use the example property values as placeholders. If you cannot identify a property for a relation, consider that property's value as "NULL" instead.
Make sure that each {NAME} relation found has a value different from "NULL" for the "_OriginId" property, otherwise remove the relation from the output.
Make sure that each {NAME} relation found satisfies the provided description, otherwise remove the relation from the output.
Use the {LANGUAGE} language."""


def generate_prompts(prompts_dir: Path) -> None:
    """Generate prompts for extracting entities and relations based on the data model.

    Builds extraction prompts for each entity and relation type included in the data model.

    Args:
        prompts_dir: The path to the directory where the generated prompts will be saved.
    """
    # Create and clean output directory structure
    prompts_dir.mkdir(parents=True, exist_ok=True)
    delete_dir_contents(prompts_dir)
    entity_prompts_dir = prompts_dir / 'entities/'
    entity_prompts_dir.mkdir(parents=True, exist_ok=True)
    relation_prompts_dir = prompts_dir / 'relations/'
    relation_prompts_dir.mkdir(parents=True, exist_ok=True)

    # Get data model
    data_model = DataModel()

    # Get role (if none provided, the LLM is a knowledge graph expert)
    default_role = 'An AI expert specialized in knowledge graph extraction'
    role = data_model.parameters.get('role', default_role).removesuffix('.')

    # Get context and input language (if none provided, the LLM must figure out the context)
    context = data_model.parameters.get('context', 'A context you must identify').removesuffix('.')
    context += f'. The text is written in {data_model.parameters.get("input_language", "english").lower()}'

    # Store general information about the data model
    model_config = {
        'role': role,
        'context': context,
        'language': data_model.parameters.get('output_language', 'english').lower(),
    }

    # Build entity prompts
    entity_model = data_model.entities | data_model.core_entities
    for entity_name, entity_info in entity_model.items():
        build_entity_prompt(entity_name, entity_info, model_config, entity_prompts_dir)

    # Build relation prompts
    relation_model = data_model.relations
    for relation_name, relation_info in relation_model.items():
        build_relation_prompt(relation_name, relation_info, entity_model, model_config, relation_prompts_dir)


def build_entity_prompt(
    entity_name: str,
    entity_info: dict[str, Any],
    general_info: dict[str, str],
    entity_prompts_dir: Path,
) -> None:
    """Build a prompt to be used for extracting a specific entity type.

    Args:
        entity_name: The name of the entity type to extract.
        entity_info: A dictionary containing information about the entity type, following the data model specifications.
        general_info: A dictionary containing general information about the data model parameters.
        entity_prompts_dir: The path to the directory where the generated entity type prompt will be saved.
    """
    # General entity info
    core_entity = entity_info.get('core_entity', False)  # If True, the entity is represented by an entire document
    primary_key = entity_info['primary_key'] if not core_entity else ''  # Primary key: only for non-core entities

    # Gather property info
    properties = []
    for property_name, property_info in entity_info.get('properties', {}).items():
        prop_dict = {
            'name': property_name,
            'type': property_info.get('type', 'string'),
            'description': property_info['description'].removesuffix('.'),
            'example': property_info.get('example', '').removesuffix('.'),
            'options': property_info.get('options', []),
        }
        properties.append(prop_dict)

    # Properties object string
    prop_object_str = ''
    for prop in properties:
        spaces = 4 if core_entity else 12
        example_str = f'For example: "{prop["example"]}". ' if prop['example'] else ''
        options_str = 'Must take one of the following values:' if prop['options'] else ''
        for option in prop['options']:
            options_str += f' "{option}",'
        values_str = f'{options_str[:-1]}. ' if options_str else example_str
        not_found_str = (
            'If not found, this value must be "NULL". Do not use the example property values as placeholders.'
        )
        prop_object_str += f'\n{spaces * " "}"{prop["name"]}": Value of type \'{prop["type"]}\'. // {prop["description"]}. {values_str}{not_found_str}'

    # Select prompt template
    prompt_template = CORE_ENTITY_PROMPT if core_entity else ENTITY_PROMPT

    # Build LLM prompt for the entity
    prompt = prompt_template.format(
        ROLE=general_info['role'],
        CONTEXT=general_info['context'],
        NAME=f"'{entity_name}'",
        DESCRIPTION=entity_info['description'].removesuffix('.'),
        PRIMARY_KEY=primary_key,
        PROPERTIES=prop_object_str,
        LANGUAGE=general_info['language'],
    )

    # Save prompt
    save_text_data(prompt, entity_prompts_dir / f'{entity_name}.txt')


def build_relation_prompt(
    relation_name: str,
    relation_info: dict[str, Any],
    entity_model: dict[str, Any],
    general_info: dict[str, str],
    relation_prompts_dir: Path,
) -> None:
    """Build a prompt to be used for extracting a specific relation type.

    Args:
        relation_name: The name of the relation type to extract.
        relation_info: A dictionary containing information about the relation type, following the data model specifications.
        entity_model: A dictionary containing all entity types from the data model and their relevant information.
        general_info: A dictionary containing general information about the data model parameters.
        relation_prompts_dir: The path to the directory where the generated relation type prompt will be saved.
    """
    # Gather property info
    properties = []
    for property_name, property_info in relation_info.get('properties', {}).items():
        prop_dict = {
            'name': property_name,
            'type': property_info.get('type', 'string'),
            'description': property_info['description'].removesuffix('.'),
            'example': property_info.get('example', '').removesuffix('.'),
            'options': property_info.get('options', []),
        }
        properties.append(prop_dict)

    # Properties object string
    prop_object_str = ''
    for prop in properties:
        spaces = 12
        example_str = f'For example: "{prop["example"]}". ' if prop['example'] else ''
        options_str = 'Must take one of the following values:' if prop['options'] else ''
        for option in prop['options']:
            options_str += f' "{option}",'
        values_str = f'{options_str[:-1]}. ' if options_str else example_str
        not_found_str = (
            'If not found, this value must be "NULL". Do not use the example property values as placeholders.'
        )
        prop_object_str += f'\n{spaces * " "}"{prop["name"]}": Value of type \'{prop["type"]}\'. // {prop["description"]}. {values_str}{not_found_str}'

    # Create a relation prompt for each combination of origin and target
    origin_entities = relation_info['origin']
    target_entities = relation_info['target']
    for origin in origin_entities:
        for target in target_entities:
            # Check if the origin/target are Core Entities
            origin_core_entity = entity_model[origin].get('core_entity', False)
            target_core_entity = entity_model[target].get('core_entity', False)

            # No relations between Core Entities
            if origin_core_entity and target_core_entity:
                continue

            # No prompt required if the relation is marked to bypass the LLM
            core_entity_relation = origin_core_entity or target_core_entity
            if core_entity_relation and relation_info.get('bypass_LLM', False):
                continue

            # Select prompt template
            prompt_template = RELATION_PROMPT if origin != target else SINGLE_ENTITY_RELATION_PROMPT

            # Special Case: Relations with Core Entities
            core_entity_description = ''
            if origin_core_entity:
                core_entity_description = entity_model[origin]['description'].removesuffix('.')
                prompt_template = CORE_ENTITY_ORIGIN_RELATION_PROMPT
            elif target_core_entity:
                core_entity_description = entity_model[target]['description'].removesuffix('.')
                prompt_template = CORE_ENTITY_TARGET_RELATION_PROMPT

            # Build LLM prompt for the relation
            prompt = prompt_template.format(
                ROLE=general_info['role'],
                CONTEXT=general_info['context'],
                ORIGIN=f"'{origin}'",
                TARGET=f"'{target}'",
                NAME=f"'{relation_name}'",
                DESCRIPTION=relation_info['description'].removesuffix('.'),
                CORE_ENTITY_DESCRIPTION=core_entity_description,
                PROPERTIES=prop_object_str,
                LANGUAGE=general_info['language'],
            )

            # Save prompt
            materialized_relation_name = f'{origin}_{relation_name}_{target}'
            save_text_data(prompt, relation_prompts_dir / f'{materialized_relation_name}.txt')
