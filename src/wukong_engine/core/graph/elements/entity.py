from dataclasses import dataclass
from typing import Any

from wukong_engine.core.graph.model import EntityType

from .values import EntityId

# TODO: SQLite Bootstrap

# PRAGMA foreign_keys = ON;
# PRAGMA journal_mode = WAL;
# PRAGMA synchronous = NORMAL;
# PRAGMA temp_store = MEMORY;
# PRAGMA cache_size = -20000; -- ~20MB


# CREATE TABLE documents (
#     document_id TEXT PRIMARY KEY,
#     document_content_id TEXT NOT NULL UNIQUE,
#     source_uri TEXT NOT NULL UNIQUE
# );
# CREATE TABLE collections (
#     collection_name TEXT PRIMARY KEY,
# );
# CREATE TABLE document_collections (
#     document_id TEXT NOT NULL,
#     collection_name TEXT NOT NULL,
#     PRIMARY KEY (document_id, collection_name),
#     FOREIGN KEY (document_id) REFERENCES documents(document_id),
#     FOREIGN KEY (collection_name) REFERENCES collections(collection_name)
# );
# CREATE TABLE entity_types (
#     entity_type_name TEXT PRIMARY KEY,
# );
# CREATE TABLE entity_type_collections (
#     entity_type_name TEXT NOT NULL,
#     collection_name TEXT NOT NULL,
#     PRIMARY KEY (entity_type_name, collection_name),
#     FOREIGN KEY (collection_name) REFERENCES collections(collection_name)
#     FOREIGN KEY (entity_type_name) REFERENCES entity_types(entity_type_name)
# );
# CREATE TABLE extracted_entity_types (
#     document_id TEXT NOT NULL,
#     entity_type_name TEXT NOT NULL,
#     PRIMARY KEY (document_id, entity_type)
#     FOREIGN KEY (document_id) REFERENCES documents(document_id)
#     FOREIGN KEY (entity_type_name) REFERENCES entity_types(entity_type_name)
# );
# CREATE TABLE entities (
#     entity_id TEXT PRIMARY KEY,
#     entity_content_id TEXT NOT NULL UNIQUE,
#     entity_type TEXT NOT NULL,
#     entity_properties TEXT NOT NULL
# );
# CREATE TABLE extracted_entities (
#     entity_id TEXT NOT NULL,
#     document_id TEXT NOT NULL,
#     PRIMARY KEY (entity_id, document_id)
#     FOREIGN KEY (entity_id) REFERENCES entities(entity_id),
#     FOREIGN KEY (document_id) REFERENCES documents(document_id)
# );


# TODO: Reset/clear options for SQLite store in the config
@dataclass(frozen=True)
class Entity:
    """Entity instance in the graph."""

    id: EntityId
    type: EntityType
    properties: dict[str, Any]
