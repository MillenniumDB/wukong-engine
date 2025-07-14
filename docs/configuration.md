<!-- omit from toc -->
# ⚙️ Configuration

This document provides an overview of the configuration options available for the project.

<!-- omit from toc -->
## 📚 Table of Contents
- [🌍 Environment Variables](#-environment-variables)
- [🔧 Engine Configuration](#-engine-configuration)
- [➡️ Pipeline Steps](#️-pipeline-steps)
- [🎛️ Engine Parameters](#️-engine-parameters)

## 🌍 Environment Variables

The project uses **environment variables** to store secrets and configuration values that are required for the engine to function properly. The following variables are available:

| Variable         | Required | Description                         | Default / Example    |
| ---------------- | :------: | ----------------------------------- | -------------------- |
| `OPENAI_API_KEY` |    ✅     | OpenAI API key for LLM interaction. | `sk-xxxxxxxxxxxxxxx` |

These variables are defined in the `.env.example` file located in the root directory of the project, which serves as a template with placeholder values.

For **local development/usage**, create a `.env` file in the root directory of the project and copy the contents from `.env.example` into it, replacing the placeholder values with the real ones for all the environment variables.

For **production/deployment**, set these variables directly in your server/cloud environment.

[📚 Back to Table of Contents](#-table-of-contents)

## 🔧 Engine Configuration

The engine uses a [TOML](https://toml.io/en/) configuration file to define its settings. which is located at `config/config.toml`. This file has the following structure:

```toml
[pipeline]

#...Pipeline Steps...

[parameters]

#...Engine Parameters...
```

The `pipeline` section defines the steps of the engine pipeline to be executed, while the `parameters` section contains various parameters that control the behavior of the engine.

[📚 Back to Table of Contents](#-table-of-contents)

## ➡️ Pipeline Steps

The `pipeline` section defines the steps that the engine will execute during its processing. Each step can be enabled or disabled by setting its value to `true` or `false`. The available steps are:

| Step                  | Description                                                                                       |  Type  | Default |
| --------------------- | ------------------------------------------------------------------------------------------------- | :----: | :-----: |
| `document_processing` | Processing of the user-provided documents, including text extraction and chunking.                | `bool` | `true`  |
| `entity_extraction`   | Extraction and processing of entities from the documents, converting them into **JSON** objects.  | `bool` | `true`  |
| `relation_extraction` | Extraction and processing of relations from the documents, converting them into **JSON** objects. | `bool` | `true`  |
| `export_graph`        | Exporting the extracted entities and relations into various knowledge graph formats.              | `bool` | `true`  |

[📚 Back to Table of Contents](#-table-of-contents)

## 🎛️ Engine Parameters

The `parameters` section contains various parameters that control the behavior of the engine. The available parameters are:

| Parameter            | Description                                                                                                                                                                                                                                                    |      Type      | Default                    |
| -------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :------------: | -------------------------- |
| `export_formats`     | List of available knowledge graph formats for exporting the results. The currently supported formats are: `"mdb"` **(MillenniumDB Quad Model File)**, `"neo4j"` **(Neo4j CSV Files)**, `"json"` **(JSON Files)**.                                              | `string array` | `["mdb", "neo4j", "json"]` |
| `max_tokens`         | Maximum number of **tokens** contained by each document chunk. This is used to control the size of the text processed by each **LLM API call**. Adjust this value based on the LLM's context window, API request/response size limits and your specific needs. |   `integer`    | `2000`                     |
| `max_worker_threads` | Maximum number of **worker threads** to use for **LLM API calls**. This controls the concurrency of API requests to the LLM. Adjust this value based on your system's capabilities and the LLM API rate limits.                                                |   `integer`    | `10`                       |

[📚 Back to Table of Contents](#-table-of-contents)