<!-- omit from toc -->
# 📝 Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

<!-- omit from toc -->
## 📚 Table of Contents
- [\[Unreleased\]](#unreleased)
  - [✨ Added](#-added)
  - [♻️ Changed](#️-changed)
  - [🔥 Removed](#-removed)
  - [🐛 Fixed](#-fixed)
  - [⚡ Performance](#-performance)
  - [📝 Documentation](#-documentation)
- [\[0.2.0\] - 2025-10-23](#020---2025-10-23)
  - [✨ Added](#-added-1)
  - [♻️ Changed](#️-changed-1)
  - [🐛 Fixed](#-fixed-1)
  - [⚡ Performance](#-performance-1)
  - [📝 Documentation](#-documentation-1)
- [\[0.1.0\] - 2025-07-25](#010---2025-07-25)
  - [✨ Added](#-added-2)
  - [🛠️ Build](#️-build)
  - [📝 Documentation](#-documentation-2)

## [Unreleased]

This entry covers a substantial redesign of the engine. The extraction model, the
execution model, the on-disk layout and the internal architecture have all changed,
and the changes are **not backwards compatible** with a `0.2.0` data directory.

### ✨ Added

- **Workspaces**, which hold the knowledge model, the document collection registry, the run state and the exports. The engine is now invoked with a workspace directory and a separate, read-only data directory.
- **Document collection registry** (`document_collections.json`), mapping named collections to sources inside the data directory, with `file`, `directory` and `recursive` source modes.
- **Two-level extraction context**: entity types declare whether their instances are properties of a document as a whole (`document`) or things mentioned inside it (`chunk`), and may specialize their instructions, patterns, defaults and retrieval modes per level.
- **Entity-grounded relationship extraction**: relationships are extracted as a matching over a candidate set of already-extracted entities, presented with request-local identifiers, so endpoints are valid by construction and cannot be invented.
- **Relationship endpoints** with context level pairings, declaring not just which entity types may be connected but at which levels, and used to prune extraction work before any LLM call is issued.
- **Deterministic, declarative identity**: content-derived identifiers computed from a normalized primary key and an explicit identity policy, making deduplication a property of the schema rather than a post-processing step.
- **Identity policies for relationships**: `primary_key`, `endpoints` and `none`.
- **Field-level merge strategies** (`keep`, `replace`, `longest`, `shortest`) for reconciling repeated observations, with a per-type default and per-field overrides. A null value never overwrites a non-null one.
- **Durable staging database** (SQLite) holding documents, chunks, extracted objects and the state of every unit of work, which makes runs resumable and re-runs incremental.
- **Typed failure handling**: immediate retry, deferred retry and critical failure, with bounded attempt budgets, inter-pass state recovery and graceful termination that preserves in-flight results.
- **Asynchronous batch execution mode**, submitting grouped requests to the provider's batch interface at substantially lower cost, with submission, polling and resolution tracked across sessions.
- **Recursive, boundary-aware chunking** along a hierarchy of headings, paragraphs, lines, sentences and words, with configurable target and overlap token counts and soft target packing.
- **Extraction metrics**: per-status progress and timing, call throughput with a smoothed completion estimate, object and mention counts, and token accounting broken down into non-overlapping uncached input, cache read, cache write, output and reasoning tokens, so that the cost of a run follows from the provider's current rate for each category.
- **Projection**, selecting which entity and relationship types are active for a run. Inactive types are never extracted, stored or exported, and a relationship type whose endpoints are all inactive deactivates itself.
- **Field constraints** used both to shape the request and to validate the reply: closed vocabularies, examples, regular expressions, default values and a required flag.
- **Primary key normalization** (Unicode normalization and transliteration, case folding, dash and whitespace unification, trimming) applied before any identity comparison.
- Support for **GPT 5.6 Luna** and generalized reasoning effort levels.
- `run` subcommand for the **CLI**, taking a workspace and a data directory, with `-v`/`-vv` verbosity and a `--reset` flag.
- Research **paper draft** and a full **Text2KGBench** evaluation harness, protocol and results under `paper/`.

### ♻️ Changed

- **The data model is now the knowledge model.** The concept previously called the *graph model* is named the *knowledge model* throughout the code, the documentation and the paper, and `graph_model.json` is now `knowledge_model.json`. The engine extracts knowledge, and graphs are one of the formats that knowledge can be exported to.
- **Architecture** rebuilt on clean architecture layers (`core`, `app`, `infrastructure`, `bootstrap`, `presentation`), with ports and adapters throughout.
- **On-disk layout** split into a workspace directory and a data directory, replacing the single data directory that previously held both the model and the documents.
- **Configuration file** restructured into `[pipeline]`, `[llm]`, `[chunking]` and `[export]` sections. Every key is now optional and falls back to a built-in default.
- **Pipeline steps** renamed and re-scoped to `ingest_documents`, `extract_entities`, `extract_relationships` and `export_knowledge`, each with explicit dependency checks against durable checkpoints.
- **Exports** are written into the workspace, under `exports/<format>/`.
- **Default LLM** is now `gpt-5.6-luna`, running at a low reasoning effort.
- **Extraction requests are grouped per source context** rather than issued per type, so the source text is transmitted once and the LLM can discriminate between similar types instead of judging each in isolation.
- **Example corpus** replaced with a set of invented mission reports, crew dossiers and incident reports from a fictional deep-space agency, paired with a knowledge model that exercises both context levels, cross-level endpoints, closed vocabularies and merge strategies.
- **Invalid output is discarded rather than repaired.** An object whose required fields are missing, whose values violate their declared vocabulary or pattern, or whose primary key does not survive normalization, is dropped and counted.

### 🔥 Removed

- **JSON export format.** The supported formats are now `mdb` (MillenniumDB) and `neo4j`.
- **Approximate deduplication.** Identity is exact on the normalized primary key. The recommended substitute is to move canonicalization into the schema, with a declared pattern and worked examples on the primary key field.
- **Metadata files.** The `docs/metadata/` directory and property extraction from it are gone.
- **Hybrid entities and document sets**, superseded by context levels and document collections.
- Configuration parameters `export_formats`, `max_tokens` and `max_worker_threads`, superseded by `export.format`, `chunking.target_tokens` and `llm.max_concurrency`.

### 🐛 Fixed

- Batches submitted to the OpenAI Batch API could remain unresolved forever, stalling a run.
- Error when clearing a non-existent export directory.
- Document ingestion picked up hidden and temporary system `.txt` files.
- Frozen worker when the LLM API never responded.

### ⚡ Performance

- Endpoint pruning skips chunks and relationship types that provably cannot produce a result, eliminating the corresponding LLM calls entirely.
- Request grouping per source context amortizes the source text across all pending types for that source.
- Document-level extraction reads a bounded prefix of each document rather than the whole text.
- Fields that are defaulted or skipped never enter a prompt.
- SQLite indexes for extraction jobs, batches and provenance streaming queries.
- **Explicit prompt caching** on models that support it (`gpt-5.6-luna`). Each prompt is split into a prefix shared by every job extracting the same types (document context, task and type definitions) and the job-specific part (available entities and source text). Only the shared prefix is cached, instead of every request paying the cache-write rate for a whole prompt that no other request can reuse.

### 📝 Documentation

- Rewrote the **README** around workspaces, the knowledge model and the current CLI.
- Rewrote the **Knowledge Model** documentation (`docs/knowledge-model.md`, previously `docs/graph-model.md`) against the current schema, including identity, identifier versioning, merging and reserved names.
- Added **Workspace** documentation (`docs/workspace.md`) covering the workspace layout, the document collection registry and the export output.
- Rewrote the **Configuration** documentation against the current TOML sections, and corrected stale default values in the shipped configuration comments.
- Rewrote the **Project Structure** documentation against the current layout.
- Added **Architecture Guidelines** documenting the layering, ports and adapters, and naming conventions the implementation follows.
- Removed the roadmap section from the README.

[📚 Back to Table of Contents](#-table-of-contents)

## [0.2.0] - 2025-10-23

### ✨ Added

- Document set logic for processing different types of documents.
- Support for **Hybrid Entities**, which act as both core and local entities.
- Support for extracting property values from available metadata files associated with the documents.
- Support for placeholder and default property values.
- Support for regex matching when extracting property values.
- General statistics file for the knowledge graph after exporting.
- String representation method for the data model.

### ♻️ Changed

- Data directory structure to support document set logic.

### 🐛 Fixed

- Frozen thread issue where the LLM API never responds.

### ⚡ Performance

- Trim large documents for **Core Entity** extraction.

### 📝 Documentation

- Updated data model docs with new fields.
- Updated data directory structure in docs.

[📚 Back to Table of Contents](#-table-of-contents)

## [0.1.0] - 2025-07-25

### ✨ Added

- Initial release of the **WUKONG** engine.
- Data model schema for representing knowledge graphs.
- Configuration file for engine settings.
- Support for a custom configuration file provided by the user.
- Support for processing plain text documents.
- Support for **GPT 4.1-mini** as the default **LLM** for extracting information from documents.
- Support for exporting knowledge graphs in **MDB**, **Neo4j** and **JSON** format.
- Basic command-line interface **(CLI)** for running the engine.
- Example data directory structure for testing purposes.
- Basic error handling and logging functionality.
- Support for loading environment variables via a `.env` file.
- **WUKONG** engine logos.

### 🛠️ Build

- **Docker** support for containerization on **Linux/MacOS/Windows**.
- **Poetry** configuration for dependency management.
- Linting and formatting setup with **Ruff** and **Pyright**.

### 📝 Documentation

- Initial documentation and basic license for the project.

[📚 Back to Table of Contents](#-table-of-contents)
