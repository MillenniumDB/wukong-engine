#!/bin/bash
set -euo pipefail

# Build the Docker image
IMAGE_NAME="wukong-engine:latest"
echo "Building Docker image: '$IMAGE_NAME'"
docker build -t "$IMAGE_NAME" .
echo "Docker image '$IMAGE_NAME' built successfully!"