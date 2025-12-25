#!/bin/bash
###############################################################################
# Part 2: Setup Kubernetes Resources (Config-Driven Version)
#
# Starts Minikube cluster and deploys data infrastructure using Helm charts.
# Reads all configuration from config/config.yaml
#
# Components deployed:
#   - Minikube (Kubernetes cluster)
#   - Kafka (Strimzi Operator)
#   - Apache Pinot (Real-time analytics)
#   - MinIO (S3-compatible object storage)
#
# Prerequisites:
#   - Part 1 completed (dependencies installed)
#   - Docker working without sudo
#
# Exit codes:
#   0 - Success
#   1 - Error occurred
#
# Usage:
#   ./scripts/2_setup_kubernetes_new.sh
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
        echo "Please install yq manually:"
        echo "  sudo wget -qO /usr/local/bin/yq https://github.com/mikefarah/yq/releases/download/${YQ_VERSION}/yq_linux_amd64"
        echo "  sudo chmod +x /usr/local/bin/yq"
        exit 1
    fi

    chmod +x "$HOME/.local/bin/yq"

    # Add to PATH for current session
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

# Logging Configuration
LOG_FILE="/tmp/alpaca_setup_$(date +%Y%m%d_%H%M%S).log"
mkdir -p "$(dirname "$LOG_FILE")"
touch "$LOG_FILE"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Verify config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "ERROR: Config file not found: $CONFIG_FILE"
    exit 1
fi

# ============================================================================
# LOGGING FUNCTIONS (defined early for use in ensure_yq_installed)
# ============================================================================

log_info() {
    local msg="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${GREEN}[INFO]${NC} $msg"
    echo "[$timestamp] [INFO] $msg" >> "$LOG_FILE"
}

log_warn() {
    local msg="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${YELLOW}[WARN]${NC} $msg"
    echo "[$timestamp] [WARN] $msg" >> "$LOG_FILE"
}

log_error() {
    local msg="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo -e "${RED}[ERROR]${NC} $msg"
    echo "[$timestamp] [ERROR] $msg" >> "$LOG_FILE"
}

# ============================================================================
# YAML PARSING FUNCTIONS
# ============================================================================

get_yaml_value() {
    local path="$1"         # e.g., ".directories.state_dir"
    local config_file="$2"

    yq eval "$path" "$config_file" 2>/dev/null
}

# Ensure yq is installed before parsing YAML
ensure_yq_installed

# Directory Configuration - Read from YAML
STATE_DIR_RAW=$(get_yaml_value ".directories.state_dir" "$CONFIG_FILE")
MINIKUBE_MOUNT_DIR=$(get_yaml_value ".directories.minikube_mount_dir" "$CONFIG_FILE")

# Expand $HOME in STATE_DIR
STATE_DIR="${STATE_DIR_RAW/\$HOME/$HOME}"

# Project directory is the root of the repo
PROJECT_DIR="$PROJECT_ROOT"

# Verify values were loaded
if [ -z "$STATE_DIR" ] || [ -z "$MINIKUBE_MOUNT_DIR" ]; then
    echo "ERROR: Failed to load configuration from $CONFIG_FILE"
    echo "Loaded values:"
    echo "  State Dir: $STATE_DIR"
    echo "  Minikube Mount Dir: $MINIKUBE_MOUNT_DIR"
    exit 1
fi

# Print loaded configuration
echo ""
echo "========================================="
echo "Configuration Loaded from: $CONFIG_FILE"
echo "========================================="
echo ""
echo "Directory Configuration:"
echo "  State Dir:              $STATE_DIR"
echo "  Minikube Mount Dir:     $MINIKUBE_MOUNT_DIR"
echo "  Project Dir:            $PROJECT_DIR"
echo ""
echo "========================================="
echo ""

# ============================================================================
# SETUP LOGGING
# ============================================================================

setup_logging() {
    {
        echo "========================================="
        echo "Part 2: Setup Kubernetes Resources (Config-Driven)"
        echo "Started: $(date)"
        echo "User: $USER"
        echo "Hostname: $(hostname)"
        echo "Config file: $CONFIG_FILE"
        echo "========================================="
        echo ""
        echo "Configuration:"
        echo "  State Dir: $STATE_DIR"
        echo "  Minikube Mount Dir: $MINIKUBE_MOUNT_DIR"
        echo "  Project Dir: $PROJECT_DIR"
        echo ""
    } >> "$LOG_FILE"
}

# ============================================================================
# KUBERNETES SETUP FUNCTIONS
# ============================================================================

minikube_start() {
    # Check state marker
    if [ -f "$STATE_DIR/minikube_started" ]; then
        log_info "Skipping Minikube start (marker found)."
        return 0
    fi

    # Check if minikube is already running
    if minikube status | grep -q "Running" 2>/dev/null; then
        log_info "Minikube is already running, skipping start."
        touch "$STATE_DIR/minikube_started"
        return 0
    fi

    # Verify docker access
    if ! docker info >/dev/null 2>&1; then
        log_error "Failed to run docker command without sudo."
        log_error "Please run Part 1 first and activate docker group."
        exit 1
    fi

    log_info "Starting Minikube..."
    log_info "Mount: $MINIKUBE_MOUNT_DIR -> /mnt"

    if ! minikube start --mount --mount-string="$MINIKUBE_MOUNT_DIR:/mnt" >> "$LOG_FILE" 2>&1; then
        log_error "Minikube failed to start! Check log: $LOG_FILE"
        log_error "Last 20 lines of log:"
        tail -n 20 "$LOG_FILE" >&2
        exit 1
    fi

    # Enable ingress addon for MinIO
    log_info "Enabling ingress addon..."
    if ! minikube addons enable ingress >> "$LOG_FILE" 2>&1; then
        log_error "Failed to enable ingress addon! Check log: $LOG_FILE"
        exit 1
    fi

    # Wait for ingress controller to be ready
    log_info "Waiting for nginx ingress controller to be ready..."
    if ! kubectl wait --namespace ingress-nginx \
        --for=condition=ready pod \
        --selector=app.kubernetes.io/component=controller \
        --timeout=300s >> "$LOG_FILE" 2>&1; then
        log_warn "Ingress controller took longer than expected, but continuing..."
    else
        log_info "✓ Ingress controller is ready"
    fi

    # Create marker
    touch "$STATE_DIR/minikube_started"

    log_info "Minikube started successfully."
}

deploy_kafka() {
    # Check state marker
    if [ -f "$STATE_DIR/kafka_deployed" ]; then
        log_info "Skipping Kafka deployment (marker found)."
        return 0
    fi

    # Check if Kafka namespace exists
    if kubectl get namespace kafka >/dev/null 2>&1; then
        log_info "Kafka namespace already exists, skipping deployment."
        touch "$STATE_DIR/kafka_deployed"
        return 0
    fi

    log_info "Deploying Kafka cluster..."

    if ! helm install kafka "$PROJECT_DIR/helm/infrastructure/kafka" \
        -f "$PROJECT_DIR/config/config.yaml" \
        -n kafka \
        --create-namespace >> "$LOG_FILE" 2>&1; then
        log_error "Failed to deploy Kafka! Check log: $LOG_FILE"
        log_error "Last 20 lines of log:"
        tail -n 20 "$LOG_FILE" >&2
        exit 1
    fi

    # Create marker
    touch "$STATE_DIR/kafka_deployed"

    log_info "✓ Kafka deployed successfully."
}

deploy_pinot() {
    # Check state marker
    if [ -f "$STATE_DIR/pinot_deployed" ]; then
        log_info "Skipping Pinot deployment (marker found)."
        return 0
    fi

    # Check if Pinot namespace exists
    if kubectl get namespace pinot >/dev/null 2>&1; then
        log_info "Pinot namespace already exists, skipping deployment."
        touch "$STATE_DIR/pinot_deployed"
        return 0
    fi

    log_info "Deploying Apache Pinot..."

    if ! helm install pinot "$PROJECT_DIR/helm/infrastructure/pinot" \
        -f "$PROJECT_DIR/config/config.yaml" \
        -n pinot \
        --create-namespace >> "$LOG_FILE" 2>&1; then
        log_error "Failed to deploy Pinot! Check log: $LOG_FILE"
        log_error "Last 20 lines of log:"
        tail -n 20 "$LOG_FILE" >&2
        exit 1
    fi

    # Create marker
    touch "$STATE_DIR/pinot_deployed"

    log_info "✓ Pinot deployed successfully."
}

deploy_minio() {
    # Check state marker
    if [ -f "$STATE_DIR/minio_deployed" ]; then
        log_info "Skipping MinIO deployment (marker found)."
        return 0
    fi

    # Check if MinIO namespace exists
    if kubectl get namespace minio-tenant >/dev/null 2>&1; then
        log_info "MinIO namespace already exists, skipping deployment."
        touch "$STATE_DIR/minio_deployed"
        return 0
    fi

    log_info "Deploying MinIO..."

    if ! helm install minio "$PROJECT_DIR/helm/infrastructure/minio" \
        -f "$PROJECT_DIR/config/config.yaml" \
        -n minio-tenant \
        --create-namespace >> "$LOG_FILE" 2>&1; then
        log_error "Failed to deploy MinIO! Check log: $LOG_FILE"
        log_error "Last 20 lines of log:"
        tail -n 20 "$LOG_FILE" >&2
        exit 1
    fi

    # Create marker
    touch "$STATE_DIR/minio_deployed"

    log_info "✓ MinIO deployed successfully."
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

main() {
    log_info "========================================="
    log_info "Part 2: Setting Up Kubernetes"
    log_info "Config-Driven Version"
    log_info "========================================="
    log_info ""
    log_info "Configuration loaded from: $CONFIG_FILE"
    log_info ""

    # Change to project directory
    cd "$PROJECT_DIR"

    # Deploy infrastructure
    minikube_start
    deploy_kafka
    deploy_pinot
    deploy_minio

    log_info ""
    log_info "========================================="
    log_info "✓ Kubernetes resources deployed"
    log_info "========================================="
    log_info ""
    log_info "Deployments are starting in the background."
    log_info ""
    log_info "Check deployment status:"
    log_info "  Kafka:  kubectl get pods -n kafka -w"
    log_info "  Pinot:  kubectl get pods -n pinot -w"
    log_info "  MinIO:  kubectl get pods -n minio-tenant -w"
    log_info ""
    log_info "Or check all at once:"
    log_info "  watch 'kubectl get pods -n kafka && echo && kubectl get pods -n pinot && echo && kubectl get pods -n minio-tenant'"
    log_info ""
    log_warn "IMPORTANT: Wait for all pods to be Running/Ready before proceeding!"
    log_info ""
    log_info "When all pods are ready, continue with:"
    log_info "  ./scripts/3_setup_apps_new.sh"
    log_info ""
    log_info "Log file: $LOG_FILE"
}

# Initialize
mkdir -p "$STATE_DIR"
setup_logging

# Run main
main

exit 0
