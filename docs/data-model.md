<!-- omit from toc -->
# 🧬 Data Model

This document describes the expected data model format for a `data_model.json` file, which is required by the engine. The data model defines the structure of the knowledge graph that will be generated from the provided documents.

<!-- omit from toc -->
## 📚 Table of Contents
- [🧾 Data Model Schema](#-data-model-schema)
- [⚙️ Parameters](#️-parameters)
- [🧩 Entities](#-entities)
- [🔗 Relations](#-relations)
- [💡 Data Model Example](#-data-model-example)

## 🧾 Data Model Schema

For a given set of documents to process, the engine expects a data model file in valid **JSON** format. The file must follow a specific structure:

```json
{
    "parameters": {
        ...
    },
    "entities": {
        ...
    },
    "relations": {
        ...
    }
}
```

The data model itself is a **JSON** object with three main sections: `parameters`, `entities`, and `relations`. Each section has its own specific structure and requirements, which are detailed below.

[📚 Back to Table of Contents](#-table-of-contents)

## ⚙️ Parameters

The `parameters` section defines the **general context and settings** for the document data extraction. It includes the following optional fields:

| Field                | Required | Description                                                                                                                              |      Type      | Default                                                                  |
| -------------------- | :------: | ---------------------------------------------------------------------------------------------------------------------------------------- | :------------: | ------------------------------------------------------------------------ |
| `role`               |    🟡     | Contextual role to be taken by the LLM when processing the documents.                                                                    |    `string`    | `"An AI expert specialized in knowledge graph extraction"`               |
| `context`            |    🟡     | Context or domain of the input documents.                                                                                                |    `string`    | `"A context you must identify"`                                          |
| `input_language`     |    🟡     | Language of the input documents.                                                                                                         |    `string`    | `"english"`                                                              |
| `output_language`    |    🟡     | Language of the output knowledge graph.                                                                                                  |    `string`    | `"english"`                                                              |
| `included_entities`  |    🟡     | Array with all entity types to include in the output knowledge graph. These entity types must be defined in the `entities` section.      | `string array` | `[List of ALL user-defined entity types from the "entities" section]`    |
| `included_relations` |    🟡     | Array with all relation types to include in the output knowledge graph. These relation types must be defined in the `relations` section. | `string array` | `[List of ALL user-defined relation types from the "relations" section]` |

All of these parameters are technically **optional**, but it's highly recommended to provide them to ensure the **LLM** has a clear understanding of the context and requirements for processing the documents.

Example of the `parameters` section in a data model:

```json
"parameters": {
    "role": "An expert legal analyst specializing in Chilean civil law, operating exclusively within the Chilean continental law system and with extensive experience in identifying legal issues and structuring civil disputes.",
    "context": "Civil judgments from the Chilean Supreme Court.",
    "input_language": "spanish",
    "output_language": "spanish",
    "included_entities": [
        "Sentencia",
        "Persona"
    ],
    "included_relations": [
        "VotaEn"
    ]
}
```

[📚 Back to Table of Contents](#-table-of-contents)

## 🧩 Entities

Entities are the fundamental building blocks of a knowledge graph. In this context, they represent **objects or concepts** that can be extracted from the documents and modeled as nodes in the final graph (e.g. people, organizations, locations).

The `entities` section defines the **types of entities** that can be extracted from the documents. Each entity type is represented as a key inside the `entities` object, with its value being another object that describes the entity's properties, among other settings.

The name of each entity type must be **unique** and should be a valid string that **starts with a letter** and contains only **alphanumeric characters**. Additionally, the names `Document` and `Chunk` are reserved for **special entities** and cannot be used for user-defined entities.

For each entity type that the user defines, the following fields are available:

| Field               | Required | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |   Type   | Default |
| ------------------- | :------: | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :------: | ------- |
| `description`       |    ✅     | A brief description of this entity type.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                | `string` | `None`  |
| `primary_key`       |    ✅     | The name of the property that serves as the primary key for this entity type. This property must be defined in the `properties` object for this entity type, and it should represent the most natural method for identifying this entity in a plain text paragraph. For example, a good primary key for a **"Person"** entity would be a property that represents their name (e.g. a user-defined property called **"name" or "nombre"**). This field is used both for entity validation and deduplication. **Note:** For **core entities** (see `core_entity` field below), the `primary_key` field becomes **optional** and has no effect.                                                                                                                                                            | `string` | `None`  |
| `core_entity`       |    🟡     | A boolean indicating whether this entity type is a core entity. A core entity is defined as an entity that represents an abstraction of an entire document, rather than being present somewhere in said document. For example, if the input documents corresponded to lawsuits, then a **"Lawsuit"** entity would be modeled as a core entity, since each document represents a single instance of this entity type. In most cases, only a single one out of all the user-defined entities should be modeled as a core entity (though there could be exceptions and this is not a mandatory restriction). For core entities, duplicates are **not defined** (since they each represent valid unique documents), which means that the `primary_key` field and the deduplication settings have no effect. |  `bool`  | `false` |
| `detect_duplicates` |    🟡     | A boolean indicating whether to detect and merge duplicates for this entity type. If activated, the duplicated entities are detected by using the property indicated by the `primary_key` field, and considering the method defined in the `duplicates` field. Detected duplicates are then merged into a single entity, trying to conserve as much information as possible from the originally extracted entities.                                                                                                                                                                                                                                                                                                                                                                                     |  `bool`  | `true`  |
| `duplicates`        |    🟡     | An indicator on how to handle duplicate detection for this entity type. If set to `"all"`, entities that have a highly similar value for their primary key will be considered duplicates. If set to `"exact"`, only those entities that share the same exact value for their primary key will be detected as duplicates. For primary key values that are name-like and should not be very similar between different entities, the best setting is `"all"`. For primary key values that act like identifiers/codes and could potentially be very similar, the best setting is `"exact"`.                                                                                                                                                                                                                 | `string` | `all`   |
| `properties`        |    🟡     | An object defining the specific **properties** of this entity type. Read below for more information.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    | `object` | `{}`    |

The value of the `properties` field is an object that defines **properties**, which are attributes of the entity that contain relevant information. Each property is represented as a key inside the `properties` object, with its value being another object that describes the property's parameters and necessary information.

The name of each property must be **unique** inside this entity type, and should be a valid string that **starts with a letter** and contains only **alphanumeric characters and underscores**. Additionally, the name `extracted_from` is reserved for a **special property** and cannot be used for user-defined properties.

For each property that the user defines, the following fields are available:

| Field         | Required | Description                                                                                                                                                                                                                                                                                                     |      Type      | Default    |
| ------------- | :------: | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :------------: | ---------- |
| `description` |    ✅     | A brief description of the property.                                                                                                                                                                                                                                                                            |    `string`    | `None`     |
| `type`        |    🟡     | The data type of the property. Currently only `"string"` is supported.                                                                                                                                                                                                                                          |    `string`    | `"string"` |
| `example`     |    🟡     | An example value for the property, illustrating its expected format and content.                                                                                                                                                                                                                                |    `string`    | `""`       |
| `options`     |    🟡     | An array with all the possible values that this property can take. If this field is present with a non-empty list, it effectively restricts the potential values of this property to a specific subset. For example, you could use this field to force the property's value to be either **"Yes"** or **"No"**. | `string array` | `[]`       |
| `required`    |    🟡     | A boolean indicating whether this property is mandatory for this entity type. If set to `true`, the property must be present in every instance of the entity type.                                                                                                                                              |     `bool`     | `false`    |

Example of the `entities` section in a data model:

```json
"entities": {
    "Sentencia": {
        "core_entity": true,
        "description": "A civil judgment from the Chilean Supreme Court. The final determination of a civil lawsuit, declaring the rights and duties of the parties involved.",
        "primary_key": "rol",
        "properties": {
            "rol": {
                "type": "string",
                "description": "A unique numerical identifier used to represent the current judgment at the Supreme Court. It is never mentioned in the beginning. Explicitly mentioned at the end, after the paragraph that starts with 'Registrese...' and before the paragraph that starts with 'Pronunciado por...'. May be located at the end of the line that talks about 'Redacción a cargo de...'. Must be in the format: <N>-<M>, where both <N> and <M> are valid integers. It is sometimes ended with symbols ('.', '.-'), or preceded by ('No', 'Nro', 'N°'), but only consider the numbers.",
                "example": "13.500-2025, or 13-2025, or 1300-25",
                "required": true
            },
            "fecha": {
                "type": "string",
                "description": "The date of the current judgment at the Supreme Court. Explicitly mentioned either at the very beginning, or at the very end. It appears written in words, do not infer it from the 'rol'. Must be in the format: TYYYYMMDD, where YYYY is the year, MM is the month, and DD is the day. If MM is not available, consider it as 01. If DD is not available, consider it as 01. If the year is not available, the entire date value should be: NULL.",
                "example": "T20240115",
                "required": true
            },
            "problema": {
                "type": "string",
                "description": "The central problem that gives rise to the legal dispute present in the judgment. Concise and written as a legal concept.",
                "example": "Incumplimiento de Promesa de Compraventa",
                "required": true
            },
        }
    },
    "Persona": {
        "description": "A natural person who participates or is mentioned in a judgment.",
        "primary_key": "nombre",
        "duplicates": "all",
        "properties": {
            "nombre": {
                "type": "string",
                "description": "The person's name.",
                "example": "Juan Andrés Pérez González",
                "required": true
            }
        }
    }
}
```

[📚 Back to Table of Contents](#-table-of-contents)

## 🔗 Relations

Relations are the connections between entities in a knowledge graph. In this context, relations are represented as **links between two entities** that can be extracted from the documents and modeled as edges in the final graph (e.g. a person living in a city).

The `relations` section defines the **types of relations** that can be extracted from the documents. Each relation type is represented as a key inside the `relations` object, with its value being another object that describes the relation's properties, among other settings.

The name of each relation type must be **unique** and should be a valid string that **starts with a letter** and contains only **alphanumeric characters**. Additionally, the names `ChunkOf` and `ExtractedFrom` are reserved for **special relations** and cannot be used for user-defined relations.

Relations are allowed between any two entity types defined in the `entities` section, with the exception of **core entities**. For **core entities**, relations can be defined with **non-core entities** (either as origin or target), but **not between two core entities**. This is because **core entities** represent abstractions of entire documents, and thus it is not possible to extract information about relations between them by looking at the contents of the documents.

For each relation type that the user defines, the following fields are available:

| Field               | Required | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |      Type      | Default |
| ------------------- | :------: | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :------------: | ------- |
| `origin`            |    ✅     | An array with the names of the entity types that can be the origin of this relation. These entity types must be defined in the `entities` section.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        | `string array` | `None`  |
| `target`            |    ✅     | An array with the names of the entity types that can be the target of this relation. These entity types must be defined in the `entities` section.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        | `string array` | `None`  |
| `description`       |    ✅     | A brief description of this relation type.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |    `string`    | `None`  |
| `primary_key`       |    🟡     | The name of the property that serves as the primary key for this relation type. This property must be defined in the `properties` object for this relation type. This field is used when duplicate detection is active, in which case the property specified as primary key here is used for deduplication in a similar way as with the entities, but with the additional condition that the **origin** and **target** entities for a relation pair must be identical to consider it a duplicate. If this field is empty or not defined, then no deduplication will be performed for this relation type, regardless of the deduplication settings.                                                                                                                                                                                                                                                                                                                                                                        |    `string`    | `""`    |
| `detect_duplicates` |    🟡     | A boolean indicating whether to detect and merge duplicates for this relation type. If activated, the duplicated relations are detected by first finding relations with the same exact **origin** and **target** entities, and then comparing the value of the property indicated by the `primary_key` field, while considering the method defined in the `duplicates` field. Detected duplicates are then merged into a single relation, trying to conserve as much information as possible from the originally extracted relations.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |     `bool`     | `true`  |
| `duplicates`        |    🟡     | An indicator on how to handle duplicate detection for this relation type. If set to `"all"`, relations that have the same **origin** and **target** entities and also have a highly similar value for their primary key will be considered duplicates. If set to `"exact"`, only those relations with the same **origin** and **target** that additionally share the same exact value for their primary key will be detected as duplicates. The recommended value follows the same rules as with the entities.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |    `string`    | `"all"` |
| `force_unique`      |    🟡     | A boolean indicating whether this relation should be forced to be unique. If set to `true`, the engine will ensure that at most one instance of this relation exists between any given **origin** and **target** entities. This is useful for relations that should not have multiple instances between the same pair of entities (e.g. a **VotaEn** relation where a person can only vote once in an election). Setting this to `true` implicitly ignores deduplication settings for this relation type, since it considers any pair of relations with the same **origin** and **target** entities as duplicates.                                                                                                                                                                                                                                                                                                                                                                                                        |     `bool`     | `false` |
| `bypass_LLM`        |    🟡     | A boolean indicating whether this relation type should be extracted without using the LLM. This option is only available for relations where either the origin or target entity type is a **core entity**. If this relation type is defined between two non-core entities, this field will be ignored and the relations will always be extracted using the LLM. When using this option, the engine **skips the LLM processing** and assumes that, for every instance of the non-core entity found in a document, said instance has a relation with the respective core entity that represents that document. This field is useful for cases where an entity being found in a document implicitly means that there is a relation with the core entity that represents said document (e.g. for documents that represent **fragments of a book**, any **character entities** mentioned in a document would be implicitly connected to the associated **book fragment core entity** by a relation such as **"MentionedIn"**). |     `bool`     | `false` |
| `properties`        |    🟡     | An object defining the specific **properties** of this relation type. This object follows the same rules and structure as with the entities.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |    `object`    | `{}`    |

Example of the `relations` section in a data model:

```json
"relations": {
    "Contiene": {
        "origin": [
            "Sentencia"
        ],
        "target": [
            "Hecho"
        ],
        "description": "A judgment that contains a factual and established event.",
        "bypass_LLM": true,
        "force_unique": true
    },
    "VotaEn": {
        "origin": [
            "Persona"
        ],
        "target": [
            "Sentencia"
        ],
        "description": "A judicial officer that participates in the voting to decide the final resolution of a judgment. This is mentioned at the end of the judgment, where the voting is recorded.",
        "force_unique": true,
        "properties": {
            "decision": {
                "type": "string",
                "description": "Whether the judicial officer is in favor or against the final resolution of the judgment.",
                "options": [
                    "A Favor",
                    "En Contra"
                ],
                "required": true
            },
            "explicacion": {
                "type": "string",
                "description": "The reasoning behind the vote given by the judicial officer. Should be concise."
            }
        }
    }
}
```

[📚 Back to Table of Contents](#-table-of-contents)

## 💡 Data Model Example

A full example of a properly formatted data model is contained in the provided [Data Model Example File](../data/example/data_model.json), located in `data/example/data_model.json`.

[📚 Back to Table of Contents](#-table-of-contents)