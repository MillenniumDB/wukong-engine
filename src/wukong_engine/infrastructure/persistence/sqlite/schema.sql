-- =========================================================
-- Core Configuration
-- =========================================================
PRAGMA foreign_keys = ON;
-- =========================================================
-- Documents, Chunks & Collections
-- =========================================================
CREATE TABLE IF NOT EXISTS documents (
    content_id BLOB PRIMARY KEY,
    instance_id BLOB NOT NULL UNIQUE,
    source_uri TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS chunks (
    content_id BLOB PRIMARY KEY,
    instance_id BLOB NOT NULL UNIQUE,
    document_content_id BLOB NOT NULL,
    chunk_index INTEGER NOT NULL,
    start_offset INTEGER NOT NULL,
    end_offset INTEGER NOT NULL,
    content TEXT NOT NULL,
    FOREIGN KEY (document_content_id) REFERENCES documents(content_id) ON DELETE CASCADE,
    UNIQUE(document_content_id, chunk_index)
);
CREATE TABLE IF NOT EXISTS collections (collection_name TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS document_collections (
    document_content_id BLOB NOT NULL,
    collection_name TEXT NOT NULL,
    PRIMARY KEY (document_content_id, collection_name),
    FOREIGN KEY (document_content_id) REFERENCES documents(content_id) ON DELETE CASCADE,
    FOREIGN KEY (collection_name) REFERENCES collections(collection_name) ON DELETE CASCADE
);
-- =========================================================
-- Entity Types
-- =========================================================
CREATE TABLE IF NOT EXISTS entity_types (entity_type_name TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS entity_type_collections (
    context_level TEXT NOT NULL,
    entity_type_name TEXT NOT NULL,
    collection_name TEXT NOT NULL,
    PRIMARY KEY (collection_name, context_level, entity_type_name),
    FOREIGN KEY (collection_name) REFERENCES collections(collection_name) ON DELETE CASCADE,
    FOREIGN KEY (entity_type_name) REFERENCES entity_types(entity_type_name) ON DELETE CASCADE,
    CHECK (
        context_level IN (
            'DOCUMENT',
            'CHUNK'
        )
    )
);
CREATE TABLE IF NOT EXISTS entity_type_extractions (
    context_level TEXT NOT NULL,
    context_content_id BLOB NOT NULL,
    entity_type_name TEXT NOT NULL,
    extraction_status TEXT NOT NULL,
    PRIMARY KEY (
        context_level,
        context_content_id,
        entity_type_name
    ),
    FOREIGN KEY (entity_type_name) REFERENCES entity_types(entity_type_name) ON DELETE CASCADE,
    CHECK (
        context_level IN (
            'DOCUMENT',
            'CHUNK'
        )
    ),
    CHECK (
        extraction_status IN (
            'PENDING',
            'COMPLETED'
        )
    )
);
-- =========================================================
-- Entities
-- =========================================================
CREATE TABLE IF NOT EXISTS entities (
    content_id BLOB PRIMARY KEY,
    instance_id BLOB NOT NULL UNIQUE,
    entity_type_name TEXT NOT NULL,
    properties TEXT NOT NULL,
    FOREIGN KEY (entity_type_name) REFERENCES entity_types(entity_type_name) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS entity_provenance (
    context_level TEXT NOT NULL,
    context_content_id BLOB NOT NULL,
    entity_content_id BLOB NOT NULL,
    PRIMARY KEY (
        context_level,
        context_content_id,
        entity_content_id
    ),
    FOREIGN KEY (entity_content_id) REFERENCES entities(content_id) ON DELETE CASCADE,
    CHECK (
        context_level IN (
            'DOCUMENT',
            'CHUNK'
        )
    )
);
-- =========================================================
-- Indexes
-- =========================================================
-- Documents, Chunks & Collections
CREATE INDEX IF NOT EXISTS idx_dc_collection ON document_collections(collection_name);
-- Entities & Entity Types
CREATE INDEX IF NOT EXISTS idx_entities_type_entity ON entities(entity_type_name, content_id);
-- Entity Extraction
CREATE INDEX IF NOT EXISTS idx_ete_pending ON entity_type_extractions(
    context_level,
    extraction_status,
    context_content_id,
    entity_type_name
);