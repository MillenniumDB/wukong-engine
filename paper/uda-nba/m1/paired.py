"""M1 paired comparison: one system against every other, question by question.

For each other system: the mean difference of per-question macro F1 over the questions both answered, its 95%
bootstrap confidence interval (5,000 resamples of the questions, fixed seed), and how many questions the first
system wins, ties and loses (a tie: the two scores agree to two decimals, a difference under 0.005). Reads the
per-question scores written by score.py (work/scores/<system>.json) or, with --scores, any folder of them, such
as the committed results/scores.

    python paired.py                                   # wukong against every system in work/scores
    python paired.py --base wukong_s4 --scores results/scores
"""

import argparse
import json
import random
import re
import statistics as st
import sys
from pathlib import Path

RESAMPLES = 5000
SEED = 0
TIE = 0.005  # scores equal to two decimals count as a tie


def load(folder: Path) -> dict[str, dict[str, float]]:
    """Per-question macro F1 of every system in a scores folder. A system run several times (<name>_r1, _r2, ...)
    also appears as <name>, with each question's score averaged over its runs."""
    out = {p.stem: {u: r['macro_f1'] for u, r in json.loads(p.read_text()).items()} for p in sorted(folder.glob('*.json'))}
    runs = {}
    for s in out:
        m = re.fullmatch(r'(.+)_r\d+', s)
        if m:
            runs.setdefault(m.group(1), []).append(out[s])
    for g, rs in runs.items():
        out[g] = {u: st.mean(r[u] for r in rs) for u in set.intersection(*(set(r) for r in rs))}
    return out


def compare(a: dict[str, float], b: dict[str, float]) -> tuple[float, float, float, int, int, int, int]:
    """Mean of a - b, its bootstrap 95% interval, wins, ties, losses and the number of questions."""
    uids = sorted(set(a) & set(b))
    diffs = [a[u] - b[u] for u in uids]
    rng = random.Random(SEED)
    means = sorted(st.mean(rng.choices(diffs, k=len(diffs))) for _ in range(RESAMPLES))
    low, high = means[int(0.025 * RESAMPLES)], means[int(0.975 * RESAMPLES) - 1]
    wins = sum(d >= TIE for d in diffs)
    losses = sum(d <= -TIE for d in diffs)
    return st.mean(diffs), low, high, wins, len(diffs) - wins - losses, losses, len(diffs)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--base', default='wukong', help='system compared against all others (default: wukong)')
    ap.add_argument('--scores', type=Path, help='folder of <system>.json scores (default: work/scores)')
    args = ap.parse_args()
    if args.scores is None:
        sys.path.insert(0, str(Path(__file__).parent))
        from common import WORK  # noqa: PLC0415
        args.scores = WORK / 'scores'
    scores = load(args.scores)
    if args.base not in scores:
        print(f'no scores for {args.base!r} in {args.scores}', file=sys.stderr)
        return 1
    print(f'{args.base} minus each system: mean difference of per-question macro F1 [95% bootstrap CI], '
          f'wins / ties / losses')
    for name, other in scores.items():
        if name == args.base:
            continue
        mean, low, high, w, t, lo, n = compare(scores[args.base], other)
        print(f'  {name:18s} {mean:+.2f} [{low:+.2f}, {high:+.2f}]  {w}/{t}/{lo}  ({n} questions)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
