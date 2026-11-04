"""Relationship type endpoints."""

import json
from dataclasses import dataclass

from wukong_engine.core.documents.model.values import EndpointContext
from wukong_engine.core.knowledge.model.values import EntityTypeName


@dataclass(frozen=True, slots=True)
class Endpoint:
    """A relationship type endpoint.

    Attributes:
        source: Entity type allowed as the relationship's source.
        target: Entity type allowed as the relationship's target.
        context_pairs: Allowed pairings of source and target context levels for this endpoint.
    """

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

    def reversed(self) -> Endpoint:
        """Return the endpoint with its source and target swapped, together with their context levels.

        Returns:
            The endpoint from this endpoint's target to its source.
        """
        return Endpoint(
            source=self.target,
            target=self.source,
            context_pairs=tuple(
                EndpointContext(source_level=pair.target_level, target_level=pair.source_level)
                for pair in self.context_pairs
            ),
        )
