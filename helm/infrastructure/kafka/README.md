# Kafka Infrastructure Helm Chart

This Helm chart deploys a complete Kafka infrastructure using the Strimzi operator on Kubernetes/Minikube.

## Overview

**Components:**
- Strimzi Kafka Operator (v0.47.0) - Manages Kafka clusters
- Kafka Cluster (v3.9.0) - KRaft mode (no Zookeeper)
- Kafka Topics - Auto-created via KafkaTopic CRDs
- Entity Operators - Topic and User operators

**Features:**
- KRaft mode (Zookeeper-free)
- Single-node deployment (suitable for development/testing)
- NodePort external access (for Minikube)
- Persistent storage (10Gi PVC)
- Automatic topic creation

## Prerequisites

- Kubernetes cluster (Minikube recommended for local development)
- Helm 3.x
- kubectl configured
- 10Gi+ available storage

## Configuration

### Central Configuration

This chart uses `config/config.yaml` as the central configuration file. The chart's `values.yaml` provides defaults, and `config/config.yaml` overrides specific values.

**Relevant sections in config/config.yaml:**

```yaml
kafka:
  topics:
    raw_trade: "iex-topic-1"
    flattened_trade: "iex-topic-1-flattened"
  consumer:
    group_id: "offset-checker"
    enable_auto_commit: false
```

### Chart Values Structure

Key configuration options in `values.yaml`:

| Parameter | Description | Default |
|-----------|-------------|---------|
| `operator.enabled` | Deploy Strimzi operator | `true` |
| `cluster.enabled` | Deploy Kafka cluster | `true` |
| `cluster.name` | Kafka cluster name | `my-cluster` |
| `cluster.namespace` | Deployment namespace | `kafka` |
| `kafka.version` | Kafka version | `3.9.0` |
| `kafka.nodePool.replicas` | Number of Kafka brokers | `1` |
| `kafka.nodePool.storage.size` | PVC size per broker | `10Gi` |
| `kafka.listeners.external.advertisedHost` | Minikube IP for external access | `192.168.49.2` |
| `topics.create` | Create topics via CRDs | `true` |

### Customization

**Override specific values:**

```bash
helm install kafka-infra . \
  -f ../../../config/config.yaml \
  --set kafka.nodePool.replicas=3 \
  --set kafka.nodePool.storage.size=20Gi
```

**Environment-specific configs:**

```bash
# Development
helm install kafka-infra . -f ../../../config/config.yaml -f values-dev.yaml

# Production
helm install kafka-infra . -f ../../../config/config.yaml -f values-prod.yaml
```

## Installation

### Quick Start

```bash
# Using the installation script (recommended)
cd helm/infrastructure/kafka
./scripts/install.sh

# Or manually
helm dependency update
helm install kafka-infra . \
  --namespace kafka \
  --create-namespace \
  --values ../../../config/config.yaml \
  --wait \
  --timeout 10m
```

### Verify Installation

```bash
# Check Strimzi operator
kubectl get pods -n kafka -l name=strimzi-cluster-operator

# Wait for Kafka to be ready
kubectl wait kafka/my-cluster --for=condition=Ready -n kafka --timeout=300s

# Check Kafka cluster
kubectl get kafka -n kafka
kubectl get pods -n kafka -l strimzi.io/cluster=my-cluster

# Check topics
kubectl get kafkatopics -n kafka
```

### Get Connection Details

```bash
# Internal bootstrap servers (from within cluster)
my-cluster-kafka-bootstrap.kafka.svc.cluster.local:9092

# External bootstrap servers (from outside cluster, e.g., host machine)
192.168.49.2:32100
```

## Validation

Validate the chart before installation:

```bash
# Using the validation script
./scripts/validate.sh

# Or manually
helm lint .
helm template kafka-test . -f ../../../config/config.yaml --debug
```

## Usage

### Test Kafka

**From within the cluster:**

```bash
# Producer
kubectl run kafka-producer -ti \
  --image=quay.io/strimzi/kafka:0.47.0-kafka-3.9.0 \
  --rm=true --restart=Never -n kafka \
  -- bin/kafka-console-producer.sh \
     --bootstrap-server my-cluster-kafka-bootstrap.kafka.svc.cluster.local:9092 \
     --topic iex-topic-1

# Consumer
kubectl run kafka-consumer -ti \
  --image=quay.io/strimzi/kafka:0.47.0-kafka-3.9.0 \
  --rm=true --restart=Never -n kafka \
  -- bin/kafka-console-consumer.sh \
     --bootstrap-server my-cluster-kafka-bootstrap.kafka.svc.cluster.local:9092 \
     --topic iex-topic-1 \
     --from-beginning
```

**From host machine (using NodePort):**

```bash
# Get Minikube IP
minikube ip  # Should match kafka.listeners.external.advertisedHost

# Test with kafkacat or any Kafka client
kafkacat -b 192.168.49.2:32100 -L
```

### Create Additional Topics

```bash
kubectl apply -f - <<EOF
apiVersion: kafka.strimzi.io/v1beta2
kind: KafkaTopic
metadata:
  name: my-new-topic
  namespace: kafka
  labels:
    strimzi.io/cluster: my-cluster
spec:
  partitions: 3
  replicas: 1
  config:
    retention.ms: 604800000  # 7 days
EOF
```

### View Kafka Logs

```bash
# Kafka broker logs
kubectl logs -n kafka -l strimzi.io/cluster=my-cluster -c kafka

# Topic operator logs
kubectl logs -n kafka -l strimzi.io/name=my-cluster-entity-operator -c topic-operator
```

## Upgrading

```bash
# Pull latest chart dependencies
helm dependency update

# Upgrade
helm upgrade kafka-infra . \
  --namespace kafka \
  --values ../../../config/config.yaml \
  --wait
```

## Uninstallation

```bash
# Using the uninstall script (recommended)
./scripts/uninstall.sh

# Or manually
helm uninstall kafka-infra -n kafka

# Delete PVCs (optional - will delete all data!)
kubectl delete pvc -n kafka -l strimzi.io/cluster=my-cluster

# Delete namespace (optional)
kubectl delete namespace kafka
```

**Note:** Strimzi CRDs are not automatically removed. To remove them (affects all Kafka clusters):

```bash
kubectl delete crd kafkas.kafka.strimzi.io
kubectl delete crd kafkanodepools.kafka.strimzi.io
kubectl delete crd kafkatopics.kafka.strimzi.io
kubectl delete crd kafkaconnects.kafka.strimzi.io
# ... etc
```

## Troubleshooting

### Operator Not Starting

```bash
# Check operator logs
kubectl logs -n kafka -l name=strimzi-cluster-operator

# Check operator status
kubectl get deployment -n kafka strimzi-cluster-operator
```

### Kafka Cluster Not Ready

```bash
# Check Kafka resource status
kubectl describe kafka my-cluster -n kafka

# Check pod events
kubectl get events -n kafka --sort-by='.lastTimestamp'

# Check broker logs
kubectl logs -n kafka my-cluster-dual-role-0 -c kafka
```

### Topics Not Created

```bash
# Check topic operator logs
kubectl logs -n kafka -l strimzi.io/name=my-cluster-entity-operator -c topic-operator

# Check KafkaTopic resources
kubectl get kafkatopics -n kafka
kubectl describe kafkatopic iex-topic-1 -n kafka
```

### Storage Issues

```bash
# Check PVCs
kubectl get pvc -n kafka

# Check storage class
kubectl get storageclass

# For Minikube, ensure sufficient disk space
minikube ssh "df -h"
```

## Architecture

```
┌─────────────────────────────────────────────┐
│         Strimzi Kafka Operator              │
│  (Manages Kafka resources via CRDs)         │
└──────────────────┬──────────────────────────┘
                   │
                   │ watches/manages
                   ▼
┌─────────────────────────────────────────────┐
│           Kafka Cluster (KRaft)              │
│  ┌────────────────────────────────────┐    │
│  │  KafkaNodePool (dual-role)         │    │
│  │  - Controller + Broker             │    │
│  │  - 1 replica                       │    │
│  │  - 10Gi PVC                        │    │
│  └────────────────────────────────────┘    │
│                                             │
│  Listeners:                                 │
│  - plain:9092 (internal)                   │
│  - tls:9093 (internal)                     │
│  - external:9094 → NodePort:32100          │
│                                             │
│  Entity Operators:                          │
│  - Topic Operator (manages KafkaTopics)    │
│  - User Operator (manages KafkaUsers)      │
└─────────────────────────────────────────────┘
```

## Dependencies

This chart depends on:
- **strimzi-kafka-operator** (v0.47.0) from https://strimzi.io/charts/

Dependencies are automatically downloaded via `helm dependency update`.

## References

- [Strimzi Documentation](https://strimzi.io/docs/)
- [Kafka Documentation](https://kafka.apache.org/documentation/)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Helm Documentation](https://helm.sh/docs/)

## License

This chart is part of the Alpaca Stream Ingestion project.
