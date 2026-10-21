"""Tests for how result materializers validate extraction results and build knowledge objects from them."""

import json
from pathlib import Path
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
from wukong_engine.app.data_extraction.services.result_materializer import _extracted_items
from wukong_engine.core.documents.model.values import ContextLevel
from wukong_engine.core.knowledge.elements import Entity, EntityRef
from wukong_engine.core.knowledge.model import KnowledgeModel
from wukong_engine.core.knowledge.model.values import EntityTypeName, RelationshipTypeName
from wukong_engine.core.shared.identity import ContentHash
from wukong_engine.infrastructure.definitions.knowledge import LocalKnowledgeModelProvider
from wukong_engine.infrastructure.normalization.primary_key import DefaultPKNormalizer


@pytest.mark.parametrize('data', [[], 'entities', None, {}, {'entities': None}, {'entities': {'name': 'Ada'}}])
def test_results_without_a_list_of_items_are_malformed(data: Any) -> None:
    """Reject results that aren't an object holding a list under the expected key."""
    with pytest.raises(ExtractionResultError):
        _extracted_items(data, 'entities')


def test_items_that_are_not_objects_are_skipped() -> None:
    """Keep only the extracted items that are objects."""
    items = [{'_entity_type': 'Person'}, 'Ada', 42, None, ['Ada']]

    assert _extracted_items({'entities': items}, 'entities') == [{'_entity_type': 'Person'}]


KNOWLEDGE_MODEL = {
    'extraction_config': {'llm': {'domain': 'Mission reports.', 'language': 'en'}},
    'entity_types': {
        'Mission': {
            'description': 'A mission.',
            'primary_key': 'code',
            'fields': {
                'code': {'data_type': 'string', 'description': 'Code.', 'regex': '^[A-Z]+-[0-9]+$', 'required': True},
                'status': {
                    'data_type': 'string',
                    'description': 'Status.',
                    'options': ['planned', 'active', 'completed'],
                    'default_value': 'planned',
                },
            },
            'document_collections': {'document': 'missions', 'chunk': 'missions'},
        },
        'Incident': {
            'description': 'An incident.',
            'primary_key': 'code',
            'fields': {'code': {'data_type': 'string', 'description': 'Code.', 'required': True}},
            'document_collections': {'chunk': 'missions'},
        },
    },
    'relationship_types': {
        'OccurredDuring': {
            'description': 'An incident during a mission.',
            'endpoints': {
                'Incident': {
                    'Mission': [{'source_context_levels': 'chunk', 'target_context_levels': ['document', 'chunk']}]
                },
            },
            'deduplication': 'endpoints',
            'fields': {'flight_day': {'data_type': 'string', 'description': 'Flight day.', 'regex': '^[0-9]+$'}},
        },
    },
}
JOB = ExtractionJob.from_context(ContextLevel.CHUNK, ContentHash.from_content_string('chunk'))


@pytest.fixture
def model(tmp_path: Path) -> KnowledgeModel:
    """Load the test knowledge model the way a workspace's is loaded."""
    path = tmp_path / 'knowledge_model.json'
    path.write_text(json.dumps(KNOWLEDGE_MODEL))
    return LocalKnowledgeModelProvider().get(str(path))


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
