#!/bin/bash
set -euo pipefail

# Runs a WUKONG command inside the Docker container, mounting the directories and configuration file it is given.
# Options other than --config are passed to the command as they are.

IMAGE_NAME="wukong-engine:latest"

usage() {
    echo "Usage: scripts/wukong.sh run    <workspace_dir> <data_dir> [--config <CONFIG_FILE>] [--reset] [--until-done] [-v|-vv]"
    echo "       scripts/wukong.sh plan   <workspace_dir> <data_dir> [--config <CONFIG_FILE>] [--reset] [-v|-vv]"
    echo "       scripts/wukong.sh status <workspace_dir>"
    echo "       scripts/wukong.sh reset  <workspace_dir> [--from <STEP>] [--yes] [-v|-vv]"
    echo "Run 'scripts/wukong.sh <command> --help' for the details of a command."
}

# Function to get absolute paths
abs_path() {
    (cd "$(dirname "$1")" && echo "$(pwd)/$(basename "$1")")
}

# Container options: --init forwards stop signals to the engine, so that "docker stop" and Ctrl+C end long runs
# promptly, and stdin stays open so that confirmation prompts can be answered, through a terminal only if there is one
CACHE_DIR="$HOME/.cache/wukong-engine"
DOCKER_ARGS=(
    --rm --init -i
    --user "$(id -u):$(id -g)"
    -e HOME=/home/app
    -e XDG_CACHE_HOME=/home/app/.cache
)
if [[ -t 0 && -t 1 ]]; then
    DOCKER_ARGS+=(-t)
fi

# Command
if [[ $# -lt 1 ]]; then
    echo "[CRITICAL] Invalid command"
    usage
    exit 1
fi
COMMAND="$1"
shift

# Help needs nothing mounted
for arg in "$COMMAND" "$@"; do
    if [[ "$arg" == "-h" || "$arg" == "--help" ]]; then
        exec docker run "${DOCKER_ARGS[@]}" "$IMAGE_NAME" "$COMMAND" "$@"
    fi
done

case "$COMMAND" in
    run | plan)
        DIRECTORIES=2
        USES_CONFIG=true
        ;;
    reset)
        DIRECTORIES=1
        USES_CONFIG=false
        ;;
    status)
        DIRECTORIES=1
        USES_CONFIG=false
        ;;
    *)
        echo "[CRITICAL] Unknown command \"$COMMAND\""
        usage
        exit 1
        ;;
esac
if [[ $# -lt $DIRECTORIES ]]; then
    echo "[CRITICAL] Invalid command"
    usage
    exit 1
fi
CLI_ARGS=("$COMMAND")

# Workspace Directory
WORKSPACE_PATH="$1"
if [[ ! -d "$WORKSPACE_PATH" ]]; then
    echo "[CRITICAL] Workspace directory \"$WORKSPACE_PATH\" does not exist"
    exit 1
fi
echo "Using workspace directory: \"$WORKSPACE_PATH\""
DOCKER_ARGS+=(-v "$(abs_path "$WORKSPACE_PATH"):/workspace")
CLI_ARGS+=(/workspace)
shift

# Data Directory
if [[ $DIRECTORIES -eq 2 ]]; then
    DATA_PATH="$1"
    if [[ ! -d "$DATA_PATH" ]]; then
        echo "[CRITICAL] Data directory \"$DATA_PATH\" does not exist"
        exit 1
    fi
    echo "Using data directory: \"$DATA_PATH\""
    DOCKER_ARGS+=(-v "$(abs_path "$DATA_PATH"):/data")
    CLI_ARGS+=(/data)
    shift
fi

# Options
CONFIG_PATH=""
VERBOSE=false
while [[ $# -gt 0 ]]; do
    if [[ "$USES_CONFIG" == true && "$1" == "--config" ]]; then
        if [[ $# -lt 2 ]]; then
            echo "[CRITICAL] The --config option requires a configuration file"
            exit 1
        fi
        CONFIG_PATH="$2"
        shift 2
        continue
    fi
    if [[ "$USES_CONFIG" == true && "$1" == --config=* ]]; then
        CONFIG_PATH="${1#--config=}"
    elif [[ "$1" =~ ^(-v+|--verbose)$ ]]; then
        VERBOSE=true
        CLI_ARGS+=("$1")
    else
        CLI_ARGS+=("$1")
    fi
    shift
done

# Runs show info logs unless another verbosity is given
if [[ "$COMMAND" == "run" && "$VERBOSE" == false ]]; then
    CLI_ARGS+=(-v)
fi

# Config File
if [[ "$USES_CONFIG" == true ]]; then
    if [[ -z "$CONFIG_PATH" ]]; then
        CONFIG_PATH="./config/default.toml"
        echo "Using default configuration file: \"config/default.toml\""
    else
        echo "Using custom configuration file: \"$CONFIG_PATH\""
    fi
    if [[ ! -f "$CONFIG_PATH" ]]; then
        echo "[CRITICAL] Configuration file \"$CONFIG_PATH\" does not exist"
        exit 1
    fi
    DOCKER_ARGS+=(-v "$(abs_path "$CONFIG_PATH"):/config/config.toml")
    CLI_ARGS+=(--config /config/config.toml)
fi

# Env file: required to run, and read by a reset to cancel the batches still running at the provider
if [[ "$COMMAND" == "run" || "$COMMAND" == "plan" ]]; then
    if [[ ! -f ".env" ]]; then
        echo "[CRITICAL] The required \".env\" file for environment variables is not present"
        exit 1
    fi
    DOCKER_ARGS+=(--env-file .env)
elif [[ "$COMMAND" == "reset" ]]; then
    if [[ -f ".env" ]]; then
        DOCKER_ARGS+=(--env-file .env)
    else
        echo "[WARNING] No \".env\" file is present, so batches still running at the provider can't be cancelled"
    fi
fi

# Cache directory
mkdir -p "$CACHE_DIR"
DOCKER_ARGS+=(-v "$CACHE_DIR:/home/app/.cache")

# Run the Docker container
exec docker run "${DOCKER_ARGS[@]}" "$IMAGE_NAME" "${CLI_ARGS[@]}"
