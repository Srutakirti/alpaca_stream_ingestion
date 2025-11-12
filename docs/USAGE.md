# Usage & Operations Guide

Common operations, monitoring, and query examples for the Alpaca Stream Ingestion pipeline.

---

## Table of Contents

- [Starting the Pipeline](#starting-the-pipeline)
- [Monitoring](#monitoring)
- [Kafka Operations](#kafka-operations)
- [Spark Operations](#spark-operations)
- [Querying Data](#querying-data)
- [Common Tasks](#common-tasks)

---

## Starting the Pipeline

### End-to-End Pipeline

**Terminal 1: Start Data Generator**
```bash
# Option A: Sample generator (no credentials needed)
python minikube/kafka/sample_event_generators/stream_producer_cli.py \
  --kafka-brokers localhost:9092 \
  --topic iex_data \
  --symbols AAPL GOOGL MSFT AMZN TSLA \
  --batch-size 100 \
  --interval 2 \
  --batch-count 0

# Option B: Live Alpaca WebSocket (requires credentials)
export ALPACA_KEY="your_key"
export ALPACA_SECRET="your_secret"
cd extract/app
python alpaca_ws_updated_conf.py
```

**Terminal 2: Start Spark Streaming Job**
```bash
python transform/spark_streaming_flattener_cli.py \
  --kafka-brokers localhost:9092 \
  --source-topic iex_data \
  --dest-topic flattened_stocks \
  --output-mode both \
  --processing-time "10 seconds"
```

**Terminal 3: Monitor Kafka Output (Optional)**
```bash
python extract/admin/kafka_consumer_stdout.py \
  --topic flattened_stocks \
  --bootstrap-servers localhost:9092
```

---

## Monitoring

### Minikube Dashboard

```bash
# Open Kubernetes dashboard
minikube dashboard

# View all resources
kubectl get all -A

# Check resource usage
kubectl top nodes
kubectl top pods -A
```

### Kafka Monitoring

```bash
# List all topics
kubectl exec -it my-cluster-kafka-0 -n kafka -- \
  bin/kafka-topics.sh \
  --bootstrap-server localhost:9092 \
  --list

# Describe topic (partitions, replicas, ISR)
kubectl exec -it my-cluster-kafka-0 -n kafka -- \
  bin/kafka-topics.sh \
  --bootstrap-server localhost:9092 \
  --describe \
  --topic iex_data

# Check consumer group lag
kubectl exec -it my-cluster-kafka-0 -n kafka -- \
  bin/kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --describe \
  --group spark-kafka-streaming

# List all consumer groups
kubectl exec -it my-cluster-kafka-0 -n kafka -- \
  bin/kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --list
```

### Spark Streaming Monitoring

```bash
# Access Spark UI (while job is running)
open http://localhost:4040

# Key metrics to watch:
# - Streaming tab: Input rate, processing rate, batch duration
# - SQL tab: Query execution details
# - Executors tab: Resource usage
```

**Spark UI Metrics:**
- **Input Rate**: Records/second being read from Kafka
- **Processing Rate**: Records/second being processed
- **Batch Duration**: Time to process each micro-batch
- **Scheduling Delay**: Backlog if processing can't keep up

**Healthy Streaming Job:**
- Processing rate ≥ Input rate
- Scheduling delay = 0 or minimal
- Batch duration < trigger interval

### MinIO Monitoring

```bash
# Access MinIO console
open http://localhost:9001

# Login: minioadmin / minioadmin
# View buckets, objects, storage usage
```

### Pinot Monitoring

```bash
# Access Pinot console
open http://localhost:9000

# View:
# - Cluster Manager: Servers, brokers, controllers
# - Query Console: Run queries
# - Tables: Table configs and stats
```

---

## Kafka Operations

### Create Topic

```bash
# Using Python utility
python extract/admin/create_kafka_topic.py \
  --topic my_topic \
  --partitions 6 \
  --replication-factor 1 \
  --bootstrap-servers localhost:9092

# Using Kafka CLI
kubectl exec -it my-cluster-kafka-0 -n kafka -- \
  bin/kafka-topics.sh \
  --bootstrap-server localhost:9092 \
  --create \
  --topic my_topic \
  --partitions 6 \
  --replication-factor 1
```

### Delete Topic

```bash
kubectl exec -it my-cluster-kafka-0 -n kafka -- \
  bin/kafka-topics.sh \
  --bootstrap-server localhost:9092 \
  --delete \
  --topic my_topic
```

### Consume Messages (Console)

```bash
# From beginning
kubectl exec -it my-cluster-kafka-0 -n kafka -- \
  bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic iex_data \
  --from-beginning

# From latest
kubectl exec -it my-cluster-kafka-0 -n kafka -- \
  bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic iex_data

# With Python utility (formatted output)
python extract/admin/kafka_consumer_stdout.py \
  --topic iex_data \
  --bootstrap-servers localhost:9092 \
  --group debug-consumer
```

### Produce Test Messages

```bash
# Interactive producer
kubectl exec -it my-cluster-kafka-0 -n kafka -- \
  bin/kafka-console-producer.sh \
  --bootstrap-server localhost:9092 \
  --topic iex_data

# Type messages, Ctrl+C to exit
```

### Reset Consumer Group Offsets

```bash
# Reset to earliest
kubectl exec -it my-cluster-kafka-0 -n kafka -- \
  bin/kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --group spark-kafka-streaming \
  --reset-offsets \
  --to-earliest \
  --topic iex_data \
  --execute

# Reset to latest
kubectl exec -it my-cluster-kafka-0 -n kafka -- \
  bin/kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --group spark-kafka-streaming \
  --reset-offsets \
  --to-latest \
  --topic iex_data \
  --execute

# Reset to specific offset
kubectl exec -it my-cluster-kafka-0 -n kafka -- \
  bin/kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --group spark-kafka-streaming \
  --reset-offsets \
  --to-offset 1000 \
  --topic iex_data:0 \
  --execute
```

### View Topic Configuration

```bash
kubectl exec -it my-cluster-kafka-0 -n kafka -- \
  bin/kafka-configs.sh \
  --bootstrap-server localhost:9092 \
  --entity-type topics \
  --entity-name iex_data \
  --describe
```

---

## Spark Operations

### Start Spark Streaming Job

```bash
# Using CLI tool (recommended)
python transform/spark_streaming_flattener_cli.py \
  --kafka-brokers localhost:9092 \
  --source-topic iex_data \
  --dest-topic flattened_stocks \
  --output-mode both

# Using shell wrapper
cd transform
./run_pyspark_streamer.sh
```

### Stop Spark Streaming Job

```bash
# Graceful stop: Ctrl+C in terminal
# Job will finish current batch and shutdown cleanly

# Force kill (not recommended)
pkill -f spark_streaming_flattener_cli
```

### Reset Spark Checkpoints

```bash
# Stop Spark job first!

# Remove checkpoint directories
rm -rf /tmp/spark-checkpoints/kafka
rm -rf /tmp/spark-checkpoints/iceberg

# Restart job - will start fresh from latest/earliest offsets
```

### Change Spark Configuration

```bash
# Increase parallelism
python transform/spark_streaming_flattener_cli.py \
  --kafka-brokers localhost:9092 \
  --source-topic iex_data \
  --dest-topic flattened_stocks \
  --output-mode both
  # Add Spark configs via environment or code

# Set environment variables
export SPARK_EXECUTOR_MEMORY=4g
export SPARK_DRIVER_MEMORY=2g
```

### View Spark Logs

```bash
# Logs are printed to console where job was started

# Or check Spark event logs
ls -la /tmp/spark-events/
```

---

## Querying Data

### Query Iceberg (Spark SQL)

**Start Spark SQL Shell:**
```bash
spark-sql \
  --packages org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.4.0 \
  --conf spark.sql.extensions=org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions \
  --conf spark.sql.catalog.spark_catalog=org.apache.iceberg.spark.SparkSessionCatalog \
  --conf spark.sql.catalog.spark_catalog.type=hadoop \
  --conf spark.sql.catalog.spark_catalog.warehouse=s3a://warehouse/ \
  --conf spark.hadoop.fs.s3a.endpoint=http://localhost:9000 \
  --conf spark.hadoop.fs.s3a.access.key=minioadmin \
  --conf spark.hadoop.fs.s3a.secret.key=minioadmin \
  --conf spark.hadoop.fs.s3a.path.style.access=true \
  --conf spark.hadoop.fs.s3a.impl=org.apache.hadoop.fs.s3a.S3AFileSystem
```

**Example Queries:**
```sql
-- Latest trades
SELECT * FROM local.db.flattened_stocks
ORDER BY timestamp DESC
LIMIT 10;

-- Trades by symbol
SELECT S, COUNT(*) as count, AVG(p) as avg_price
FROM local.db.flattened_stocks
GROUP BY S
ORDER BY count DESC;

-- Time-travel to specific snapshot
SELECT * FROM local.db.flattened_stocks
VERSION AS OF 123456789;

-- View table history
SELECT * FROM local.db.flattened_stocks.history;

-- View snapshots
SELECT
  snapshot_id,
  committed_at,
  operation,
  summary
FROM local.db.flattened_stocks.snapshots;
```

### Query Pinot

**Access Pinot Console:**
```bash
open http://localhost:9000
```

**Example Queries:**
```sql
-- Recent trades
SELECT * FROM flattened_stocks
ORDER BY timestamp DESC
LIMIT 10;

-- Top symbols by volume
SELECT
  S as symbol,
  SUM(s) as total_volume,
  COUNT(*) as trade_count
FROM flattened_stocks
GROUP BY S
ORDER BY total_volume DESC
LIMIT 10;

-- Price statistics
SELECT
  S as symbol,
  AVG(p) as avg_price,
  MIN(p) as min_price,
  MAX(p) as max_price,
  STDDEV(p) as price_stddev
FROM flattened_stocks
GROUP BY S;

-- Trades in last hour
SELECT
  S as symbol,
  COUNT(*) as recent_trades,
  AVG(p) as avg_price
FROM flattened_stocks
WHERE timestamp > now() - 3600000
GROUP BY S
ORDER BY recent_trades DESC;

-- Time-series (1-minute buckets)
SELECT
  DATETIMECONVERT(timestamp, '1:MILLISECONDS:EPOCH', '1:MINUTES:EPOCH', '1:MINUTES') as minute,
  S as symbol,
  AVG(p) as avg_price,
  SUM(s) as volume
FROM flattened_stocks
WHERE S = 'AAPL'
GROUP BY minute, S
ORDER BY minute DESC
LIMIT 60;
```

---

## Common Tasks

### Start All Services

```bash
# Start Minikube (if stopped)
minikube start

# Verify all pods are running
kubectl get pods -A

# Port-forward services
kubectl port-forward -n kafka svc/my-cluster-kafka-bootstrap 9092:9092 &
kubectl port-forward -n minio svc/minio 9000:9000 9001:9001 &
kubectl port-forward -n pinot svc/pinot-controller 9000:9000 &

# Or use automated script
./test_new_2.sh --port-forward
```

### Stop All Services

```bash
# Stop Minikube (preserves data)
minikube stop

# Kill port-forward processes
pkill -f "kubectl port-forward"
```

### Restart Kafka

```bash
# Restart Kafka StatefulSet
kubectl rollout restart statefulset/my-cluster-kafka -n kafka

# Wait for pods to be ready
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=kafka -n kafka --timeout=300s
```

### Clean Kafka Topics (Delete All Data)

```bash
# List topics
kubectl exec -it my-cluster-kafka-0 -n kafka -- \
  bin/kafka-topics.sh --bootstrap-server localhost:9092 --list

# Delete specific topic
kubectl exec -it my-cluster-kafka-0 -n kafka -- \
  bin/kafka-topics.sh --bootstrap-server localhost:9092 --delete --topic iex_data

# Recreate
python extract/admin/create_kafka_topic.py \
  --topic iex_data \
  --partitions 3 \
  --replication-factor 1
```

### Clean Iceberg Tables (Delete All Data)

```bash
# Drop table in Spark SQL
spark-sql --packages org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.4.0 \
  --conf spark.sql.catalog.spark_catalog=org.apache.iceberg.spark.SparkSessionCatalog

# In Spark SQL shell
DROP TABLE local.db.flattened_stocks;

# Delete from MinIO (optional - removes all data)
# Access MinIO console at http://localhost:9001
# Delete warehouse bucket or specific table path
```

### Export Data from Iceberg

```bash
# Using Spark SQL
spark-sql --packages org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.4.0 \
  --conf spark.sql.catalog.spark_catalog=org.apache.iceberg.spark.SparkSessionCatalog

# Export to CSV
SELECT * FROM local.db.flattened_stocks
WHERE S = 'AAPL'
ORDER BY timestamp;

# Save results to file
SELECT * FROM local.db.flattened_stocks
INTO '/tmp/export.csv' FORMAT csv;
```

### Backup Minikube Data

```bash
# Stop Minikube
minikube stop

# Backup Minikube profile
cp -r ~/.minikube/profiles/minikube ~/minikube-backup-$(date +%Y%m%d)

# Backup MinIO data
cp -r /mnt/mydrive2/minio ~/minio-backup-$(date +%Y%m%d)
```

### Update Python Dependencies

```bash
# Add new package
uv add package-name

# Update existing packages
uv sync

# Lock dependencies
uv lock

# Install from lock file
uv pip install -r requirements.txt
```

### View Logs

```bash
# Kafka broker logs
kubectl logs -n kafka my-cluster-kafka-0

# Pinot controller logs
kubectl logs -n pinot -l app=pinot-controller

# MinIO logs
kubectl logs -n minio -l app=minio

# WebSocket extractor logs (if deployed)
kubectl logs -n default -l app=alpaca-extractor
```

### Scale Services

```bash
# Scale Kafka brokers (edit YAML)
kubectl edit kafka my-cluster -n kafka
# Change spec.kafka.replicas to desired number

# Scale Pinot servers
helm upgrade pinot pinot/pinot \
  -n pinot \
  -f minikube/pinot/myvalues.yaml \
  --set server.replicaCount=2
```

---

## Performance Tuning

### Kafka Performance

**Increase throughput:**
```yaml
# Edit minikube/kafka/02-kafka_deploy.yaml
spec:
  kafka:
    config:
      num.network.threads: 8
      num.io.threads: 16
      socket.send.buffer.bytes: 102400
      socket.receive.buffer.bytes: 102400
      socket.request.max.bytes: 104857600
```

### Spark Performance

**Increase parallelism:**
```bash
# Set environment variables
export SPARK_EXECUTOR_CORES=4
export SPARK_EXECUTOR_MEMORY=4g
export SPARK_DRIVER_MEMORY=2g

# Or use spark-defaults.conf
cat >> $SPARK_HOME/conf/spark-defaults.conf <<EOF
spark.executor.cores 4
spark.executor.memory 4g
spark.driver.memory 2g
spark.sql.shuffle.partitions 200
EOF
```

### Minikube Performance

```bash
# Allocate more resources
minikube delete
minikube start --cpus=12 --memory=20000 --disk-size=50g
```

---

## Next Steps

- See **[Setup Guide](SETUP.md)** for installation details
- See **[Pipeline Components](PIPELINE.md)** for component deep dive
- See **[Troubleshooting](TROUBLESHOOTING.md)** for common issues
