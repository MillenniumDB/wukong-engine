<!-- omit from toc -->
# 🧬 Knowledge Model

This document describes the expected format for a `knowledge_model.json` file, which is required by the engine and lives inside a **workspace** directory. The knowledge model declares *what knowledge to extract* from the provided documents: the entity and relationship types, the fields they carry, how each field is obtained, which documents each type is read from, and what makes two extracted objects the same object.

> 🗂️ For the workspace directory layout and the companion `document_collections.json` file, refer to the [Workspace](/docs/workspace.md) documentation.

<!-- omit from toc -->
## 📚 Table of Contents
- [🧾 Knowledge Model Schema](#-knowledge-model-schema)
- [🧭 Context Levels](#-context-levels)
- [⚙️ Extraction Configuration](#️-extraction-configuration)
  - [LLM Settings](#llm-settings)
  - [Projection Settings](#projection-settings)
- [🧩 Entity Types](#-entity-types)
  - [General Definition](#general-definition)
  - [Entity Fields](#entity-fields)
  - [Entity Example](#entity-example)
- [🔗 Relationship Types](#-relationship-types)
  - [General Definition](#general-definition-1)
  - [Endpoints](#endpoints)
  - [Relationship Fields](#relationship-fields)
  - [Relationship Example](#relationship-example)
- [🧮 Identity and Merging](#-identity-and-merging)
  - [Deduplication](#deduplication)
  - [Merge Strategies](#merge-strategies)
  - [Identifiers and Versioning](#identifiers-and-versioning)
- [🔒 Reserved Names](#-reserved-names)
- [💡 Knowledge Model Example](#-knowledge-model-example)

## 🧾 Knowledge Model Schema

The knowledge model is a **JSON** object with three top-level sections:

```json
{
    "extraction_config": {
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

| Section              | Required | Description                                                          |          Type          | Default |
| -------------------- | :------: | -------------------------------------------------------------------- | :--------------------: | ------- |
| `extraction_config`  |    🟡     | Global context and settings for the extraction process.              |        `object`        | `{}`    |
| `entity_types`       |    🟡     | The entity types to extract, keyed by entity type name.              | `object[string, type]` | `{}`    |
| `relationship_types` |    🟡     | The relationship types to extract, keyed by relationship type name.  | `object[string, type]` | `{}`    |

Every section is technically optional, but a model with no entity types extracts nothing.

Throughout this document, ✅ marks a **required** parameter and 🟡 marks an **optional** one.

[📚 Back to Table of Contents](#-table-of-contents)

## 🧭 Context Levels

Many parameters can be specialized per **context level**, which is the kind of source text an extraction reads from. There are two:

| Context Level | Source Text                     | Meaning                                                                            |
| ------------- | ------------------------------- | ---------------------------------------------------------------------------------- |
| `"chunk"`     | A single text chunk.            | The entities a document **mentions**.                                              |
| `"document"`  | A bounded prefix of a document. | The single entity of a given type that a document **is** (e.g. a specific report). |

Wherever a parameter accepts a context level mapping, you may write either:

- an **object** keyed by context level, to give each level its own value:

    ```json
    "retrieval_mode": { "chunk": "extract", "document": "skip" }
    ```

- a **single value**, which is applied to *all* context levels:

    ```json
    "retrieval_mode": "extract"
    ```

Context level keys are case-insensitive (`"chunk"` and `"CHUNK"` are equivalent).

[📚 Back to Table of Contents](#-table-of-contents)

## ⚙️ Extraction Configuration

The `extraction_config` section defines the **general context and settings** for the extraction. It has two sub-sections: `llm` and `projection`.

### LLM Settings

The `llm` sub-section provides contextual information that is included in every extraction request:

| Parameter  | Required | Description                                                                                                     |   Type   | Default                |
| ---------- | :------: | ----------------------------------------------------------------------------------------------------------------- | :------: | ---------------------- |
| `domain`   |    🟡     | A natural-language statement of what the corpus is about. The cheapest available lever on precision, since it lets the LLM reject content that is superficially similar but domain-irrelevant. | `string` | `"General documents."` |
| `language` |    🟡     | The language of the corpus, which also fixes the language in which extracted values are expressed. If omitted, no language instruction is given to the LLM. | `string` | `null`                 |

Accepted `language` values (case-insensitive): `"en"` / `"english"`, and `"es"` / `"spanish"`.

### Projection Settings

The `projection` sub-section controls which of the defined types are **active** for the run. Inactive types are never extracted, never stored and never exported.

| Parameter               | Required | Description                                                                      |      Type      | Default |
| ----------------------- | :------: | ---------------------------------------------------------------------------------- | :------------: | ------- |
| `enabled_entities`      |    🟡     | The names of the entity types to activate. Omit the key (or use `null`) to activate **all** defined entity types; use `[]` to activate none. | `string array` | `null`  |
| `enabled_relationships` |    🟡     | The names of the relationship types to activate. Omit the key (or use `null`) to activate **all** defined relationship types; use `[]` to activate none. | `string array` | `null`  |

Every name listed must correspond to a type defined in `entity_types` / `relationship_types`, otherwise the model is rejected.

A relationship type is active only if it is selected **and** at least one of its endpoints connects two active entity types. A relationship type whose endpoints are all inactive is therefore automatically inactive, which makes it impossible for a projection to produce relationships pointing at absent entities.

Example of a complete `extraction_config` section:

```json
"extraction_config": {
    "llm": {
        "domain": "Mission reports, crew dossiers and incident logs from a fictional deep-space exploration agency.",
        "language": "en"
    },
    "projection": {
        "enabled_entities": [
            "Mission",
            "Spacecraft",
            "Astronaut"
        ],
        "enabled_relationships": [
            "AssignedTo"
        ]
    }
}
```

[📚 Back to Table of Contents](#-table-of-contents)

## 🧩 Entity Types

Entities are the fundamental building blocks of the extracted knowledge. They represent **objects or concepts** found in the documents (e.g. people, organizations, missions), and become nodes when the result is exported to a graph format.

### General Definition

Each entity type is a key inside the `entity_types` object (the **entity type's name**), whose value is an object describing that type.

Entity type names must start with an **uppercase letter**, contain only **alphanumeric characters**, and be at most 64 characters long (regex: `^[A-Z][a-zA-Z0-9]{0,63}$`).

| Parameter                | Required | Description                                                                                                                                                                                                                  |                 Type                 | Default         |
| ------------------------ | :------: | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | :----------------------------------: | --------------- |
| `description`            |    ✅     | What this type represents, in your own words. Reaches the LLM.                                                                                                                                                               |               `string`               | —               |
| `instructions`           |    🟡     | Additional technical guidance for extracting this type. Accepts a context level mapping, since telling the model how to recognize "the mission this document *is*" differs from "the missions this text *mentions*".         | `object[string, string]` or `string` | `{}`            |
| `primary_key`            |    ✅     | The name of the field that identifies instances of this type. Must be defined in `fields`, must be marked `"required": true`, and its retrieval mode must be `"extract"` at every context level it is used at — never `"default"` or `"skip"`.               |               `string`               | —               |
| `deduplication`          |    🟡     | The identity policy for this type. Currently only `"primary_key"` is supported. See [Identity and Merging](#-identity-and-merging).                                                                                          |               `string`               | `"primary_key"` |
| `default_merge_strategy` |    🟡     | How to reconcile field values when the same entity is observed again. Individual fields may override it. See [Merge Strategies](#merge-strategies).                                                                          |               `string`               | `"keep"`        |
| `fields`                 |    🟡     | The **fields** of this entity type, keyed by field name. See [Entity Fields](#entity-fields).                                                                                                                                |       `object[string, Field]`        | `{}`            |
| `document_collections`   |    🟡     | Which document collections this type is extracted from, per context level. Values are collection names (or a single name) defined in `document_collections.json`. A context level left unspecified is **never attempted**.    |    `object[string, string array]`    | `{}`            |

`document_collections` is how you say "this type only makes sense as a whole-document concept" (declare `"document"` only) or "only as a mention" (declare `"chunk"` only). Duplicate collection names within one context level are rejected.

### Entity Fields

The `fields` object defines the attributes of an entity type. Each key is the **field's name**, which must start with a **lowercase letter**, contain only **lowercase alphanumeric characters and underscores**, and be at most 64 characters long (regex: `^[a-z][a-z0-9_]{0,63}$`).

| Parameter        | Required | Description                                                                                                                                                                                             |                 Type                 | Default     |
| ---------------- | :------: | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :----------------------------------: | ----------- |
| `data_type`      |    ✅     | The data type of the field. Currently only `"string"` is supported (aliases: `"str"`, `"text"`).                                                                                                        |               `string`               | —           |
| `description`    |    ✅     | What this field represents. Reaches the LLM.                                                                                                                                                            |               `string`               | —           |
| `instructions`   |    🟡     | Detailed technical guidance for obtaining this field. Accepts a context level mapping.                                                                                                                  | `object[string, string]` or `string` | `{}`        |
| `options`        |    🟡     | A closed vocabulary: the only values this field may take. An empty array means unrestricted.                                                                                                            |      `string array` or `string`      | `[]`        |
| `examples`       |    🟡     | Example value(s) illustrating the expected form. Must themselves satisfy `options` and `regex`, otherwise the model is rejected.                                                                        |      `string array` or `string`      | `[]`        |
| `regex`          |    🟡     | A pattern the value must match to be considered valid (e.g. `"^[a-z][a-z0-9_]*$"`). Accepts a context level mapping, so one level can be stricter than the other.                                       | `object[string, string]` or `string` | `{}`        |
| `default_value`  |    🟡     | The value used when nothing can be extracted, or when the `"default"` retrieval mode is chosen. Accepts a context level mapping. Must itself satisfy `options` and `regex`.                             | `object[string, string]` or `string` | `{}`        |
| `retrieval_mode` |    🟡     | How the value is obtained. Accepts a context level mapping. See the table below.                                                                                                                        | `object[string, string]` or `string` | `"extract"` |
| `required`       |    🟡     | Whether the field is mandatory. An entity missing a required value is discarded rather than repaired. The primary key field must set this to `true` explicitly.                                         |                `bool`                | `false`     |
| `merge_strategy` |    🟡     | Overrides the entity type's `default_merge_strategy` for this field. See [Merge Strategies](#merge-strategies).                                                                                         |               `string`               | `null`      |

**Retrieval modes** determine where an entity field's value comes from:

| Mode        | Description                                                                 | `chunk` | `document` |
| ----------- | --------------------------------------------------------------------------- | :-----: | :--------: |
| `"extract"` | The LLM reads the value from the source text.                               |    ✅    |     ✅      |
| `"default"` | The declared `default_value` is used; the field never enters a prompt.      |    ✅    |     ✅      |
| `"skip"`    | The field is not retrieved at this level and is left `NULL`.                |    ✅    |     ✅      |

Choosing `"default"` or `"skip"` where possible is a real cost and precision lever: a field whose value is known in advance should never occupy space in a prompt or risk being hallucinated. Declaring `"default"` for a context level requires a `default_value` for that same level.

### Entity Example

```json
"Mission": {
    "description": "A crewed or uncrewed deep-space mission operated by the agency.",
    "instructions": {
        "document": "This document IS a mission report. Extract the single mission it reports on.",
        "chunk": "Extract missions explicitly named in this passage, including ones only referred to in passing."
    },
    "primary_key": "code",
    "deduplication": "primary_key",
    "default_merge_strategy": "keep",
    "fields": {
        "code": {
            "data_type": "string",
            "description": "The agency's unique mission code.",
            "instructions": "Must be uppercase letters, a hyphen, then digits, exactly as printed in the report header.",
            "regex": "^[A-Z]{2,10}-[0-9]{1,4}$",
            "examples": ["ARTEMIS-7", "KEPLER-12"],
            "required": true
        },
        "status": {
            "data_type": "string",
            "description": "The current status of the mission.",
            "options": ["planned", "active", "completed", "aborted"],
            "default_value": "active"
        },
        "summary": {
            "data_type": "string",
            "description": "A concise summary of the mission's objective and outcome.",
            "retrieval_mode": { "chunk": "skip", "document": "extract" },
            "merge_strategy": "longest"
        }
    },
    "document_collections": {
        "chunk": ["missions", "incidents"],
        "document": "missions"
    }
}
```

[📚 Back to Table of Contents](#-table-of-contents)

## 🔗 Relationship Types

Relationships are the connections between entities. They represent **links between two entities** found in the documents (e.g. an astronaut assigned to a mission), and become edges when the result is exported to a graph format.

Relationship extraction always happens at the **chunk** level, over entities that have already been extracted. For each chunk, the engine assembles a candidate set from the entities extracted from that chunk plus the entities extracted at the document level from its parent document, and the LLM may only connect candidates drawn from that set. Endpoints are therefore valid by construction.

### General Definition

Each relationship type is a key inside the `relationship_types` object (the **relationship type's name**), whose value is an object describing that type. Names follow the same rule as entity type names (regex: `^[A-Z][a-zA-Z0-9]{0,63}$`).

| Parameter                | Required | Description                                                                                                                                                                                     |                             Type                              | Default         |
| ------------------------ | :------: | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :-----------------------------------------------------------: | --------------- |
| `description`            |    ✅     | What this relationship represents. Reaches the LLM.                                                                                                                                             |                           `string`                            | —               |
| `instructions`           |    🟡     | Additional technical guidance for extracting this type. Unlike entity instructions, this is a plain string (relationships are only extracted at chunk level).                                   |                           `string`                            | `null`          |
| `endpoints`              |    🟡     | The permitted source/target entity type pairs and their context level pairings. See [Endpoints](#endpoints).                                                                                    | `object[string, object[string, EndpointRule array \| object]]` | `{}`            |
| `primary_key`            |    🟡     | The field that distinguishes relationships sharing the same endpoints. Required by the `"primary_key"` deduplication policy. Must be in `fields`, marked `"required": true`, and `"extract"`.    |                           `string`                            | `null`          |
| `deduplication`          |    🟡     | The identity policy for this type: `"primary_key"`, `"endpoints"` or `"none"`. See [Deduplication](#deduplication).                                                                             |                           `string`                            | `"primary_key"` |
| `default_merge_strategy` |    🟡     | How to reconcile field values when the same relationship is observed again. Individual fields may override it.                                                                                  |                           `string`                            | `"keep"`        |
| `fields`                 |    🟡     | The **fields** of this relationship type, keyed by field name. See [Relationship Fields](#relationship-fields).                                                                                 |                     `object[string, Field]`                   | `{}`            |

> ⚠️ `deduplication` defaults to `"primary_key"`, which **requires** a `primary_key`. A relationship type with no primary key must declare `"deduplication": "endpoints"` or `"deduplication": "none"` explicitly, otherwise the model is rejected.

A relationship type with no endpoints is never active, since a relationship needs at least one valid source/target pair to be extractable.

### Endpoints

The `endpoints` object declares which entity types may be connected, and at which context levels. It is a two-level mapping: **source entity type name** → **target entity type name** → the context level pairing rules for that pair.

Each rule is an object with two parameters:

| Parameter               | Required | Description                                                      |               Type                |
| ----------------------- | :------: | ------------------------------------------------------------------ | :-------------------------------: |
| `source_context_levels` |    ✅     | The context level(s) at which the **source** entity may be found. | `string array` or `string` |
| `target_context_levels` |    ✅     | The context level(s) at which the **target** entity may be found. | `string array` or `string` |

Every combination of the two lists is generated. A pair may carry a single rule object instead of an array of rules.

An endpoint therefore carries more information than a conventional domain/range declaration: it is not merely "`A` may reference `B`", but "`A` *as recognized at level l₁* may reference `B` *as recognized at level l₂*". The valid pairings are:

| Source Context Level | Target Context Level | Valid |
| :------------------: | :------------------: | :---: |
|       `chunk`        |       `chunk`        |   ✅   |
|       `chunk`        |      `document`      |   ✅   |
|      `document`      |       `chunk`        |   ✅   |
|      `document`      |      `document`      |   ❌   |

`document` → `document` is excluded by construction: relating two whole documents cannot be justified from a single text region, which would break the engine's provenance guarantee. Declaring it raises an error.

Endpoint declarations are used three times: to decide whether an extraction is worth attempting for a given chunk at all, to decide which candidate entities to show the model, and to validate what the LLM returns.

```json
"endpoints": {
    "Astronaut": {
        "Mission": [
            {
                "source_context_levels": "chunk",
                "target_context_levels": ["document", "chunk"]
            }
        ],
        "Spacecraft": {
            "source_context_levels": "chunk",
            "target_context_levels": "chunk"
        }
    }
}
```

In this example, `Astronaut` entities found in a chunk may be connected to `Mission` entities found either at the document level or in the same chunk, and to `Spacecraft` entities found in the same chunk.

### Relationship Fields

Relationship fields work like entity fields, except that they take **plain values instead of context level mappings** (relationships are only extracted at chunk level) and support a reduced set of retrieval modes.

| Parameter        | Required | Description                                                                                                                       |            Type            | Default     |
| ---------------- | :------: | ----------------------------------------------------------------------------------------------------------------------------------- | :------------------------: | ----------- |
| `data_type`      |    ✅     | The data type of the field. Currently only `"string"` is supported.                                                               |          `string`          | —           |
| `description`    |    ✅     | What this field represents. Reaches the LLM.                                                                                      |          `string`          | —           |
| `instructions`   |    🟡     | Detailed technical guidance for extracting this field.                                                                            |          `string`          | `null`      |
| `options`        |    🟡     | A closed vocabulary: the only values this field may take.                                                                         | `string array` or `string` | `[]`        |
| `examples`       |    🟡     | Example value(s). Must satisfy `options` and `regex`.                                                                             | `string array` or `string` | `[]`        |
| `regex`          |    🟡     | A pattern the value must match to be considered valid.                                                                            |          `string`          | `null`      |
| `default_value`  |    🟡     | The value used when nothing is extracted, or with the `"default"` retrieval mode. Must satisfy `options` and `regex`.             |          `string`          | `null`      |
| `retrieval_mode` |    🟡     | Either `"extract"` (the LLM reads it from the text) or `"default"` (the declared `default_value` is used). `"default"` requires a non-null `default_value`. |          `string`          | `"extract"` |
| `required`       |    🟡     | Whether the field is mandatory. A relationship missing a required value is discarded.                                             |           `bool`           | `false`     |
| `merge_strategy` |    🟡     | Overrides the relationship type's `default_merge_strategy` for this field.                                                        |          `string`          | `null`      |

### Relationship Example

```json
"AssignedTo": {
    "description": "An astronaut serving on a mission.",
    "instructions": "Only assert the assignment when the text states it. Do not infer it from the astronaut merely being mentioned alongside the mission.",
    "endpoints": {
        "Astronaut": {
            "Mission": [
                {
                    "source_context_levels": "chunk",
                    "target_context_levels": ["document", "chunk"]
                }
            ]
        }
    },
    "primary_key": "role",
    "deduplication": "primary_key",
    "fields": {
        "role": {
            "data_type": "string",
            "description": "The role the astronaut served in on this mission.",
            "options": [
                "commander",
                "pilot",
                "flight engineer",
                "science officer",
                "medical officer"
            ],
            "required": true
        },
        "notes": {
            "data_type": "string",
            "description": "A short note on the circumstances of the assignment.",
            "instructions": "Should be concise.",
            "examples": "Replaced the original pilot after the ARTEMIS-6 stand-down.",
            "merge_strategy": "longest"
        }
    }
}
```

[📚 Back to Table of Contents](#-table-of-contents)

## 🧮 Identity and Merging

Identity in WUKONG is **declared, not inferred**. Whether two extracted objects are the same object is decided from the knowledge model and the extracted values alone, with no similarity thresholds and no global clustering step.

Before anything is compared, primary key values are **normalized**: Unicode normalization and transliteration, case folding, dash and whitespace unification, removal of non-printable characters, and trimming. The normalized form is used for identity only — the original extracted value is what the object carries as its property. A value that normalizes to nothing (an empty or purely punctuational key) invalidates its object, which is discarded.

Normalization is deliberately conservative. It removes variation that carries no information (accents, casing, spacing, dash styles) and preserves everything else. Stemming, abbreviation expansion and token reordering are **not** performed, because they destroy distinctions that matter in some domains. The practical consequence is that a primary key with a declared `regex` and worked `examples` — which asks the LLM to emit a canonical form directly — deduplicates far better than a free-form name-like key.

### Deduplication

The `deduplication` parameter selects the identity policy.

For **entity types**:

| Value           | Aliases          | Meaning                                                                       |
| --------------- | ---------------- | ------------------------------------------------------------------------------- |
| `"primary_key"` | `"pk"`, `"identity"` | Two entities of this type with the same normalized primary key are the same entity. |

For **relationship types**:

| Value           | Aliases                      | Meaning                                                                                                                                               |
| --------------- | ---------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- | 
| `"primary_key"` | `"pk"`, `"identity"`         | Same only if the endpoints **and** the normalized primary key match. For pairs that may be connected in several distinguishable ways. Requires a `primary_key`. |
| `"endpoints"`   | `"structural"`, `"edge"`     | Same if the source and target entities match, regardless of field values. For edges asserting a fact that either holds or does not.                   |
| `"none"`        | `"disabled"`, `"off"`        | Every extraction is a distinct relationship. For event- or observation-like relations, where repetition is itself information.                        |

### Merge Strategies

When an object is observed again, each field is reconciled according to its merge strategy — the field's own `merge_strategy` if set, otherwise the type's `default_merge_strategy`.

| Value        | Aliases                                              | Meaning                                                      |
| ------------ | ---------------------------------------------------- | -------------------------------------------------------------- |
| `"keep"`     | `"existing"`, `"preserve"`, `"retain"`, `"first"`    | Keep the stored value, ignore the incoming one.              |
| `"replace"`  | `"incoming"`, `"overwrite"`, `"update"`, `"last"`    | Replace the stored value with the incoming one.              |
| `"longest"`  | `"verbose"`, `"complete"`                            | Prefer the longer value, assuming it carries more information. |
| `"shortest"` | `"concise"`, `"minimal"`                             | Prefer the shorter value, assuming it is more precise.        |

A `NULL` value never overwrites a non-null one, regardless of strategy. Observations are therefore monotonically informative: seeing an object again can add knowledge but never remove it.

A typical arrangement is `"keep"` as the type default (identifier-like fields should be immutable) with `"longest"` on descriptive fields such as summaries.

### Identifiers and Versioning

Every exported object carries two identifiers:

| Identifier     | Form                                                              | Meaning                                                                                                                                                           |
| -------------- | ----------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Instance ID** | A UUIDv7, as 32 hex characters.                                  | Unique per object and per run. It is the object's ID in the export, and what relationships and provenance links use to reference their endpoints.                |
| **Content ID**  | The first 128 bits of a SHA-256 hash, as 32 hex characters.      | Derived only from the object's identity-defining components, so it is **deterministic**: the same components always produce the same content ID, in any run or workspace. Two objects are the same object exactly when their content IDs are equal. |

The content ID is what makes identity reproducible, and what lets results be compared across runs: an entity extracted in two different workspaces with the same type and the same normalized primary key has the same content ID in both.

The way a content ID is computed is an **identity definition**, and each definition is **versioned**. The version tag is the first component of the hashed string, so identifiers from different versions can never collide, and it is exported next to the content ID so that every identifier in the output declares the definition it was computed under. If a future release changes what goes into an identity — its components, their order, or the primary key normalization — the version is bumped rather than the meaning of an existing version changed. Content IDs are therefore only comparable when their versions match; to compare results produced under different versions, re-run the older workspace with the current engine.

The current identity definitions are version **`v1`**, where `|` is a literal separator and a *content ID* component is the hex content ID of the referenced object:

| Object                                  | Version | Hashed String                                                                   |
| --------------------------------------- | :-----: | --------------------------------------------------------------------------------- |
| Entity                                  |  `v1`   | `v1\|<EntityType>\|<NormalizedPK>`                                               |
| Relationship (`"primary_key"`)          |  `v1`   | `v1\|<RelationshipType>\|PRIMARY_KEY\|<SourceContentID>\|<TargetContentID>\|<NormalizedPK>` |
| Relationship (`"endpoints"`)            |  `v1`   | `v1\|<RelationshipType>\|ENDPOINTS\|<SourceContentID>\|<TargetContentID>`        |
| Relationship (`"none"`)                 |  `v1`   | Nothing is hashed: the content ID equals the instance ID, so every relationship is distinct. |
| `Chunk`                                 |  `v1`   | `v1\|<DocumentContentID>\|<ChunkIndex>`                                          |
| `Document`                              |    —    | The document's raw bytes. Unversioned, since it depends on nothing but the file.  |

Relationship identities are built from the **content IDs** of their endpoints, not their instance IDs, so they are as reproducible as the entities they connect. The identity policy is part of the hashed string, so changing a relationship type's `deduplication` changes the identity of all of its relationships.

The normalized primary key is part of the `v1` definition. Under `v1`, a raw primary key is normalized by, in order:

1. Applying Unicode **NFKC** normalization.
2. Removing non-printable characters.
3. Replacing en and em dashes (`–`, `—`) with a hyphen (`-`).
4. **Case folding**.
5. **Transliterating** to ASCII (e.g. `é` → `e`, `ß` → `ss`).
6. Removing every character other than lowercase letters, digits, whitespace and `/ \ - + _ # & @ . : ( )`.
7. Trimming whitespace and `/ \ . : ( )` from both ends.
8. Collapsing runs of whitespace into a single space.

A key that is empty after these steps is invalid, and its object is discarded.

In the exported output, identifiers appear as follows:

| Export Format | Instance ID                                                    | Content ID      | Version         | Relationship Identity Policy |
| ------------- | -------------------------------------------------------------- | --------------- | --------------- | ---------------------------- |
| `mdb`         | The node ID (`N_<InstanceID>`); `P_id` on relationships.       | `P_content_id`  | `P_id_version`  | `P_id_policy`                |
| `neo4j`       | `_id`                                                          | `_content_id`   | `_id_version`   | `_id_policy`                 |

`Document` objects carry no version property, and the `ChunkOf` / `ExtractedFrom` provenance links carry no identifiers of their own.

[📚 Back to Table of Contents](#-table-of-contents)

## 🔒 Reserved Names

The engine always materializes the source documents as part of the result, so a few names are reserved and cannot be used in a knowledge model:

| Reserved Name   | Kind              | Purpose                                                            |
| --------------- | ----------------- | -------------------------------------------------------------------- |
| `Document`      | Entity type       | One object per source document.                                    |
| `Chunk`         | Entity type       | One object per text chunk, carrying its text and its exact span.   |
| `ChunkOf`       | Relationship type | Links each `Chunk` to its parent `Document`.                       |
| `ExtractedFrom` | Relationship type | Links each extracted entity to every source context it was seen in. |

The check is case-insensitive, so `document` and `CHUNKOF` are rejected too.

[📚 Back to Table of Contents](#-table-of-contents)

## 💡 Knowledge Model Example

A complete, working knowledge model is provided at [`workspaces/example/knowledge_model.json`](/workspaces/example/knowledge_model.json), paired with the documents in [`data/example/`](/data/example/). It exercises both context levels, cross-level endpoints, closed vocabularies, pattern-constrained identifiers and per-field merge strategies.

Run the engine over it with:

```sh
poetry run wukong run workspaces/example data/example
```

[📚 Back to Table of Contents](#-table-of-contents)
