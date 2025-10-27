#!/bin/bash
#not depending on s3 for now
# also set alpaca sercrtes as env vars  brofore running this script

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

# --- State dir for idempotency ---
STATE_DIR="/tmp/.setup_infra_state"
mkdir -p "$STATE_DIR"

# --- Ensure docker group and re-exec to pick it up (no sudo for docker thereafter) ---
DOCKER_GROUP_ACTIVATED="${DOCKER_GROUP_ACTIVATED:-0}"

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
        exec sg docker -c "$CMD"
    else
        # newgrp - not always available with -c on all distros; we try it as a fallback
        if newgrp docker -c "$CMD" >/dev/null 2>&1; then
            exec newgrp docker -c "$CMD"
        else
            log_error "Neither 'sg' nor working 'newgrp -c' available to re-exec under docker group. Please logout/login to pick up group membership."
            return 1
        fi
    fi

    # exec replaces process; we should not reach here.
    return 1
}

# Configuration variables
DOCKER_VERSION="5:28.5.1-1~ubuntu.25.10~questing"
MINIKUBE_VERSION="v1.36.0"
KUBECTL_VERSION="v1.34.0"
HELM_VERSION="v3.19.0"
SPARK_VERSION="3.5.1"
HADOOP_VERSION="3"
JAVA_VERSION="openjdk-17-jdk"
UV_VERSION="latest"

MINIKUBE_MOUNT_DIR="/mnt/mydrive2"
MINIKUBE_MOUNT_MINIO="$MINIKUBE_MOUNT_DIR"/minio
MINIKUBE_MOUNT_SHR="$MINIKUBE_MOUNT_DIR"/shr
MINIKUBE_CPU=4
MINIKUBE_MEMORY=31000


###############################################################################
# Docker  Installation
###############################################################################

install_docker() {

    # idempotent: skip if marker exists
    if [ -f "$STATE_DIR/docker_installed" ]; then
        log_info "Skipping Docker install (marker found)."
        return 0
    fi

    log_info "preparing to install docker"

    # Add Docker's official GPG key:
    sudo apt-get update
    sudo apt-get install -y ca-certificates curl
    sudo install -m 0755 -d /etc/apt/keyrings
    sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
    sudo chmod a+r /etc/apt/keyrings/docker.asc

    # Add the repository to Apt sources:
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
      $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}") stable" | \
      sudo tee /etc/apt/sources.list.d/docker.list > /dev/null
    sudo apt-get update

    sudo apt-get install -y docker-ce="$DOCKER_VERSION" docker-ce-cli="$DOCKER_VERSION" containerd.io docker-buildx-plugin docker-compose-plugin

    ##add user to docker group (idempotent)
    sudo usermod -aG docker "$USER"

    # create marker so we don't re-run install
    touch "$STATE_DIR/docker_installed"

    log_info "docker installed successfully."
}

###############################################################################
# UV  Installation
###############################################################################

install_uv() {
curl -LsSf https://astral.sh/uv/0.9.2/install.sh -k| sh
source $HOME/.local/bin/env
}

###############################################################################
# Minikube  Installation
###############################################################################

install_minikube() {
    # idempotent
    if [ -f "$STATE_DIR/minikube_installed" ]; then
        log_info "Skipping minikube install (marker found)."
        return 0
    fi

    ##install minikube
    curl -LO https://github.com/kubernetes/minikube/releases/download/$MINIKUBE_VERSION/minikube-linux-amd64
    sudo install minikube-linux-amd64 /usr/local/bin/minikube && rm minikube-linux-amd64

    ##configs for minikube and setup the dirs to be mounted
    sudo mkdir -p  "$MINIKUBE_MOUNT_DIR"
    sudo chmod 777 "$MINIKUBE_MOUNT_DIR"

    mkdir -p "$MINIKUBE_MOUNT_MINIO"
    mkdir -p "$MINIKUBE_MOUNT_SHR" ##both would be used one for minio and another for code/jar sharing

    minikube config set cpus "$MINIKUBE_CPU"
    minikube config set memory "$MINIKUBE_MEMORY" ##set it according to the VM

    touch "$STATE_DIR/minikube_installed"
    log_info "minikube installed successfully"
}

###############################################################################
# Helm  Installation
###############################################################################
install_helm() {
    if [ -f "$STATE_DIR/helm_installed" ]; then
        log_info "Skipping helm install (marker found)."
        return 0
    fi

    curl -LO https://get.helm.sh/helm-$HELM_VERSION-linux-amd64.tar.gz -k
    tar -xzvf helm-$HELM_VERSION-linux-amd64.tar.gz
    sudo mv linux-amd64/helm /usr/local/bin
    rm -rf helm-$HELM_VERSION-linux-amd64.tar.gz linux-amd64

    touch "$STATE_DIR/helm_installed"
}

###############################################################################
# Kubectl  Installation
###############################################################################
install_kubectl() {
    if [ -f "$STATE_DIR/kubectl_installed" ]; then
        log_info "Skipping kubectl install (marker found)."
        return 0
    fi

    curl -LO https://dl.k8s.io/release/$KUBECTL_VERSION/bin/linux/amd64/kubectl -k
    sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl
    rm kubectl

    touch "$STATE_DIR/kubectl_installed"
}

###############################################################################
# Java  Installation
###############################################################################

install_java() {
    if [ -f "$STATE_DIR/java_installed" ]; then
        log_info "Skipping Java install (marker found)."
        return 0
    fi

    echo "Installing $JAVA_VERSION..."
    sudo apt-get install -y "$JAVA_VERSION"

    echo "Verifying installation..."
    java -version
    javac -version

    # Find JDK installation path
    JAVA_PATH=$(readlink -f /usr/bin/java | sed "s:bin/java::")

    echo "Setting JAVA_HOME..."
    # Add JAVA_HOME to /etc/environment if not already present
    if grep -q "JAVA_HOME" /etc/environment; then
        echo "JAVA_HOME already set in /etc/environment"
    else
        echo "JAVA_HOME=$JAVA_PATH" | sudo tee -a /etc/environment
        echo "JAVA_HOME added to /etc/environment"
    fi

    # Export JAVA_HOME for current session
    export JAVA_HOME=$JAVA_PATH
    echo "JAVA_HOME is set to $JAVA_HOME"

    touch "$STATE_DIR/java_installed"
    echo "Done."
}

###############################################################################
# Spark  Installation
###############################################################################
install_spark() {
    if [ -f "$STATE_DIR/spark_installed" ]; then
        log_info "Skipping Spark install (marker found)."
        return 0
    fi

    curl -L https://archive.apache.org/dist/spark/spark-3.5.1/spark-3.5.1-bin-hadoop3.tgz -o ~/spark-download.tgz -k
    # Extract with a specific directory name
    mkdir -p ~/spark-3.5.1
    tar -xzf ~/spark-download.tgz -C ~/spark-3.5.1 --strip-components=1
    # Clean up the downloaded archive file (optional)
    rm ~/spark-download.tgz
    # Verify installation
    echo "Spark extracted to: ~/spark-3.5.1"

    touch "$STATE_DIR/spark_installed"
}

#######setting up kubernetes resource
###############################################################################
# Enable docker user
###############################################################################
enable_docker_user() {
    log_info "Adding user to docker group..."
    sudo usermod -aG docker "$USER"

    # Create a subshell to run newgrp
    (
        exec sg docker -c "
            # Set environment variable to indicate docker group is active
            # export DOCKER_GROUP_ACTIVE=1
            echo 'Docker group enabled in current session'
        "
    )
}


###############################################################################
# Minikube Start
###############################################################################

# Verify docker access before starting minikube
# ./docker_perms.sh
minikube_start() {
    # sudo systemctl restart docker
    if ! docker info >/dev/null 2>&1; then
        log_error "Failed to run docker command without sudo. Please check docker installation."
        exit 1
    fi
    minikube start --mount --mount-string="$MINIKUBE_MOUNT_DIR:/mnt"

    ## enable ingress for minio
    minikube addons enable ingress

}

###############################################################################
# Spark Image Building
###############################################################################
build_spark_img() {

    # minikube start --mount --mount-string="$MINIKUBE_MOUNT_DIR:/mnt"

    #sudo systemctl restart docker
    eval $(minikube docker-env)
    docker build -t spark:v3.5.2.2  -f ~/alpaca_stream_ingestion/minikube/spark/Dockerfile  ~/spark-3.5.1
    docker build   --build-arg base_img=spark:v3.5.2.2   -t pyspark:v3.5.2.3 -f ~/alpaca_stream_ingestion/minikube/spark/Dockerfile_pyspark ~/spark-3.5.1

}


###############################################################################
# Kafka cluster creation
###############################################################################
deploy_kafka() {
    kubectl apply -f minikube/kafka/00-kafka_ns.yaml
    kubectl apply -f minikube/kafka/01-stimzi_operator.yaml
    sleep 5
    kubectl apply -f minikube/kafka/02-kafka_deploy.yaml
}

###############################################################################
# Pinot Deployment
###############################################################################
deploy_pinot() {
    kubectl create ns pinot-quickstart || true
    helm install -n pinot-quickstart pinot minikube/pinot/pinot-0.3.4.tgz -f minikube/pinot/myvalues.yaml || true
}

###############################################################################
# Minio Deployment
###############################################################################
deploy_minio() {
    kubectl apply -f minikube/minio/00-minio-operator.yaml
    sleep 5
    kubectl apply -f minikube/minio
}

####Setup the DE Application

###############################################################################
# setup mc client for buckets
###############################################################################
install_mc_client() {
wget https://dl.min.io/client/mc/release/linux-amd64/mc
chmod +x mc
sudo mv mc  /usr/local/bin
mc alias set  s3 http://minio-api.192.168.49.2.nip.io:80  minio minio123
mc mb s3/spark-logs/events #used for spark app logs
mc mb s3/data #for chkpt of spark streaming app
}

###############################################################################
# Create topics and pinot tables (can be containerized)
###############################################################################
#(portforwarding must happen for pinot controller create.py to work)
setup_de_app() {
    nohup  minikube/pinot/query-pinot-data.sh > /tmp/setup_infra.log 2>&1 &
    sleep 5 # sleep to wait for the port forward
    uv run extract/admin/create_kafka_topic.py
    uv run load/create.py
    ##create extractor image and deploy
    kubectl create configmap app-config \
      --from-file=config.yaml=config/config.yaml || true
    kubectl create secret generic alpaca-creds \
      --from-literal=ALPACA_KEY="$ALPACA_KEY" \
      --from-literal=ALPACA_SECRET="$ALPACA_SECRET" || true
    eval $(minikube docker-env)
    docker build -t ws_scraper:v1.0 -f extract/app/Dockerfile extract/app
    kubectl apply -f minikube/extractor_deploy/extractor_deploy.yaml

    ##run spark job to read from kafka and write to pinot topic
    cp transform/spark_streaming_flattener.py "$MINIKUBE_MOUNT_SHR"
    ##setup spark resources
    kubectl apply -f minikube/spark/spark_resources.yaml
}

main() {
    # Install docker once (idempotent)
    install_docker

    # Ensure docker group is active for this session (may prompt for sudo once).
    # This will re-exec the script under the docker group if required. Because install_docker
    # writes a marker, the re-exec will skip the install step.
    ensure_docker_group_no_sudo "$@" || { log_error "Could not activate docker group for session"; exit 1; }

    # The rest of your flow (kept as comments so you can enable as needed)
    install_uv
    install_minikube
    install_helm
    install_kubectl
    install_java
    install_spark
    enable_docker_user
    minikube_start
    build_spark_img
    deploy_kafka
    deploy_pinot
    deploy_minio
    install_mc_client
    setup_de_app
}

main
