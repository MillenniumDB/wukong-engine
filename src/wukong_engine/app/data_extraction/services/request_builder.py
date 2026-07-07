"""Request builders for extraction tasks."""

import logging
from types import MappingProxyType
from typing import Any, ClassVar, Protocol

from wukong_engine.app.data_extraction.elements import ExtractionJob, ExtractionRequest, ExtractionSpec
from wukong_engine.app.data_extraction.exceptions import ExtractionRequestBuildError
from wukong_engine.app.document_ingestion.ports import DocumentLoader
from wukong_engine.app.llm.elements.values import ReasoningEffort
from wukong_engine.core.documents.elements import Chunk, Document
from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.extraction.model.values import EntityRetrievalMode, RelationshipRetrievalMode
from wukong_engine.core.graph.model import (
    EntityField,
    EntityType,
    ExtractionConfig,
    Field,
    GraphModel,
    RelationshipField,
    RelationshipType,
)
from wukong_engine.core.graph.model.values import DataType

from .repository import EntityExtractionRepository, RelationshipExtractionRepository

# Logging
logger = logging.getLogger(__name__)

# Constants
# TODO: Test and set reasoning effort to None or a specific value best for extraction
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
            ContextLevel.DOCUMENT: 'For each of the following entity types, identify the single primary entity described by the source text'
            ' and extract its properties using all relevant information found throughout the text.',
            ContextLevel.CHUNK: 'For each of the following entity types, extract all matching entities found in the source text.',
        },
    )

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

        # Build extraction specification and request
        spec = ExtractionSpec(
            document_context=self._render_document_context(model.extraction_config),
            task=self._render_task(job),
            definitions=self._render_definitions(tuple(entity_types), job.context_ref.level),
            source_text=source_text,
            response_schema=self._generate_response_schema(tuple(entity_types), job.context_ref.level),
        )
        return ExtractionRequest(job, spec, reasoning_effort=ENTITY_EXTRACTION_EFFORT)

    def _render_document_context(self, extraction_config: ExtractionConfig) -> str:
        """Render the document context section."""
        document_context = f'Domain: {extraction_config.domain}'
        if extraction_config.language is not None:
            document_context += f'\nLanguage: {extraction_config.language.value}'
        return document_context

    def _render_task(self, job: ExtractionJob) -> str:
        """Render the task section."""
        task = self.TASK_INSTRUCTIONS.get(job.context_ref.level)
        if task is None:
            error = 'Failed to build extraction request: Invalid task instructions'
            logger.error(error)
            raise ExtractionRequestBuildError(error)
        task += '\nDo not extract an entity if a value cannot be determined from the source text for any of its Required Fields.'
        return task

    def _render_definitions(self, entity_types: tuple[EntityType, ...], context_level: ContextLevel) -> str:
        """Render the definitions section."""
        sections: list[str] = []
        for entity_type in sorted(entity_types, key=lambda e: e.name.value):
            section = self._render_entity_type(entity_type, context_level)
            if section is not None:
                sections.append(section)
        return '\n\n'.join(sections)

    def _render_entity_type(self, entity_type: EntityType, context_level: ContextLevel) -> str | None:
        """Render the definition for a single entity type if it participates in extraction."""
        # Get relevant fields for the context level, if there are none then skip this entity type
        fields_to_extract = entity_type.fields_for(context_level, EntityRetrievalMode.EXTRACT)
        if not fields_to_extract:
            return None

        # Basic info
        lines: list[str] = []
        lines.append(f'EntityType: {entity_type.name}\n')
        lines.append(entity_type.description)

        # Optional extraction-specific instructions
        instructions = entity_type.instructions.get(context_level)
        if instructions is not None:
            lines.append(instructions)

        # Fields
        required_field_names: list[str] = []
        fields: list[str] = []
        for field in sorted(fields_to_extract, key=lambda f: f.name.value):
            if field.required:
                required_field_names.append(f'- {field.name.value}')
            fields.extend(self._render_field(field, context_level))
        lines.append('\nRequired Fields:\n')
        lines.extend(required_field_names or ['None'])
        lines.append('\nFields:')
        lines.extend(fields)

        return '\n'.join(lines)

    def _render_field(self, field: EntityField, context_level: ContextLevel) -> list[str]:
        """Render the definition for a single field."""
        # Basic info
        lines: list[str] = []
        lines.append(f'\n- {field.name}\n')
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

        # Start with Entity Type name
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


# TODO: Complete
class RelationshipExtractionRequestBuilder(ExtractionRequestBuilder):
    """Request builder for relationship extraction tasks."""

    TASK_INSTRUCTIONS: ClassVar[str] = 'A'

    def __init__(self, repository: RelationshipExtractionRepository) -> None:
        """Initialize the request builder."""
        self._repository = repository

    def build(self, job: ExtractionJob, model: GraphModel) -> ExtractionRequest:
        """Build extraction request for a single job."""
        # Gather entity types for the job, ensuring they exist in the graph model
        relationship_types: list[RelationshipType] = []
        for name in self._repository.get_job_relationship_types(job):
            relationship_type = model.relationship_type(name)
            if relationship_type is None:
                error = f'Failed to build extraction request: RelationshipType "{name}" not found in graph model'
                logger.error(error)
                raise ExtractionRequestBuildError(error)
            relationship_types.append(relationship_type)

        # Build extraction specification and request
        spec = ExtractionSpec(
            document_context=self._render_document_context(model.extraction_config),
            task=self._render_task(),
            definitions=self._render_definitions(tuple(relationship_types)),
            source_text=self._repository.get_job_source_context(job).content,
            response_schema=self._generate_response_schema(tuple(relationship_types)),
        )
        return ExtractionRequest(job, spec, reasoning_effort=RELATIONSHIP_EXTRACTION_EFFORT)

    def _render_document_context(self, extraction_config: ExtractionConfig) -> str:
        """Render the document context section."""
        document_context = f'Domain: {extraction_config.domain}'
        if extraction_config.language is not None:
            document_context += f'\nLanguage: {extraction_config.language.value}'
        return document_context

    def _render_task(self) -> str:
        """Render the task section."""
        task = self.TASK_INSTRUCTIONS
        if task is None:
            error = 'Failed to build extraction request: Invalid task instructions'
            logger.error(error)
            raise ExtractionRequestBuildError(error)
        task += '\nDo not extract an entity if a value cannot be determined from the source text for any of its Required Fields.'
        return task

    def _render_definitions(self, relationship_types: tuple[RelationshipType, ...]) -> str:
        """Render the definitions section."""
        sections: list[str] = []
        for relationship_type in sorted(relationship_types, key=lambda e: e.name.value):
            section = self._render_relationship_type(relationship_type)
            if section is not None:
                sections.append(section)
        return '\n\n'.join(sections)

    def _render_relationship_type(self, relationship_type: RelationshipType) -> str | None:
        """Render the definition for a single entity type if it participates in extraction."""
        # Get relevant fields for the context level, if there are none then skip this entity type
        fields_to_extract = relationship_type.fields_for(RelationshipRetrievalMode.EXTRACT)
        if not fields_to_extract:
            return None

        # Basic info
        lines: list[str] = []
        lines.append(f'EntityType: {relationship_type.name}\n')
        lines.append(relationship_type.description)

        # Optional extraction-specific instructions
        instructions = relationship_type.instructions
        if instructions is not None:
            lines.append(instructions)

        # Fields
        required_field_names: list[str] = []
        fields: list[str] = []
        for field in sorted(fields_to_extract, key=lambda f: f.name.value):
            if field.required:
                required_field_names.append(f'- {field.name.value}')
            fields.extend(self._render_field(field))
        lines.append('\nRequired Fields:\n')
        lines.extend(required_field_names or ['None'])
        lines.append('\nFields:')
        lines.extend(fields)

        return '\n'.join(lines)

    def _render_field(self, field: RelationshipField) -> list[str]:
        """Render the definition for a single field."""
        # Basic info
        lines: list[str] = []
        lines.append(f'\n- {field.name}\n')
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

    def _generate_response_schema(self, relationship_types: tuple[RelationshipType, ...]) -> dict[str, Any]:
        """Generate a JSON schema for the expected structured response."""
        relationship_type_schemas: list[dict[str, Any]] = []
        for relationship_type in sorted(relationship_types, key=lambda e: e.name.value):
            rt_schema = self._generate_relationship_type_schema(relationship_type)
            if rt_schema is not None:
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
    def _generate_relationship_type_schema(relationship_type: RelationshipType) -> dict[str, Any] | None:
        """Generate a JSON schema for a single entity type."""
        # Get relevant fields for the context level, if there are none then skip this entity type
        fields_to_extract = relationship_type.fields_for(RelationshipRetrievalMode.EXTRACT)
        if not fields_to_extract:
            return None

        # Start with Relationship Type name
        properties: dict[str, Any] = {
            '_relationship_type': {
                'type': 'string',
                'const': relationship_type.name.value,
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
