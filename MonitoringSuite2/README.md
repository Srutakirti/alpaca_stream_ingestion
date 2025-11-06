# Monitoring Suite 2.0

A production-ready monitoring application for tracking data pipeline progress across Kafka, Spark Streaming, and Apache Pinot.

## Features

✅ **Multi-Pipeline Support** - Monitor multiple data flows simultaneously
✅ **Lag Calculation** - Real lag metrics, not just message deltas
✅ **Partition-Level Visibility** - Detect lagging partitions
✅ **Retry Logic** - Resilient to transient failures with exponential backoff
✅ **Configuration Management** - YAML-based config with environment variable overrides
✅ **Graceful Shutdown** - Proper resource cleanup on termination
✅ **Structured Logging** - SLF4J + Log4j2 with file rotation
✅ **Unit Tested** - Core components covered by unit tests

## Architecture

Monitors the complete data pipeline flow:

```
Kafka Source Topic → Spark Streaming → Kafka Sink Topic → Pinot Real-time Table
        ↓                   ↓                  ↓                    ↓
   [Monitor]          [Monitor]          [Monitor]            [Monitor]
```

### Metrics Tracked

- **Lag Metrics**:
  - Spark Lag: How far Spark is behind the source Kafka topic
  - Pinot Lag: How far Pinot is behind the sink Kafka topic

- **Throughput Metrics**:
  - Messages moved in source topic (last interval)
  - Messages processed by Spark
  - Messages moved in sink topic
  - Messages ingested by Pinot

- **Partition-Level Analysis**:
  - Per-partition lag calculation
  - Detection of lagging partitions (outliers)

## Requirements

- Java 17+
- Gradle 7.0+
- Access to:
  - Kafka cluster
  - MinIO/S3 (for Spark checkpoints)
  - Pinot controller

## Quick Start

### 1. Build the Project

```bash
./gradlew build
```

### 2. Configure Monitoring

Edit `src/main/resources/monitoring-config.yaml`:

```yaml
kafka:
  bootstrapServers: "192.168.49.2:32100"

minio:
  endpoint: "http://minio-api.192.168.49.2.nip.io"
  accessKey: "minio"
  secretKey: "minio123"

pinot:
  controllerUrl: "http://localhost:9000/tables/"

monitoring:
  intervalSeconds: 30
  maxRetries: 3
  retryBackoffMs: 1000
  requestTimeoutMs: 10000

pipelines:
  - name: "stock-ticks-pipeline"
    sourceKafkaTopic: "iex-topic-1"
    sinkKafkaTopic: "iex-topic-1-flattened"
    sparkCheckpointPath: "chkpt1/offsets/"
    sparkCheckpointBucket: "data"
    pinotTable: "stock_ticks_latest_1_REALTIME"
    enabled: true
```

### 3. Run the Application

```bash
./gradlew run
```

Or using the fat JAR:

```bash
./gradlew fatJar
java -jar build/libs/MonitoringSuite2-2.0.0-all.jar
```

## Configuration

### YAML Configuration

Configuration is loaded from `monitoring-config.yaml` in the following order:
1. External file specified via `-Dconfig.file=/path/to/config.yaml`
2. File in current directory: `./monitoring-config.yaml`
3. Classpath resource: `/monitoring-config.yaml`

### Environment Variable Overrides

Override any configuration using environment variables:

```bash
# Kafka settings
export MONITORING_KAFKA_BOOTSTRAPSERVERS="localhost:9092"

# MinIO settings
export MONITORING_MINIO_ENDPOINT="http://localhost:9000"
export MONITORING_MINIO_ACCESSKEY="admin"
export MONITORING_MINIO_SECRETKEY="password"

# Pinot settings
export MONITORING_PINOT_CONTROLLERURL="http://localhost:9000/tables/"

# Monitoring settings
export MONITORING_MONITORING_INTERVALSECONDS="60"
export MONITORING_MONITORING_MAXRETRIES="5"
```

### Multiple Pipelines

Add multiple pipelines to the configuration:

```yaml
pipelines:
  - name: "pipeline-1"
    sourceKafkaTopic: "source-1"
    sinkKafkaTopic: "sink-1"
    sparkCheckpointPath: "chkpt1/offsets/"
    sparkCheckpointBucket: "data"
    pinotTable: "table_1_REALTIME"
    enabled: true

  - name: "pipeline-2"
    sourceKafkaTopic: "source-2"
    sinkKafkaTopic: "sink-2"
    sparkCheckpointPath: "chkpt2/offsets/"
    sparkCheckpointBucket: "data"
    pinotTable: "table_2_REALTIME"
    enabled: true
```

## Output Example

```
================================================================================
Pipeline Monitoring Report - 2025-11-05 12:00:00
================================================================================

--------------------------------------------------------------------------------
Pipeline: stock-ticks-pipeline
--------------------------------------------------------------------------------

  LAG SUMMARY:
    Spark Lag:            150 messages (behind source topic)
    Pinot Lag:            100 messages (behind sink topic)

  THROUGHPUT (last 30s):
    Source Topic:       1,250 messages
    Spark Processed:    1,200 messages
    Sink Topic:         1,180 messages
    Pinot Ingested:     1,150 messages

  TOTAL OFFSETS:
    Source Topic:     125,450
    Spark Consumed:   125,300
    Sink Topic:       118,200
    Pinot Consumed:   118,100

  [WARNING] Lagging Partitions for Spark:
    Partition 2 [Spark]: source=50000, consumer=48000, lag=2000
```

## Project Structure

```
MonitoringSuite2/
├── src/main/java/org/depipeline/monitoring/
│   ├── MonitoringApplication.java      # Main application
│   ├── config/
│   │   ├── ConfigLoader.java           # YAML config loader
│   │   ├── MonitoringConfig.java       # Config data classes
│   │   └── PipelineConfig.java         # Pipeline config
│   ├── monitor/
│   │   ├── OffsetMonitor.java          # Monitor interface
│   │   ├── KafkaOffsetMonitor.java     # Kafka monitoring
│   │   ├── SparkOffsetMonitor.java     # Spark monitoring
│   │   └── PinotOffsetMonitor.java     # Pinot monitoring
│   ├── metrics/
│   │   ├── PipelineLagMetrics.java     # Lag metrics calculation
│   │   └── PartitionLagAnalyzer.java   # Partition analysis
│   └── util/
│       └── RetryHelper.java            # Retry logic utility
└── src/test/java/                      # Unit tests
```

## Testing

Run all tests:

```bash
./gradlew test
```

Run specific test:

```bash
./gradlew test --tests PipelineLagMetricsTest
```

## Logging

Logs are written to:
- Console: INFO level and above
- File: `logs/monitoring.log` (rotated daily, max 10 files, 100MB each)

Configure logging in `src/main/resources/log4j2.xml`.

## Graceful Shutdown

The application handles SIGTERM and SIGINT signals:

```bash
# Send SIGTERM
kill <pid>

# Or Ctrl+C
^C
```

All resources (Kafka clients, HTTP clients) are properly closed.

## Improvements Over Original

| Feature | Original | MonitoringSuite2 |
|---------|----------|------------------|
| Configuration | Hardcoded | YAML + env overrides |
| Resource Management | Leaked resources | AutoCloseable, proper cleanup |
| Multi-pipeline | Single pipeline | Multiple pipelines |
| Metrics | Deltas only | Lag + deltas + partition analysis |
| Error Handling | Basic try-catch | Retry with exponential backoff |
| Logging | System.out | SLF4J + Log4j2 with rotation |
| Shutdown | Infinite loop | Graceful shutdown hook |
| Testing | None | Unit tests |
| Topic Hardcoding | Hardcoded in code | Configurable per pipeline |

## Troubleshooting

### Configuration not found

```
ERROR: Configuration file not found: monitoring-config.yaml
```

**Solution**: Ensure `monitoring-config.yaml` is in the classpath or specify path:
```bash
java -Dconfig.file=/path/to/monitoring-config.yaml -jar app.jar
```

### Connection timeout

```
ERROR: Failed to get offsets for topic: iex-topic-1
```

**Solution**:
- Check Kafka/MinIO/Pinot are running and accessible
- Verify network connectivity
- Increase `requestTimeoutMs` in config

### Missing checkpoint files

```
WARN: No checkpoint files found at path: chkpt1/offsets/
```

**Solution**:
- Verify Spark Structured Streaming is running and writing checkpoints
- Check MinIO bucket and path configuration
- Ensure Spark checkpoint location matches config

## License

Internal use only.

## Support

For issues or questions, contact the Data Engineering team.
