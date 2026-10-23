<!-- omit from toc -->
# 🗂️ Workspaces and Data

This document describes the two directories the engine needs to run: a **workspace** directory, which holds everything that defines and records a run, and a **data** directory, which holds the documents to read.

<!-- omit from toc -->
## 📚 Table of Contents
- [🧱 Two Directories, Two Jobs](#-two-directories-two-jobs)
- [📁 Workspace Layout](#-workspace-layout)
- [🔒 Input Snapshots](#-input-snapshots)
- [📚 Document Collections](#-document-collections)
  - [Registry Schema](#registry-schema)
  - [Sources](#sources)
  - [Example](#example)
- [📄 Data Directory](#-data-directory)
- [📤 Exports](#-exports)
- [♻️ Resetting a Workspace](#️-resetting-a-workspace)

## 🧱 Two Directories, Two Jobs

The engine is invoked with both directories, in this order:

```sh
poetry run wukong run <path/to/workspace_dir> <path/to/data_dir>
```

| Directory     | Holds                                                                          | Written to by the engine |
| ------------- | ------------------------------------------------------------------------------ | :----------------------: |
| **Workspace** | The knowledge model, the document collection registry, the staging database and the exports. |            ✅             |
| **Data**      | The plain text documents to read.                                              |            ❌             |

The separation is deliberate: the data directory is **read-only** as far as the engine is concerned, so a single corpus can be shared by several workspaces that extract different knowledge from it, and a workspace can be re-pointed at a different corpus without moving any files.

[📚 Back to Table of Contents](#-table-of-contents)

## 📁 Workspace Layout

A workspace is a directory with the following structure:

```sh
your-workspace/
├── knowledge_model.json        # required — what knowledge to extract
├── document_collections.json   # required — which documents to read
├── staging/
│   ├── extraction.db           # created by the engine — durable run state
│   └── snapshots/              # created by the engine — the inputs the stored results come from
└── exports/                    # created by the engine — the rendered output
```

| Path                        | Required | Description                                                                                                                       |
| --------------------------- | :------: | ----------------------------------------------------------------------------------------------------------------------------------- |
| `knowledge_model.json`      |    ✅     | The knowledge model. See the [Knowledge Model](/docs/knowledge-model.md) documentation.                                           |
| `document_collections.json` |    ✅     | The document collection registry. See [Document Collections](#-document-collections).                                             |
| `staging/extraction.db`     |  auto    | A SQLite database holding ingested documents, chunks, extracted objects and the state of every unit of work. Created on first run. |
| `staging/snapshots/`        |  auto    | Copies of the input files and chunking settings the stored results were produced from. See [Input Snapshots](#-input-snapshots). |
| `exports/`                  |  auto    | The rendered output. Created by the export step.                                                                                  |

The engine validates the workspace before doing anything: the directory must exist, and both JSON files must be present. A missing file aborts the run with an `InvalidWorkspaceError`.

The staging database is what makes runs **resumable**. Completed work is skipped on a re-run, so interrupting the engine loses at most the LLM calls in flight.

[📚 Back to Table of Contents](#-table-of-contents)

## 🔒 Input Snapshots

The inputs of a workspace are **fixed once the steps that use them have run**, so every stored result is consistent with the inputs it was produced from. When a step that first uses an input runs, the engine keeps a snapshot of it in `staging/snapshots/`, and later runs read the snapshot instead of the workspace files or the configuration:

| Input                            | Snapshotted when                | Kept until                  |
| -------------------------------- | ------------------------------- | --------------------------- |
| `document_collections.json`      | Documents are first ingested    | Ingestion is reset          |
| `[chunking]` settings            | Documents are first ingested    | Ingestion is reset          |
| `knowledge_model.json`           | Entities are first extracted    | Entity extraction is reset, directly or by resetting ingestion |

Editing a snapshotted input therefore has no effect on the workspace until the step that took the snapshot is reset. Each run compares the files with their snapshots and logs a warning naming any input that changed and the step to reset to apply it; formatting changes, such as whitespace or key order, don't count. Once documents are ingested, the data directory isn't read again for the registry's sources, so later steps still run if it moves or changes.

The intended workflow follows from this. While setting a workspace up, enable only the steps you are testing and re-run them with `--reset` after editing the inputs: re-running entity extraction with `--reset`, for instance, applies an edited knowledge model without ingesting again. Once the inputs are ready, run the whole pipeline once with `--reset`, or step by step. From then on, the inputs stay as they were for that workspace until you reset it.

[📚 Back to Table of Contents](#-table-of-contents)

## 📚 Document Collections

A **document collection** is a named group of documents that share a nature or provenance — one per source institution, per document genre, per legal body, and so on. Collections are the unit at which the knowledge model says *"this entity type applies to that part of the corpus"*, via each entity type's `document_collections` parameter.

The `document_collections.json` file is the registry that maps each collection name to the files that belong to it.

### Registry Schema

```json
{
    "collections": {
        "your-collection-name": {
            "sources": [
                { "root": "...", "mode": "..." }
            ]
        }
    }
}
```

| Parameter     | Required | Description                                                  |          Type           | Default |
| ------------- | :------: | -------------------------------------------------------------- | :---------------------: | ------- |
| `collections` |    🟡     | The collections, keyed by collection name.                   | `object[string, object]` | `{}`    |
| `sources`     |    🟡     | The sources that make up a collection. Duplicates are rejected. |     `Source array`      | `[]`    |

Unknown keys, such as a misspelled `collection`, are rejected rather than ignored.

Collection names may contain letters, digits, dots, hyphens and underscores, must start with a letter or digit, and must be at most 64 characters long (regex: `^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$`).

A collection may draw from several sources, and the same file may belong to more than one collection — documents are identified by their content, so a file reachable from two collections is **one document belonging to two collections**, not two documents.

### Sources

| Parameter | Required | Description                                                                    |   Type   |
| --------- | :------: | -------------------------------------------------------------------------------- | :------: |
| `root`    |    ✅     | A path **relative to the data directory**. Must not be empty.                  | `string` |
| `mode`    |    ✅     | How the root is expanded into a set of files. See below.                       | `string` |

| Mode          | Aliases                      | Expands to                                                             |
| ------------- | ---------------------------- | ------------------------------------------------------------------------ |
| `"file"`      | `"document"`, `"single"`     | The single `.txt` file at `root`.                                      |
| `"directory"` | `"dir"`, `"folder"`          | Every `.txt` file directly inside `root`, not descending into subdirectories. |
| `"recursive"` | `"nested"`, `"deep"`         | Every `.txt` file inside `root` and all of its subdirectories.         |

Mode values are case-insensitive. In every mode, only files with the `.txt` extension are picked up, and hidden or temporary files (those starting with `.`, `~` or `~$`) are ignored, as is everything inside a hidden or temporary directory such as `.git/`. Symlinks are followed only when they resolve inside the data directory; any other one is skipped with a warning. Files are picked up in name order, so the same data directory always yields the same documents in the same order.

Every `root` is resolved against the data directory given on the command line and must stay **inside** it. A source that resolves outside the data root is rejected, which is what keeps a workspace from reading arbitrary files on the machine.

### Example

```json
{
    "collections": {
        "missions": {
            "sources": [
                { "root": "missions", "mode": "directory" }
            ]
        },
        "crew": {
            "sources": [
                { "root": "crew", "mode": "directory" }
            ]
        },
        "logs": {
            "sources": [
                { "root": "incidents", "mode": "recursive" },
                { "root": "notices/safety_bulletin_14.txt", "mode": "file" }
            ]
        }
    }
}
```

[📚 Back to Table of Contents](#-table-of-contents)

## 📄 Data Directory

The data directory holds the documents, as **UTF-8 plain text files with the `.txt` extension** (a leading byte order mark is dropped). A file that can't be read, isn't valid UTF-8 or holds nothing but whitespace is skipped with a warning naming it, and the rest of the corpus is still ingested. There is no required layout: the engine finds files through the `root` and `mode` of each source in `document_collections.json`, so you are free to organize the directory however suits the corpus, as long as the registry points at it.

Filenames are unrestricted. A document's identity is derived from the content of its bytes, not from its name, so renaming a file does not create a new document and re-ingesting an unchanged file is a no-op.

A directory matching the registry example above would look like:

```sh
your-data-dir/
├── missions/
│   ├── artemis_7.txt
│   └── kepler_12.txt
├── crew/
│   ├── vance_okonkwo.txt
│   └── liang_serrano.txt
├── incidents/
│   └── 2189/
│       └── hull_breach_0412.txt
└── notices/
    └── safety_bulletin_14.txt
```

[📚 Back to Table of Contents](#-table-of-contents)

## 📤 Exports

The export step writes to `<workspace>/exports/`, in a subdirectory named after the chosen format:

```sh
your-workspace/exports/
├── mdb/
│   └── knowledge_graph.qm          # format = "mdb"
└── neo4j/                          # format = "neo4j"
    ├── entities/
    │   ├── Document.csv
    │   ├── Chunk.csv
    │   └── <EntityType>.csv
    └── relationships/
        ├── ChunkOf.csv
        ├── ExtractedFrom.csv
        └── <RelationshipType>.csv
```

Only the format selected in the configuration is written. Each export replaces that format's directory as a whole, and only once it has completed: files of types no longer exported don't linger, and a failed export leaves the previous one intact. Resetting the export step clears the whole `exports/` directory, including previous exports in other formats, so its contents always reflect the latest run. Alongside the entity and relationship types from the knowledge model, the output always contains the source `Document` and `Chunk` objects and the `ChunkOf` / `ExtractedFrom` provenance links, so the result is self-contained: it can be queried for domain facts, for the text supporting them, or for both at once, without consulting the original corpus.

String values are written exactly as they were extracted. The Neo4j CSV files quote them, and chunk contents span several lines, so import them with `neo4j-admin database import` and the `--multiline-fields=true` option.

> ⚙️ For selecting the export format, refer to the [Configuration](/docs/configuration.md) documentation.

[📚 Back to Table of Contents](#-table-of-contents)

## ♻️ Resetting a Workspace

Passing `--reset` to the `run` command clears the stored data at the start of each **active** pipeline step, so the step recomputes from scratch:

```sh
poetry run wukong run workspaces/example data/example --reset
```

Because later steps depend on earlier ones, resetting a step also resets the steps downstream of it — their results are no longer justified by their inputs. Resetting a step also releases the [input snapshots](#-input-snapshots) it took, so the step runs with the current inputs. Combine `--reset` with the `pipeline` section of the configuration file to re-run only part of the pipeline. A plan whose reset would wipe the results of a disabled step that a later enabled step needs (for example, resetting ingestion but only exporting) is refused before anything is reset.

Resetting an extraction step also asks the provider to cancel the batches it still has in flight, so they stop billing requests whose results would be discarded. The run doesn't wait for them to stop: the cancellations are only requested, and a failed request is logged as a warning so that the batch can be cancelled from the provider instead.

[📚 Back to Table of Contents](#-table-of-contents)
