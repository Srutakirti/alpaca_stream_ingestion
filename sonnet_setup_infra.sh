#!/bin/bash

###############################################################################
# Data Engineering Infrastructure Setup Script
# For Ubuntu VM - Installs Docker, Minikube, Kafka (Strimzi), Pinot, Spark
#
# Usage: ./setup_infra.sh [OPTIONS]
# Options:
#   --skip-docker       Skip Docker installation
#   --skip-java        Skip Java installation
#   --skip-minikube    Skip Minikube installation
#   --skip-spark       Skip Spark installation
#   --help             Show this help message
#
# Requirements:
#   - Ubuntu Linux
#   - Minimum 32GB RAM
#   - 8 CPU cores
#   - 100GB free disk space
#   - Internet connection
###############################################################################

set -e  # Exit on error

# Trap errors
trap 'echo "Error: Script failed on line $LINENO"; exit 1' ERR

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration variables
MINIKUBE_VERSION="v1.36.0"
KUBECTL_VERSION="v1.34.0"
HELM_VERSION="v3.19.0"
SPARK_VERSION="3.5.1"
HADOOP_VERSION="3"
JAVA_VERSION="17"

MINIKUBE_MOUNT_DIR="/mnt/mydrive2"
MINIKUBE_MOUNT_MINIO="$MINIKUBE_MOUNT_DIR"/minio
MINIKUBE_MOUNT_SHR="$MINIKUBE_MOUNT_DIR"/shr
MINIKUBE_CPU=7
MINIKUBE_MEMORY=31000

# Flags for skipping components
SKIP_DOCKER=false
SKIP_JAVA=false
SKIP_MINIKUBE=false
SKIP_SPARK=false

###############################################################################
# Utility Functions
###############################################################################

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

download_with_retry() {
    local url=$1
    local output=$2
    local max_attempts=3
    local attempt=1
    
    while [ $attempt -le $max_attempts ]; do
        if curl -L "$url" -o "$output" -k; then
            return 0
        fi
        log_warn "Download failed, attempt $attempt of $max_attempts"
        attempt=$((attempt + 1))
        sleep 5
    done
    log_error "Failed to download after $max_attempts attempts"
    return 1
}

check_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "Required command '$1' not found"
        return 1
    fi
}

wait_for_pod_ready() {
    local namespace=$1
    local label=$2
    local timeout=300
    local interval=10
    local elapsed=0

    while [ $elapsed -lt $timeout ]; do
        if kubectl get pods -n "$namespace" -l "$label" | grep -q "Running"; then
            log_info "Pod with label $label is ready"
            return 0
        fi
        sleep $interval
        elapsed=$((elapsed + interval))
        log_info "Waiting for pod with label $label... ($elapsed/${timeout}s)"
    done
    log_error "Timeout waiting for pod with label $label"
    return 1
}

###############################################################################
# Prerequisites Check
###############################################################################

check_prerequisites() {
    log_info "Checking prerequisites..."

    # Check if running as root
    if [[ $(id -u) -eq 0 ]]; then
        log_error "Do not run this script as root"
        exit 1
    }

    # Check system resources
    TOTAL_MEM=$(free -g | awk '/^Mem:/{print $2}')
    if [ $TOTAL_MEM -lt 32 ]; then
        log_warn "Less than 32GB RAM detected. This might affect performance."
    }

    CPU_CORES=$(nproc)
    if [ $CPU_CORES -lt 8 ]; then
        log_warn "Less than 8 CPU cores detected. This might affect performance."
    }

    # Check required commands
    for cmd in curl wget sudo apt-get; do
        check_command "$cmd" || exit 1
    done

    # Check disk space
    FREE_SPACE=$(df -BG "${MINIKUBE_MOUNT_DIR}" | awk 'NR==2 {print $4}' | sed 's/G//')
    if [ "${FREE_SPACE}" -lt 100 ]; then
        log_error "Insufficient disk space. Need at least 100GB free."
        exit 1
    }
}

###############################################################################
# Docker Installation
###############################################################################

install_docker() {
    if $SKIP_DOCKER; then
        log_info "Skipping Docker installation"
        return 0
    }

    if command -v docker &> /dev/null; then
        log_info "Docker already installed"
        return 0
    }

    log_info "Installing Docker..."
    
    # Rest of your existing Docker installation code...
    # (Keep your existing Docker installation code here)
}

###############################################################################
# Component Installation Functions
###############################################################################

# Keep your existing installation functions but add checks:
# - install_minikube()
# - install_helm()
# - install_kubectl()
# - install_java()
# - install_spark()
# - build_spark_img()
# - minikube_start()
# - deploy_kafka()
# - deploy_pinot()
# - deploy_minio()

###############################################################################
# Kubernetes Resource Deployment
###############################################################################

verify_deployments() {
    log_info "Verifying deployments..."

    # Wait for Kafka
    wait_for_pod_ready "kafka" "app=kafka" || exit 1

    # Wait for Pinot
    wait_for_pod_ready "pinot-quickstart" "app=pinot" || exit 1

    # Wait for Minio
    wait_for_pod_ready "minio-operator" "app=minio" || exit 1

    log_info "All deployments are ready"
}

###############################################################################
# Argument Parsing
###############################################################################

parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --skip-docker)
                SKIP_DOCKER=true
                shift
                ;;
            --skip-java)
                SKIP_JAVA=true
                shift
                ;;
            --skip-minikube)
                SKIP_MINIKUBE=true
                shift
                ;;
            --skip-spark)
                SKIP_SPARK=true
                shift
                ;;
            --help)
                echo "Usage: $0 [OPTIONS]"
                echo "Options:"
                echo "  --skip-docker     Skip Docker installation"
                echo "  --skip-java      Skip Java installation"
                echo "  --skip-minikube  Skip Minikube installation"
                echo "  --skip-spark     Skip Spark installation"
                echo "  --help           Show this help message"
                exit 0
                ;;
            *)
                log_error "Unknown option: $1"
                exit 1
                ;;
        esac
    done
}

###############################################################################
# Main
###############################################################################

main() {
    parse_args "$@"
    check_prerequisites

    # Create backup directory
    BACKUP_DIR="$HOME/infra_setup_backup_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$BACKUP_DIR"

    # Backup existing configurations
    if [ -f /etc/environment ]; then
        cp /etc/environment "$BACKUP_DIR/"
    fi

    # Run installations
    install_docker
    install_minikube
    install_helm
    install_kubectl
    install_java
    install_spark
    minikube_start
    build_spark_img
    deploy_kafka
    deploy_pinot
    deploy_minio

    # Verify deployments
    verify_deployments

    log_info "Infrastructure setup completed successfully!"
    log_info "Backup of configurations saved in: $BACKUP_DIR"
}

# Execute main function with all arguments
main "$@"