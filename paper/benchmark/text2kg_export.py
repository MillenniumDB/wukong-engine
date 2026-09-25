"""Convert a WUKONG run into Text2KGBench system output.

Reads the extracted knowledge straight from a workspace's staging database and
emits one JSONL record per test sentence, in the shape `run_eval.py` consumes:

    {"id": "ont_2_music_test_1", "triples": [["' 39", "composer", "Brian May"]]}

Triples are attributed to sentences through relationship provenance:

    relationships -> relationship_provenance -> chunks -> documents.source_uri

Since setup writes one sentence per document named after its benchmark id, the
document's file stem is the test sentence id. Every test sentence gets a record,
including sentences that yielded no triples, so the evaluator counts them.

A workspace compiled with `--literal-properties` also carries relations as entity
properties. Each property value becomes a triple `(entity, relation, value)`,
attributed through entity provenance instead:

    entities -> entity_provenance -> chunks -> documents.source_uri

Entities are merged across sentences, so a merged value may have been read from
a different sentence than the one being attributed. A value is therefore only
emitted for a sentence that states it.

Example:
    python paper/benchmark/text2kg_export.py \
        --benchmark ../benchmarks/Text2KGBench --onto 2_music \
        --workspace-root paper/benchmark/workspaces --out paper/benchmark/results/wukong
"""

import argparse
import json
import re
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from text2kg_setup import DATE_OBJECT_PATTERN, ONTOLOGIES  # noqa: E402

# Every chunk-level sighting of an entity, with the text it was seen in
PROPERTY_QUERY = """
    SELECT
        d.source_uri       AS source_uri,
        c.content          AS content,
        e.entity_type_name AS entity_type,
        e.properties       AS properties
    FROM entity_provenance ep
    JOIN entities e  ON e.content_id = ep.entity_content_id
    JOIN chunks c    ON c.content_id = ep.context_content_id
    JOIN documents d ON d.content_id = c.document_content_id
    WHERE ep.context_level = 'CHUNK'
"""

# Each relationship is attributed to every chunk it was extracted from, so a
# triple is emitted once per contributing sentence.
TRIPLE_QUERY = """
    SELECT
        d.source_uri             AS source_uri,
        r.relationship_type_name AS relationship_type,
        src.entity_type_name     AS source_type,
        tgt.entity_type_name     AS target_type,
        src.properties           AS source_properties,
        tgt.properties           AS target_properties
    FROM relationship_provenance rp
    JOIN relationships r ON r.content_id = rp.relationship_content_id
    JOIN chunks c        ON c.content_id = rp.chunk_content_id
    JOIN documents d     ON d.content_id = c.document_content_id
    JOIN entities src    ON src.content_id = r.source_content_id
    JOIN entities tgt    ON tgt.content_id = r.target_content_id
"""


def read_primary_key(properties: str, primary_keys: dict[str, str], entity_type: str) -> str | None:
    """Read an entity's primary key value out of its serialized properties.

    Args:
        properties: JSON-serialized entity properties, as stored in the staging database.
        primary_keys: Mapping from entity type name to its primary key field.
        entity_type: Name of the entity's type.

    Returns:
        The stripped primary key value, or None if the type has no known primary key or the value is missing, not a
        string, or blank.
    """
    field = primary_keys.get(entity_type)
    if field is None:
        return None
    value = json.loads(properties).get(field)
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def load_primary_keys(workspace: Path) -> dict[str, str]:
    """Map each entity type to the field holding its primary key.

    Args:
        workspace: Workspace directory holding the compiled ``knowledge_model.json``.

    Returns:
        Mapping from entity type name to its primary key field name.
    """
    model = json.loads((workspace / 'knowledge_model.json').read_text(encoding='utf-8'))
    return {name: definition['primary_key'] for name, definition in model['entity_types'].items()}


def collect_triples(
    staging_db: Path,
    relation_labels: dict[str, str],
    primary_keys: dict[str, str],
) -> tuple[dict[str, list[list[str]]], int]:
    """Group extracted triples by the test sentence they were extracted from.

    Args:
        staging_db: Staging SQLite database of the workspace, opened read-only.
        relation_labels: Mapping from relationship type name to benchmark relation label.
        primary_keys: Mapping from entity type name to its primary key field.

    Returns:
        A tuple of the deduplicated ``[subject, relation, object]`` triples keyed by sentence (document file stem),
        and the number of rows skipped because an endpoint carried no usable primary key value.

    Raises:
        KeyError: If an extracted relationship type is missing from ``relation_labels``.
    """
    triples: dict[str, list[list[str]]] = defaultdict(list)
    skipped = 0

    connection = sqlite3.connect(f'file:{staging_db}?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    try:
        for row in connection.execute(TRIPLE_QUERY):
            relationship_type = row['relationship_type']
            relation = relation_labels.get(relationship_type)

            # An unmapped type means the workspace and mapping are out of sync
            if relation is None:
                raise KeyError(f'Relationship type "{relationship_type}" is missing from the mapping file')

            subject = read_primary_key(row['source_properties'], primary_keys, row['source_type'])
            obj = read_primary_key(row['target_properties'], primary_keys, row['target_type'])
            if subject is None or obj is None:
                skipped += 1
                continue

            sentence_id = Path(row['source_uri']).stem
            triple = [subject, relation, obj]
            if triple not in triples[sentence_id]:
                triples[sentence_id].append(triple)
    finally:
        connection.close()

    return triples, skipped


def compact(text: str) -> str:
    """Lowercase and drop spaces and underscores, as the evaluator compares strings.

    Args:
        text: Text to compact.

    Returns:
        The lowercased text without whitespace or underscores.
    """
    return re.sub(r'(_|\s+)', '', text).lower()


def stated_in(value: str, text: str) -> bool:
    """Return whether a property value is stated in a sentence.

    A date follows the dataset's `<DD> <Month> <YYYY>` convention rather than the
    sentence's wording, so only its year is required to occur.

    Args:
        value: Property value to look for.
        text: Sentence text to search.

    Returns:
        True if the value (or, for a date, its year) occurs in the text, compared as the evaluator does, False
        otherwise.
    """
    if DATE_OBJECT_PATTERN.match(value):
        return value[-4:] in text
    return compact(value) in compact(text)


def collect_property_triples(
    staging_db: Path,
    properties: dict[str, dict[str, str]],
    separator: str,
    primary_keys: dict[str, str],
    triples: dict[str, list[list[str]]],
) -> int:
    """Add the triples encoded as entity properties to the per-sentence triples.

    Multi-valued properties are split on ``separator``, and each value is only kept for
    a sentence that states it. ``triples`` is updated in place, skipping duplicates.

    Args:
        staging_db: Staging SQLite database of the workspace, opened read-only.
        properties: Mapping from entity type name to a mapping from field name to benchmark relation label.
        separator: Separator between values in a multi-valued property. Surrounding whitespace is ignored.
        primary_keys: Mapping from entity type name to its primary key field.
        triples: Per-sentence triples to extend, keyed by sentence (document file stem).

    Returns:
        The number of values withheld because the sentence does not state them.
    """
    withheld = 0
    connection = sqlite3.connect(f'file:{staging_db}?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    try:
        for row in connection.execute(PROPERTY_QUERY):
            fields = properties.get(row['entity_type'])
            if not fields:
                continue
            subject = read_primary_key(row['properties'], primary_keys, row['entity_type'])
            if subject is None:
                continue
            values = json.loads(row['properties'])
            sentence_id = Path(row['source_uri']).stem
            for field, relation in fields.items():
                raw = values.get(field)
                if not isinstance(raw, str):
                    continue
                for value in (part.strip() for part in raw.split(separator.strip())):
                    if not value:
                        continue
                    if not stated_in(value, row['content']):
                        withheld += 1
                        continue
                    triple = [subject, relation, value]
                    if triple not in triples[sentence_id]:
                        triples[sentence_id].append(triple)
    finally:
        connection.close()
    return withheld


def read_test_cases(test_path: Path) -> list[tuple[str, str]]:
    """Read the ordered (id, sentence) pairs for an ontology.

    Args:
        test_path: JSONL file of the ontology's test split.

    Returns:
        The ``(id, stripped sentence)`` pairs in file order.
    """
    cases = []
    with test_path.open(encoding='utf-8') as test_file:
        for line in test_file:
            if line.strip():
                case = json.loads(line)
                cases.append((case['id'], case['sent'].strip()))
    return cases


def export_ontology(onto: str, args: argparse.Namespace) -> dict[str, int | str]:
    """Convert one ontology's workspace into a benchmark system output file.

    Args:
        onto: Ontology identifier.
        args: Parsed command-line arguments (benchmark, dataset, workspace_root, prefix and out).

    Returns:
        Export summary: ontology, sentence count, sentences with triples, triple count, skipped and withheld rows,
        number of documents not matching any test id, and the output path.

    Raises:
        FileNotFoundError: If the workspace has no staging database.
        KeyError: If an extracted relationship type is missing from the workspace's mapping file.
    """
    workspace = Path(args.workspace_root) / f'{args.prefix}{onto}'
    staging_db = workspace / 'staging' / 'extraction.db'
    if not staging_db.exists():
        raise FileNotFoundError(f'No staging database for {onto}: {staging_db}')

    mapping = json.loads((workspace / 'text2kg_mapping.json').read_text(encoding='utf-8'))
    primary_keys = load_primary_keys(workspace)
    by_document, skipped = collect_triples(staging_db, mapping['relationship_types'], primary_keys)
    withheld = 0
    if mapping.get('properties'):
        withheld = collect_property_triples(
            staging_db, mapping['properties'], mapping['property_separator'], primary_keys, by_document,
        )

    test_path = Path(args.benchmark).resolve() / 'data' / args.dataset / 'test' / f'ont_{onto}_test.jsonl'
    test_cases = read_test_cases(test_path)

    # Documents are content addressed, so test sentences repeated verbatim under
    # different ids collapse into a single document. Triples extracted from that
    # document belong to every id sharing the sentence.
    sentence_of = dict(test_cases)
    ids_of_sentence: dict[str, list[str]] = defaultdict(list)
    for test_id, sentence in test_cases:
        ids_of_sentence[sentence].append(test_id)

    triples: dict[str, list[list[str]]] = {}
    unknown = 0
    for document_id, document_triples in by_document.items():
        sentence = sentence_of.get(document_id)
        if sentence is None:
            unknown += 1
            continue
        for test_id in ids_of_sentence[sentence]:
            triples[test_id] = document_triples

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f'ont_{onto}_wukong_responses.jsonl'
    with out_path.open('w', encoding='utf-8') as out_file:
        for test_id, _ in test_cases:
            record = {'id': test_id, 'triples': triples.get(test_id, [])}
            out_file.write(json.dumps(record, ensure_ascii=False) + '\n')

    return {
        'onto': onto,
        'sentences': len(test_cases),
        'with_triples': sum(1 for i, _ in test_cases if triples.get(i)),
        'triples': sum(len(triples.get(i, [])) for i, _ in test_cases),
        'skipped': skipped,
        'withheld': withheld,
        'unknown_ids': unknown,
        'out': str(out_path),
    }


def build_parser() -> argparse.ArgumentParser:
    """Build the command line parser.

    Returns:
        The argument parser for this script.
    """
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--benchmark', type=Path, required=True, help='Path to the Text2KGBench repository')
    parser.add_argument('--dataset', default='wikidata_tekgen', help='Benchmark dataset directory name')
    parser.add_argument('--onto', action='append', choices=[*ONTOLOGIES], help='Ontology to export (repeatable)')
    parser.add_argument('--workspace-root', type=Path, default=Path('paper/benchmark/workspaces'))
    parser.add_argument('--prefix', default='tekgen_', help='Workspace directory name prefix')
    parser.add_argument('--out', type=Path, default=Path('paper/benchmark/results/wukong'))
    return parser


def main() -> int:
    """Convert every requested ontology into benchmark system output.

    Returns:
        The process exit code, always 0.
    """
    args = build_parser().parse_args()
    for onto in args.onto or ONTOLOGIES:
        result = export_ontology(onto, args)
        warning = ''
        if result['skipped']:
            warning += f' skipped={result["skipped"]}'
        if result['withheld']:
            warning += f' withheld_unstated={result["withheld"]}'
        if result['unknown_ids']:
            warning += f' UNKNOWN_IDS={result["unknown_ids"]}'
        print(
            f'{result["onto"]:12s} '
            f'sentences={result["sentences"]:4d} '
            f'with_triples={result["with_triples"]:4d} '
            f'triples={result["triples"]:5d}{warning} -> {result["out"]}',
        )
    return 0


if __name__ == '__main__':
    sys.exit(main())
