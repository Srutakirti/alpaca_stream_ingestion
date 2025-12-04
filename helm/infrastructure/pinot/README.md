# Pinot Infrastructure Helm Chart

This Helm chart deploys Apache Pinot, a realtime distributed OLAP datastore for low-latency analytics.

## Overview

Apache Pinot is designed to deliver scalable real-time analytics with low latency. It can ingest data from:
- Offline sources (Hadoop, flat files)
- Online sources (Kafka)

## Components

- **Controller**: Manages cluster metadata and orchestrates operations
- **Broker**: Handles query routing and aggregation
- **Server**: Stores and serves data segments
- **Minion**: Performs background tasks (optional)
- **ZooKeeper**: Cluster coordination

## Prerequisites

- Kubernetes cluster (Minikube, Multipass VM, or production cluster)
- Helm 3.x
- kubectl configured
- Kafka cluster (for real-time ingestion)

## Installation

### Update Dependencies

```bash
helm dependency update
```

### Install Chart

```bash
# Create namespace
kubectl create namespace pinot

# Install with default values
helm install pinot . --namespace pinot --create-namespace

# Install with custom values
helm install pinot . \
  --namespace pinot \
  --create-namespace \
  -f custom-values.yaml
```

### Install with Central Config

```bash
helm install pinot . \
  --namespace pinot \
  --create-namespace \
  -f ../../config/config.yaml
```

## Configuration

### ZooKeeper

```yaml
pinot-chart:
  zookeeper:
    enabled: true
    replicaCount: 1
    resources:
      requests:
        memory: "512Mi"
        cpu: "250m"
```

### Controller

```yaml
pinot-chart:
  controller:
    enabled: true
    replicaCount: 1
    persistence:
      enabled: false
      size: 10Gi
```

### Broker

```yaml
pinot-chart:
  broker:
    enabled: true
    replicaCount: 1
    service:
      type: NodePort
      nodePort: 30099
```

### Server

```yaml
pinot-chart:
  server:
    enabled: true
    replicaCount: 1
    persistence:
      enabled: false
      size: 10Gi
```

### Kafka Integration

```yaml
kafka:
  bootstrapServers: "my-cluster-kafka-bootstrap.kafka.svc.cluster.local:9092"
  topics:
    - name: "my-topic"
      schema: "my-schema"
```

## Accessing Pinot

### Port Forward (Development)

```bash
# Controller UI (port 9000)
kubectl port-forward -n pinot svc/pinot-controller 9000:9000

# Broker (port 8099)
kubectl port-forward -n pinot svc/pinot-broker 8099:8099
```

Access the UI at: http://localhost:9000

### NodePort (Minikube)

```bash
# Get Minikube IP
minikube ip

# Access broker
curl http://$(minikube ip):30099/health
```

## Creating Tables and Schemas

Pinot tables and schemas are created via REST API after installation.

### Example: Create Schema

```bash
curl -X POST http://localhost:9000/schemas \
  -H "Content-Type: application/json" \
  -d @schema.json
```

### Example: Create Table

```bash
curl -X POST http://localhost:9000/tables \
  -H "Content-Type: application/json" \
  -d @table-config.json
```

See `pinot_notes.txt` in the minikube/pinot directory for example configurations.

## Validation

```bash
./scripts/validate.sh
```

## Uninstall

```bash
helm uninstall pinot --namespace pinot
kubectl delete namespace pinot
```

## Integration with Kafka

This chart is designed to work with the Kafka infrastructure chart. Ensure:

1. Kafka is installed and running
2. Bootstrap servers are accessible
3. Topics are created before creating Pinot tables

Example Kafka bootstrap server:
```
my-cluster-kafka-bootstrap.kafka.svc.cluster.local:9092
```

## Troubleshooting

### Check Pod Status

```bash
kubectl get pods -n pinot
```

### View Logs

```bash
# Controller logs
kubectl logs -n pinot -l app=pinot-controller

# Broker logs
kubectl logs -n pinot -l app=pinot-broker

# Server logs
kubectl logs -n pinot -l app=pinot-server
```

### Check Services

```bash
kubectl get svc -n pinot
```

### Health Check

```bash
# Controller health
kubectl exec -n pinot -it deployment/pinot-controller -- curl localhost:9000/health

# Broker health
kubectl exec -n pinot -it deployment/pinot-broker -- curl localhost:8099/health
```

## References

- [Apache Pinot Documentation](https://docs.pinot.apache.org/)
- [Pinot Helm Chart](https://github.com/apache/pinot/tree/master/kubernetes/helm)
- [Kafka Integration](https://docs.pinot.apache.org/basics/data-import/pinot-stream-ingestion/import-from-apache-kafka)
