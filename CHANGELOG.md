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
  - [🐛 Fixed](#-fixed)
  - [⚡ Performance](#-performance)
  - [🛠️ Build](#️-build)
  - [📝 Documentation](#-documentation)
- [\[0.5.1\] - 2026-10-16](#051---2026-10-16)
  - [🐛 Fixed](#-fixed-1)
  - [🛠️ Build](#️-build-1)
  - [📝 Documentation](#-documentation-1)
- [\[0.5.0\] - 2026-09-25](#050---2026-09-25)
  - [✨ Added](#-added-1)
  - [♻️ Changed](#️-changed-1)
  - [🔥 Removed](#-removed)
  - [🐛 Fixed](#-fixed-2)
  - [⚡ Performance](#-performance-1)
  - [📝 Documentation](#-documentation-2)
- [\[0.2.0\] - 2025-10-23](#020---2025-10-23)
  - [✨ Added](#-added-2)
  - [♻️ Changed](#️-changed-2)
  - [🐛 Fixed](#-fixed-3)
  - [⚡ Performance](#-performance-2)
  - [📝 Documentation](#-documentation-3)
- [\[0.1.0\] - 2025-07-25](#010---2025-07-25)
  - [✨ Added](#-added-3)
  - [🛠️ Build](#️-build-2)
  - [📝 Documentation](#-documentation-4)

## [Unreleased]

### ✨ Added

- **Anthropic** support as an **LLM** provider, with `claude-haiku-5-5` in both real-time and batch modes. The provider is inferred from the configured model name, and the default model is still `gpt-5.6-luna`. Response schemas are adapted to Anthropic's structured output limits, and fall back to unenforced instructions when they can't fit them. The model runs without thinking at the `low` effort level that extraction uses, and concurrent real-time requests sharing a cached prompt prefix wait for the first one to write the cache instead of all writing it.
- Response schemas that exceed the provider's structured output limits, or that the provider rejects, are sent as instructions for the rest of the run instead of stopping it, with a warning, for both **OpenAI** and **Anthropic**.
- A **pytest** suite under `tests/`, covering the **Anthropic** client against a mocked API and the resolution of the **LLM** settings.

### ♻️ Changed

- Only the API key of the configured model's provider is required: `OPENAI_API_KEY` for **OpenAI** models and `ANTHROPIC_API_KEY` for **Anthropic** models.
- The error for an unsupported model now lists the supported models of every provider.
- An extracted value of an optional field that doesn't satisfy its `options` or `regex` is now discarded on its own, falling back to the field's default, instead of discarding the whole entity or relationship.

### 🐛 Fixed

- A response that is valid JSON but not shaped like the expected result no longer crashes the run: items that aren't objects are skipped, and a malformed response is retried like invalid JSON.
- Deferred retries (timeouts, rate limits, server errors) are now bounded: a source extraction is marked as failed after 10 attempts of any kind across runs, instead of keeping the later pipeline steps from ever running.
- Responses cut off at the output token limit are no longer retried with the same request, which would be cut off again, and the tokens of cut-off and refused responses are now recorded in the usage metrics.
- An exhausted **OpenAI** quota now stops the run, instead of being treated as a rate limit that defers every job.
- In batch mode, the jobs of a batch that fails as a whole now count toward the 10-attempt limit, instead of being resubmitted on every run forever.
- In batch mode, a completed batch whose results can't be retrieved no longer blocks the pipeline forever: it is failed, and its jobs retried, once it is older than the maximum batch resolution time (30 hours). An **OpenAI** batch in which every request failed is now read from its error file instead of failing to retrieve.
- In batch mode, a response schema the provider rejects is now detected before submitting, by checking each distinct schema once per run, and is sent as instructions, instead of failing every request that uses it until they run out of attempts.
- In batch mode, the requests that an **OpenAI** batch finished before it expired or was cancelled are now kept, instead of being discarded and paid for again.
- In batch mode, failed results now follow the same retry rules as in real time (cut-off responses aren't retried, refusals are retried immediately), and the token usage of unsuccessful responses is recorded.

### ⚡ Performance

- Relationship results load their job's context (types, entity ID mapping and candidate entities) once per response, instead of once or twice per extracted relationship.

### 🛠️ Build

- Added the `anthropic` runtime dependency and the `pytest` development dependency.
- Ignored the **Ruff** rules `S101`, `PLR2004` and `SLF001` under `tests/`, so tests can use plain asserts, literal expected values and private members.

### 📝 Documentation

- Documented that an interrupted batch submission can leave a batch the engine doesn't track.
- Clarified that a field's `regex` is checked after extraction rather than shown to the LLM, and documented the 8,000-token cap of document-level extraction.
- Documented the **Anthropic** model, its API key, its response schema limits and how to switch providers with batches in flight.

[📚 Back to Table of Contents](#-table-of-contents)

## [0.5.1] - 2026-10-16

### 🐛 Fixed

- `requirements.txt` had drifted from `poetry.lock`, so the **Docker** image was installed with an outdated dependency set. It is now regenerated from the lockfile.
- The `reset` **CLI** subcommand, which is not implemented yet, silently exited with success. It now reports that it is not implemented and exits with status 1.

### 🛠️ Build

- **Ruff** and **Pyright** are now pinned as **Poetry** development dependencies, so the editor and the command line use the same versions.
- Ignored the **Ruff** rules `COM812`, which conflicts with the formatter, and `FIX002`, so TODO comments are allowed.
- Removed the obsolete `reportShadowedImports` **Pyright** setting.

### 📝 Documentation

- Updated the **Development Guidelines** with the command-line linting and type checking workflow, how to keep `requirements.txt` in sync, and the testing policy.
- Added a `CLAUDE.md` with project context for **Claude Code**.

[📚 Back to Table of Contents](#-table-of-contents)

## [0.5.0] - 2026-09-25

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
