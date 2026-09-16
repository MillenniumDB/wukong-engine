"""Generate WUKONG workspaces and data directories from Text2KGBench ontologies.

For each requested ontology, this script produces:
    - <workspace>/graph_model.json: the ontology mapped to a WUKONG graph model
    - <workspace>/document_collections.json: a single "sentences" collection
    - <workspace>/text2kg_mapping.json: WUKONG type names -> benchmark labels
    - <data>/sentences/<test_id>.txt: one test sentence per document

The mapping file is what lets `text2kg_export.py` translate an extracted graph
back into benchmark triples, since WUKONG type names cannot contain the spaces
and underscores used by the benchmark relation labels.

Example:
    python scripts/benchmark/text2kg_setup.py \
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


def pascal_case(label: str) -> str:
    """Convert an ontology label into a valid WUKONG type name.

    Type names must match `^[A-Z][a-zA-Z0-9]{0,63}$`, so every non-alphanumeric
    separator is dropped and each remaining word is capitalized.
    """
    parts = [p for p in re.split(r'[^0-9A-Za-z]+', label.strip()) if p]
    if not parts:
        raise ValueError(f'Label produces an empty type name: "{label}"')
    name = ''.join(p[:1].upper() + p[1:] for p in parts)

    # A name starting with a digit cannot satisfy the engine's pattern
    if not name[0].isalpha():
        name = f'X{name}'

    return name[:64]


def benchmark_relation(label: str) -> str:
    """Convert an ontology relation label into the string the evaluator expects."""
    return label.strip().replace(' ', '_')


class OntologyAdapter:
    """Maps a single Text2KGBench ontology onto a WUKONG graph model."""

    def __init__(
        self,
        ontology: dict[str, Any],
        collection: str,
        date_examples: dict[str, list[str]] | None = None,
        entity_examples: dict[str, list[str]] | None = None,
        *,
        permissive_endpoints: bool = False,
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
        """
        self._ontology = ontology
        self._collection = collection
        self._date_examples = date_examples or {}
        self._entity_examples = entity_examples or {}
        self._permissive_endpoints = permissive_endpoints
        self._title = ontology.get('title', ontology['id']).strip()

        # qid -> concept label, for every concept declared by the ontology
        self._concepts: dict[str, str] = {c['qid']: c['label'].strip() for c in ontology['concepts']}

        self._entity_names = self._resolve_entity_names()
        self._relationship_names = self._resolve_relationship_names()

    # Name resolution

    def _referenced_qids(self) -> set[str]:
        """Collect the concept qids actually used as a relation domain or range.

        A qid that no concept declares carries no label we could describe to the
        LLM, so it is treated exactly like an empty range and falls back to Value.
        """
        qids: set[str] = set()
        for relation in self._ontology['relations']:
            for key in ('domain', 'range'):
                qid = relation.get(key, '').strip()
                if qid and qid in self._concepts:
                    qids.add(qid)
        return qids

    def _resolve_entity_names(self) -> dict[str, str]:
        """Build the qid -> WUKONG entity type name mapping."""
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

    def _resolve_relationship_names(self) -> dict[str, str]:
        """Build the benchmark relation label -> WUKONG relationship type name mapping.

        Relations sharing a label (same pid, different range) are a single
        relationship type carrying several endpoint pairs.
        """
        names: dict[str, str] = {}
        taken: set[str] = set()
        for relation in self._ontology['relations']:
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
        """Resolve a domain/range qid to the entity type name representing it."""
        return self._entity_names.get(qid.strip(), VALUE_TYPE)

    # Graph model construction

    def _value_instruction(self) -> str | None:
        """Describe which relations need a Value object, to bound its extraction.

        Without this the type is unbounded and the LLM extracts every noun phrase
        in the sentence.
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
        """Build a single entity type definition."""
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
        """Map entity type names to date examples, for types that receive date objects."""
        targets: dict[str, list[str]] = {}
        for relation in self._ontology['relations']:
            examples = self._date_examples.get(relation['label'].strip())
            if not examples:
                continue
            target = self._endpoint_type(relation.get('range', ''))
            for example in examples:
                if example not in targets.setdefault(target, []):
                    targets[target].append(example)
        return targets

    def _build_entity_types(self) -> dict[str, Any]:
        """Build every entity type required by the ontology's relations."""
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
        """
        rule = {'source_context_levels': 'chunk', 'target_context_levels': 'chunk'}
        return {source: {target: [rule] for target in entity_types} for source in entity_types}

    def _build_relationship_types(self, entity_types: dict[str, Any]) -> dict[str, Any]:
        """Build one relationship type per distinct ontology relation label."""
        relationship_types: dict[str, Any] = {}
        for relation in self._ontology['relations']:
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

    def graph_model(self) -> dict[str, Any]:
        """Build the complete WUKONG graph model for this ontology."""
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
        """Build the reverse mapping used to export benchmark triples."""
        return {
            'ontology_id': self._ontology['id'],
            'title': self._title,
            'value_entity_type': VALUE_TYPE,
            'entity_types': {name: self._concepts[qid] for qid, name in self._entity_names.items()},
            # The evaluator compares relation strings with spaces replaced by underscores
            'relationship_types': {
                name: benchmark_relation(label) for label, name in self._relationship_names.items()
            },
        }


def scan_train_date_examples(train_path: Path, limit: int = 2) -> dict[str, list[str]]:
    """Collect date-formatted objects per relation from the train split.

    Train records are flat, carrying one triple per line as sub_label/rel_label/
    obj_label. Only the train split is read, never test or ground truth,
    mirroring the information the few-shot baselines obtained from their
    retrieved examples.
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
) -> dict[str, list[str]]:
    """Collect example surface forms per concept from the train split.

    A train record carries one triple as sub_label/rel_label/obj_label, so the
    subject illustrates the relation's domain concept and the object its range.
    Only the train split is read, never test or ground truth, which mirrors the
    information the few-shot baselines obtained from their retrieved examples --
    and gives entity types the same kind of grounding that dates already get.
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
                key = qid if qid in declared else (f'rel:{relation}' if index == 1 else '')
                if not key:
                    continue
                found = examples.setdefault(key, [])
                if value not in found and len(found) < limit:
                    found.append(value)
    return examples


def write_json(path: Path, payload: dict[str, Any]) -> None:
    """Write a JSON document with a trailing newline."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=4, ensure_ascii=False) + '\n', encoding='utf-8')


def write_sentences(test_path: Path, sentences_dir: Path) -> int:
    """Write one document per test sentence, named after its benchmark id."""
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
    """Generate the workspace and data directory for a single ontology."""
    dataset = Path(args.benchmark).resolve() / 'data' / args.dataset
    ontology = json.loads((dataset / 'ontologies' / f'{onto}_ontology.json').read_text(encoding='utf-8'))

    train_path = dataset / 'train' / f'ont_{onto}_train.jsonl'
    date_examples = {} if args.no_date_convention else scan_train_date_examples(train_path)
    entity_examples = scan_train_entity_examples(train_path, ontology) if args.entity_examples else {}
    adapter = OntologyAdapter(
        ontology,
        collection=args.collection,
        date_examples=date_examples,
        entity_examples=entity_examples,
        permissive_endpoints=args.permissive_endpoints,
    )
    workspace = Path(args.workspace_root) / f'{args.prefix}{onto}'
    data_dir = Path(args.data_root) / onto

    write_json(workspace / 'graph_model.json', adapter.graph_model())
    write_json(
        workspace / 'document_collections.json',
        {'collections': {args.collection: {'sources': [{'root': args.collection, 'mode': 'directory'}]}}},
    )
    write_json(workspace / 'text2kg_mapping.json', adapter.mapping())

    sentences = write_sentences(dataset / 'test' / f'ont_{onto}_test.jsonl', data_dir / args.collection)

    model = adapter.graph_model()
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
    """Build the command line parser."""
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
    return parser


def main() -> int:
    """Generate workspaces and data directories for the requested ontologies."""
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
