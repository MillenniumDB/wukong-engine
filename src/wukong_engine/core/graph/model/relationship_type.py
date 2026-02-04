from dataclasses import dataclass
from typing import Any, Self

from .values import ContextLevel, DataType, RetrievalMode


@dataclass(frozen=True)
class RelationshipType: ...
