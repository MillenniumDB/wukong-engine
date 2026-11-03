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
from wukong_engine.app.data_extraction.services.result_materializer import (
    _extracted_items,
    _normalize_boolean,
    _normalize_float,
    _normalize_integer,
    _normalize_string,
)
from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.knowledge.elements import Entity, EntityRef
from wukong_engine.core.knowledge.elements.values import EntityId
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
        ('ACTIVE', ('planned', 'active'), 'active'),
        ('active', ('Active', 'active'), 'active'),
        ('ACTIVE', ('Active', 'active'), 'Active'),
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
    assert _normalize_string(value, options) == expected


@pytest.mark.parametrize(
    ('value', 'expected'),
    [
        (42, 42),
        (42.0, 42),
        (' -7 ', -7),
        ('+3', 3),
        ('1.234', 1234),
        ('1,234,567', 1234567),
        ('12 345', 12345),
        ('1_000', 1000),
        ('', None),
        (' null ', None),
        (None, None),
    ],
)
def test_integer_values_are_normalized_from_their_integral_forms(value: Any, expected: int | None) -> None:
    """Convert integral floats and integer text, with consistently grouped thousands separators, to integers."""
    assert _normalize_integer(value) == expected


@pytest.mark.parametrize('value', [42.5, '1.5', '1.2345', '1,234.00', '1.234,567', '12.34', '42 people', True, {}])
def test_values_without_an_integer_form_are_left_for_validation_to_reject(value: Any) -> None:
    """Leave values that aren't unambiguously integers unchanged, so they are discarded as invalid, not as missing."""
    assert _normalize_integer(value) == value


@pytest.mark.parametrize(
    ('value', 'expected'),
    [
        (4, 4.0),
        (2.5, 2.5),
        (' -0,5 ', -0.5),
        ('1.234', 1.234),
        ('1,234', 1.234),
        ('1.234,5', 1234.5),
        ('1,234.5', 1234.5),
        ('1.234.567', 1234567.0),
        ('12 345,6', 12345.6),
        ('+2.5e3', 2500.0),
        ('1e-5', 1e-05),
        ('', None),
        (' null ', None),
        (None, None),
    ],
)
def test_float_values_are_normalized_from_their_decimal_forms(value: Any, expected: float | None) -> None:
    """Convert integers and decimal text, reading a lone point or comma as the decimal separator, to floats."""
    result = _normalize_float(value)

    assert result == expected
    assert expected is None or isinstance(result, float)


@pytest.mark.parametrize(
    'value',
    ['1.234.5', '1,234,5', '12,34,5', '.5', '1.5 kg', 'inf', 'NaN', True, pytest.param(10**400, id='huge integer'), {}],
)
def test_values_without_a_float_form_are_left_for_validation_to_reject(value: Any) -> None:
    """Leave values that aren't decimal numbers unchanged, so they are discarded as invalid, not as missing."""
    assert _normalize_float(value) is value


@pytest.mark.parametrize(
    ('value', 'expected'),
    [
        (True, True),
        (0, False),
        (1.0, True),
        (' TRUE ', True),
        ('no', False),
        ('Sí', True),
        ('si', True),
        ('Falso', False),
        ('1', True),
        ('', None),
        ('null', None),
        (None, None),
    ],
)
def test_boolean_values_are_normalized_from_yes_and_no_forms(value: Any, *, expected: bool | None) -> None:
    """Convert 1 and 0, and yes or no words in English or Spanish regardless of case, to booleans."""
    assert _normalize_boolean(value) is expected


@pytest.mark.parametrize('value', [2, 0.5, 'maybe', 'tal vez', 'yes!', {}])
def test_values_without_a_boolean_form_are_left_for_validation_to_reject(value: Any) -> None:
    """Leave values that aren't yes or no unchanged, so they are discarded as invalid, not as missing."""
    assert _normalize_boolean(value) is value


JOB = ExtractionJob.from_context(ContextLevel.CHUNK, ContentHash.from_content_string('chunk'))


def _entity(model: KnowledgeModel, type_name: str, code: str) -> Entity:
    """Build an entity of the given type identified by its code."""
    normalized_pk = DefaultPKNormalizer().normalize(code)
    assert normalized_pk is not None
    entity_type = model.entity_type(EntityTypeName(type_name))
    assert entity_type is not None
    return Entity.from_extraction(entity_type, {'code': code}, normalized_pk)


class StubEntityRepository(EntityExtractionRepository):
    """Entity extraction repository assigning the Mission and Sol types to every job, recording the jobs looked up."""

    def __init__(self) -> None:
        """Initialize the repository without a unit of work, since no lookup reaches the database."""
        self.looked_up_jobs: list[ExtractionJob] = []

    def get_job_entity_types(self, job: ExtractionJob) -> tuple[EntityTypeName, ...]:
        """Record the lookup and assign the Mission and Sol types to the job."""
        self.looked_up_jobs.append(job)
        return (EntityTypeName('Mission'), EntityTypeName('Sol'))


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
            "it does not satisfy the field's data type or constraints"
        ),
        (
            'Discarded extracted "Mission" entity: value \'artemis 7\' of field "code" '
            "does not satisfy the field's data type or constraints"
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


def test_integer_values_are_converted_and_validated_against_their_bounds(model: KnowledgeModel) -> None:
    """Convert integer forms, discarding optional values out of bounds or without one, and key entities by integers."""
    materializer = EntityExtractionResultMaterializer(StubEntityRepository(), DefaultPKNormalizer())
    data = {
        'entities': [
            {'_entity_type': 'Mission', 'code': 'ARTEMIS-7', 'crew_size': '4'},
            {'_entity_type': 'Mission', 'code': 'ARTEMIS-8', 'crew_size': [3.0]},
            {'_entity_type': 'Mission', 'code': 'KEPLER-12', 'crew_size': 40},
            {'_entity_type': 'Mission', 'code': 'KEPLER-13', 'crew_size': 'four'},
            {'_entity_type': 'Sol', 'number': '1.204'},
            {'_entity_type': 'Sol', 'number': 'day 3'},
        ],
    }

    entities = materializer.materialize(ExtractionResult(status=JobStatus.COMPLETED, data=data), JOB, model)

    assert [entity.properties for entity in entities] == [
        {'code': 'ARTEMIS-7', 'crew_size': 4, 'status': 'planned'},
        {'code': 'ARTEMIS-8', 'crew_size': 3, 'status': 'planned'},
        {'code': 'KEPLER-12', 'status': 'planned'},
        {'code': 'KEPLER-13', 'status': 'planned'},
        {'number': 1204},
    ]
    sol_pk = DefaultPKNormalizer().normalize('1204')
    assert sol_pk is not None
    assert entities[-1].id.content == EntityId.from_identity(EntityTypeName('Sol'), sol_pk).content


def test_float_values_are_converted_and_validated_against_their_bounds(model: KnowledgeModel) -> None:
    """Convert integers and decimal text to floats, discarding optional values out of bounds or without a float form."""
    materializer = EntityExtractionResultMaterializer(StubEntityRepository(), DefaultPKNormalizer())
    data = {
        'entities': [
            {'_entity_type': 'Mission', 'code': 'ARTEMIS-7', 'payload_tons': 4},
            {'_entity_type': 'Mission', 'code': 'ARTEMIS-8', 'payload_tons': '12,5'},
            {'_entity_type': 'Mission', 'code': 'KEPLER-12', 'payload_tons': -0.5},
            {'_entity_type': 'Mission', 'code': 'KEPLER-13', 'payload_tons': 'heavy'},
        ],
    }

    entities = materializer.materialize(ExtractionResult(status=JobStatus.COMPLETED, data=data), JOB, model)

    payloads = [entity.properties.get('payload_tons') for entity in entities]
    assert payloads == [4.0, 12.5, None, None]
    assert isinstance(payloads[0], float)


def test_boolean_values_are_converted_and_not_confused_with_numbers(model: KnowledgeModel) -> None:
    """Convert yes or no forms to booleans, and discard booleans extracted for numeric fields as invalid."""
    materializer = EntityExtractionResultMaterializer(StubEntityRepository(), DefaultPKNormalizer())
    data = {
        'entities': [
            {'_entity_type': 'Mission', 'code': 'ARTEMIS-7', 'crewed': 'Sí', 'crew_size': True},
            {'_entity_type': 'Mission', 'code': 'ARTEMIS-8', 'crewed': 0, 'payload_tons': False},
            {'_entity_type': 'Mission', 'code': 'KEPLER-12', 'crewed': 'maybe'},
        ],
    }

    entities = materializer.materialize(ExtractionResult(status=JobStatus.COMPLETED, data=data), JOB, model)

    assert [entity.properties for entity in entities] == [
        {'code': 'ARTEMIS-7', 'crewed': True, 'status': 'planned'},
        {'code': 'ARTEMIS-8', 'crewed': False, 'status': 'planned'},
        {'code': 'KEPLER-12', 'status': 'planned'},
    ]
