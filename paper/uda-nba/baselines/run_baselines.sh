#!/usr/bin/env bash
# Build the schema-based baseline graphs over the full UDA-Bench NBA corpus with the same model
# as Wukong (gpt-5.6-luna, low reasoning). Each system has its own env and runner (see the
# runner docstrings for the schema translation and settings).
#
#   baselines/run_baselines.sh "neo4j-graphrag llamaindex ontogpt"     # from paper/uda-nba
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; source ../../.env; set +a
SYSTEMS=${1:-"neo4j-graphrag llamaindex ontogpt"}

caffeinate -i bash -c '
  for s in "$@"; do
    case $s in
      neo4j-graphrag) py=envs/neo4j-graphrag/bin/python; script=baselines/neo4j_graphrag_build.py ;;
      llamaindex)     py=envs/llamaindex/bin/python;     script=baselines/llamaindex_build.py ;;
      ontogpt)        py=envs/ontogpt/bin/python;        script=baselines/ontogpt_build.py ;;
    esac
    ( $py $script --data data/docs --out runs/$s-full > runs/$s-full.log 2>&1; echo "$s exit=$?" ) &
  done
  wait
' _ $SYSTEMS
echo "done: $(date)"
