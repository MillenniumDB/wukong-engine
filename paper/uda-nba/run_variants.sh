#!/usr/bin/env bash
# Schema ablation: Wukong over the full corpus with workspace-v1, -v2 and -v3
# (built by make_schema_variants.py, which refuses schemas whose examples leak gold
# values), in parallel. runs/wukong-full used the original, leaky schema in workspace/.
#
#   ./run_variants.sh            # from paper/uda-nba
set -euo pipefail
cd "$(dirname "$0")"
set -a; [[ -f ../../.env ]] && source ../../.env; set +a  # or export OPENAI_API_KEY yourself
KEEP_AWAKE=$(command -v caffeinate >/dev/null && echo 'caffeinate -i' || true)  # macOS: keep the machine awake

python3 make_schema_variants.py
for v in v1 v2 v3; do
  mkdir -p runs/wukong-$v
  cp workspace-$v/*.json runs/wukong-$v/
  cp wukong-config.toml runs/wukong-$v/config.toml
done

$KEEP_AWAKE bash -c '
  for v in v1 v2 v3; do
    ( /usr/bin/time -p envs/wukong/bin/wukong run runs/wukong-$v data/docs \
        --config runs/wukong-$v/config.toml -v > runs/wukong-$v.log 2>&1 ) &
  done
  wait
'
echo "done: $(date)"
