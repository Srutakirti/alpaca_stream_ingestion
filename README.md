# Alpaca Stream Ingestion

> **Real-time streaming data pipeline for local development, education, and exploration**

A production-ready streaming platform that ingests live stock market data via WebSocket, processes it with Kafka Streams, and loads it into Apache Pinot for real-time analytics - all running locally on Minikube with a config-driven, Helm-based architecture that's transferable to enterprise cloud deployments.

---

## Purpose

- **Local Development**: Full streaming pipeline on your laptop using Minikube
- **Education**: Hands-on experience with modern data engineering (Kafka, Kafka Streams, Pinot, Helm)
- **Exploration**: Experiment with streaming patterns, transformations, and real-time analytics
- **Enterprise-Ready**: Helm-based infrastructure and config-driven design for easy cloud migration

---

## Architecture

```
┌─────────────────────┐
│  EXTRACT            │
│  extract/           │  Alpaca WebSocket API / Synthetic Generator
│  - Alpaca WS        │  → Kafka (iex-topic-1)
│  - Synthetic Gen    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Kafka (Strimzi)    │  Message Broker
│  iex-topic-1        │  (Deployed via Helm)
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  TRANSFORM          │
│  transform/Kstreams │  Stream Processing (Java)
│  - Flatten arrays   │  iex-topic-1 → iex-topic-1-flattened
│  - Field transform  │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  LOAD               │
│  load/              │  Apache Pinot (Real-time Analytics)
│  - Pinot tables     │  Query stock data in real-time
│  - Schema/Config    │
└─────────────────────┘

           ┌─────────────────────┐
           │  INFRASTRUCTURE     │
           │  helm/              │  Kafka Connect → MinIO
           │  - Kafka            │  Archive data to S3-compatible storage
           │  - Kafka Connect    │
           │  - MinIO            │
           │  - Pinot            │
           └─────────────────────┘
```

**Pipeline:** Extract (WebSocket) → Transform (KStreams) → Load (Pinot) + Archive (MinIO)

---

## Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Infrastructure** | Minikube + Helm | Local Kubernetes with declarative deployments |
| **Messaging** | Apache Kafka (Strimzi) | Distributed event streaming |
| **Stream Processing** | Kafka Streams (Java 17) | Real-time transformation and flattening |
| **Analytics** | Apache Pinot | Low-latency OLAP and real-time queries |
| **Archival** | Kafka Connect + MinIO | S3-compatible object storage sink |
| **Data Source** | Alpaca WebSocket / Synthetic | Live market data or generated events |
| **Configuration** | YAML (config/config.yaml) | Single source of truth for all components |
| **Languages** | Java 17, Python 3.10+ | Stream processing and tooling |

---

## Project Structure

```
alpaca_stream_ingestion/
│
├── extract/                          # EXTRACT: Data Ingestion
│   ├── app/
│   │   └── alpaca_ws_updated_conf.py      # Alpaca WebSocket → Kafka
│   ├── helpers/
│   │   └── synthetic_stock_generator.py   # Synthetic event generator
│   └── history/
│       └── history_data_collect_streaming.py  # Historical data fetcher
│
├── transform/                        # TRANSFORM: Stream Processing
│   └── Kstreams/
│       ├── src/main/java/com/example/kstreams/
│       │   ├── StreamProcessor.java       # Main KStreams application
│       │   └── StockData.java             # Stock data POJO with transformations
│       ├── Dockerfile                     # Multi-stage build
│       └── build.gradle                   # Gradle config
│
├── load/                             # LOAD: Analytics Layer
│   ├── pinot_qeury_display.py             # Query Pinot tables
│   ├── schema.json                        # Pinot schema definition
│   ├── table.json                         # Pinot table config
│   ├── create.py                          # Create schemas/tables
│   └── kafka-connect/                     # Kafka Connect image build
│
├── helm/infrastructure/              # INFRASTRUCTURE: Helm Charts
│   ├── kafka/                             # Kafka (Strimzi operator)
│   ├── kafka-connect/                     # Kafka Connect S3 sink
│   ├── minio/                             # MinIO object storage
│   └── pinot/                             # Apache Pinot
│
├── config/
│   └── config.yaml                   # Central configuration (single source of truth)
│
├── scripts/                          # Installation & Setup
│   ├── 1_install_dependencies_new.sh      # Install system dependencies
│   ├── 2_setup_kubernetes_new.sh          # Setup Minikube cluster
│   ├── 3_setup_apps_new.sh                # Deploy all applications
│   └── build_kafka_connect_image.sh       # Build Kafka Connect image
│
└── pyproject.toml                    # Python dependencies (managed by uv)
```

---

## Quick Start

### Prerequisites
- **Hardware**: 8 CPU cores, 15GB RAM minimum
- **OS**: Ubuntu Linux (22.04+)
- **Optional**: Alpaca API credentials for live data ([free tier](https://alpaca.markets))

### 1. Install Dependencies & Setup Infrastructure

```bash
# Clone repository
git clone <repository-url>
cd alpaca_stream_ingestion

# Make scripts executable
chmod +x scripts/*.sh

# Step 1: Install system dependencies (Docker, Minikube, kubectl, Helm, Java, uv)
./scripts/1_install_dependencies_new.sh

# Step 2: Setup Minikube cluster
./scripts/2_setup_kubernetes_new.sh

# Step 3: Deploy infrastructure (Kafka, MinIO, Pinot, Kafka Connect)
./scripts/3_setup_apps_new.sh
```

This deploys all infrastructure components via Helm using configuration from `config/config.yaml`.

### 2. Generate Data

**Option A: Synthetic data (no API credentials needed)**
```bash
uv run python extract/helpers/synthetic_stock_generator.py \
  --symbols AAPL TSLA GOOGL \
  --rate 5
```

**Option B: Live Alpaca data**
```bash
export ALPACA_KEY="your-key"
export ALPACA_SECRET="your-secret"
uv run python extract/app/alpaca_ws_updated_conf.py
```

### 3. Query Real-Time Data

```bash
# Monitor Pinot table (auto-detects controller)
uv run python load/pinot_qeury_display.py --interval 60
```

**Access Pinot Web UI:**
```bash
open http://$(minikube ip):30900
```

**That's it!** Your real-time pipeline is running.

---

## Access Services

All services are accessible via Minikube NodePort (no port-forwarding needed):

```bash
# Get Minikube IP
export MINIKUBE_IP=$(minikube ip)
```

- **Pinot Controller**: `http://$MINIKUBE_IP:30900` (Web UI, query editor, schema management)
- **Pinot Broker**: `http://$MINIKUBE_IP:30099` (SQL query endpoint)
- **MinIO Console**: `http://$MINIKUBE_IP:30001` (object storage, credentials: minio/minio123)
- **Kafka (External)**: `$MINIKUBE_IP:32100` (bootstrap server for external clients)

---

## How It Works

### 1. Extract (Data Ingestion)
- **Alpaca WebSocket**: Live stock market data (IEX feed) → Kafka topic `iex-topic-1`
- **Synthetic Generator**: Realistic simulated stock bars → Kafka topic `iex-topic-1`
- Data arrives as JSON arrays of stock bars

### 2. Transform (Stream Processing)
Kafka Streams application (`transform/Kstreams/`):
- Consumes from `iex-topic-1`
- Flattens JSON arrays into individual events
- Transforms field names: `t` → `time_stamp`, `S` → symbol, etc.
- Produces to `iex-topic-1-flattened`

**Example:** `[{...}, {...}, {...}]` → `{...}`, `{...}`, `{...}` (3 separate messages)

### 3. Load (Real-Time Analytics)
- **Pinot**: Ingests from `iex-topic-1-flattened` for sub-second SQL queries
- **Kafka Connect**: Archives raw data to MinIO (S3-compatible) in JSONL+gzip format

---

## Common Operations

### Query Pinot (Real-Time Analytics)

```bash
# Auto-refresh query display (auto-detects Pinot controller)
uv run python load/pinot_qeury_display.py --interval 60
```

**Or use Pinot Web UI** at `http://$(minikube ip):30900`:
```sql
-- Count events by symbol
SELECT S, COUNT(*) as count
FROM stock_ticks_latest_2
GROUP BY S
ORDER BY count DESC;

-- Latest prices with timestamps
SELECT S, o, h, l, c, v, time_stamp
FROM stock_ticks_latest_2
ORDER BY time_stamp DESC
LIMIT 10;
```

### Monitor Infrastructure

```bash
# View all pods across namespaces
kubectl get pods -A

# Check Kafka cluster
kubectl get pods -n kafka
kubectl logs -n kafka my-cluster-kafka-0

# Check KStreams transformer
kubectl logs -n kafka -l app=kstreams-flatten

# Check Pinot
kubectl get pods -n pinot
kubectl logs -n pinot -l app=pinot-controller

# View services and NodePorts
kubectl get svc -A | grep NodePort
```

### Check Configuration

```bash
# View current config
cat config/config.yaml

# Validate Helm chart with config
helm template helm/infrastructure/kafka -f config/config.yaml

# Update infrastructure (after config changes)
helm upgrade kafka helm/infrastructure/kafka -f config/config.yaml -n kafka
```

### Kafka Operations

```bash
# List topics
kubectl exec -it my-cluster-kafka-0 -n kafka -- \
  bin/kafka-topics.sh --bootstrap-server localhost:9092 --list

# Check consumer groups
kubectl exec -it my-cluster-kafka-0 -n kafka -- \
  bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 --list

# View topic data
kubectl exec -it my-cluster-kafka-0 -n kafka -- \
  bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic iex-topic-1-flattened \
  --max-messages 10
```

---

## Configuration

All configuration is centralized in `config/config.yaml`:

```yaml
kafka:
  bootstrap_servers: "my-cluster-kafka-bootstrap.kafka.svc.cluster.local:9092"
  topics:
    raw_trade: "iex-topic-1"
    flattened_trade: "iex-topic-1-flattened"

kafka_connect:
  s3_sink:
    bucket: "archive"
    format: "jsonl"
    compression: "gzip"

minio:
  rootUser: "minio"
  rootPassword: "minio123"

minikube:
  cpu: 8
  memory: 14999  # MB
```

**Update infrastructure after config changes:**
```bash
helm upgrade <component> helm/infrastructure/<component> -f config/config.yaml -n <namespace>
```

---

## Troubleshooting

### Pods Not Starting
```bash
# Check pod status and events
kubectl get pods -A
kubectl describe pod <pod-name> -n <namespace>

# View logs
kubectl logs <pod-name> -n <namespace>
```

### Minikube Resource Issues
```bash
# Check resource usage
kubectl top nodes
kubectl top pods -A

# Increase resources (requires restart)
minikube delete
minikube start --cpus=10 --memory=16384
```

### Kafka Connect Issues
```bash
# Check connector status
kubectl get kafkaconnector -n kafka
kubectl describe kafkaconnector s3-sink-raw -n kafka

# View Kafka Connect logs
kubectl logs -n kafka -l strimzi.io/kind=KafkaConnect
```

### Pinot Table Not Ingesting
```bash
# Check Pinot server logs
kubectl logs -n pinot -l app=pinot-server

# Verify Kafka connectivity from Pinot
kubectl exec -it -n pinot <pinot-server-pod> -- \
  curl my-cluster-kafka-bootstrap.kafka.svc.cluster.local:9092
```

---

## Cleanup

### Stop Minikube (preserve data)
```bash
minikube stop
```

### Delete Everything
```bash
minikube delete
rm -rf .venv
```

### Uninstall Individual Components
```bash
# Uninstall via Helm
helm uninstall kafka -n kafka
helm uninstall pinot -n pinot
helm uninstall minio -n minio-tenant
helm uninstall kafka-connect -n kafka

# Delete namespaces
kubectl delete namespace kafka pinot minio-tenant
```

---

## Enterprise Migration

This local setup is designed for cloud migration:

1. **Helm Charts**: All infrastructure uses Helm → deploy to EKS/GKE/AKS
2. **Config-Driven**: Update `config/config.yaml` for cloud resources (managed Kafka, S3, etc.)
3. **Kubernetes Native**: Manifests work on any K8s cluster
4. **Operator-Based**: Strimzi operator for production Kafka management

**Cloud Replacements:**
- Minikube → EKS/GKE/AKS
- MinIO → AWS S3/GCS/Azure Blob
- Local Kafka → Confluent Cloud/AWS MSK/Azure Event Hubs
- KStreams pod → AWS ECS/Fargate or keep in K8s

---

## Resources

- [Apache Kafka](https://kafka.apache.org/documentation/)
- [Kafka Streams](https://kafka.apache.org/documentation/streams/)
- [Apache Pinot](https://docs.pinot.apache.org/)
- [Strimzi Operator](https://strimzi.io/docs/operators/latest/)
- [Alpaca Markets API](https://alpaca.markets/docs/)
- [Helm Charts](https://helm.sh/docs/)

---

**Built for learning, designed for production.**
