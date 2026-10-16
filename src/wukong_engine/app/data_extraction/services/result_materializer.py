"""Result materializers for extraction tasks."""

from typing import Any, Protocol

from wukong_engine.app.data_extraction.elements import ExtractionJob, ExtractionResult, MaterializedResult, Rejection
from wukong_engine.app.data_extraction.elements.values import RejectionReason, RejectionScope
from wukong_engine.app.data_extraction.ports import PKNormalizer
from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.extraction.model.values import EntityRetrievalMode, RelationshipRetrievalMode
from wukong_engine.core.knowledge.elements import Entity, Relationship
from wukong_engine.core.knowledge.elements.values import EntityId
from wukong_engine.core.knowledge.model import EntityType, KnowledgeModel, RelationshipType
from wukong_engine.core.knowledge.model.values import EntityTypeName, RelationshipTypeName
from wukong_engine.core.shared.regex_pattern import RegexPattern

from .repository import EntityExtractionRepository, RelationshipExtractionRepository


class ExtractionResultMaterializer(Protocol):
    """Materializer that converts raw extraction results into knowledge object instances."""

    def materialize(self, result: ExtractionResult, job: ExtractionJob, model: KnowledgeModel) -> MaterializedResult:
        """Materialize the extraction result into knowledge object instances.

        Extracted items that are malformed or don't match the knowledge model are skipped, and reported as rejections.

        Args:
            result: Raw LLM extraction result to materialize.
            job: Extraction job that produced the result.
            model: Knowledge model used to resolve and validate types and fields.

        Returns:
            The valid knowledge objects built from the result, and the rejections.
        """
        ...


def _object_rejection(reason: RejectionReason, type_name: object, field_name: str | None = None) -> Rejection:
    """Build the rejection of a whole extracted object.

    Args:
        reason: Why the object is rejected.
        type_name: Type name of the object as returned by the LLM, or None if it returned none.
        field_name: Name of the field the rejection is about, if any.

    Returns:
        A rejection of ``OBJECT`` scope.
    """
    return Rejection(RejectionScope.OBJECT, reason, str(type_name) if type_name is not None else None, field_name)


def _invalid_value_reason(
    value: object,
    options: tuple[str, ...],
    regex: RegexPattern | None,
) -> RejectionReason | None:
    """Check a non-null extracted value against its field's allowed options and regex.

    Args:
        value: Extracted value to check.
        options: Allowed values of the field. Empty if any value is allowed.
        regex: Pattern the value must match, or None if there is none.

    Returns:
        Why the value is invalid, or None if it is valid. Options are checked before the regex.
    """
    if options and value not in options:
        return RejectionReason.INVALID_OPTION
    if regex is not None and not regex.match(str(value)):
        return RejectionReason.REGEX_MISMATCH
    return None


class EntityExtractionResultMaterializer(ExtractionResultMaterializer):
    """Materializer that converts raw extraction results into entity instances."""

    def __init__(self, repository: EntityExtractionRepository, pk_normalizer: PKNormalizer) -> None:
        """Initialize the materializer with necessary dependencies.

        Args:
            repository: Repository used to look up the entity types assigned to a job.
            pk_normalizer: Normalizer applied to primary key values before computing entity identities.
        """
        self._repository = repository
        self._pk_normalizer = pk_normalizer

    def materialize(
        self,
        result: ExtractionResult,
        job: ExtractionJob,
        model: KnowledgeModel,
    ) -> MaterializedResult[Entity]:
        """Materialize the extraction result into entity instances.

        Items under the result's ``entities`` key are skipped when their type is unknown or not assigned to the job,
        a required property is missing or invalid, or their primary key doesn't normalize. Invalid optional properties
        are unset instead. At document level, only the first valid entity of each type is kept, since a
        document-level type stands for the document itself; a later one with the same identity is a repetition of it
        and is kept for merging. Each skipped item, and each value unset in a kept item, is reported as a rejection.

        Args:
            result: Raw LLM extraction result to materialize.
            job: Extraction job that produced the result.
            model: Knowledge model used to resolve and validate entity types and fields.

        Returns:
            The valid entities built from the result, and the rejections.
        """
        extracted_entities = result.data.get('entities', [])
        materialized_entities: list[Entity] = []
        rejections: list[Rejection] = []
        document_entities: dict[EntityTypeName, EntityId] = {}  # First valid entity of each type, at document level
        for extracted in extracted_entities:
            # Get entity type
            job_types = set(self._repository.get_job_entity_types(job))
            entity_type = self._materialize_entity_type(extracted, job_types, model)
            if entity_type is None:
                rejections.append(_object_rejection(RejectionReason.UNKNOWN_TYPE, extracted.get('_entity_type')))
                continue
            type_name = entity_type.name.value

            # Assemble properties
            properties: dict[str, Any] = {}

            # Add constant properties
            properties.update(
                self._materialize_properties(
                    extracted,
                    entity_type,
                    job.context_ref.level,
                    EntityRetrievalMode.DEFAULT,
                ),
            )

            # Add extracted properties
            properties.update(
                self._materialize_properties(
                    extracted,
                    entity_type,
                    job.context_ref.level,
                    EntityRetrievalMode.EXTRACT,
                ),
            )

            # Validate properties, unsetting invalid optional values, and skip materialization if a required one is
            # missing or invalid
            validated, field_rejections = self._validate_properties(properties, entity_type, job.context_ref.level)
            if validated is None:
                rejections.extend(field_rejections)
                continue
            properties = validated

            # Normalize PK value and skip materialization if invalid
            pk_name = entity_type.primary_key.value
            normalized_pk = self._pk_normalizer.normalize(properties[pk_name])
            if normalized_pk is None:
                rejections.append(_object_rejection(RejectionReason.INVALID_PRIMARY_KEY, type_name, pk_name))
                continue

            # Materialize full entity instance
            entity = Entity.from_extraction(entity_type, properties, normalized_pk)

            # At document level, a different entity of a type already returned is not the document's own entity
            if job.context_ref.level == ContextLevel.DOCUMENT:
                first = document_entities.setdefault(entity_type.name, entity.id)
                if first.content != entity.id.content:
                    rejections.append(_object_rejection(RejectionReason.EXTRA_DOCUMENT_ENTITY, type_name))
                    continue

            # Keep the entity; values unset during validation only count once the entity is kept
            materialized_entities.append(entity)
            rejections.extend(field_rejections)

        return MaterializedResult(tuple(materialized_entities), tuple(rejections))

    def _materialize_entity_type(
        self,
        data: dict[str, Any],
        job_types: set[EntityTypeName],
        model: KnowledgeModel,
    ) -> EntityType | None:
        """Materialize the entity type from extracted data.

        Args:
            data: Single extracted item, carrying its type name under ``_entity_type``.
            job_types: Entity types assigned to the job that produced the item.
            model: Knowledge model used to resolve the type name.

        Returns:
            The entity type, or None if it is missing, invalid, unknown to the model, or not assigned to the job.
        """
        try:
            extracted_et_name = data.get('_entity_type')

            # Missing entity type in extracted data
            if extracted_et_name is None:
                return None

            # Get EntityType instance from knowledge model
            et_name = EntityTypeName(str(extracted_et_name))
            entity_type = model.entity_type(et_name)

            # Valid entity type found in knowledge model and job types
            if entity_type is not None and entity_type.name in job_types:
                return entity_type
        except ValueError:
            return None  # Invalid entity type name in extracted data

    def _materialize_properties(
        self,
        data: dict[str, Any],
        entity_type: EntityType,
        context_level: ContextLevel,
        retrieval_mode: EntityRetrievalMode,
    ) -> dict[str, Any]:
        """Materialize the entity properties obtained through a given retrieval mode.

        Extracted values are stringified; fields with no extracted value fall back to their default for the context
        level, and fields that end up null are omitted.

        Args:
            data: Single extracted item holding the extracted field values.
            entity_type: Entity type whose fields are materialized.
            context_level: Context level of the job, which selects the applicable fields and defaults.
            retrieval_mode: Retrieval mode of the fields to materialize.

        Returns:
            Mapping from field name to value. Empty for the ``SKIP`` retrieval mode.
        """
        # Skipped fields should not be materialized
        if retrieval_mode == EntityRetrievalMode.SKIP:
            return {}

        # Materialize properties according to the retrieval mode
        properties: dict[str, Any] = {}
        for field in entity_type.fields_for(context_level, retrieval_mode):
            value = None

            # For extracted fields, assign the extracted value when it exists in the data
            if retrieval_mode == EntityRetrievalMode.EXTRACT:
                value = data.get(field.name.value)

            # Assign default value when it corresponds to a constant field or when the extracted value is null
            value = str(value) if value is not None else field.default_value.get(context_level)

            # If the assigned value is not null, add it to the materialized properties
            if value is not None:
                properties[field.name.value] = value

        return properties

    def _validate_properties(
        self,
        properties: dict[str, Any],
        entity_type: EntityType,
        context_level: ContextLevel,
    ) -> tuple[dict[str, Any] | None, tuple[Rejection, ...]]:
        """Validate the materialized properties against the entity type definition.

        Only extracted fields are checked, against their required flag, allowed options, and regex. An invalid value
        of a required field (which includes the primary key) rejects the entity, since the entity is incomplete
        without it. An invalid value of an optional field only rejects the value: the field is unset, without falling
        back to its default, so that the property is absent rather than asserted.

        Args:
            properties: Materialized properties to validate.
            entity_type: Entity type defining the field constraints.
            context_level: Context level of the job, which selects the applicable fields and regexes.

        Returns:
            The properties without the invalid optional values, or None if a required field is missing or invalid;
            and the rejections: the one that rejects the entity, or else one per unset value.
        """
        type_name = entity_type.name.value
        validated = dict(properties)
        unset: list[Rejection] = []
        for field in entity_type.fields_for(context_level, EntityRetrievalMode.EXTRACT):
            field_name = field.name.value
            value = validated.get(field_name)
            if value is None:
                # Required fields must be present and not null
                if field.required:
                    return None, (_object_rejection(RejectionReason.MISSING_VALUE, type_name, field_name),)
                continue

            # Allowed values must be respected when options are defined, and the regex pattern when one is defined
            reason = _invalid_value_reason(value, field.options, field.regex.get(context_level))
            if reason is not None:
                if field.required:
                    return None, (_object_rejection(reason, type_name, field_name),)
                del validated[field_name]
                unset.append(Rejection(RejectionScope.VALUE, reason, type_name, field_name))

        return validated, tuple(unset)


class RelationshipExtractionResultMaterializer(ExtractionResultMaterializer):
    """Materializer that converts raw extraction results into relationship instances."""

    def __init__(self, repository: RelationshipExtractionRepository, pk_normalizer: PKNormalizer) -> None:
        """Initialize the materializer with necessary dependencies.

        Args:
            repository: Repository used to look up a job's relationship types and resolve its entity references.
            pk_normalizer: Normalizer applied to primary key values when the relationship identity requires one.
        """
        self._repository = repository
        self._pk_normalizer = pk_normalizer

    def materialize(
        self,
        result: ExtractionResult,
        job: ExtractionJob,
        model: KnowledgeModel,
    ) -> MaterializedResult[Relationship]:
        """Materialize the extraction result into relationship instances.

        Items under the result's ``relationships`` key are skipped when their type is unknown or not assigned to the
        job, their endpoints don't resolve to a valid endpoint of the type (or form a self-loop on an irreflexive
        type), a required property is missing or invalid, or a required primary key is missing or doesn't normalize.
        Invalid optional properties are unset instead. Each skipped item, and each value unset in a kept item, is
        reported as a rejection.

        Args:
            result: Raw LLM extraction result to materialize.
            job: Extraction job that produced the result.
            model: Knowledge model used to resolve and validate relationship types, fields, and endpoints.

        Returns:
            The valid relationships built from the result, and the rejections.
        """
        extracted_relationships = result.data.get('relationships', [])
        materialized_relationships: list[Relationship] = []
        rejections: list[Rejection] = []
        for extracted in extracted_relationships:
            # Get relationship type
            job_types = set(self._repository.get_job_relationship_types(job))
            relationship_type = self._materialize_relationship_type(extracted, job_types, model)
            if relationship_type is None:
                rejections.append(_object_rejection(RejectionReason.UNKNOWN_TYPE, extracted.get('_relationship_type')))
                continue
            type_name = relationship_type.name.value

            # Get source and target entity IDs
            endpoint = self._materialize_endpoint(extracted, relationship_type, job, model)
            if isinstance(endpoint, RejectionReason):
                rejections.append(_object_rejection(endpoint, type_name))
                continue
            source, target = endpoint

            # Assemble properties
            properties: dict[str, Any] = {}

            # Add constant properties
            properties.update(
                self._materialize_properties(
                    extracted,
                    relationship_type,
                    RelationshipRetrievalMode.DEFAULT,
                ),
            )

            # Add extracted properties
            properties.update(
                self._materialize_properties(
                    extracted,
                    relationship_type,
                    RelationshipRetrievalMode.EXTRACT,
                ),
            )

            # Validate properties, unsetting invalid optional values, and skip materialization if a required one is
            # missing or invalid
            validated, field_rejections = self._validate_properties(properties, relationship_type)
            if validated is None:
                rejections.extend(field_rejections)
                continue
            properties = validated

            # If the identity policy uses a Primary Key, normalize the PK value and skip materialization if invalid
            normalized_pk = None
            if relationship_type.identity_policy.requires_primary_key:
                pk_field = relationship_type.primary_key
                pk_name = pk_field.value if pk_field is not None else None
                if pk_name is None or pk_name not in properties:
                    rejections.append(_object_rejection(RejectionReason.MISSING_VALUE, type_name, pk_name))
                    continue
                normalized_pk = self._pk_normalizer.normalize(properties[pk_name])
                if normalized_pk is None:
                    rejections.append(_object_rejection(RejectionReason.INVALID_PRIMARY_KEY, type_name, pk_name))
                    continue

            # Materialize full relationship instance; values unset during validation only count once it is kept
            relationship = Relationship.from_extraction(relationship_type, source, target, properties, normalized_pk)
            materialized_relationships.append(relationship)
            rejections.extend(field_rejections)

        return MaterializedResult(tuple(materialized_relationships), tuple(rejections))

    def _materialize_relationship_type(
        self,
        data: dict[str, Any],
        job_types: set[RelationshipTypeName],
        model: KnowledgeModel,
    ) -> RelationshipType | None:
        """Materialize the relationship type from extracted data.

        Args:
            data: Single extracted item, carrying its type name under ``_relationship_type``.
            job_types: Relationship types assigned to the job that produced the item.
            model: Knowledge model used to resolve the type name.

        Returns:
            The relationship type, or None if it is missing, invalid, unknown to the model, or not assigned to the
            job.
        """
        try:
            extracted_rt_name = data.get('_relationship_type')

            # Missing relationship type in extracted data
            if extracted_rt_name is None:
                return None

            # Get RelationshipType instance from knowledge model
            rt_name = RelationshipTypeName(str(extracted_rt_name))
            relationship_type = model.relationship_type(rt_name)

            # Valid relationship type found in knowledge model and job types
            if relationship_type is not None and relationship_type.name in job_types:
                return relationship_type
        except ValueError:
            return None  # Invalid relationship type name in extracted data

    def _materialize_endpoint(
        self,
        data: dict[str, Any],
        relationship_type: RelationshipType,
        job: ExtractionJob,
        model: KnowledgeModel,
    ) -> tuple[EntityId, EntityId] | RejectionReason:
        """Materialize the source and target entity IDs.

        The extracted ``_source_entity_id`` and ``_target_entity_id`` are temporary IDs local to the job's prompt;
        they are capitalized and mapped back to the job's entity references.

        Args:
            data: Single extracted item holding the temporary source and target IDs.
            relationship_type: Relationship type whose endpoint definitions the pair must match.
            job: Extraction job whose entity references the temporary IDs belong to.
            model: Knowledge model used to resolve the context levels of the referenced entities.

        Returns:
            The source and target entity IDs, or the reason they are rejected: either ID is missing or unknown, the
            pair doesn't match an endpoint of the relationship type, or the type is irreflexive and both IDs refer to
            the same entity.
        """
        # Get source and target temporary entity IDs from extracted data
        source_id = data.get('_source_entity_id')
        target_id = data.get('_target_entity_id')

        # Missing temporary entity IDs in extracted data
        if source_id is None or target_id is None:
            return RejectionReason.MISSING_ENDPOINT

        # Normalize temporary entity IDs
        source_id = str(source_id).capitalize()
        target_id = str(target_id).capitalize()

        # Map the temporary IDs back to EntityRef instances
        source_ref = self._repository.get_entity_ref_for_job(job, source_id)
        target_ref = self._repository.get_entity_ref_for_job(job, target_id)

        # Invalid EntityRef instances
        if source_ref is None or target_ref is None:
            return RejectionReason.UNRESOLVED_ENDPOINT

        # Get context levels for source and target refs
        source_ctx = self._repository.get_job_entity_ref_context_levels(job, source_ref, model)
        target_ctx = self._repository.get_job_entity_ref_context_levels(job, target_ref, model)

        # Endpoint references do not match any endpoint defined in the relationship type
        if not relationship_type.is_valid_endpoint(
            source_ref.entity_type_name,
            source_ctx,
            target_ref.entity_type_name,
            target_ctx,
        ):
            return RejectionReason.INVALID_ENDPOINT

        # Irreflexive types can't relate an entity to itself; compared by content, since that identifies the entity
        if relationship_type.irreflexive and source_ref.entity_id.content == target_ref.entity_id.content:
            return RejectionReason.SELF_LOOP

        # Return valid endpoint
        return source_ref.entity_id, target_ref.entity_id

    def _materialize_properties(
        self,
        data: dict[str, Any],
        relationship_type: RelationshipType,
        retrieval_mode: RelationshipRetrievalMode,
    ) -> dict[str, Any]:
        """Materialize the relationship properties obtained through a given retrieval mode.

        Extracted values are stringified; fields with no extracted value fall back to their default, and fields
        that end up null are omitted.

        Args:
            data: Single extracted item holding the extracted field values.
            relationship_type: Relationship type whose fields are materialized.
            retrieval_mode: Retrieval mode of the fields to materialize.

        Returns:
            Mapping from field name to value.
        """
        # Materialize properties according to the retrieval mode
        properties: dict[str, Any] = {}
        for field in relationship_type.fields_for(retrieval_mode):
            value = None

            # For extracted fields, assign the extracted value when it exists in the data
            if retrieval_mode == RelationshipRetrievalMode.EXTRACT:
                value = data.get(field.name.value)

            # Assign default value when it corresponds to a constant field or when the extracted value is null
            value = str(value) if value is not None else field.default_value

            # If the assigned value is not null, add it to the materialized properties
            if value is not None:
                properties[field.name.value] = value

        return properties

    def _validate_properties(
        self,
        properties: dict[str, Any],
        relationship_type: RelationshipType,
    ) -> tuple[dict[str, Any] | None, tuple[Rejection, ...]]:
        """Validate the materialized properties against the relationship type definition.

        Only extracted fields are checked, against their required flag, allowed options, and regex. An invalid value
        of a required field (which includes the primary key) rejects the relationship, since the relationship is
        incomplete without it. An invalid value of an optional field only rejects the value: the field is unset,
        without falling back to its default, so that the property is absent rather than asserted.

        Args:
            properties: Materialized properties to validate.
            relationship_type: Relationship type defining the field constraints.

        Returns:
            The properties without the invalid optional values, or None if a required field is missing or invalid;
            and the rejections: the one that rejects the relationship, or else one per unset value.
        """
        type_name = relationship_type.name.value
        validated = dict(properties)
        unset: list[Rejection] = []
        for field in relationship_type.fields_for(RelationshipRetrievalMode.EXTRACT):
            field_name = field.name.value
            value = validated.get(field_name)
            if value is None:
                # Required fields must be present and not null
                if field.required:
                    return None, (_object_rejection(RejectionReason.MISSING_VALUE, type_name, field_name),)
                continue

            # Allowed values must be respected when options are defined, and the regex pattern when one is defined
            reason = _invalid_value_reason(value, field.options, field.regex)
            if reason is not None:
                if field.required:
                    return None, (_object_rejection(reason, type_name, field_name),)
                del validated[field_name]
                unset.append(Rejection(RejectionScope.VALUE, reason, type_name, field_name))

        return validated, tuple(unset)
