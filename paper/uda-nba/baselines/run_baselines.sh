#!/usr/bin/env bash
# Build the schema-based baseline graphs over the full UDA-Bench NBA corpus with the same model
# as Wukong (gpt-5.6-luna, low reasoning); KGGen and EDC are the schema-free triple extractors. Each system has its own env and runner (see the
# runner docstrings for the schema translation and settings).
#
#   baselines/run_baselines.sh "neo4j-graphrag llamaindex ontogpt kggen edc"     # from paper/uda-nba
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; [[ -f ../../.env ]] && source ../../.env; set +a  # or export OPENAI_API_KEY yourself
KEEP_AWAKE=$(command -v caffeinate >/dev/null && echo 'caffeinate -i' || true)  # macOS: keep the machine awake
SYSTEMS=${1:-"neo4j-graphrag llamaindex ontogpt"}

$KEEP_AWAKE bash -c '
  for s in "$@"; do
    case $s in
      neo4j-graphrag) py=envs/neo4j-graphrag/bin/python; script=baselines/neo4j_graphrag_build.py ;;
      llamaindex)     py=envs/llamaindex/bin/python;     script=baselines/llamaindex_build.py ;;
      ontogpt)        py=envs/ontogpt/bin/python;        script=baselines/ontogpt_build.py ;;
      kggen)          py=envs/kggen/bin/python;          script=baselines/kggen_build.py ;;
      edc)            py=envs/edc/bin/python;            script=baselines/edc_build.py ;;
    esac
    ( $py $script --data data/docs --out runs/$s-full > runs/$s-full.log 2>&1; echo "$s exit=$?" ) &
  done
  wait
' _ $SYSTEMS
echo "done: $(date)"
