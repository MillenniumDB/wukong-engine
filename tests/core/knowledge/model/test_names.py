"""Tests for the validation of knowledge model and document collection names."""

import pytest

from wukong_engine.core.documents.model.values import DocumentCollectionName
from wukong_engine.core.knowledge.model.values import EntityTypeName, FieldName, RelationshipTypeName


@pytest.mark.parametrize(
    ('name_type', 'value'),
    [
        (EntityTypeName, 'Mission\n'),
        (RelationshipTypeName, 'AssignedTo\n'),
        (FieldName, 'notes\n'),
        (DocumentCollectionName, 'missions\n'),
    ],
)
def test_names_with_a_trailing_newline_are_rejected(
    name_type: type[EntityTypeName | RelationshipTypeName | FieldName | DocumentCollectionName],
    value: str,
) -> None:
    """Reject a trailing newline, which a ``$`` anchor lets through and which splits exported lines in two."""
    with pytest.raises(ValueError, match='Must match regex pattern'):
        name_type(value)


@pytest.mark.parametrize('value', ['true', 'false'])
def test_field_names_that_are_millenniumdb_keywords_are_rejected(value: str) -> None:
    """Reject field names the MillenniumDB format reads as keywords rather than as property keys."""
    with pytest.raises(ValueError, match='Reserved name'):
        FieldName(value)
