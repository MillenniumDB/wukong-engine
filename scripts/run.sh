#!/bin/bash
set -euo pipefail

# Function to get absolute paths
abs_path() {
    (cd "$(dirname "$1")" && echo "$(pwd)/$(basename "$1")")
}

# Data Directory
if [[ $# -lt 1 ]]; then
    echo "[CRITICAL_ERROR] Invalid command."
    echo "Usage: scripts/run.sh <data_dir> [--config <CONFIG_FILE>]"
    exit 1
fi
DATA_PATH="$1"
if [[ ! -d "$DATA_PATH" ]]; then
    echo "[CRITICAL_ERROR] Data directory \""$DATA_PATH"\" does not exist."
    exit 1
fi
echo "Using data directory: \"$DATA_PATH\""
shift

# Config File
CONFIG_PATH="./config/default.toml"
if [[ $# -ge 2 && "$1" == "--config" ]]; then
    CONFIG_PATH="$2"
    if [[ ! -f "$CONFIG_PATH" ]]; then
        echo "[CRITICAL_ERROR] Configuration file \""$CONFIG_PATH"\" does not exist."
        exit 1
    fi
    echo "Using custom configuration file: \"$CONFIG_PATH\""
else
    echo "Using default configuration file: \"config/default.toml\""
fi

# Env file
if [[ ! -f ".env" ]]; then
    echo "[CRITICAL_ERROR] The required \".env\" file for environment variables is not present."
    exit 1
fi

# Get absolute paths
DATA_DIR="$(abs_path "$DATA_PATH")"
CONFIG_FILE="$(abs_path "$CONFIG_PATH")"

# Run the Docker container
IMAGE_NAME="wukong-engine:latest"
docker run --rm \
    --env-file .env \
    -v "$DATA_DIR:/data" \
    -v "$CONFIG_FILE:/config/config.toml" \
    "$IMAGE_NAME" \
    /data --config /config/config.toml

# Exit if the docker command fails
status=$?
if [[ $status -ne 0 ]]; then
    exit $status
fi

# Fix permissions (only for Linux and macOS)
if [[ "$OSTYPE" == "msys"* || "$OSTYPE" == "cygwin"* || "$OSTYPE" == "win32"* ]]; then
    echo "Done!"
else
    echo "Fixing Output Files Ownership..."
    sudo chown -R "$(id -u):$(id -g)" "$DATA_DIR"
    echo "Done!"
fi