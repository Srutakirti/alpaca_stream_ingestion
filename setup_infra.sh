#!/bin/bash

###############################################################################
# Data Engineering Infrastructure Setup Script
# For Ubuntu VM - Installs Docker, Minikube, Kafka (Strimzi), Pinot, Spark
###############################################################################

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Configuration variables
MINIKUBE_VERSION="v1.36.0"
KUBECTL_VERSION="v1.28.0"
HELM_VERSION="v3.13.0"
SPARK_VERSION="3.5.0"
HADOOP_VERSION="3"
JAVA_VERSION="11"
UV_VERSION="latest"

MINIKUBE_MOUNT_DIR="/mnt/mydrive2"
MINIKUBE_MOUNT_MINIO="$MINIKUBE_MOUNT_DIR"/minio
MINIKUBE_MOUNT_SHR="$MINIKUBE_MOUNT_DIR"/shr
MINIKUBE_CPU=7
MINIKUBE_MEMORY=31000

###############################################################################
# Docker  Installation
###############################################################################

install_docker() {

log_info "preparing to install docker"

# Add Docker's official GPG key:
sudo apt-get update
sudo apt-get install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

# Add the repository to Apt sources:
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
sudo apt-get update

sudo apt-get install -y docker-ce=5:28.5.0-1~ubuntu.24.04~noble  docker-ce-cli=5:28.5.0-1~ubuntu.24.04~noble  containerd.io docker-buildx-plugin docker-compose-plugin

##add user to dokcer group
sudo usermod -aG docker $USER && newgrp docker

log_info "dokcer installed successfully."
}

###############################################################################
# Minikube  Installation
###############################################################################

install_minikube() {
##install minikube
curl -LO https://github.com/kubernetes/minikube/releases/download/$MINIKUBE_VERSION/minikube-linux-amd64
sudo install minikube-linux-amd64 /usr/local/bin/minikube && rm minikube-linux-amd64

##configs for minikube and setup the dirs to be mounted

sudo mkdir -p  $MINIKUBE_MOUNT_DIR

sudo chmod 777 $MINIKUBE_MOUNT_DIR

mkdir $MINIKUBE_MOUNT_MINIO;mkdir $MINIKUBE_MOUNT_SHR ##both would be used one for minio and another for code/jar sharing

minikube config set cpus $MINIKUBE_CPU;minikube config set memory $MINIKUBE_MEMORY ##set it according to the VM
log_info "minikube installed successfully"
}

main() {
#install_docker
install_minikube
}

main
