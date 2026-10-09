#!/usr/bin/env bash
# X6 / E3 coupling ablation: Wukong on the full corpus with workspace-x6-s0..s4
# (make_coupling_variants.py), current engine, x6-config.toml. Repetitions run as
# batches; each batch runs every variant once, in parallel. Output: runs/x6-s<k>-r<n>.
#
#   ./run_x6.sh "1 2 3" ["s0 s1 s2 s3 s4 s5"]          # from paper/uda-nba
set -euo pipefail
cd "$(dirname "$0")"
set -a; source ../../.env; set +a
REPS=${1:-"1 2 3"}
VARIANTS=${2:-"s0 s1 s2 s3 s4 s5"}

python3 make_coupling_variants.py
echo "engine: $(git rev-parse --short HEAD) $(git status --porcelain -- ../../src | wc -l | tr -d ' ') uncommitted src files"
for n in $REPS; do
  echo "batch r$n: $(date)"
  runs=()
  for s in $VARIANTS; do
    r=x6-$s-r$n
    mkdir -p runs/$r
    cp workspace-x6-$s/*.json runs/$r/
    cp x6-config.toml runs/$r/config.toml
    runs+=("$r")
  done
  caffeinate -i bash -c '
    for r in "$@"; do
      ( /usr/bin/time -p envs/wukong/bin/wukong run runs/$r data/docs \
          --config runs/$r/config.toml -v > runs/$r.log 2>&1 ) &
    done
    wait
  ' _ "${runs[@]}"
done
echo "done: $(date)"
