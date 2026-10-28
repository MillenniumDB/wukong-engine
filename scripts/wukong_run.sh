#!/bin/bash
set -euo pipefail

# Kept for compatibility: same as "scripts/wukong.sh run <workspace_dir> <data_dir> [options]"
exec "$(dirname "$0")/wukong.sh" run "$@"
