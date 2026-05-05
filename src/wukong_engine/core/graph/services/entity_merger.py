from typing import Any

from wukong_engine.core.graph.elements import Entity
from wukong_engine.core.graph.model import EntityType


class EntityMerger:
    """Merge two entities based on deduplication policies."""

    def merge(self, existing: Entity, incoming: Entity) -> Entity:
        """Merge two entities and return the result."""
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

    # TODO: Keys not in fields
    def _merge_properties(
        self,
        existing: dict[str, Any],
        incoming: dict[str, Any],
        entity_type: EntityType,
    ) -> dict[str, Any]:
        merged: dict[str, Any] = {}
        fields = {name.value: field for name, field in entity_type.fields.items()}
        all_keys = sorted(set(existing) | set(incoming))

        for key in all_keys:
            if key not in fields:
                print(f'MERGE: Key "{key}" not found')
                continue

            merged[key] = self._choose_value(incoming.get(key), existing.get(key))

        return merged

    @staticmethod
    def _choose_value(incoming: Any, existing: Any) -> Any:
        return incoming if incoming is not None else existing
