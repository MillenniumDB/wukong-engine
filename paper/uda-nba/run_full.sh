#!/usr/bin/env bash
# Build the three graphs (Wukong, LightRAG, GraphRAG) over the full UDA-Bench NBA
# corpus, in parallel, with the same LLM (gpt-5.6-luna, low reasoning effort).
# caffeinate keeps the Mac awake until all three finish.
#
#   ./run_full.sh            # from paper/uda-nba
#
# Logs: runs/<system>-full.log. Each system can be re-run on its own by copying
# its line below.
set -euo pipefail
cd "$(dirname "$0")"
set -a; source ../../.env; set +a

mkdir -p runs

# Wukong: the full corpus is data/docs, whose layout matches workspace/document_collections.json
mkdir -p runs/wukong-full
cp workspace/*.json runs/wukong-full/
cp wukong-config.toml runs/wukong-full/config.toml

# GraphRAG: settings.yaml and the default prompts of `graphrag init`, as used in the full run
# (concurrent_requests raised from 25 to 50: the 8-doc pilot took 17 min, mostly community reports)
if [ ! -d runs/graphrag-full ]; then
  mkdir -p runs/graphrag-full
  cp -r graphrag-config/settings.yaml graphrag-config/prompts runs/graphrag-full/
fi
python3 graphrag_prepare.py full_docs.txt runs/graphrag-full

caffeinate -i bash -c '
  ( /usr/bin/time -p envs/wukong/bin/wukong run runs/wukong-full data/docs \
      --config runs/wukong-full/config.toml -v > runs/wukong-full.log 2>&1 ) &
  ( envs/lightrag/bin/python lightrag_build.py --workdir runs/lightrag-full \
      --manifest full_docs.txt --max-async 16 > runs/lightrag-full.log 2>&1 ) &
  ( /usr/bin/time -p envs/graphrag/bin/graphrag index --root runs/graphrag-full \
      > runs/graphrag-full.log 2>&1 ) &
  wait
'
echo "done: $(date)"
