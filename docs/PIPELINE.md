# Pipeline Components

Deep dive into the data pipeline components: extraction, processing, and storage.

---

## Table of Contents

- [Data Extraction](#data-extraction)
- [Stream Processing](#stream-processing)
- [Storage Layers](#storage-layers)
- [Data Schemas](#data-schemas)

---

## Data Extraction

### 1. WebSocket Producer (Live Alpaca Data)

**Location:** `extract/app/alpaca_ws_updated_conf.py`

Connects to Alpaca's WebSocket API and streams live IEX stock market data to Kafka.

#### Features
- Async WebSocket client using `websockets` library
- Non-blocking Kafka producer (`aiokafka`)
- Batched message production for efficiency
- Graceful shutdown on SIGINT (Ctrl+C)
- Metrics tracking (messages received/sent)
- Cloud logging support (Google Cloud Logging)
- Configurable via YAML file

#### Configuration

Edit `extract/app/config.yaml` or use environment variables:

```yaml
alpaca:
  key: "${ALPACA_KEY}"
  secret: "${ALPACA_SECRET}"
  ws_url: "wss://stream.data.alpaca.markets/v2/iex"

kafka:
  bootstrap_servers: "localhost:9092"
  topic: "iex_data"
  batch_size: 100

symbols:
  - "AAPL"
  - "GOOGL"
  - "MSFT"
  - "AMZN"
  - "TSLA"
```

#### Usage

```bash
# Deploy as Kubernetes pod (automated)
./test_new_2.sh --setup-app

# Or run locally
cd extract/app
python alpaca_ws_updated_conf.py
```

#### Data Format

Messages are sent as JSON arrays:

```json
[
  {
    "T": "t",           // Message type (trade)
    "S": "AAPL",        // Symbol
    "i": 12345,         // Trade ID
    "x": "V",           // Exchange code
    "p": 150.25,        // Price
    "s": 100,           // Size (shares)
    "t": 1699564800000, // Timestamp (Unix ms)
    "c": ["@"],         // Conditions
    "z": "C"            // Tape
  },
  // ... more trades in batch
]
```

---

### 2. Sample Data Generator

**Location:** `minikube/kafka/sample_event_generators/stream_producer_cli.py`

Generates synthetic stock data for testing without Alpaca credentials.

#### Features
- CLI-based configuration
- Non-blocking Kafka producer with callbacks
- Auto-creates Kafka topic if missing
- Configurable symbols, batch size, interval
- Statistics tracking (success rate, throughput)
- Continuous or limited batch generation

#### Usage

```bash
python minikube/kafka/sample_event_generators/stream_producer_cli.py \
  --kafka-brokers localhost:9092 \
  --topic iex_data \
  --symbols AAPL GOOGL MSFT AMZN TSLA \
  --batch-size 100 \
  --interval 2 \
  --batch-count 0 \
  --partitions 3 \
  --replication-factor 1
```

#### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--kafka-brokers` | `localhost:9092` | Kafka broker addresses |
| `--topic` | `iex_data` | Destination Kafka topic |
| `--symbols` | `AAPL GOOGL MSFT` | Stock symbols to generate |
| `--batch-size` | `50` | Records per batch |
| `--interval` | `1` | Seconds between batches |
| `--batch-count` | `0` | Total batches (0 = infinite) |
| `--partitions` | `3` | Topic partitions (if creating) |
| `--replication-factor` | `1` | Replication factor (if creating) |

#### Generated Data

```json
[
  {
    "T": "t",
    "S": "AAPL",
    "i": 52849183745,
    "x": "V",
    "p": 182.45,         // Random price between 100-200
    "s": 150,            // Random size between 1-1000
    "t": 1731408245123,  // Current timestamp
    "c": ["@"],
    "z": "C"
  }
]
```

---

### 3. Historical Data Replay

**Location:** `extract/history/simulate_stream_from_history.py`

Replays historical stock data from CSV files to Kafka.

#### Usage

```bash
cd extract/history
python simulate_stream_from_history.py
```

Useful for backtesting streaming pipelines with real historical data.

---

## Stream Processing

### Spark Streaming Flattener (CLI Tool)

**Location:** `transform/spark_streaming_flattener_cli.py`

The main Spark Structured Streaming job that reads JSON arrays from Kafka, flattens them, and writes to both Kafka and Iceberg.

#### Architecture

```
Kafka (iex_data)
    ↓
Read JSON arrays
    ↓
Parse with from_json()
    ↓
Explode arrays → individual records
    ↓
Rename 't' field to 'timestamp'
    ↓
    ├──→ Write to Kafka (flattened_stocks)
    └──→ Write to Iceberg (local.db.flattened_stocks)
```

#### Features
- Fully typed with Python type hints
- CLI-based configuration
- Multiple output modes (both, kafka-only, iceberg-only, console-debug)
- Auto-creates destination Kafka topic
- Configurable checkpointing
- MinIO/S3 integration for Iceberg storage
- Processing time trigger (micro-batching)

#### Usage

```bash
# Full configuration
python transform/spark_streaming_flattener_cli.py \
  --kafka-brokers localhost:9092 \
  --source-topic iex_data \
  --dest-topic flattened_stocks \
  --checkpoint-kafka /tmp/spark-checkpoints/kafka \
  --checkpoint-iceberg /tmp/spark-checkpoints/iceberg \
  --iceberg-table local.db.flattened_stocks \
  --iceberg-catalog spark_catalog \
  --iceberg-warehouse s3a://warehouse/ \
  --s3-endpoint http://localhost:9000 \
  --s3-access-key minioadmin \
  --s3-secret-key minioadmin \
  --processing-time "10 seconds" \
  --output-mode both \
  --starting-offsets latest
```

#### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `--kafka-brokers` | `localhost:9092` | Kafka broker addresses |
| `--source-topic` | `iex_data` | Source Kafka topic |
| `--dest-topic` | `flattened_stocks` | Destination Kafka topic |
| `--checkpoint-kafka` | `/tmp/checkpoints/kafka` | Kafka checkpoint location |
| `--checkpoint-iceberg` | `/tmp/checkpoints/iceberg` | Iceberg checkpoint location |
| `--iceberg-table` | `local.db.flattened_stocks` | Iceberg table name |
| `--iceberg-catalog` | `spark_catalog` | Iceberg catalog name |
| `--iceberg-warehouse` | `s3a://warehouse/` | S3 warehouse path |
| `--s3-endpoint` | `http://localhost:9000` | MinIO/S3 endpoint |
| `--s3-access-key` | `minioadmin` | S3 access key |
| `--s3-secret-key` | `minioadmin` | S3 secret key |
| `--processing-time` | `10 seconds` | Micro-batch trigger interval |
| `--output-mode` | `both` | Output mode (see below) |
| `--starting-offsets` | `latest` | Kafka starting offsets |

#### Output Modes

- **`both`** (default): Write to both Kafka and Iceberg
- **`kafka-only`**: Only write to destination Kafka topic
- **`iceberg-only`**: Only write to Iceberg table
- **`console-debug`**: Print to console (for debugging)

#### Processing Logic

**Input (Kafka):**
```json
// JSON array as string in Kafka message value
[{"T":"t","S":"AAPL","i":123,"x":"V","p":150.25,"s":100,"t":1699564800000,"c":["@"],"z":"C"}]
```

**Processing Steps:**
1. Read from Kafka as string
2. Parse JSON with `from_json()` using array schema
3. Explode array into individual records using `explode()`
4. Rename field `t` to `timestamp` for clarity
5. Select all fields in flattened format

**Output (Kafka):**
```json
// Individual JSON objects
{"T":"t","S":"AAPL","i":123,"x":"V","p":150.25,"s":100,"timestamp":1699564800000,"c":["@"],"z":"C"}
```

**Output (Iceberg):**
- Parquet files stored in MinIO
- Partitioned by date (derived from timestamp)
- ACID transactions with snapshot isolation

#### Monitoring

While the job is running:

```bash
# View Spark UI
open http://localhost:4040

# Check streaming query metrics:
# - Input Rate (records/sec)
# - Process Rate (records/sec)
# - Batch Duration
# - Trigger Interval
```

#### Checkpoint Management

Checkpoints store streaming state for fault tolerance.

**Reset checkpoints** (start fresh):
```bash
# Stop Spark job first
rm -rf /tmp/spark-checkpoints/kafka
rm -rf /tmp/spark-checkpoints/iceberg

# Restart job - will start from latest offsets
```

**Change starting offsets**:
```bash
# Start from earliest messages in Kafka
python transform/spark_streaming_flattener_cli.py \
  --starting-offsets earliest \
  ...
```

---

## Storage Layers

### 1. Apache Iceberg (Data Lakehouse)

**Purpose:** ACID-compliant table format for historical queries and time-travel.

#### Features
- **ACID Transactions**: Serializable isolation, atomic commits
- **Time-Travel**: Query historical snapshots
- **Schema Evolution**: Add/rename/reorder columns safely
- **Hidden Partitioning**: No need to specify partitions in queries
- **Snapshot Isolation**: Multiple readers/writers without conflicts
- **Storage**: MinIO (S3-compatible object storage)

#### Table Schema

```
root
 |-- T: string (trade type)
 |-- S: string (symbol)
 |-- i: long (trade ID)
 |-- x: string (exchange code)
 |-- p: double (price)
 |-- s: long (size in shares)
 |-- timestamp: long (Unix timestamp in milliseconds)
 |-- c: array<string> (trade conditions)
 |-- z: string (tape)
```

#### Querying Iceberg

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

**Query Examples:**

```sql
-- View latest data
SELECT * FROM local.db.flattened_stocks
ORDER BY timestamp DESC
LIMIT 10;

-- Time-travel query (specific snapshot)
SELECT * FROM local.db.flattened_stocks
VERSION AS OF 123456789;

-- Time-travel query (specific timestamp)
SELECT * FROM local.db.flattened_stocks
TIMESTAMP AS OF '2024-11-01 10:00:00';

-- View table history
SELECT * FROM local.db.flattened_stocks.history;

-- View snapshots
SELECT
  snapshot_id,
  parent_id,
  committed_at,
  operation,
  summary
FROM local.db.flattened_stocks.snapshots;

-- View manifest files
SELECT * FROM local.db.flattened_stocks.files;

-- Aggregate queries
SELECT
  S as symbol,
  COUNT(*) as trade_count,
  AVG(p) as avg_price,
  SUM(s) as total_volume
FROM local.db.flattened_stocks
GROUP BY S
ORDER BY trade_count DESC;
```

#### Iceberg Metadata Operations

```sql
-- Expire old snapshots (cleanup)
CALL spark_catalog.system.expire_snapshots(
  table => 'local.db.flattened_stocks',
  older_than => TIMESTAMP '2024-11-01 00:00:00'
);

-- Remove orphan files
CALL spark_catalog.system.remove_orphan_files(
  table => 'local.db.flattened_stocks'
);

-- Rewrite manifests (optimize metadata)
CALL spark_catalog.system.rewrite_manifests(
  'local.db.flattened_stocks'
);
```

---

### 2. Apache Pinot (Real-time Analytics)

**Purpose:** Low-latency OLAP queries on real-time streaming data.

#### Features
- **Real-time Ingestion**: Sub-second data availability
- **Fast Queries**: Optimized for aggregations and filters
- **Star-Tree Indexes**: Pre-aggregated data for common queries
- **Scalable**: Distributed query execution

#### Accessing Pinot

```bash
# Open Pinot query console
open http://localhost:9000

# Or use Python utility
cd load
python pinot_qeury_display.py
```

#### Query Examples

**In Pinot Console (http://localhost:9000):**

```sql
-- Count trades by symbol
SELECT
  S as symbol,
  COUNT(*) as trade_count
FROM flattened_stocks
GROUP BY S
ORDER BY trade_count DESC
LIMIT 10;

-- Average price by symbol
SELECT
  S as symbol,
  AVG(p) as avg_price,
  MIN(p) as min_price,
  MAX(p) as max_price
FROM flattened_stocks
GROUP BY S;

-- Trades in last hour
SELECT
  S as symbol,
  COUNT(*) as recent_trades
FROM flattened_stocks
WHERE timestamp > now() - 3600000  -- 1 hour in ms
GROUP BY S;

-- Top exchanges by volume
SELECT
  x as exchange,
  SUM(s) as total_volume,
  COUNT(*) as trade_count
FROM flattened_stocks
GROUP BY x
ORDER BY total_volume DESC;

-- Time-series aggregation (1-minute buckets)
SELECT
  S as symbol,
  DATETIMECONVERT(timestamp, '1:MILLISECONDS:EPOCH', '1:MINUTES:EPOCH', '1:MINUTES') as time_bucket,
  AVG(p) as avg_price,
  SUM(s) as volume
FROM flattened_stocks
WHERE S = 'AAPL'
GROUP BY S, time_bucket
ORDER BY time_bucket DESC
LIMIT 60;

-- Price percentiles
SELECT
  S as symbol,
  PERCENTILE50(p) as median_price,
  PERCENTILE90(p) as p90_price,
  PERCENTILE99(p) as p99_price
FROM flattened_stocks
GROUP BY S;
```

#### Pinot Table Configuration

Tables can be created via Pinot console or API. See `load/create.py` for table creation utilities.

**Real-time Table Schema:**
```json
{
  "tableName": "flattened_stocks",
  "tableType": "REALTIME",
  "segmentsConfig": {
    "timeColumnName": "timestamp",
    "timeType": "MILLISECONDS",
    "replication": "1",
    "retentionTimeUnit": "DAYS",
    "retentionTimeValue": "7"
  },
  "ingestionConfig": {
    "streamIngestionConfig": {
      "streamConfigMaps": [
        {
          "realtime.segment.flush.threshold.rows": "50000",
          "stream.kafka.broker.list": "my-cluster-kafka-bootstrap.kafka.svc.cluster.local:9092",
          "stream.kafka.consumer.type": "lowLevel",
          "stream.kafka.topic.name": "flattened_stocks"
        }
      ]
    }
  }
}
```

---

## Data Schemas

### Raw Alpaca IEX Schema (Kafka Source)

**Topic:** `iex_data`

**Format:** JSON array of trade objects

```json
[
  {
    "T": "t",           // string - Message type (always "t" for trade)
    "S": "AAPL",        // string - Stock symbol
    "i": 12345,         // long - Trade ID
    "x": "V",           // string - Exchange code
    "p": 150.25,        // double - Trade price
    "s": 100,           // long - Trade size (shares)
    "t": 1699564800000, // long - Trade timestamp (Unix ms)
    "c": ["@"],         // array<string> - Trade conditions
    "z": "C"            // string - Tape (A, B, C)
  }
]
```

### Flattened Schema (Kafka Destination + Iceberg)

**Topic:** `flattened_stocks`
**Iceberg Table:** `local.db.flattened_stocks`

**Format:** Individual JSON objects (one per trade)

```json
{
  "T": "t",
  "S": "AAPL",
  "i": 12345,
  "x": "V",
  "p": 150.25,
  "s": 100,
  "timestamp": 1699564800000,  // Renamed from 't'
  "c": ["@"],
  "z": "C"
}
```

**Spark Schema:**
```python
StructType([
    StructField("T", StringType(), True),
    StructField("S", StringType(), True),
    StructField("i", LongType(), True),
    StructField("x", StringType(), True),
    StructField("p", DoubleType(), True),
    StructField("s", LongType(), True),
    StructField("timestamp", LongType(), True),
    StructField("c", ArrayType(StringType()), True),
    StructField("z", StringType(), True)
])
```

### Field Descriptions

| Field | Type | Description | Example |
|-------|------|-------------|---------|
| `T` | string | Message type | `"t"` (trade) |
| `S` | string | Stock symbol | `"AAPL"` |
| `i` | long | Trade ID (unique) | `52849183745` |
| `x` | string | Exchange code | `"V"` (IEX), `"Q"` (NASDAQ) |
| `p` | double | Trade price (USD) | `150.25` |
| `s` | long | Trade size (shares) | `100` |
| `timestamp` | long | Unix timestamp (ms) | `1699564800000` |
| `c` | array<string> | Trade conditions | `["@", "T"]` |
| `z` | string | Tape (market tier) | `"A"`, `"B"`, `"C"` |

**Exchange Codes:**
- `V` = IEX
- `Q` = NASDAQ
- `N` = NYSE
- `Z` = BATS

**Tape Codes:**
- `A` = NYSE stocks
- `B` = NYSE Arca/American stocks
- `C` = NASDAQ stocks

---

## Next Steps

- See **[Usage Guide](USAGE.md)** for operational commands and examples
- See **[Troubleshooting](TROUBLESHOOTING.md)** for common issues
