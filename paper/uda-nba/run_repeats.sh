#!/usr/bin/env bash
# Repeat runs of the Wukong schema variants, for error bars. Run 1 of each variant is
# runs/wukong-<v> (run_variants.sh); repeats go to runs/wukong-<v>-r<k>.
#
#   ./run_repeats.sh "v2 v3" "2 3"       # from paper/uda-nba
set -euo pipefail
cd "$(dirname "$0")"
set -a; [[ -f ../../.env ]] && source ../../.env; set +a  # or export OPENAI_API_KEY yourself
KEEP_AWAKE=$(command -v caffeinate >/dev/null && echo 'caffeinate -i' || true)  # macOS: keep the machine awake
VARIANTS=${1:-"v2 v3"}
REPS=${2:-"2 3"}

python3 make_schema_variants.py
runs=()
for v in $VARIANTS; do
  for k in $REPS; do
    r=wukong-$v-r$k
    mkdir -p runs/$r
    cp workspace-$v/*.json runs/$r/
    cp wukong-config.toml runs/$r/config.toml
    runs+=("$r")
  done
done

$KEEP_AWAKE bash -c '
  for r in "$@"; do
    ( /usr/bin/time -p envs/wukong/bin/wukong run runs/$r data/docs \
        --config runs/$r/config.toml -v > runs/$r.log 2>&1 ) &
  done
  wait
' _ "${runs[@]}"
echo "done: $(date)"
