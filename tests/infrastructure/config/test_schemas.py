"""Tests for the validation of the configuration file schema."""

from typing import Any

import pytest
from pydantic import ValidationError

from wukong_engine.infrastructure.config.schemas import ApplicationConfigSchema


@pytest.mark.parametrize(
    ('config', 'misspelled_key'),
    [
        ({'pipline': {'export_knowledge': False}}, 'pipline'),
        ({'llm': {'modle': 'claude-haiku-5-5'}}, 'llm.modle'),
        ({'chunking': {'target_token': 500}}, 'chunking.target_token'),
    ],
)
def test_misspelled_keys_are_rejected(config: dict[str, Any], misspelled_key: str) -> None:
    """Reject an unknown table or key instead of silently running with its default."""
    with pytest.raises(ValidationError, match=rf'{misspelled_key}\s+Extra inputs are not permitted'):
        ApplicationConfigSchema.model_validate(config)
