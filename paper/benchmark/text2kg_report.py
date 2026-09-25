"""Summarize a completed benchmark run into the tables used by the paper.

Reads the evaluator's per-ontology metrics, the converted system outputs and the
workspace staging databases, and prints:

    - the per-ontology metric table, for both test populations
    - the comparison against the published Text2KGBench baselines
    - coverage (how many sentences produced triples) and extraction cost

Example:
    python paper/benchmark/text2kg_report.py
"""

import argparse
import collections
import json
import re
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from text2kg_setup import ONTOLOGIES  # noqa: E402

# Metric keys as the evaluator writes them, in reporting order
METRICS = ('avg_precision', 'avg_recall', 'avg_f1', 'avg_onto_conf', 'avg_sub_halluc', 'avg_rel_halluc', 'avg_obj_halluc')

BASELINES = ('Vicuna-13B', 'Alpaca-LoRA-13B')


def read_avg_stats(path: Path) -> dict[tuple[str, str], dict[str, float]]:
    """Read an average-metrics file into {(ontology, population): metrics}."""
    stats: dict[tuple[str, str], dict[str, float]] = {}
    if not path.exists():
        return stats
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        name = record.get('onto', record.get('id', '?'))
        stats[name, record['type']] = {key: float(record[key]) for key in METRICS}
    return stats


def baseline_stats(results_root: Path) -> dict[str, dict[tuple[str, str], dict[str, float]]]:
    """Read the baseline metrics produced by re-scoring their published outputs.

    The baselines are re-scored under this harness rather than read from the
    metrics files shipped with the benchmark, because those ship two settings
    side by side (the main test split and a separate "unseen sentences" split)
    and only the main split is comparable to our run.
    """
    return {name: read_avg_stats(results_root / 'baselines' / name / 'ont_avg_stats.jsonl') for name in BASELINES}


def coverage(responses: Path) -> dict[str, tuple[int, int, int]]:
    """Count (sentences, sentences with triples, total triples) per ontology."""
    counts = {}
    for onto in ONTOLOGIES:
        path = responses / f'ont_{onto}_wukong_responses.jsonl'
        if not path.exists():
            continue
        total = with_triples = triples = 0
        for line in path.read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            total += 1
            triples += len(record['triples'])
            with_triples += 1 if record['triples'] else 0
        counts[onto] = (total, with_triples, triples)
    return counts


def cost(workspaces: Path, prefix: str) -> dict[str, dict[str, int]]:
    """Read job counts, token usage and wall clock from each staging database."""
    usage = {}
    for onto in ONTOLOGIES:
        staging = workspaces / f'{prefix}{onto}' / 'staging' / 'extraction.db'
        if not staging.exists():
            continue
        connection = sqlite3.connect(f'file:{staging}?mode=ro', uri=True)
        try:
            jobs, failed = connection.execute(
                "SELECT COUNT(*), SUM(job_status != 'COMPLETED') FROM extraction_jobs",
            ).fetchone()
            tokens = connection.execute(
                'SELECT SUM(input_tokens), SUM(cached_tokens), SUM(cache_write_tokens),'
                ' SUM(output_tokens), SUM(reasoning_tokens) FROM extraction_jobs',
            ).fetchone()
            started, finished = connection.execute(
                'SELECT MIN(created_at), MAX(finished_at) FROM extraction_jobs',
            ).fetchone()
            documents = connection.execute('SELECT COUNT(*) FROM documents').fetchone()[0]
        finally:
            connection.close()
        usage[onto] = {
            'documents': documents,
            'jobs': jobs,
            'failed': failed or 0,
            'input': tokens[0] or 0,
            'cached': tokens[1] or 0,
            'cache_write': tokens[2] or 0,
            'output': tokens[3] or 0,
            'reasoning': tokens[4] or 0,
            'seconds': round((finished - started) / 1000) if started and finished else 0,
        }
    return usage


def normalize_triple(triple: list[str]) -> str:
    """Build the comparison key `run_eval.py` uses for a triple."""
    return ''.join(re.sub(r'(_|\s+)', '', part).lower() for part in triple)


def recall_by_object_type(
    dataset: Path,
    responses: Path,
    workspaces: Path,
    prefix: str,
) -> tuple[dict[str, tuple[int, int]], list[tuple[str, str, int, int]]]:
    """Split gold-triple recall by how the object had to be modelled.

    WUKONG represents literals as properties of an entity, but a benchmark triple
    has no room for a property, so setup routes objects with no usable range
    concept to the catch-all `Value` entity type. Such an object must then be
    extracted as an entity in its own right before any relationship can point at
    it, which is the cost this table measures. A workspace compiled with
    `--literal-properties` stores those objects as entity properties instead, and
    the same bucket then measures recall on property-valued triples.
    """
    buckets: dict[str, list[int]] = {'entity': [0, 0], 'value': [0, 0], 'off_ontology': [0, 0]}
    per_relation: list[tuple[str, str, int, int]] = []

    for onto in ONTOLOGIES:
        workspace = workspaces / f'{prefix}{onto}'
        if not (responses / f'ont_{onto}_wukong_responses.jsonl').exists():
            continue
        model = json.loads((workspace / 'knowledge_model.json').read_text(encoding='utf-8'))
        mapping = json.loads((workspace / 'text2kg_mapping.json').read_text(encoding='utf-8'))
        value_type = mapping['value_entity_type']

        # A relation is "value typed" when every endpoint it declares targets
        # Value, or when it is compiled into an entity property
        is_value: dict[str, bool] = {}
        for wukong_name, label in mapping['relationship_types'].items():
            targets = {t for source in model['relationship_types'][wukong_name]['endpoints'].values() for t in source}
            is_value[label] = bool(targets) and targets == {value_type}
        for fields in mapping.get('properties', {}).values():
            for label in fields.values():
                is_value[label] = True

        system: dict[str, list[list[str]]] = {}
        for line in (responses / f'ont_{onto}_wukong_responses.jsonl').read_text(encoding='utf-8').splitlines():
            if line.strip():
                record = json.loads(line)
                system[record['id']] = record['triples']

        counts: dict[str, list[int]] = {}
        ground_truth = dataset / 'ground_truth' / f'ont_{onto}_ground_truth.jsonl'
        for line in ground_truth.read_text(encoding='utf-8').splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            gold = [[t['sub'], t['rel'].replace(' ', '_'), t['obj']] for t in record['triples']]
            if not gold:
                continue

            # The evaluator only scores system triples whose relation this
            # sentence's gold standard also uses
            gold_relations = {t[1] for t in gold}
            emitted = {normalize_triple(t) for t in system.get(record['id'], []) if t[1] in gold_relations}
            for triple in gold:
                found = counts.setdefault(triple[1], [0, 0])
                found[0] += 1
                found[1] += normalize_triple(triple) in emitted

        for relation, (total, matched) in sorted(counts.items()):
            value = is_value.get(relation)
            bucket = 'off_ontology' if value is None else ('value' if value else 'entity')
            buckets[bucket][0] += total
            buckets[bucket][1] += matched
            if value:
                per_relation.append((onto, relation, total, matched))

    return {name: (total, matched) for name, (total, matched) in buckets.items()}, per_relation


def extracted_entities(staging: Path, model: dict) -> dict[str, dict[str, set[str]]]:
    """Map each sentence to the entities extracted from it and their types."""
    primary_keys = {name: spec['primary_key'] for name, spec in model['entity_types'].items()}
    query = """
        SELECT d.source_uri, e.entity_type_name, e.properties
        FROM entity_provenance ep
        JOIN entities e   ON e.content_id = ep.entity_content_id
        JOIN chunks c     ON c.content_id = ep.context_content_id
        JOIN documents d  ON d.content_id = c.document_content_id
    """
    found: dict[str, dict[str, set[str]]] = {}
    connection = sqlite3.connect(f'file:{staging}?mode=ro', uri=True)
    try:
        for source_uri, entity_type, properties in connection.execute(query):
            value = json.loads(properties).get(primary_keys.get(entity_type, ''))
            if isinstance(value, str) and value.strip():
                sentence = found.setdefault(Path(source_uri).stem, {})
                sentence.setdefault(re.sub(r'(_|\s+)', '', value).lower(), set()).add(entity_type)
    finally:
        connection.close()
    return found


def miss_decomposition(
    dataset: Path,
    responses: Path,
    workspaces: Path,
    prefix: str,
) -> tuple[collections.Counter, collections.Counter]:
    """Explain why recoverable gold triples were missed.

    Restricted to gold triples that were achievable at all: both arguments occur
    in the sentence under the evaluator's normalization. The categories separate
    the entity pass from the relationship pass, and single out the triples lost
    because a relationship's compiled endpoint types reject the pair of types the
    entity pass actually assigned.
    """
    totals = collections.Counter()
    blocked_by_relation = collections.Counter()

    for onto in ONTOLOGIES:
        workspace = workspaces / f'{prefix}{onto}'
        if not (responses / f'ont_{onto}_wukong_responses.jsonl').exists():
            continue
        model = json.loads((workspace / 'knowledge_model.json').read_text(encoding='utf-8'))
        mapping = json.loads((workspace / 'text2kg_mapping.json').read_text(encoding='utf-8'))
        relationship_of = {label: name for name, label in mapping['relationship_types'].items()}

        # A property-valued object is never an entity, so the entity/relationship
        # decomposition does not apply to it
        property_only = {
            label for fields in mapping.get('properties', {}).values() for label in fields.values()
        } - set(relationship_of)
        allowed = {
            name: {(source, target) for source, targets in spec['endpoints'].items() for target in targets}
            for name, spec in model['relationship_types'].items()
        }
        entities = extracted_entities(workspace / 'staging' / 'extraction.db', model)

        system: dict[str, list[list[str]]] = {}
        for line in (responses / f'ont_{onto}_wukong_responses.jsonl').read_text(encoding='utf-8').splitlines():
            if line.strip():
                record = json.loads(line)
                system[record['id']] = record['triples']

        for line in (dataset / 'ground_truth' / f'ont_{onto}_ground_truth.jsonl').read_text(
            encoding='utf-8',
        ).splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            sentence = re.sub(r'(_|\s+)', '', record['sent']).lower()
            gold = [[t['sub'], t['rel'].replace(' ', '_'), t['obj']] for t in record['triples']]
            if not gold:
                continue
            gold_relations = {t[1] for t in gold}
            emitted = system.get(record['id'], [])
            keys = {normalize_triple(t) for t in emitted if t[1] in gold_relations}
            pairs = {(normalize_triple([t[0]]), normalize_triple([t[2]])) for t in emitted if t[1] in gold_relations}
            found = entities.get(record['id'], {})

            for subject, relation, obj in gold:
                key_s, key_o = normalize_triple([subject]), normalize_triple([obj])
                if relation in property_only or key_s not in sentence or key_o not in sentence:
                    continue
                totals['achievable'] += 1
                if key_s + normalize_triple([relation]) + key_o in keys:
                    totals['matched'] += 1
                elif (key_s, key_o) in pairs:
                    totals['different relation'] += 1
                elif key_s in found and key_o in found:
                    name = relationship_of.get(relation)
                    combinations = {(a, b) for a in found[key_s] for b in found[key_o]}
                    if name is not None and not (combinations & allowed[name]):
                        totals['blocked by endpoint types'] += 1
                        blocked_by_relation[f'{onto}:{relation}'] += 1
                    else:
                        totals['both entities found, no link'] += 1
                elif key_s in found or key_o in found:
                    totals['one entity missing'] += 1
                else:
                    totals['neither entity found'] += 1
    return totals, blocked_by_relation


def print_metric_table(stats: dict[tuple[str, str], dict[str, float]], population: str) -> None:
    """Print the per-ontology metric table for one test population."""
    print(f'\n### {population}\n')
    print('| Ontology | P | R | F1 | Conf. | Subj. hall. | Rel. hall. | Obj. hall. |')
    print('|---|---|---|---|---|---|---|---|')
    for onto in (*ONTOLOGIES, 'global'):
        key = (onto, 'global' if onto == 'global' else population)
        row = stats.get(key)
        if row is None:
            continue
        name = f'**{onto}**' if onto == 'global' else onto
        values = ' | '.join(f'{row[metric]:.2f}' for metric in METRICS)
        print(f'| {name} | {values} |')


def main() -> int:
    """Print every summary table for a completed run."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--results', type=Path, default=Path('paper/benchmark/results'))
    parser.add_argument('--workspace-root', type=Path, default=Path('paper/benchmark/workspaces'))
    parser.add_argument('--prefix', default='tekgen_')
    parser.add_argument(
        '--benchmark',
        type=Path,
        help='Path to the Text2KGBench repository; enables the recall-by-object-type table',
    )
    parser.add_argument('--dataset', default='wikidata_tekgen')
    args = parser.parse_args()

    stats = read_avg_stats(args.results / 'eval' / 'ont_avg_stats.jsonl')

    print('## WUKONG')
    for population in ('all_test_cases', 'selected_test_cases'):
        print_metric_table(stats, population)

    print('\n## Comparison (global, all test cases)\n')
    print('| System | P | R | F1 | Conf. | Subj. hall. | Rel. hall. | Obj. hall. |')
    print('|---|---|---|---|---|---|---|---|')
    rows = {'WUKONG': stats, **baseline_stats(args.results)}
    for name, table in rows.items():
        row = table.get(('global', 'global'))
        if row is None:
            continue
        values = ' | '.join(f'{row[metric]:.2f}' for metric in METRICS)
        print(f'| {name} | {values} |')

    if args.benchmark:
        dataset = args.benchmark.resolve() / 'data' / args.dataset
        buckets, per_relation = recall_by_object_type(
            dataset, args.results / 'wukong', args.workspace_root, args.prefix,
        )
        print('\n## Gold-triple recall by how the object is modelled\n')
        print('| Object modelled as | Gold triples | Matched | Recall |')
        print('|---|---|---|---|')
        for bucket, label in (
            ('entity', 'A typed entity'),
            ('value', 'Generic `Value` node, or entity property with `--literal-properties`'),
            ('off_ontology', 'Relation absent from the ontology'),
        ):
            total, matched = buckets[bucket]
            if total:
                print(f'| {label} | {total} | {matched} | {matched/total:.3f} |')

        print('\n### Worst value-typed relations\n')
        print('| Ontology | Relation | Gold | Matched | Recall |')
        print('|---|---|---|---|---|')
        worst = sorted(per_relation, key=lambda row: (row[3] / row[2], -row[2]))
        for onto, relation, total, matched in worst[:8]:
            if total >= 20:
                print(f'| {onto} | {relation} | {total} | {matched} | {matched/total:.3f} |')

        totals, blocked = miss_decomposition(dataset, args.results / 'wukong', args.workspace_root, args.prefix)
        achievable, matched = totals.pop('achievable'), totals.pop('matched')
        print('\n## Why recoverable gold triples were missed\n')
        print(f'Gold triples with both arguments present in the sentence: **{achievable}**, '
              f'of which **{matched}** matched ({matched/achievable:.1%}).\n')
        print('| Cause | Triples | Share of misses |')
        print('|---|---|---|')
        misses = achievable - matched
        for cause, count in totals.most_common():
            print(f'| {cause} | {count} | {count/misses:.1%} |')
        print('\n### Relations most affected by endpoint type gating\n')
        print('| Relation | Blocked |')
        print('|---|---|')
        for relation, count in blocked.most_common(8):
            print(f'| {relation} | {count} |')

    print('\n## Coverage and cost\n')
    print('| Ontology | Sentences | With triples | Triples | Docs | Jobs | Failed | Input tok | Output tok | Reasoning tok | Seconds |')
    print('|---|---|---|---|---|---|---|---|---|---|---|')
    counts, usage = coverage(args.results / 'wukong'), cost(args.workspace_root, args.prefix)
    totals: dict[str, int] = {}
    for onto in ONTOLOGIES:
        if onto not in counts or onto not in usage:
            continue
        total, with_triples, triples = counts[onto]
        use = usage[onto]
        print(
            f'| {onto} | {total} | {with_triples} | {triples} | {use["documents"]} | {use["jobs"]} '
            f'| {use["failed"]} | {use["input"]:,} | {use["output"]:,} | {use["reasoning"]:,} | {use["seconds"]} |',
        )
        for key, value in (('sent', total), ('with', with_triples), ('tri', triples), *use.items()):
            totals[key] = totals.get(key, 0) + value
    if totals:
        print(
            f'| **Total** | {totals["sent"]} | {totals["with"]} | {totals["tri"]} | {totals["documents"]} '
            f'| {totals["jobs"]} | {totals["failed"]} | {totals["input"]:,} | {totals["output"]:,} '
            f'| {totals["reasoning"]:,} | {totals["seconds"]} |',
        )
    return 0


if __name__ == '__main__':
    sys.exit(main())
