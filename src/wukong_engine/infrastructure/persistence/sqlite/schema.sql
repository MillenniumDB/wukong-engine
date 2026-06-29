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
-- Entities
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
-- Relationships
-- =========================================================
CREATE TABLE IF NOT EXISTS relationship_types (relationship_type_name TEXT PRIMARY KEY);
CREATE TABLE IF NOT EXISTS relationship_type_endpoints (
    relationship_type_name TEXT NOT NULL,
    source_entity_type_name TEXT NOT NULL,
    target_entity_type_name TEXT NOT NULL,
    source_context_level TEXT NOT NULL,
    target_context_level TEXT NOT NULL,
    PRIMARY KEY (
        relationship_type_name,
        source_entity_type_name,
        target_entity_type_name,
        source_context_level,
        target_context_level
    ),
    FOREIGN KEY (relationship_type_name) REFERENCES relationship_types(relationship_type_name) ON DELETE CASCADE,
    FOREIGN KEY (source_entity_type_name) REFERENCES entity_types(entity_type_name) ON DELETE CASCADE,
    FOREIGN KEY (target_entity_type_name) REFERENCES entity_types(entity_type_name) ON DELETE CASCADE,
    CHECK (
        source_context_level IN (
            'DOCUMENT',
            'CHUNK'
        )
    ),
    CHECK (
        target_context_level IN (
            'DOCUMENT',
            'CHUNK'
        )
    )
);
CREATE TABLE IF NOT EXISTS relationships (
    content_id BLOB PRIMARY KEY,
    instance_id BLOB NOT NULL UNIQUE,
    relationship_type_name TEXT NOT NULL,
    source_entity_content_id BLOB NOT NULL,
    target_entity_content_id BLOB NOT NULL,
    properties TEXT NOT NULL,
    FOREIGN KEY (relationship_type_name) REFERENCES relationship_types(relationship_type_name) ON DELETE CASCADE,
    FOREIGN KEY (source_entity_content_id) REFERENCES entities(content_id) ON DELETE CASCADE,
    FOREIGN KEY (target_entity_content_id) REFERENCES entities(content_id) ON DELETE CASCADE
);
CREATE TABLE IF NOT EXISTS relationship_provenance (
    chunk_content_id BLOB NOT NULL,
    relationship_content_id BLOB NOT NULL,
    PRIMARY KEY (
        chunk_content_id,
        relationship_content_id
    ),
    FOREIGN KEY (relationship_content_id) REFERENCES relationships(content_id) ON DELETE CASCADE,
    FOREIGN KEY (chunk_content_id) REFERENCES chunks(content_id) ON DELETE CASCADE
);
-- =========================================================
-- Extraction
-- =========================================================
CREATE TABLE IF NOT EXISTS entity_extractions (
    context_level TEXT NOT NULL,
    context_content_id BLOB NOT NULL,
    entity_type_name TEXT NOT NULL,
    extraction_status TEXT NOT NULL,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
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
            'IN_PROGRESS',
            'RETRY',
            'COMPLETED',
            'FAILED'
        )
    )
);
CREATE TABLE IF NOT EXISTS relationship_extractions (
    chunk_content_id BLOB NOT NULL,
    relationship_type_name TEXT NOT NULL,
    extraction_status TEXT NOT NULL,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    failed_attempts INTEGER NOT NULL DEFAULT 0,
    last_error TEXT,
    PRIMARY KEY (
        chunk_content_id,
        relationship_type_name
    ),
    FOREIGN KEY (chunk_content_id) REFERENCES chunks(content_id) ON DELETE CASCADE,
    FOREIGN KEY (relationship_type_name) REFERENCES relationship_types(relationship_type_name) ON DELETE CASCADE,
    CHECK (
        extraction_status IN (
            'PENDING',
            'IN_PROGRESS',
            'RETRY',
            'COMPLETED',
            'FAILED'
        )
    )
);
CREATE TABLE IF NOT EXISTS extraction_jobs (
    job_id BLOB PRIMARY KEY,
    job_type TEXT NOT NULL,
    job_status TEXT NOT NULL,
    context_level TEXT NOT NULL,
    context_content_id BLOB NOT NULL,
    created_at INTEGER NOT NULL,
    finished_at INTEGER,
    input_tokens INTEGER,
    cached_tokens INTEGER,
    output_tokens INTEGER,
    reasoning_tokens INTEGER,
    batch_id BLOB,
    error TEXT,
    CHECK (
        job_type IN (
            'ENTITY_EXTRACTION',
            'RELATIONSHIP_EXTRACTION'
        )
    ),
    CHECK (
        job_status IN (
            'IN_PROGRESS',
            'COMPLETED',
            'FAILED'
        )
    ),
    CHECK (
        context_level IN (
            'DOCUMENT',
            'CHUNK'
        )
    ),
    FOREIGN KEY (batch_id) REFERENCES extraction_batches(batch_id) ON DELETE
    SET NULL
);
CREATE TABLE IF NOT EXISTS extraction_batches (
    batch_id BLOB PRIMARY KEY,
    provider_name TEXT NOT NULL,
    provider_batch_id TEXT NOT NULL,
    batch_status TEXT NOT NULL,
    created_at INTEGER NOT NULL,
    finished_at INTEGER,
    error TEXT,
    UNIQUE(provider_name, provider_batch_id),
    CHECK (
        batch_status IN (
            'SUBMITTED',
            'IN_PROGRESS',
            'COMPLETED',
            'FAILED',
            'CANCELLED'
        )
    )
);
CREATE TABLE IF NOT EXISTS pipeline_checkpoints (
    checkpoint_name TEXT PRIMARY KEY,
    checkpoint_status TEXT NOT NULL,
    updated_at INTEGER NOT NULL,
    CHECK (
        checkpoint_status IN (
            'PENDING',
            'COMPLETED'
        )
    )
);
-- =========================================================
-- Indexes
-- =========================================================
-- Documents, Chunks & Collections
CREATE INDEX IF NOT EXISTS idx_dc_collection_document ON document_collections(collection_name, document_content_id);
-- Entities
CREATE INDEX IF NOT EXISTS idx_entities_type_id ON entities(entity_type_name, content_id);
CREATE INDEX IF NOT EXISTS idx_ep_entity_level_ctx ON entity_provenance(
    entity_content_id,
    context_level,
    context_content_id
);
CREATE INDEX IF NOT EXISTS idx_etc_type_level_name ON entity_type_collections(entity_type_name, context_level, collection_name);
-- Relationships
-- Extraction
CREATE INDEX IF NOT EXISTS idx_ee_level_status_ctx_type ON entity_extractions(
    context_level,
    extraction_status,
    context_content_id,
    entity_type_name
);
CREATE INDEX IF NOT EXISTS idx_ee_level_ctx_status ON entity_extractions(
    context_level,
    context_content_id,
    extraction_status
);
CREATE INDEX IF NOT EXISTS idx_jobs_batch_status_type ON extraction_jobs(batch_id, job_status, job_type);
CREATE INDEX IF NOT EXISTS idx_jobs_type_status_batch ON extraction_jobs(job_type, job_status, batch_id);
CREATE INDEX IF NOT EXISTS idx_jobs_type_level_status ON extraction_jobs(
    job_type,
    context_level,
    job_status
);
CREATE INDEX IF NOT EXISTS idx_batches_status_created_id ON extraction_batches(batch_status, created_at, batch_id);