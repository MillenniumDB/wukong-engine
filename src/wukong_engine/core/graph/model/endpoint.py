import json
from dataclasses import dataclass

from wukong_engine.core.documents.model.values import EndpointContext
from wukong_engine.core.graph.model.values import EntityTypeName


@dataclass(frozen=True)
class Endpoint:
    """A relationship type endpoint."""

    source: EntityTypeName
    target: EntityTypeName
    context_pairs: tuple[EndpointContext, ...]

    def __str__(self) -> str:
        """User-friendly string representation of the endpoint."""
        context_info = ', '.join(
            f'{pair.source_level.value} → {pair.target_level.value}' for pair in self.context_pairs
        )
        return f'{self.source} → {self.target} [{context_info}]'

    def __repr__(self) -> str:
        """JSON representation of the endpoint."""
        return json.dumps({'source': str(self.source), 'target': str(self.target)})
