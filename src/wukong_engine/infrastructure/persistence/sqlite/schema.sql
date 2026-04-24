-- =========================================================
-- Core Configuration
-- =========================================================

PRAGMA foreign_keys = ON;

-- =========================================================
-- Documents & Collections
-- =========================================================

CREATE TABLE IF NOT EXISTS documents (
    document_content_id TEXT PRIMARY KEY,
    document_id TEXT NOT NULL UNIQUE,
    source_uri TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS collections (
    collection_name TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS document_collections (
    document_content_id TEXT NOT NULL,
    collection_name TEXT NOT NULL,
    PRIMARY KEY (document_content_id, collection_name),
    FOREIGN KEY (document_content_id) REFERENCES documents(document_content_id) ON DELETE CASCADE,
    FOREIGN KEY (collection_name) REFERENCES collections(collection_name) ON DELETE CASCADE
);

-- =========================================================
-- Entity Types
-- =========================================================

CREATE TABLE IF NOT EXISTS entity_types (
    entity_type_name TEXT PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS extracted_entity_types (
    document_content_id TEXT NOT NULL,
    entity_type_name TEXT NOT NULL,
    PRIMARY KEY (document_content_id, entity_type_name),
    FOREIGN KEY (document_content_id) REFERENCES documents(document_content_id) ON DELETE CASCADE,
    FOREIGN KEY (entity_type_name) REFERENCES entity_types(entity_type_name) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS entity_type_collections (
    entity_type_name TEXT NOT NULL,
    collection_name TEXT NOT NULL,
    PRIMARY KEY (entity_type_name, collection_name),
    FOREIGN KEY (collection_name) REFERENCES collections(collection_name) ON DELETE CASCADE,
    FOREIGN KEY (entity_type_name) REFERENCES entity_types(entity_type_name) ON DELETE CASCADE
);

-- =========================================================
-- Entities
-- =========================================================

CREATE TABLE IF NOT EXISTS entities (
    entity_id TEXT PRIMARY KEY,
    entity_content_id TEXT NOT NULL UNIQUE,
    entity_type_name TEXT NOT NULL,
    entity_properties TEXT NOT NULL,
    FOREIGN KEY (entity_type_name) REFERENCES entity_types(entity_type_name) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS extracted_entities (
    document_content_id TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    PRIMARY KEY (document_content_id, entity_id),
    FOREIGN KEY (document_content_id) REFERENCES documents(document_content_id) ON DELETE CASCADE,
    FOREIGN KEY (entity_id) REFERENCES entities(entity_id) ON DELETE CASCADE
);

-- =========================================================
-- Indexes
-- =========================================================

-- Entities
CREATE INDEX IF NOT EXISTS idx_entity_type_entities
ON entities(entity_type_name);

-- Entity Extraction
CREATE INDEX IF NOT EXISTS idx_document_collections
ON document_collections(document_content_id);

CREATE INDEX IF NOT EXISTS idx_collection_entity_types
ON entity_type_collections(collection_name);

CREATE INDEX IF NOT EXISTS idx_extracted_documents_entity_types
ON extracted_entity_types(document_content_id, entity_type_name);

CREATE INDEX IF NOT EXISTS idx_extracted_entity_types_documents
ON extracted_entity_types(entity_type_name, document_content_id);