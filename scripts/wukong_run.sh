#!/bin/bash
set -euo pipefail

# Function to get absolute paths
abs_path() {
    (cd "$(dirname "$1")" && echo "$(pwd)/$(basename "$1")")
}

# Workspace and Data Directory
if [[ $# -lt 2 ]]; then
    echo "[CRITICAL] Invalid command"
    echo "Usage: scripts/wukong_run.sh <workspace_dir> <data_dir> [--config <CONFIG_FILE>] [--reset]"
    exit 1
fi
WORKSPACE_PATH="$1"
if [[ ! -d "$WORKSPACE_PATH" ]]; then
    echo "[CRITICAL] Workspace directory \""$WORKSPACE_PATH"\" does not exist"
    exit 1
fi
echo "Using workspace directory: \"$WORKSPACE_PATH\""
DATA_PATH="$2"
if [[ ! -d "$DATA_PATH" ]]; then
    echo "[CRITICAL] Data directory \""$DATA_PATH"\" does not exist"
    exit 1
fi
echo "Using data directory: \"$DATA_PATH\""
shift 2

# Config File
CONFIG_PATH="./config/default.toml"
if [[ $# -ge 2 && "$1" == "--config" ]]; then
    CONFIG_PATH="$2"
    if [[ ! -f "$CONFIG_PATH" ]]; then
        echo "[CRITICAL] Configuration file \""$CONFIG_PATH"\" does not exist"
        exit 1
    fi
    echo "Using custom configuration file: \"$CONFIG_PATH\""
    shift 2
else
    echo "Using default configuration file: \"config/default.toml\""
fi

# Reset Flag
RESET_FLAG=""
if [[ $# -ge 1 && "$1" == "--reset" ]]; then
    RESET_FLAG="--reset"
fi

# Env file
if [[ ! -f ".env" ]]; then
    echo "[CRITICAL] The required \".env\" file for environment variables is not present"
    exit 1
fi

# Get absolute paths
WORKSPACE_DIR="$(abs_path "$WORKSPACE_PATH")"
DATA_DIR="$(abs_path "$DATA_PATH")"
CONFIG_FILE="$(abs_path "$CONFIG_PATH")"

# Run the Docker container
IMAGE_NAME="wukong-engine:latest"
docker run --rm \
    --env-file .env \
    -v "$WORKSPACE_DIR:/workspace" \
    -v "$DATA_DIR:/data" \
    -v "$CONFIG_FILE:/config/config.toml" \
    "$IMAGE_NAME" \
    run /workspace /data --config /config/config.toml -v $RESET_FLAG

# Exit if the docker command fails
status=$?
if [[ $status -ne 0 ]]; then
    exit $status
fi

# Script has finished successfully
echo "Done!"