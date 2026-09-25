"""Generate WUKONG workspaces and data directories from Text2KGBench ontologies.

For each requested ontology, this script produces:
    - <workspace>/knowledge_model.json: the ontology mapped to a WUKONG knowledge model
    - <workspace>/document_collections.json: a single "sentences" collection
    - <workspace>/text2kg_mapping.json: WUKONG type names -> benchmark labels
    - <data>/sentences/<test_id>.txt: one test sentence per document

The mapping file is what lets `text2kg_export.py` translate extracted knowledge
back into benchmark triples, since WUKONG type names cannot contain the spaces
and underscores used by the benchmark relation labels.

Example:
    python paper/benchmark/text2kg_setup.py \
        --benchmark ../benchmarks/Text2KGBench \
        --onto 2_music \
        --workspace-root workspaces --data-root data/tekgen
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# The 10 ontologies of the Wikidata-TekGen dataset, in benchmark order
ONTOLOGIES = (
    '1_movie',
    '2_music',
    '3_sport',
    '4_book',
    '5_military',
    '6_computer',
    '7_space',
    '8_politics',
    '9_nature',
    '10_culture',
)

# Entity type holding literal objects of relations with no ontology range
VALUE_TYPE = 'Value'

# Separator between the values of a multi-valued property. The exporter splits
# on it, so the two must stay in sync.
PROPERTY_VALUE_SEPARATOR = '; '

# Names the engine reserves for its own special types
RESERVED_ENTITY_NAMES = frozenset({'document', 'chunk'})
RESERVED_RELATIONSHIP_NAMES = frozenset({'chunkof', 'extractedfrom'})

# Instruction applied to every primary key field, to keep extracted surface
# forms comparable against the benchmark ground truth
SURFACE_FORM_INSTRUCTION = (
    'Use the exact surface form as it appears in the source text, '
    'without adding, removing, reordering or normalizing any words.'
)

# Objects written as "<DD> <Month> <YYYY>", the Wikidata date convention the
# benchmark inherits from TekGen
DATE_OBJECT_PATTERN = re.compile(r'^\d{2} [A-Za-z]+ \d{4}$')

# Convention the few-shot baselines picked up from their retrieved train
# sentences, restated here so it is available from the ontology alone
DATE_CONVENTION_INSTRUCTION = (
    'Dates must be written in the format "<DD> <Month> <YYYY>". '
    'When the source text states only a year, use "01 January <YYYY>".'
)

# Instruction applied to every property field compiled from a range-less relation.
# The splitting rule must be stated as overriding the verbatim rule: worded as
# two independent rules, the LLM copies an enumeration ("A, B and C") verbatim
# as one value.
PROPERTY_INSTRUCTION = (
    'Only fill this field when the source text explicitly states it; otherwise leave it empty. '
    'Each value must use the exact surface form as it appears in the source text, without '
    'normalizing its words. When the text states several values, for instance as an enumeration, '
    f'extract each value on its own and separate them with "{PROPERTY_VALUE_SEPARATOR.strip()}": '
    '"written for violin, cello and piano" gives "violin; cello; piano".'
)


def pascal_case(label: str) -> str:
    """Convert an ontology label into a valid WUKONG type name.

    Type names must match `^[A-Z][a-zA-Z0-9]{0,63}$`, so every non-alphanumeric
    separator is dropped and each remaining word is capitalized. A name that
    would start with a digit is prefixed with "X", and names are truncated to 64
    characters.

    Args:
        label: Ontology concept or relation label.

    Returns:
        The PascalCase type name.

    Raises:
        ValueError: If the label contains no alphanumeric characters.
    """
    parts = [p for p in re.split(r'[^0-9A-Za-z]+', label.strip()) if p]
    if not parts:
        raise ValueError(f'Label produces an empty type name: "{label}"')
    name = ''.join(p[:1].upper() + p[1:] for p in parts)

    # A name starting with a digit cannot satisfy the engine's pattern
    if not name[0].isalpha():
        name = f'X{name}'

    return name[:64]


def snake_case(label: str) -> str:
    """Convert an ontology relation label into a valid WUKONG field name.

    Field names must match `^[a-z][a-z0-9_]{0,63}$`, so a name that would start
    with a digit is prefixed with "x_", and names are truncated to 64 characters.

    Args:
        label: Ontology relation label.

    Returns:
        The snake_case field name.

    Raises:
        ValueError: If the label contains no alphanumeric characters.
    """
    parts = [p.lower() for p in re.split(r'[^0-9A-Za-z]+', label.strip()) if p]
    if not parts:
        raise ValueError(f'Label produces an empty field name: "{label}"')
    name = '_'.join(parts)
    if not name[0].isalpha():
        name = f'x_{name}'
    return name[:64]


def benchmark_relation(label: str) -> str:
    """Convert an ontology relation label into the string the evaluator expects.

    Args:
        label: Ontology relation label.

    Returns:
        The stripped label with spaces replaced by underscores.
    """
    return label.strip().replace(' ', '_')


class OntologyAdapter:
    """Maps a single Text2KGBench ontology onto a WUKONG knowledge model."""

    def __init__(
        self,
        ontology: dict[str, Any],
        collection: str,
        date_examples: dict[str, list[str]] | None = None,
        entity_examples: dict[str, list[str]] | None = None,
        *,
        permissive_endpoints: bool = False,
        literal_properties: bool = False,
    ) -> None:
        """Initialize the adapter and resolve all type names up front.

        Args:
            ontology: The parsed Text2KGBench ontology definition.
            collection: Name of the document collection holding the sentences.
            date_examples: Relation label -> example date objects observed in the
                train split. Empty or None leaves the date convention unstated.
            entity_examples: Concept qid -> example surface forms observed in the
                train split, for the ablation that gives entity types examples.
            permissive_endpoints: Accept any pair of entity types on every
                relationship, instead of only the declared domain and range.
            literal_properties: Compile relations with no usable range concept
                into properties of their domain entity type instead of
                relationships to a `Value` entity, and give relations with no
                usable domain concept a generic subject type.
        """
        self._ontology = ontology
        self._collection = collection
        self._date_examples = date_examples or {}
        self._entity_examples = entity_examples or {}
        self._permissive_endpoints = permissive_endpoints
        self._literal_properties = literal_properties
        self._title = ontology.get('title', ontology['id']).strip()

        # qid -> concept label, for every concept declared by the ontology
        self._concepts: dict[str, str] = {c['qid']: c['label'].strip() for c in ontology['concepts']}

        self._entity_names = self._resolve_entity_names()
        self._subject_names = self._resolve_subject_names()
        self._relationship_names = self._resolve_relationship_names()
        self._property_names = self._resolve_property_names()

    # Name resolution

    def _referenced_qids(self) -> set[str]:
        """Collect the concept qids actually used as a relation domain or range.

        A qid that no concept declares carries no label we could describe to the
        LLM, so it is treated exactly like an empty range and falls back to Value.

        Returns:
            The declared concept qids referenced by at least one relation.
        """
        qids: set[str] = set()
        for relation in self._ontology['relations']:
            for key in ('domain', 'range'):
                qid = relation.get(key, '').strip()
                if qid and qid in self._concepts:
                    qids.add(qid)
        return qids

    def _resolve_entity_names(self) -> dict[str, str]:
        """Build the qid -> WUKONG entity type name mapping.

        Returns:
            Mapping from each referenced concept qid to a unique entity type name that avoids reserved names and
            `Value`.
        """
        names: dict[str, str] = {}
        taken: set[str] = {VALUE_TYPE}
        for qid in sorted(self._referenced_qids()):
            name = pascal_case(self._concepts[qid])
            if name.lower() in RESERVED_ENTITY_NAMES:
                name = f'{name}Concept'

            # Distinct concepts may collapse to the same name, so disambiguate
            if name in taken:
                name = f'{name}{qid}'
            taken.add(name)
            names[qid] = name
        return names

    def _is_property(self, relation: dict[str, Any]) -> bool:
        """Return whether a relation declaration is compiled into a property of its domain.

        Args:
            relation: Relation declaration from the ontology.

        Returns:
            True if literal properties are enabled and the relation's range is not a declared entity type, False
            otherwise.
        """
        return self._literal_properties and relation.get('range', '').strip() not in self._entity_names

    def _resolve_subject_names(self) -> dict[str, str]:
        """Build the undeclared domain qid -> generic subject type name mapping.

        Only used with literal properties: a property needs an entity type to
        live on, and an undeclared domain qid would otherwise fall back to Value.

        Returns:
            Mapping from each undeclared domain qid (possibly empty) to a unique subject type name, or an empty
            mapping when literal properties are disabled.
        """
        if not self._literal_properties:
            return {}
        names: dict[str, str] = {}
        taken = set(self._entity_names.values())
        for relation in self._ontology['relations']:
            qid = relation.get('domain', '').strip()
            if qid in self._entity_names or qid in names:
                continue
            name = f'Subject{pascal_case(qid)}' if qid else 'Subject'
            if name in taken:
                name = f'{name}Entity'
            taken.add(name)
            names[qid] = name
        return names

    def _resolve_property_names(self) -> dict[str, dict[str, str]]:
        """Build the entity type name -> {field name: benchmark relation label} mapping.

        Returns:
            Mapping from each domain entity type name to its property fields, keyed by field name. A field name
            that clashes with `name` or another field gets the relation pid appended.
        """
        properties: dict[str, dict[str, str]] = {}
        for relation in self._ontology['relations']:
            if not self._is_property(relation):
                continue
            label = relation['label'].strip()
            fields = properties.setdefault(self._endpoint_type(relation.get('domain', '')), {})
            if label in fields.values():
                continue

            # `name` is the primary key field of every entity type
            name = snake_case(label)
            if name == 'name' or name in fields:
                name = f'{name}_{relation["pid"].lower()}'
            fields[name] = label
        return properties

    def _resolve_relationship_names(self) -> dict[str, str]:
        """Build the benchmark relation label -> WUKONG relationship type name mapping.

        Relations sharing a label (same pid, different range) are a single
        relationship type carrying several endpoint pairs.

        Returns:
            Mapping from each non-property relation label to a unique relationship type name.
        """
        names: dict[str, str] = {}
        taken: set[str] = set()
        for relation in self._ontology['relations']:
            if self._is_property(relation):
                continue
            label = relation['label'].strip()
            if label in names:
                continue
            name = pascal_case(label)
            if name.lower() in RESERVED_RELATIONSHIP_NAMES:
                name = f'{name}Relation'
            if name in taken:
                name = f'{name}{relation["pid"]}'
            taken.add(name)
            names[label] = name
        return names

    def _endpoint_type(self, qid: str) -> str:
        """Resolve a domain/range qid to the entity type name representing it.

        Args:
            qid: Domain or range qid from a relation declaration, possibly empty.

        Returns:
            The declared entity type name, else the generic subject type name, else `Value`.
        """
        qid = qid.strip()
        return self._entity_names.get(qid) or self._subject_names.get(qid, VALUE_TYPE)

    # Knowledge model construction

    def _value_instruction(self) -> str | None:
        """Describe which relations need a Value object, to bound its extraction.

        Without this the type is unbounded and the LLM extracts every noun phrase
        in the sentence.

        Returns:
            The instruction listing the relations whose object falls back to Value, or None if there are none.
        """
        labels = sorted(
            {
                relation['label'].strip()
                for relation in self._ontology['relations']
                if self._endpoint_type(relation.get('range', '')) == VALUE_TYPE
            },
        )
        if not labels:
            return None
        quoted = ', '.join(f'"{label}"' for label in labels)
        return (
            'Only extract a value when it is the object of one of the following relations: '
            f'{quoted}. Do not extract any other terms from the source text.'
        )

    def _entity_type(
        self,
        name: str,
        description: str,
        instructions: str | None,
        examples: list[str] | None = None,
        *,
        dates: bool = False,
    ) -> dict[str, Any]:
        """Build a single entity type definition.

        Args:
            name: Entity type name, used in the primary key field description.
            description: Description of the entity type.
            instructions: Type-level extraction instructions, or None to omit them.
            examples: Example surface forms for the `name` primary key field. If None or empty, no examples are
                given and the date convention is not added.
            dates: Whether the examples include dates, which appends the date convention to the field
                instructions.

        Returns:
            The entity type definition, with `name` as its primary key field.
        """
        definition: dict[str, Any] = {'description': description}
        if instructions is not None:
            definition['instructions'] = instructions

        field: dict[str, Any] = {
            'data_type': 'string',
            'description': f'The text that identifies this {name} in the source text.',
            'instructions': SURFACE_FORM_INSTRUCTION,
            'required': True,
            'retrieval_mode': 'extract',
        }

        # The date convention overrides the verbatim rule for date objects only
        if examples:
            if dates:
                field['instructions'] = f'{SURFACE_FORM_INSTRUCTION} {DATE_CONVENTION_INSTRUCTION}'
            field['examples'] = examples

        definition.update(
            {
                'primary_key': 'name',
                'deduplication': 'primary_key',
                'fields': {'name': field},
                'document_collections': {'chunk': [self._collection]},
            },
        )
        return definition

    def _date_target_examples(self) -> dict[str, list[str]]:
        """Map entity type names to date examples, for types that receive date objects.

        Returns:
            Mapping from each range entity type name of a non-property relation with date examples to the
            deduplicated examples of all such relations.
        """
        targets: dict[str, list[str]] = {}
        for relation in self._ontology['relations']:
            examples = self._date_examples.get(relation['label'].strip())
            if not examples or self._is_property(relation):
                continue
            target = self._endpoint_type(relation.get('range', ''))
            for example in examples:
                if example not in targets.setdefault(target, []):
                    targets[target].append(example)
        return targets

    def _property_field(self, entity_type: str, label: str) -> dict[str, Any]:
        """Build the property field holding the objects of one range-less relation.

        Args:
            entity_type: Name of the domain entity type the property lives on.
            label: Benchmark relation label the property represents.

        Returns:
            The property field definition, with date examples (and the date convention) first, followed by
            entity examples keyed by the relation.
        """
        field: dict[str, Any] = {
            'data_type': 'string',
            'description': f'The "{label}" of this {entity_type}, as defined by the {self._title}.',
            'instructions': PROPERTY_INSTRUCTION,
            'required': False,
            'retrieval_mode': 'extract',
        }

        # Date examples come first: they carry the format convention
        dates = self._date_examples.get(label, [])
        examples = list(dates)
        for example in self._entity_examples.get(f'rel:{label}', []):
            if example not in examples:
                examples.append(example)
        if dates:
            field['instructions'] = f'{PROPERTY_INSTRUCTION} {DATE_CONVENTION_INSTRUCTION}'
        if examples:
            field['examples'] = examples
        return field

    def _add_property_fields(self, entity_types: dict[str, Any]) -> None:
        """Attach every range-less relation as a property of its domain entity type.

        Args:
            entity_types: Entity type definitions to update in place; must include every domain type that has
                properties.
        """
        for entity_type, fields in self._property_names.items():
            for field_name, label in fields.items():
                entity_types[entity_type]['fields'][field_name] = self._property_field(entity_type, label)

    def _build_subject_types(self) -> dict[str, Any]:
        """Build a generic entity type for every undeclared relation domain.

        The ontology gives no label for such a domain, so the type is described
        by the relations it is the subject of, which is all the ontology says.

        Returns:
            Mapping from each subject type name to its entity type definition.
        """
        entity_types: dict[str, Any] = {}
        for qid, name in self._subject_names.items():
            labels = sorted(
                {
                    relation['label'].strip()
                    for relation in self._ontology['relations']
                    if relation.get('domain', '').strip() == qid
                },
            )
            quoted = ', '.join(f'"{label}"' for label in labels)
            entity_types[name] = self._entity_type(
                name,
                f'An entity that is the subject of the {quoted} relation(s) of the {self._title}, '
                'whose type the ontology does not name.',
                None,
                self._entity_examples.get(qid) or None,
            )
        return entity_types

    def _build_entity_types(self) -> dict[str, Any]:
        """Build every entity type required by the ontology's relations.

        With literal properties, this adds the generic subject types and the property fields instead of the
        `Value` type.

        Returns:
            Mapping from entity type name to its definition.
        """
        date_examples = self._date_target_examples()
        entity_types: dict[str, Any] = {}
        for qid, name in self._entity_names.items():
            label = self._concepts[qid]

            # Date examples come first: they carry the format convention, which
            # the field instruction refers to
            examples = list(date_examples.get(name) or [])
            for example in self._entity_examples.get(qid, []):
                if example not in examples:
                    examples.append(example)
            entity_types[name] = self._entity_type(
                name,
                f'An entity of the type "{label}", as defined by the {self._title}.',
                None,
                examples or None,
                dates=bool(date_examples.get(name)),
            )

        if self._literal_properties:
            entity_types.update(self._build_subject_types())
            self._add_property_fields(entity_types)
            return entity_types

        # Value only exists when some relation has no usable range concept
        value_instruction = self._value_instruction()
        if value_instruction is not None:
            value_dates = date_examples.get(VALUE_TYPE)
            examples = list(value_dates or [])

            # Value has no qid, so its examples are keyed by the relations that
            # fall back to it
            for relation in self._ontology['relations']:
                if self._endpoint_type(relation.get('range', '')) != VALUE_TYPE:
                    continue
                for example in self._entity_examples.get(f'rel:{relation["label"].strip()}', []):
                    if example not in examples:
                        examples.append(example)
            entity_types[VALUE_TYPE] = self._entity_type(
                VALUE_TYPE,
                'A literal value mentioned in the source text, such as a date, a quantity, a name '
                'or a descriptive term, that is the object of a relation with no specific type.',
                value_instruction,
                examples or None,
                dates=bool(value_dates),
            )
        return entity_types

    def _all_endpoint_pairs(self, entity_types: dict[str, Any]) -> dict[str, Any]:
        """Build endpoints accepting every ordered pair of entity types.

        Used by the permissive ablation. The declared domain and range become
        documentation rather than a constraint, because a sentence often mentions
        an argument whose most natural type is a sibling of the declared one.

        Args:
            entity_types: Entity type definitions, keyed by name.

        Returns:
            Endpoints mapping every source type to every target type, each with a single chunk-level rule.
        """
        rule = {'source_context_levels': 'chunk', 'target_context_levels': 'chunk'}
        return {source: {target: [rule] for target in entity_types} for source in entity_types}

    def _build_relationship_types(self, entity_types: dict[str, Any]) -> dict[str, Any]:
        """Build one relationship type per distinct ontology relation label.

        Args:
            entity_types: Entity type definitions, used for the permissive endpoints.

        Returns:
            Mapping from relationship type name to its definition, skipping relations compiled into properties.
        """
        relationship_types: dict[str, Any] = {}
        for relation in self._ontology['relations']:
            if self._is_property(relation):
                continue
            label = relation['label'].strip()
            name = self._relationship_names[label]
            source = self._endpoint_type(relation.get('domain', ''))
            target = self._endpoint_type(relation.get('range', ''))
            rule = {'source_context_levels': 'chunk', 'target_context_levels': 'chunk'}

            if name not in relationship_types:
                relationship_types[name] = {
                    'description': f'The "{label}" relation, as defined by the {self._title}.',
                    'endpoints': self._all_endpoint_pairs(entity_types) if self._permissive_endpoints else {},
                    'deduplication': 'endpoints',
                }
            if self._permissive_endpoints:
                continue

            endpoints = relationship_types[name]['endpoints']
            endpoints.setdefault(source, {}).setdefault(target, [])
            if rule not in endpoints[source][target]:
                endpoints[source][target].append(rule)
        return relationship_types

    def knowledge_model(self) -> dict[str, Any]:
        """Build the complete WUKONG knowledge model for this ontology.

        Returns:
            The knowledge model document, with every entity and relationship type enabled in the projection.
        """
        entity_types = self._build_entity_types()
        relationship_types = self._build_relationship_types(entity_types)
        return {
            'extraction_config': {
                'llm': {
                    'domain': f'{self._title}. Single sentences extracted from Wikipedia articles.',
                    'language': 'en',
                },
                'projection': {
                    'enabled_entities': list(entity_types),
                    'enabled_relationships': list(relationship_types),
                },
            },
            'entity_types': entity_types,
            'relationship_types': relationship_types,
        }

    def mapping(self) -> dict[str, Any]:
        """Build the reverse mapping used to export benchmark triples.

        Returns:
            The mapping from WUKONG entity, relationship and (with literal properties) subject and property
            names back to benchmark labels.
        """
        mapping: dict[str, Any] = {
            'ontology_id': self._ontology['id'],
            'title': self._title,
            'value_entity_type': None if self._literal_properties else VALUE_TYPE,
            'entity_types': {name: self._concepts[qid] for qid, name in self._entity_names.items()},
            # The evaluator compares relation strings with spaces replaced by underscores
            'relationship_types': {
                name: benchmark_relation(label) for label, name in self._relationship_names.items()
            },
        }
        if self._literal_properties:
            mapping['subject_types'] = {name: qid for qid, name in self._subject_names.items()}
            mapping['property_separator'] = PROPERTY_VALUE_SEPARATOR
            mapping['properties'] = {
                entity_type: {field: benchmark_relation(label) for field, label in fields.items()}
                for entity_type, fields in self._property_names.items()
            }
        return mapping


def scan_train_date_examples(train_path: Path, limit: int = 2) -> dict[str, list[str]]:
    """Collect date-formatted objects per relation from the train split.

    Train records are flat, carrying one triple per line as sub_label/rel_label/
    obj_label. Only the train split is read, never test or ground truth,
    mirroring the information the few-shot baselines obtained from their
    retrieved examples.

    Args:
        train_path: Path to the ontology's train split JSONL file.
        limit: Maximum number of distinct examples kept per relation.

    Returns:
        Mapping from relation label to its "<DD> <Month> <YYYY>" example objects, or an empty mapping if the
        train file doesn't exist.
    """
    examples: dict[str, list[str]] = {}
    if not train_path.exists():
        return examples

    with train_path.open(encoding='utf-8') as train_file:
        for line in train_file:
            if not line.strip():
                continue
            record = json.loads(line)
            obj = (record.get('obj_label') or '').strip()
            if not DATE_OBJECT_PATTERN.match(obj):
                continue
            found = examples.setdefault((record.get('rel_label') or '').strip(), [])
            if obj not in found and len(found) < limit:
                found.append(obj)
    return examples


def scan_train_entity_examples(
    train_path: Path,
    ontology: dict[str, Any],
    limit: int = 3,
    *,
    undeclared_subjects: bool = False,
) -> dict[str, list[str]]:
    """Collect example surface forms per concept from the train split.

    A train record carries one triple as sub_label/rel_label/obj_label, so the
    subject illustrates the relation's domain concept and the object its range.
    Only the train split is read, never test or ground truth, which mirrors the
    information the few-shot baselines obtained from their retrieved examples --
    and gives entity types the same kind of grounding that dates already get.

    With `undeclared_subjects`, subjects of relations whose domain qid is not a
    declared concept are also collected, keyed by that qid, for the generic
    subject types that literal properties compile such domains into.

    Args:
        train_path: Path to the ontology's train split JSONL file.
        ontology: Parsed ontology definition, giving each relation's domain and range.
        limit: Maximum number of distinct examples kept per key.
        undeclared_subjects: Whether to also collect subjects of relations whose domain qid is undeclared.

    Returns:
        Mapping from key to non-date example surface forms, where the key is a declared concept qid, an
        undeclared domain qid, or "rel:<label>" for objects of relations with no declared range. Empty if the
        train file doesn't exist.
    """
    examples: dict[str, list[str]] = {}
    if not train_path.exists():
        return examples

    endpoints: dict[str, tuple[str, str]] = {
        relation['label'].strip(): (relation.get('domain', '').strip(), relation.get('range', '').strip())
        for relation in ontology['relations']
    }
    with train_path.open(encoding='utf-8') as train_file:
        for line in train_file:
            if not line.strip():
                continue
            record = json.loads(line)
            pair = endpoints.get((record.get('rel_label') or '').strip())
            if pair is None:
                continue
            relation = (record.get('rel_label') or '').strip()
            declared = {concept['qid'] for concept in ontology['concepts']}
            for index, (qid, label) in enumerate(
                zip(pair, (record.get('sub_label'), record.get('obj_label')), strict=True),
            ):
                value = (label or '').strip()

                # A date example is already supplied through the date convention
                if not value or DATE_OBJECT_PATTERN.match(value):
                    continue

                # An object with no usable range concept lands on the untyped
                # Value type, whose examples are keyed by relation instead
                if qid in declared:
                    key = qid
                elif index == 1:
                    key = f'rel:{relation}'
                else:
                    key = qid if undeclared_subjects else ''
                if not key:
                    continue
                found = examples.setdefault(key, [])
                if value not in found and len(found) < limit:
                    found.append(value)
    return examples


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write a JSON document with a trailing newline.

    Args:
        path: Output file; its parent directories are created if missing.
        payload: Document to write.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=4, ensure_ascii=False) + '\n', encoding='utf-8')


def write_sentences(test_path: Path, sentences_dir: Path) -> int:
    """Write one document per test sentence, named after its benchmark id.

    Args:
        test_path: Path to the ontology's test split JSONL file.
        sentences_dir: Directory to write the `<id>.txt` documents into; created if missing.

    Returns:
        The number of sentences written.
    """
    sentences_dir.mkdir(parents=True, exist_ok=True)
    count = 0
    with test_path.open(encoding='utf-8') as test_file:
        for line in test_file:
            if not line.strip():
                continue
            case = json.loads(line)
            (sentences_dir / f'{case["id"]}.txt').write_text(case['sent'].strip() + '\n', encoding='utf-8')
            count += 1
    return count


def setup_ontology(onto: str, args: argparse.Namespace) -> dict[str, Any]:
    """Generate the workspace and data directory for a single ontology.

    Args:
        onto: Ontology name, e.g. "2_music".
        args: Parsed command line arguments.

    Returns:
        A summary of the generated ontology: its name, workspace and data paths, and the counts of sentences,
        entity types, relationship types and relations with date examples.
    """
    dataset = Path(args.benchmark).resolve() / 'data' / args.dataset
    ontology = json.loads((dataset / 'ontologies' / f'{onto}_ontology.json').read_text(encoding='utf-8'))

    train_path = dataset / 'train' / f'ont_{onto}_train.jsonl'
    date_examples = {} if args.no_date_convention else scan_train_date_examples(train_path)
    entity_examples = (
        scan_train_entity_examples(train_path, ontology, undeclared_subjects=args.literal_properties)
        if args.entity_examples
        else {}
    )
    adapter = OntologyAdapter(
        ontology,
        collection=args.collection,
        date_examples=date_examples,
        entity_examples=entity_examples,
        permissive_endpoints=args.permissive_endpoints,
        literal_properties=args.literal_properties,
    )
    workspace = Path(args.workspace_root) / f'{args.prefix}{onto}'
    data_dir = Path(args.data_root) / onto

    write_json(workspace / 'knowledge_model.json', adapter.knowledge_model())
    write_json(
        workspace / 'document_collections.json',
        {'collections': {args.collection: {'sources': [{'root': args.collection, 'mode': 'directory'}]}}},
    )
    write_json(workspace / 'text2kg_mapping.json', adapter.mapping())

    sentences = write_sentences(dataset / 'test' / f'ont_{onto}_test.jsonl', data_dir / args.collection)

    model = adapter.knowledge_model()
    return {
        'onto': onto,
        'workspace': str(workspace),
        'data_dir': str(data_dir),
        'sentences': sentences,
        'entity_types': len(model['entity_types']),
        'relationship_types': len(model['relationship_types']),
        'date_relations': len(date_examples),
    }


def build_parser() -> argparse.ArgumentParser:
    """Build the command line parser.

    Returns:
        The argument parser for this script.
    """
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--benchmark', type=Path, required=True, help='Path to the Text2KGBench repository')
    parser.add_argument('--dataset', default='wikidata_tekgen', help='Benchmark dataset directory name')
    parser.add_argument(
        '--onto',
        action='append',
        choices=[*ONTOLOGIES],
        help='Ontology to set up (repeatable, defaults to all 10)',
    )
    parser.add_argument('--workspace-root', type=Path, default=Path('paper/benchmark/workspaces'))
    parser.add_argument('--data-root', type=Path, default=Path('paper/benchmark/data'))
    parser.add_argument('--prefix', default='tekgen_', help='Workspace directory name prefix')
    parser.add_argument('--collection', default='sentences', help='Document collection name')
    parser.add_argument(
        '--no-date-convention',
        action='store_true',
        help="Omit the train-derived date format convention (ablation arm)",
    )
    parser.add_argument(
        '--permissive-endpoints',
        action='store_true',
        help='Accept any pair of entity types on every relationship (ablation arm)',
    )
    parser.add_argument(
        '--entity-examples',
        action='store_true',
        help='Seed entity types with train-derived example surface forms (ablation arm)',
    )
    parser.add_argument(
        '--literal-properties',
        action='store_true',
        help='Compile range-less relations into properties of their domain entity type (adjusted run)',
    )
    return parser


def main() -> int:
    """Generate workspaces and data directories for the requested ontologies.

    Returns:
        The process exit code, always 0.
    """
    args = build_parser().parse_args()
    for onto in args.onto or ONTOLOGIES:
        result = setup_ontology(onto, args)
        print(
            f'{result["onto"]:12s} '
            f'entities={result["entity_types"]:2d} '
            f'relations={result["relationship_types"]:2d} '
            f'sentences={result["sentences"]:4d} '
            f'date_rels={result["date_relations"]:d} -> {result["workspace"]}',
        )
    return 0


if __name__ == '__main__':
    sys.exit(main())
