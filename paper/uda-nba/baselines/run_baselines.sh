#!/usr/bin/env bash
# Build the baseline graphs over the full UDA-Bench NBA corpus with the same model as Wukong
# (gpt-5.6-luna, low reasoning): the schema-based extractors, from the NBA schema of the paper
# (workspace-x6-s4, their default), into runs/<tool>-s4-r<RUN>; KGGen, the schema-free triple
# extractor, into runs/kggen-full. Each system has its own env and runner (see the runner
# docstrings for the schema translation and settings).
#
#   RUN=1 baselines/run_baselines.sh "neo4j-graphrag llamaindex ontogpt kggen"     # from paper/uda-nba
set -euo pipefail
cd "$(dirname "$0")/.."
set -a; [[ -f ../../.env ]] && source ../../.env; set +a  # or export OPENAI_API_KEY yourself
KEEP_AWAKE=$(command -v caffeinate >/dev/null && echo 'caffeinate -i' || true)  # macOS: keep the machine awake
SYSTEMS=${1:-"neo4j-graphrag llamaindex ontogpt"}
export RUN=${RUN:-1}

$KEEP_AWAKE bash -c '
  for s in "$@"; do
    case $s in
      neo4j-graphrag) py=envs/neo4j-graphrag/bin/python; script=baselines/neo4j_graphrag_build.py; out=runs/$s-s4-r$RUN ;;
      llamaindex)     py=envs/llamaindex/bin/python;     script=baselines/llamaindex_build.py;     out=runs/$s-s4-r$RUN ;;
      ontogpt)        py=envs/ontogpt/bin/python;        script=baselines/ontogpt_build.py;        out=runs/$s-s4-r$RUN ;;
      kggen)          py=envs/kggen/bin/python;          script=baselines/kggen_build.py;          out=runs/kggen-full ;;
    esac
    ( $py $script --data data/docs --out $out > $out.log 2>&1; echo "$s exit=$?" ) &
  done
  wait
' _ $SYSTEMS
echo "done: $(date)"
