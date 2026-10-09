"""Relation-vocabulary statistics of the three graphs, without any knowledge of the domain.

    envs/graphrag/bin/python relation_vocab.py [--thresholds 0.95 0.9 0.85 0.8]

Labelings compared:
  Wukong            its relationship types
  LightRAG-keywords the keywords LightRAG attaches to each edge (sorted keyword set)
  LightRAG-derived  a predicate read from the edge description (derive_labels.py)
  GraphRAG-derived  same; GraphRAG edges have no label of their own

Synonym merging, generous to the baselines: labels are embedded (text-embedding-3-small) and
merged greedily into the most frequent label within cosine >= t (leader clustering: each label
joins the most similar existing leader, leaders taken in decreasing frequency, so a cluster is
held together by its leader and cannot chain). Statistics are reported before merging and at
each threshold, with the largest cluster and example members to check that merges are sane.
"""

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from openai import OpenAI

import e1_analysis as A

LABELS = A.RUNS / 'labels'
EMB_CACHE = LABELS / 'embeddings.npz'


def labelings():
    """name -> (edges with 'label' set, nodes)"""
    out = {}
    nodes, edges, _ = A.load_wukong(A.WUKONG_RUNS['Wukong-r1'])  # 3 types, the same in every run
    out['Wukong'] = (edges, nodes)
    nodes, edges, _ = A.load_lightrag()
    out['LightRAG-keywords'] = (edges, nodes)
    for system, load in (('LightRAG', A.load_lightrag), ('GraphRAG', A.load_graphrag)):
        nodes, edges, _ = load()
        derived = {}
        for line in (LABELS / f'{system}.jsonl').open():
            r = json.loads(line)
            derived[r['id']] = r
        edges = [dict(e, label=derived[i]['predicate'] if i in derived else None,
                      subject=derived[i].get('subject') if i in derived else None)
                 for i, e in enumerate(edges)]
        out[f'{system}-derived'] = (edges, nodes)
    return out


def text(label):
    return label.replace('_', ' ').replace(',', ', ')


def embed(labels):
    cache = dict(np.load(EMB_CACHE, allow_pickle=True)['emb'].item()) if EMB_CACHE.exists() else {}
    todo = [l for l in labels if l not in cache]
    client = OpenAI()
    for k in range(0, len(todo), 2048):
        chunk = todo[k:k + 2048]
        resp = client.embeddings.create(model='text-embedding-3-small', input=[text(l) for l in chunk],
                                        dimensions=512)
        for l, d in zip(chunk, resp.data):
            cache[l] = np.asarray(d.embedding, dtype=np.float32)
    if todo:
        np.savez(EMB_CACHE, emb=np.array(cache, dtype=object))
    X = np.stack([cache[l] for l in labels])
    return X / np.linalg.norm(X, axis=1, keepdims=True)


def merge(freq, t):
    """Leader clustering: label -> leader label."""
    labels = [l for l, _ in freq.most_common()]
    X = embed(labels)
    leaders, L = [], np.zeros((0, X.shape[1]), dtype=np.float32)
    assign = {}
    block = 1024
    for b in range(0, len(labels), block):
        idx = list(range(b, min(b + block, len(labels))))
        S = X[idx] @ L.T if len(leaders) else np.zeros((len(idx), 0))
        new = []  # leaders created inside this block
        for row, i in enumerate(idx):
            best, who = -1.0, None
            if S.shape[1]:
                j = int(S[row].argmax())
                best, who = float(S[row, j]), leaders[j]
            if new:
                s2 = X[new] @ X[i]
                j = int(s2.argmax())
                if s2[j] > best:
                    best, who = float(s2[j]), new[j]
            if who is not None and best >= t:
                assign[labels[i]] = labels[who]
            else:
                assign[labels[i]] = labels[i]
                new.append(i)
        leaders += new
        L = X[leaders]
    return assign


def stats(edges, nodes, label_of=lambda l: l):
    lab = Counter(label_of(e['label']) for e in edges if e['label'])
    n_e = len(edges)
    out = {'edges': n_e, 'unlabeled_edges': n_e - sum(lab.values()), 'labels': len(lab)}
    if not lab:
        return out
    tot, acc = sum(lab.values()), 0
    for k, (_, c) in enumerate(lab.most_common(), 1):
        acc += c
        if acc >= 0.5 * tot and 'labels_cover_50' not in out:
            out['labels_cover_50'] = k
        if acc >= 0.9 * tot:
            out['labels_cover_90'] = k
            break
    out['edges_per_label'] = round(tot / len(lab), 1)
    out['singleton_labels_pct'] = round(100 * sum(c == 1 for c in lab.values()) / len(lab), 1)
    out['edges_with_singleton_label_pct'] = round(100 * sum(c for c in lab.values() if c == 1) / tot, 1)
    out['top_label_share_pct'] = round(100 * lab.most_common(1)[0][1] / tot, 1)
    # direction: does the stored edge (src -> dst) read the way its relation reads? Derived
    # labels record the subject (X = src). Typed schemas fix direction by their endpoints.
    if any('subject' in e for e in edges):
        sub = [e for e in edges if e['label'] and e.get('subject') in ('X', 'Y')]
        out['edges_stored_backwards_pct'] = round(100 * sum(e['subject'] == 'Y' for e in sub) / len(sub), 1)
        per = defaultdict(Counter)
        for e in sub:
            per[label_of(e['label'])][e['subject']] += 1
        mixed = [c for c in per.values() if sum(c.values()) >= 10]
        out['labels_10plus_both_directions_pct'] = round(
            100 * sum(min(c['X'], c['Y']) >= 0.1 * sum(c.values()) for c in mixed) / len(mixed), 1)
    pair = defaultdict(Counter)
    for e in edges:
        if e['label']:
            a, b = sorted([nodes[e['src']]['type'], nodes[e['dst']]['type']])
            pair[(a, b)][label_of(e['label'])] += 1
    big = [len(c) for c in pair.values() if sum(c.values()) >= 100]
    out['type_pairs_100plus'] = len(big)
    out['labels_per_type_pair_mean'] = round(sum(big) / len(big), 1) if big else None
    out['labels_per_type_pair_max'] = max(big) if big else None
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--thresholds', type=float, nargs='+', default=[0.95, 0.9, 0.85, 0.8])
    ap.add_argument('--out', type=Path, default=A.RUNS / 'e1/relation_vocab.json')
    args = ap.parse_args()
    report = {}
    for name, (edges, nodes) in labelings().items():
        report[name] = {'raw': stats(edges, nodes)}
        freq = Counter(e['label'] for e in edges if e['label'])
        if len(freq) < 10:
            continue
        for t in args.thresholds:
            assign = merge(freq, t)
            s = stats(edges, nodes, label_of=assign.get)
            clusters = defaultdict(list)
            for l, lead in assign.items():
                clusters[lead].append(l)
            big = max(clusters, key=lambda k: sum(freq[x] for x in clusters[k]))
            s['largest_cluster'] = {'leader': big, 'labels': len(clusters[big]),
                                    'edges_pct': round(100 * sum(freq[x] for x in clusters[big]) / sum(freq.values()), 1),
                                    'members': sorted(clusters[big], key=lambda x: -freq[x])[:12]}
            report[name][f'merged_{t}'] = s
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=1))

    cols = list(report)
    rows = ['labels', 'edges_per_label', 'singleton_labels_pct', 'edges_with_singleton_label_pct',
            'labels_cover_50', 'labels_cover_90', 'top_label_share_pct', 'labels_per_type_pair_mean',
            'labels_per_type_pair_max', 'unlabeled_edges', 'edges_stored_backwards_pct',
            'labels_10plus_both_directions_pct']
    for level in ['raw'] + [f'merged_{t}' for t in args.thresholds]:
        print(f'\n== {level}')
        print(f'{"":<32}' + ''.join(f'{c:>20}' for c in cols))
        for r in rows:
            print(f'{r:<32}' + ''.join(f'{str(report[c].get(level, {}).get(r, "")):>20}' for c in cols))
        if level != 'raw':
            for c in cols:
                lc = report[c].get(level, {}).get('largest_cluster')
                if lc:
                    print(f'   {c}: largest cluster {lc["leader"]!r} ({lc["labels"]} labels, {lc["edges_pct"]}% of edges): {lc["members"][:8]}')


if __name__ == '__main__':
    main()
