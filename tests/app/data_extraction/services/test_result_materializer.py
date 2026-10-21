"""Tests for how result materializers handle extraction results that don't have the expected structure."""

from typing import Any

import pytest

from wukong_engine.app.data_extraction.exceptions import ExtractionResultError
from wukong_engine.app.data_extraction.services.result_materializer import _extracted_items


@pytest.mark.parametrize('data', [[], 'entities', None, {}, {'entities': None}, {'entities': {'name': 'Ada'}}])
def test_results_without_a_list_of_items_are_malformed(data: Any) -> None:
    """Reject results that aren't an object holding a list under the expected key."""
    with pytest.raises(ExtractionResultError):
        _extracted_items(data, 'entities')


def test_items_that_are_not_objects_are_skipped() -> None:
    """Keep only the extracted items that are objects."""
    items = [{'_entity_type': 'Person'}, 'Ada', 42, None, ['Ada']]

    assert _extracted_items({'entities': items}, 'entities') == [{'_entity_type': 'Person'}]
