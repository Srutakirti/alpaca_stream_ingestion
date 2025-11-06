# Strimzi Kafka Connect - Complete Guide

**Source**: Official Strimzi Documentation (strimzi.io)
**Version**: Based on Strimzi 0.48.0 (latest)

---

## Table of Contents

1. [Overview](#overview)
2. [Architecture](#architecture)
3. [Prerequisites](#prerequisites)
4. [Deployment Steps](#deployment-steps)
5. [Configuration Options](#configuration-options)
6. [Adding Connector Plugins](#adding-connector-plugins)
7. [Creating Connectors](#creating-connectors)
8. [Monitoring and Management](#monitoring-and-management)
9. [Examples](#examples)
10. [Troubleshooting](#troubleshooting)
11. [References](#references)

---

## Overview

**Kafka Connect** is an integration toolkit for streaming data between Kafka brokers and other systems using a plugin architecture. In Strimzi, Kafka Connect runs in **distributed mode** across multiple worker pods for high scalability and fault tolerance.

### Key Components

1. **Connectors** - Source (push data into Kafka) or Sink (extract data from Kafka)
2. **Tasks** - Parallel data transfer units distributed across workers
3. **Workers** - Pod instances running tasks and connector instances
4. **Transforms** - Single-message modifications adjusting data format
5. **Converters** - Format translation (JSON, Avro, schema-based)

### Benefits

- Kubernetes-native deployment via Custom Resources
- Declarative configuration with YAML
- Automatic container image building with connectors
- Fault-tolerant distributed architecture
- Managed by Strimzi Cluster Operator

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Kafka Cluster                         │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐    │
│  │   Broker 1  │  │   Broker 2  │  │   Broker 3  │    │
│  └─────────────┘  └─────────────┘  └─────────────┘    │
└────────────┬────────────────────────────────────────────┘
             │
             │ bootstrapServers
             │
┌────────────▼────────────────────────────────────────────┐
│              Kafka Connect Cluster                      │
│  ┌───────────────────────────────────────────────────┐ │
│  │  Worker Pod 1    │  Worker Pod 2   │  Worker Pod 3│ │
│  │  ┌────────────┐  │  ┌────────────┐ │ ┌──────────┐│ │
│  │  │ Connector  │  │  │ Connector  │ │ │Connector ││ │
│  │  │   Task 1   │  │  │   Task 2   │ │ │  Task 3  ││ │
│  │  └────────────┘  │  └────────────┘ │ └──────────┘│ │
│  └───────────────────────────────────────────────────┘ │
└────────────┬────────────────────────────────────────────┘
             │
             │ Source/Sink Connectors
             │
     ┌───────┴────────┐
     │                │
┌────▼─────┐    ┌────▼─────┐
│ Database │    │  MinIO   │
│PostgreSQL│    │   S3     │
└──────────┘    └──────────┘
```

---

## Prerequisites

Before deploying Kafka Connect:

1. ✅ **Strimzi Cluster Operator** - Must be installed
2. ✅ **Kafka Cluster** - Running Kafka cluster (via `Kafka` custom resource)
3. ✅ **Kubernetes Cluster** - Access with `kubectl`
4. ✅ **Bootstrap Servers** - Kafka broker addresses
5. ⚠️ **Connector Plugins** - Either pre-built image or configuration to build

---

## Deployment Steps

### Step 1: Create KafkaConnect Custom Resource

Create a file `kafka-connect.yaml`:

```yaml
apiVersion: kafka.strimzi.io/v1beta2
kind: KafkaConnect
metadata:
  name: my-connect-cluster
  annotations:
    # Enable KafkaConnector resources (recommended)
    strimzi.io/use-connector-resources: "true"
spec:
  version: 3.6.0
  replicas: 3
  bootstrapServers: my-cluster-kafka-bootstrap:9092

  # Kafka Connect configuration
  config:
    group.id: connect-cluster
    offset.storage.topic: connect-cluster-offsets
    config.storage.topic: connect-cluster-configs
    status.storage.topic: connect-cluster-status
    # Replication factors (use 3 for production, 1 for single-node)
    offset.storage.replication.factor: 3
    config.storage.replication.factor: 3
    status.storage.replication.factor: 3
    # Converters
    key.converter: org.apache.kafka.connect.json.JsonConverter
    value.converter: org.apache.kafka.connect.json.JsonConverter
    key.converter.schemas.enable: false
    value.converter.schemas.enable: false
```

**For single-node Kafka clusters (< 3 brokers):**

```yaml
config:
  offset.storage.replication.factor: 1
  config.storage.replication.factor: 1
  status.storage.replication.factor: 1
```

### Step 2: Deploy the KafkaConnect Resource

```bash
kubectl apply -f kafka-connect.yaml
```

Verify deployment:

```bash
kubectl get kafkaconnect
kubectl get pods -l strimzi.io/cluster=my-connect-cluster
```

---

## Configuration Options

### Authentication

**TLS Certificate Authentication:**

```yaml
spec:
  authentication:
    type: tls
    certificateAndKey:
      secretName: my-user
      certificate: user.crt
      key: user.key
```

**SCRAM-SHA-512:**

```yaml
spec:
  authentication:
    type: scram-sha-512
    username: my-connect-user
    passwordSecret:
      secretName: my-connect-user
      password: password
```

**OAuth:**

```yaml
spec:
  authentication:
    type: oauth
    tokenEndpointUri: https://auth-server.com/token
    clientId: kafka-connect
    clientSecret:
      secretName: oauth-client-secret
      key: secret
```

### TLS Encryption

```yaml
spec:
  tls:
    trustedCertificates:
      - secretName: my-cluster-cluster-ca-cert
        certificate: ca.crt
```

### Resource Limits

```yaml
spec:
  resources:
    requests:
      memory: "2Gi"
      cpu: "1000m"
    limits:
      memory: "4Gi"
      cpu: "2000m"
```

### Logging

**Inline logging:**

```yaml
spec:
  logging:
    type: inline
    loggers:
      connect.root.logger.level: "INFO"
      log4j.logger.org.apache.kafka.connect: "DEBUG"
```

**External logging (ConfigMap):**

```yaml
spec:
  logging:
    type: external
    valueFrom:
      configMapKeyRef:
        name: custom-connect-logging
        key: log4j.properties
```

### JVM Options

```yaml
spec:
  jvmOptions:
    "-Xmx": "2g"
    "-Xms": "2g"
    "-XX":
      UseG1GC: true
      MaxGCPauseMillis: 20
```

---

## Adding Connector Plugins

Kafka Connect requires connector plugins to integrate with external systems. Strimzi provides three methods:

### Method 1: Automatic Image Building (Recommended)

Strimzi can automatically build a custom container image with your connectors:

```yaml
apiVersion: kafka.strimzi.io/v1beta2
kind: KafkaConnect
metadata:
  name: my-connect-cluster
  annotations:
    strimzi.io/use-connector-resources: "true"
spec:
  version: 3.6.0
  replicas: 3
  bootstrapServers: my-cluster-kafka-bootstrap:9092

  # Automatic image building
  build:
    output:
      type: docker
      image: my-registry.io/my-connect-cluster:latest
      pushSecret: my-registry-credentials
    plugins:
      - name: debezium-postgres-connector
        artifacts:
          - type: tgz
            url: https://repo1.maven.org/maven2/io/debezium/debezium-connector-postgres/2.1.0.Final/debezium-connector-postgres-2.1.0.Final-plugin.tar.gz

      - name: camel-http-connector
        artifacts:
          - type: tgz
            url: https://repo.maven.apache.org/maven2/org/apache/camel/kafkaconnector/camel-http-kafka-connector/0.11.5/camel-http-kafka-connector-0.11.5-package.tar.gz

      - name: confluentinc-kafka-connect-s3
        artifacts:
          - type: zip
            url: https://d1i4a15mxbxib1.cloudfront.net/api/plugins/confluentinc/kafka-connect-s3/versions/10.5.0/confluentinc-kafka-connect-s3-10.5.0.zip

  config:
    # ... rest of config
```

### Method 2: Pre-built Custom Image

If you've already built a custom image:

```yaml
spec:
  image: my-registry.io/kafka-connect-with-plugins:v1.0
  # ... rest of config
```

### Method 3: Kubernetes Volumes

Mount connector plugins from ConfigMaps or Secrets:

```yaml
spec:
  externalConfiguration:
    volumes:
      - name: connector-plugins
        configMap:
          name: my-connector-plugins
  # ... rest of config
```

---

## Creating Connectors

Once Kafka Connect is deployed with plugins, create connectors using `KafkaConnector` resources.

### Source Connector Example

Reads data from external system → Kafka topic

**File: `file-source-connector.yaml`**

```yaml
apiVersion: kafka.strimzi.io/v1beta2
kind: KafkaConnector
metadata:
  name: file-source-connector
  labels:
    strimzi.io/cluster: my-connect-cluster  # Must match KafkaConnect name
spec:
  class: org.apache.kafka.connect.file.FileStreamSourceConnector
  tasksMax: 2
  autoRestart:
    enabled: true
  config:
    file: "/opt/kafka/LICENSE"
    topic: my-source-topic
```

### Sink Connector Example

Reads data from Kafka topic → external system

**File: `s3-sink-connector.yaml`**

```yaml
apiVersion: kafka.strimzi.io/v1beta2
kind: KafkaConnector
metadata:
  name: s3-sink-connector
  labels:
    strimzi.io/cluster: my-connect-cluster
spec:
  class: io.confluent.connect.s3.S3SinkConnector
  tasksMax: 3
  autoRestart:
    enabled: true
    maxRestarts: 5
  config:
    topics: my-kafka-topic
    s3.bucket.name: my-bucket
    s3.region: us-east-1
    flush.size: 1000
    storage.class: io.confluent.connect.s3.storage.S3Storage
    format.class: io.confluent.connect.s3.format.json.JsonFormat
    aws.access.key.id: "${file:/opt/kafka/external-config/aws-credentials.properties:aws_access_key_id}"
    aws.secret.access.key: "${file:/opt/kafka/external-config/aws-credentials.properties:aws_secret_access_key}"
```

### Debezium CDC Connector Example

Captures database changes and streams to Kafka:

**File: `postgres-cdc-connector.yaml`**

```yaml
apiVersion: kafka.strimzi.io/v1beta2
kind: KafkaConnector
metadata:
  name: postgres-cdc-connector
  labels:
    strimzi.io/cluster: my-connect-cluster
spec:
  class: io.debezium.connector.postgresql.PostgresConnector
  tasksMax: 1
  autoRestart:
    enabled: true
  config:
    database.hostname: postgres.database.svc.cluster.local
    database.port: 5432
    database.user: debezium
    database.password: ${file:/opt/kafka/external-config/db-credentials.properties:password}
    database.dbname: mydb
    database.server.name: postgres-server
    table.include.list: public.customers,public.orders
    plugin.name: pgoutput
    topic.prefix: cdc
```

### Deploy Connectors

```bash
kubectl apply -f file-source-connector.yaml
kubectl apply -f s3-sink-connector.yaml
kubectl apply -f postgres-cdc-connector.yaml
```

---

## Monitoring and Management

### Check KafkaConnect Status

```bash
# Get KafkaConnect cluster status
kubectl get kafkaconnect my-connect-cluster -o yaml

# Check pods
kubectl get pods -l strimzi.io/cluster=my-connect-cluster

# View logs
kubectl logs -l strimzi.io/cluster=my-connect-cluster -f
```

### Check KafkaConnector Status

```bash
# List all connectors
kubectl get kafkaconnector

# Get specific connector details
kubectl get kafkaconnector file-source-connector -o yaml

# Check connector state
kubectl get kafkaconnector file-source-connector -o jsonpath='{.status.connectorStatus.connector.state}'
```

### Connector States

- **RUNNING** - Connector is working normally
- **FAILED** - Connector encountered an error
- **PAUSED** - Connector is paused
- **UNASSIGNED** - Connector not yet assigned to worker

### Pause/Resume Connector

```bash
# Pause
kubectl annotate kafkaconnector file-source-connector strimzi.io/pause=true

# Resume
kubectl annotate kafkaconnector file-source-connector strimzi.io/pause-
```

### Delete Connector

```bash
kubectl delete kafkaconnector file-source-connector
```

### Expose Kafka Connect REST API

By default, the REST API is internal. To expose it:

```yaml
spec:
  externalConfiguration:
    volumes:
      - name: connector-config
        secret:
          secretName: my-connector-config
  # Enable metrics
  metricsConfig:
    type: jmxPrometheusExporter
    valueFrom:
      configMapKeyRef:
        name: connect-metrics
        key: metrics-config.yml
```

---

## Examples

### Complete Pipeline: PostgreSQL → Kafka → MinIO

**1. Deploy Kafka Connect with Plugins:**

```yaml
apiVersion: kafka.strimzi.io/v1beta2
kind: KafkaConnect
metadata:
  name: cdc-connect
  annotations:
    strimzi.io/use-connector-resources: "true"
spec:
  version: 3.6.0
  replicas: 3
  bootstrapServers: my-cluster-kafka-bootstrap:9092
  build:
    output:
      type: docker
      image: my-registry.io/cdc-connect:latest
    plugins:
      - name: debezium-postgres
        artifacts:
          - type: tgz
            url: https://repo1.maven.org/maven2/io/debezium/debezium-connector-postgres/2.1.0.Final/debezium-connector-postgres-2.1.0.Final-plugin.tar.gz
      - name: minio-s3-sink
        artifacts:
          - type: zip
            url: https://d1i4a15mxbxib1.cloudfront.net/api/plugins/confluentinc/kafka-connect-s3/versions/10.5.0/confluentinc-kafka-connect-s3-10.5.0.zip
  config:
    group.id: cdc-connect-cluster
    offset.storage.topic: cdc-connect-offsets
    config.storage.topic: cdc-connect-configs
    status.storage.topic: cdc-connect-status
    key.converter: org.apache.kafka.connect.json.JsonConverter
    value.converter: org.apache.kafka.connect.json.JsonConverter
```

**2. Create Source Connector (PostgreSQL → Kafka):**

```yaml
apiVersion: kafka.strimzi.io/v1beta2
kind: KafkaConnector
metadata:
  name: postgres-source
  labels:
    strimzi.io/cluster: cdc-connect
spec:
  class: io.debezium.connector.postgresql.PostgresConnector
  tasksMax: 1
  config:
    database.hostname: postgres.default.svc.cluster.local
    database.port: 5432
    database.user: postgres
    database.password: ${file:/opt/kafka/external-config/db.properties:password}
    database.dbname: mydb
    database.server.name: postgres
    table.include.list: public.orders,public.customers
    plugin.name: pgoutput
```

**3. Create Sink Connector (Kafka → MinIO):**

```yaml
apiVersion: kafka.strimzi.io/v1beta2
kind: KafkaConnector
metadata:
  name: minio-sink
  labels:
    strimzi.io/cluster: cdc-connect
spec:
  class: io.confluent.connect.s3.S3SinkConnector
  tasksMax: 2
  config:
    topics: postgres.public.orders,postgres.public.customers
    s3.bucket.name: data-lake
    s3.region: us-east-1
    store.url: http://minio.default.svc.cluster.local:9000
    flush.size: 1000
    format.class: io.confluent.connect.s3.format.json.JsonFormat
```

---

## Troubleshooting

### Connector Not Starting

**Check connector status:**

```bash
kubectl describe kafkaconnector my-connector
```

**Common issues:**
- Missing connector plugin (check `build.plugins` in KafkaConnect)
- Incorrect `class` name in KafkaConnector spec
- Wrong `strimzi.io/cluster` label

### Connection Errors

**Symptoms:** Connector fails with connection timeout

**Solutions:**
- Verify `bootstrapServers` address
- Check authentication and TLS configuration
- Ensure network policies allow traffic

### Task Failures

**Check logs:**

```bash
kubectl logs -l strimzi.io/cluster=my-connect-cluster | grep ERROR
```

**Common causes:**
- Invalid connector configuration
- External system unavailable
- Permission issues

### Image Build Failures

**Symptoms:** KafkaConnect stuck in `NotReady`

**Check build status:**

```bash
kubectl get kafkaconnect my-connect-cluster -o jsonpath='{.status.conditions[?(@.type=="Ready")].message}'
```

**Solutions:**
- Verify plugin artifact URLs are accessible
- Check registry credentials in `pushSecret`
- Ensure sufficient resources for build

### Performance Issues

**Increase parallelism:**

```yaml
spec:
  tasksMax: 10  # Increase number of tasks
```

**Tune connector config:**

```yaml
config:
  batch.size: 1000
  max.poll.records: 500
```

---

## References

### Official Documentation

- **Strimzi Documentation**: https://strimzi.io/documentation/
- **Kafka Connect Overview**: https://strimzi.io/docs/operators/latest/overview.html
- **Configuring Strimzi**: https://strimzi.io/docs/operators/latest/configuring.html
- **Deploying Guide**: https://strimzi.io/docs/operators/latest/deploying

### Example Files

Strimzi provides example configurations:
- `examples/connect/kafka-connect.yaml` - Multi-node deployment
- `examples/connect/kafka-connect-single-node-kafka.yaml` - Single-node deployment
- `examples/connect/source-connector.yaml` - Sample source connector
- `examples/connect/sink-connector.yaml` - Sample sink connector

### Connector Plugins

- **Debezium (CDC)**: https://debezium.io/
- **Confluent Hub**: https://www.confluent.io/hub/
- **Apache Camel**: https://camel.apache.org/camel-kafka-connector/

---

## Best Practices

1. ✅ Always use `strimzi.io/use-connector-resources: "true"` annotation
2. ✅ Set appropriate replication factors (3 for production)
3. ✅ Use `autoRestart.enabled: true` for connectors
4. ✅ Configure resource requests and limits
5. ✅ Use external secrets for sensitive data
6. ✅ Enable JMX metrics for monitoring
7. ✅ Test connectors in dev environment first
8. ✅ Use multiple tasks (`tasksMax`) for parallelism
9. ✅ Monitor connector and task states regularly
10. ✅ Keep Strimzi and Kafka versions aligned

---

## Quick Reference Commands

```bash
# Deploy Kafka Connect
kubectl apply -f kafka-connect.yaml

# Deploy Connector
kubectl apply -f my-connector.yaml

# List all connectors
kubectl get kafkaconnector

# Check connector status
kubectl get kafkaconnector my-connector -o yaml

# View logs
kubectl logs -l strimzi.io/cluster=my-connect-cluster -f

# Pause connector
kubectl annotate kafkaconnector my-connector strimzi.io/pause=true

# Resume connector
kubectl annotate kafkaconnector my-connector strimzi.io/pause-

# Delete connector
kubectl delete kafkaconnector my-connector

# Scale Kafka Connect
kubectl patch kafkaconnect my-connect-cluster -p '{"spec":{"replicas":5}}' --type=merge
```

---

**Document Version**: 1.0
**Last Updated**: 2025-11-06
**Based on**: Strimzi 0.48.0 Official Documentation
