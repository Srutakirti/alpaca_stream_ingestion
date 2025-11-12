# Alpaca Stream Ingestion

> **A complete real-time data engineering pipeline for learning and rapid prototyping**

Local-first streaming data platform that ingests live stock market data, processes it through Kafka and Spark, and stores it in modern data lakehouse (Iceberg) and analytics (Pinot) systems - all running on Minikube without any cloud dependencies.

---

## 🎯 Purpose

This project is designed for:
- **Learning**: Hands-on experience with modern data engineering tools (Kafka, Spark, Iceberg, Pinot)
- **Rapid Prototyping**: Test streaming patterns and transformations locally before cloud deployment
- **No Cloud Lock-in**: Everything runs on your machine using Minikube
- **Real Data**: Connect to Alpaca's free tier for live stock market data, or use built-in sample generators

Perfect for data engineers learning streaming patterns, students exploring distributed systems, or professionals prototyping data pipelines.

---

## 🏗️ Architecture

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
│   PySpark Streaming│  (Stream Processing)
│   - Flatten JSON   │
│   - Transform      │
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

**Data Flow:** WebSocket → Kafka → Spark → (Iceberg + Pinot)

---

## 🛠️ Tech Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Infrastructure** | Minikube + Docker | Local Kubernetes cluster |
| **Messaging** | Apache Kafka (Strimzi) | Distributed message broker |
| **Stream Processing** | PySpark 3.5.1 | Real-time data transformation |
| **Data Lakehouse** | Apache Iceberg | ACID-compliant table format with time-travel |
| **Analytics Database** | Apache Pinot | Low-latency OLAP queries |
| **Object Storage** | MinIO | S3-compatible storage for Iceberg |
| **Data Source** | Alpaca WebSocket API | Live stock market data (IEX feed) |
| **Language** | Python 3.10+ | Primary development language |

---

## 📁 Project Structure

```
alpaca_stream_ingestion/
├── extract/                    # Data ingestion layer
│   ├── app/
│   │   ├── alpaca_ws_updated_conf.py   # WebSocket → Kafka producer
│   │   └── conf_reader.py              # Configuration loader
│   ├── admin/
│   │   ├── create_kafka_topic.py       # Topic management utility
│   │   └── kafka_consumer_stdout.py    # Debug consumer
│   └── history/
│       └── simulate_stream_from_history.py  # Historical data replay
│
├── transform/                  # Stream processing layer
│   ├── spark_streaming_flattener_cli.py    # Main Spark streaming job (CLI)
│   ├── spark_kafka_to_iceberg.py           # Kafka → Iceberg writer
│   └── run_pyspark_streamer.sh             # Spark job launcher
│
├── load/                       # Query and analytics layer
│   ├── pinot_qeury_display.py  # Pinot query utilities
│   └── create.py               # Table creation helpers
│
├── minikube/                   # Kubernetes manifests
│   ├── kafka/
│   │   ├── 00-kafka_ns.yaml                # Kafka namespace
│   │   ├── 01-stimzi_operator.yaml         # Strimzi operator
│   │   ├── 02-kafka_deploy.yaml            # Kafka cluster definition
│   │   └── sample_event_generators/
│   │       └── stream_producer_cli.py      # Standalone sample data generator
│   ├── minio/                              # MinIO deployment manifests
│   ├── pinot/                              # Pinot deployment (Helm values)
│   ├── spark/                              # Spark operator manifests
│   └── extractor_deploy/                   # WebSocket app K8s deployment
│
├── config/                     # Configuration files
├── iceberg/                    # Iceberg table definitions
├── docs/                       # Documentation
│   ├── SETUP.md                # Installation & configuration guide
│   ├── PIPELINE.md             # Pipeline components deep dive
│   ├── USAGE.md                # Operations & examples
│   └── TROUBLESHOOTING.md      # Common issues & solutions
│
├── test_new_2.sh              # PRIMARY: Automated infrastructure setup
├── cron_trigger.sh            # Periodic job scheduler
├── pyproject.toml             # Python dependencies
├── STRIMZI_KAFKA_CONNECT_GUIDE.md  # Kafka Connect setup guide
└── README.md                  # This file
```

---

## 🚀 Quick Start

### Prerequisites
- **Hardware**: 8 CPU cores, 15GB RAM minimum
- **OS**: Ubuntu Linux (22.04+) or similar
- **Optional**: Alpaca API credentials for live data ([free tier](https://alpaca.markets))

### Automated Setup (5 minutes)

```bash
# Clone the repository
git clone <repository-url>
cd alpaca_stream_ingestion

# Run the automated setup script
chmod +x test_new_2.sh

# Full setup: installs dependencies, starts Minikube, deploys all services
./test_new_2.sh --setup-infra --setup-minikube --setup-kafka --setup-minio --setup-pinot

# Start sample data generator (no credentials needed)
python minikube/kafka/sample_event_generators/stream_producer_cli.py \
  --kafka-brokers localhost:9092 \
  --topic iex_data \
  --symbols AAPL GOOGL MSFT \
  --batch-size 50 \
  --interval 2

# Start Spark streaming job
python transform/spark_streaming_flattener_cli.py \
  --kafka-brokers localhost:9092 \
  --source-topic iex_data \
  --dest-topic flattened_stocks \
  --output-mode both
```

**That's it!** Your pipeline is now running. Access:
- **Pinot Console**: http://localhost:9000 (query analytics)
- **MinIO Console**: http://localhost:9001 (view storage)
- **Spark UI**: http://localhost:4040 (monitoring)

For detailed setup instructions, see **[Setup Guide](docs/SETUP.md)**.

---

## 💡 Key Usage Examples

### Stream Live Stock Data

```bash
# Option 1: Use sample generator (no API keys needed)
python minikube/kafka/sample_event_generators/stream_producer_cli.py \
  --kafka-brokers localhost:9092 \
  --topic iex_data \
  --symbols AAPL GOOGL MSFT AMZN TSLA \
  --batch-size 100 \
  --interval 2

# Option 2: Connect to live Alpaca WebSocket (requires credentials)
export ALPACA_KEY="your_api_key"
export ALPACA_SECRET="your_api_secret"
./test_new_2.sh --setup-app
```

### Query Real-time Analytics (Pinot)

```sql
-- Access Pinot console at http://localhost:9000

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

### Query Historical Data (Iceberg)

```bash
# Start Spark SQL shell
spark-sql \
  --packages org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.4.0 \
  --conf spark.sql.catalog.spark_catalog=org.apache.iceberg.spark.SparkSessionCatalog

# Query latest data
SELECT * FROM local.db.flattened_stocks ORDER BY timestamp DESC LIMIT 10;

# Time-travel query
SELECT * FROM local.db.flattened_stocks VERSION AS OF 123456789;
```

For more examples, see **[Usage Guide](docs/USAGE.md)**.

---

## 📖 Documentation

| Document | Description |
|----------|-------------|
| **[Setup Guide](docs/SETUP.md)** | Installation, prerequisites, manual setup steps |
| **[Pipeline Components](docs/PIPELINE.md)** | Deep dive into extractors, processors, and storage |
| **[Usage & Operations](docs/USAGE.md)** | Common operations, monitoring, query examples |
| **[Troubleshooting](docs/TROUBLESHOOTING.md)** | Common issues and solutions |
| **[Kafka Connect Guide](STRIMZI_KAFKA_CONNECT_GUIDE.md)** | Strimzi Kafka Connect setup |

---

## 🎓 What You'll Learn

This project provides hands-on experience with:

- **Stream Ingestion**: WebSocket → Kafka producer patterns
- **Message Brokers**: Kafka topics, partitions, consumer groups
- **Stream Processing**: Spark Structured Streaming, transformations
- **Data Lakehouse**: Iceberg ACID transactions, time-travel, schema evolution
- **Real-time Analytics**: Pinot indexing, OLAP query optimization
- **Kubernetes**: Deploying stateful applications, operators (Strimzi)
- **Object Storage**: S3-compatible storage with MinIO

**Suggested Next Steps:**
- Add windowed aggregations in Spark (e.g., 5-minute VWAP)
- Implement late data handling and watermarking
- Create Pinot real-time tables with complex indexes
- Experiment with Iceberg partition evolution
- Build custom Spark transformations (joins, sessionization)

---

## 🔧 Common Commands

```bash
# Minikube
minikube start
minikube stop
minikube status

# Check Kafka topics
kubectl exec -it my-cluster-kafka-0 -n kafka -- bin/kafka-topics.sh \
  --bootstrap-server localhost:9092 --list

# Monitor Kafka consumer lag
kubectl exec -it my-cluster-kafka-0 -n kafka -- bin/kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 --describe --group spark-kafka-streaming

# View Spark streaming UI
open http://localhost:4040

# Access Pinot query console
open http://localhost:9000
```

See **[Usage Guide](docs/USAGE.md)** for complete command reference.

---

## 🐛 Troubleshooting

**Common issues:**
- **Snappy compression error**: Install `libsnappy-dev` and `python-snappy`
- **Minikube out of resources**: Restart with `--cpus=12 --memory=20000`
- **Kafka pod not starting**: Check logs with `kubectl logs -n kafka my-cluster-kafka-0`
- **S3 connection error**: Verify MinIO port-forward is active

See **[Troubleshooting Guide](docs/TROUBLESHOOTING.md)** for detailed solutions.

---

## 📚 External Resources

- [Apache Kafka Documentation](https://kafka.apache.org/documentation/)
- [PySpark Structured Streaming Guide](https://spark.apache.org/docs/latest/structured-streaming-programming-guide.html)
- [Apache Iceberg Documentation](https://iceberg.apache.org/docs/latest/)
- [Apache Pinot Documentation](https://docs.pinot.apache.org/)
- [Strimzi Kafka Operator](https://strimzi.io/docs/operators/latest/overview.html)
- [Alpaca API Documentation](https://alpaca.markets/docs/)

---

## 📝 License

This project is for educational and learning purposes. Feel free to use, modify, and extend for your own learning and prototyping needs.

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome! This is a learning-focused project, so improvements to documentation, additional examples, and new pipeline patterns are especially appreciated.

---

**Happy Streaming! 🚀**
