#!/usr/bin/env bash
# M1 full run: every system on the 101 scored questions, in parallel, with a budget watchdog.
set -uo pipefail
M=$HOME/wukong-runs/wukong-engine/paper/uda-nba/m1
E=$HOME/wukong-runs/m1/envs
L=$HOME/wukong-runs/m1/work/logs
mkdir -p "$L"
OPENAI_API_KEY="$(security find-generic-password -a "$USER" -s openai-wukong -w 2>/dev/null)" || true
[[ -n ${OPENAI_API_KEY:-} ]] || { echo "No key" >&2; exit 1; }
export OPENAI_API_KEY
cd "$M"
$E/harness/bin/python sys_floor.py > "$L/floor.log" 2>&1 &
$E/harness/bin/python sys_wukong.py > "$L/wukong.log" 2>&1 &
$E/lightrag/bin/python sys_lightrag.py > "$L/lightrag.log" 2>&1 &
$E/graphrag/bin/python sys_graphrag.py --methods local > "$L/graphrag.log" 2>&1 &
# Watchdog: stop every system if M1's total spend (all usage logs) passes $14 (cap $15)
( while pgrep -f "sys_(floor|wukong|lightrag|graphrag).py" >/dev/null; do
    spent=$($E/harness/bin/python -c "import sys; sys.path.insert(0, '$M'); from common import WORK, cost; print(round(sum(cost(p) for p in (WORK / 'usage').glob('*.jsonl')), 2))")
    echo "$(date +%H:%M) spent \$$spent" >> "$L/watchdog.log"
    if python3 -c "import sys; sys.exit(0 if $spent > 14 else 1)"; then
        echo "$(date +%H:%M) BUDGET STOP at \$$spent" >> "$L/watchdog.log"; pkill -f "sys_(floor|wukong|lightrag|graphrag).py"
    fi
    sleep 60
  done ) &
wait
echo "=== M1 systems finished $(date +%H:%M)" >> "$L/watchdog.log"
