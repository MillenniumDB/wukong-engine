"""Tests for the validation of entity types and their fields."""

from typing import Any

import pytest

from wukong_engine.core.knowledge.model import KnowledgeModel
from wukong_engine.core.knowledge.model.values import EntityTypeName, FieldName
from wukong_engine.infrastructure.definitions.knowledge.mapper import KnowledgeModelMapper
from wukong_engine.infrastructure.definitions.knowledge.schemas import KnowledgeModelSchema


def _load_mission(**fields: dict[str, Any]) -> KnowledgeModel:
    """Load a model with a ``Mission`` entity type keyed by ``code``, overriding or adding the given fields."""
    mission_fields: dict[str, Any] = {
        'code': {'data_type': 'string', 'description': 'Code.', 'required': True},
        'name': {'data_type': 'string', 'description': 'Name.'},
        **fields,
    }
    schema = KnowledgeModelSchema.model_validate(
        {
            'entity_types': {
                'Mission': {
                    'description': 'A mission.',
                    'primary_key': 'code',
                    'fields': mission_fields,
                    'document_collections': {'document': 'missions'},
                },
            },
        },
    )
    return KnowledgeModelMapper().map_knowledge_model(schema)


@pytest.mark.parametrize('field_name', ['code', 'name'])
def test_load_retrieval_mode_is_rejected_until_implemented(field_name: str) -> None:
    """Reject the ``load`` retrieval mode, which would otherwise leave the field unfilled after the LLM call."""
    field = {'data_type': 'string', 'description': 'A field.', 'retrieval_mode': {'document': 'load'}}
    if field_name == 'code':
        field['required'] = True

    with pytest.raises(ValueError, match='"load" is not implemented yet'):
        _load_mission(**{field_name: field})


def test_primary_key_cannot_declare_a_default_value() -> None:
    """Reject a default primary key, which would merge every entity the LLM returned without one into one entity."""
    code = {'data_type': 'string', 'description': 'Code.', 'required': True, 'default_value': 'ARTEMIS-7'}

    with pytest.raises(ValueError, match='primary key "code" cannot declare a default value'):
        _load_mission(code=code)


@pytest.mark.parametrize('key', ['options', 'examples', 'default_value'])
@pytest.mark.parametrize('value', ['', '  ', ' active', 'active '])
def test_values_must_have_the_form_of_an_extracted_value(key: str, value: str) -> None:
    """Reject a value no extraction can produce, since extracted values are stripped and an empty one is missing."""
    with pytest.raises(ValueError, match='leading or trailing whitespace'):
        _load_mission(name={'data_type': 'string', 'description': 'Name.', key: value})


REGEX_CODE = {'data_type': 'string', 'description': 'Code.', 'required': True, 'regex': '[A-Z]+-[0-9]+'}


def test_regex_without_anchors_accepts_a_whole_match() -> None:
    """Accept a value the regex matches as a whole, even when the pattern has no anchors."""
    _load_mission(code={**REGEX_CODE, 'examples': 'ARTEMIS-7'})


def test_regex_must_match_the_whole_value() -> None:
    """Reject a value the regex only matches a prefix of, even when the pattern has no ``$`` anchor."""
    with pytest.raises(ValueError, match='ARTEMIS-7 and more'):
        _load_mission(code={**REGEX_CODE, 'examples': 'ARTEMIS-7 and more'})


def _crew_size(**settings: Any) -> dict[str, Any]:
    """Build the definition of an optional integer ``crew_size`` field with the given settings."""
    return {'data_type': 'integer', 'description': 'Crew size.', **settings}


@pytest.mark.parametrize(
    ('field', 'error'),
    [
        (_crew_size(default_value='4'), "Default value '4' is not a valid integer value"),
        (_crew_size(options=[2, 2**56]), 'Option 72057594037927936 is not a valid integer value'),
        ({'data_type': 'string', 'description': 'Name.', 'examples': 4}, 'Example 4 is not a valid string value'),
        (_crew_size(regex='[0-9]+'), 'regex only applies to string fields'),
        (
            {'data_type': 'string', 'description': 'Name.', 'max': 10},
            'min and max only apply to integer and float fields',
        ),
        (_crew_size(min={'chunk': 5}, max=4), 'min 5 is greater than max 4 for context level "CHUNK"'),
        (_crew_size(min=1, default_value={'document': 0}), 'Default value 0 for context level "DOCUMENT" is less'),
        (_crew_size(min=1, max=12, examples=[4, 13]), 'Example 13 for context level "CHUNK" is outside the range'),
    ],
)
def test_integer_fields_hold_integers_and_only_take_bounds(field: dict[str, Any], error: str) -> None:
    """Reject values of another data type and constraints that don't apply to it, and check values against bounds."""
    with pytest.raises(ValueError, match=error):
        _load_mission(crew_size=field)


def test_booleans_are_not_integers() -> None:
    """Reject a boolean where an integer is expected, even though Python treats booleans as integers."""
    with pytest.raises(ValueError, match='Default value True is not a valid integer value'):
        _load_mission(crew_size=_crew_size(default_value=True))


def test_integer_fields_can_be_primary_keys() -> None:
    """Accept an integer primary key with bounds, options and examples that satisfy each other."""
    number = {'data_type': 'int', 'description': 'Number.', 'required': True, 'min': 1, 'examples': [1, 1204]}

    _load_mission(code=number)


def _payload(**settings: Any) -> dict[str, Any]:
    """Build the definition of an optional float ``payload`` field with the given settings."""
    return {'data_type': 'float', 'description': 'Payload mass.', **settings}


def test_integers_in_float_fields_become_floats() -> None:
    """Read integers written for a float field as floats, since every integer is also a float value."""
    field = _payload(options=[1, 2.5], examples=1, default_value={'chunk': 2.5, 'document': 1}, min=0, max=2.5)

    payload = _load_mission(payload=field).entity_types[EntityTypeName('Mission')].fields[FieldName('payload')]

    values = [*payload.options, *payload.examples, *payload.default_value.values(), *payload.minimum.values()]
    assert values == [1.0, 2.5, 1.0, 2.5, 1.0, 0.0, 0.0]
    assert all(isinstance(value, float) for value in values)


@pytest.mark.parametrize(
    ('field', 'error'),
    [
        (_payload(default_value=float('nan')), 'Default value nan is not a valid float value'),
        (_payload(options=[1.5, 1e39]), 'Option 1e[+]39 is not a valid float value'),
        (_payload(regex='[0-9.]+'), 'regex only applies to string fields'),
        (_payload(min=0.5, max=0.25), 'min 0.5 is greater than max 0.25'),
        (_payload(max=10, examples=[10.5]), 'Example 10.5 for context level "CHUNK" is greater than the max 10.0'),
        (_crew_size(min=0.5), 'Bound 0.5 is not a valid integer value'),
        ({'data_type': 'number', 'description': 'Code.', 'required': True}, 'primary key "code" cannot be a float'),
    ],
)
def test_float_fields_hold_finite_floats_and_cannot_be_primary_keys(field: dict[str, Any], error: str) -> None:
    """Reject non-finite or out of range floats, misplaced constraints, float bounds on integers and float keys."""
    name = 'code' if field.get('required') else 'payload'
    with pytest.raises(ValueError, match=error):
        _load_mission(**{name: field})


def test_largest_and_smallest_apply_to_float_fields() -> None:
    """Accept merging float values by size."""
    _load_mission(payload=_payload(merge_strategy='max'), mass=_payload(merge_strategy='smallest'))


@pytest.mark.parametrize(
    ('field', 'error'),
    [
        (_crew_size(merge_strategy='longest'), 'Merge strategy "longest" does not apply to integer values'),
        ({'data_type': 'string', 'description': 'Name.', 'merge_strategy': 'max'}, '"largest" does not apply'),
    ],
)
def test_merge_strategies_must_apply_to_the_field_data_type(field: dict[str, Any], error: str) -> None:
    """Reject a field merge strategy that compares values in a way that doesn't apply to the field's data type."""
    with pytest.raises(ValueError, match=error):
        _load_mission(crew_size=field)


def test_the_default_merge_strategy_must_apply_to_fields_without_their_own() -> None:
    """Reject a type default merge strategy that doesn't apply to a field without its own, asking to set one."""
    schema = KnowledgeModelSchema.model_validate(
        {
            'entity_types': {
                'Mission': {
                    'description': 'A mission.',
                    'primary_key': 'code',
                    'default_merge_strategy': 'longest',
                    'fields': {
                        'code': {'data_type': 'string', 'description': 'Code.', 'required': True},
                        'crew_size': _crew_size(),
                    },
                    'document_collections': {'document': 'missions'},
                },
            },
        },
    )

    with pytest.raises(ValueError, match='integer field "crew_size", which must set its own merge strategy'):
        KnowledgeModelMapper().map_knowledge_model(schema)


def _crewed(**settings: Any) -> dict[str, Any]:
    """Build the definition of an optional boolean ``crewed`` field with the given settings."""
    return {'data_type': 'boolean', 'description': 'Whether the mission is crewed.', **settings}


@pytest.mark.parametrize(
    ('fields', 'error'),
    [
        ({'crewed': _crewed(default_value=1)}, 'Default value 1 is not a valid boolean value'),
        ({'crewed': _crewed(options=['yes'])}, "Option 'yes' is not a valid boolean value"),
        ({'crewed': _crewed(min=0)}, 'min and max only apply to integer and float fields'),
        ({'crewed': _crewed(regex='true')}, 'regex only applies to string fields'),
        ({'crewed': _crewed(merge_strategy='largest')}, '"largest" does not apply to boolean values'),
        ({'crew_size': _crew_size(merge_strategy='any')}, '"any" does not apply to integer values'),
        ({'payload': _payload(default_value=True)}, 'Default value True is not a valid float value'),
        ({'code': _crewed(required=True)}, 'primary key "code" cannot be a boolean field'),
    ],
)
def test_boolean_fields_hold_booleans_and_take_no_bounds(fields: dict[str, Any], error: str) -> None:
    """Reject numbers as booleans and booleans as numbers, constraints and merge strategies that don't apply, and keys."""
    with pytest.raises(ValueError, match=error):
        _load_mission(**fields)


def test_boolean_fields_accept_their_values_and_merge_strategies() -> None:
    """Accept boolean options, examples and defaults, and merging by logical OR or AND under any alias."""
    _load_mission(
        crewed=_crewed(options=[True, False], examples=True, default_value={'chunk': False}, merge_strategy='or'),
        docked=_crewed(merge_strategy='all'),
    )
