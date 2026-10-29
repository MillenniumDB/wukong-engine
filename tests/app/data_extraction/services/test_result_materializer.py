"""Tests for how result materializers validate extraction results and build knowledge objects from them."""

from typing import Any

import pytest

from wukong_engine.app.data_extraction.elements import (
    ExtractionJob,
    ExtractionResult,
    RelationshipExtractionRequestObjects,
)
from wukong_engine.app.data_extraction.elements.values import JobStatus
from wukong_engine.app.data_extraction.exceptions import ExtractionResultError
from wukong_engine.app.data_extraction.services import (
    EntityExtractionRepository,
    EntityExtractionResultMaterializer,
    RelationshipExtractionRepository,
    RelationshipExtractionResultMaterializer,
)
from wukong_engine.app.data_extraction.services.result_materializer import _extracted_items, _normalize_value
from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.knowledge.elements import Entity, EntityRef
from wukong_engine.core.knowledge.model import KnowledgeModel
from wukong_engine.core.knowledge.model.values import EntityTypeName, RelationshipTypeName
from wukong_engine.core.shared.identity import ContentHash
from wukong_engine.infrastructure.normalization.primary_key import DefaultPKNormalizer


@pytest.mark.parametrize('data', ['entities', None, {}, {'entities': None}, {'entities': {'name': 'Ada'}}])
def test_results_without_a_list_of_items_are_malformed(data: Any) -> None:
    """Reject results that are neither a list nor an object holding a list under the expected key."""
    with pytest.raises(ExtractionResultError):
        _extracted_items(data, 'entities')


@pytest.mark.parametrize('wrap', [lambda items: {'entities': items}, lambda items: items])
def test_items_that_are_not_objects_are_skipped(wrap: Any) -> None:
    """Keep only the extracted items that are objects, whether or not the list is wrapped under its key."""
    items = [{'_entity_type': 'Person'}, 'Ada', 42, None, ['Ada']]

    assert _extracted_items(wrap(items), 'entities') == [{'_entity_type': 'Person'}]


@pytest.mark.parametrize(
    ('value', 'options', 'expected'),
    [
        ('  Ada ', (), 'Ada'),
        (True, ('true', 'false'), 'true'),
        (False, (), 'false'),
        (3, (), '3'),
        (3.0, (), '3'),
        (2.5, (), '2.5'),
        (['Ada'], (), 'Ada'),
        ('ACTIVE', ('planned', 'active'), 'active'),
        ('retired', ('planned', 'active'), 'retired'),
        ('', (), None),
        ('null', (), None),
        (None, (), None),
        ({'name': 'Ada'}, (), None),
        (['Ada', 'Grace'], (), None),
        (float('nan'), (), None),
    ],
)
def test_values_are_normalized_to_their_string_form(value: Any, options: tuple[str, ...], expected: str | None) -> None:
    """Convert values of other JSON types and casings to the field's string form, or to None if they have none."""
    assert _normalize_value(value, options) == expected


JOB = ExtractionJob.from_context(ContextLevel.CHUNK, ContentHash.from_content_string('chunk'))


def _entity(model: KnowledgeModel, type_name: str, code: str) -> Entity:
    """Build an entity of the given type identified by its code."""
    normalized_pk = DefaultPKNormalizer().normalize(code)
    assert normalized_pk is not None
    entity_type = model.entity_type(EntityTypeName(type_name))
    assert entity_type is not None
    return Entity.from_extraction(entity_type, {'code': code}, normalized_pk)


class StubEntityRepository(EntityExtractionRepository):
    """Entity extraction repository assigning the Mission type to every job, recording the jobs looked up."""

    def __init__(self) -> None:
        """Initialize the repository without a unit of work, since no lookup reaches the database."""
        self.looked_up_jobs: list[ExtractionJob] = []

    def get_job_entity_types(self, job: ExtractionJob) -> tuple[EntityTypeName, ...]:
        """Record the lookup and assign the Mission type to the job."""
        self.looked_up_jobs.append(job)
        return (EntityTypeName('Mission'),)


class StubRelationshipRepository(RelationshipExtractionRepository):
    """Relationship extraction repository serving a fixed job context, recording the lookups of each part of it."""

    def __init__(self, entity_refs: dict[str, EntityRef], elements: RelationshipExtractionRequestObjects) -> None:
        """Initialize the repository without a unit of work, since no lookup reaches the database."""
        self.entity_refs = entity_refs
        self.elements = elements
        self.lookups: list[tuple[str, ExtractionJob]] = []
        self.elements_model: KnowledgeModel | None = None

    def get_job_relationship_types(self, job: ExtractionJob) -> tuple[RelationshipTypeName, ...]:
        """Record the lookup and assign the OccurredDuring type to the job."""
        self.lookups.append(('types', job))
        return (RelationshipTypeName('OccurredDuring'),)

    def get_job_entity_ref_mapping(self, job: ExtractionJob) -> dict[str, EntityRef]:
        """Record the lookup and serve the temporary entity ID mapping."""
        self.lookups.append(('mapping', job))
        return self.entity_refs

    def get_job_extraction_elements(
        self, job: ExtractionJob, model: KnowledgeModel
    ) -> RelationshipExtractionRequestObjects:
        """Record the lookup, with the model it resolves against, and serve the job's extraction elements."""
        self.lookups.append(('elements', job))
        self.elements_model = model
        return self.elements


def test_entities_lose_only_invalid_optional_values_but_are_dropped_for_invalid_required_ones(
    model: KnowledgeModel,
) -> None:
    """Discard invalid optional values (falling back to the default), but drop entities with an invalid required one."""
    repository = StubEntityRepository()
    materializer = EntityExtractionResultMaterializer(repository, DefaultPKNormalizer())
    data = {
        'entities': [
            {'_entity_type': 'Mission', 'code': 'ARTEMIS-7', 'status': 'in progress'},
            {'_entity_type': 'Mission', 'code': 'artemis 7', 'status': 'active'},
            {'_entity_type': 'Mission', 'code': 'KEPLER-12', 'status': 'active'},
        ],
    }

    entities = materializer.materialize(ExtractionResult(status=JobStatus.COMPLETED, data=data), JOB, model)

    assert [entity.properties for entity in entities] == [
        {'code': 'ARTEMIS-7', 'status': 'planned'},
        {'code': 'KEPLER-12', 'status': 'active'},
    ]
    assert repository.looked_up_jobs == [JOB]


def test_discarded_entity_values_and_entities_are_logged(
    model: KnowledgeModel, caplog: pytest.LogCaptureFixture
) -> None:
    """Log each invalid optional value discarded and each entity dropped, naming the type, field and value."""
    materializer = EntityExtractionResultMaterializer(StubEntityRepository(), DefaultPKNormalizer())
    data = {
        'entities': [
            {'_entity_type': 'Mission', 'code': 'ARTEMIS-7', 'status': 'in progress'},
            {'_entity_type': 'Mission', 'code': 'artemis 7', 'status': 'active'},
        ],
    }

    with caplog.at_level('INFO'):
        materializer.materialize(ExtractionResult(status=JobStatus.COMPLETED, data=data), JOB, model)

    assert [record.getMessage() for record in caplog.records] == [
        (
            'Discarded invalid value \'in progress\' of optional field "Mission.status": '
            "it does not satisfy the field's options or regex"
        ),
        (
            'Discarded extracted "Mission" entity: value \'artemis 7\' of field "code" '
            "does not satisfy the field's options or regex"
        ),
    ]


def test_relationships_load_the_job_context_once_and_lose_only_invalid_optional_values(model: KnowledgeModel) -> None:
    """Load the job's types, ID mapping and entities once per result, discarding invalid optional values."""
    incident, mission = _entity(model, 'Incident', 'INC-1'), _entity(model, 'Mission', 'ARTEMIS-7')
    relationship_type = model.relationship_type(RelationshipTypeName('OccurredDuring'))
    assert relationship_type is not None
    repository = StubRelationshipRepository(
        entity_refs={
            'E1': EntityRef(entity_id=incident.id, entity_type_name=incident.type.name),
            'E2': EntityRef(entity_id=mission.id, entity_type_name=mission.type.name),
        },
        elements=RelationshipExtractionRequestObjects(
            relationship_types=(relationship_type,),
            chunk_entities=(incident, mission),
            parent_document_entities=(),
        ),
    )
    materializer = RelationshipExtractionResultMaterializer(repository, DefaultPKNormalizer())
    item = {'_relationship_type': 'OccurredDuring', '_source_entity_id': 'E1', '_target_entity_id': 'E2'}
    data = {
        'relationships': [
            item | {'flight_day': '45'},
            item | {'flight_day': 'day 45'},
            item | {'_target_entity_id': 'E9', 'flight_day': '45'},
        ],
    }

    relationships = materializer.materialize(ExtractionResult(status=JobStatus.COMPLETED, data=data), JOB, model)

    assert [relationship.properties for relationship in relationships] == [{'flight_day': '45'}, {}]
    assert repository.lookups == [('types', JOB), ('mapping', JOB), ('elements', JOB)]
    assert repository.elements_model is model


def test_entities_of_unvalidated_responses_keep_their_normalized_values(model: KnowledgeModel) -> None:
    """Keep entities whose type name and values only differ in case, spacing or JSON type from valid ones."""
    materializer = EntityExtractionResultMaterializer(StubEntityRepository(), DefaultPKNormalizer())
    data = {'entities': [{'_entity_type': ' mission', 'code': ' ARTEMIS-7 ', 'status': 'Active'}]}

    entities = materializer.materialize(ExtractionResult(status=JobStatus.COMPLETED, data=data), JOB, model)

    assert [entity.properties for entity in entities] == [{'code': 'ARTEMIS-7', 'status': 'active'}]


def test_relationships_of_unvalidated_responses_keep_their_normalized_values(model: KnowledgeModel) -> None:
    """Keep numeric values as their decimal text, and discard optional values that still don't satisfy the field."""
    incident, mission = _entity(model, 'Incident', 'INC-1'), _entity(model, 'Mission', 'ARTEMIS-7')
    relationship_type = model.relationship_type(RelationshipTypeName('OccurredDuring'))
    assert relationship_type is not None
    repository = StubRelationshipRepository(
        entity_refs={
            'E1': EntityRef(entity_id=incident.id, entity_type_name=incident.type.name),
            'E2': EntityRef(entity_id=mission.id, entity_type_name=mission.type.name),
        },
        elements=RelationshipExtractionRequestObjects(
            relationship_types=(relationship_type,),
            chunk_entities=(incident, mission),
            parent_document_entities=(),
        ),
    )
    materializer = RelationshipExtractionResultMaterializer(repository, DefaultPKNormalizer())
    item = {'_relationship_type': 'occurredduring', '_source_entity_id': ' e1', '_target_entity_id': 'E2'}
    data = {'relationships': [item | {'flight_day': 45}, item | {'flight_day': 45.0}, item | {'flight_day': True}]}

    relationships = materializer.materialize(ExtractionResult(status=JobStatus.COMPLETED, data=data), JOB, model)

    assert [relationship.properties for relationship in relationships] == [{'flight_day': '45'}] * 2 + [{}]
