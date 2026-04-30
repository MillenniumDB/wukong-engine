# from collections.abc import Iterator
from typing import Protocol

# from wukong_engine.core.documents.elements.values import DocumentId
# from wukong_engine.core.graph.elements import Entity
# from wukong_engine.core.graph.model.values import EntityTypeName


# TODO: link_entities_to_document(document_id, entity_ids)

# TODO: mark_completed(document_id, entity_type(s))

# TODO: stream_pending_work()
# SELECT
#     d.document_id,
#     d.source_uri,
#     GROUP_CONCAT(DISTINCT et.entity_type) AS pending_entity_types
# FROM documents d
# JOIN document_collections dc ON dc.document_id = d.document_id
# JOIN entity_type_collections etc ON etc.collection_name = dc.collection_name
# JOIN entity_types et ON et.entity_type = etc.entity_type
# LEFT JOIN extracted_entity_types eet
#     ON eet.document_id = d.document_id
#     AND eet.entity_type = et.entity_type
# WHERE eet.entity_type IS NULL
# GROUP BY d.document_id;

# SELECT
#     d.document_id,
#     d.source_uri,
#     GROUP_CONCAT(DISTINCT et.entity_type) AS pending_entity_types
# FROM documents d
# JOIN document_collections dc
#     ON dc.document_id = d.document_id
# JOIN entity_type_collections etc
#     ON etc.collection_name = dc.collection_name
# JOIN entity_types et
#     ON et.entity_type = etc.entity_type
# WHERE NOT EXISTS (
#     SELECT 1
#     FROM extracted_entity_types eet
#     WHERE eet.document_id = d.document_id
#       AND eet.entity_type = et.entity_type
# )
# GROUP BY d.document_id;

# TODO: get_entity_document_pairs()

# SELECT entity_id, document_id FROM extracted_entities;


# TODO: Complete protocol
# TODO: Design one for Relationships and contain both in a general ExtractionStore
# TODO: Implement and test
# TODO: Look into indexes
class EntityExtractionStore(Protocol):
    """Store for managing entity extraction."""

    def clear(self) -> None:
        """Reset the entity extraction store."""
        ...
