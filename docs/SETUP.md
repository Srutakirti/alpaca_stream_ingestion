# Setup Guide

Complete installation and configuration guide for the Alpaca Stream Ingestion pipeline.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Automated Setup (Recommended)](#automated-setup-recommended)
- [Manual Setup](#manual-setup)
- [Configuration](#configuration)
- [Verification](#verification)

---

## Prerequisites

### Hardware Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU | 8 cores | 12+ cores |
| RAM | 15 GB | 20+ GB |
| Disk | 20 GB free | 50+ GB free |
| OS | Ubuntu 22.04 | Ubuntu 22.04+ |

### Required Software

The automated setup script will install these for you:
- **Docker** (v28.5+)
- **Minikube** (v1.36+)
- **kubectl** (v1.34+)
- **Helm** (v3.19+)
- **Java** (OpenJDK 17)
- **Apache Spark** (3.5.1)
- **UV** (Python package manager 0.9+)

### Optional: Alpaca API Credentials

For live stock market data:
1. Sign up for free tier at [alpaca.markets](https://alpaca.markets)
2. Generate API key and secret
3. Set environment variables:
   ```bash
   export ALPACA_KEY="your_api_key"
   export ALPACA_SECRET="your_api_secret"
   ```

**Note:** You can use the sample data generator without Alpaca credentials.

---

## Automated Setup (Recommended)

### Step 1: Clone Repository

```bash
git clone <repository-url>
cd alpaca_stream_ingestion
```

### Step 2: View Setup Options

```bash
chmod +x test_new_2.sh
./test_new_2.sh --help
```

**Available flags:**
- `--setup-infra`: Install system dependencies (Docker, UV, Java, Spark)
- `--setup-minikube`: Install and start Minikube cluster
- `--setup-kafka`: Deploy Kafka (Strimzi operator)
- `--setup-minio`: Deploy MinIO (S3-compatible storage)
- `--setup-pinot`: Deploy Apache Pinot
- `--setup-app`: Deploy WebSocket extractor (requires Alpaca credentials)
- `--port-forward`: Set up port forwarding for all services
- `--cleanup`: Remove all components

### Step 3: Run Full Setup

```bash
# Complete infrastructure setup (5-10 minutes)
./test_new_2.sh --setup-infra --setup-minikube --setup-kafka --setup-minio --setup-pinot

# Enable port forwarding
./test_new_2.sh --port-forward
```

This will:
1. Install Docker, Minikube, kubectl, Helm, Java, Spark, UV
2. Start Minikube cluster with 8 CPUs and 15GB RAM
3. Deploy Kafka cluster (Strimzi operator + 3 brokers)
4. Deploy MinIO for object storage
5. Deploy Apache Pinot for analytics
6. Set up port forwarding to localhost

### Step 4: (Optional) Deploy WebSocket Extractor

```bash
# Only if you have Alpaca credentials
export ALPACA_KEY="your_api_key"
export ALPACA_SECRET="your_api_secret"

./test_new_2.sh --setup-app
```

### Step 5: Install Python Dependencies

```bash
# Install UV if not done by script
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env

# Install project dependencies
uv pip install -e .
```

---

## Manual Setup

### Step 1: Install System Dependencies

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Java
sudo apt install -y openjdk-17-jdk

# Verify Java installation
java -version
```

### Step 2: Install Docker

```bash
# Install Docker
sudo apt install -y docker.io

# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Verify Docker
docker --version
docker ps
```

### Step 3: Install Minikube

```bash
# Download Minikube
curl -LO https://storage.googleapis.com/minikube/releases/latest/minikube-linux-amd64

# Install
sudo install minikube-linux-amd64 /usr/local/bin/minikube

# Verify
minikube version
```

### Step 4: Install kubectl

```bash
# Download kubectl
curl -LO "https://dl.k8s.io/release/v1.34.0/bin/linux/amd64/kubectl"

# Install
sudo install -o root -g root -m 0755 kubectl /usr/local/bin/kubectl

# Verify
kubectl version --client
```

### Step 5: Install Helm

```bash
# Download Helm
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash

# Verify
helm version
```

### Step 6: Install Apache Spark

```bash
# Download Spark
cd ~
wget https://archive.apache.org/dist/spark/spark-3.5.1/spark-3.5.1-bin-hadoop3.tgz

# Extract
tar -xzf spark-3.5.1-bin-hadoop3.tgz
mv spark-3.5.1-bin-hadoop3 spark-3.5.1

# Set environment variables (add to ~/.bashrc for persistence)
export SPARK_HOME=~/spark-3.5.1
export PATH=$SPARK_HOME/bin:$PATH
export PYSPARK_PYTHON=python3

# Verify
spark-submit --version
```

### Step 7: Install UV and Python Dependencies

```bash
# Install UV
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env

# Install project dependencies
cd ~/alpaca_stream_ingestion
uv pip install -e .

# Install snappy compression library
sudo apt-get install -y libsnappy-dev
pip install python-snappy
```

### Step 8: Start Minikube

```bash
# Start Minikube with sufficient resources
minikube start \
  --cpus=8 \
  --memory=14999 \
  --driver=docker \
  --addons=metrics-server,ingress,dashboard

# Verify
minikube status
kubectl get nodes
```

### Step 9: Deploy Kafka (Strimzi)

```bash
cd ~/alpaca_stream_ingestion

# Create Kafka namespace
kubectl apply -f minikube/kafka/00-kafka_ns.yaml

# Install Strimzi operator
kubectl apply -f minikube/kafka/01-stimzi_operator.yaml

# Wait for operator to be ready (may take 2-3 minutes)
kubectl wait --for=condition=ready pod \
  -l name=strimzi-cluster-operator \
  -n kafka \
  --timeout=300s

# Deploy Kafka cluster
kubectl apply -f minikube/kafka/02-kafka_deploy.yaml

# Wait for Kafka to be ready (may take 5-10 minutes)
kubectl wait kafka/my-cluster \
  --for=condition=Ready \
  --timeout=600s \
  -n kafka

# Port-forward Kafka to localhost
kubectl port-forward -n kafka svc/my-cluster-kafka-bootstrap 9092:9092 &
```

### Step 10: Deploy MinIO

```bash
# Create MinIO data directory
mkdir -p /mnt/mydrive2/minio

# Deploy MinIO
kubectl apply -f minikube/minio/

# Wait for MinIO to be ready
kubectl wait --for=condition=ready pod \
  -l app=minio \
  -n minio \
  --timeout=300s

# Port-forward MinIO
kubectl port-forward -n minio svc/minio 9000:9000 9001:9001 &

# Access MinIO console at http://localhost:9001
# Default credentials: minioadmin / minioadmin
```

### Step 11: Deploy Apache Pinot

```bash
# Add Pinot Helm repository
helm repo add pinot https://raw.githubusercontent.com/apache/pinot/master/kubernetes/helm
helm repo update

# Install Pinot
helm install pinot pinot/pinot \
  -n pinot \
  --create-namespace \
  -f minikube/pinot/myvalues.yaml

# Wait for Pinot to be ready (may take 3-5 minutes)
kubectl wait --for=condition=ready pod \
  -l app=pinot \
  -n pinot \
  --timeout=300s

# Port-forward Pinot controller
kubectl port-forward -n pinot svc/pinot-controller 9000:9000 &

# Access Pinot console at http://localhost:9000
```

---

## Configuration

### Environment Variables

Add these to your `~/.bashrc` for persistence:

```bash
# Alpaca API credentials (optional, for live data)
export ALPACA_KEY="your_api_key"
export ALPACA_SECRET="your_api_secret"

# Spark configuration
export SPARK_HOME=~/spark-3.5.1
export PATH=$SPARK_HOME/bin:$PATH
export PYSPARK_PYTHON=python3

# Java
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
export PATH=$JAVA_HOME/bin:$PATH

# Minikube (if using custom location)
export MINIKUBE_HOME=/nvmewd/minikube_home
```

Apply changes:
```bash
source ~/.bashrc
```

### Minikube Resource Configuration

Edit resources after creation:

```bash
# Stop Minikube
minikube stop

# Delete and recreate with new resources
minikube delete
minikube start --cpus=12 --memory=20000 --driver=docker
```

### Kafka Configuration

Edit `minikube/kafka/02-kafka_deploy.yaml` to customize:

```yaml
spec:
  kafka:
    replicas: 3  # Number of Kafka brokers
    config:
      num.partitions: 3  # Default partitions for new topics
      default.replication.factor: 1
      min.insync.replicas: 1
      log.retention.hours: 168  # 7 days
```

Apply changes:
```bash
kubectl apply -f minikube/kafka/02-kafka_deploy.yaml
```

### MinIO Configuration

Default credentials are `minioadmin` / `minioadmin`.

To change, edit MinIO deployment manifest before applying:

```yaml
env:
  - name: MINIO_ROOT_USER
    value: "admin"
  - name: MINIO_ROOT_PASSWORD
    value: "your_secure_password"
```

### Pinot Configuration

Edit `minikube/pinot/myvalues.yaml` to customize Pinot deployment:

```yaml
controller:
  replicaCount: 1

broker:
  replicaCount: 1

server:
  replicaCount: 1
```

---

## Verification

### Check All Services

```bash
# View all running pods
kubectl get pods -A

# Expected namespaces:
# - kafka: Strimzi operator + 3 Kafka brokers
# - minio: MinIO pod
# - pinot: Pinot controller, broker, server

# Check service endpoints
minikube service list
```

### Test Kafka

```bash
# List Kafka topics
kubectl exec -it my-cluster-kafka-0 -n kafka -- \
  bin/kafka-topics.sh \
  --bootstrap-server localhost:9092 \
  --list

# Create test topic
python extract/admin/create_kafka_topic.py \
  --topic test_topic \
  --partitions 3 \
  --replication-factor 1 \
  --bootstrap-servers localhost:9092
```

### Test MinIO

```bash
# Access MinIO console
open http://localhost:9001

# Login with minioadmin / minioadmin
# Create a bucket named "warehouse"
```

### Test Pinot

```bash
# Access Pinot query console
open http://localhost:9000

# Verify controller is accessible
curl http://localhost:9000/health
```

### Test Spark

```bash
# Start PySpark shell
pyspark

# Verify Spark is working
>>> spark.range(10).show()
>>> exit()
```

### Run Sample Pipeline

```bash
# Terminal 1: Start sample data generator
python minikube/kafka/sample_event_generators/stream_producer_cli.py \
  --kafka-brokers localhost:9092 \
  --topic iex_data \
  --symbols AAPL \
  --batch-size 10 \
  --interval 5

# Terminal 2: Consume from Kafka (verify data is flowing)
python extract/admin/kafka_consumer_stdout.py \
  --topic iex_data \
  --bootstrap-servers localhost:9092
```

---

## Next Steps

- See **[Pipeline Components](PIPELINE.md)** for detailed component documentation
- See **[Usage Guide](USAGE.md)** for operations and examples
- See **[Troubleshooting](TROUBLESHOOTING.md)** if you encounter issues

---

## Cleanup

### Stop Services (preserve data)

```bash
# Stop Minikube
minikube stop

# Stop port-forwarding processes
pkill -f "kubectl port-forward"
```

### Delete Everything

```bash
# Delete Minikube cluster (destroys all data)
minikube delete

# Remove Spark installation
rm -rf ~/spark-3.5.1

# Remove project virtual environment
rm -rf .venv
```

### Selective Cleanup

```bash
# Delete specific namespace
kubectl delete namespace kafka
kubectl delete namespace pinot
kubectl delete namespace minio

# Remove Helm releases
helm uninstall pinot -n pinot
```
