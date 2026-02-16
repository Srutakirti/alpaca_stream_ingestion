#!/bin/bash
###############################################################################
# Part 1: Install Dependencies (Config-Driven Version)
#
# Installs all system-level dependencies required for the data engineering stack.
# Reads all configuration from config/config.yaml
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
#   - config/config.yaml with dependencies, directories, and minikube sections
#
# Exit codes:
#   0 - Success
#   1 - Error occurred
#   3 - Docker group needs activation (restart shell required)
#
# Usage:
#   ./scripts/1_install_dependencies_new.sh
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

    log_info "yq not found, installing..."

    # Create ~/.local/bin if it doesn't exist
    mkdir -p "$HOME/.local/bin"

    # Download yq binary
    local YQ_VERSION="v4.44.1"
    local YQ_URL="https://github.com/mikefarah/yq/releases/download/${YQ_VERSION}/yq_linux_amd64"

    if ! curl -kL "$YQ_URL" -o "$HOME/.local/bin/yq" >> "$LOG_FILE" 2>&1; then
        log_error "Failed to download yq from $YQ_URL"
        log_error "Please install yq manually:"
        log_error "  sudo wget -qO /usr/local/bin/yq https://github.com/mikefarah/yq/releases/download/${YQ_VERSION}/yq_linux_amd64"
        log_error "  sudo chmod +x /usr/local/bin/yq"
        exit 1
    fi

    chmod +x "$HOME/.local/bin/yq"

    # Add to PATH for current session
    export PATH="$HOME/.local/bin:$PATH"

    log_info "yq installed successfully to ~/.local/bin/yq"
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
    local path="$1"         # e.g., ".dependencies.docker_version" or ".minikube.cpu"
    local config_file="$2"

    yq eval "$path" "$config_file" 2>/dev/null
}

# Verify config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "ERROR: Config file not found: $CONFIG_FILE"
    exit 1
fi

# Ensure yq is installed before parsing YAML
ensure_yq_installed

# Version Configuration - Read from YAML
DOCKER_VERSION=$(get_yaml_value ".dependencies.docker_version" "$CONFIG_FILE")
MINIKUBE_VERSION=$(get_yaml_value ".dependencies.minikube_version" "$CONFIG_FILE")
KUBECTL_VERSION=$(get_yaml_value ".dependencies.kubectl_version" "$CONFIG_FILE")
HELM_VERSION=$(get_yaml_value ".dependencies.helm_version" "$CONFIG_FILE")
JAVA_VERSION=$(get_yaml_value ".dependencies.java_version" "$CONFIG_FILE")
UV_VERSION=$(get_yaml_value ".dependencies.uv_version" "$CONFIG_FILE")

# Directory Configuration - Read from YAML
STATE_DIR_RAW=$(get_yaml_value ".directories.state_dir" "$CONFIG_FILE")
MINIKUBE_MOUNT_DIR=$(get_yaml_value ".directories.minikube_mount_dir" "$CONFIG_FILE")
MINIKUBE_MOUNT_MINIO=$(get_yaml_value ".directories.minikube_mount_minio" "$CONFIG_FILE")
MINIKUBE_MOUNT_SHR=$(get_yaml_value ".directories.minikube_mount_shr" "$CONFIG_FILE")

# Expand $HOME in STATE_DIR
STATE_DIR="${STATE_DIR_RAW/\$HOME/$HOME}"

# Minikube Resource Configuration - Read from YAML
MINIKUBE_CPU=$(get_yaml_value ".minikube.cpu" "$CONFIG_FILE")
MINIKUBE_MEMORY=$(get_yaml_value ".minikube.memory" "$CONFIG_FILE")

# Verify all values were loaded
if [ -z "$DOCKER_VERSION" ] || [ -z "$MINIKUBE_VERSION" ] || [ -z "$KUBECTL_VERSION" ] || \
   [ -z "$HELM_VERSION" ] || [ -z "$JAVA_VERSION" ] || [ -z "$UV_VERSION" ] || \
   [ -z "$STATE_DIR" ] || [ -z "$MINIKUBE_MOUNT_DIR" ] || \
   [ -z "$MINIKUBE_CPU" ] || [ -z "$MINIKUBE_MEMORY" ]; then
    echo "ERROR: Failed to load all configuration from $CONFIG_FILE"
    echo "Loaded values:"
    echo "  Docker: $DOCKER_VERSION"
    echo "  Minikube: $MINIKUBE_VERSION"
    echo "  Kubectl: $KUBECTL_VERSION"
    echo "  Helm: $HELM_VERSION"
    echo "  Java: $JAVA_VERSION"
    echo "  UV: $UV_VERSION"
    echo "  State Dir: $STATE_DIR"
    echo "  Minikube Mount Dir: $MINIKUBE_MOUNT_DIR"
    echo "  Minikube CPU: $MINIKUBE_CPU"
    echo "  Minikube Memory: $MINIKUBE_MEMORY"
    exit 1
fi

# ============================================================================
# SETUP LOGGING
# ============================================================================

setup_logging() {
    {
        echo "========================================="
        echo "Part 1: Install Dependencies (Config-Driven)"
        echo "Started: $(date)"
        echo "User: $USER"
        echo "Hostname: $(hostname)"
        echo "Config file: $CONFIG_FILE"
        echo "========================================="
        echo ""
        echo "Dependency Versions:"
        echo "  Docker: $DOCKER_VERSION"
        echo "  Minikube: $MINIKUBE_VERSION"
        echo "  Kubectl: $KUBECTL_VERSION"
        echo "  Helm: $HELM_VERSION"
        echo "  Java: $JAVA_VERSION"
        echo "  UV: $UV_VERSION"
        echo ""
        echo "Directory Configuration:"
        echo "  State Dir: $STATE_DIR"
        echo "  Minikube Mount Dir: $MINIKUBE_MOUNT_DIR"
        echo "  Minikube Mount MinIO: $MINIKUBE_MOUNT_MINIO"
        echo "  Minikube Mount SHR: $MINIKUBE_MOUNT_SHR"
        echo ""
        echo "Minikube Resources:"
        echo "  CPU: $MINIKUBE_CPU"
        echo "  Memory: ${MINIKUBE_MEMORY}MB"
        echo ""
    } >> "$LOG_FILE"
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
    sudo curl -kfsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
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

    curl -kLsSf https://astral.sh/uv/$UV_VERSION/install.sh | sh >> "$LOG_FILE" 2>&1

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
    curl -kLO https://github.com/kubernetes/minikube/releases/download/$MINIKUBE_VERSION/minikube-linux-amd64 >> "$LOG_FILE" 2>&1
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

    curl -kLO https://get.helm.sh/helm-$HELM_VERSION-linux-amd64.tar.gz >> "$LOG_FILE" 2>&1
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

    curl -kLO https://dl.k8s.io/release/$KUBECTL_VERSION/bin/linux/amd64/kubectl >> "$LOG_FILE" 2>&1
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
    log_info "Config-Driven Version"
    log_info "========================================="
    log_info ""
    log_info "Configuration loaded from: $CONFIG_FILE"
    log_info ""
    log_info "Dependency Versions:"
    log_info "  Docker: $DOCKER_VERSION"
    log_info "  Minikube: $MINIKUBE_VERSION"
    log_info "  Kubectl: $KUBECTL_VERSION"
    log_info "  Helm: $HELM_VERSION"
    log_info "  Java: $JAVA_VERSION"
    log_info "  UV: $UV_VERSION"
    log_info ""
    log_info "Minikube Resources:"
    log_info "  CPU: $MINIKUBE_CPU"
    log_info "  Memory: ${MINIKUBE_MEMORY}MB"
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
