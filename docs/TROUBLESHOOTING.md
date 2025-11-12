# Troubleshooting Guide

Common issues and solutions for the Alpaca Stream Ingestion pipeline.

---

## Table of Contents

- [Installation Issues](#installation-issues)
- [Minikube Issues](#minikube-issues)
- [Kafka Issues](#kafka-issues)
- [Spark Issues](#spark-issues)
- [Storage Issues](#storage-issues)
- [Network Issues](#network-issues)
- [Performance Issues](#performance-issues)

---

## Installation Issues

### Issue: `python-snappy` Import Error

**Error:**
```
Libraries for snappy compression codec not found
ModuleNotFoundError: No module named 'snappy'
```

**Cause:** Kafka uses Snappy compression, which requires both system library and Python package.

**Solution:**
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y libsnappy-dev
pip install python-snappy

# macOS
brew install snappy
pip install python-snappy

# Conda
conda install python-snappy

# Verify installation
python -c "import snappy; print('Snappy OK')"
```

---

### Issue: UV Installation Fails

**Error:**
```
curl: command not found
```

**Solution:**
```bash
# Install curl first
sudo apt-get update
sudo apt-get install -y curl

# Retry UV installation
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.local/bin/env
```

---

### Issue: Java Not Found

**Error:**
```
Error: JAVA_HOME is not set
```

**Solution:**
```bash
# Install OpenJDK 17
sudo apt-get update
sudo apt-get install -y openjdk-17-jdk

# Set JAVA_HOME (add to ~/.bashrc)
export JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
export PATH=$JAVA_HOME/bin:$PATH

# Apply changes
source ~/.bashrc

# Verify
java -version
```

---

## Minikube Issues

### Issue: Minikube Won't Start

**Error:**
```
Exiting due to GUEST_PROVISION: error provisioning host
```

**Causes:**
- Insufficient resources
- Docker issues
- Previous failed installation

**Solution 1: Increase Resources**
```bash
# Delete and restart with more resources
minikube delete
minikube start --cpus=12 --memory=20000 --driver=docker
```

**Solution 2: Fix Docker Permissions**
```bash
# Add user to docker group
sudo usermod -aG docker $USER
newgrp docker

# Restart Docker
sudo systemctl restart docker

# Retry Minikube
minikube start
```

**Solution 3: Clean Minikube State**
```bash
# Remove all Minikube files
minikube delete --all --purge
rm -rf ~/.minikube

# Reinstall
minikube start --cpus=8 --memory=14999 --driver=docker
```

---

### Issue: Pods Stuck in Pending State

**Error:**
```bash
kubectl get pods -A
# Shows pods in "Pending" state
```

**Cause:** Insufficient cluster resources.

**Solution:**
```bash
# Check node resources
kubectl describe node minikube

# Check events
kubectl get events -A --sort-by='.lastTimestamp'

# Increase Minikube resources
minikube delete
minikube start --cpus=12 --memory=20000

# Or free up space
minikube ssh
docker system prune -a
exit
```

---

### Issue: Minikube Disk Full

**Error:**
```
no space left on device
```

**Solution:**
```bash
# SSH into Minikube
minikube ssh

# Check disk usage
df -h

# Clean Docker images
docker system prune -a -f

# Clean old logs
sudo rm -rf /var/log/*.log

# Exit Minikube
exit

# Or increase disk size (requires delete)
minikube delete
minikube start --cpus=8 --memory=14999 --disk-size=50g
```

---

## Kafka Issues

### Issue: Kafka Pod Not Starting

**Error:**
```bash
kubectl get pods -n kafka
# my-cluster-kafka-0: CrashLoopBackOff
```

**Solution 1: Check Logs**
```bash
# View pod logs
kubectl logs -n kafka my-cluster-kafka-0

# View previous logs (if pod restarted)
kubectl logs -n kafka my-cluster-kafka-0 --previous

# Describe pod for events
kubectl describe pod -n kafka my-cluster-kafka-0
```

**Solution 2: Restart Strimzi Operator**
```bash
# Restart operator
kubectl rollout restart deployment/strimzi-cluster-operator -n kafka

# Wait for operator
kubectl wait --for=condition=ready pod -l name=strimzi-cluster-operator -n kafka --timeout=300s

# Delete and recreate Kafka cluster
kubectl delete kafka my-cluster -n kafka
kubectl apply -f minikube/kafka/02-kafka_deploy.yaml
```

**Solution 3: Check PersistentVolumes**
```bash
# View PVCs
kubectl get pvc -n kafka

# If PVCs are stuck, delete them
kubectl delete pvc -n kafka --all

# Redeploy Kafka
kubectl apply -f minikube/kafka/02-kafka_deploy.yaml
```

---

### Issue: Cannot Connect to Kafka

**Error:**
```
Connection refused: localhost:9092
```

**Solution:**
```bash
# Check if Kafka is running
kubectl get pods -n kafka

# Check Kafka service
kubectl get svc -n kafka

# Verify port-forward is active
ps aux | grep "port-forward"

# If not running, start port-forward
kubectl port-forward -n kafka svc/my-cluster-kafka-bootstrap 9092:9092 &

# Test connection
nc -zv localhost 9092
# Should output: Connection to localhost 9092 port [tcp/*] succeeded!
```

---

### Issue: Topic Already Exists Error

**Error:**
```
TopicExistsException: Topic 'iex_data' already exists
```

**Solution:**
```bash
# List topics
kubectl exec -it my-cluster-kafka-0 -n kafka -- \
  bin/kafka-topics.sh --bootstrap-server localhost:9092 --list

# Delete topic
kubectl exec -it my-cluster-kafka-0 -n kafka -- \
  bin/kafka-topics.sh --bootstrap-server localhost:9092 --delete --topic iex_data

# Recreate with desired config
python extract/admin/create_kafka_topic.py \
  --topic iex_data \
  --partitions 3 \
  --replication-factor 1
```

---

### Issue: Consumer Lag Growing

**Problem:** Consumer can't keep up with producers.

**Diagnosis:**
```bash
# Check consumer group lag
kubectl exec -it my-cluster-kafka-0 -n kafka -- \
  bin/kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --describe \
  --group spark-kafka-streaming
```

**Solution:**
```bash
# Increase Spark parallelism
python transform/spark_streaming_flattener_cli.py \
  --kafka-brokers localhost:9092 \
  --source-topic iex_data \
  --dest-topic flattened_stocks \
  --output-mode both
  # Add more executor cores/memory via environment

# Increase Kafka topic partitions
kubectl exec -it my-cluster-kafka-0 -n kafka -- \
  bin/kafka-topics.sh \
  --bootstrap-server localhost:9092 \
  --alter \
  --topic iex_data \
  --partitions 6

# Decrease batch interval
python transform/spark_streaming_flattener_cli.py \
  --processing-time "5 seconds"  # Faster batches
```

---

## Spark Issues

### Issue: PySpark `StreamingQuery` Import Error

**Error:**
```
"StreamingQuery" is not exported from module "pyspark.sql.streaming"
```

**Cause:** Using wrong import path for Pylance type checking.

**Solution:**
```python
# Change import
from pyspark.sql.streaming.query import StreamingQuery

# Instead of
from pyspark.sql.streaming import StreamingQuery
```

**Note:** This was already fixed in commit `8a4cac8`.

---

### Issue: Spark Job Out of Memory

**Error:**
```
java.lang.OutOfMemoryError: Java heap space
```

**Solution:**
```bash
# Increase executor and driver memory
export SPARK_EXECUTOR_MEMORY=4g
export SPARK_DRIVER_MEMORY=2g

# Or set in spark-defaults.conf
echo "spark.executor.memory 4g" >> $SPARK_HOME/conf/spark-defaults.conf
echo "spark.driver.memory 2g" >> $SPARK_HOME/conf/spark-defaults.conf

# Restart Spark job
```

---

### Issue: Spark Streaming Batch Duration Too Long

**Problem:** Batches taking longer than trigger interval, causing backlog.

**Diagnosis:**
Check Spark UI at http://localhost:4040:
- Streaming tab: "Batch Duration" > "Trigger Interval"
- Scheduling delay increasing

**Solution:**
```bash
# Option 1: Increase trigger interval
python transform/spark_streaming_flattener_cli.py \
  --processing-time "30 seconds"  # More time per batch

# Option 2: Increase parallelism
export SPARK_EXECUTOR_CORES=4
export SPARK_EXECUTOR_MEMORY=4g

# Option 3: Simplify transformations
# Review and optimize Spark transformations

# Option 4: Filter data earlier
# Add WHERE clauses to reduce data volume
```

---

### Issue: Spark Checkpoint Corruption

**Error:**
```
Failed to read checkpoint from file
```

**Solution:**
```bash
# Stop Spark job

# Delete corrupted checkpoints
rm -rf /tmp/spark-checkpoints/kafka
rm -rf /tmp/spark-checkpoints/iceberg

# Restart job (will start fresh)
python transform/spark_streaming_flattener_cli.py \
  --starting-offsets latest  # or earliest
```

---

## Storage Issues

### Issue: MinIO Connection Error

**Error:**
```
Unable to connect to MinIO at s3a://warehouse/
Connection refused
```

**Solution:**
```bash
# Check MinIO is running
kubectl get pods -n minio

# Verify port-forward
ps aux | grep "port-forward.*minio"

# If not running, start port-forward
kubectl port-forward -n minio svc/minio 9000:9000 9001:9001 &

# Test MinIO health
curl http://localhost:9000/minio/health/live

# Verify credentials in Spark config
# Check --s3-access-key and --s3-secret-key match MinIO
```

---

### Issue: Iceberg Table Not Found

**Error:**
```
Table local.db.flattened_stocks not found
```

**Cause:** Table doesn't exist yet, or Spark catalog misconfigured.

**Solution:**
```bash
# Verify Spark catalog configuration
spark-sql \
  --conf spark.sql.catalog.spark_catalog=org.apache.iceberg.spark.SparkSessionCatalog \
  --conf spark.sql.catalog.spark_catalog.type=hadoop \
  --conf spark.sql.catalog.spark_catalog.warehouse=s3a://warehouse/

# Check if table exists
SHOW TABLES IN local.db;

# If not, run Spark streaming job to create it
python transform/spark_streaming_flattener_cli.py \
  --output-mode both  # or iceberg-only
```

---

### Issue: Pinot Table Not Created

**Error:**
```
Table flattened_stocks does not exist
```

**Solution:**
```bash
# Access Pinot console
open http://localhost:9000

# Create table manually or use utility
cd load
python create.py

# Or create via Pinot REST API
curl -X POST http://localhost:9000/tables \
  -H 'Content-Type: application/json' \
  -d @table_config.json
```

---

## Network Issues

### Issue: Port-Forward Stops Working

**Problem:** Port-forward processes die after some time.

**Solution:**
```bash
# Kill old port-forwards
pkill -f "kubectl port-forward"

# Restart all port-forwards
kubectl port-forward -n kafka svc/my-cluster-kafka-bootstrap 9092:9092 &
kubectl port-forward -n minio svc/minio 9000:9000 9001:9001 &
kubectl port-forward -n pinot svc/pinot-controller 9000:9000 &

# Or use automated script
./test_new_2.sh --port-forward
```

**Persistent Solution:**
Create a systemd service or use `screen`/`tmux`:
```bash
# Using screen
screen -dmS kafka-pf kubectl port-forward -n kafka svc/my-cluster-kafka-bootstrap 9092:9092
screen -dmS minio-pf kubectl port-forward -n minio svc/minio 9000:9000 9001:9001
screen -dmS pinot-pf kubectl port-forward -n pinot svc/pinot-controller 9000:9000

# List screens
screen -ls

# Reattach
screen -r kafka-pf
```

---

### Issue: Alpaca WebSocket Connection Fails

**Error:**
```
WebSocket connection failed: 401 Unauthorized
```

**Solution:**
```bash
# Verify credentials are set
echo $ALPACA_KEY
echo $ALPACA_SECRET

# If empty, set them
export ALPACA_KEY="your_api_key"
export ALPACA_SECRET="your_api_secret"

# Verify credentials are valid on Alpaca dashboard
open https://alpaca.markets/

# Check WebSocket URL
# Paper trading: wss://stream.data.alpaca.markets/v2/iex
# Live trading: wss://stream.data.alpaca.markets/v2/iex
```

---

## Performance Issues

### Issue: High CPU Usage

**Problem:** Minikube consuming too much CPU.

**Solution:**
```bash
# Check resource usage
kubectl top nodes
kubectl top pods -A

# Reduce Kafka broker replicas
kubectl edit kafka my-cluster -n kafka
# Set spec.kafka.replicas: 1

# Reduce Pinot replicas
helm upgrade pinot pinot/pinot -n pinot \
  --set controller.replicaCount=1 \
  --set broker.replicaCount=1 \
  --set server.replicaCount=1

# Reduce Spark batch frequency
python transform/spark_streaming_flattener_cli.py \
  --processing-time "30 seconds"  # Less frequent batches
```

---

### Issue: High Memory Usage

**Problem:** System running out of memory.

**Solution:**
```bash
# Check memory usage
free -h
kubectl top pods -A

# Restart Minikube with less memory
minikube delete
minikube start --cpus=8 --memory=10000  # 10GB instead of 15GB

# Reduce JVM heap sizes
export SPARK_EXECUTOR_MEMORY=2g  # Instead of 4g
export SPARK_DRIVER_MEMORY=1g    # Instead of 2g

# Clear Docker cache
docker system prune -a -f
```

---

## Data Quality Issues

### Issue: Duplicate Records in Iceberg

**Cause:** Spark streaming job restarted without checkpoints, or exactly-once semantics not configured.

**Solution:**
```bash
# Use idempotent writes with watermarking
# Modify Spark job to deduplicate based on trade ID

# Or deduplicate in post-processing
spark-sql
> CREATE OR REPLACE TABLE local.db.flattened_stocks_dedup AS
  SELECT DISTINCT * FROM local.db.flattened_stocks;
```

---

### Issue: Missing Data in Pinot

**Cause:** Pinot consumer lag, or table not configured correctly.

**Solution:**
```bash
# Check Pinot ingestion status
curl http://localhost:9000/tables/flattened_stocks

# Verify Kafka topic has data
kubectl exec -it my-cluster-kafka-0 -n kafka -- \
  bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 \
  --topic flattened_stocks \
  --from-beginning \
  --max-messages 10

# Check Pinot logs
kubectl logs -n pinot -l app=pinot-server

# Restart Pinot
kubectl rollout restart deployment -n pinot
```

---

## General Debug Commands

### Check All Services Status

```bash
# View all pods
kubectl get pods -A

# Check for errors
kubectl get events -A --sort-by='.lastTimestamp' | grep -i error

# Check resource usage
kubectl top nodes
kubectl top pods -A

# Check disk space
minikube ssh
df -h
exit
```

### Collect Logs

```bash
# Kafka logs
kubectl logs -n kafka my-cluster-kafka-0 > kafka.log

# Spark logs (if running as pod)
kubectl logs -n default spark-driver > spark.log

# Pinot logs
kubectl logs -n pinot -l app=pinot-controller > pinot-controller.log
kubectl logs -n pinot -l app=pinot-broker > pinot-broker.log
kubectl logs -n pinot -l app=pinot-server > pinot-server.log

# MinIO logs
kubectl logs -n minio -l app=minio > minio.log
```

### Full System Reset

**WARNING: This deletes all data!**

```bash
# Delete Minikube
minikube delete

# Remove Minikube files
rm -rf ~/.minikube

# Clean Docker
docker system prune -a -f

# Remove MinIO data
rm -rf /mnt/mydrive2/minio

# Reinstall everything
./test_new_2.sh --setup-infra --setup-minikube --setup-kafka --setup-minio --setup-pinot
```

---

## Getting Help

If you're still stuck:

1. **Check logs** - Most issues show up in pod logs
2. **Search GitHub issues** - Someone may have encountered the same problem
3. **Review documentation** - [Setup](SETUP.md), [Pipeline](PIPELINE.md), [Usage](USAGE.md)
4. **Test components individually** - Isolate the failing component
5. **Verify prerequisites** - Ensure hardware/software requirements are met

**Common debug workflow:**
```bash
# 1. Check if all pods are running
kubectl get pods -A

# 2. Check recent events
kubectl get events -A --sort-by='.lastTimestamp' | tail -20

# 3. Check resource usage
kubectl top nodes
kubectl top pods -A

# 4. Check specific pod logs
kubectl logs -n <namespace> <pod-name>

# 5. Describe pod for detailed info
kubectl describe pod -n <namespace> <pod-name>
```

---

## Next Steps

- See **[Setup Guide](SETUP.md)** for installation details
- See **[Pipeline Components](PIPELINE.md)** for component deep dive
- See **[Usage Guide](USAGE.md)** for operational commands
