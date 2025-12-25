# Kafka Connect → MinIO Archive Setup Commands

This document lists all commands executed to set up Kafka Connect with S3 sink connector for archiving raw Kafka data to MinIO.

**Versions:**
- Aiven S3 Sink Connector: v3.4.1 (latest, Aug 2024)
- Kafka: 3.9.0
- Strimzi: 0.47.0

---

## 1. Create MinIO Bucket

```bash
mc mb s3/archive
```
Creates the `archive` bucket in MinIO for storing archived JSON files.

---

## 2. Enable Minikube Registry

```bash
minikube addons enable registry
```
Enables Minikube's built-in Docker registry, creating registry pod and registry-proxy DaemonSet for localhost:5000 access.

```bash
kubectl get pods -n kube-system | grep registry
```
Verifies registry and registry-proxy pods are running.

---

## 3. Build Custom Kafka Connect Image

```bash
eval $(minikube docker-env)
```
Points local Docker client to Minikube's Docker daemon so images build inside Minikube VM.

```bash
cd /home/kumararpita/alpaca_stream_ingestion/load/kafka-connect
docker build -t localhost:5000/kafka-connect-s3:latest .
```
Builds Kafka Connect image with Aiven S3 connector v3.4.1 from GitHub (CloudFront blocked).

```bash
docker push localhost:5000/kafka-connect-s3:latest
```
Pushes image to Minikube's local registry at localhost:5000 for Kubernetes pods to pull.

---

## 4. Deploy Kafka Connect Cluster

```bash
kubectl apply -f /home/kumararpita/alpaca_stream_ingestion/load/kafka-connect/kafkaconnect.yaml
```
Creates Kafka Connect cluster using pre-built image (skips Strimzi build due to DNS issues).

```bash
kubectl get kafkaconnect -n kafka
```
Checks KafkaConnect status - should show DESIRED REPLICAS: 1.

```bash
kubectl wait --for=condition=Ready pod/kafka-connect-cluster-connect-0 -n kafka --timeout=120s
```
Waits up to 2 minutes for Kafka Connect pod to be fully ready.

---

## 5. Deploy S3 Sink Connector

```bash
kubectl apply -f /home/kumararpita/alpaca_stream_ingestion/load/kafka-connect/s3-sink-connector.yaml
```
Creates S3 sink connector consuming from iex-topic-1, writing GZIP JSON to MinIO archive bucket.

```bash
kubectl get kafkaconnector -n kafka
```
Lists connectors - s3-sink-raw should show READY: True after ~10 seconds.

---

## 6. Verify Archival

```bash
kubectl logs -n kafka kafka-connect-cluster-connect-0 --tail=50 | grep "Processing"
```
Checks connector logs for "Processing X records" messages confirming data consumption.

```bash
mc ls s3/archive/ --recursive
```
Lists archived files - should show .jsonl.gz files for each partition (0, 1, 2).

```bash
mc cat s3/archive/iex-topic-1-0-0.jsonl.gz | gunzip | head -3
```
Downloads and decompresses first file to verify data format.

---

## Troubleshooting

### Rebuild After Registry Restart

If registry restarts, the image is lost (no persistent storage). Rebuild:

```bash
eval $(minikube docker-env)
cd /home/kumararpita/alpaca_stream_ingestion/load/kafka-connect
docker build -t localhost:5000/kafka-connect-s3:latest .
docker push localhost:5000/kafka-connect-s3:latest
kubectl delete pod kafka-connect-cluster-connect-0 -n kafka
```
Rebuilds, pushes image, and restarts pod to pull fresh image.

### Check Pod Status

```bash
kubectl get pods -n kafka | grep connect
```
Should show Running status, not ImagePullBackOff or CrashLoopBackOff.

```bash
kubectl describe pod kafka-connect-cluster-connect-0 -n kafka | grep -A 5 "Events:"
```
Shows image pull errors or other startup issues.

### Check Connector Logs

```bash
kubectl logs -n kafka kafka-connect-cluster-connect-0 --tail=100 | grep -E "ERROR|Exception"
```
Searches for errors in connector operation.

### Check Connector Status

```bash
kubectl get kafkaconnector s3-sink-raw -n kafka -o jsonpath='{.status.conditions[?(@.type=="Ready")].message}'
```
Shows detailed error message if connector is not ready.

### Verify MinIO Access

```bash
kubectl get svc -n minio-tenant
```
Confirms MinIO service name is `minio-single-hl` (not `minio-tenant-hl`).

---

## Key Configuration Issues Fixed

1. **Bucket naming**: `raw_data_archive` → `archive` (S3 spec doesn't allow underscores)
2. **Credentials**: `aws.secret.access.key.id` → `aws.secret.access.key` (typo fix)
3. **Service name**: `minio-tenant-hl` → `minio-single-hl` (correct service)
4. **Format**: `parquet` → `jsonl` (Parquet requires schemas, JSON doesn't)
5. **Kafka version**: `3.8.0` → `3.9.0` (match cluster version)

---

## Architecture

```
[WebSocket Extractor]
        ↓
[Kafka: iex-topic-1] (raw arrays)
        ↓
[Kafka Connect: 2 tasks]
        ↓
[MinIO: s3://archive/]
        ↓
[Files: *.jsonl.gz]
```

---

## File Naming & Flush Behavior

**File template**: `{{topic}}-{{partition}}-{{start_offset}}.jsonl.gz`

**Examples**:
- `iex-topic-1-0-0.jsonl.gz` - Partition 0, offset 0
- `iex-topic-1-1-0.jsonl.gz` - Partition 1, offset 0
- `iex-topic-1-2-0.jsonl.gz` - Partition 2, offset 0

**New file created when**:
- `file.max.records: 1000` - After 1000 records accumulated, OR
- `kafka.retry.backoff.ms: 60000` - After 60 seconds elapsed

Whichever condition is met first triggers file write and S3 upload.

---

## Why Manual Build Instead of Strimzi Build?

**Standard Strimzi flow** (failed):
```
KafkaConnect CR with build: section
  ↓
Strimzi creates Kaniko build pod
  ↓
Downloads connector from CloudFront URL
  ↓
DNS FAILURE: Can't resolve d1i4a15mxbxib1.cloudfront.net
```

**Our workaround**:
```
Manual build with Minikube's Docker
  ↓
Download connector from GitHub (accessible)
  ↓
Push to Minikube registry
  ↓
KafkaConnect CR references pre-built image (no build: section)
```

This bypasses Strimzi's build feature due to network restrictions blocking CloudFront CDN.
