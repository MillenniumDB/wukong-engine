from dataclasses import dataclass
from typing import Any

from .request import EntityExtractionRequest


@dataclass(frozen=True)
class EntityExtractionOutput:
    """Runtime output produced by an entity extraction request."""

    request: EntityExtractionRequest
    payload: Any
