#!/bin/bash
###############################################################################
# Part 3: Setup Applications
#
# Bootstraps application-level resources and deploys processing applications.
#
# Components setup:
#   - Kafka topics (from config.yaml)
#   - Pinot schema and table (from load/*.json)
#   - MinIO client (mc) and buckets
#   - KStreams processing application
#   - WebSocket extractor (optional - requires ALPACA_KEY/SECRET)
#
# Prerequisites:
#   - Part 2 completed (Kubernetes resources deployed)
#   - ALPACA_KEY and ALPACA_SECRET env vars (for extractor deployment)
#
# Exit codes:
#   0 - Success
#   1 - Error occurred
#
# Usage:
#   # Without extractor
#   ./scripts/3_setup_apps.sh
#
#   # With extractor
#   ALPACA_KEY=xxx ALPACA_SECRET=yyy ./scripts/3_setup_apps.sh
###############################################################################

set -e  # Exit on error

# ============================================================================
# CONFIGURATION
# ============================================================================

# Directory Configuration
STATE_DIR="$HOME/.alpaca_infra_state"
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
        echo "Part 3: Setup Applications"
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

check_binary_exists() {
    command -v "$1" >/dev/null 2>&1
}

# ============================================================================
# APPLICATION SETUP FUNCTIONS
# ============================================================================

setup_infrastructure_resources() {
    # Check state marker
    if [ -f "$STATE_DIR/infra_resources_setup" ]; then
        log_info "Skipping infrastructure resources setup (marker found)."
        return 0
    fi

    log_info "Creating Kafka topics and Pinot schema/table..."
    log_info "Running setup_infrastructure.py..."

    if ! python3 "$PROJECT_DIR/scripts/setup_infrastructure.py" >> "$LOG_FILE" 2>&1; then
        log_error "Failed to setup infrastructure resources! Check log: $LOG_FILE"
        log_error "Last 20 lines of log:"
        tail -n 20 "$LOG_FILE" >&2
        exit 1
    fi

    # Create marker
    touch "$STATE_DIR/infra_resources_setup"

    log_info "✓ Kafka topics and Pinot schema/table created."
}

install_minio_client() {
    # Check state marker
    if [ -f "$STATE_DIR/minio_client_setup" ]; then
        log_info "Skipping MinIO client setup (marker found)."
        return 0
    fi

    # Check if mc binary already exists and is configured
    if check_binary_exists mc && mc alias list 2>/dev/null | grep -q "s3"; then
        log_info "MinIO client already configured, skipping setup."
        touch "$STATE_DIR/minio_client_setup"
        return 0
    fi

    log_info "Installing MinIO client..."

    # Download mc if not exists
    if ! check_binary_exists mc; then
        wget https://dl.min.io/client/mc/release/linux-amd64/mc -O /tmp/mc >> "$LOG_FILE" 2>&1
        chmod +x /tmp/mc
        sudo mv /tmp/mc /usr/local/bin
    fi

    # Get Minikube IP dynamically
    MINIKUBE_IP=$(minikube ip 2>/dev/null || echo "192.168.49.2")

    # Configure S3 alias
    log_info "Configuring MinIO S3 alias..."
    mc alias set s3 "http://minio-api.${MINIKUBE_IP}.nip.io:80" minio minio123 >> "$LOG_FILE" 2>&1

    # Create buckets
    log_info "Creating S3 buckets..."
    mc mb s3/spark-logs/events >> "$LOG_FILE" 2>&1 || true
    mc mb s3/data >> "$LOG_FILE" 2>&1 || true

    # Create marker
    touch "$STATE_DIR/minio_client_setup"

    log_info "✓ MinIO client setup successfully."
}

build_and_deploy_kstreams() {
    # Check state marker
    if [ -f "$STATE_DIR/kstreams_deployed" ]; then
        log_info "Skipping KStreams deployment (marker found)."
        return 0
    fi

    # Check if deployment already exists
    if kubectl get deployment kstreams-flatten-app -n kafka >/dev/null 2>&1; then
        log_info "KStreams deployment already exists, skipping."
        touch "$STATE_DIR/kstreams_deployed"
        return 0
    fi

    log_info "Building KStreams Docker image..."

    # Switch to Minikube's Docker daemon
    eval $(minikube docker-env)

    # Build KStreams image
    if ! docker build -t kstreams-flatten:1.0.0 \
        -f "$PROJECT_DIR/transform/Kstreams/Dockerfile" \
        "$PROJECT_DIR/transform/Kstreams" >> "$LOG_FILE" 2>&1; then
        log_error "Failed to build KStreams image! Check log: $LOG_FILE"
        log_error "Last 20 lines of log:"
        tail -n 20 "$LOG_FILE" >&2
        exit 1
    fi

    log_info "✓ KStreams image built successfully."

    # Create ConfigMap in kafka namespace for KStreams
    log_info "Creating ConfigMap in kafka namespace..."
    kubectl create configmap app-config \
        --from-file=config.yaml="$PROJECT_DIR/config/config.yaml" \
        -n kafka >> "$LOG_FILE" 2>&1 || true

    # Deploy KStreams application
    log_info "Deploying KStreams application..."
    if ! kubectl apply -f "$PROJECT_DIR/transform/Kstreams/k8s/deployment.yaml" >> "$LOG_FILE" 2>&1; then
        log_error "Failed to deploy KStreams application! Check log: $LOG_FILE"
        exit 1
    fi

    # Create marker
    touch "$STATE_DIR/kstreams_deployed"

    log_info "✓ KStreams application deployed successfully."
}

deploy_websocket_extractor() {
    # Check state marker
    if [ -f "$STATE_DIR/extractor_deployed" ]; then
        log_info "Skipping WebSocket extractor deployment (marker found)."
        return 0
    fi

    # Check if deployment already exists
    if kubectl get deployment websocket-extractor -n kafka >/dev/null 2>&1; then
        log_info "WebSocket extractor already exists, skipping."
        touch "$STATE_DIR/extractor_deployed"
        return 0
    fi

    # Validate required environment variables
    if [ -z "$ALPACA_KEY" ] || [ -z "$ALPACA_SECRET" ]; then
        log_warn "ALPACA_KEY and ALPACA_SECRET not set, skipping extractor deployment."
        log_warn "To deploy extractor later, run:"
        log_warn "  ALPACA_KEY=xxx ALPACA_SECRET=yyy ./scripts/3_setup_apps.sh"
        return 0
    fi

    log_info "Deploying WebSocket extractor..."

    # Create ConfigMap and Secret in kafka namespace
    log_info "Creating Kubernetes ConfigMap and Secret in kafka namespace..."
    kubectl create configmap app-config \
        --from-file=config.yaml="$PROJECT_DIR/config/config.yaml" \
        -n kafka \
        --dry-run=client -o yaml | kubectl apply -f - >> "$LOG_FILE" 2>&1

    kubectl create secret generic alpaca-creds \
        --from-literal=ALPACA_KEY="$ALPACA_KEY" \
        --from-literal=ALPACA_SECRET="$ALPACA_SECRET" \
        -n kafka \
        --dry-run=client -o yaml | kubectl apply -f - >> "$LOG_FILE" 2>&1

    # Build extractor image
    log_info "Building WebSocket extractor image..."
    eval $(minikube docker-env)
    if ! docker build -t ws_scraper:v1.0 \
        -f "$PROJECT_DIR/extract/app/Dockerfile" \
        "$PROJECT_DIR/extract/app" >> "$LOG_FILE" 2>&1; then
        log_error "Failed to build WebSocket extractor image! Check log: $LOG_FILE"
        exit 1
    fi

    # Deploy extractor
    log_info "Deploying WebSocket extractor pod..."
    if ! kubectl apply -f "$PROJECT_DIR/minikube/extractor_deploy/extractor_deploy.yaml" >> "$LOG_FILE" 2>&1; then
        log_error "Failed to deploy WebSocket extractor! Check log: $LOG_FILE"
        exit 1
    fi

    # Create marker
    touch "$STATE_DIR/extractor_deployed"

    log_info "✓ WebSocket extractor deployed successfully."
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

main() {
    log_info "========================================="
    log_info "Part 3: Setting Up Applications"
    log_info "========================================="
    log_info ""

    # Change to project directory
    cd "$PROJECT_DIR"

    # Setup application components
    setup_infrastructure_resources
    install_minio_client
    build_and_deploy_kstreams
    deploy_websocket_extractor

    log_info ""
    log_info "========================================="
    log_info "✓ Applications setup completed"
    log_info "========================================="
    log_info ""
    log_info "Deployment Status:"
    log_info "  KStreams:  kubectl get pods -n kafka -l app=kstreams-flatten"
    if [ -n "$ALPACA_KEY" ]; then
        log_info "  Extractor: kubectl get pods -n kafka -l app=websocket-extractor"
    fi
    log_info ""
    log_info "Access Information:"
    MINIKUBE_IP=$(minikube ip 2>/dev/null || echo "192.168.49.2")
    log_info "  Kafka:     ${MINIKUBE_IP}:32100"
    log_info "  MinIO API: http://minio-api.${MINIKUBE_IP}.nip.io"
    log_info "  MinIO UI:  http://minio.${MINIKUBE_IP}.nip.io"
    log_info "  Pinot:     kubectl port-forward -n pinot svc/pinot-pinot-chart-controller 9000:9000"
    log_info ""
    log_info "Log file: $LOG_FILE"
}

# Initialize
mkdir -p "$STATE_DIR"
setup_logging

# Run main
main

exit 0
