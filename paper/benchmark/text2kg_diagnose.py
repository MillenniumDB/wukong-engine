"""Measure properties of the Text2KGBench data that bound or distort any score.

The Wikidata-TekGen ground truth is distantly supervised: triples were aligned
from Wikidata onto Wikipedia sentences, so a sentence's gold triples may name
entities the sentence never mentions, or use relations its own ontology does not
declare. Neither is recoverable by a system that extracts only what the text
states and only what the ontology allows, which is what WUKONG does by
construction.

Nothing here is specific to WUKONG: these are properties of the benchmark that
apply to every system evaluated on it. The script reports

    reachability: the share of gold triples a faithful extractor could produce
    ceiling:      the best macro F1 such a system could score
    artifacts:    data defects that distort scores in either direction

Run it with the evaluator environment, which has nltk:

    paper/benchmark/.venv-eval/bin/python paper/benchmark/text2kg_diagnose.py \
        --benchmark ../benchmarks/Text2KGBench
"""

import argparse
import collections
import json
import re
import sys
from pathlib import Path

from nltk.stem import PorterStemmer
from nltk.tokenize import word_tokenize

sys.path.insert(0, str(Path(__file__).parent))

from text2kg_setup import ONTOLOGIES  # noqa: E402

# 'Ã'/'Â' followed by a character in the U+0080-U+00BF band is what a UTF-8
# continuation byte becomes when the text is decoded as latin-1.
MOJIBAKE = re.compile('[ÃÂ][-¿]|â')


def read_jsonl(path: Path) -> list[dict]:
    """Read a JSONL file into a list of records."""
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]


def normalize(stemmer: PorterStemmer, text: str) -> str:
    """Stem, concatenate and lowercase a string, as `run_eval.py` does.

    The evaluator strips the stemmed form of the "01 January" date prefix, since
    TekGen writes year-only dates that way and only the year is in the sentence.
    """
    stemmed = ''.join(stemmer.stem(word) for word in word_tokenize(text))
    return re.sub(r'(_|\s+)', '', stemmed).lower().replace('01januari', '')


def repair_encoding(text: str) -> str:
    """Undo one round of utf-8-decoded-as-latin-1, where that is reversible."""
    try:
        return text.encode('latin-1').decode('utf-8')
    except (UnicodeEncodeError, UnicodeDecodeError):
        return text


class OntologyData:
    """The ground truth, ontology and verified subset for one ontology."""

    def __init__(self, onto: str, dataset: Path, stemmer: PorterStemmer) -> None:
        """Load every file the diagnostics need for a single ontology."""
        self.onto = onto
        self.stemmer = stemmer
        ontology = json.loads((dataset / 'ontologies' / f'{onto}_ontology.json').read_text(encoding='utf-8'))
        self.labels = {relation['label'].strip() for relation in ontology['relations']}
        self.concepts = ' '.join(concept['label'] for concept in ontology['concepts'])
        self.ground_truth = read_jsonl(dataset / 'ground_truth' / f'ont_{onto}_ground_truth.jsonl')

        selected = dataset / 'manually_verified_sentences' / f'selected_ont_{onto}.txt'
        self.selected = (
            {line.strip() for line in selected.read_text(encoding='utf-8').splitlines() if line.strip()}
            if selected.exists()
            else set()
        )

    def reachable(self, record: dict) -> tuple[int, dict[str, int]]:
        """Count the gold triples of one sentence a faithful extractor could produce."""
        haystack = normalize(self.stemmer, record['sent'] + ' ' + self.concepts)
        counts = collections.Counter()
        ok = 0
        for triple in record['triples']:
            off = triple['rel'].strip() not in self.labels
            no_subject = haystack.find(normalize(self.stemmer, triple['sub'])) == -1
            no_object = haystack.find(normalize(self.stemmer, triple['obj'])) == -1
            counts['off_ontology'] += off
            counts['absent_subject'] += no_subject
            counts['absent_object'] += no_object
            ok += not (off or no_subject or no_object)
        return ok, counts


def report_reachability(data: list[OntologyData]) -> None:
    """Print the share of gold triples that any faithful extractor could match."""
    print('\n## Reachable ground truth\n')
    print('| Ontology | GT triples | Off-ontology | Absent subject | Absent object | Reachable |')
    print('|---|---|---|---|---|---|')
    totals = collections.Counter()
    for item in data:
        counts = collections.Counter()
        triples = ok = 0
        for record in item.ground_truth:
            reachable, found = item.reachable(record)
            counts.update(found)
            ok += reachable
            triples += len(record['triples'])
        share = ok / triples if triples else 0
        print(
            f'| {item.onto} | {triples} | {counts["off_ontology"]} | {counts["absent_subject"]} '
            f'| {counts["absent_object"]} | {ok} ({share:.0%}) |',
        )
        totals.update(counts)
        totals['triples'] += triples
        totals['ok'] += ok
    share = totals['ok'] / totals['triples']
    print(
        f'| **Total** | {totals["triples"]} | {totals["off_ontology"]} | {totals["absent_subject"]} '
        f'| {totals["absent_object"]} | {totals["ok"]} ({share:.0%}) |',
    )


def report_ceiling(data: list[OntologyData]) -> None:
    """Print the best macro F1 a faithful, ontology-conforming system could score.

    Two limits compound: a sentence whose gold standard is empty scores zero
    however the system answers, and unreachable gold triples cost recall. The
    ceiling assumes a system that emits exactly the reachable triples and
    nothing else, so its precision is 1 wherever it answers at all.
    """
    print('\n## Macro F1 ceiling\n')
    print('| Ontology | Sentences | Empty GT | Ceiling (all) | Ceiling (verified) |')
    print('|---|---|---|---|---|')
    every: list[float] = []
    chosen: list[float] = []
    sentences = empty_total = 0
    for item in data:
        all_values: list[float] = []
        selected_values: list[float] = []
        empty = 0
        for record in item.ground_truth:
            gold = record['triples']
            if not gold:
                empty += 1
                best = 0.0
            else:
                ok, _ = item.reachable(record)
                best = 0.0 if not ok else 2 * ok / (len(gold) + ok)
            all_values.append(best)
            if record['id'] in item.selected:
                selected_values.append(best)
        print(
            f'| {item.onto} | {len(item.ground_truth)} | {empty} '
            f'| {sum(all_values)/len(all_values):.3f} | {sum(selected_values)/len(selected_values):.3f} |',
        )
        every += all_values
        chosen += selected_values
        sentences += len(item.ground_truth)
        empty_total += empty
    print(
        f'| **Global** | {sentences} | {empty_total} | **{sum(every)/len(every):.3f}** '
        f'| **{sum(chosen)/len(chosen):.3f}** |',
    )


def report_artifacts(data: list[OntologyData]) -> None:
    """Print data defects that distort scores independently of any system."""
    print('\n## Data artifacts\n')
    print('| Ontology | Empty GT | Dup. triples | GT self-loops | Mojibake sents | Fragments |')
    print('|---|---|---|---|---|---|')
    totals = collections.Counter()
    encoding_changes = 0
    for item in data:
        counts = collections.Counter()
        for record in item.ground_truth:
            sentence = record['sent'].strip()
            counts['empty'] += not record['triples']
            counts['mojibake'] += bool(MOJIBAKE.search(sentence))

            # A sentence starting lower case or on stray punctuation has had its
            # subject stripped, while the gold triples still name it
            counts['fragment'] += bool(sentence) and (sentence[0].islower() or sentence[0] in ')]},;:-')

            seen = set()
            for triple in record['triples']:
                key = (triple['sub'], triple['rel'], triple['obj'])
                counts['duplicate'] += key in seen
                seen.add(key)
                counts['self_loop'] += triple['sub'].strip().lower() == triple['obj'].strip().lower()

            # Does repairing the encoding change what the gold arguments match?
            fixed = repair_encoding(record['sent'])
            if fixed != record['sent']:
                for triple in record['triples']:
                    for argument in (triple['sub'], triple['obj']):
                        before = argument in record['sent']
                        after = argument in fixed or repair_encoding(argument) in fixed
                        encoding_changes += before != after
        print(
            f'| {item.onto} | {counts["empty"]} | {counts["duplicate"]} | {counts["self_loop"]} '
            f'| {counts["mojibake"]} | {counts["fragment"]} |',
        )
        totals.update(counts)
    print(
        f'| **Total** | {totals["empty"]} | {totals["duplicate"]} | {totals["self_loop"]} '
        f'| {totals["mojibake"]} | {totals["fragment"]} |',
    )
    print(
        f'\nGold arguments whose matchability changes if the mojibake is repaired: '
        f'**{encoding_changes}**. The corruption is present identically in the sentences and in '
        f'the ground truth, so it does not affect scoring.',
    )


def report_contamination(data: list[OntologyData], dataset: Path) -> None:
    """Print how many test sentences also appear in the train split."""
    print('\n## Train/test overlap\n')
    print('| Ontology | Test sentences | Also in train | Share |')
    print('|---|---|---|---|')
    total = overlap_total = 0
    for item in data:
        train_path = dataset / 'train' / f'ont_{item.onto}_train.jsonl'
        train = {record.get('sent', '').strip() for record in read_jsonl(train_path)} if train_path.exists() else set()
        sentences = [record['sent'].strip() for record in item.ground_truth]
        overlap = sum(1 for sentence in sentences if sentence in train)
        print(f'| {item.onto} | {len(sentences)} | {overlap} | {overlap/len(sentences):.1%} |')
        total += len(sentences)
        overlap_total += overlap
    print(f'| **Total** | {total} | {overlap_total} | {overlap_total/total:.1%} |')


def main() -> int:
    """Print every diagnostic for the Wikidata-TekGen suite."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--benchmark', type=Path, required=True)
    parser.add_argument('--dataset', default='wikidata_tekgen')
    args = parser.parse_args()

    dataset = args.benchmark.resolve() / 'data' / args.dataset
    stemmer = PorterStemmer()
    data = [OntologyData(onto, dataset, stemmer) for onto in ONTOLOGIES]

    report_reachability(data)
    report_ceiling(data)
    report_artifacts(data)
    report_contamination(data, dataset)
    return 0


if __name__ == '__main__':
    sys.exit(main())
