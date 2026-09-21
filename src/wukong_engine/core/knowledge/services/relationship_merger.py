from typing import Any

from wukong_engine.core.knowledge.elements import Relationship
from wukong_engine.core.knowledge.model import RelationshipType
from wukong_engine.core.knowledge.model.values import MergeStrategy


class RelationshipMerger:
    """Merge two relationships based on specified strategies."""

    def merge(self, existing: Relationship, incoming: Relationship) -> Relationship:
        """Merge two relationships into one."""
        # Both relationships should have the same type, otherwise this is a data integrity issue
        if incoming.type != existing.type:
            raise ValueError(
                f'Incoming relationship type "{incoming.type.name}" does not match existing type "{existing.type.name}" while merging',
            )
        return Relationship(
            id=existing.id,
            type=existing.type,
            source=existing.source,
            target=existing.target,
            properties=self._merge_properties(existing.properties, incoming.properties, existing.type),
        )

    def _merge_properties(
        self,
        existing: dict[str, Any],
        incoming: dict[str, Any],
        relationship_type: RelationshipType,
    ) -> dict[str, Any]:
        """Merge properties of two relationships based on the relationship type's field merge strategy."""
        merged: dict[str, Any] = {}
        fields = {name.value: field for name, field in relationship_type.fields.items()}
        all_keys = sorted(set(existing) | set(incoming))

        # Use the default merge strategy unless a specific strategy is defined for the field
        for key in all_keys:
            merge_strategy = relationship_type.default_merge_strategy
            if key in fields:
                merge_strategy = fields[key].merge_strategy or merge_strategy
            merged[key] = self._choose_value(existing.get(key), incoming.get(key), merge_strategy)

        return merged

    @staticmethod
    def _choose_value(existing: Any, incoming: Any, strategy: MergeStrategy) -> Any:
        """Choose the value according to the field's merge strategy."""
        # If one of the values is None, return the other value regardless of the strategy
        if existing is None:
            return incoming
        if incoming is None:
            return existing

        # If both values are present, apply the merge strategy
        chosen = existing
        match strategy:
            case MergeStrategy.KEEP:
                chosen = existing
            case MergeStrategy.REPLACE:
                chosen = incoming
            case MergeStrategy.LONGEST:
                chosen = existing if len(existing) >= len(incoming) else incoming
            case MergeStrategy.SHORTEST:
                chosen = existing if len(existing) <= len(incoming) else incoming
        return chosen
