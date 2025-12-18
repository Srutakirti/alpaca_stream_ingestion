#!/bin/bash
###############################################################################
# Part 2: Setup Kubernetes Resources
#
# Starts Minikube cluster and deploys data infrastructure using Helm charts.
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
#   ./scripts/2_setup_kubernetes.sh
###############################################################################

set -e  # Exit on error

# ============================================================================
# CONFIGURATION
# ============================================================================

# Directory Configuration
STATE_DIR="$HOME/.alpaca_infra_state"
MINIKUBE_MOUNT_DIR="/mnt/mydrive2"
PROJECT_DIR="$HOME/alpaca_stream_ingestion"

# Logging Configuration
LOG_FILE="/tmp/alpaca_setup_$(date +%Y%m%d_%H%M%S).log"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# ============================================================================
# LOGGING FUNCTIONS
# ============================================================================

setup_logging() {
    mkdir -p "$(dirname "$LOG_FILE")"
    touch "$LOG_FILE"

    {
        echo "========================================="
        echo "Part 2: Setup Kubernetes Resources"
        echo "Started: $(date)"
        echo "User: $USER"
        echo "Hostname: $(hostname)"
        echo "========================================="
        echo ""
    } >> "$LOG_FILE"
}

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

    log_info "Deploying Kafka cluster (this will wait until ready)..."

    if ! helm install kafka "$PROJECT_DIR/helm/infrastructure/kafka" \
        -f "$PROJECT_DIR/config/config.yaml" \
        -n kafka \
        --create-namespace \
        --wait \
        --timeout 10m >> "$LOG_FILE" 2>&1; then
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

    log_info "Deploying Apache Pinot (this will wait until ready)..."

    if ! helm install pinot "$PROJECT_DIR/helm/infrastructure/pinot" \
        -f "$PROJECT_DIR/config/config.yaml" \
        -n pinot \
        --create-namespace \
        --wait \
        --timeout 10m >> "$LOG_FILE" 2>&1; then
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

    log_info "Deploying MinIO (this will wait until ready)..."

    if ! helm install minio "$PROJECT_DIR/helm/infrastructure/minio" \
        -f "$PROJECT_DIR/config/config.yaml" \
        -n minio-tenant \
        --create-namespace \
        --wait \
        --timeout 10m >> "$LOG_FILE" 2>&1; then
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
    log_info "========================================="
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
    log_info "Infrastructure Status:"
    log_info "  Kafka:  kubectl get pods -n kafka"
    log_info "  Pinot:  kubectl get pods -n pinot"
    log_info "  MinIO:  kubectl get pods -n minio-tenant"
    log_info ""
    log_info "Next step:"
    log_info "  ./scripts/3_setup_apps.sh"
    log_info ""
    log_info "Log file: $LOG_FILE"
}

# Initialize
mkdir -p "$STATE_DIR"
setup_logging

# Run main
main

exit 0
