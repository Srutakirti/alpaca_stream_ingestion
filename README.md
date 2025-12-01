# Alpaca Stream Ingestion

> **A complete real-time data engineering pipeline for learning and rapid prototyping**

Local-first streaming data platform that ingests live stock market data, processes it with Kafka Streams, and stores it in modern data lakehouse (Iceberg) and analytics (Pinot) systems - all running on Minikube without any cloud dependencies.

---

## Purpose

This project is designed for:
- **Learning**: Hands-on experience with modern data engineering tools (Kafka, Kafka Streams, Iceberg, Pinot)
- **Rapid Prototyping**: Test streaming patterns and transformations locally before cloud deployment
- **No Cloud Lock-in**: Everything runs on your machine using Minikube
- **Real Data**: Connect to Alpaca's free tier for live stock market data, or use built-in sample generators

Perfect for data engineers learning streaming patterns, students exploring distributed systems, or professionals prototyping data pipelines.

---

## Architecture

```
┌──────────────────┐
│  Alpaca WebSocket│  (Live IEX Stock Data)
│  or Sample Gen   │
└────────┬─────────┘
         │
         ▼
┌────────────────────┐
│   Apache Kafka     │  (Message Broker - Strimzi Operator)
│  Topic: iex_data   │
└────────┬───────────┘
         │
         ▼
┌────────────────────┐
│  Kafka Streams     │  (Stream Processing - Java)
│  - Flatten JSON    │
│  - Transform       │
└────────┬───────────┘
         │
         ├─────────────────┐
         ▼                 ▼
┌─────────────────┐  ┌──────────────────┐
│ Apache Iceberg  │  │  Apache Pinot    │
│ (Data Lakehouse)│  │  (Real-time      │
│                 │  │   Analytics)     │
│ Storage: MinIO  │  │                  │
└─────────────────┘  └──────────────────┘
```

**Data Flow:** WebSocket → Kafka → Kafka Streams → (Iceberg + Pinot)

---

## Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Infrastructure** | Minikube + Docker | Local Kubernetes cluster |
| **Messaging** | Apache Kafka (Strimzi) | Distributed message broker |
| **Stream Processing** | Kafka Streams (Java 17) | Real-time data transformation and flattening |
| **Data Lakehouse** | Apache Iceberg | ACID-compliant table format with time-travel |
| **Analytics Database** | Apache Pinot | Low-latency OLAP queries |
| **Object Storage** | MinIO | S3-compatible storage for Iceberg |
| **Data Source** | Alpaca WebSocket API | Live stock market data (IEX feed) |
| **Languages** | Java 17, Python 3.10+ | Application development |

---

## Project Structure

```
alpaca_stream_ingestion/
├── kstreams-app/              # Kafka Streams application (Java)
│   ├── src/main/java/com/example/kstreams/
│   │   ├── StreamProcessor.java      # Main KStreams app with CLI
│   │   ├── StockData.java            # Stock data POJO
│   │   ├── JsonSerializer.java       # JSON serialization
│   │   ├── JsonDeserializer.java     # JSON deserialization
│   │   └── JsonSerde.java            # Combined serdes
│   ├── build.gradle                  # Gradle build config
│   ├── Dockerfile                    # Multi-stage Docker build
│   ├── build-docker.sh               # Docker image builder
│   ├── deploy-k8s.sh                 # K8s deployment script
│   └── k8s/deployment.yaml           # K8s manifest
│
├── extract/                   # Data ingestion layer
│   ├── app/
│   │   ├── alpaca_ws_updated_conf.py   # WebSocket → Kafka producer
│   │   └── conf_reader.py              # Configuration loader
│   ├── admin/
│   │   ├── create_kafka_topic.py       # Topic management utility
│   │   └── kafka_consumer_stdout.py    # Debug consumer
│   └── history/
│       └── simulate_stream_from_history.py  # Historical data replay
│
├── transform/                 # Stream processing utilities
│   └── iceberg_compaction.py  # Iceberg table compaction script
│
├── load/                      # Query and analytics layer
│   ├── pinot_qeury_display.py  # Pinot query utilities
│   ├── schema.json             # Pinot schema definitions
│   └── table.json              # Pinot table configurations
│
├── minikube/                  # Kubernetes manifests
│   ├── kafka/
│   │   ├── 00-kafka_ns.yaml                # Kafka namespace
│   │   ├── 01-stimzi_operator.yaml         # Strimzi operator
│   │   ├── 02-kafka_deploy.yaml            # Kafka cluster definition
│   │   └── sample_event_generators/
│   │       └── stream_producer_cli.py      # Sample data generator
│   ├── minio/                 # MinIO deployment manifests
│   ├── pinot/                 # Pinot deployment (Helm values)
│   └── extractor_deploy/      # WebSocket app K8s deployment
│
├── config/                    # Configuration files
├── iceberg/                   # Iceberg table definitions
├── test_new_2.sh             # Automated infrastructure setup script
├── pyproject.toml            # Python dependencies
└── README.md                 # This file
```

---

## Quick Start

### Prerequisites
- **Hardware**: 8 CPU cores, 15GB RAM minimum
- **OS**: Ubuntu Linux (22.04+) or similar
- **Optional**: Alpaca API credentials for live data ([free tier](https://alpaca.markets))

### 1. Automated Setup (5 minutes)

```bash
# Clone the repository
git clone <repository-url>
cd alpaca_stream_ingestion

# Run the automated setup script
chmod +x test_new_2.sh

# Full setup: installs dependencies, starts Minikube, deploys all services
./test_new_2.sh --setup-infra --setup-minikube --setup-kafka --setup-minio --setup-pinot

# Enable port forwarding
./test_new_2.sh --port-forward
```

This installs: Docker, Minikube, kubectl, Helm, Java, Spark, UV, and deploys Kafka, MinIO, and Pinot.

### 2. Start Sample Data Generator

```bash
# Generate sample stock data (no API credentials needed)
python minikube/kafka/sample_event_generators/stream_producer_cli.py \
  --kafka-brokers localhost:9092 \
  --topic iex_data \
  --symbols AAPL GOOGL MSFT \
  --batch-size 50 \
  --interval 2
```

### 3. Build and Deploy Kafka Streams Application

```bash
cd kstreams-app

# Build Docker image in Minikube
./build-docker.sh

# Deploy to Kubernetes
./deploy-k8s.sh

# Check status
kubectl get pods -n kafka -l app=kstreams-flatten

# View logs
kubectl logs -n kafka -l app=kstreams-flatten -f
```

**That's it!** Your pipeline is now running.

---

## Access Services

Once deployed, access these services:

- **Pinot Console**: http://localhost:9000 (query analytics)
- **MinIO Console**: http://localhost:9001 (view storage, credentials: minio/minio123)
- **Kafka**: localhost:9092 (message broker)

---

## How It Works

### 1. Data Ingestion
Stock market data flows from either:
- **Live**: Alpaca WebSocket API (requires free API credentials)
- **Sample**: Built-in generator (`stream_producer_cli.py`)

Data is produced to Kafka topic `iex_data` as JSON arrays.

### 2. Stream Processing (Kafka Streams)
The Java-based Kafka Streams application:
- Reads JSON arrays from the source topic
- Flattens each array element into individual messages
- Transforms and validates stock data
- Writes flattened records to output topic

**Example Transformation:**

Input (JSON array):
```json
[
  {"T": "T", "S": "NVDA", "o": 187.87, "h": 185.67, "l": 184.94, "c": 185.47, "v": 44481045, "t": "2025-11-13T00:35:21.076148Z", "n": 145488, "vw": 185.36},
  {"T": "T", "S": "AAPL", "o": 150.0, "h": 152.0, "l": 149.5, "c": 151.0, "v": 30000000, "t": "2025-11-13T00:35:21.076148Z", "n": 100000, "vw": 150.5}
]
```

Output (individual messages):
```json
{"T": "T", "S": "NVDA", "o": 187.87, "h": 185.67, "l": 184.94, "c": 185.47, "v": 44481045, "t": "2025-11-13T00:35:21.076148Z", "n": 145488, "vw": 185.36}
{"T": "T", "S": "AAPL", "o": 150.0, "h": 152.0, "l": 149.5, "c": 151.0, "v": 30000000, "t": "2025-11-13T00:35:21.076148Z", "n": 100000, "vw": 150.5}
```

### 3. Dual Storage
Processed data is stored in both:
- **Iceberg**: Data lakehouse for historical analysis, time-travel queries
- **Pinot**: Real-time analytics for low-latency OLAP queries

---

## Common Operations

### Query Real-time Analytics (Pinot)

Access Pinot console at http://localhost:9000

```sql
-- Count trades by symbol
SELECT S as symbol, COUNT(*) as trade_count
FROM flattened_stocks
GROUP BY S
ORDER BY trade_count DESC
LIMIT 10;

-- Average price by symbol
SELECT S as symbol, AVG(p) as avg_price
FROM flattened_stocks
GROUP BY S;
```

### Compact Iceberg Tables

The Iceberg compaction script optimizes storage by merging small files:

```bash
python transform/iceberg_compaction.py \
  --table iex_db.raw_stream_iex_2 \
  --target-file-size-mb 512 \
  --iceberg-catalog my_catalog \
  --iceberg-warehouse s3a://test2/mywarehouse
```

**Features:**
- Merges small files to improve query performance
- Displays before/after statistics
- Supports partition filtering
- Dry-run mode available

### Manage Kafka Topics

```bash
# Create topic
python extract/admin/create_kafka_topic.py \
  --topic my_topic \
  --partitions 3 \
  --replication-factor 1 \
  --bootstrap-servers localhost:9092

# List topics
kubectl exec -it my-cluster-kafka-0 -n kafka -- \
  bin/kafka-topics.sh --bootstrap-server localhost:9092 --list

# Debug consumer
python extract/admin/kafka_consumer_stdout.py \
  --topic iex_data \
  --bootstrap-servers localhost:9092
```

### Monitor Kafka Streams Application

```bash
# View application logs
kubectl logs -n kafka -l app=kstreams-flatten -f

# Check consumer lag
kubectl exec -it my-cluster-kafka-0 -n kafka -- \
  bin/kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --describe --group kstreams-flatten-app

# Edit configuration
kubectl edit configmap kstreams-flatten-config -n kafka

# Restart application
kubectl rollout restart deployment/kstreams-flatten-app -n kafka
```

### Minikube Commands

```bash
# Start/stop Minikube
minikube start
minikube stop
minikube status

# View all pods
kubectl get pods -A

# Service list
minikube service list

# Check resources
kubectl top nodes
kubectl top pods -A
```

---

## Troubleshooting

### Kafka Streams Application Not Starting

**Check logs:**
```bash
kubectl logs -n kafka -l app=kstreams-flatten
```

**Common issues:**
- Kafka broker not ready - wait for Kafka pods to be running
- Topic doesn't exist - create input/output topics first
- Resource constraints - check pod events with `kubectl describe pod`

### Minikube Out of Resources

```bash
# Stop Minikube
minikube stop

# Restart with more resources
minikube start --cpus=12 --memory=20000
```

### Kafka Pod Not Starting

```bash
# Check logs
kubectl logs -n kafka my-cluster-kafka-0

# Check events
kubectl describe pod my-cluster-kafka-0 -n kafka

# Verify Strimzi operator
kubectl get pods -n kafka -l name=strimzi-cluster-operator
```

### MinIO Connection Issues

```bash
# Verify MinIO is running
kubectl get pods -n minio

# Check port forwarding
ps aux | grep "kubectl port-forward"

# Restart port forward
kubectl port-forward -n minio svc/minio 9000:9000 9001:9001 &
```

### Snappy Compression Error

```bash
# Install required libraries
sudo apt-get install -y libsnappy-dev
pip install python-snappy
```

---

## Development

### Modifying Kafka Streams Application

1. Edit source code in `kstreams-app/src/main/java/`
2. Rebuild Docker image: `cd kstreams-app && ./build-docker.sh`
3. Redeploy: `kubectl rollout restart deployment/kstreams-flatten-app -n kafka`

### Adding New Stock Data Fields

1. Update `StockData.java` with new fields
2. Add Jackson annotations (`@JsonProperty`)
3. Update getters/setters and `toString()`
4. Rebuild and redeploy

### Running Locally (without Kubernetes)

```bash
cd kstreams-app

# Build
./gradlew build

# Run with local Kafka
./gradlew run --args="-b localhost:9092 -i iex_data -o iex_data_flattened"
```

---

## What You'll Learn

This project provides hands-on experience with:

- **Stream Ingestion**: WebSocket → Kafka producer patterns
- **Message Brokers**: Kafka topics, partitions, consumer groups
- **Stream Processing**: Kafka Streams topology, transformations, serdes
- **Data Lakehouse**: Iceberg ACID transactions, time-travel, schema evolution, compaction
- **Real-time Analytics**: Pinot indexing, OLAP query optimization
- **Kubernetes**: Deploying stateful applications, operators (Strimzi), ConfigMaps
- **Object Storage**: S3-compatible storage with MinIO
- **Java Streaming**: Modern Java patterns, picocli, Jackson, multi-stage Docker builds

**Suggested Next Steps:**
- Add windowed aggregations in Kafka Streams (e.g., 5-minute VWAP)
- Implement stateful transformations with state stores
- Create Pinot real-time tables with complex indexes
- Experiment with Iceberg partition evolution and hidden partitions
- Build custom stream processors with joins and branching
- Add metrics and monitoring with JMX/Prometheus

---

## Configuration Reference

### Kafka Streams Application

Edit `kstreams-app/k8s/deployment.yaml` ConfigMap:

```yaml
data:
  KAFKA_BROKER: "my-cluster-kafka-bootstrap:9092"
  INPUT_TOPIC: "iex-topic-1"
  OUTPUT_TOPIC: "iex-topic-1-flattened"
  APP_NAME: "kstreams-flatten-app"
```

### Kafka Cluster

Edit `minikube/kafka/02-kafka_deploy.yaml`:

```yaml
spec:
  kafka:
    replicas: 3  # Number of brokers
    config:
      num.partitions: 3
      default.replication.factor: 1
      log.retention.hours: 168  # 7 days
```

### MinIO Credentials

Default: `minio` / `minio123`

To change, edit MinIO deployment before applying.

---

## Cleanup

### Stop Services (preserve data)

```bash
minikube stop
pkill -f "kubectl port-forward"
```

### Delete Everything

```bash
# Delete Minikube cluster
minikube delete

# Remove project dependencies
rm -rf .venv
```

### Delete Kafka Streams App Only

```bash
kubectl delete -f kstreams-app/k8s/deployment.yaml
```

---

## External Resources

- [Apache Kafka Documentation](https://kafka.apache.org/documentation/)
- [Kafka Streams Documentation](https://kafka.apache.org/documentation/streams/)
- [Apache Iceberg Documentation](https://iceberg.apache.org/docs/latest/)
- [Apache Pinot Documentation](https://docs.pinot.apache.org/)
- [Strimzi Kafka Operator](https://strimzi.io/docs/operators/latest/overview.html)
- [Alpaca API Documentation](https://alpaca.markets/docs/)

---

## License

This project is for educational and learning purposes. Feel free to use, modify, and extend for your own learning and prototyping needs.

---

**Happy Streaming!**
