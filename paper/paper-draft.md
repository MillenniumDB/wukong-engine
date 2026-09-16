# WUKONG: Schema-Guided, Provenance-Aware Knowledge Extraction from Unstructured Text with Large Language Models

> **Status:** Draft v0.2. Text only, conceptual level. Architecture, code and
> implementation-specific concerns are deliberately out of scope.
> Sections marked `[TODO]` require author input or experimental results.
> Section 14 lists open questions to resolve before the next revision.

---

## Abstract

Structured representations of information that originates as unstructured text — knowledge
graphs among them — are an effective substrate for integration, querying and reasoning, but
building them remains costly: classical information-extraction pipelines require per-domain
supervision, while open-ended extraction with large language models (LLMs) produces output
that is noisy, schema-free, unstable across runs, and difficult to align with the questions
a user actually wants to ask.

We present **WUKONG** (*Weaving Unstructured Knowledge: Organize, Normalize, Generate*), a
schema-guided pipeline that turns a collection of plain-text documents into a typed,
deduplicated, provenance-carrying body of knowledge that conforms, by construction, to a
user-supplied *knowledge model*. The knowledge model is a declarative artifact that
specifies which entity and relationship types exist, which fields they carry, how each field
is obtained, which source material each type should be read from, and — critically — what
makes two extracted objects *the same object*. Extraction produces a canonical,
format-independent result, which a final rendering stage emits in a target representation;
property-graph formats are supported today, and the separation is what allows further
representations to be added without repeating any extraction work.

WUKONG contributes four ideas. First, a **two-level extraction context**: every entity
type declares whether its instances are properties *of a document as a whole* or things
*mentioned inside* a document, and relationships may cross these two levels. Second,
**entity-grounded relationship extraction**: relationships are never extracted as free
text triples; the LLM is shown a pre-computed, type-compatible candidate set of already
extracted entities and can only connect identifiers drawn from that set, which turns
relation extraction into a constrained matching problem and eliminates dangling
endpoints. Third, **deterministic, declarative identity**: entities and relationships are
assigned content-derived identifiers computed from a normalized primary key and a
user-chosen identity policy, so deduplication and cross-document merging are a
consequence of the schema rather than a post-hoc clustering step. Fourth, an
**incremental, resumable execution model** in which extraction is decomposed into
independently retryable units of work over a durable staging representation, allowing
long-running jobs over large corpora to be interrupted, resumed, partially re-run, and
executed either interactively or through asynchronous batch interfaces at substantially
lower cost.

The result is provenance-aware by default: every extracted object is linked to the exact
text region it was read from, and the source documents and their chunks are first-class
objects in the output. We describe the design, discuss the trade-offs of each decision, and
report an evaluation on a public benchmark with reference annotations and on a corpus of
~1,000 Spanish news articles. On Text2KGBench's Wikidata-TekGen suite the system produces
output that conforms to the given ontology in every case and whose relation arguments are
almost never absent from the source sentence — subject hallucination 0.00 and object
hallucination 0.01, against 0.17 for 2-shot baselines on the same data — at accuracy
comparable to those baselines and a cost of roughly $0.0007 per sentence. On the news
corpus, request grouping and endpoint pruning together reduce the number of LLM calls by
roughly 6× against a naive per-type decomposition.

**Keywords:** knowledge extraction, knowledge graph construction, information extraction,
large language models, schema-guided extraction, entity resolution, provenance.

---

## 1. Introduction

### 1.1 Motivation

A large fraction of institutional knowledge — legal codes and their administrative
interpretations, court rulings, incident reports, clinical notes, scientific literature,
news archives — exists only as prose. Making it queryable at scale requires converting it
into a structured representation. Knowledge graphs are an attractive target: they are
schema-flexible, they support multi-hop navigation, and they compose naturally with both
symbolic querying and retrieval-augmented generation.

The difficulty is the conversion itself. Traditional information extraction (IE)
pipelines — named entity recognition, entity linking, relation classification — are
accurate but require labelled data for every new domain, entity type and relation type.
LLMs remove that requirement: a competent model, given a description of what to look for,
can extract entities and relations from arbitrary prose in a zero-shot manner. This has
made "prompt an LLM over text chunks and collect triples" a common recipe.

That recipe, however, degrades in predictable ways once it leaves the demo setting:

- **Schema drift.** Without an enforced schema, the same real-world concept appears under
  different type names, with different attributes, in different chunks. The output is a
  union of many locally reasonable but globally inconsistent decisions.
- **Identity collapse and identity explosion.** "Article 5 bis", "artículo 5 bis" and
  "art. 5-bis" may become three nodes; conversely, two genuinely different entities with
  similar surface forms may be conflated. Deduplication is usually deferred to a
  string-similarity or embedding-clustering step whose behaviour the user cannot specify
  in advance.
- **Ungrounded relations.** When relations are extracted as free-text `(subject,
  predicate, object)` triples, the endpoints must be linked to nodes afterwards. Linking
  fails for a non-trivial fraction of triples, producing dangling edges, duplicated
  endpoints, or silently dropped facts.
- **Loss of provenance.** Once triples are merged, the connection to the sentence that
  justified them is typically lost, making verification, auditing and
  retrieval-augmented use much weaker.
- **Cost and fragility at scale.** A corpus of tens of thousands of documents means
  hundreds of thousands of LLM calls. A pipeline that cannot resume after a failure,
  cannot skip work already done, and cannot exploit cheaper asynchronous execution modes
  is not economically viable.
- **Context mismatch.** Some facts are properties of an entire document (its
  identifier, its type, its date, its issuing body); others are mentioned inside it. A
  pipeline that only knows how to process chunks cannot express the first kind, and a
  pipeline that only processes whole documents cannot find the second.

### 1.2 Approach

WUKONG takes the position that **the schema should be an input, not an output**. The user
provides a *knowledge model*: a declarative description of the knowledge to be extracted,
written once per domain, that specifies not only the vocabulary (entity types, relationship
types, fields) but also the *operational* semantics of extraction — what each type should be
read from, how each field is obtained, what identifies an object, how conflicting values are
reconciled, and which parts of the model are active in a given run.

Everything downstream is derived from that artifact. Prompts are generated from it. The
structure the LLM is required to emit is generated from it. Validation, identity,
deduplication, merging and rendering are all governed by it. The user's leverage over output
quality is therefore concentrated in a single, inspectable, versionable object, rather
than being spread across prompt engineering and post-processing heuristics.

A second, related position is that **extraction and representation are separate concerns**.
What the pipeline produces is a canonical body of typed, deduplicated, provenance-carrying
knowledge; how that body is written out is a downstream choice. Property-graph formats are
what the current implementation emits, and the design is deliberately arranged so that
additional representations require no re-extraction. The system is named after the Monkey
King of *Journey to the West*, whose defining power is transformation — a fitting emblem for
knowledge that is read once and can then take whatever shape its consumer requires.

### 1.3 Contributions

1. **A declarative knowledge model for LLM-based extraction** (§4) that unifies target-schema
   description, extraction instructions, source selection, identity policy and merge
   policy in one artifact, with per-context-level specialization.
2. **A two-level extraction context** (§5.2) distinguishing document-level entities
   (an entity representing a whole source) from chunk-level entities (instances mentioned
   inside a source), and relationships that connect across levels.
3. **Entity-grounded relationship extraction** (§5.3): relationships are extracted as
   matchings over a pre-filtered candidate entity set presented with local identifiers,
   so endpoints are valid by construction and the extraction task is reduced from
   generation to selection.
4. **Deterministic declarative identity and deduplication** (§6): content-derived
   identifiers computed from normalized primary keys and explicit identity policies,
   plus field-level merge strategies for reconciling repeated observations.
5. **A provenance model in which sources are part of the output** (§7): documents and
   chunks are first-class objects, and every extracted object retains links to all the text
   regions in which it was observed.
6. **An incremental, resumable, dual-mode execution model** (§8) with per-unit state,
   typed retry semantics and support for both interactive and asynchronous batch
   execution, together with the cost/progress observability such runs require.
7. **Separation of extraction from representation** (§9): a single canonical result is
   rendered into target formats by an interchangeable final stage, together with a
   *projection* mechanism that selects which schema elements reach the output.

Empirically (§11.5), on a public benchmark with reference annotations the design yields
output that is ontology-conformant in every case and effectively free of hallucinated
arguments (subject 0.00, object 0.01, against 0.17–0.19 for 2-shot baselines), at accuracy
comparable to those baselines and a cost of ≈$0.0007 per sentence.

---

## 2. Related Work

`[TODO: this section is a skeleton with the intended argument; citations to be filled in.]`

**Classical information extraction.** Supervised NER, entity linking and relation
extraction achieve high precision within their training distribution but require
annotated corpora per domain and per relation inventory. WUKONG targets the setting where
no such annotation exists and the type inventory changes with each project.

**Open information extraction.** OpenIE-style systems extract surface triples without a
predefined schema. They maximize recall and require no configuration, but their output is
a lexical rather than conceptual graph: normalization, typing and canonicalization are
left entirely to downstream consumers. WUKONG makes the opposite trade: it accepts a
configuration cost in exchange for output that is directly usable.

**LLM-based knowledge graph construction.** Recent systems prompt LLMs to emit graph
fragments per chunk and then merge them, optionally summarizing communities for
retrieval. These systems are closest to WUKONG in spirit. The distinguishing points of
our design are: (i) the schema is enforced at both generation and validation time rather
than suggested; (ii) relationship endpoints are selected from a candidate set instead of
generated and linked afterwards; (iii) identity is declarative and deterministic rather
than similarity-based; (iv) extraction context is explicitly two-level; and (v) the
execution model is designed for resumable, cost-aware operation over large corpora.
`[TODO: name and position GraphRAG, LLMGraphTransformer, iText2KG, KGGen, SAC-KG, Docs2KG
or whichever systems the authors want to compare against.]`

**Ontology- and schema-driven extraction.** Work on ontology-guided prompting shares our
premise that a target vocabulary improves consistency. WUKONG extends this beyond
vocabulary to the operational aspects of extraction: source selection, retrieval mode,
identity, merging and projection.

**Entity resolution.** Classical ER computes similarity between records and clusters
them. WUKONG instead asks the user to declare *what identifies an object* and then
enforces that declaration exactly, after a normalization step. This is a deliberate
restriction, discussed in §10; approximate matching is complementary future work.

**Retrieval-augmented generation.** Graphs produced by WUKONG are intended, among other
uses, as a substrate for grounded RAG: because chunks are part of the result and every fact
points back to its supporting text, a structural query can be turned into a set of verbatim
passages.
`[TODO: connect to the authors' intended downstream applications.]`

---

## 3. Problem Statement and Preliminaries

### 3.1 Input

The input is a set of **document collections**. A collection is a named group of
plain-text documents that share a nature or provenance (for example, one collection per
legal body, per source institution, or per document genre). Collections are the unit at
which the user says "this part of the schema applies to that part of the corpus", which
matters because real corpora are heterogeneous: a schema element that makes sense for
regulations makes no sense for the news articles filed alongside them.

Formally, the input is a pair `(C, M)` where `C = {c_1, ..., c_k}` is a family of document
collections and `M` is a knowledge model (§4).

### 3.2 Output

The pipeline produces a canonical **knowledge base** `K = (O, R)` in which:

- `O` contains one object per extracted entity, plus one object per source document and one
  per text chunk;
- `R` contains one relation instance per extracted relationship, plus structural relations
  linking chunks to their documents and extracted objects to the text regions they came
  from;
- objects and relations are labelled with the type names declared in `M` and carry the
  fields declared for those types.

`K` is representation-independent: it is a typed, deduplicated, provenance-carrying result,
not a file format. A final stage renders it into a concrete target representation (§9).
Because `K` is entity–relation shaped, property graphs are its most direct rendering, and
they are what the current implementation emits: `O` becomes nodes, `R` becomes edges. This
is a natural fit rather than a constraint — other renderings of the same result require no
change to anything upstream of §9, and none of the design in §4–§8 assumes a graph target.

### 3.3 Requirements

The design is driven by the following requirements:

- **R1 — Conformance.** Every object and relation in `K` must be an instance of a type
  declared in `M`, with fields that satisfy the constraints declared for that type.
- **R2 — Determinism of identity.** Whether two extracted objects are the same object must
  be decidable from `M` and the extracted values alone, without similarity thresholds or
  run-dependent state.
- **R3 — Grounding.** Every relationship must connect two entities that exist in `K`; no
  dangling or invented endpoints.
- **R4 — Provenance.** Every extracted object must be traceable to the text region(s) that
  justify it.
- **R5 — Incrementality.** A run must be resumable, and re-running must not duplicate
  completed work or corrupt existing results.
- **R6 — Cost-awareness.** The pipeline must expose and control the number, size and
  execution mode of LLM calls.
- **R7 — Domain independence.** No component may hard-code domain vocabulary; all domain
  knowledge lives in `M`.
- **R8 — Representation independence.** No stage before rendering may assume a particular
  output representation, and adding one must not require re-extraction.

### 3.4 Terminology

| Term | Meaning |
| --- | --- |
| Document | One plain-text source, identified by its content. |
| Chunk | A contiguous text region of a document, produced by segmentation. |
| Context level | Whether extraction reads a whole document or a single chunk. |
| Source context | The specific document or chunk an extraction reads from. |
| Entity type / relationship type | An object/relation class declared in the knowledge model. |
| Field | A named, typed attribute of an entity or relationship type. |
| Primary key | The field whose (normalized) value identifies an object of its type. |
| Mention | An observation of an object in a particular source context. |
| Projection | The subset of the knowledge model that is active for a given run. |

---

## 4. The Knowledge Model

The knowledge model is the single declarative input that governs the run. It has three parts:
an extraction configuration, a set of entity types, and a set of relationship types.

### 4.1 Extraction configuration

Global context for the run:

- **Domain description.** A natural-language statement of what the corpus is about,
  provided to the LLM in every extraction request. This is the cheapest available lever
  on precision: it lets the LLM reject content that is superficially similar but
  domain-irrelevant.
- **Language.** The language of the corpus, which also fixes the language in which
  extracted values are expressed.
- **Projection.** The subsets of entity types and relationship types that are active. A
  projection lets a user maintain one comprehensive model of a domain and run
  narrower experiments from it, and it composes with the rest of the pipeline: inactive
  types are never extracted, never stored and never exported, and a relationship type
  whose endpoints are all inactive is itself automatically inactive.

### 4.2 Entity types

An entity type declares:

- a **description** — what the type represents, in the user's own words;
- optional **instructions** — technical guidance for extraction, which may be specialized
  per context level, since telling a model how to recognize "the article this document
  *is*" differs from telling it how to recognize "articles this text *mentions*";
- a **primary key** — the field that identifies instances of the type;
- an **identity (deduplication) policy** — see §6;
- a **default merge strategy** — see §6.4;
- a set of **fields** (§4.4);
- a **source binding**: for each context level, the document collections from which this
  type should be extracted. A type may be extracted from documents in some collections,
  from chunks in others, or both. A context level that is left unspecified is never
  attempted, which is how the user says "this type only makes sense as a whole-document
  concept" or "only as a mention".

Two type names are reserved for the structural types (`Document`, `Chunk`) that the
pipeline always materializes.

### 4.3 Relationship types

A relationship type declares:

- a **description** and optional **instructions**, as above;
- **endpoints**: the permitted `(source entity type, target entity type)` pairs, each
  annotated with the permitted **context-level pairings** of its two ends;
- an optional **primary key**;
- an **identity policy** (§6.3);
- a **default merge strategy**;
- a set of **fields**.

Endpoints deserve emphasis, because they carry more information than a conventional
domain/range declaration. An endpoint is not merely "`A` may reference `B`"; it is "`A`
*as recognized at level `l₁`* may reference `B` *as recognized at level `l₂`*". A
relationship may therefore connect an entity representing an entire document to an entity
mentioned inside a different document, which is exactly the shape of, e.g., a citation
between a regulation and a provision quoted in another text. The `document`–`document`
pairing is excluded by construction, since relating two whole documents cannot be
justified from a single text region under our provenance requirement (R4).

Endpoint declarations are used three times: to decide *whether an extraction is worth
attempting at all* for a given chunk, to decide *which candidate entities to show the
model*, and to *validate* what the LLM returns (§5.3).

### 4.4 Fields

Fields are the attributes of entity and relationship types. A field declares:

- **data type** `[currently: string only — see §10]`;
- **description**, and optional **instructions**, both of which reach the LLM;
- optional **allowed values**, restricting the field to a closed vocabulary;
- optional **examples**, illustrating the expected form;
- optional **regular expression**, a hard syntactic constraint on the value;
- an optional **default value**, used when nothing can be extracted;
- a **retrieval mode**, stating *how* the value is obtained;
- a **required** flag;
- an optional **merge strategy** overriding the type's default.

For entity fields, all of these may be specialized per context level. This is what allows
a single type definition to behave differently depending on where it is read from: a
field may be extracted from whole documents, defaulted at chunk level, and constrained by
a stricter pattern in one context than the other.

**Retrieval modes.** A field value may be *extracted* from the text by the LLM,
*defaulted* to a constant declared in the knowledge model, or *skipped* (left null). Making
this explicit matters for cost and precision: fields whose value is known a priori (a
provenance tag, a source category, a constant classification) should never occupy space in a
prompt or risk being hallucinated. Relationship fields support extraction and defaulting.

**Constraints as a two-sided mechanism.** Allowed values, examples and patterns are used
both *before* the call — they shape the request and, where the provider supports it, the
enumerated values the LLM may emit — and *after* it, as validation predicates. A value
that violates its declared constraints causes its object to be discarded rather than
repaired, on the principle that a silently corrected value is worse than an absent one
(§10 revisits this).

---

## 5. Pipeline

The pipeline has four conceptual stages: ingestion, entity extraction, relationship
extraction, and rendering. Stages are ordered by data dependency and each is individually
skippable, so a user may re-render without re-extracting, or extend an existing knowledge
base with a new relationship type without re-reading documents.

### 5.1 Stage A — Ingestion and segmentation

Documents are registered and segmented; their text is stored in an internal staging
representation, while the original files are referenced by location rather than copied.

**Identity of sources.** A document is identified by the content of its bytes, and a chunk
by its parent document together with its position. Re-ingesting the same document is
therefore a no-op, and two identical files in different collections are one document
belonging to two collections. This is the first place where the pipeline's general
identity discipline (§6) appears.

**Structure-aware segmentation.** Segmentation must reconcile two opposing pressures.
Chunks should be small, because a smaller chunk means a cheaper call, a more focused
model, and finer-grained provenance. Chunks should be large, because a fact split across a
boundary is a fact that cannot be extracted, and because per-call overhead is amortized
over chunk content.

WUKONG segments recursively along a *hierarchy of boundaries*, from most to least
semantically meaningful: structural headings, paragraphs, lines, sentences, and finally
words. The procedure is:

1. If the region already fits the size budget, keep it.
2. Otherwise split it at the current boundary level and *pack* the resulting pieces
   greedily toward a target size, never exceeding a hard maximum.
3. Any piece that alone exceeds the maximum is refined at the next boundary level.
4. If all boundary levels are exhausted, split at token positions as a last resort,
   snapping the cut to the nearest whitespace so that words survive intact.

The target size is treated as *soft*: when adding the next piece would overshoot, the
packer keeps whichever alternative lands closer to the target, rather than mechanically
cutting at the limit. The effect is that chunk boundaries coincide with document structure
whenever the structure permits, and degrade gracefully when it does not.

**Overlap.** Consecutive chunks share a configurable overlap, so that a statement
straddling a boundary is complete in at least one chunk. Overlap trades cost (the same
text is read more than once) for recall, and interacts with deduplication: the same fact
observed in two overlapping chunks converges to one object with two mentions (§6, §7),
rather than to two objects.

Segmentation is deterministic and offset-preserving: every chunk records its exact span in
the source, which is what makes the provenance links of §7 verifiable.

### 5.2 Stage B — Entity extraction

**Two context levels.** Entity extraction runs at two levels, in order:

- **Document level.** The source text is the document itself (truncated to a bounded
  prefix, since document-defining information is overwhelmingly front-loaded and reading
  entire documents is neither affordable nor necessary). The task is: *identify the single
  primary entity of each declared type that this whole document represents, and fill in
  its fields from all relevant information in the text.* This yields the entity that a
  document *is* — a specific regulation, a specific case, a specific report.
- **Chunk level.** The source text is one chunk. The task is: *find all entities of the
  declared types that appear in this text.* This yields the entities a document *mentions*.

Running the document level first is not incidental: document-level entities become part of
the context available when relationships are extracted from that document's chunks (§5.3).

**Unit of work.** An extraction request corresponds to one *source context* and covers all
entity types still pending for it. Grouping types per source rather than issuing one call
per (source, type) pair is a deliberate cost decision: the source text — by far the largest
part of the request — is transmitted once, and the LLM sees all the type definitions
simultaneously, which lets it discriminate between similar types instead of judging each in
isolation. Progress is nevertheless tracked at (source, type) granularity, so that a type
added to the knowledge model later is extracted only where it is actually missing.

**Request composition.** Each request is assembled from the knowledge model: the domain and
language context, the task statement for the applicable context level, the definitions of the
relevant entity types with their descriptions, instructions, and per-field guidance
(description, instructions, examples, obligatoriness), and the source text, delimited so
that it is unambiguously data rather than instruction. A structural description of the
expected response is attached, so that the reply is a typed object per extracted entity,
tagged with its type, rather than free prose to be parsed.

Two global constraints are stated in every request: *do not infer, invent or guess values*,
and *do not emit an entity whose required fields cannot be determined from this text*.
Omission is always preferable to fabrication, because a missing entity can be recovered by
another chunk or another run, while a fabricated one propagates into the result and, worse,
into anything computed from it.

**Materialization and validation.** A returned object becomes an entity only if it passes
every check: its type is one that was actually requested for this source; every required
field is present; every value respects its declared vocabulary and pattern; and its
primary-key value survives normalization (§6.1). Objects failing any check are discarded
and counted. Constant-valued and defaulted fields are filled in at this point, so that
values the user already knows never depend on the LLM.

### 5.3 Stage C — Relationship extraction

Relationship extraction is where the design departs most from the common practice, and it
is the stage that most determines whether the output is a connected body of knowledge or a
pile of triples.

**Relationships are matchings, not generations.** Relationship extraction is always
performed at the chunk level, over the entities that have already been extracted. For a
given chunk, the pipeline assembles a *candidate set* consisting of the entities extracted
from that chunk and the entities extracted at the document level from its parent document.
Each candidate is presented with a **local identifier** valid only for this request,
together with its primary key and its other known field values. The task given to the
model is then: *given this text and these available entities, report which of the declared
relationships hold between them*, where endpoints must be referred to by local identifier.

This has several consequences. The model never has to invent, spell or re-normalize an
entity name, so relationship extraction does not reintroduce the surface-form variation
that entity deduplication just removed. Endpoints are guaranteed to resolve to entities
that exist (R3). The local identifiers are compact, so the candidate set costs little to
transmit compared with the entity descriptions it replaces. And the task itself becomes a
selection problem over a small closed set, which is markedly easier than open generation
— a difference we expect to be most pronounced for smaller and cheaper models. The
grounding half of this claim is supported in §11.5: selecting endpoints from a candidate set
yields 0.00 subject and 0.01 object hallucination on a public benchmark, where 2-shot
baselines generating endpoint strings freely reach 0.17–0.19 on the same sentences. The
claim about *smaller* models specifically remains untested, since we report one model.
`[TODO: a second, cheaper model would turn this into a real comparison — see RQ6.]`

**Type-compatibility pruning.** Before anything is sent anywhere, each chunk is checked
against the declared endpoints: for each relationship type, is there an endpoint whose
source type is available at the required level and whose target type is available at the
required level, given what was actually extracted from this chunk and its parent document?
Relationship types with no viable endpoint for this chunk are dropped from the request;
chunks with no viable relationship type at all are never sent. Only the entity types that
participate in some viable endpoint are included in the candidate set.

This pruning is the main cost control of the stage. Relationship extraction naively costs
one call per chunk per relationship type; with grouping and pruning it costs one call per
*eligible* chunk, and the candidate set contains only entities that could plausibly be
connected. In corpora where relationships are sparse — the common case — the majority of
chunks are eliminated without a single LLM call.

**Validation.** A returned relationship is materialized only if its type was requested, its
two local identifiers resolve, the resulting `(source type, source level, target type,
target level)` combination matches a declared endpoint, and its fields pass the same
constraint checks as entity fields. Endpoint validation is performed even though the
request already listed only valid combinations: the declared endpoints are the
specification, and the LLM's output is evidence, not authority.

### 5.4 Stage D — Rendering

Once extraction is complete, the staging representation holds the canonical knowledge base
`K` in a representation-independent form. Rendering is a traversal of that representation,
emitting the active types (per the projection), the structural document and chunk objects,
the provenance relations, and the fields of every object, in the target representation.
Renderers are interchangeable and read only `K`, so support for a representation is additive
and no extraction work is repeated to obtain a second one. `[TODO: state the currently
supported targets at the intended level of generality — a quad-model graph database format
and a bulk-import CSV format for a mainstream property-graph engine.]`

---

## 6. Identity, Deduplication and Merging

Identity is the part of KG construction where LLM pipelines most often fail, and WUKONG's
central position is that identity should be **declared, not inferred**.

### 6.1 Normalization

Before anything is compared, primary-key values are normalized: Unicode normalization and
transliteration, case folding, dash and whitespace unification, removal of
non-printable and disallowed characters, and trimming. The normalized form is the *identity
surface* of the object; the original extracted value is kept as the object's property, so
the output presents the value as it appeared in the text while identity is computed on a
canonical form. A value that cannot be normalized to a valid identity surface — an empty
or purely punctuational key, for instance — invalidates its object, which is discarded.

Normalization is intentionally conservative: it removes the variation that carries no
information (accents, casing, spacing, dash styles) and preserves everything that might.
Aggressive normalization (stemming, abbreviation expansion, token reordering) is not
performed, because it destroys distinctions that are meaningful in some domains — legal
identifiers being the obvious example.

### 6.2 Content-derived identity for entities

The identifier of an entity is derived deterministically from `(identity scheme version,
entity type, normalized primary key)`. Two extractions from different chunks, different
documents, different runs or different machines that yield the same type and the same
normalized key yield the same identity. Deduplication is therefore not a stage of the
pipeline; it is a property of how identity is computed, and it holds across the entire
corpus without any global comparison step.

Each object also carries a second, run-unique identifier, which is what appears as its
identity in the rendered output. Separating "what this object is" from "which object this
is" lets the content identity change with the identity scheme without invalidating
references, and lets each rendering use identifiers of the kind its target prefers. The
identity scheme is explicitly versioned, and the version travels with the rendered data, so
that results built under different schemes are distinguishable rather than silently mixed.

### 6.3 Identity policies for relationships

Relationships do not have a single sensible notion of identity, so the knowledge model
declares one per type:

- **Endpoint identity.** Two relationships of this type with the same source and target
  entities are the same relationship, regardless of their field values. Appropriate when
  the edge asserts a fact that either holds or does not — "cites", "is located in".
- **Endpoint + primary key identity.** Two relationships are the same only if they share
  endpoints *and* the normalized value of the declared primary key. Appropriate when the
  same pair of entities may be connected in several distinguishable ways — a "references"
  edge qualified by a *kind* of reference, where "interprets" and "amends" are different
  facts about the same pair.
- **No identity.** Every extraction is a distinct edge. Appropriate for event- or
  observation-like relations, where repetition is itself information and collapsing it
  would lose data.

As with entities, the policy is part of the identifier computation, so it is enforced
uniformly and needs no separate reconciliation step.

### 6.4 Merging repeated observations

When an object is observed again, the pipeline must reconcile the new field values with the
stored ones. Reconciliation is per-field and governed by a declared **merge strategy**:
keep the existing value, replace it with the incoming one, prefer the longer value (on the
assumption that it is more informative), or prefer the shorter one (on the assumption that
it is more precise). A null value never overwrites a non-null one, regardless of strategy,
so observations are monotonically informative: seeing an object again can add knowledge but
never remove it. Types declare a default strategy and individual fields may override it —
an identifier field may sensibly be immutable while a description field prefers the fullest
version encountered.

### 6.5 Why declarative rather than similarity-based

The alternative — cluster extracted objects by string or embedding similarity — offers
higher recall on messy surface forms, at the cost of three properties WUKONG treats as
non-negotiable: *predictability* (the user can state, in advance and exactly, when two
objects are one), *stability* (results do not shift because a threshold, an embedding model
or the corpus composition changed), and *locality* (identity is computed per object, with
no global clustering pass, which is what makes incremental and distributed extraction
possible at all).

The cost is real: variants that normalization does not unify remain distinct objects. The
mitigation available today is to move canonicalization into the schema — a primary key with
a declared pattern and worked examples asks the LLM to emit a canonical form directly
rather than asking the pipeline to repair a free-form one. In the corpora we have processed
this is highly effective for identifier-like keys and weaker for name-like keys. §10
returns to this.

---

## 7. Provenance

Provenance is not an add-on in WUKONG; the source material is part of the output.

- Each **document** is a first-class object, referencing where the original text lives.
- Each **chunk** is a first-class object carrying its text and its exact span within its
  document.
- A structural relation connects each chunk to its document.
- A structural relation connects each extracted entity to *every* source context it was
  observed in — a document for document-level extraction, a chunk for chunk-level
  extraction.
- Each relationship records the chunk(s) it was extracted from.

Consequences: any assertion can be traced to verbatim supporting text, which is what makes
the output auditable rather than merely plausible. The number of mentions of an object is
available as a signal of salience or of extraction confidence. Because deduplication is
content-based, a widely discussed entity naturally accumulates many mentions while remaining
a single object. And because sources are part of the result, the output is directly usable
for grounded retrieval: a structural query returns not only facts but the passages that
justify them.

---

## 8. Execution Model

Extraction over a real corpus is a long-running, failure-prone, expensive process. WUKONG
treats it as such.

### 8.1 Work decomposition and durable state

Before any LLM call, the pipeline **materializes** the full set of pending work: every
(source context, type) pair implied by the knowledge model's source bindings becomes a
durable record
with an explicit state — pending, in progress, awaiting retry, completed, or failed. Calls
are then issued against this record set, and every outcome updates it.

Making the work plan explicit and durable is what makes everything else in this section
possible. The pipeline always knows exactly how much work remains; interrupting it loses at
most the calls in flight; resuming it re-derives nothing; adding a type to the knowledge model
materializes only the genuinely new work; and progress and cost can be reported against a
known denominator rather than estimated.

### 8.2 Failure handling

Failures are classified by what they imply about retrying:

- **Immediate retry** — the request was well-formed but the response was not usable (an
  unparseable or malformed reply). Retrying at once is likely to succeed. A bounded
  attempt counter prevents a pathological source from consuming the run.
- **Deferred retry** — a transient condition (rate limiting, provider unavailability, a
  source temporarily unreadable). The unit is set aside and retried on a subsequent pass,
  rather than hammering a service that is already struggling.
- **Critical failure** — a condition no retry can fix (invalid credentials, a
  misconfiguration). The run stops scheduling new work, allows in-flight work to finish and
  be persisted, and terminates. Work already completed is never discarded because of a
  later failure.

Units that exhaust their attempt budget are marked failed and reported, and the run
continues: one unextractable document does not sink a corpus.

Between passes, the pipeline **recovers** inconsistent state — units left in progress by an
abrupt termination are returned to the pending pool, deferred units are re-armed — so that
a resumed run starts from a coherent picture rather than an ambiguous one.

### 8.3 Two execution modes

The same work plan can be executed in two ways:

- **Interactive mode.** Requests are issued concurrently, up to a configured degree of
  parallelism, and results are consumed as they complete. Latency is low; the run finishes
  in one sitting; cost is at the standard rate. Concurrency is user-controlled because the
  binding constraint is the provider's rate limits, not local resources.
- **Asynchronous batch mode.** Requests are grouped and submitted to a provider's
  asynchronous batch interface, which offers substantially lower per-token pricing in
  exchange for a delayed, best-effort turnaround. The run then becomes a lifecycle problem:
  submitted groups are tracked, polled, and resolved when the provider finishes; results are
  matched back to their units; groups that fail, are cancelled, or never resolve within a
  bounded horizon are failed and their units returned to the pool. A user may submit work
  in one session and collect it in another.

Both modes share the same work plan, the same validation, the same identity logic and the
same state machine; they differ only in how requests reach the provider. This matters
practically: a user can prototype interactively on a subset and then run the full corpus in
batch mode without changing anything but a setting.

### 8.4 Idempotence and re-runs

Because identity is content-derived (§6) and work state is durable (§8.1), re-running the
pipeline is safe: completed work is skipped, re-extracted objects converge to the same
identities and are merged rather than duplicated, and only genuinely new work costs money.
The user may also deliberately reset a stage, in which case dependent downstream stages are
reset with it, since their results are no longer justified by their inputs.

### 8.5 Observability

Long, expensive runs need to be legible while they are running. The pipeline continuously
reports, per stage and context level: how many sources are pending, in progress, completed
and failed; call throughput and a smoothed completion-rate estimate; per-status timing;
token consumption broken down into fresh input, cached input, output and reasoning tokens;
the number of objects and mentions produced so far; and derived ratios such as objects per
source and mentions per object. Token accounting at this granularity is what makes the
cost of a configuration choice — a chunk size, an overlap, a reasoning effort, a decision to
group types — measurable rather than merely arguable.

---

## 9. Representation and Projection

The canonical result is representation-independent, and renderers are thin traversals over
it. Three aspects are worth stating conceptually.

**Why the separation is load-bearing.** Extraction is where all the cost and all the
uncertainty live: a run over a large corpus takes hours and consumes millions of tokens.
Rendering is a deterministic traversal that costs nothing by comparison. Coupling the two —
committing to a target format while extracting — would mean that wanting a second
representation implies paying the extraction cost twice. Keeping `K` canonical means a
corpus is read once and can be rendered arbitrarily many times, including into
representations that did not exist when it was read. This is the concrete content of R8, and
it is why the pipeline is described here in terms of a knowledge base rather than a graph.

**Projection.** The active subset of the knowledge model determines what is extracted, stored
and rendered. A relationship type is active only if it is selected *and* at least one of its
endpoints connects two active entity types, so projections cannot produce relations to
absent objects.

**Structural types in the output.** Documents and chunks appear in the rendered output
alongside domain entities, as do the structural relations linking chunks to documents and
extracted objects to their sources. The output is therefore self-contained: it can be
queried for domain facts, for the text supporting them, or for both at once, without
consulting the original corpus.

**Current renderers.** The implementation emits property-graph representations: a quad-model
format for a graph database, and bulk-import CSV files for a mainstream property-graph
engine. These are the most direct rendering of an entity–relation result, which is why they
came first. `[TODO: name the additional representations you intend to support, and say
whether the paper should describe them as planned or wait until they ship — see the note in
§14. Candidates worth considering, if they match your plans: relational tables, JSON/JSONL
record sets, RDF.]`

---

## 10. Discussion

### 10.1 Where the design pays off

**Schema-first as a precision instrument.** Every constraint the user can declare —
allowed values, patterns, obligatoriness, per-level instructions, source bindings — is both
a hint to the LLM and a filter on its output. The user tunes extraction quality by editing
a declarative artifact rather than by rewriting prompts, and the same artifact documents
what the resulting knowledge base means.

**Grounded relationships.** Presenting candidate entities and accepting only references to
them converts the hardest generation task in the pipeline into a selection task, removes
endpoint linking as a failure mode entirely, and keeps relationship extraction from
undoing entity normalization.

**Cost structure.** The dominant cost is the number and size of LLM calls. WUKONG attacks
both: grouping types per source amortizes the source text across all types; endpoint pruning
eliminates calls that provably cannot produce anything; document-level extraction reads a
bounded prefix rather than whole documents; non-extracted fields never enter a prompt; and
batch execution trades latency for a materially lower rate.

### 10.2 Costs of the design

**Configuration burden.** A good knowledge model requires domain understanding and some
iteration. This is the deliberate trade: WUKONG is aimed at users who know what knowledge
they want, not at exploratory schema discovery. `[TODO: report how long it took to author the
models used in the evaluation — this is a genuinely useful number for readers.]`

**Recall ceiling from strict validation.** Discarding objects that violate their declared
constraints costs recall whenever a constraint is too strict or the LLM's output is nearly
right. We consider this the correct default for output intended to be authoritative, but it
is a real trade, and a "repair" or "quarantine" tier is plausible future work. §11.5
measures the trade on a benchmark whose ontologies we did not author and could not adjust:
798 gold triples — 11% of that gold standard — were unreachable because both arguments had
been extracted but the entity pass assigned one of them a type the relation did not admit,
typically a sibling concept the same ontology also declares. Relaxing the endpoint
constraint on one such ontology raised its F1 from 0.09 to 0.23. This is the sharpest
evidence we have that strict validation is a cost borne by the *quality of the schema*
rather than by the extractor, and it is the strongest argument for a quarantine tier that
retains near-miss objects for review instead of discarding them.

**Dependence on schema quality.** Related but distinct: the system is only as good as the
model it is given, and §11.5 quantifies this more starkly than we expected. Adding a handful
of example surface forms per entity type — no change to the engine, the prompts or the
evaluator — moved benchmark F1 from 0.26 to 0.34, improved all ten ontologies, and cut
degenerate self-referential output by 85%. For users this is encouraging, since it means
effort spent on the model pays off directly; for the design it is a caution, since a
mechanically derived model can underperform badly for reasons that look like extraction
failures and are not.

**Identity brittleness for name-like keys.** Exact identity on normalized keys is
predictable but unforgiving. Where primary keys are natural-language names rather than
identifiers, unresolved variants remain distinct objects.

**Chunk-local reasoning.** Extraction sees one chunk (plus its document-level entities) at
a time. Facts that require combining evidence across distant parts of a document, or across
documents, are not directly recoverable. Overlap mitigates boundary effects but not
long-range dependencies.

### 10.3 Design decisions revisited

| Decision | Alternative | Why this choice |
| --- | --- | --- |
| Schema as input | Schema induced from text | Conformance, comparability across runs, usable output |
| Declared identity | Similarity clustering | Predictability, stability, locality, incrementality |
| Candidate-set relationships | Free triple generation + linking | No dangling endpoints; easier task; preserves normalization |
| Group types per source | One call per (source, type) | Source text sent once; types disambiguated jointly |
| Two context levels | Chunks only | Expresses document-defining facts that chunk-only pipelines cannot |
| Discard invalid output | Repair or coerce it | A wrong value is worse than a missing one |
| Durable per-unit work state | Stateless re-run | Resumability, incrementality, honest progress and cost accounting |
| Sources as first-class objects | External provenance store | Self-contained, auditable, directly usable for grounded retrieval |
| Canonical result, separate rendering | Extract directly into a target format | A corpus is read once and can be rendered many times, including into later formats |

---

## 11. Evaluation `[TODO — RQ2, RQ4, RQ7 outstanding]`

This section is part result, part proposal. §11.5 reports a comparative evaluation against
reference annotations on a public benchmark, which settles RQ1, RQ3 and RQ5 and provides a
first answer on RQ6. §11.4 reports descriptive measurements from one production-shaped run,
establishing cost and behaviour but not correctness. RQ2 (quality against human annotation
on our own corpora), RQ4 (deduplication) and RQ7 (stability across repeated runs) remain
unaddressed by either.

### 11.1 Corpora

- **Crime news (Spanish).** ~1,000 Chilean news articles reporting crime. Schema: six
  entity types (`Event`, `Person`, `Organization`, `Place`, `Weapon`, `Drug`) and five
  relationship types (`ParticipatesIn`, `OccurredIn`, `IsMemberOf`, `IsBasedIn`,
  `InvolvedIn`). This corpus exercises chunk-level extraction over short documents,
  multi-endpoint relationship types (`ParticipatesIn` accepts both `Person`→`Event` and
  `Organization`→`Event`), a mix of identity policies (endpoint+primary-key for
  `OccurredIn`, none for the rest), and — importantly for the discussion in §10.2 —
  *name-like and description-like primary keys*, the hardest case for exact identity. It is
  the corpus run under the current design (§11.4).
- **Legal / regulatory (Spanish).** Chilean urban-planning law: a general statute, its
  implementing ordinance, and the administrative circulars interpreting both. Schema:
  provision-like entity types plus a qualified cross-reference relationship. This corpus is
  the complement of the first: it exercises document-level entities (each document *is* a
  provision), cross-level endpoints, closed-vocabulary fields, and pattern-constrained
  identifiers where exact identity is at its strongest. `[TODO: this corpus has only been
  run under an earlier version of the tool; it must be re-run under the current design
  before any of its numbers are cited.]`

  Together the two corpora support the domain-independence claim (R7) and, more usefully,
  span the two extremes of the identity discussion — identifier-like keys versus
  name-like keys — which makes the trade-off in §6.5 measurable rather than asserted.
- **Text2KGBench, Wikidata-TekGen (English).** A public benchmark with reference
  annotations: 10 ontologies and 4,062 single-sentence documents, each with gold triples and
  a manually verified subset (939 sentences). Unlike the two corpora above it is not
  representative of our intended deployment — the documents are single sentences, the
  ontologies are Wikidata fragments we did not author, and the expected output is bare
  triples rather than a typed graph with properties (§11.5 discusses what that costs). Its
  value is precisely that it is not ours: it supplies reference annotations, published
  baselines, and an evaluation script written by someone else, which makes the conformance
  and hallucination claims of R1 and R3 falsifiable rather than self-reported. It is the
  corpus behind §11.5.

### 11.2 Research questions

- **RQ1 — Conformance.** What fraction of model output survives validation, and why is the
  rest rejected (missing required field, vocabulary violation, pattern violation,
  unnormalizable key, invalid endpoint)? This is directly measurable and is the clearest
  evidence for the schema-first argument.
- **RQ2 — Quality.** Precision and recall of entities and relationships against a
  human-annotated sample. `[TODO: define the annotation protocol and sample size.]`
- **RQ3 — Grounding.** Fraction of extracted relationships whose endpoints are valid — by
  construction 100% here, versus the measured linking failure rate of a
  generate-then-link baseline on the same corpus. This isolates the benefit of the
  candidate-set formulation.
- **RQ4 — Deduplication.** Objects before and after identity resolution; mentions per
  object; residual duplicate rate measured on a manually inspected sample; sensitivity to
  normalization strength.
- **RQ5 — Cost.** Tokens and monetary cost per document, per entity and per relationship,
  under each execution mode; savings attributable to endpoint pruning, to type grouping,
  and to batch execution, measured separately.
- **RQ6 — Ablations.** Effect on quality and cost of: chunk size and overlap; document-level
  extraction on/off; endpoint pruning on/off; type grouping on/off; per-level instructions
  on/off; declared patterns and vocabularies on/off; reasoning effort; model scale.
- **RQ7 — Stability.** Variance across repeated runs with identical inputs — an aspect
  rarely reported and directly relevant to whether a constructed KG can be trusted as
  infrastructure.

### 11.3 Baselines

- Free triple extraction per chunk followed by string-based endpoint linking (the common
  recipe), same model and corpus.
- Schema-aware prompting without candidate-set grounding, to isolate the contribution of
  §5.3 from that of §4.
- **Vicuna-13B and Alpaca-LoRA-13B, 2-shot** — the published baselines of Text2KGBench,
  which prompt an instruction-tuned model with the ontology and two train sentences
  retrieved by similarity. They are not configured by us: we re-scored their released
  outputs with the benchmark's own evaluator, reproducing the published aggregate exactly,
  so the comparison in §11.5 rests on their authors' numbers rather than our
  reimplementation. The comparison is imperfect — these are 13B open models and we run a
  proprietary model of unknown scale — so §11.5 reads the *hallucination and conformance*
  columns as the meaningful contrast and treats the F1 column as context.

### 11.4 Preliminary measurements

The following describe one complete run of the crime-news corpus under the current design,
executed in asynchronous batch mode. They are reported to make the cost argument of §10.1
concrete; they say nothing about extraction quality, which RQ2 must establish.

**Corpus and output.** 1,001 documents segmented into 1,140 chunks; 5,904 entities and
5,528 relationships extracted. All extraction was chunk-level: this schema declares no
document-level entity types, so the run exercises the chunk half of §5.2 only.

| Entity type | Count | | Relationship type | Count |
| --- | ---: | --- | --- | ---: |
| Person | 1,844 | | ParticipatesIn | 2,779 |
| Organization | 1,752 | | OccurredIn | 1,307 |
| Event | 1,387 | | IsMemberOf | 560 |
| Place | 739 | | IsBasedIn | 559 |
| Weapon | 128 | | InvolvedIn | 323 |
| Drug | 54 | | | |

**Call reduction from grouping and pruning.** The two mechanisms of §5.2 and §5.3 are
directly measurable here, because the work plan (§8.1) records the units that *would* have
been individual calls under a naive decomposition:

| | Naive (one call per unit) | Actual calls | Reduction |
| --- | ---: | ---: | ---: |
| Entity extraction | 6,840 (1,140 chunks × 6 types) | 1,140 | 6.0× |
| Relationship extraction | 5,700 (1,140 chunks × 5 types) | 938 | 6.1× |

For relationships, the reduction has two independent sources. Endpoint pruning eliminated
202 chunks entirely (17.7%) — no entity pair in them could satisfy any declared endpoint,
so no call was issued — and among the 938 chunks that survived, only 3,011 of a possible
4,690 (chunk, relationship type) pairs were viable, i.e. an average of 3.2 rather than 5
relationship types per request. Both savings compound with grouping.

**Deduplication.** 6,829 entity mentions collapsed to 5,904 distinct entities (1.16
mentions per entity, 13.5% of observations merged). Relationships collapsed at a rate of
1.00, i.e. not at all — unsurprising given that four of the five relationship types in this
schema declare no identity, so repetition is preserved by design. This is a useful negative
result to report honestly: the deduplication rate here is low *because the schema asked for
it to be low*, and the legal corpus, whose identifier-like keys recur across many documents,
should show the opposite. `[TODO: confirm once that corpus is re-run.]`

**Token consumption.** 4.68M input and 0.68M output tokens in total, or roughly 4,700 input
and 680 output tokens per document. Per call, entity extraction averaged 2,644 input / 408
output tokens and relationship extraction 1,773 input / 226 output — the relationship calls
being smaller despite carrying a candidate entity set, which supports the claim in §5.3 that
local identifiers are a cheap way to ground endpoints.

**Reliability.** 26 entity-extraction calls failed and were retried; every one of the 6,840
extraction units ultimately completed, and no unit exhausted its attempt budget. This is
evidence for the retry classification of §8.2, though a single successful run is weak
evidence; deliberate fault injection would be stronger. `[TODO: consider it.]`

**Caveats.** One run, one model, one corpus, no repetitions, and no ground truth. Reasoning
and cached-token counts were zero for this run, so the caching and reasoning-effort
dimensions of RQ5/RQ6 are untested. Before publication these numbers should be regenerated
under a fixed configuration, with repetitions, alongside the legal corpus.

### 11.5 Benchmark evaluation against reference annotations

We evaluate on Text2KGBench's Wikidata-TekGen suite (§11.1): 10 ontologies, 4,062 sentences,
scored by the benchmark authors' own `run_eval.py`, unmodified. Each ontology is compiled
into a knowledge model mechanically — concepts become entity types, relation labels become
relationship types, declared domains and ranges become endpoints — with no per-ontology
hand-tuning, and the extracted graph is converted back to triples through relationship
provenance. The full protocol, the harness and the per-sentence outputs are in
`paper/benchmark.md`; this section reports what it establishes for the design.

Two configurations are reported. **Zero-tuning** compiles each ontology exactly as published
and gives the model nothing beyond it. **Train-grounded** additionally seeds each entity type
with up to three example surface forms drawn from the benchmark's *train* split — the same
mechanism the pipeline already uses for date formats, generalized from one field convention
to entity types. Neither configuration reads the test or ground-truth files. The second is
the closer comparison to the baselines, which retrieve two train sentences *with their gold
triples* for every test sentence; three surface forms per type is considerably less
supervision than that.

| System | P | R | F1 | Ontology conf. | Subj. halluc. | Rel. halluc. | Obj. halluc. |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| WUKONG, zero-tuning | 0.28 | 0.26 | 0.26 | **1.00** | **0.00** | **0.00** | **0.01** |
| WUKONG, train-grounded | 0.36 | 0.35 | **0.34** | **1.00** | **0.00** | **0.00** | **0.01** |
| Vicuna-13B, 2-shot | 0.38 | 0.35 | 0.35 | 0.84 | 0.17 | 0.13 | 0.17 |
| Alpaca-LoRA-13B, 2-shot | 0.32 | 0.26 | 0.27 | 0.88 | 0.19 | 0.12 | 0.18 |

Conformance and relation hallucination are reported after correcting a benchmark defect:
three ontology files declare a relation label with a trailing space that their own ground
truth omits, so no output string can satisfy the conformance vocabulary and the F1 matcher
simultaneously. We emit the ground-truth form, which the evaluator then counts as a relation
hallucination; every one of the 117 affected triples is one of those three relations, and
measured conformance is 0.97. The baselines are depressed by the same defect.

**RQ1 — Conformance.** Every triple WUKONG produced in both configurations uses a relation
declared by its ontology: conformance 1.000 on all ten ontologies, against 0.84 and 0.88 for
the baselines. This is the schema-first argument at its strongest, and it is structural
rather than statistical — output that cannot be validated against the model never becomes
part of the graph (§5.2, §5.3).

**RQ3 — Grounding.** Subject hallucination is 0.00 and object hallucination 0.01, against
0.17–0.19 and 0.17–0.18 for the baselines. Endpoints selected from a candidate set of
already-extracted entities cannot name something absent from the text, which is the claim of
§5.3; the baselines generate endpoint strings freely and 17% of their subjects do not occur
in the sentence they were extracted from.

**RQ5 — Cost.** The full suite cost **$2.81** at `gpt-5.6-luna` rates — 6.78M input and
1.10M output tokens over 6,709 calls, 25 minutes at concurrency 15, ≈$0.00069 per sentence,
with no failed call. Cost is linear in corpus size and output-dominated: output is 48% of
spend from 14% of tokens, and reasoning accounts for 64% of billable output, which makes
reasoning effort rather than prompt size the lever if cost binds. Prompt caching was
ineffective here (0.3% hit rate) because every document is a distinct sentence.

**RQ6 — Ablation.** Train-grounded entity types raise F1 from 0.26 to 0.34, improving every
one of the ten ontologies, with precision rising alongside recall and conformance and
hallucination unchanged, at 5% additional cost. The same change reduces degenerate
self-referential triples from 192 to 29 and, without altering any endpoint declaration,
reduces by 38% the gold triples that were unreachable because the entity pass assigned an
argument a type the relation did not admit. A second arm, run on one ontology only, removes
the endpoint type constraint entirely and raises that ontology's F1 from 0.09 to 0.23,
confirming that those arguments were being extracted and the model was refusing the link.

**What the F1 column does and does not show.** Three properties of the benchmark bound it
for any faithful system, and they should be stated wherever the number is quoted. First,
only 65% of gold triples are reachable at all: 2,001 name a subject the sentence never
mentions — inherited from the source article rather than stated — and 96 use relations absent
from their own ontology. Second, 142 sentences have an empty gold standard and score zero
however a system answers, including when it correctly answers nothing. Together these cap
macro F1 at **0.644**. Third, and specific to us, a benchmark triple has no place for a
property: a literal that WUKONG would model as a field on an entity must instead become a
node with a relationship pointing at it, and recall on those objects is 0.199 against 0.382
for objects that are genuinely entities, across 24% of the gold standard. The baselines emit
undifferentiated `(s, r, o)` strings and pay nothing for that distinction. The honest reading
is that WUKONG reaches accuracy comparable to the baselines *while* satisfying constraints
they do not satisfy, not that it is the more accurate extractor on this benchmark.

**Caveats.** One model, one run per configuration, no repetitions, so RQ7 is untouched. The
benchmark's documents are single sentences, which exercises neither cross-chunk nor
document-level extraction (§5.2) and leaves deduplication almost inert — 4,062 sentences
yield 3,911 distinct documents and little entity merging — so RQ4 is untested here. The
second ablation arm covers one ontology rather than ten, for reasons of cost: removing the
endpoint constraint makes every relationship type applicable to every chunk and inflates the
relationship prompt roughly 29×. `[TODO: decide whether to run that arm on the full suite —
approximately $20 and five hours — or report it as the targeted probe it currently is.]`

---

## 12. Limitations and Future Work

- **Additional representations.** The separation of extraction from rendering (§9) is in
  place, but only property-graph renderers exist today. The claim that a corpus can be read
  once and rendered many ways is therefore architectural rather than demonstrated, and it
  stays that way until a second, structurally different representation ships. `[TODO: name
  the intended ones.]`
- **Field data types.** Only string-valued fields are supported today; numeric, boolean and
  temporal types would allow richer constraints and better downstream querying — and matter
  more once representations with real type systems are targeted.
- **Properties versus triples.** The model represents a literal as a field on an entity,
  which is the right shape for the data but does not survive conversion to a bare triple:
  the literal has to become a node with a relationship pointing at it, and it must therefore
  be recognized as an entity in its own right before any link can be made. §11.5 measures
  the cost on a benchmark that admits only triples — recall 0.199 on such objects against
  0.382 on genuine entities, over a quarter of that gold standard. This is a limitation of
  the interchange format rather than of the extraction, but it is a real obstacle to
  evaluating property-bearing models against triple-shaped reference data, and it will
  recur with any RDF-style target.
- **Schema quality as the dominant variable.** §11.5 shows a larger effect from grounding
  entity types with a few examples (F1 0.26 → 0.34) than we would have predicted from the
  design alone. Systematically studying what makes a knowledge model good — which of
  descriptions, examples, instructions and endpoint breadth actually carry the weight — is
  probably the highest-value follow-up, and would also inform the schema assistance below.
- **Approximate identity.** An optional similarity-based identity mode — fuzzy matching over
  normalized keys, blocking for tractability — would raise recall for name-like keys. The
  challenge is to add it without losing the predictability that motivated the current
  design; a promising direction is to *propose* merges and record them explicitly rather
  than performing them silently.
- **Cross-chunk and cross-document reasoning.** Facts requiring evidence from distant text
  regions are out of reach; a second pass over aggregated candidates is a natural extension.
- **Model-side confidence.** The pipeline records whether extraction succeeded but not how
  confident the LLM was; per-field confidence would enable thresholding and targeted
  human review.
- **Schema assistance.** Authoring a knowledge model is the main user cost. Semi-automatic
  model proposal from a corpus sample, refined by the user, would preserve the schema-first
  discipline while lowering its entry cost.
- **Beyond plain text.** Ingestion currently assumes plain text; documents with layout,
  tables or figures require conversion beforehand.
- **Iterative extraction.** Feeding the knowledge extracted so far back as context for
  subsequent extraction — so that later chunks benefit from what earlier ones established —
  is a natural but non-trivial extension, since it reintroduces order dependence into an
  otherwise order-independent process.

---

## 13. Conclusion

WUKONG treats knowledge extraction from text as a *specification* problem rather than a
generation problem. The user declares the knowledge they want — its types, fields,
constraints, sources, identity rules and merge rules — and the pipeline's job is to realize
that specification faithfully over a corpus, at a cost and with a reliability that make
large corpora practical. LLMs are used where they are irreplaceable, as readers of prose,
and constrained everywhere else: by generated request structure, by explicit candidate
sets, by post-hoc validation, and by deterministic identity. The result conforms to a
declared schema, deduplicates predictably, contains no ungrounded relations, carries its own
provenance, and can be built incrementally and resumably at a known cost — and because it is
kept in a canonical form independent of any output syntax, a corpus is read once and can be
rendered in whatever representation its consumer needs.

On a public benchmark with reference annotations these properties hold in the numbers and
not only in the design: every triple the system emitted conformed to the ontology it was
given, its relation arguments were almost never absent from the sentence they were read
from — subject hallucination 0.00 against 0.17 for 2-shot baselines on the same data — and
accuracy was comparable to those baselines at roughly $0.0007 per sentence. What the same
evaluation shows just as clearly is how much of the remaining gap belongs to the schema
rather than the extractor: grounding the entity types with a handful of examples per type,
and nothing else, moved F1 from 0.26 to 0.34 without disturbing either property. A knowledge
model is not merely a constraint the system must satisfy; it is the main thing the system's
quality depends on.

---

## References

`[TODO]`

---

## Appendix A — Worked example `[TODO]`

A compact end-to-end illustration on the legal corpus: a fragment of a knowledge model, the
resulting request skeleton at both context levels, a candidate set for relationship
extraction, and the resulting graph fragment with its provenance edges. Two to three
figures.

## Appendix B — Notation `[TODO]`

---

## 14. Open questions for the authors *(remove before submission)*

**Framing**

1. **Venue and length.** Which venue and format (conference short/full, journal, demo,
   resource paper)? This determines how much of §4 and §8 survives — the current draft is
   roughly 12–14 pages of a two-column format before figures.
2. **Framing.** Should the paper be positioned as (a) a *system* paper, (b) a *methodology*
   paper about schema-guided extraction, or (c) a *resource/application* paper centred on
   the legal knowledge graph? The draft currently sits between (a) and (b).
3. **Primary claim.** If a reader remembers one thing, should it be the declarative graph
   model, the candidate-set relationship extraction, the deterministic identity discipline,
   or the resumable/cost-aware execution model? I currently give the first three roughly
   equal weight and treat the fourth as supporting.

**Naming and generality** *(new — from the rename)*

4. **How hard to claim generality?** The draft now says extraction and representation are
   separate concerns, and that property graphs are one rendering among possible others. That
   is true of the design but only property-graph renderers exist. I have written it as
   architecture plus an explicit limitation (§12), never as a shipped capability. If a
   second representation lands before submission, §9 and §12 should be rewritten to claim it
   outright; if not, a reviewer may still object that the generality is untested. Which risk
   do you prefer to carry?
5. **Which representations are actually planned?** Naming them in §9 costs one sentence and
   makes the forward-looking framing concrete rather than vague. Relational tables? JSONL
   record sets? RDF? Something domain-specific?
6. **Knowledge model rename — pending in the code.** The paper now says *knowledge model*
   throughout, ahead of the rename in the tool, where the artifact is still `graph_model.json`.
   Two consequences. First, if the engine is released as an artifact alongside the paper
   (Q17), the rename should land first, or a reader following the paper into the repository
   will not find the term it uses. Second, if any figure or appendix listing shows a real
   model file, its filename and any internal keys must match whatever the code says at
   submission time — worth a final consistency pass once the code rename is done.

   Related: since "model" alone is now genuinely ambiguous between the knowledge model and
   the LLM, I have reserved *the LLM* for the language model and always qualified *the
   knowledge model*, including changing "model calls" to "LLM calls" throughout. Worth
   preserving in later edits.

**Content and accuracy**

7. **Reasoning effort.** Extraction currently runs at a low reasoning effort for both
   entities and relationships. Was this tuned empirically? If so it is worth reporting as an
   ablation (RQ6) rather than a constant.
8. **Document-level truncation.** Document-level extraction reads a bounded prefix of each
   document. Is the rationale purely cost, or also that the identifying information is
   front-loaded in your corpora? I have written both; tell me which to emphasize.
9. **Approximate identity as future work.** Now that fuzzy matching is definitively gone, do
   you still want it framed as a future direction (§12), or would you rather the paper
   defend exact identity as the deliberate and final position? The second framing is
   stronger rhetorically but commits you.
10. **Anything conceptually important I have missed?** I derived this from the code, the
   configuration and the existing docs. Ideas that live in your head rather than in the
   repository — rejected alternatives especially — are exactly what makes a design paper
   worth reading.

**Evaluation**

11. **What can we actually measure, and by when?** The evaluation plan in §11 is ambitious.
    Which subset is realistic: conformance and cost only (cheap, entirely automatic), or
    also a human-annotated quality study (expensive, much stronger)?
12. **Do we have, or can we build, a gold-standard sample?** Even 100–200 annotated chunks
    would support RQ2 and materially strengthen the paper.
13. **Re-running the legal corpus.** §11 currently leans on the crime corpus alone for real
    numbers. Re-running the urban-planning corpus under the current design would give the
    paper its document-level and cross-level evidence, and would test exact identity where
    it should perform best. Is that feasible, and roughly what would it cost?
14. **Baseline effort.** Are you willing to implement the generate-then-link baseline? It is
    the single most persuasive comparison available for the candidate-set contribution
    (RQ3), and it is cheap to build since the infrastructure already exists.
15. **Corpora we may publish about.** Are both the crime-news and urban-planning corpora
    usable in a publication (licensing, redistribution of the source articles)? If the news
    corpus cannot be released, the paper can still report over it but the artifact story in
    Q17 changes.

**Attribution**

16. **Author list, affiliations, funding and acknowledgements.**
17. **Artifact availability.** Will the engine, the example knowledge models, or a produced
    graph be released alongside the paper? This affects both venue choice and how §9 and
    §11 should be written.
