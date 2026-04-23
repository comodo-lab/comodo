#!/usr/bin/env bash
set -eo pipefail

ORG="williamjsmith15"
DATETIME=$(date +%Y%m%d-%H%M%S)

# Ensure a multi-platform builder is ready
docker buildx create --use --name comodo-builder 2>/dev/null || docker buildx use comodo-builder

build_and_push() {
    local name=$1
    local dockerfile=$2

    echo "Building and pushing multi-platform image for $name..."
    
    # Use buildx with --platform and --push
    # This builds for both, creates a manifest, and pushes to Docker Hub in one go.
    docker buildx build \
        --platform linux/amd64,linux/arm64 \
        -t "$ORG/$name:latest" \
        -t "$ORG/$name:$DATETIME" \
        -f "$dockerfile" \
        --push .
}

build_and_push comodo-ui                  ./ui/Dockerfile
build_and_push comodo-controller          ./controller/Dockerfile
build_and_push comodo-mqtt_probe          ./mqtt_probe/Dockerfile
build_and_push comodo-setpoint_controller ./setpoint_controller/Dockerfile
build_and_push comodo-firmware            ./firmware/Dockerfile
