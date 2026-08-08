"""Request builders for extraction tasks."""

import logging
from textwrap import dedent
from types import MappingProxyType
from typing import Any, ClassVar, Protocol

from wukong_engine.app.data_extraction.elements import (
    ExtractionJob,
    ExtractionRequest,
    ExtractionSpec,
    RelationshipExtractionRequestObjects,
)
from wukong_engine.app.data_extraction.exceptions import ExtractionRequestBuildError
from wukong_engine.app.document_ingestion.ports import DocumentLoader
from wukong_engine.app.llm.elements.values import ReasoningEffort
from wukong_engine.core.documents.elements import Chunk, Document
from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.extraction.model.values import EntityRetrievalMode, RelationshipRetrievalMode
from wukong_engine.core.graph.elements import Entity, EntityRef
from wukong_engine.core.graph.elements.values import EntityId
from wukong_engine.core.graph.model import (
    Endpoint,
    EntityField,
    EntityType,
    ExtractionConfig,
    Field,
    GraphModel,
    RelationshipField,
    RelationshipType,
)
from wukong_engine.core.graph.model.values import DataType, EntityTypeName

from .repository import EntityExtractionRepository, RelationshipExtractionRepository

# Logging
logger = logging.getLogger(__name__)

# Constants
ENTITY_EXTRACTION_EFFORT = ReasoningEffort.LOW
RELATIONSHIP_EXTRACTION_EFFORT = ReasoningEffort.LOW
MAX_DOCUMENT_TOKENS = 8000  # To avoid hitting LLM context window limits


def _generate_field_schema(field: Field) -> dict[str, Any]:
    """Generate a JSON schema for a single field."""
    # Data type
    schema: dict[str, Any] = {}
    schema['type'] = [_data_type_to_json(field.data_type), 'null']

    # Allowed values if specified
    if field.options:
        schema['enum'] = [*field.options, None]

    return schema


def _data_type_to_json(data_type: DataType) -> str:
    """Map a Python type to a JSON schema type."""
    match data_type:
        case DataType.STRING:
            return 'string'
        # case DataType.INTEGER:
        #     return 'integer'
        # case DataType.FLOAT:
        #     return 'number'
        # case DataType.BOOLEAN:
        #     return 'boolean'


class ExtractionRequestBuilder(Protocol):
    """Request builder for data extraction tasks."""

    def build(self, job: ExtractionJob, model: GraphModel) -> ExtractionRequest:
        """Build extraction request for a single job."""
        ...


class EntityExtractionRequestBuilder(ExtractionRequestBuilder):
    """Request builder for entity extraction tasks."""

    TASK_INSTRUCTIONS: ClassVar[MappingProxyType[ContextLevel, str]] = MappingProxyType(
        {
            ContextLevel.DOCUMENT: 'For each of the entity types defined, identify a single primary entity represented by the entire source text'
            ' and extract its field values using all relevant information found.',
            ContextLevel.CHUNK: 'For each of the entity types defined, extract all entities found in the source text.',
        },
    )

    TASK_CONSTRAINTS: ClassVar[str] = dedent("""
        Do not infer, invent, or guess field values.
        Do not extract an entity if any required field value cannot be determined from the source text.
    """).strip()

    def __init__(self, repository: EntityExtractionRepository, document_loader: DocumentLoader) -> None:
        """Initialize the request builder."""
        self._repository = repository
        self._document_loader = document_loader
        self.max_document_tokens = MAX_DOCUMENT_TOKENS

    def build(self, job: ExtractionJob, model: GraphModel) -> ExtractionRequest:
        """Build extraction request for a single job."""
        # Handle potential errors like missing documents
        try:
            source_text = self._get_source_text(self._repository.get_job_source_context(job))
        except Exception as exc:
            error = 'Failed to build extraction request: Could not load source document content'
            logger.error(error)
            raise ExtractionRequestBuildError(error) from exc

        # Gather entity types for the job, ensuring they exist in the graph model
        entity_types: list[EntityType] = []
        for name in self._repository.get_job_entity_types(job):
            entity_type = model.entity_type(name)
            if entity_type is None:
                error = f'Failed to build extraction request: EntityType "{name}" not found in graph model'
                logger.error(error)
                raise ExtractionRequestBuildError(error)
            entity_types.append(entity_type)

        # Build extraction specification
        spec = ExtractionSpec(
            document_context=self._render_document_context(model.extraction_config),
            task=self._render_task(job.context_ref.level),
            definitions=self._render_definitions(tuple(entity_types), job.context_ref.level),
            source_text=source_text,
            response_schema=self._generate_response_schema(tuple(entity_types), job.context_ref.level),
        )

        # Return the extraction request with the specified reasoning effort
        return ExtractionRequest(job, spec, reasoning_effort=ENTITY_EXTRACTION_EFFORT)

    def _render_document_context(self, extraction_config: ExtractionConfig) -> str:
        """Render the document context section."""
        document_context = f'Domain: {extraction_config.domain}'
        if extraction_config.language is not None:
            document_context += f'\nLanguage: {extraction_config.language.value}'
        return document_context

    def _render_task(self, context_level: ContextLevel) -> str:
        """Render the task section."""
        task = self.TASK_INSTRUCTIONS.get(context_level)
        if task is None:
            error = 'Failed to build extraction request: Invalid task instructions'
            logger.error(error)
            raise ExtractionRequestBuildError(error)
        task += f'\n{self.TASK_CONSTRAINTS}'
        return task

    def _render_definitions(self, entity_types: tuple[EntityType, ...], context_level: ContextLevel) -> str:
        """Render the definitions section."""
        definitions: list[str] = []

        # Entity types section
        ent_types: list[str] = []
        for entity_type in sorted(entity_types, key=lambda e: e.name.value):
            rendered_et = self._render_entity_type(entity_type, context_level)
            if rendered_et is not None:
                ent_types.append(rendered_et)

        # This cannot happen currently, this changes if LOAD is implemented
        if not ent_types:
            raise NotImplementedError(
                'No entity types to extract for the given context level, which can only happen if LOAD is implemented',
            )

        definitions.append(f'Entity Type Definitions\n{"-" * 23}\n\n' + '\n\n'.join(ent_types))

        return '\n\n'.join(definitions)

    def _render_entity_type(self, entity_type: EntityType, context_level: ContextLevel) -> str | None:
        """Render the definition for a single entity type."""
        # Get relevant fields for the context level, if there are none then skip this entity type
        fields_to_extract = entity_type.fields_for(context_level, EntityRetrievalMode.EXTRACT)
        if not fields_to_extract:
            return None

        # Basic info
        lines: list[str] = []
        lines.append(f'Entity Type: {entity_type.name}\n')
        lines.append(f'Description\n{entity_type.description}')

        # Optional extraction-specific instructions
        instructions = entity_type.instructions.get(context_level)
        if instructions is not None:
            lines.append(instructions)

        # Fields
        fields: list[str] = []
        for field in sorted(fields_to_extract, key=lambda f: f.name.value):
            fields.extend(self._render_field(field, context_level))
        lines.append('\nFields')
        lines.extend(fields)

        return '\n'.join(lines)

    def _render_field(self, field: EntityField, context_level: ContextLevel) -> list[str]:
        """Render the definition for a single field."""
        # Basic info
        lines: list[str] = []
        lines.append(f'\n- {field.name}')
        lines.append(f'  ({"Required" if field.required else "Optional"})')
        lines.append(f'  {field.description}')

        # Optional extraction-specific instructions
        instructions = field.instructions.get(context_level)
        if instructions is not None:
            lines.append(f'  {instructions}')

        # Optional examples
        if field.examples:
            lines.append('  Examples:')
            lines.extend(f'  - {example}' for example in field.examples)
        return lines

    def _get_source_text(self, source: Document | Chunk) -> str:
        """Get the relevant text from the source."""
        if isinstance(source, Document):
            loaded_doc = self._document_loader.load(source, max_tokens=self.max_document_tokens)
            text = loaded_doc.content
        else:
            text = source.content
        return text

    def _generate_response_schema(
        self,
        entity_types: tuple[EntityType, ...],
        context_level: ContextLevel,
    ) -> dict[str, Any]:
        """Generate a JSON schema for the expected structured response."""
        entity_type_schemas: list[dict[str, Any]] = []
        for entity_type in sorted(entity_types, key=lambda e: e.name.value):
            et_schema = self._generate_entity_type_schema(entity_type, context_level)
            if et_schema is not None:
                entity_type_schemas.append(et_schema)

        # This cannot happen currently, this changes if LOAD is implemented
        if not entity_type_schemas:
            raise NotImplementedError(
                'No entity types to extract for the given context level, which can only happen if LOAD is implemented',
            )

        return {
            'type': 'object',
            'properties': {
                'entities': {
                    'type': 'array',
                    'items': {
                        'anyOf': entity_type_schemas,
                    },
                },
            },
            'required': ['entities'],
            'additionalProperties': False,
        }

    @staticmethod
    def _generate_entity_type_schema(entity_type: EntityType, context_level: ContextLevel) -> dict[str, Any] | None:
        """Generate a JSON schema for a single entity type."""
        # Get relevant fields for the context level, if there are none then skip this entity type
        fields_to_extract = entity_type.fields_for(context_level, EntityRetrievalMode.EXTRACT)
        if not fields_to_extract:
            return None

        # Start with Entity Type Name
        properties: dict[str, Any] = {
            '_entity_type': {
                'type': 'string',
                'const': entity_type.name.value,
            },
        }

        # Add all relevant fields
        for field in sorted(fields_to_extract, key=lambda f: f.name.value):
            properties[field.name.value] = _generate_field_schema(field)

        return {
            'type': 'object',
            'properties': properties,
            'required': list(properties.keys()),
            'additionalProperties': False,
        }


class RelationshipExtractionRequestBuilder(ExtractionRequestBuilder):
    """Request builder for relationship extraction tasks."""

    TASK_INSTRUCTIONS: ClassVar[str] = dedent("""
        For each of the relationship types defined, extract all relationships found in the source text between the available entities.
        Use only the available entity IDs when assigning relationship endpoints.
        Do not infer, invent, or guess relationships or field values.
        Do not extract a relationship if any required field value cannot be determined from the source text.
    """).strip()

    def __init__(self, repository: RelationshipExtractionRepository) -> None:
        """Initialize the request builder."""
        self._repository = repository
        self._current_entity_count: int = 0  # Track the number of extracted entities for the current job (for temp IDs)
        self._entity_temp_to_ref: dict[str, EntityRef] = {}  # Mapping of temporary entity IDs to EntityRefs
        self._entity_true_to_temp_id: dict[EntityId, str] = {}  # Mapping of true EntityIds to temporary entity IDs

    def build(self, job: ExtractionJob, model: GraphModel) -> ExtractionRequest:
        """Build extraction request for a single job."""
        # Reset entity count and ID mappings for the current job
        self._current_entity_count = 0
        self._entity_temp_to_ref.clear()
        self._entity_true_to_temp_id.clear()

        # Ensure that all relationship types for the job exist in the graph model
        for name in self._repository.get_job_relationship_types(job):
            if model.relationship_type(name) is None:
                error = f'Failed to build extraction request: RelationshipType "{name}" not found in graph model'
                logger.error(error)
                raise ExtractionRequestBuildError(error)

        # Get the source chunk for the job
        source_chunk = self._repository.get_job_source_context(job)

        # Gather elements to build job definitions
        extraction_elements = self._repository.get_job_extraction_elements(job, model)

        # Build and store the entity ID mapping for the job
        self._build_entity_id_mappings(
            extraction_elements.parent_document_entities + extraction_elements.chunk_entities,
        )
        self._repository.set_job_entity_ref_mapping(job, self._entity_temp_to_ref)

        # Build extraction specification
        spec = ExtractionSpec(
            document_context=self._render_document_context(model.extraction_config),
            task=self._render_task(),
            definitions=self._render_definitions(extraction_elements),
            source_text=source_chunk.content,
            response_schema=self._generate_response_schema(extraction_elements.relationship_types),
        )

        # Return the extraction request with the specified reasoning effort
        return ExtractionRequest(job, spec, reasoning_effort=RELATIONSHIP_EXTRACTION_EFFORT)

    def _build_entity_id_mappings(self, entities: tuple[Entity, ...]) -> None:
        """Build mappings between temporary entity IDs and true EntityIds."""
        for entity in entities:
            if entity.id in self._entity_true_to_temp_id:
                continue  # Skip if the entity has already been assigned a temporary ID
            self._current_entity_count += 1
            temp_id = f'E{self._current_entity_count}'
            self._entity_temp_to_ref[temp_id] = entity.reference
            self._entity_true_to_temp_id[entity.id] = temp_id

    def _render_document_context(self, extraction_config: ExtractionConfig) -> str:
        """Render the document context section."""
        document_context = f'Domain: {extraction_config.domain}'
        if extraction_config.language is not None:
            document_context += f'\nLanguage: {extraction_config.language.value}'
        return document_context

    def _render_task(self) -> str:
        """Render the task section."""
        return self.TASK_INSTRUCTIONS

    def _render_definitions(self, elements: RelationshipExtractionRequestObjects) -> str:
        """Render the definitions section."""
        definitions: list[str] = []

        # Relationship types section
        rel_types = [
            self._render_relationship_type(rt) for rt in sorted(elements.relationship_types, key=lambda r: r.name.value)
        ]
        definitions.append(f'Relationship Type Definitions\n{"-" * 29}\n\n' + '\n\n'.join(rel_types))

        # Chunk entities section
        chunk_entities = self._render_available_entities(elements.chunk_entities)
        if chunk_entities:
            definitions.append(f'Available CHUNK Entities\n{"-" * 24}\n' + '\n'.join(chunk_entities))

        # Document entities section
        document_entities = self._render_available_entities(elements.parent_document_entities)
        if document_entities:
            definitions.append(f'Available DOCUMENT Entities\n{"-" * 27}\n' + '\n'.join(document_entities))

        return '\n\n'.join(definitions)

    def _render_relationship_type(self, relationship_type: RelationshipType) -> str:
        """Render the definition for a single relationship type."""
        # Basic info
        lines: list[str] = []
        lines.append(f'Relationship Type: {relationship_type.name}\n')
        lines.append(f'Description\n{relationship_type.description}')

        # Optional extraction-specific instructions
        instructions = relationship_type.instructions
        if instructions is not None:
            lines.append(instructions)

        # Endpoints
        endpoints: list[str] = []
        for endpoint in sorted(relationship_type.endpoints, key=lambda f: f.source.value + f.target.value):
            endpoints.extend(self._render_endpoint(endpoint))
        lines.append('\nValid Endpoints\n')
        lines.extend(endpoints)

        # Fields
        fields_to_extract = relationship_type.fields_for(RelationshipRetrievalMode.EXTRACT)
        fields: list[str] = []
        for field in sorted(fields_to_extract, key=lambda f: f.name.value):
            fields.extend(self._render_field(field))
        lines.append('\nFields')
        if not fields:
            lines.append('\n(NO Fields)')
        else:
            lines.extend(fields)

        return '\n'.join(lines)

    def _render_endpoint(self, endpoint: Endpoint) -> list[str]:
        """Render the definition for a single endpoint."""
        return [
            f'- {endpoint.source} ({pair.source_level.value}) -> {endpoint.target} ({pair.target_level.value})'
            for pair in endpoint.context_pairs
        ]

    def _render_field(self, field: RelationshipField) -> list[str]:
        """Render the definition for a single field."""
        # Basic info
        lines: list[str] = []
        lines.append(f'\n- {field.name}')
        lines.append(f'  ({"Required" if field.required else "Optional"})')
        lines.append(f'  {field.description}')

        # Optional extraction-specific instructions
        instructions = field.instructions
        if instructions is not None:
            lines.append(f'  {instructions}')

        # Optional examples
        if field.examples:
            lines.append('  Examples:')
            lines.extend(f'  - {example}' for example in field.examples)
        return lines

    def _render_available_entities(self, entities: tuple[Entity, ...]) -> list[str]:
        """Render the available entities subsection."""
        lines: list[str] = []

        # Group entities by type
        name_to_type: dict[EntityTypeName, EntityType] = {}
        entities_grouped_by_type: dict[EntityTypeName, list[Entity]] = {}
        for entity in sorted(entities, key=lambda e: e.id.content.bytes):
            name_to_type.setdefault(entity.type.name, entity.type)
            entities_grouped_by_type.setdefault(entity.type.name, []).append(entity)

        # Display entities grouped by type
        for entity_type_name, entities_of_type in sorted(entities_grouped_by_type.items(), key=lambda e: e[0].value):
            entity_type = name_to_type[entity_type_name]
            lines.append(f'\n{entity_type_name}')
            lines.append(entity_type.description)
            for entity in entities_of_type:
                lines.extend(self._render_entity(entity))

        return lines

    def _render_entity(self, entity: Entity) -> list[str]:
        """Render the definition for a single entity instance."""
        lines: list[str] = []

        # ID: Assign temporary ID
        temp_id = self._entity_true_to_temp_id[entity.id]
        lines.append(f'\nEntity ID: {temp_id}')

        # Primary Key
        pk_field, pk_value = entity.primary_key_property
        lines.append(f'{pk_field.name}: {pk_value}')

        # Properties
        for field, value in entity.required_properties.items():
            if field != pk_field:  # Avoid repeating the primary key property
                lines.append(f'{field.name}: {value}')
        for field, value in entity.optional_properties.items():
            lines.append(f'{field.name}: {value}')

        return lines

    def _generate_response_schema(self, relationship_types: tuple[RelationshipType, ...]) -> dict[str, Any]:
        """Generate a JSON schema for the expected structured response."""
        relationship_type_schemas: list[dict[str, Any]] = []
        for relationship_type in sorted(relationship_types, key=lambda r: r.name.value):
            rt_schema = self._generate_relationship_type_schema(relationship_type)
            relationship_type_schemas.append(rt_schema)
        return {
            'type': 'object',
            'properties': {
                'relationships': {
                    'type': 'array',
                    'items': {
                        'anyOf': relationship_type_schemas,
                    },
                },
            },
            'required': ['relationships'],
            'additionalProperties': False,
        }

    @staticmethod
    def _generate_relationship_type_schema(relationship_type: RelationshipType) -> dict[str, Any]:
        """Generate a JSON schema for a single relationship type."""
        # Start with Relationship Type Name and Endpoints
        properties: dict[str, Any] = {
            '_relationship_type': {
                'type': 'string',
                'const': relationship_type.name.value,
            },
            '_source_entity_id': {'type': 'string'},
            '_target_entity_id': {'type': 'string'},
        }

        # Add all relevant fields
        fields_to_extract = relationship_type.fields_for(RelationshipRetrievalMode.EXTRACT)
        for field in sorted(fields_to_extract, key=lambda f: f.name.value):
            properties[field.name.value] = _generate_field_schema(field)

        return {
            'type': 'object',
            'properties': properties,
            'required': list(properties.keys()),
            'additionalProperties': False,
        }
