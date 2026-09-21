<!-- omit from toc -->
# ⚙️ Configuration

This document describes the environment variables and the engine configuration file.

<!-- omit from toc -->
## 📚 Table of Contents
- [🌍 Environment Variables](#-environment-variables)
- [🔧 Engine Configuration](#-engine-configuration)
- [➡️ Pipeline](#️-pipeline)
- [🤖 LLM](#-llm)
- [✂️ Chunking](#️-chunking)
- [📤 Export](#-export)
- [💡 Configuration File Example](#-configuration-file-example)

## 🌍 Environment Variables

The engine uses **environment variables** for secrets that must not live in a configuration file:

| Variable         | Required | Description                         | Example              |
| ---------------- | :------: | ----------------------------------- | -------------------- |
| `OPENAI_API_KEY` |    ✅     | OpenAI API key for LLM interaction. | `sk-xxxxxxxxxxxxxxx` |

These variables are listed in the `.env.example` file in the root directory of the project, which serves as a template with placeholder values.

For **local development/usage**, create a `.env` file in the root directory of the project and copy the contents from `.env.example` into it, replacing the placeholders with real values. The engine loads `.env` at startup without overriding variables that are already set in the environment.

For **production/deployment**, set these variables directly in your server/cloud environment.

A missing or empty `OPENAI_API_KEY` aborts the run.

[📚 Back to Table of Contents](#-table-of-contents)

## 🔧 Engine Configuration

The engine is configured through a [TOML](https://toml.io/en/) file, passed with the `--config` option:

```sh
poetry run wukong run <path/to/workspace_dir> <path/to/data_dir> --config <path/to/config.toml>
```

If no configuration is given, the engine uses `config/default.toml`, which runs the entire pipeline with the recommended values.

The file has four sections, all of them optional. Any section or individual key you leave out falls back to the built-in default shown in the tables below, so a configuration file only needs to state what it changes:

```toml
[pipeline]
# ...which steps to run...

[llm]
# ...which model, how, and how fast...

[chunking]
# ...how documents are segmented...

[export]
# ...what the output looks like...
```

[📚 Back to Table of Contents](#-table-of-contents)

## ➡️ Pipeline

The `[pipeline]` section selects which steps of the pipeline are executed. Each step is a boolean.

| Key                     | Description                                                                                                        |  Type  | Default |
| ----------------------- | -------------------------------------------------------------------------------------------------------------------- | :----: | :-----: |
| `ingest_documents`      | Read, register and segment the documents declared in the workspace's document collections.                         | `bool` | `true`  |
| `extract_entities`      | Extract entities from the ingested documents, at the context levels declared in the knowledge model.               | `bool` | `true`  |
| `extract_relationships` | Extract relationships between the already-extracted entities.                                                      | `bool` | `true`  |
| `export_knowledge`      | Render the extracted knowledge into the configured output format.                                                  | `bool` | `true`  |

The steps run in the order listed and each depends on the ones before it. Disabling a step does **not** skip its results: because state is durable in the workspace's staging database, a disabled step whose work was completed on an earlier run still satisfies the dependency. Disabling a step whose work has *never* been completed aborts the run with a clear error, rather than producing a partial result.

This is what lets you re-export without re-extracting, or add a relationship type and extract only it, by enabling just the step you need.

[📚 Back to Table of Contents](#-table-of-contents)

## 🤖 LLM

The `[llm]` section controls the language model used for extraction.

| Key               | Description                                                                                      |   Type    | Default          |
| ----------------- | -------------------------------------------------------------------------------------------------- | :-------: | ---------------- |
| `model`           | The model to use. Only OpenAI models are currently supported.                                    | `string`  | `"gpt-5.6-luna"` |
| `execution_mode`  | How requests reach the provider. See below.                                                      | `string`  | `"real-time"`    |
| `max_concurrency` | Maximum number of in-flight LLM calls in real-time mode. Must be at least 1.                     | `integer` | `5`              |

**Supported models:**

| Model            | Notes                                                    |
| ---------------- | -------------------------------------------------------- |
| `"gpt-5.6-luna"` | Reasoning model, runs at `low` effort. Balanced default. |
| `"gpt-4.1-mini"` | Non-reasoning. Cheaper, lower quality.                   |

**Execution modes:**

| Value           | Aliases                                                       | Behaviour                                                                                                                                                              |
| --------------- | ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `"real-time"`   | `"realtime"`, `"real_time"`, `"sync"`, `"synchronous"`, `"immediate"` | Requests are issued concurrently and results consumed as they complete. Low latency, finishes in one sitting, standard pricing.                                        |
| `"batch"`       | `"batched"`, `"async"`, `"asynchronous"`, `"queue"`, `"queued"`, `"deferred"` | Requests are grouped and submitted to the provider's asynchronous batch interface. Substantially cheaper per token, in exchange for a delayed, best-effort turnaround. |

Both modes share the same work plan, validation and identity logic, so you can prototype interactively on a subset and then run the full corpus in batch mode by changing nothing but this key. In batch mode a run may be submitted in one session and collected in another.

`max_concurrency` only applies to real-time mode, and the binding constraint is the provider's rate limits rather than local resources. Reference values for OpenAI usage tiers with mini models:

| Tier   | Suggested `max_concurrency` |
| ------ | :-------------------------: |
| Tier 1 |              1              |
| Tier 2 |              8              |
| Tier 3 |             15              |
| Tier 4 |             35              |
| Tier 5 |             500             |

[📚 Back to Table of Contents](#-table-of-contents)

## ✂️ Chunking

The `[chunking]` section controls how documents are segmented into the text chunks that chunk-level extraction reads.

| Key              | Description                                                                                 |   Type    | Default  |
| ---------------- | ----------------------------------------------------------------------------------------------- | :-------: | -------- |
| `target_tokens`  | The size each chunk aims for. Must be in `[1, 5000]`; the recommended range is `[100, 2000]`, and a value outside it logs a warning. | `integer` | `800`    |
| `overlap_tokens` | Tokens shared between consecutive chunks. Must be in `[0, target_tokens - 1]`.              | `integer` | derived  |

When `overlap_tokens` is omitted it is derived from `target_tokens` as `min(max(20, 0.15 × target_tokens), target_tokens / 3, 200)` — so a target of 800 yields an overlap of 120. There is also an internal hard maximum per chunk, derived as `min(1.3 × target_tokens, 10000)`, which is not user-configurable.

Segmentation proceeds recursively along a hierarchy of boundaries, from most to least semantically meaningful — structural headings, paragraphs, lines, sentences, and finally words — so chunk boundaries coincide with document structure wherever the structure permits. The target size is treated as *soft*: when adding the next piece would overshoot, the packer keeps whichever alternative lands closer to the target.

These two values are the main quality/cost trade-off available:

- **Smaller chunks** mean cheaper calls, a more focused model and finer-grained provenance.
- **Larger chunks** mean fewer facts split across a boundary, and less per-call overhead.
- **More overlap** protects statements that straddle a boundary, at the cost of reading the same text more than once. It interacts well with deduplication: the same fact seen in two overlapping chunks converges to one object with two mentions, not two objects.

Adjust them against the model's context window and the provider's request/response size limits.

[📚 Back to Table of Contents](#-table-of-contents)

## 📤 Export

The `[export]` section selects the output format.

| Key      | Description                    |   Type   | Default |
| -------- | ------------------------------ | :------: | ------- |
| `format` | The format to render the extracted knowledge into. | `string` | `"mdb"` |

| Value     | Aliases            | Output                                                                     |
| --------- | ------------------ | ---------------------------------------------------------------------------- |
| `"mdb"`   | `"millenniumdb"`   | A MillenniumDB QM (Quad Model) file at `<workspace>/exports/mdb/knowledge_graph.qm`. |
| `"neo4j"` | —                  | Neo4j bulk-import CSV files under `<workspace>/exports/neo4j/`.            |

Only the selected format is written. Rendering is a deterministic traversal of the staging database and costs nothing compared to extraction, so producing a second format is a matter of changing this key and re-running with only `export_knowledge` enabled — no re-extraction required.

> 📂 For the exact layout of the exported files, refer to the [Workspace](/docs/workspace.md) documentation.

[📚 Back to Table of Contents](#-table-of-contents)

## 💡 Configuration File Example

A fully commented configuration file is provided at [`config/default.toml`](/config/default.toml).

[📚 Back to Table of Contents](#-table-of-contents)
