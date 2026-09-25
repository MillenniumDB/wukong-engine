"""Service for merging duplicate entities."""

from typing import Any

from wukong_engine.core.knowledge.elements import Entity
from wukong_engine.core.knowledge.model import EntityType
from wukong_engine.core.knowledge.model.values import MergeStrategy


class EntityMerger:
    """Merge two entities based on specified strategies."""

    def merge(self, existing: Entity, incoming: Entity) -> Entity:
        """Merge two entities into one.

        The result keeps the identifier of ``existing``; only properties are merged.

        Args:
            existing: Entity already stored.
            incoming: Newly extracted entity to merge into ``existing``.

        Returns:
            A new entity with the merged properties.

        Raises:
            ValueError: If the entities don't share the same type.
        """
        # Both entities should have the same type, otherwise this is a data integrity issue
        if incoming.type != existing.type:
            raise ValueError(
                f'Incoming entity type "{incoming.type.name}" does not match existing type "{existing.type.name}" while merging',
            )
        return Entity(
            id=existing.id,
            type=existing.type,
            properties=self._merge_properties(existing.properties, incoming.properties, existing.type),
        )

    def _merge_properties(
        self,
        existing: dict[str, Any],
        incoming: dict[str, Any],
        entity_type: EntityType,
    ) -> dict[str, Any]:
        """Merge properties of two entities based on the entity type's field merge strategy.

        Args:
            existing: Properties of the existing entity.
            incoming: Properties of the incoming entity.
            entity_type: Type whose field and default merge strategies are applied.

        Returns:
            The union of both property sets, with each value chosen by its field's merge strategy.
        """
        merged: dict[str, Any] = {}
        fields = {name.value: field for name, field in entity_type.fields.items()}
        all_keys = sorted(set(existing) | set(incoming))

        # Use the default merge strategy unless a specific strategy is defined for the field
        for key in all_keys:
            merge_strategy = entity_type.default_merge_strategy
            if key in fields:
                merge_strategy = fields[key].merge_strategy or merge_strategy
            merged[key] = self._choose_value(existing.get(key), incoming.get(key), merge_strategy)

        return merged

    @staticmethod
    def _choose_value(existing: Any, incoming: Any, strategy: MergeStrategy) -> Any:
        """Choose the value according to the field's merge strategy.

        If either value is None, the other one is returned regardless of the strategy. Length ties keep ``existing``.

        Args:
            existing: Current value of the field.
            incoming: New value of the field.
            strategy: Merge strategy to apply when both values are present.

        Returns:
            The chosen value.
        """
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
