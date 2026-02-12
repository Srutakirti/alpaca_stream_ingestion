#!/bin/bash
###############################################################################
# Part 3: Setup Applications (Config-Driven Version)
#
# Bootstraps application-level resources and deploys processing applications.
# Reads all configuration from config/config.yaml
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
#   ./scripts/3_setup_apps_new.sh
#
#   # With extractor
#   ALPACA_KEY=xxx ALPACA_SECRET=yyy ./scripts/3_setup_apps_new.sh
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

check_binary_exists() {
    command -v "$1" >/dev/null 2>&1
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
MINIKUBE_IP=$(get_yaml_value ".minio.minikube_ip" "$CONFIG_FILE")

# Expand $HOME in STATE_DIR
STATE_DIR="${STATE_DIR_RAW/\$HOME/$HOME}"

# Project directory is the root of the repo
PROJECT_DIR="$PROJECT_ROOT"

# Verify values were loaded
if [ -z "$STATE_DIR" ]; then
    echo "ERROR: Failed to load configuration from $CONFIG_FILE"
    echo "Loaded values:"
    echo "  State Dir: $STATE_DIR"
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
echo "  Project Dir:            $PROJECT_DIR"
echo ""
echo "MinIO Configuration:"
echo "  Minikube IP (from config): $MINIKUBE_IP"
echo ""
echo "Note: Dynamic Minikube IP will be detected at runtime"
echo "========================================="
echo ""

# ============================================================================
# SETUP LOGGING
# ============================================================================

setup_logging() {
    {
        echo "========================================="
        echo "Part 3: Setup Applications (Config-Driven)"
        echo "Started: $(date)"
        echo "User: $USER"
        echo "Hostname: $(hostname)"
        echo "Config file: $CONFIG_FILE"
        echo "========================================="
        echo ""
        echo "Configuration:"
        echo "  State Dir: $STATE_DIR"
        echo "  Project Dir: $PROJECT_DIR"
        echo "  Minikube IP: $MINIKUBE_IP"
        echo ""
    } >> "$LOG_FILE"
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
    log_info ""

    # Run setup script with output to both stdout and log file
    if ! uv run "$PROJECT_DIR/scripts/setup_infrastructure.py" 2>&1 | tee -a "$LOG_FILE"; then
        log_error ""
        log_error "Failed to setup infrastructure resources! Check log: $LOG_FILE"
        exit 1
    fi

    log_info ""

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

    # Get Minikube IP dynamically (fall back to config value)
    local DYNAMIC_IP=$(minikube ip 2>/dev/null || echo "$MINIKUBE_IP")

    # Configure S3 alias
    log_info "Configuring MinIO S3 alias..."
    mc alias set s3 "http://minio-api.${DYNAMIC_IP}.nip.io:80" minio minio123 >> "$LOG_FILE" 2>&1

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
        log_warn "  ALPACA_KEY=xxx ALPACA_SECRET=yyy ./scripts/3_setup_apps_new.sh"
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
    if ! kubectl apply -f "$PROJECT_DIR/extract/app/extractor_deploy.yaml" >> "$LOG_FILE" 2>&1; then
        log_error "Failed to deploy WebSocket extractor! Check log: $LOG_FILE"
        exit 1
    fi

    # Create marker
    touch "$STATE_DIR/extractor_deployed"

    log_info "✓ WebSocket extractor deployed successfully."
}

deploy_kafka_connect() {
    # Check state marker
    if [ -f "$STATE_DIR/kafka_connect_deployed" ]; then
        log_info "Skipping Kafka Connect deployment (marker found)."
        return 0
    fi

    # Check if deployment already exists
    if kubectl get kafkaconnect kafka-connect-cluster -n kafka >/dev/null 2>&1; then
        log_info "Kafka Connect already exists, skipping deployment."
        touch "$STATE_DIR/kafka_connect_deployed"
        return 0
    fi

    log_info "Deploying Kafka Connect with S3 sink connector..."

    # Step 1: Create MinIO bucket first (connector needs it)
    log_info "Creating MinIO bucket for archival..."
    if command -v mc >/dev/null 2>&1 && mc alias list 2>/dev/null | grep -q "^s3"; then
        local BUCKET=$(get_yaml_value ".kafka_connect.s3_sink.bucket" "$CONFIG_FILE")
        if ! mc ls s3/ 2>/dev/null | grep -q "$BUCKET"; then
            if mc mb "s3/$BUCKET" >> "$LOG_FILE" 2>&1; then
                log_info "✓ Bucket '$BUCKET' created"
            else
                log_warn "Failed to create bucket, but continuing..."
            fi
        else
            log_info "✓ Bucket '$BUCKET' already exists"
        fi
    else
        log_warn "MinIO client not configured, skipping bucket creation"
    fi

    # Step 3: Build and push image
    log_info "Building Kafka Connect image..."
    if ! "$PROJECT_DIR/scripts/build_kafka_connect_image.sh" >> "$LOG_FILE" 2>&1; then
        log_error "Failed to build Kafka Connect image"
        log_error "Check log: $LOG_FILE"
        exit 1
    fi
    log_info "✓ Kafka Connect image built and pushed"

    # Step 4: Deploy with Helm
    log_info "Deploying Kafka Connect cluster with Helm..."
    if ! helm install kafka-connect "$PROJECT_DIR/helm/infrastructure/kafka-connect" \
        -f "$CONFIG_FILE" \
        -n kafka \
        --create-namespace >> "$LOG_FILE" 2>&1; then
        log_error "Failed to deploy Kafka Connect with Helm"
        log_error "Check log: $LOG_FILE"
        exit 1
    fi
    log_info "✓ Kafka Connect deployed"

    # Step 5: Wait for pod to be ready
    log_info "Waiting for Kafka Connect pod to be ready (this may take 2-3 minutes)..."
    if kubectl wait --for=condition=Ready pod/kafka-connect-cluster-connect-0 \
        -n kafka --timeout=300s >> "$LOG_FILE" 2>&1; then
        log_info "✓ Kafka Connect pod is ready"
    else
        log_warn "Kafka Connect pod took longer than expected to be ready"
    fi

    # Step 6: Wait for connector to be ready
    log_info "Waiting for S3 sink connector to be ready..."
    local retries=0
    local max_retries=30
    while [ $retries -lt $max_retries ]; do
        local ready=$(kubectl get kafkaconnector s3-sink-raw -n kafka \
            -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || echo "False")

        if [ "$ready" = "True" ]; then
            log_info "✓ S3 sink connector is ready"
            break
        fi

        retries=$((retries + 1))
        if [ $retries -eq $max_retries ]; then
            log_warn "Connector not ready after $max_retries attempts, but continuing..."
            break
        fi

        sleep 2
    done

    # Create marker
    touch "$STATE_DIR/kafka_connect_deployed"

    log_info "✓ Kafka Connect and S3 sink connector deployed successfully."
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

main() {
    log_info "========================================="
    log_info "Part 3: Setting Up Applications"
    log_info "========================================="

    # Change to project directory
    cd "$PROJECT_DIR"

    # Setup application components
    setup_infrastructure_resources
    install_minio_client
    build_and_deploy_kstreams
    deploy_kafka_connect
    deploy_websocket_extractor

    log_info ""
    log_info "========================================="
    log_info "✓ Applications setup completed"
    log_info "========================================="
    log_info ""
    log_info "Deployment Status:"
    log_info "  KStreams:      kubectl get pods -n kafka -l app=kstreams-flatten"
    log_info "  Kafka Connect: kubectl get kafkaconnect -n kafka"
    log_info "  S3 Connector:  kubectl get kafkaconnector -n kafka"
    if [ -n "$ALPACA_KEY" ]; then
        log_info "  Extractor:     kubectl get pods -n kafka -l app=ws-scraper"
    fi
    log_info ""
    log_info "Access Information:"
    local DYNAMIC_IP=$(minikube ip 2>/dev/null || echo "$MINIKUBE_IP")
    log_info "  Kafka:     ${DYNAMIC_IP}:32100"
    log_info "  MinIO API: http://minio-api.${DYNAMIC_IP}.nip.io"
    log_info "  MinIO UI:  http://minio.${DYNAMIC_IP}.nip.io"
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
