# MinIO Infrastructure Helm Chart

This Helm chart deploys a complete MinIO infrastructure using the MinIO Operator on Kubernetes/Minikube.

## Overview

**Components:**
- MinIO Operator (v7.1.1) - Manages MinIO tenants
- MinIO Tenant - Single-node S3-compatible object storage
- StorageClass - Local storage configuration
- PersistentVolume - Local volume for Minikube

**Features:**
- Single-node deployment (suitable for development/testing)
- Local persistent storage (100Gi)
- S3-compatible API
- Web console for management
- Compatible with Spark, Iceberg, and other S3 clients

## Prerequisites

- Kubernetes cluster (Minikube recommended for local development)
- Helm 3.x
- kubectl configured
- 100Gi+ available storage
- Local directory `/mnt/minio` created on Minikube node

## Configuration

### Central Configuration

This chart uses `config/config.yaml` as the central configuration file. The chart's `values.yaml` provides defaults for MinIO-specific settings.

**Relevant sections in config/config.yaml:**

```yaml
# Add MinIO section to config.yaml
minio:
  rootUser: "minio"
  rootPassword: "minio123"
  endpoint: "http://minio-api.192.168.49.2.nip.io"
  accessKey: "minio"
  secretKey: "minio123"
  storage:
    size: 100Gi
```

### Chart Values Structure

Key configuration options in `values.yaml`:

| Parameter | Description | Default |
|-----------|-------------|---------|
| `operator.enabled` | Deploy MinIO operator | `true` |
| `tenant.enabled` | Deploy MinIO tenant | `true` |
| `tenant.name` | MinIO tenant name | `minio-single` |
| `tenant.namespace` | Deployment namespace | `minio-tenant` |
| `minio.rootUser` | Root username | `minio` |
| `minio.rootPassword` | Root password | `minio123` |
| `minio.storage.size` | Storage size per volume | `100Gi` |
| `minio.storage.local.path` | Local volume path | `/mnt/minio` |
| `minio.storage.local.nodeName` | Node name for affinity | `minikube` |

### Customization

**Override specific values:**

```bash
helm install minio-infra . \
  --set minio.storage.local.nodeName=kafka-helm-test \
  --set minio.storage.size=200Gi
```

## Installation

### Preparation (Minikube)

```bash
# Create local directory for MinIO storage
minikube ssh
sudo mkdir -p /mnt/minio
sudo chmod 777 /mnt/minio
exit
```

### Quick Start

```bash
# Update dependencies
cd helm/infrastructure/minio
helm dependency update

# Install
helm install minio-infra . \
  --namespace minio-tenant \
  --create-namespace \
  --wait \
  --timeout 10m
```

### Verify Installation

```bash
# Check MinIO operator
kubectl get pods -n minio-operator

# Wait for MinIO tenant to be ready
kubectl wait tenant/minio-single --for=condition=Ready -n minio-tenant --timeout=300s

# Check tenant
kubectl get tenant -n minio-tenant
kubectl get pods -n minio-tenant
```

### Get Connection Details

```bash
# API endpoint (S3-compatible)
kubectl get svc -n minio-tenant minio

# Console endpoint
kubectl get svc -n minio-tenant minio-single-console
```

## Validation

Validate the chart before installation:

```bash
# Using the validation script
./scripts/validate.sh

# Or manually
helm lint .
helm template minio-test . --debug
```

## Usage

### Access MinIO Console

```bash
# Port forward to access console
kubectl port-forward -n minio-tenant svc/minio-single-console 9090:9090

# Open browser: http://localhost:9090
# Login: minio / minio123
```

### Using MinIO Client (mc)

```bash
# Install mc (MinIO Client)
# https://min.io/docs/minio/linux/reference/minio-mc.html

# Configure alias
mc alias set myminio http://minio.minio-tenant.svc.cluster.local minio minio123

# List buckets
mc ls myminio

# Create bucket
mc mb myminio/test-bucket

# Upload file
mc cp myfile.txt myminio/test-bucket/

# List objects
mc ls myminio/test-bucket
```

### Using with Spark/Iceberg

```python
# Spark configuration
spark.hadoop.fs.s3a.endpoint = "http://minio.minio-tenant.svc.cluster.local"
spark.hadoop.fs.s3a.access.key = "minio"
spark.hadoop.fs.s3a.secret.key = "minio123"
spark.hadoop.fs.s3a.path.style.access = "true"
spark.hadoop.fs.s3a.impl = "org.apache.hadoop.fs.s3a.S3AFileSystem"

# Write data
df.write.format("iceberg").save("s3a://mybucket/mytable")
```

### Using with Python (boto3)

```python
import boto3

s3 = boto3.client(
    's3',
    endpoint_url='http://minio.minio-tenant.svc.cluster.local',
    aws_access_key_id='minio',
    aws_secret_access_key='minio123',
)

# List buckets
response = s3.list_buckets()
print(response['Buckets'])

# Upload file
s3.upload_file('myfile.txt', 'test-bucket', 'myfile.txt')
```

## Upgrading

```bash
# Pull latest chart dependencies
helm dependency update

# Upgrade
helm upgrade minio-infra . \
  --namespace minio-tenant \
  --wait
```

## Uninstallation

```bash
# Uninstall release
helm uninstall minio-infra -n minio-tenant

# Delete PVCs (optional - will delete all data!)
kubectl delete pvc -n minio-tenant --all

# Delete namespace (optional)
kubectl delete namespace minio-tenant

# Delete PV
kubectl delete pv minio-pv1

# Delete storage class
kubectl delete storageclass local-storage
```

**Note:** MinIO operator and CRDs are not automatically removed. To remove them:

```bash
kubectl delete namespace minio-operator
kubectl delete crd tenants.minio.min.io
kubectl delete crd policybindings.sts.min.io
```

## Troubleshooting

### Operator Not Starting

```bash
# Check operator logs
kubectl logs -n minio-operator -l app.kubernetes.io/name=operator

# Check operator deployment
kubectl get deployment -n minio-operator
```

### Tenant Not Ready

```bash
# Check tenant resource status
kubectl describe tenant minio-single -n minio-tenant

# Check pod events
kubectl get events -n minio-tenant --sort-by='.lastTimestamp'

# Check MinIO logs
kubectl logs -n minio-tenant -l app=minio-single
```

### Storage Issues

```bash
# Check PVCs
kubectl get pvc -n minio-tenant

# Check PV
kubectl get pv minio-pv1

# Check if local directory exists on node
minikube ssh "ls -la /mnt/minio"
```

### Connection Issues

```bash
# Check services
kubectl get svc -n minio-tenant

# Test from within cluster
kubectl run test-minio --image=minio/mc --rm -it --restart=Never -- \
  alias set test http://minio.minio-tenant.svc.cluster.local minio minio123

kubectl run test-minio --image=minio/mc --rm -it --restart=Never -- \
  ls test
```

## Architecture

```
┌─────────────────────────────────────────────┐
│         MinIO Operator                       │
│  (Manages MinIO tenants via CRDs)           │
└──────────────────┬──────────────────────────┘
                   │
                   │ manages
                   ▼
┌─────────────────────────────────────────────┐
│           MinIO Tenant                       │
│  ┌────────────────────────────────────┐    │
│  │  Pool: pool-0                      │    │
│  │  - 1 server                        │    │
│  │  - 1 volume per server             │    │
│  │  - 100Gi PVC                       │    │
│  └────────────────────────────────────┘    │
│                                             │
│  Services:                                  │
│  - minio (S3 API)                          │
│  - minio-single-console (Web UI)           │
│                                             │
│  Storage:                                   │
│  - Local PV: /mnt/minio                    │
│  - StorageClass: local-storage              │
└─────────────────────────────────────────────┘
```

## Dependencies

This chart depends on:
- **operator** (v7.1.1) from https://operator.min.io

Dependencies are automatically downloaded via `helm dependency update`.

## Integration with Other Charts

This chart is designed to be used with:
- **kafka** chart - Message streaming
- **alpaca-etl** chart - Stream processing applications

All charts can be deployed together via an umbrella chart.

## References

- [MinIO Documentation](https://min.io/docs/)
- [MinIO Operator Documentation](https://min.io/docs/minio/kubernetes/upstream/)
- [Kubernetes Documentation](https://kubernetes.io/docs/)
- [Helm Documentation](https://helm.sh/docs/)

## License

This chart is part of the Alpaca Stream Ingestion project.
