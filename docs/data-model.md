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

| Field                | Required | Description                                                                                                                                                                                                                                                                   |      Type      | Default                                                                  |
| -------------------- | :------: | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :------------: | ------------------------------------------------------------------------ |
| `role`               |    🟡     | The contextual role to be taken by the LLM when processing the documents.                                                                                                                                                                                                     |    `string`    | `"An AI expert specialized in knowledge graph extraction"`               |
| `context`            |    🟡     | The context or domain of the input documents.                                                                                                                                                                                                                                 |    `string`    | `"A context you must identify"`                                          |
| `input_language`     |    🟡     | The language of the input documents.                                                                                                                                                                                                                                          |    `string`    | `"english"`                                                              |
| `output_language`    |    🟡     | The language of the output knowledge graph.                                                                                                                                                                                                                                   |    `string`    | `"english"`                                                              |
| `included_documents` |    🟡     | An array with all document sets to consider while extracting the knowledge graph information. These document sets must correspond to names of sub-directories present inside the `<path/to/data_dir>/docs/text/` directory, where each set contains the plain text documents. | `string array` | `[]`                                                                     |
| `included_entities`  |    🟡     | An array with all entity types to include in the output knowledge graph. These entity types must be defined in the `entities` section.                                                                                                                                        | `string array` | `[List of ALL user-defined entity types from the "entities" section]`    |
| `included_relations` |    🟡     | An array with all relation types to include in the output knowledge graph. These relation types must be defined in the `relations` section.                                                                                                                                   | `string array` | `[List of ALL user-defined relation types from the "relations" section]` |

All of these parameters are technically **optional**, but it's highly recommended to provide them to ensure the **LLM** has a clear understanding of the context and requirements for processing the documents.

Example of the `parameters` section in a data model:

```json
"parameters": {
    "role": "An expert legal analyst specializing in Chilean civil law, operating exclusively within the Chilean continental law system and with extensive experience in identifying legal issues and structuring civil disputes.",
    "context": "Civil judgments from the Chilean Supreme Court.",
    "input_language": "spanish",
    "output_language": "spanish",
    "included_documents": [
        "sentencias-2024",
        "sentencias-2025"
    ],
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

| Field               | Required | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |      Type      | Default                                                                       |
| ------------------- | :------: | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :------------: | ----------------------------------------------------------------------------- |
| `description`       |    ✅     | A brief description of this entity type.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                        |    `string`    | `None`                                                                        |
| `primary_key`       |    ✅     | The name of the property that serves as the primary key for this entity type. This property must be defined in the `properties` object for this entity type, and it should represent the best method for uniquely identifying entities of this type. This field is used both for entity validation and deduplication.                                                                                                                                                                                                                                                                           |    `string`    | `None`                                                                        |
| `core_entity`       |    🟡     | A boolean indicating whether this entity type models a core entity. A core entity is defined as an entity that represents an abstraction of an entire document, rather than being locally present somewhere in said document. For example, if the input documents correspond to lawsuits, then a **"Lawsuit"** entity type could model a core entity, since each document represents a single instance of this entity type.                                                                                                                                                                     |     `bool`     | `false`                                                                       |
| `hybrid_entity`     |    🟡     | A boolean indicating whether this entity type models a hybrid entity. A hybrid entity is defined as an entity that acts as both a core entity and a locally defined one, meaning that it should be extracted in both ways. For example, if the input documents correspond to lawsuits, where each lawsuit references other lawsuits in its corresponding document, then a **"Lawsuit"** entity type could model a hybrid entity, since lawsuits are not only represented by each document, but also referenced locally in the text paragraphs.                                                  |     `bool`     | `false`                                                                       |
| `detect_duplicates` |    🟡     | A boolean indicating whether to detect and merge duplicates for this entity type. If activated, the duplicated entities are detected by using the property indicated by the `primary_key` field, and considering the method defined in the `duplicates` field. Detected duplicates are then merged into a single entity, trying to conserve as much information as possible from the originally extracted entities.                                                                                                                                                                             |     `bool`     | `true`                                                                        |
| `duplicates`        |    🟡     | An indicator on how to handle duplicate detection for this entity type. If set to `"similar"`, entities that have a highly similar value for their primary key will be considered duplicates. If set to `"exact"`, only those entities that share the same exact value for their primary key will be detected as duplicates. For primary key values that are name-like and should not be very similar between different entities, the best setting is `"similar"`. For primary key values that act like identifiers/codes and could potentially be very similar, the best setting is `"exact"`. |    `string`    | `"exact"`                                                                     |
| `documents`         |    🟡     | An array with all document sets to consider while extracting this entity type. These document sets must correspond to names of sub-directories present inside the `<path/to/data_dir>/docs/text/` directory. If this entity type models a hybrid entity, these document sets will only be considered when extracting the core entity instances.                                                                                                                                                                                                                                                 | `string array` | `[The value of the "included_documents" field from the "parameters" section]` |
| `documents_hybrid`  |    🟡     | An array with all document sets to consider while extracting this entity type as a locally defined entity. These document sets must correspond to names of sub-directories present inside the `<path/to/data_dir>/docs/text/` directory. This field is only valid for entity types that model hybrid entities.                                                                                                                                                                                                                                                                                  | `string array` | `[The value of the "included_documents" field from the "parameters" section]` |
| `properties`        |    🟡     | An object defining the specific **properties** of this entity type. Read below for more information.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                            |    `object`    | `{}`                                                                          |

The value of the `properties` field is an object that defines **properties**, which are attributes of the entity type that contain relevant information. Each property is represented as a key inside the `properties` object, with its value being another object that describes the property's parameters and necessary information.

The name of each property must be **unique** inside this entity type, and should be a valid string that **starts with a letter** and contains only **alphanumeric characters and underscores**. Additionally, the name `extracted_from` is reserved for a **special property** and cannot be used for user-defined properties.

For each property that the user defines, the following fields are available:

| Field                | Required | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |      Type      | Default                                 |
| -------------------- | :------: | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | :------------: | --------------------------------------- |
| `description`        |    ✅     | A brief description of the property.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |    `string`    | `None`                                  |
| `description_hybrid` |    🟡     | A brief description of the property, to be used when extracting this entity type as a locally defined entity. This field is only valid for properties where the parent entity type models hybrid entities.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                 |    `string`    | `Same value as the "description" field` |
| `type`               |    🟡     | The data type of the property. Currently only `"string"` is supported.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |    `string`    | `"string"`                              |
| `example`            |    🟡     | An example value for the property, illustrating its expected format and content.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |    `string`    | `None`                                  |
| `metadata`           |    🟡     | A boolean indicating whether this property should be extracted from available metadata files instead of the plain text documents for this entity type. This field is only valid for properties where the parent entity type models core/hybrid entities. For the metadata extraction to work properly, the same document set sub-directories present at `<path/to/data_dir>/docs/text/` must be also present inside a `<path/to/data_dir>/docs/metadata/` directory, containing each of the metadata files in **JSON** object format. These metadata files must have the exact same filenames as their plain text document counterparts, but with the `.json` extension instead of `.txt`. |     `bool`     | `false`                                 |
| `hybrid`             |    🟡     | A boolean indicating whether this property should be considered when extracting this entity type as a locally defined entity. This field is only valid for properties where the parent entity type models hybrid entities. If set to `true`, the property value will be normally extracted, otherwise it will be set to `NULL`.                                                                                                                                                                                                                                                                                                                                                            |     `bool`     | `false`                                 |
| `placeholder`        |    🟡     | A predefined value that acts as a placeholder for this property. If not defined, the property will be extracted from the documents normally.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |    `string`    | `None`                                  |
| `options`            |    🟡     | An array with all the possible values that this property can take. If this field is present with a non-empty list, it effectively restricts the potential values of this property to a specific subset. For example, you could use this field to force the property's value to be either **"Yes"** or **"No"**.                                                                                                                                                                                                                                                                                                                                                                            | `string array` | `[]`                                    |
| `default`            |    🟡     | The default value for this property, in case it cannot be properly extracted from the documents/metadata. If not defined, the property value will be set to `NULL` when a valid value cannot be obtained through the extraction process.                                                                                                                                                                                                                                                                                                                                                                                                                                                   |    `string`    | `None`                                  |
| `regex`              |    🟡     | A regex pattern that this property's value must match to be considered valid. If not defined, the property will be extracted from the documents normally.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  |    `string`    | `None`                                  |
| `required`           |    🟡     | A boolean indicating whether this property is mandatory for this entity type. If set to `true`, the property must be present in every instance of the entity type.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                         |     `bool`     | `false`                                 |

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

For each relation type that the user defines, the following fields are available:

| Field                  | Required | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                              |      Type      | Default   |
| ---------------------- | :------: | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :------------: | --------- |
| `origin`               |    ✅     | An array with the names of the entity types that can be the origin of this relation type. These entity types must be defined in the `entities` section.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  | `string array` | `None`    |
| `target`               |    ✅     | An array with the names of the entity types that can be the target of this relation type. These entity types must be defined in the `entities` section.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  | `string array` | `None`    |
| `origin_target (TODO)` |    ✅     | An object that models all origin value combinations. array with the names of the entity types that can be the target of this relation type. These entity types must be defined in the `entities` section.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                |    `object`    | `None`    |
| `description`          |    ✅     | A brief description of this relation type.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                               |    `string`    | `None`    |
| `primary_key`          |    🟡     | The name of the property that serves as the primary key for this relation type. This property must be defined in the `properties` object for this relation type. This field is used when duplicate detection is active, in which case the property specified as primary key here is used for deduplication in a similar way as with the entities, but with the additional condition that the **origin** and **target** entities for a relation pair must be identical to consider it a duplicate. If this field is empty or not defined, then no deduplication will be performed for this relation type, regardless of the deduplication settings.                                                                                                                                                                                                                                                                                                                                                                                       |    `string`    | `None`    |
| `detect_duplicates`    |    🟡     | A boolean indicating whether to detect and merge duplicates for this relation type. If activated, the duplicated relations are detected by first finding relations with the same exact **origin** and **target** entities, and then comparing the value of the property indicated by the `primary_key` field, while considering the method defined in the `duplicates` field. Detected duplicates are then merged into a single relation, trying to conserve as much information as possible from the originally extracted relations.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    |     `bool`     | `true`    |
| `duplicates`           |    🟡     | An indicator on how to handle duplicate detection for this relation type. If set to `"similar"`, relations that have the same **origin** and **target** entities and also have a highly similar value for their primary key will be considered duplicates. If set to `"exact"`, only those relations with the same **origin** and **target** that additionally share the same exact value for their primary key will be detected as duplicates. The recommended value follows the same rules as with the entities.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                       |    `string`    | `"exact"` |
| `force_unique`         |    🟡     | A boolean indicating whether this relation type should be forced to be unique. If set to `true`, the engine will ensure that at most one instance of this relation type exists between any given **origin** and **target** entities. This is useful for relation types that should not have multiple instances between the same pair of entities (e.g. a **VotaEn** relation type where a person can only vote once in an election). Setting this to `true` implicitly ignores deduplication settings for this relation type, since it considers any pair of relations with the same **origin** and **target** entities as duplicates.                                                                                                                                                                                                                                                                                                                                                                                                   |     `bool`     | `false`   |
| `bypass_LLM`           |    🟡     | A boolean indicating whether this relation type should be extracted without using the LLM. This option is only available for relation types where either the origin or target entity type is a **core entity**. If this relation type is defined between two non-core entities, this field will be ignored and the relations will always be extracted using the LLM. When using this option, the engine **skips the LLM processing** and assumes that, for every instance of the non-core entity type found in a document, said instance has a relation with the respective core entity that represents that document. This field is useful for cases where an entity being found in a document implicitly means that there is a relation with the core entity that represents said document (e.g. for documents that represent **fragments of a book**, any **character entities** mentioned in a document would be implicitly connected to the associated **book fragment core entity** by a relation type such as **"MentionedIn"**). |     `bool`     | `false`   |
| `properties`           |    🟡     | An object defining the specific **properties** of this relation type. This object follows the same rules and structure as with the entities.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             |    `object`    | `{}`      |

Example of the `relations` section in a data model:

```json
"relations": {
    "Contiene": {
        "origin_target": {
            "Sentencia": [
                "Hecho",
            ]
        },
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