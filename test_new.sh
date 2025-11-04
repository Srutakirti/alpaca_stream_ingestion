#!/bin/bash
###############################################################################
# Alpaca Stream Ingestion - Infrastructure Setup Script
#
# This script automates the setup of a complete data engineering stack for
# real-time financial data streaming and analytics.
#
# Components installed:
#   - Docker, UV, Minikube, Helm, Kubectl, Java, Spark
#   - Kafka (Strimzi), Apache Pinot, MinIO
#   - WebSocket extractor, Spark streaming jobs
#
# Prerequisites:
#   - Ubuntu Linux
#   - sudo access
#   - ALPACA_KEY and ALPACA_SECRET environment variables (for --setup-app)
#
# For usage information, run: ./test_new.sh --help
###############################################################################

set -e  # Exit on error

# ============================================================================
# CONFIGURATION SECTION
# ============================================================================

# Version Configuration
DOCKER_VERSION="5:28.5.1-1~ubuntu.25.10~questing"
MINIKUBE_VERSION="v1.36.0"
KUBECTL_VERSION="v1.34.0"
HELM_VERSION="v3.19.0"
SPARK_VERSION="3.5.1"
HADOOP_VERSION="3"
JAVA_VERSION="openjdk-17-jdk"
UV_VERSION="0.9.2"

# Directory Configuration
STATE_DIR="$HOME/.alpaca_infra_state"
MINIKUBE_MOUNT_DIR="/mnt/mydrive2"
MINIKUBE_MOUNT_MINIO="$MINIKUBE_MOUNT_DIR/minio"
MINIKUBE_MOUNT_SHR="$MINIKUBE_MOUNT_DIR/shr"

# Minikube Resource Configuration
MINIKUBE_CPU=4
MINIKUBE_MEMORY=31000

# Paths
SPARK_HOME="$HOME/spark-$SPARK_VERSION"
PROJECT_DIR="$HOME/alpaca_stream_ingestion"

# Logging Configuration
LOG_FILE="/tmp/alpaca_setup_$(date +%Y%m%d_%H%M%S).log"

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Docker group activation flag (for re-exec)
DOCKER_GROUP_ACTIVATED="${DOCKER_GROUP_ACTIVATED:-0}"

# ============================================================================
# LOGGING FUNCTIONS
# ============================================================================

###############################################################################
# Setup Logging
#
# Initializes the log file and writes header information.
# Called once at the start of script execution.
###############################################################################
setup_logging() {
    mkdir -p "$(dirname "$LOG_FILE")"
    touch "$LOG_FILE"

    {
        echo "========================================="
        echo "Alpaca Infrastructure Setup Log"
        echo "Started: $(date)"
        echo "User: $USER"
        echo "Hostname: $(hostname)"
        echo "========================================="
        echo ""
    } >> "$LOG_FILE"
}

###############################################################################
# Log Info Message
#
# Logs an informational message to both stdout (with color) and log file
# (with timestamp).
#
# Arguments:
#   $1 - Message to log
###############################################################################
log_info() {
    local msg="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    # To stdout with color
    echo -e "${GREEN}[INFO]${NC} $msg"

    # To file with timestamp
    echo "[$timestamp] [INFO] $msg" >> "$LOG_FILE"
}

###############################################################################
# Log Warning Message
#
# Logs a warning message to both stdout (with color) and log file
# (with timestamp).
#
# Arguments:
#   $1 - Message to log
###############################################################################
log_warn() {
    local msg="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    # To stdout with color
    echo -e "${YELLOW}[WARN]${NC} $msg"

    # To file with timestamp
    echo "[$timestamp] [WARN] $msg" >> "$LOG_FILE"
}

###############################################################################
# Log Error Message
#
# Logs an error message to both stdout (with color) and log file
# (with timestamp).
#
# Arguments:
#   $1 - Message to log
###############################################################################
log_error() {
    local msg="$1"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    # To stdout with color
    echo -e "${RED}[ERROR]${NC} $msg"

    # To file with timestamp
    echo "[$timestamp] [ERROR] $msg" >> "$LOG_FILE"
}

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

###############################################################################
# Show Help
#
# Displays usage information and available command-line options.
###############################################################################
show_help() {
    printf '%b\n' "
${GREEN}Alpaca Stream Ingestion - Infrastructure Setup Script${NC}

${YELLOW}USAGE:${NC}
    $0 [OPTIONS]

${YELLOW}OPTIONS:${NC}
    ${GREEN}--install-infra${NC}       Install base infrastructure components:
                         - Docker, UV, Minikube, Helm, Kubectl, Java, Spark

    ${GREEN}--setup-k8s${NC}           Setup Kubernetes and deploy DE tools:
                         - Start Minikube, build Spark images
                         - Deploy Kafka, Pinot, MinIO

    ${GREEN}--install-mc${NC}          Install and configure MinIO client:
                         - Download mc binary
                         - Configure S3 alias
                         - Create required buckets

    ${GREEN}--setup-app${NC}           Setup application components:
                         - Create Kafka topics
                         - Create Pinot tables
                         - Deploy WebSocket extractor
                         - Setup Spark resources

    ${GREEN}--all${NC}                 Run complete setup (all of the above)

    ${GREEN}-h, --help${NC}            Show this help message

${YELLOW}EXAMPLES:${NC}
    # Full setup (requires ALPACA_KEY and ALPACA_SECRET env vars)
    ALPACA_KEY=xxx ALPACA_SECRET=yyy $0 --all

    # Install only infrastructure components
    $0 --install-infra

    # Setup Kubernetes tools and application
    $0 --setup-k8s --setup-app

    # Continue from a partial installation
    $0 --install-mc --setup-app

${YELLOW}NOTES:${NC}
    - State is tracked in: $STATE_DIR
    - Logs are written to: $LOG_FILE
    - Script is idempotent - safe to re-run
    - Requires ALPACA_KEY and ALPACA_SECRET for --setup-app
    - Requires sudo access for system installations

${YELLOW}COMPONENTS:${NC}
    Infrastructure:  Docker, UV, Minikube, Helm, Kubectl, Java, Spark
    Data Stack:      Kafka (Strimzi), Apache Pinot, MinIO
    Application:     WebSocket Extractor, Spark Streaming Jobs

For more information, see the project documentation.
"
}

###############################################################################
# Check Binary Exists
#
# Checks if a binary/command exists in the system PATH.
#
# Arguments:
#   $1 - Binary name to check
#
# Returns:
#   0 if binary exists, 1 otherwise
###############################################################################
check_binary_exists() {
    command -v "$1" >/dev/null 2>&1
}

# ============================================================================
# DOCKER GROUP HANDLING (Re-exec mechanism)
# ============================================================================

###############################################################################
# Ensure Docker Group Without Sudo
#
# Ensures the current user can run docker commands without sudo.
# If the user is in the docker group but the session doesn't reflect it,
# this function will re-exec the script under the docker group using 'sg'.
#
# This solves the problem where adding a user to docker group requires
# logout/login to take effect.
#
# Idempotency:
#   - Checks if docker already works without sudo
#   - Uses DOCKER_GROUP_ACTIVATED flag to prevent infinite re-exec loops
#
# Side effects:
#   - May add user to docker group (requires sudo)
#   - May re-exec the entire script (current process is replaced)
###############################################################################
ensure_docker_group_no_sudo() {
    # If docker already usable without sudo, nothing to do
    if docker info >/dev/null 2>&1; then
        log_info "Docker usable without sudo"
        return 0
    fi

    # Prevent infinite re-exec loops
    if [ "$DOCKER_GROUP_ACTIVATED" = "1" ]; then
        log_error "Docker still not usable without sudo after attempting group activation."
        return 1
    fi

    # If user not in docker group, add them (requires sudo)
    if id -nG "$USER" | tr ' ' '\n' | grep -xq docker; then
        log_info "User $USER is already in docker group (session doesn't reflect it yet)."
    else
        log_info "Adding user $USER to docker group (requires sudo)..."
        if ! sudo usermod -aG docker "$USER"; then
            log_error "Failed to add $USER to docker group via sudo. Cannot continue without manual fix."
            return 1
        fi
        log_info "Added $USER to docker group."
    fi

    # Mark that we're re-execing so we don't loop, then re-exec the script with the docker group active.
    export DOCKER_GROUP_ACTIVATED=1

    # Build a safe quoted command and re-exec under docker group.
    # Use sg if available (POSIX-safe); newgrp fallback if sg missing.
    CMD=$(printf '%q ' "$0" "$@")

    if command -v sg >/dev/null 2>&1; then
        log_info "Re-executing script with docker group permissions..."
        exec sg docker -c "$CMD"
    else
        # newgrp - not always available with -c on all distros; we try it as a fallback
        if newgrp docker -c "$CMD" >/dev/null 2>&1; then
            exec newgrp docker -c "$CMD"
        else
            log_error "Neither 'sg' nor working 'newgrp -c' available to re-exec under docker group."
            log_error "Please logout/login to pick up group membership."
            return 1
        fi
    fi

    # exec replaces process; we should not reach here.
    return 1
}

# ============================================================================
# INSTALLATION FUNCTIONS (Base Infrastructure)
# ============================================================================

###############################################################################
# Install Docker
#
# Installs Docker CE from the official Docker repository with a pinned version.
# Adds the current user to the docker group for sudo-less docker commands.
#
# Idempotency:
#   - Checks for state marker: $STATE_DIR/docker_installed
#   - Checks if docker binary exists
#
# Dependencies: None
#
# Side effects:
#   - Adds Docker apt repository
#   - Modifies user groups (requires logout/login or script re-exec)
#   - Requires sudo access
###############################################################################
install_docker() {
    # Check state marker
    if [ -f "$STATE_DIR/docker_installed" ]; then
        log_info "Skipping Docker install (marker found)."
        return 0
    fi

    # Check if docker binary already exists
    if check_binary_exists docker; then
        log_info "Docker binary already exists, skipping installation."
        touch "$STATE_DIR/docker_installed"
        return 0
    fi

    log_info "Installing Docker..."

    # Add Docker's official GPG key
    sudo apt-get update >> "$LOG_FILE" 2>&1
    sudo apt-get install -y ca-certificates curl >> "$LOG_FILE" 2>&1
    sudo install -m 0755 -d /etc/apt/keyrings
    sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    sudo chmod a+r /etc/apt/keyrings/docker.asc

    # Add the repository to Apt sources
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
      $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | \
      sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

    sudo apt-get update >> "$LOG_FILE" 2>&1

    # Install Docker with specific version
    log_info "Installing Docker version $DOCKER_VERSION..."
    sudo apt-get install -y \
        docker-ce="$DOCKER_VERSION" \
        docker-ce-cli="$DOCKER_VERSION" \
        containerd.io \
        docker-buildx-plugin \
        docker-compose-plugin >> "$LOG_FILE" 2>&1

    # Add user to docker group
    sudo usermod -aG docker "$USER"

    # Create marker
    touch "$STATE_DIR/docker_installed"

    log_info "Docker installed successfully."
}

###############################################################################
# Install UV
#
# Installs UV, a fast Python package manager, from the official installer.
#
# Idempotency:
#   - Checks for state marker: $STATE_DIR/uv_installed
#   - Checks if uv binary exists in PATH
#
# Dependencies: curl
#
# Side effects:
#   - Installs to ~/.local/bin/uv
#   - Sources environment file
###############################################################################
install_uv() {
    # Check state marker
    if [ -f "$STATE_DIR/uv_installed" ]; then
        log_info "Skipping UV install (marker found)."
        return 0
    fi

    # Check if uv binary already exists
    if check_binary_exists uv; then
        log_info "UV binary already exists, skipping installation."
        touch "$STATE_DIR/uv_installed"
        return 0
    fi

    log_info "Installing UV package manager..."

    curl -LsSf https://astral.sh/uv/$UV_VERSION/install.sh | sh >> "$LOG_FILE" 2>&1

    # Source the environment
    if [ -f "$HOME/.local/bin/env" ]; then
        source "$HOME/.local/bin/env"
    fi

    # Create marker
    touch "$STATE_DIR/uv_installed"

    log_info "UV installed successfully."
}

###############################################################################
# Install Minikube
#
# Installs Minikube for running local Kubernetes clusters.
# Also creates mount directories and configures default CPU/memory settings.
#
# Idempotency:
#   - Checks for state marker: $STATE_DIR/minikube_installed
#   - Checks if minikube binary exists
#
# Dependencies: curl
#
# Side effects:
#   - Creates mount directories at $MINIKUBE_MOUNT_DIR
#   - Sets minikube config for cpus and memory
###############################################################################
install_minikube() {
    # Check state marker
    if [ -f "$STATE_DIR/minikube_installed" ]; then
        log_info "Skipping Minikube install (marker found)."
        return 0
    fi

    # Check if minikube binary already exists
    if check_binary_exists minikube; then
        log_info "Minikube binary already exists, skipping installation."
        # Still need to ensure directories exist
        sudo mkdir -p "$MINIKUBE_MOUNT_DIR"
        sudo chmod 777 "$MINIKUBE_MOUNT_DIR"
        mkdir -p "$MINIKUBE_MOUNT_MINIO" "$MINIKUBE_MOUNT_SHR"
        touch "$STATE_DIR/minikube_installed"
        return 0
    fi

    log_info "Installing Minikube..."

    # Download and install Minikube
    curl -LO https://github.com/kubernetes/minikube/releases/download/$MINIKUBE_VERSION/minikube-linux-amd64 >> "$LOG_FILE" 2>&1
    sudo install minikube-linux-amd64 /usr/local/bin/minikube
    rm minikube-linux-amd64

    # Setup mount directories
    log_info "Creating mount directories..."
    sudo mkdir -p "$MINIKUBE_MOUNT_DIR"
    sudo chmod 777 "$MINIKUBE_MOUNT_DIR"
    mkdir -p "$MINIKUBE_MOUNT_MINIO"
    mkdir -p "$MINIKUBE_MOUNT_SHR"

    # Configure Minikube defaults
    log_info "Configuring Minikube (CPU: $MINIKUBE_CPU, Memory: ${MINIKUBE_MEMORY}MB)..."
    minikube config set cpus "$MINIKUBE_CPU" >> "$LOG_FILE" 2>&1
    minikube config set memory "$MINIKUBE_MEMORY" >> "$LOG_FILE" 2>&1

    # Create marker
    touch "$STATE_DIR/minikube_installed"

    log_info "Minikube installed successfully."
}

###############################################################################
# Install Helm
#
# Installs Helm, the Kubernetes package manager.
#
# Idempotency:
#   - Checks for state marker: $STATE_DIR/helm_installed
#   - Checks if helm binary exists
#
# Dependencies: curl, tar
#
# Side effects:
#   - Installs helm to /usr/local/bin/helm
###############################################################################
install_helm() {
    # Check state marker
    if [ -f "$STATE_DIR/helm_installed" ]; then
        log_info "Skipping Helm install (marker found)."
        return 0
    fi

    # Check if helm binary already exists
    if check_binary_exists helm; then
        log_info "Helm binary already exists, skipping installation."
        touch "$STATE_DIR/helm_installed"
        return 0
    fi

    log_info "Installing Helm..."

    curl -LO https://get.helm.sh/helm-$HELM_VERSION-linux-amd64.tar.gz >> "$LOG_FILE" 2>&1
    tar -xzf helm-$HELM_VERSION-linux-amd64.tar.gz >> "$LOG_FILE" 2>&1
    sudo mv linux-amd64/helm /usr/local/bin
    rm -rf helm-$HELM_VERSION-linux-amd64.tar.gz linux-amd64

    # Create marker
    touch "$STATE_DIR/helm_installed"

    log_info "Helm installed successfully."
}

###############################################################################
# Install Kubectl
#
# Installs kubectl, the Kubernetes command-line tool.
#
# Idempotency:
#   - Checks for state marker: $STATE_DIR/kubectl_installed
#   - Checks if kubectl binary exists
#
# Dependencies: curl
#
# Side effects:
#   - Installs kubectl to /usr/local/bin/kubectl
###############################################################################
install_kubectl() {
    # Check state marker
    if [ -f "$STATE_DIR/kubectl_installed" ]; then
        log_info "Skipping kubectl install (marker found)."
        return 0
    fi

    # Check if kubectl binary already exists
    if check_binary_exists kubectl; then
        log_info "Kubectl binary already exists, skipping installation."
        touch "$STATE_DIR/kubectl_installed"
        return 0
    fi

    log_info "Installing kubectl..."

    curl -LO https://dl.k8s.io/release/$KUBECTL_VERSION/bin/linux/amd64/kubectl >> "$LOG_FILE" 2>&1
    sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
    rm kubectl

    # Create marker
    touch "$STATE_DIR/kubectl_installed"

    log_info "Kubectl installed successfully."
}

###############################################################################
# Install Java
#
# Installs OpenJDK for running Spark and Kafka.
# Also sets JAVA_HOME environment variable.
#
# Idempotency:
#   - Checks for state marker: $STATE_DIR/java_installed
#   - Checks if java binary exists
#
# Dependencies: None
#
# Side effects:
#   - Installs Java via apt
#   - Adds JAVA_HOME to /etc/environment
#   - Requires sudo access
###############################################################################
install_java() {
    # Check state marker
    if [ -f "$STATE_DIR/java_installed" ]; then
        log_info "Skipping Java install (marker found)."
        return 0
    fi

    # Check if java binary already exists
    if check_binary_exists java; then
        log_info "Java binary already exists, skipping installation."
        touch "$STATE_DIR/java_installed"
        return 0
    fi

    log_info "Installing $JAVA_VERSION..."

    sudo apt-get update >> "$LOG_FILE" 2>&1
    sudo apt-get install -y "$JAVA_VERSION" >> "$LOG_FILE" 2>&1

    log_info "Verifying Java installation..."
    java -version >> "$LOG_FILE" 2>&1

    # Find JDK installation path
    JAVA_PATH=$(readlink -f /usr/bin/java | sed "s:bin/java::")

    # Set JAVA_HOME
    log_info "Setting JAVA_HOME to $JAVA_PATH..."
    if grep -q "JAVA_HOME" /etc/environment; then
        log_info "JAVA_HOME already set in /etc/environment"
    else
        echo "JAVA_HOME=$JAVA_PATH" | sudo tee -a /etc/environment >> "$LOG_FILE"
        log_info "JAVA_HOME added to /etc/environment"
    fi

    # Export for current session
    export JAVA_HOME=$JAVA_PATH

    # Create marker
    touch "$STATE_DIR/java_installed"

    log_info "Java installed successfully."
}

###############################################################################
# Install Spark
#
# Downloads and extracts Apache Spark for local development and building
# custom Docker images.
#
# Idempotency:
#   - Checks for state marker: $STATE_DIR/spark_installed
#   - Checks if Spark directory exists
#
# Dependencies: curl, tar, Java
#
# Side effects:
#   - Downloads ~300MB tarball
#   - Extracts to ~/spark-{VERSION}
###############################################################################
install_spark() {
    # Check state marker
    if [ -f "$STATE_DIR/spark_installed" ]; then
        log_info "Skipping Spark install (marker found)."
        return 0
    fi

    # Check if Spark directory already exists
    if [ -d "$SPARK_HOME" ]; then
        log_info "Spark directory already exists at $SPARK_HOME, skipping installation."
        touch "$STATE_DIR/spark_installed"
        return 0
    fi

    log_info "Installing Spark $SPARK_VERSION..."
    log_info "Downloading Spark (this may take a few minutes)..."

    curl -L https://archive.apache.org/dist/spark/spark-$SPARK_VERSION/spark-$SPARK_VERSION-bin-hadoop3.tgz \
        -o /tmp/spark-download.tgz >> "$LOG_FILE" 2>&1

    # Extract Spark
    log_info "Extracting Spark to $SPARK_HOME..."
    mkdir -p "$SPARK_HOME"
    tar -xzf /tmp/spark-download.tgz -C "$SPARK_HOME" --strip-components=1 >> "$LOG_FILE" 2>&1
    rm /tmp/spark-download.tgz

    # Create marker
    touch "$STATE_DIR/spark_installed"

    log_info "Spark installed successfully at $SPARK_HOME"
}

# ============================================================================
# KUBERNETES & DE TOOLS SETUP FUNCTIONS
# ============================================================================

###############################################################################
# Minikube Start
#
# Starts the Minikube Kubernetes cluster with configured resources.
# Enables the ingress addon for MinIO external access.
#
# Idempotency:
#   - Checks for state marker: $STATE_DIR/minikube_started
#   - Checks if minikube is already running
#
# Dependencies: Docker, Minikube
#
# Side effects:
#   - Starts Minikube VM/container
#   - Mounts host directory to Minikube
#   - Enables ingress addon
###############################################################################
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
        log_error "Failed to run docker command without sudo. Please check docker installation."
        exit 1
    fi

    log_info "Starting Minikube..."
    log_info "Mount: $MINIKUBE_MOUNT_DIR -> /mnt"

    minikube start --mount --mount-string="$MINIKUBE_MOUNT_DIR:/mnt" >> "$LOG_FILE" 2>&1

    # Enable ingress addon for MinIO
    log_info "Enabling ingress addon..."
    minikube addons enable ingress >> "$LOG_FILE" 2>&1

    # Create marker
    touch "$STATE_DIR/minikube_started"

    log_info "Minikube started successfully."
}

###############################################################################
# Build Spark Images
#
# Builds custom Spark Docker images with Java 21 and Python 3.10.12.
# Images are built directly in Minikube's Docker daemon.
#
# Idempotency:
#   - Checks for state marker: $STATE_DIR/spark_images_built
#   - Checks if Docker images already exist
#
# Dependencies: Minikube (running), Spark installation
#
# Side effects:
#   - Builds two Docker images: spark:v3.5.2.2 and pyspark:v3.5.2.3
#   - Uses Minikube's Docker daemon
#   - May take 10-15 minutes
###############################################################################
build_spark_img() {
    # Check state marker
    if [ -f "$STATE_DIR/spark_images_built" ]; then
        log_info "Skipping Spark image build (marker found)."
        return 0
    fi

    # Switch to Minikube's Docker daemon
    eval $(minikube docker-env)

    # Check if images already exist
    if docker images | grep -q "spark.*v3.5.2.2" && docker images | grep -q "pyspark.*v3.5.2.3" 2>/dev/null; then
        log_info "Spark images already exist, skipping build."
        touch "$STATE_DIR/spark_images_built"
        return 0
    fi

    log_info "Building Spark Docker images (this may take 10-15 minutes)..."

    # Build base Spark image
    log_info "Building spark:v3.5.2.2..."
    docker build -t spark:v3.5.2.2 \
        -f "$PROJECT_DIR/minikube/spark/Dockerfile" \
        "$SPARK_HOME" >> "$LOG_FILE" 2>&1

    # Build PySpark image
    log_info "Building pyspark:v3.5.2.3..."
    docker build --build-arg base_img=spark:v3.5.2.2 \
        -t pyspark:v3.5.2.3 \
        -f "$PROJECT_DIR/minikube/spark/Dockerfile_pyspark" \
        "$SPARK_HOME" >> "$LOG_FILE" 2>&1

    # Create marker
    touch "$STATE_DIR/spark_images_built"

    log_info "Spark images built successfully."
}

###############################################################################
# Deploy Kafka
#
# Deploys Kafka cluster using Strimzi operator on Kubernetes.
#
# Idempotency:
#   - Checks for state marker: $STATE_DIR/kafka_deployed
#   - Checks if Kafka namespace and resources exist
#
# Dependencies: Minikube (running), kubectl
#
# Side effects:
#   - Creates kafka namespace
#   - Deploys Strimzi operator
#   - Deploys Kafka cluster (3 brokers)
###############################################################################
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

    kubectl apply -f minikube/kafka/00-kafka_ns.yaml >> "$LOG_FILE" 2>&1
    kubectl apply -f minikube/kafka/01-stimzi_operator.yaml >> "$LOG_FILE" 2>&1

    log_info "Waiting for Strimzi operator to be ready..."
    sleep 5

    kubectl apply -f minikube/kafka/02-kafka_deploy.yaml >> "$LOG_FILE" 2>&1

    # Create marker
    touch "$STATE_DIR/kafka_deployed"

    log_info "Kafka deployed successfully."
}

###############################################################################
# Deploy Pinot
#
# Deploys Apache Pinot using Helm chart for real-time analytics.
#
# Idempotency:
#   - Checks for state marker: $STATE_DIR/pinot_deployed
#   - Checks if Pinot namespace exists
#
# Dependencies: Minikube (running), Helm
#
# Side effects:
#   - Creates pinot-quickstart namespace
#   - Deploys Pinot via Helm
###############################################################################
deploy_pinot() {
    # Check state marker
    if [ -f "$STATE_DIR/pinot_deployed" ]; then
        log_info "Skipping Pinot deployment (marker found)."
        return 0
    fi

    # Check if Pinot namespace exists
    if kubectl get namespace pinot-quickstart >/dev/null 2>&1; then
        log_info "Pinot namespace already exists, skipping deployment."
        touch "$STATE_DIR/pinot_deployed"
        return 0
    fi

    log_info "Deploying Apache Pinot..."

    kubectl create ns pinot-quickstart >> "$LOG_FILE" 2>&1 || true
    helm install -n pinot-quickstart pinot \
        minikube/pinot/pinot-0.3.4.tgz \
        -f minikube/pinot/myvalues.yaml >> "$LOG_FILE" 2>&1 || true

    # Create marker
    touch "$STATE_DIR/pinot_deployed"

    log_info "Pinot deployed successfully."
}

###############################################################################
# Deploy MinIO
#
# Deploys MinIO for S3-compatible object storage.
#
# Idempotency:
#   - Checks for state marker: $STATE_DIR/minio_deployed
#   - Checks if MinIO namespace exists
#
# Dependencies: Minikube (running), kubectl
#
# Side effects:
#   - Deploys MinIO operator
#   - Deploys MinIO tenant
###############################################################################
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

    kubectl apply -f minikube/minio/00-minio-operator.yaml >> "$LOG_FILE" 2>&1

    log_info "Waiting for MinIO operator to be ready..."
    sleep 5

    kubectl apply -f minikube/minio >> "$LOG_FILE" 2>&1

    # Create marker
    touch "$STATE_DIR/minio_deployed"

    log_info "MinIO deployed successfully."
}

# ============================================================================
# APPLICATION SETUP FUNCTIONS
# ============================================================================

###############################################################################
# Install MinIO Client
#
# Installs the MinIO client (mc) and configures S3 buckets for Spark.
#
# Idempotency:
#   - Checks for state marker: $STATE_DIR/minio_client_setup
#   - Checks if mc binary exists
#
# Dependencies: MinIO (deployed)
#
# Side effects:
#   - Installs mc to /usr/local/bin
#   - Configures S3 alias
#   - Creates spark-logs and data buckets
###############################################################################
install_mc_client() {
    # Check state marker
    if [ -f "$STATE_DIR/minio_client_setup" ]; then
        log_info "Skipping MinIO client setup (marker found)."
        return 0
    fi

    # Check if mc binary already exists and is configured
    if check_binary_exists mc && mc alias list | grep -q "s3" 2>/dev/null; then
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

    # Configure S3 alias
    log_info "Configuring MinIO S3 alias..."
    mc alias set s3 http://minio-api.192.168.49.2.nip.io:80 minio minio123 >> "$LOG_FILE" 2>&1

    # Create buckets
    log_info "Creating S3 buckets..."
    mc mb s3/spark-logs/events >> "$LOG_FILE" 2>&1 || true
    mc mb s3/data >> "$LOG_FILE" 2>&1 || true

    # Create marker
    touch "$STATE_DIR/minio_client_setup"

    log_info "MinIO client setup successfully."
}

###############################################################################
# Setup DE Application
#
# Sets up the data engineering application components:
#   - Port-forwards Pinot controller
#   - Creates Kafka topics
#   - Creates Pinot schema and tables
#   - Builds and deploys WebSocket extractor
#   - Copies Spark scripts to shared mount
#   - Applies Spark RBAC resources
#
# Idempotency:
#   - Checks for state marker: $STATE_DIR/app_setup
#   - Checks if resources already exist
#
# Dependencies:
#   - Kafka (deployed)
#   - Pinot (deployed)
#   - Minikube (running)
#   - ALPACA_KEY and ALPACA_SECRET environment variables
#
# Side effects:
#   - Creates Kubernetes ConfigMaps and Secrets
#   - Builds Docker image in Minikube
#   - Deploys extractor pod
###############################################################################
setup_de_app() {
    # Check state marker
    if [ -f "$STATE_DIR/app_setup" ]; then
        log_info "Skipping DE app setup (marker found)."
        return 0
    fi

    # Validate required environment variables
    if [ -z "$ALPACA_KEY" ] || [ -z "$ALPACA_SECRET" ]; then
        log_error "ALPACA_KEY and ALPACA_SECRET environment variables must be set."
        log_error "Usage: ALPACA_KEY=xxx ALPACA_SECRET=yyy $0 --setup-app"
        return 1
    fi

    log_info "Setting up DE application..."

    # Port-forward Pinot controller in background
    log_info "Starting Pinot port-forward..."
    nohup minikube/pinot/query-pinot-data.sh > /tmp/setup_infra.log 2>&1 &
    sleep 5

    # Create Kafka topics
    log_info "Creating Kafka topics..."
    uv run extract/admin/create_kafka_topic.py >> "$LOG_FILE" 2>&1

    # Create Pinot tables
    log_info "Creating Pinot tables..."
    uv run load/create.py >> "$LOG_FILE" 2>&1

    # Create ConfigMap and Secret
    log_info "Creating Kubernetes ConfigMap and Secret..."
    kubectl create configmap app-config \
        --from-file=config.yaml=config/config.yaml >> "$LOG_FILE" 2>&1 || true

    kubectl create secret generic alpaca-creds \
        --from-literal=ALPACA_KEY="$ALPACA_KEY" \
        --from-literal=ALPACA_SECRET="$ALPACA_SECRET" >> "$LOG_FILE" 2>&1 || true

    # Build extractor image
    log_info "Building WebSocket extractor image..."
    eval $(minikube docker-env)
    docker build -t ws_scraper:v1.0 \
        -f extract/app/Dockerfile extract/app >> "$LOG_FILE" 2>&1

    # Deploy extractor
    log_info "Deploying WebSocket extractor..."
    kubectl apply -f minikube/extractor_deploy/extractor_deploy.yaml >> "$LOG_FILE" 2>&1

    # Copy Spark scripts to shared mount
    log_info "Copying Spark scripts to shared mount..."
    cp transform/spark_streaming_flattener.py "$MINIKUBE_MOUNT_SHR"

    # Apply Spark RBAC resources
    log_info "Applying Spark RBAC resources..."
    kubectl apply -f minikube/spark/spark_resources.yaml >> "$LOG_FILE" 2>&1

    # Create marker
    touch "$STATE_DIR/app_setup"

    log_info "DE application setup completed successfully."
}

# ============================================================================
# ORCHESTRATION FUNCTIONS
# ============================================================================

###############################################################################
# Install All Infrastructure
#
# Orchestrates the installation of all base infrastructure components.
# Includes Docker group activation handling.
#
# Components installed:
#   - Docker
#   - UV
#   - Minikube
#   - Helm
#   - Kubectl
#   - Java
#   - Spark
###############################################################################
install_all_infra() {
    log_info "========================================="
    log_info "Installing All Infrastructure Components"
    log_info "========================================="

    install_docker
    ensure_docker_group_no_sudo "$@"
    install_uv
    install_minikube
    install_helm
    install_kubectl
    install_java
    install_spark

    log_info "========================================="
    log_info "✓ All infrastructure components installed"
    log_info "========================================="
}

###############################################################################
# Setup Kubernetes DE Tools
#
# Orchestrates the setup of Kubernetes cluster and deployment of data
# engineering tools.
#
# Components deployed:
#   - Minikube cluster (started)
#   - Custom Spark images
#   - Kafka cluster
#   - Apache Pinot
#   - MinIO
###############################################################################
setup_kubernetes_de_tools() {
    log_info "========================================="
    log_info "Setting Up Kubernetes & DE Tools"
    log_info "========================================="

    ensure_docker_group_no_sudo "$@"
    minikube_start
    build_spark_img
    deploy_kafka
    deploy_pinot
    deploy_minio

    log_info "========================================="
    log_info "✓ Kubernetes & DE tools deployed"
    log_info "========================================="
}

###############################################################################
# Run All
#
# Executes the complete infrastructure and application setup.
# This is the equivalent of running --all flag.
###############################################################################
run_all() {
    log_info "========================================="
    log_info "Starting Complete Infrastructure Setup"
    log_info "========================================="

    install_all_infra "$@"
    setup_kubernetes_de_tools "$@"
    install_mc_client
    setup_de_app

    log_info ""
    log_info "========================================="
    log_info "✓ Complete Setup Finished Successfully!"
    log_info "========================================="
    log_info ""
    log_info "Next Steps:"
    log_info "  1. Run Spark streaming: cd transform && ./run_pyspark_streamer.sh"
    log_info "  2. Query Pinot data: uv run load/pinot_qeury_display.py"
    log_info "  3. Check logs: tail -f $LOG_FILE"
    log_info ""
    log_info "Access Information:"
    log_info "  - Kafka: 192.168.49.2:32100"
    log_info "  - MinIO: http://minio-api.192.168.49.2.nip.io"
    log_info "  - Pinot: kubectl port-forward -n pinot-quickstart svc/pinot-controller 9000:9000"
    log_info ""
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

# Initialize state directory and logging
mkdir -p "$STATE_DIR"
setup_logging

# Parse command line arguments
INSTALL_INFRA=false
SETUP_K8S=false
INSTALL_MC=false
SETUP_APP=false
RUN_ALL=false

# Store original arguments for re-exec
ORIGINAL_ARGS=("$@")

while [[ $# -gt 0 ]]; do
    case $1 in
        --install-infra)
            INSTALL_INFRA=true
            shift
            ;;
        --setup-k8s)
            SETUP_K8S=true
            shift
            ;;
        --install-mc)
            INSTALL_MC=true
            shift
            ;;
        --setup-app)
            SETUP_APP=true
            shift
            ;;
        --all)
            RUN_ALL=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            show_help
            exit 1
            ;;
    esac
done

# If no arguments provided, show help
if [ "$INSTALL_INFRA" = false ] && [ "$SETUP_K8S" = false ] && \
   [ "$INSTALL_MC" = false ] && [ "$SETUP_APP" = false ] && \
   [ "$RUN_ALL" = false ]; then
    show_help
    exit 0
fi

# Log script start
log_info "========================================="
log_info "Alpaca Infrastructure Setup Script"
log_info "Started at: $(date)"
log_info "Log file: $LOG_FILE"
log_info "========================================="

# Execute based on flags
if [ "$RUN_ALL" = true ]; then
    run_all "${ORIGINAL_ARGS[@]}"
else
    # Execute selected components
    if [ "$INSTALL_INFRA" = true ]; then
        install_all_infra "${ORIGINAL_ARGS[@]}"
    fi

    if [ "$SETUP_K8S" = true ]; then
        setup_kubernetes_de_tools "${ORIGINAL_ARGS[@]}"
    fi

    if [ "$INSTALL_MC" = true ]; then
        install_mc_client
    fi

    if [ "$SETUP_APP" = true ]; then
        setup_de_app
    fi
fi

# Log completion
log_info "========================================="
log_info "Script completed at: $(date)"
log_info "Log file: $LOG_FILE"
log_info "========================================="

exit 0
