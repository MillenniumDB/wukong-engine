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

| Variable            |        Required        | Description                            | Example                  |
| ------------------- | :--------------------: | -------------------------------------- | ------------------------ |
| `OPENAI_API_KEY`    | With an OpenAI model    | OpenAI API key for LLM interaction.    | `sk-xxxxxxxxxxxxxxx`     |
| `ANTHROPIC_API_KEY` | With an Anthropic model | Anthropic API key for LLM interaction. | `sk-ant-xxxxxxxxxxxxxxx` |

These variables are listed in the `.env.example` file in the root directory of the project, which serves as a template with placeholder values.

For **local development/usage**, create a `.env` file in the root directory of the project and copy the contents from `.env.example` into it, replacing the placeholders with real values. The engine loads `.env` at startup without overriding variables that are already set in the environment.

For **production/deployment**, set these variables directly in your server/cloud environment.

Only the key of the provider of the configured [model](#-llm) is required, and a missing or empty one aborts the run. The key of another provider is only needed while batches submitted to it are still pending (see [batch mode after switching providers](#-llm)).

[📚 Back to Table of Contents](#-table-of-contents)

## 🔧 Engine Configuration

The engine is configured through a [TOML](https://toml.io/en/) file, passed with the `--config` option:

```sh
poetry run wukong run <path/to/workspace_dir> <path/to/data_dir> --config <path/to/config.toml>
```

If no configuration is given, the engine uses `config/default.toml`, which runs the entire pipeline with the recommended values.

The file has four sections, all of them optional. Any section or individual key you leave out falls back to the built-in default shown in the tables below, so a configuration file only needs to state what it changes. A section or key the engine doesn't know, such as a misspelled one, aborts the run instead of being ignored:

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

The steps run in the order listed and each depends on the ones before it. Disabling a step does **not** skip its results: because state is durable in the workspace's staging database, a disabled step whose work was completed on an earlier run still satisfies the dependency. Disabling a step whose work has *never* been completed aborts the run with a clear error, rather than producing a partial result. The whole plan is checked before anything runs, so such a run aborts without running or resetting any step.

This is what lets you re-export without re-extracting, or test each step in isolation while setting up a workspace, by enabling just the step you need. The inputs a step has used stay fixed until it is reset; see [Input Snapshots](/docs/workspace.md#-input-snapshots).

[📚 Back to Table of Contents](#-table-of-contents)

## 🤖 LLM

The `[llm]` section controls the language model used for extraction.

| Key               | Description                                                                                      |   Type    | Default          |
| ----------------- | -------------------------------------------------------------------------------------------------- | :-------: | ---------------- |
| `model`           | The model to use, case-insensitive. Its provider is inferred from the name. An empty name is rejected; omit the key to use the default. | `string`  | `"gpt-6-luna"`   |
| `execution_mode`  | How requests reach the provider. See below.                                                      | `string`  | `"real-time"`    |
| `max_concurrency` | Maximum number of in-flight LLM calls in real-time mode. Must be at least 1.                     | `integer` | `5`              |
| `reasoning_effort` | ⚙️ Advanced. Overrides the reasoning effort of every model, `low` by default. Case-insensitive. See below. | `string`  | Model's default  |

**Supported models:**

| Model                | Provider  | Notes                                                    |
| -------------------- | --------- | -------------------------------------------------------- |
| `"gpt-6-luna"`       | OpenAI    | Reasoning model, runs at `low` effort. Default.          |
| `"claude-haiku-5-5"` | Anthropic | Reasoning model, runs at `low` effort. Lower recall.     |

> ⚠️ Response schemas are enforced by the provider whenever possible, so that every response follows them. A schema that exceeds the provider's documented limits, or that the provider rejects, is sent as instructions instead for the rest of the run, and a warning is logged once per schema. In batch mode, where a rejection would otherwise only show up as an error of every request using the schema, each distinct schema is checked once per run before it's submitted: for free through **OpenAI**'s token counting, and with a one-token request on **Anthropic** (a fraction of a cent). With OpenAI, responses are then still valid JSON (JSON mode); with Anthropic, responses that are not valid JSON are retried. Either way, values are normalized as a standard extractor would (e.g. booleans and numbers become text, and options match regardless of case), and items that still don't match their type are discarded.
>
> Anthropic's limits are much tighter: at most **16** nullable fields without options (plus one per extracted type list) in a single request. Past that, Anthropic models get the fields as optional instead of nullable, which fits up to **24** of them but makes the model leave out values more often, and only then the schema is sent as instructions.

> ⚠️ A run interrupted (killed or crashed) while it submits batches can leave a batch that reached the provider but was never recorded locally. The provider still processes and bills it, but the engine can't collect its results, and the next run submits its jobs again. Avoid interrupting batch runs during submission, and if one is interrupted, check the provider's batch dashboard for batches the engine doesn't know about.

> ⏱️ A batch that hasn't ended within **25 hours** of its submission (providers end batches within 24) is asked to be cancelled at the provider, and stays tracked so that the requests it finished are still collected, while the rest are retried. If it still hasn't ended **26 hours** after its submission (for instance because the cancellation could not be requested), it is discarded and its jobs are retried, with a warning to check the provider for it.

> 🔀 Batches in flight are tied to the provider that received them. If the provider changes while batches are still pending, new batches go to the configured model, while the pending ones keep being checked, collected and cancelled through the provider that received them, as long as its API key is still set. Without it they can't be reached: since they most likely ended with their results already billed, they are kept past the deadlines above, and each run logs an error telling how many are waiting, as the extraction can't finish until they are collected. Add the missing key to collect them. Batches still unreachable **30 days** after their submission, when the provider no longer keeps their results, are discarded and their jobs are retried with the configured model.

**Reasoning effort (advanced):** every model runs at `low` effort unless `reasoning_effort` is set, which is best left unset. It takes one of the generalized levels `"none"`, `"low"`, `"medium"`, `"high"`, `"extreme"` or `"max"`, which each model translates to its closest native level (`"extreme"` is `xhigh` for all supported models, and on `claude-haiku-5-5` `"none"` runs without thinking). In [the benchmark of the supported models](/benchmark/llm_effort/README.md), `low` extracted field values much more accurately than `"none"`, which extracted more relationships but with many more errors. `"none"` can still suit a workload where finding more items matters more than their field values, and `"medium"` one with a harder schema (many interdependent or normalized fields, document-level extraction, long chunks), at a higher cost and latency.

**Execution modes:**

| Value           | Aliases                                                       | Behaviour                                                                                                                                                              |
| --------------- | ------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `"real-time"`   | `"realtime"`, `"real_time"`, `"sync"`, `"synchronous"`, `"immediate"` | Requests are issued concurrently and results consumed as they complete. Low latency, finishes in one sitting, standard pricing.                                        |
| `"batch"`       | `"batched"`, `"async"`, `"asynchronous"`, `"queue"`, `"queued"`, `"deferred"` | Requests are grouped and submitted to the provider's asynchronous batch interface. Substantially cheaper per token, in exchange for a delayed, best-effort turnaround. |

Both modes share the same work plan, validation and identity logic, so you can prototype interactively on a subset and then run the full corpus in batch mode by changing nothing but this key. In batch mode a run may be submitted in one session and collected in another.

`max_concurrency` only applies to real-time mode, and the binding constraint is the provider's rate limits rather than local resources. Reference values for OpenAI usage tiers with mini models (for Anthropic, check the rate limits of your usage tier):

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

When `overlap_tokens` is omitted it is derived from `target_tokens` as `min(max(20, 0.15 × target_tokens), target_tokens / 3, 200)` — so a target of 800 yields an overlap of 120. There is also an internal hard maximum, derived as `min(1.3 × target_tokens, 10000)` and not user-configurable, that keeps each chunk from drifting too far above the target. It bounds a chunk **before** the overlap is added: the overlap is a separate concern, so a chunk with its overlap may exceed the maximum by up to `overlap_tokens` (1,160 tokens at the defaults).

Segmentation proceeds recursively along a hierarchy of boundaries, from most to least semantically meaningful — structural headings, paragraphs, lines, sentences, and finally words — so chunk boundaries coincide with document structure wherever the structure permits. The target size is treated as *soft*: when adding the next piece would overshoot, the packer keeps whichever alternative lands closer to the target.

Before segmenting, line endings are normalized to `\n` (including CRLF, CR and the Unicode line and paragraph separators) and NUL characters are removed (a leading byte order mark is already dropped when the file is read). A chunk's `start_offset` and `end_offset` index this normalized text, counted in Unicode code points rather than bytes, so they map directly back to the source file only when it uses `\n` line endings and holds no NUL characters or byte order mark.

The chunking settings documents were ingested with are kept for the workspace: changing them only takes effect after resetting ingestion (see [Input Snapshots](/docs/workspace.md#-input-snapshots)).

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
