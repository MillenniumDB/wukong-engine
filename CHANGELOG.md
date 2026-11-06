<!-- omit from toc -->
# 📝 Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

<!-- omit from toc -->
## 📚 Table of Contents
- [\[Unreleased\]](#unreleased)
- [\[0.6.1\] - 2026-11-06](#061---2026-11-06)
  - [✨ Added](#-added)
  - [♻️ Changed](#️-changed)
  - [🐛 Fixed](#-fixed)
- [\[0.6.0\] - 2026-11-04](#060---2026-11-04)
  - [✨ Added](#-added-1)
  - [♻️ Changed](#️-changed-1)
  - [🔥 Removed](#-removed)
  - [🐛 Fixed](#-fixed-1)
  - [⚡ Performance](#-performance)
  - [🛠️ Build](#️-build)
  - [📝 Documentation](#-documentation)
- [\[0.5.1\] - 2026-10-16](#051---2026-10-16)
  - [🐛 Fixed](#-fixed-2)
  - [🛠️ Build](#️-build-1)
  - [📝 Documentation](#-documentation-1)
- [\[0.5.0\] - 2026-09-25](#050---2026-09-25)
  - [✨ Added](#-added-2)
  - [♻️ Changed](#️-changed-2)
  - [🔥 Removed](#-removed-1)
  - [🐛 Fixed](#-fixed-3)
  - [⚡ Performance](#-performance-1)
  - [📝 Documentation](#-documentation-2)
- [\[0.2.0\] - 2025-10-23](#020---2025-10-23)
  - [✨ Added](#-added-3)
  - [♻️ Changed](#️-changed-3)
  - [🐛 Fixed](#-fixed-4)
  - [⚡ Performance](#-performance-2)
  - [📝 Documentation](#-documentation-3)
- [\[0.1.0\] - 2025-07-25](#010---2025-07-25)
  - [✨ Added](#-added-4)
  - [🛠️ Build](#️-build-2)
  - [📝 Documentation](#-documentation-4)

## [Unreleased]

[📚 Back to Table of Contents](#-table-of-contents)

## [0.6.1] - 2026-11-06

This patch keeps failures outside an extraction's control from failing it for good, such as batch uploads timing out, and makes batch submission safer and visible. Some changes need attention when upgrading from `0.6.0`:

- Extractions now fail for good after 5 counted attempts instead of 10, so an extraction of an existing workspace already at 5 to 9 attempts fails on its next counted failure.
- Failures unrelated to an extraction are retried as many runs as needed, so `--until-done` keeps running through a long provider outage instead of giving up on the affected extractions.

### ✨ Added

- Batch submission shows a progress line for each uploaded batch, with the requests uploaded so far, the batches that failed to upload and the estimated time left.

### ♻️ Changed

- An extraction now fails for good after 5 counted attempts across runs, instead of 10, and an unusable response (refused or not valid JSON) is retried twice in the same run, instead of three times. Only failures that may come from the extraction itself are counted: rejected requests, real-time requests that time out, and unusable responses.
- **LLM** requests now wait up to 5 minutes for a response, instead of 2.
- Batches are uploaded 5 at a time, instead of 10.
- Counts from a million up are shortened to millions or billions (`12.35 M`) in the progress lines and run stats. `stats.json` keeps them in full.

### 🐛 Fixed

- Repeated failures unrelated to an extraction, such as batch uploads timing out, no longer fail it for good: provider outages, rate limits and server errors, batches that failed to upload or that the provider didn't finish, and interrupted runs are now retried as many runs as needed, without counting against its attempts.
- A batch creation whose response was lost is no longer retried by the provider's client, which could create a second, billed batch for the same jobs. The submission is left for the next run instead.
- An **OpenAI** batch error file line without a response no longer crashes the collection of the batch results.

[📚 Back to Table of Contents](#-table-of-contents)

## [0.6.0] - 2026-11-04

This release adds **Anthropic** as a second **LLM** provider, typed fields, symmetric relationships, run reporting, and adding documents to a workspace without resetting it. Some changes need attention when upgrading from `0.5.x`:

- Knowledge models, document registries and configurations are validated more strictly, so some that loaded before are now rejected (see [Changed](#️-changed-1)).
- A workspace's inputs are now snapshotted when first used: editing the knowledge model, the document registry or the `[chunking]` settings afterwards only takes effect after resetting the step that first used them, or with `--add-documents` for additions.
- **OpenAI**'s `gpt-4.1-mini` and `gpt-5.6-luna` are no longer supported. `gpt-6-luna` is the new default.
- Relationships that connect an entity to itself are now discarded unless their type sets `allow_self_relationships`.
- **Neo4j** imports need `--multiline-fields=true`, which the `import.sh` written with each export passes.

### ✨ Added

- **Anthropic** support as an **LLM** provider, with `claude-haiku-5-5` in both real-time and batch modes. The provider is inferred from the configured model name. Response schemas are adapted to Anthropic's structured output limits, and fall back to unenforced instructions when they can't fit them. The model runs at the `low` effort level, and concurrent real-time requests sharing a cached prompt prefix wait for the first one to write the cache instead of all writing it.
- Response schemas that exceed the provider's structured output limits, or that the provider rejects, are sent as instructions for the rest of the run instead of stopping it, with a warning, for both **OpenAI** and **Anthropic**.
- Batch cancellation at the provider: a batch that hasn't ended within 25 hours (a provider's 24-hour limit plus a margin) is cancelled at the provider and its finished requests are still collected (it is discarded after 26 hours if it doesn't end), and resetting an extraction step requests the cancellation of its batches in flight, without waiting for them to stop.
- A **pytest** suite under `tests/`, covering the **Anthropic** client against a mocked API and the resolution of the **LLM** settings.
- **OpenAI**'s `gpt-6-luna` as a supported model and the new default, replacing `gpt-5.6-luna`: in `benchmark/llm_effort/` it extracted as well or better at under half the cost. It runs at the `low` effort level with explicit prompt caching.
- An advanced `[llm]` `reasoning_effort` setting that overrides the reasoning effort of every extraction, which otherwise runs at `low` for every model.
- `reset` **CLI** command, which clears a workspace without running the pipeline, entirely or from a step onwards with `--from`, after a confirmation that `--yes` skips. It needs no configuration file: it only reads the API keys of the providers whose batches it cancels from the environment.
- `plan` **CLI** command, which shows the configuration and what `run` would do with the same arguments (which steps it runs, skips or resets, and which inputs it reads from their snapshots), without running, resetting or snapshotting anything.
- `status` **CLI** command, which shows the progress of each pipeline step in a workspace, including the batches pending at the provider, and whether the inputs changed since their snapshots were taken.
- `--until-done` flag for the `run` **CLI** command, which runs the pipeline again, waiting between runs, until every enabled step is completed, retrying failed runs unless their inputs caused the failure.
- `scripts/wukong.sh`, which runs any **CLI** command inside the **Docker** container. `scripts/wukong_run.sh` is kept as a shorthand for its `run` command.
- Symmetric relationship types, declared with `"symmetric": true`, whose endpoints are unordered: each endpoint is valid in both orientations, both orientations of a relationship share one identity and deduplicate into one relationship, and it is stored and exported as a single edge in a canonical order. Their `v1` identities carry a `SYMMETRIC` marker, so directed identities are unchanged.
- `allow_self_relationships` relationship type option, which lets a relationship connect an entity to itself.
- `integer`, `float`, `boolean` and `date` field data types, alongside `string`, each with its own parsing of extracted text, validation, merging and typed export (**MillenniumDB** literals and **Neo4j** column types). Integers are limited to ±(2^56−1) and floats to the 32-bit range, as **MillenniumDB** stores them. Dates may be partial (`YYYY`, `YYYY-MM` or `YYYY-MM-DD`), and a more precise date replaces a less precise one it agrees with when merging.
- `min` and `max` bounds for integer, float and date fields, checked after extraction and settable per context level for entities, and the `largest` and `smallest` merge strategies.
- Input snapshots: the knowledge model, the document registry and the `[chunking]` settings are copied to `staging/snapshots/` when the step that first uses them runs, and later runs read the copies until that step is reset, warning when the files changed. The model is only snapshotted once entities are extracted, so a workspace can still be tried step by step with `--reset` before the full run.
- `--add-documents` flag for the `run` and `plan` **CLI** commands, which ingests and extracts the documents not ingested yet while keeping every stored result. It accepts new files under existing sources, new sources or collections, and collections added to entity types. An addition that would leave already extracted relationships missing entities is refused before anything is written.
- Run progress at the default verbosity: each run prints its plan, each step a start line and an end line with its duration and main results, and extraction a progress line with the sources done, failures, objects, tokens and estimated time left.
- Run stats at the end of a completed pipeline: step durations (for the run and since the step was last reset), documents and chunks per collection, extraction results, token usage with an estimated cost, and the nodes, edges and files exported. They are also saved as `stats.json` next to the exported files.
- `init` **CLI** command, which writes a skeleton document registry and knowledge model into a workspace, never overwriting existing files.
- An `import.sh` script written with every **Neo4j** export, which imports all of its files with `neo4j-admin database import full`.
- If a document's file is gone or changed when document-level extraction runs, its text is rebuilt from its ingested chunks, logging the error and the fallback.
- Info logs (shown with `-v`) for every extracted value, entity and relationship that validation discards, naming the type, field and value.

### ♻️ Changed

- Only the API key of the configured model's provider is required: `OPENAI_API_KEY` for **OpenAI** models and `ANTHROPIC_API_KEY` for **Anthropic** models.
- The error for an unsupported model now lists the supported models of every provider.
- An extracted value of an optional field that doesn't satisfy its `options` or `regex` is now discarded on its own, falling back to the field's default, instead of discarding the whole entity or relationship.
- Generalized reasoning effort levels now map to each model's closest native level, and extraction uses each model's own default effort instead of the `low` level for every model, which doesn't change the effort any supported model runs at.
- A run that stops with steps left unfinished (e.g. while batches are pending) now says so, instead of reporting that the pipeline completed.
- Relationships that connect an entity to itself are now discarded unless their type sets `allow_self_relationships`, and the **LLM** is told so for every type with an endpoint between the same entity type.
- Exported relationship edges now carry whether their type is symmetric: `P_symmetric` in **MillenniumDB** and `_symmetric` in **Neo4j**.
- Knowledge models, document registries and configurations are validated more strictly. Unknown or misspelled keys, repeated JSON keys, context levels repeated in another case, the unimplemented `load` retrieval mode, default values on primary keys, endpoints allowing no context pair, names with a trailing newline and the field names `true` and `false` are now rejected. Invalid definition files are reported naming the file, and enabled types that can never be extracted are warned about.
- A field's `regex` must now match the whole value.
- String options, examples and defaults that extraction could never produce (empty, with surrounding whitespace, or containing NUL characters or lone UTF-16 surrogates) are rejected when the model loads, and so is a merge strategy or constraint that doesn't apply to a field's data type.
- A value that can't be converted to its field's data type counts as invalid (logged and discarded), not as missing.
- `[llm]` values are parsed like the other settings: an empty model is rejected, model and effort names are case-insensitive, and `max_concurrency` must be an integer.
- Only the collections of enabled entity types must exist.
- The extraction prompt no longer tells the **LLM** to preserve every value exactly as written, which contradicted `options`, `examples` and instructions asking for a canonical form. Values are preserved as expressed unless a definition specifies their form, without adding information.
- `config/default.toml` derives the chunk overlap from the target chunk size instead of fixing it at 120 tokens.
- The **Docker** container now runs with an init process, so stopping it (`docker stop` or `Ctrl+C`) stops the engine right away instead of after a 10-second timeout, and keeps stdin open so that confirmation prompts can be answered.

### 🔥 Removed

- **OpenAI**'s `gpt-4.1-mini` is no longer supported: it now costs more than `gpt-6-luna` and extracts worse.
- **OpenAI**'s `gpt-5.6-luna` is no longer supported, replaced by `gpt-6-luna` as the default model. Configurations naming it must switch to `gpt-6-luna`.

### 🐛 Fixed

- A run whose knowledge model failed to load after its document registry was read no longer leaves a snapshot of the registry behind, as if documents had been ingested with it: inputs are now all loaded before any snapshot is taken.
- A response that is valid JSON but not shaped like the expected result no longer crashes the run: items that aren't objects are skipped, and a malformed response is retried like invalid JSON.
- Deferred retries (timeouts, rate limits, server errors) are now bounded: a source extraction is marked as failed after 10 attempts of any kind across runs, instead of keeping the later pipeline steps from ever running.
- Responses cut off at the output token limit are no longer retried with the same request, which would be cut off again, and the tokens of cut-off and refused responses are now recorded in the usage metrics.
- An exhausted **OpenAI** quota now stops the run, instead of being treated as a rate limit that defers every job.
- In batch mode, the jobs of a batch that fails as a whole now count toward the 10-attempt limit, instead of being resubmitted on every run forever.
- In batch mode, a completed batch whose results can't be retrieved no longer blocks the pipeline forever: it is failed, and its jobs retried, once it is older than the maximum batch resolution time (25 hours). An **OpenAI** batch in which every request failed is now read from its error file instead of failing to retrieve.
- In batch mode, a response schema the provider rejects is now detected before submitting, by checking each distinct schema once per run, and is sent as instructions, instead of failing every request that uses it until they run out of attempts.
- In batch mode, the requests that an **OpenAI** batch finished before it expired or was cancelled are now kept, instead of being discarded and paid for again.
- In batch mode, entity and relationship extraction now only list their own active batches, which share one table, so each step synchronizes (and cancels) only its own batches.
- Extracted values are normalized before being validated, instead of being dropped (or, for a required field, dropping their item) when they don't come as the expected text, which mostly happens when the provider doesn't enforce the schema: booleans and numbers become their text (a JSON `true` was stored as `True`, missing the `true` option), a single-element list becomes its element, strings are trimmed, empty and `null` strings count as missing, options and type names match regardless of case, and objects are no longer stored as their Python representation.
- A response whose JSON is surrounded by text or followed by extra data is decoded from its first JSON object or array, instead of failing to decode and being retried.
- In batch mode, failed results now follow the same retry rules as in real time (cut-off responses aren't retried, refusals are retried immediately), and the token usage of unsuccessful responses is recorded.
- The whole step plan is checked before anything is reset, so a `--reset` run can no longer wipe results and then abort.
- Strings are exported in the form each format decodes: raw in **Neo4j** CSV files, since `neo4j-admin import` doesn't decode backslash escapes, and with only the escapes **MillenniumDB** decodes.
- Extracted strings drop NUL characters and replace lone UTF-16 surrogates with U+FFFD, either of which broke the export files or their import.
- Edges to entity types left out of the export (provenance links and relationships) are skipped, so no edge points at a missing node.
- An export directory is only replaced once the export succeeds, so a failed export keeps the previous one and no stale files linger.
- Document discovery stays inside the data root when following symlinks, skips hidden directories and walks in name order. Unreadable, non-UTF-8 and empty files are skipped with a warning instead of aborting ingestion, a BOM is dropped, and whitespace-only chunks are no longer emitted.
- The chunker no longer drops characters at hard splits or overlap boundaries with small budgets, and truncation cuts the original text instead of decoding tokens.
- The `longest` and `shortest` merge strategies break length ties the same way in any order, instead of depending on the order extraction jobs finish in.
- An exact option match now wins over a case-insensitive one.

### ⚡ Performance

- Relationship results load their job's context (types, entity ID mapping and candidate entities) once per response, instead of once or twice per extracted relationship.
- Documents already stored are only linked to the collection being ingested, not loaded and chunked again, so ingesting again, or ingesting a document that belongs to several collections, no longer re-chunks it.

### 🛠️ Build

- Added the `anthropic` runtime dependency and the `pytest` development dependency.
- Ignored the **Ruff** rules `S101`, `PLR2004` and `SLF001` under `tests/`, so tests can use plain asserts, literal expected values and private members.
- Added a shared **Claude Code** hook that runs **Ruff** on every Python file Claude writes or edits, and excluded the `paper/` research material from **Ruff**.

### 📝 Documentation

- Documented that an interrupted batch submission can leave a batch the engine doesn't track.
- Clarified that a field's `regex` is checked after extraction rather than shown to the LLM, and documented the 8,000-token cap of document-level extraction.
- Documented the **Anthropic** model, its API key, its response schema limits and how to switch providers with batches in flight.
- Documented symmetric relationships, self-relationships, their identities and how to query symmetric edges.
- Documented the field data types, their bounds and merge strategies, and what can vary per context level.
- Documented input snapshots, adding documents to a workspace, the run stats and `stats.json`.
- Documented the **Neo4j** import script, how **MillenniumDB** stores very small floats, and how to look up chunk provenance in **MillenniumDB** through a text index.
- Documented that the `keep` and `replace` merge strategies depend on the order extraction jobs finish in.
- Documented the **Claude Code** **Ruff** hook in the **Development Guidelines**.

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
