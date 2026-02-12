#!/bin/bash
###############################################################################
# Build Kafka Connect Image (Config-Driven)
#
# Builds custom Kafka Connect image with Aiven S3 connector and pushes to
# Minikube's local registry. Reads configuration from config/config.yaml.
#
# Prerequisites:
#   - Minikube running
#   - Minikube registry addon enabled
#   - yq installed (auto-installs if missing)
#
# Exit codes:
#   0 - Success
#   1 - Error occurred
#
# Usage:
#   ./scripts/build_kafka_connect_image.sh
###############################################################################

set -e  # Exit on error

# ============================================================================
# YQ INSTALLATION
# ============================================================================

ensure_yq_installed() {
    # Check if yq is already available
    if command -v yq >/dev/null 2>&1; then
        return 0
    fi

    echo "yq not found, installing..."

    # Create ~/.local/bin if it doesn't exist
    mkdir -p "$HOME/.local/bin"

    # Download yq binary
    local YQ_VERSION="v4.44.1"
    local YQ_URL="https://github.com/mikefarah/yq/releases/download/${YQ_VERSION}/yq_linux_amd64"

    if ! curl -L "$YQ_URL" -o "$HOME/.local/bin/yq" 2>/dev/null; then
        echo "ERROR: Failed to download yq from $YQ_URL"
        exit 1
    fi

    chmod +x "$HOME/.local/bin/yq"
    export PATH="$HOME/.local/bin:$PATH"

    echo "yq installed successfully to ~/.local/bin/yq"
}

# ============================================================================
# CONFIGURATION
# ============================================================================

# Determine script location and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="$PROJECT_ROOT/config/config.yaml"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Verify config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}ERROR:${NC} Config file not found: $CONFIG_FILE"
    exit 1
fi

# ============================================================================
# YAML PARSING FUNCTIONS
# ============================================================================

get_yaml_value() {
    local path="$1"
    local config_file="$2"
    yq eval "$path" "$config_file" 2>/dev/null
}

# Ensure yq is installed
ensure_yq_installed

# Load configuration
IMAGE_REPOSITORY=$(get_yaml_value ".kafka_connect.image.repository" "$CONFIG_FILE")
IMAGE_TAG=$(get_yaml_value ".kafka_connect.image.tag" "$CONFIG_FILE")
IMAGE_FULL="${IMAGE_REPOSITORY}:${IMAGE_TAG}"

# Verify values were loaded
if [ -z "$IMAGE_REPOSITORY" ] || [ -z "$IMAGE_TAG" ]; then
    echo -e "${RED}ERROR:${NC} Failed to load image configuration from $CONFIG_FILE"
    echo "Loaded values:"
    echo "  Repository: $IMAGE_REPOSITORY"
    echo "  Tag: $IMAGE_TAG"
    exit 1
fi

# Print configuration
echo ""
echo "========================================="
echo "Build Kafka Connect Image"
echo "========================================="
echo ""
echo "Configuration:"
echo "  Config File:  $CONFIG_FILE"
echo "  Image:        $IMAGE_FULL"
echo "  Build Dir:    $PROJECT_ROOT/load/kafka-connect"
echo ""
echo "========================================="
echo ""

# ============================================================================
# BUILD AND PUSH
# ============================================================================

main() {
    # Step 1: Switch to Minikube's Docker daemon
    echo -e "${BLUE}==>${NC} Switching to Minikube's Docker daemon..."
    eval $(minikube docker-env)
    echo -e "${GREEN}✓${NC} Using Minikube's Docker daemon"
    echo ""

    # Step 2: Build the image
    echo -e "${BLUE}==>${NC} Building Kafka Connect image..."
    echo "This may take a few minutes on first build..."
    echo ""

    if ! docker build \
        -t "$IMAGE_FULL" \
        -f "$PROJECT_ROOT/load/kafka-connect/Dockerfile" \
        "$PROJECT_ROOT/load/kafka-connect"; then
        echo ""
        echo -e "${RED}ERROR:${NC} Failed to build image"
        exit 1
    fi

    echo ""
    echo -e "${GREEN}✓${NC} Image built successfully: $IMAGE_FULL"
    echo ""
    echo "Image is available in Minikube's Docker daemon (imagePullPolicy: IfNotPresent)"
    echo ""

    # Summary
    echo "========================================="
    echo -e "${GREEN}✓ Build Complete${NC}"
    echo "========================================="
    echo ""
    echo "Image: $IMAGE_FULL"
    echo ""
    echo "Next steps:"
    echo "  Deploy with Helm:"
    echo "    helm install kafka-connect ./helm/infrastructure/kafka-connect -f config/config.yaml -n kafka"
    echo ""
    echo "  Or apply manually:"
    echo "    kubectl apply -f load/kafka-connect/kafkaconnect.yaml"
    echo "    kubectl apply -f load/kafka-connect/s3-sink-connector.yaml"
    echo ""
}

# Run main function
main

exit 0
