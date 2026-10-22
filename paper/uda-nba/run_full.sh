#!/usr/bin/env bash
# Build the LightRAG and GraphRAG graphs over the full UDA-Bench NBA corpus, in parallel, with
# the same LLM as Wukong (gpt-5.6-luna, low reasoning effort). Wukong's graphs are built by
# run_x6.sh (variant s4, the NBA schema of the paper).
#
#   ./run_full.sh            # from paper/uda-nba
#
# Logs: runs/<system>-full.log. Each system can be re-run on its own by copying
# its line below.
set -euo pipefail
cd "$(dirname "$0")"
set -a; [[ -f ../../.env ]] && source ../../.env; set +a  # or export OPENAI_API_KEY yourself
KEEP_AWAKE=$(command -v caffeinate >/dev/null && echo 'caffeinate -i' || true)  # macOS: keep the machine awake

mkdir -p runs

# GraphRAG: settings.yaml and the default prompts of `graphrag init`, as used in the full run
# (concurrent_requests raised from 25 to 50: the 8-doc pilot took 17 min, mostly community reports)
if [ ! -d runs/graphrag-full ]; then
  mkdir -p runs/graphrag-full
  cp -r graphrag-config/settings.yaml graphrag-config/prompts runs/graphrag-full/
fi
python3 graphrag_prepare.py full_docs.txt runs/graphrag-full

$KEEP_AWAKE bash -c '
  ( envs/lightrag/bin/python lightrag_build.py --workdir runs/lightrag-full \
      --manifest full_docs.txt --max-async 16 > runs/lightrag-full.log 2>&1 ) &
  ( /usr/bin/time -p envs/graphrag/bin/graphrag index --root runs/graphrag-full \
      > runs/graphrag-full.log 2>&1 ) &
  wait
'
echo "done: $(date)"
