#!/bin/bash
###############################################################################
# Part 1: Install Dependencies
#
# Installs all system-level dependencies required for the data engineering stack.
#
# Components installed:
#   - Docker CE (container runtime)
#   - UV (Python package manager)
#   - Minikube (local Kubernetes)
#   - Helm (Kubernetes package manager)
#   - Kubectl (Kubernetes CLI)
#   - Java 17 (for KStreams applications)
#
# Prerequisites:
#   - Ubuntu Linux
#   - sudo access
#
# Exit codes:
#   0 - Success
#   1 - Error occurred
#   3 - Docker group needs activation (restart shell required)
#
# Usage:
#   ./scripts/1_install_dependencies.sh
###############################################################################

set -e  # Exit on error

# ============================================================================
# CONFIGURATION
# ============================================================================

# Version Configuration
DOCKER_VERSION="5:28.5.1-1~ubuntu.25.10~questing"
MINIKUBE_VERSION="v1.36.0"
KUBECTL_VERSION="v1.34.0"
HELM_VERSION="v3.19.0"
JAVA_VERSION="openjdk-17-jdk"
UV_VERSION="0.9.2"

# Directory Configuration
STATE_DIR="$HOME/.alpaca_infra_state"
MINIKUBE_MOUNT_DIR="/mnt/mydrive2"
MINIKUBE_MOUNT_MINIO="$MINIKUBE_MOUNT_DIR/minio"
MINIKUBE_MOUNT_SHR="$MINIKUBE_MOUNT_DIR/shr"

# Minikube Resource Configuration
MINIKUBE_CPU=8
MINIKUBE_MEMORY=14999  # in MB

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
        echo "Part 1: Install Dependencies"
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

ensure_docker_group_no_sudo() {
    # If docker already usable without sudo, nothing to do
    if docker info >/dev/null 2>&1; then
        log_info "Docker usable without sudo"
        return 0
    fi

    log_warn "Docker requires sudo access currently."

    # Check if user is in docker group (covers both just-added and already-in cases)
    if id -nG "$USER" | tr ' ' '\n' | grep -xq docker; then
        log_warn "User $USER is in docker group, but current shell doesn't reflect it."
        return 1
    fi

    # User not in docker group, add them (requires sudo)
    log_info "Adding user $USER to docker group (requires sudo)..."
    if ! sudo usermod -aG docker "$USER"; then
        log_error "Failed to add $USER to docker group via sudo."
        return 2
    fi

    log_info "Successfully added $USER to docker group."
    return 1
}

# ============================================================================
# INSTALLATION FUNCTIONS
# ============================================================================

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

    # Add UV to PATH permanently
    if ! grep -q 'export PATH="$HOME/.local/bin:$PATH"' "$HOME/.bashrc"; then
        echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
        log_info "Added UV to PATH in ~/.bashrc"
    fi

    # Ensure ~/.local/bin is in PATH for current session
    export PATH="$HOME/.local/bin:$PATH"

    # Create marker
    touch "$STATE_DIR/uv_installed"

    log_info "UV installed successfully."
}

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

# ============================================================================
# MAIN EXECUTION
# ============================================================================

main() {
    log_info "========================================="
    log_info "Part 1: Installing Dependencies"
    log_info "========================================="
    log_info ""

    # Install all components
    install_docker
    install_uv
    install_minikube
    install_helm
    install_kubectl
    install_java

    log_info ""
    log_info "========================================="
    log_info "✓ All dependencies installed"
    log_info "========================================="
    log_info ""

    # Check if docker group needs activation
    # Temporarily disable set -e to capture return code
    set +e
    ensure_docker_group_no_sudo
    DOCKER_STATUS=$?
    set -e

    if [ $DOCKER_STATUS -eq 1 ]; then
        echo ""
        echo ""
        echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
        echo "!!!   ACTION REQUIRED: Activate Docker Group       !!!"
        echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
        echo ""
        echo "Docker commands will not work until you activate the docker group."
        echo ""
        echo "Choose ONE of these commands to activate it:"
        echo ""
        echo "  1. newgrp docker           (recommended - activates in current shell)"
        echo "  2. su - $USER              (starts new login shell)"
        echo "  3. logout and login again  (full session restart)"
        echo ""
        echo "After activating, verify with:"
        echo "  docker info"
        echo ""
        echo "Then continue with:"
        echo "  ./scripts/2_setup_kubernetes.sh"
        echo ""
        echo "!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!"
        echo ""
        exit 3
    elif [ $DOCKER_STATUS -eq 2 ]; then
        log_error "Failed to setup Docker group. Cannot continue."
        exit 1
    fi

    log_info "✓ Docker is ready to use"
    log_info ""
    log_info "Next step:"
    log_info "  ./scripts/2_setup_kubernetes.sh"
    log_info ""
    log_info "Log file: $LOG_FILE"
}

# Initialize
mkdir -p "$STATE_DIR"
setup_logging

# Run main
main

exit 0
