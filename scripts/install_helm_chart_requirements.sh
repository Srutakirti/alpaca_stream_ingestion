#!/bin/bash
###############################################################################
# Helm Charts Testing - Requirements Installation Script
#
# This script installs only the required tools for testing Helm charts:
#   - Docker
#   - Minikube
#   - Helm
#   - Kubectl
#
# The actual Minikube start and Helm deployment commands are run manually by the user.
#
# Prerequisites:
#   - Ubuntu Linux
#   - sudo access
#
# Usage: ./install_helm_chart_requirements.sh
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

# Directory Configuration
STATE_DIR="$HOME/.helm_test_state"
MINIKUBE_MOUNT_DIR="/mnt/mydrive2"
MINIKUBE_MOUNT_MINIO="$MINIKUBE_MOUNT_DIR/minio"
MINIKUBE_MOUNT_SHR="$MINIKUBE_MOUNT_DIR/shr"

# Minikube Resource Configuration
MINIKUBE_CPU=8
MINIKUBE_MEMORY=14999  # in MB

# Logging Configuration
LOG_FILE="/tmp/helm_requirements_$(date +%Y%m%d_%H%M%S).log"

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
        echo "Helm Chart Requirements Installation Log"
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
# UTILITY FUNCTIONS
# ============================================================================

check_binary_exists() {
    command -v "$1" >/dev/null 2>&1
}

# ============================================================================
# DOCKER GROUP HANDLING
# ============================================================================

###############################################################################
# Ensure Docker Group Without Sudo
#
# Ensures the current user can run docker commands without sudo.
# If the user needs to be added to the docker group, adds them but
# does NOT re-exec the script.
#
# Returns:
#   0 - Docker already works without sudo
#   1 - User was added to docker group, needs new shell
#   2 - Error occurred
###############################################################################
ensure_docker_group_no_sudo() {
    # If docker already usable without sudo, nothing to do
    if docker info >/dev/null 2>&1; then
        log_info "Docker usable without sudo"
        return 0
    fi

    log_warn "Docker requires sudo access currently."

    # Check if user is already in docker group (but session not active)
    if id -nG "$USER" | tr ' ' '\n' | grep -xq docker; then
        log_warn "User $USER is already in docker group, but current shell doesn't reflect it."
        log_warn "Run 'newgrp docker' to activate, or start a new shell."
        return 1
    fi

    # User not in docker group, add them (requires sudo)
    log_info "Adding user $USER to docker group (requires sudo)..."
    if ! sudo usermod -aG docker "$USER"; then
        log_error "Failed to add $USER to docker group via sudo."
        return 2
    fi

    log_info "Successfully added $USER to docker group."
    log_warn "You need to start a new shell to activate the group membership."
    return 1
}

# ============================================================================
# INSTALLATION FUNCTIONS
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
# Side effects:
#   - Adds Docker apt repository
#   - Modifies user groups (requires logout/login or new shell)
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
        EXISTING_VERSION=$(docker --version 2>/dev/null || echo "unknown")
        log_info "Docker binary already exists ($EXISTING_VERSION), skipping installation."
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
# Install Minikube
#
# Installs Minikube for running local Kubernetes clusters.
# Also creates mount directories and configures default CPU/memory settings.
#
# Idempotency:
#   - Checks for state marker: $STATE_DIR/minikube_installed
#   - Checks if minikube binary exists
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
        EXISTING_VERSION=$(minikube version --short 2>/dev/null || echo "unknown")
        log_info "Minikube binary already exists ($EXISTING_VERSION), skipping installation."
        # Still need to ensure directories exist
        sudo mkdir -p "$MINIKUBE_MOUNT_DIR"
        sudo chmod 777 "$MINIKUBE_MOUNT_DIR"
        mkdir -p "$MINIKUBE_MOUNT_MINIO" "$MINIKUBE_MOUNT_SHR"
        touch "$STATE_DIR/minikube_installed"
        return 0
    fi

    log_info "Installing Minikube $MINIKUBE_VERSION..."

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
        EXISTING_VERSION=$(helm version --short 2>/dev/null || echo "unknown")
        log_info "Helm binary already exists ($EXISTING_VERSION), skipping installation."
        touch "$STATE_DIR/helm_installed"
        return 0
    fi

    log_info "Installing Helm $HELM_VERSION..."

    curl -LO https://get.helm.sh/helm-$HELM_VERSION-linux-amd64.tar.gz >> "$LOG_FILE" 2>&1
    tar -xzf helm-$HELM_VERSION-linux-amd64.tar.gz >> "$LOG_FILE" 2>&1
    sudo mv linux-amd64/helm /usr/local/bin
    rm -rf helm-$HELM_VERSION-linux-amd64.tar.gz linux-amd64

    # Create marker
    touch "$STATE_DIR/helm_installed"

    log_info "Helm installed successfully."
    helm version --short
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
        EXISTING_VERSION=$(kubectl version --client --short 2>/dev/null || echo "unknown")
        log_info "Kubectl binary already exists ($EXISTING_VERSION), skipping installation."
        touch "$STATE_DIR/kubectl_installed"
        return 0
    fi

    log_info "Installing kubectl $KUBECTL_VERSION..."

    curl -LO https://dl.k8s.io/release/$KUBECTL_VERSION/bin/linux/amd64/kubectl >> "$LOG_FILE" 2>&1
    sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
    rm kubectl

    # Create marker
    touch "$STATE_DIR/kubectl_installed"

    log_info "Kubectl installed successfully."
    kubectl version --client --short
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

# Initialize state directory and logging
mkdir -p "$STATE_DIR"
setup_logging

# Log script start
log_info "========================================="
log_info "Helm Chart Requirements Installation"
log_info "========================================="
log_info "Versions:"
log_info "  Docker: $DOCKER_VERSION"
log_info "  Minikube: $MINIKUBE_VERSION"
log_info "  Helm: $HELM_VERSION"
log_info "  Kubectl: $KUBECTL_VERSION"
log_info "========================================="
log_info ""

# Install components
install_docker
install_minikube
install_helm
install_kubectl

# Check Docker group permissions
log_info ""
log_info "========================================="
log_info "Checking Docker Permissions"
log_info "========================================="

ensure_docker_group_no_sudo
DOCKER_STATUS=$?

if [ $DOCKER_STATUS -eq 1 ]; then
    log_warn ""
    log_warn "========================================="
    log_warn "ACTION REQUIRED: Docker Group Added"
    log_warn "========================================="
    log_warn ""
    log_warn "Your user has been added to the 'docker' group."
    log_warn "To activate this group membership, you need to start a new shell."
    log_warn ""
    log_warn "Run one of the following commands:"
    log_warn "  1. newgrp docker"
    log_warn "  2. su - $USER"
    log_warn "  3. Or logout and login again"
    log_warn ""
    log_warn "Then continue with the Minikube and Helm commands below."
    log_warn ""
    log_warn "========================================="
elif [ $DOCKER_STATUS -eq 2 ]; then
    log_error "Failed to setup Docker group. Cannot continue."
    exit 1
fi

# Verify installations
log_info ""
log_info "========================================="
log_info "✓ Installation Complete"
log_info "========================================="
log_info ""
log_info "Installed versions:"
docker --version
minikube version --short
helm version --short
kubectl version --client --short

log_info ""
log_info "========================================="
log_info "Next Steps (Run Manually):"
log_info "========================================="
log_info ""
log_info "1. Start Minikube with mount:"
log_info "   minikube start --mount --mount-string=\"$MINIKUBE_MOUNT_DIR:/mnt\""
log_info ""
log_info "2. Get Minikube IP:"
log_info "   MINIKUBE_IP=\$(minikube ip)"
log_info "   echo \$MINIKUBE_IP"
log_info ""
log_info "3. Update config/config.yaml with Minikube IP if different from 192.168.49.2"
log_info ""
log_info "4. Create namespaces:"
log_info "   kubectl create namespace kafka"
log_info "   kubectl create namespace pinot-quickstart"
log_info ""
log_info "5. Deploy Kafka:"
log_info "   helm install kafka ./helm/infrastructure/kafka \\"
log_info "     -f config/config.yaml -n kafka"
log_info ""
log_info "6. Wait for Kafka to be ready:"
log_info "   kubectl wait --for=condition=Ready kafka/my-cluster \\"
log_info "     -n kafka --timeout=600s"
log_info ""
log_info "7. Deploy Pinot:"
log_info "   helm install pinot ./helm/infrastructure/pinot \\"
log_info "     -f config/config.yaml -n pinot-quickstart"
log_info ""
log_info "8. Wait for Pinot to be ready:"
log_info "   kubectl wait --for=condition=Ready pods --all \\"
log_info "     -n pinot-quickstart --timeout=600s"
log_info ""
log_info "9. Run setup script:"
log_info "   python3 scripts/setup_infrastructure.py"
log_info ""
log_info "========================================="
log_info "Log file: $LOG_FILE"
log_info "========================================="

exit 0
