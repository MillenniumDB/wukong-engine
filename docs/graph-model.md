<!-- omit from toc -->
# 🧬 Graph Model

This document describes the expected graph model format for a `graph_model.json` file, which is required by the engine. The graph model defines the structure of the knowledge graph that will be generated from the provided documents.

<!-- omit from toc -->
## 📚 Table of Contents
- [🧾 Graph Model Schema](#-graph-model-schema)
- [⚙️ Extraction Configuration](#️-extraction-configuration)
  - [LLM Settings](#llm-settings)
  - [Language Settings](#language-settings)
  - [Projection Settings](#projection-settings)
- [🧩 Entity Types](#-entity-types)
  - [General Definition](#general-definition)
  - [Fields](#fields)
  - [Example](#example)
- [🔗 Relationship Types](#-relationship-types)
  - [General Definition](#general-definition-1)
  - [Endpoints](#endpoints)
  - [Fields](#fields-1)
  - [Example](#example-1)
- [💡 Graph Model Example](#-graph-model-example)

## 🧾 Graph Model Schema

To construct a knowledge graph, the engine expects a graph model file in valid **JSON** format. The file must follow a specific structure:

```json
{
    "extraction": {
        ...
    },
    "entity_types": {
        ...
    },
    "relationship_types": {
        ...
    }
}
```

The graph model itself is a **JSON** object with three main sections: `extraction`, `entity_types`, and `relationship_types`. Each section has its own specific structure and requirements, which are detailed below.

[📚 Back to Table of Contents](#-table-of-contents)

## ⚙️ Extraction Configuration

The `extraction` section defines the **general context and settings** for the document data extraction. It is structured into three sub-sections: `llm`, `language`, and `projection`.

### LLM Settings

The `llm` sub-section specifies contextual information to guide the extraction process:

| Parameter          | Required | Description                                                                       |   Type   | Default                                                    |
| ------------------ | :------: | --------------------------------------------------------------------------------- | :------: | ---------------------------------------------------------- |
| `persona`          |    🟡     | The contextual role/persona to be taken by the LLM when processing the documents. | `string` | `"An AI expert specialized in knowledge graph extraction"` |
| `document_context` |    🟡     | The context or domain of the input documents.                                     | `string` | `None`                                                     |

### Language Settings

The `language` sub-section specifies relevant languages:

| Parameter | Required | Description                               |   Type   | Default |
| --------- | :------: | ----------------------------------------- | :------: | ------- |
| `input`   |    🟡     | The language code of the input documents. | `string` | `"en"`  |
| `output`  |    🟡     | The language code of the output graph.    | `string` | `"en"`  |

### Projection Settings

The `projection` sub-section controls which of the defined entity and relationship types are included in the output knowledge graph:

| Parameter               | Required | Description                                                                                 |      Type      | Default                                                                        |
| ----------------------- | :------: | ------------------------------------------------------------------------------------------- | :------------: | ------------------------------------------------------------------------------ |
| `enabled_entities`      |    🟡     | An array with the names of all entity types to include in the output knowledge graph.       | `string array` | `[List of ALL entity types defined in the "entity_types" section]`             |
| `enabled_relationships` |    🟡     | An array with the names of all relationship types to include in the output knowledge graph. | `string array` | `[List of ALL relationship types defined in the "relationship_types" section]` |

All parameters in these sections are technically **optional**, but it's highly recommended to provide them to ensure the **LLM** has a clear understanding of the context and requirements for processing the documents.

Example of the `extraction` section in a graph model:

```json
"extraction": {
    "llm": {
        "persona": "An expert legal analyst specializing in Chilean law, with extensive experience in identifying connections between legal articles.",
        "document_context": "Legal regulations and rules relating to the Ley General de Urbanismo y Construcciones (LGUC) and the Ministerio de Vivienda y Urbanismo (MINVU) of Chile."
    },
    "language": {
        "input": "es",
        "output": "es"
    },
    "projection": {
        "enabled_entities": [
            "LGUC",
            "OGUC",
            "DDU"
        ],
        "enabled_relationships": [
            "References"
        ]
    }
}
```

[📚 Back to Table of Contents](#-table-of-contents)

## 🧩 Entity Types

Entities are the fundamental building blocks of a knowledge graph. They represent **objects or concepts** that can be extracted from the documents and modeled as nodes in the final graph (e.g. people, organizations, legal articles).

### General Definition

The `entity_types` section defines the **types of entities** that can be extracted from the documents. Each entity type is represented as a key inside the `entity_types` object (using the **entity type's name**), with its value being another object that describes the entity type's parameters and extraction-related settings.

The name of each entity type must be a valid string that starts with an **uppercase letter**, and contains only **alphanumeric characters**. The names `Document` and `Chunk` are reserved for **special entity types** and cannot be used.

Each entity type can be extracted at different **context levels** (e.g. from text chunks or at the document level), and the graph model allows users to specify different extraction settings for each context level if desired. The currently supported context levels are `"chunk"` and `"document"`.

For each entity type that the user defines, the following parameters are available:

| Parameter              | Required | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |                 Type                 | Default  |
| ---------------------- | :------: | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :----------------------------------: | -------- |
| `description`          |    ✅     | A brief description of this entity type.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |               `string`               | `None`   |
| `instructions`         |    🟡     | Additional technical instructions for extracting this entity type. Can be specified using an object that maps each context level (`"chunk"`, `"document"`) to a string representing their respective instructions, or with a single string that is applied to *all* context levels.                                                                                                                                                                                                                                             | `object[string, string]` or `string` | `None`   |
| `primary_key`          |    ✅     | The name of the field that serves as the primary key for this entity type. This field must be defined in the `fields` object and should uniquely identify entities of this type. Used for both validation and deduplication.                                                                                                                                                                                                                                                                                                    |               `string`               | `None`   |
| `deduplication_mode`   |    🟡     | Controls how duplicates are detected for this entity type. Options: `"exact"` (only detect exact matches on primary key), `"approximate"` (near duplicates on primary key using fuzzy matching and hashing), or `"none"` (no deduplication). The recommendation is to use `"approximate"` for name-like values and `"exact"` for identifier/code-like values that are more strict.                                                                                                                                              |               `string`               | `"none"` |
| `fields`               |    🟡     | An object defining the specific **fields** of this entity type. See the **Fields** section for more information on these definitions.                                                                                                                                                                                                                                                                                                                                                                                           |       `object[string, Field]`        | `{}`     |
| `document_collections` |    🟡     | Specifies which document collections to use when extracting the entities, considering the different context levels. Must be an object where the keys are context levels (`"chunk"`, `"document"`), and the values are arrays of **document collections**. Document collections must correspond to **subdirectory names** inside the `<path/to/data_dir>/docs/text/` directory, where these subdirectories contain the input documents in `.txt` format. Any non-specified context levels are ignored in the extraction process. |    `object[string, string array]`    | `{}`     |

### Fields

The `fields` object inside each entity type defines **fields** that contain relevant information about that entity type. Each field is represented as a key (using the **field's name**) inside the `fields` object, with its value being another object describing the **field's parameters**.

The name of each field must start with a **lowercase letter**, and contain only **lowercase alphanumeric characters and underscores**. The name `extracted_from` is reserved for a special field and cannot be used.

Each field can have different extraction settings for different context levels (e.g. extract from text chunks but load from document-level external files), and the graph model allows users to specify these settings accordingly. The currently supported context levels are `"chunk"` and `"document"`. The currently supported field retrieval modes for entity types are `"extract"` (extract from text), `"load"` (load from external files), `"default"` (use the default value), and `"skip"` (don't retrieve the field, assume `NULL`).

For each field that the user defines, the following parameters are available:

| Parameter        | Required | Description                                                                                                                                                                                                                                                                                                                                                                                      |                 Type                 | Default     |
| ---------------- | :------: | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | :----------------------------------: | ----------- |
| `data_type`      |    ✅     | The data type of the field. Currently only `"string"` is supported.                                                                                                                                                                                                                                                                                                                              |               `string`               | `None`      |
| `description`    |    ✅     | A brief description of what this field represents.                                                                                                                                                                                                                                                                                                                                               |               `string`               | `None`      |
| `instructions`   |    🟡     | Detailed technical instructions for extracting this field. Can be specified using an object that maps each context level (`"chunk"`, `"document"`) to a string representing their respective instructions, or with a single string that is applied to *all* context levels.                                                                                                                      | `object[string, string]` or `string` | `None`      |
| `options`        |    🟡     | An array of all possible values this field can take. Restricts the field to a specific set of values. If not specified, the field may take any value without restrictions (equivalent to an empty array).                                                                                                                                                                                        |            `string array`            | `[]`        |
| `examples`       |    🟡     | Example value(s) for the field, illustrating its expected format and content. Can be a single string or an array of strings for multiple examples.                                                                                                                                                                                                                                               |      `string` or `string array`      | `[]`        |
| `regex`          |    🟡     | A regex pattern that this field's value must match to be considered valid (e.g. `"^[a-z][a-z0-9_]*$"`). Can be specified using an object that maps each context level (`"chunk"`, `"document"`) to a string representing their respective regex patterns, or with a single regex pattern string that is applied to *all* context levels.                                                         | `object[string, string]` or `string` | `None`      |
| `default_value`  |    🟡     | The default value for this field if it cannot be obtained, or if the `"default"` retrieval mode is chosen. Can be specified using an object that maps each context level (`"chunk"`, `"document"`) to a string representing their respective default values, or with a single default value string that is applied to *all* context levels. If not specified, the default value will be `NULL`.  | `object[string, string]` or `string` | `None`      |
| `retrieval_mode` |    🟡     | Controls how this field should be retrieved. Can be specified using an object that maps each context level (`"chunk"`, `"document"`) to a string representing their respective retrieval modes (`"extract"`, `"load"`, `"default"`, `"skip"`), or with a single retrieval mode string that is applied to *all* context levels. If not specified, the default retrieval mode will be `"extract"`. | `object[string, string]` or `string` | `"extract"` |
| `required`       |    🟡     | A boolean indicating whether this field is mandatory for this entity type. If set to `true`, the field must be present with a valid value in every instance of the entity type. This parameter is ignored by fields chosen as primary keys, since those must always be required.                                                                                                                 |                `bool`                | `false`     |

### Example

Example of an entity type object contained in the `entity_types` section of a graph model:

```json
"LGUC": {
    "description": "A specific article from the LGUC (Ley General de Urbanismo y Construcciones).",
    "instructions": "Must explicitly mention or refer to the LGUC, ignore articles from other legal bodies such as OGUC/DDU.",
    "primary_key": "node_name",
    "deduplication_mode": "exact",
    "fields": {
        "node_name": {
            "data_type": "string",
            "description": "The unique identifier of the LGUC article.",
            "instructions": {
                "chunk": "Must be in the format: lguc_articulo_<A>_<NUM>_<LETTER>, where <A> is a valid integer without leading '0's..."
            },
            "regex": "^lguc[ _.-]articulo[ _.-]\\d+(?:[ _.-][A-Za-z]+(?:[ _.-][A-Za-z])?)?$",
            "examples": [
                "lguc_articulo_1",
                "lguc_articulo_4_bis"
            ],
            "retrieval_mode": {
                "chunk": "extract",
                "document": "load"
            }
        },
        "source_type": {
            "data_type": "string",
            "description": "The type of the parent document.",
            "default_value": "lguc",
            "retrieval_mode": "default"
        },
        "title": {
            "data_type": "string",
            "description": "The title of the LGUC article.",
            "instructions": "Mentioned in the beginning, right in between 'TITULO' and 'CAPITULO'.",
            "retrieval_mode": {
                "chunk": "skip",
                "document": "extract"
            }
        }
    },
    "document_collections": {
        "chunk": ["LGUC", "OGUC", "DDU"],
        "document": ["LGUC"]
    }
}
```

[📚 Back to Table of Contents](#-table-of-contents)

## 🔗 Relationship Types

Relationships are the connections between entities in a knowledge graph. They represent **links between two entities** that can be extracted from the documents and modeled as edges in the final graph (e.g. a legal article referencing another article).

### General Definition

The `relationship_types` section defines the **types of relationships** that can be extracted from the documents. Each relationship type is represented as a key inside the `relationship_types` object (using the **relationship type's name**), with its value being another object that describes the relationship type's parameters and extraction-related settings.

The name of each relationship type must be a valid string that starts with an **uppercase letter**, and contains only **alphanumeric characters**. The names `ChunkOf` and `ExtractedFrom` are reserved for **special relationship types** and cannot be used.

For each relationship type that the user defines, the following parameters are available:

| Parameter            | Required | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                       |                         Type                         | Default  |
| -------------------- | :------: | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :--------------------------------------------------: | -------- |
| `description`        |    ✅     | A brief description of this relationship type.                                                                                                                                                                                                                                                                                                                                                                                                                    |                       `string`                       | `None`   |
| `instructions`       |    🟡     | Additional technical instructions for extracting this relationship type.                                                                                                                                                                                                                                                                                                                                                                                          |                       `string`                       | `None`   |
| `endpoints`          |    🟡     | An object defining all valid source-target entity type combinations and their context level pairings for this relationship type. Each key is a **source entity type name**, with its value being an object that maps **target entity type names** to **arrays of context level pairing rules**. See the **Endpoints** section for more information on these definitions.                                                                                          | `object[string, object[string, EndpointRule array]]` | `{}`     |
| `primary_key`        |    🟡     | The name of the field that serves as the primary key for this relationship type. This field must be defined in the `fields` object and should uniquely identify relationships of this type between the same source/target pairs. Used for both validation and deduplication, if defined. If no primary key is specified, the `"exact"` and `"approximate"` deduplication modes cannot be used.                                                                    |                       `string`                       | `None`   |
| `deduplication_mode` |    🟡     | Controls how duplicates are detected for this relationship type, when looking at relationships with identical source/target entity pairs. Options: `"exact"` (only detect exact matches on primary key), `"approximate"` (near duplicates on primary key using fuzzy matching and hashing), `"endpoints"` (any two relationships with identical source and target entities are considered duplicates, regardless of primary key), or `"none"` (no deduplication). |                       `string`                       | `"none"` |
| `fields`             |    🟡     | An object defining the specific **fields** of this relationship type. See the **Field** section below for more information on these definitions.                                                                                                                                                                                                                                                                                                                  |               `object[string, Field]`                | `{}`     |

### Endpoints

The `endpoints` object defines valid source-target entity type combinations and their context level pairing rules. Each endpoint rule is represented as an object with the `source_context_levels` and `target_context_levels` parameters, specifying the context levels at which the source and target entities can be connected. Each of these parameters can be specified as a single context level string or as an array of context level strings, where all combinations between them will be generated.

The currently supported context levels for entity types are `"chunk"` (entity extracted from a text chunk) and `"document"` (entity extracted at the document level). The currently valid context level pairings for relationship endpoints are:

| Source Context Level | Target Context Level |
| :------------------: | :------------------: |
|       `chunk`        |       `chunk`        |
|       `chunk`        |      `document`      |
|      `document`      |       `chunk`        |

An example of the endpoints definition for a relationship type connecting the `LGUC` and `OGUC` entity types could look like this:

```json
"endpoints": {
    "LGUC": {
        "OGUC": [
            {
                "source_context_levels": "chunk",
                "target_context_levels": ["document", "chunk"]
            },
            {
                "source_context_levels": "document",
                "target_context_levels": "chunk"
            }
        ]
    }
}
```

In the example, the relationship type can connect `LGUC` entities extracted from text chunks to `OGUC` entities extracted at either the chunk or document level, as well as `LGUC` entities extracted at the document level to `OGUC` entities extracted from text chunks. It avoids the invalid pairing of `document` to `document`, which would raise an error since its not supported by the engine.

### Fields

The `fields` object inside each relationship type defines **fields** that contain relevant information about that relationship type. Each field is represented as a key (using the **field's name**) inside the `fields` object, with its value being another object describing the **field's parameters**.

The name of each field must start with a **lowercase letter**, and contain only **lowercase alphanumeric characters and underscores**. The name `extracted_from` is reserved for a special field and cannot be used.

Each field can specify a mode for retrieving the information. The currently supported field retrieval modes for relationship types are `"extract"` (extract from text), and `"default"` (use the default value).

For each field that the user defines, the following parameters are available:

| Parameter        | Required | Description                                                                                                                                                                                                                                                                                  |            Type            | Default     |
| ---------------- | :------: | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :------------------------: | ----------- |
| `data_type`      |    ✅     | The data type of the field. Currently only `"string"` is supported.                                                                                                                                                                                                                          |          `string`          | `None`      |
| `description`    |    ✅     | A brief description of what this field represents.                                                                                                                                                                                                                                           |          `string`          | `None`      |
| `instructions`   |    🟡     | Detailed technical instructions for extracting this field.                                                                                                                                                                                                                                   |          `string`          | `None`      |
| `options`        |    🟡     | An array of all possible values this field can take. Restricts the field to a specific set of values. If not specified, the field may take any value without restrictions (equivalent to an empty array).                                                                                    |       `string array`       | `[]`        |
| `examples`       |    🟡     | Example value(s) for the field, illustrating its expected format and content. Can be a single string or an array of strings for multiple examples.                                                                                                                                           | `string` or `string array` | `[]`        |
| `regex`          |    🟡     | A regex pattern that this field's value must match to be considered valid (e.g. `"^[a-z][a-z0-9_]*$"`).                                                                                                                                                                                      |          `string`          | `None`      |
| `default_value`  |    🟡     | The default value for this field if it cannot be obtained, or if the `"default"` retrieval mode is chosen. If not specified, the default value will be `NULL`.                                                                                                                               |          `string`          | `None`      |
| `retrieval_mode` |    🟡     | Controls how this field should be retrieved. Must be specified using a string representing one of the supported relationship retrieval modes (`"extract"`, `"default"`). If not specified, the default retrieval mode will be `"extract"`.                                                   |          `string`          | `"extract"` |
| `required`       |    🟡     | A boolean indicating whether this field is mandatory for this relationship type. If set to `true`, the field must be present with a valid value in every instance of the relationship type. This parameter is ignored by fields chosen as primary keys, since those must always be required. |           `bool`           | `false`     |

### Example

Example of a relationship type object contained in the `relationship_types` section of a graph model:

```json
"References": {
    "description": "A source legal provision explicitly referencing a target legal provision.",
    "instructions": "The source and target legal provisions must be different.",
    "endpoints": {
        "LGUC": {
            "LGUC": [
                {
                    "source_context_levels": "document",
                    "target_context_levels": "chunk"
                }
            ],
        },
        "OGUC": {
            "LGUC": [
                {
                    "source_context_levels": ["document", "chunk"],
                    "target_context_levels": "chunk"
                }
            ],
            "OGUC": [
                {
                    "source_context_levels": "document",
                    "target_context_levels": "chunk"
                }
            ]
        }
    },
    "primary_key": "ref_type",
    "deduplication_mode": "exact",
    "fields": {
        "ref_type": {
            "data_type": "string",
            "description": "The type of reference that the source imposes over the target.",
            "options": [
                "refiere",
                "interpreta",
                "condiciona",
                "complementa",
                "fundamenta",
                "modifica",
                "deroga",
                "instruye"
            ]
        },
        "description": {
            "data_type": "string",
            "description": "An explanation of how the source references the target.",
            "instructions": "Should be concise.",
            "examples": "Se refiere al punto 7.1 de la Circular DDU 279..."
        }
    }
}
```

[📚 Back to Table of Contents](#-table-of-contents)

## 💡 Graph Model Example

A full example of a properly formatted graph model is contained in the provided [Graph Model Example File](/data/example/graph_model.json). This example includes multiple entity and relationship types with various configurations, demonstrating the flexibility and structure of the graph model format.

[📚 Back to Table of Contents](#-table-of-contents)