#!/usr/bin/env python3
"""
Kafka Stream Flattener - CLI Tool

This Spark Structured Streaming application reads JSON arrays from Kafka,
flattens them into individual records, and writes to both Kafka and Iceberg.

Features:
  - Reads and parses JSON arrays from Kafka
  - Flattens nested arrays into individual stock tick records
  - Writes flattened data to destination Kafka topic
  - Writes raw stream data to Iceberg table
  - Auto-creates destination Kafka topic if needed
  - Fully configurable via CLI arguments
  - Multiple output modes for debugging and production

Data Flow:
  1. Read JSON arrays from source Kafka topic
  2. Parse and explode arrays into individual records
  3. Restructure fields (rename 't' to 'timestamp')
  4. Write flattened JSON to destination Kafka topic
  5. Write raw stream to Iceberg table

Requirements:
  - PySpark with Kafka support
  - Iceberg Spark runtime
  - kafka-python (for topic creation)
  - S3-compatible storage (MinIO/AWS S3)

Usage Examples:
  # Run with defaults
  spark-submit spark_streaming_flattener_cli.py

  # Custom topics
  spark-submit spark_streaming_flattener_cli.py \\
    --source-topic raw-stock-data \\
    --dest-topic processed-stock-data

  # Custom Iceberg table
  spark-submit spark_streaming_flattener_cli.py \\
    --iceberg-table analytics_db.stock_ticks

  # Kafka-only mode (no Iceberg)
  spark-submit spark_streaming_flattener_cli.py \\
    --output-mode kafka-only

  # Console debug mode
  spark-submit spark_streaming_flattener_cli.py \\
    --output-mode console-debug

  # High-frequency processing (30 second triggers)
  spark-submit spark_streaming_flattener_cli.py \\
    --processing-time "30 seconds"

Author: Generated with Claude Code
"""

import argparse
import logging
import sys
from dataclasses import dataclass
from typing import Optional, List

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import col, from_json, explode, to_json, struct
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType,
    LongType, ArrayType
)
from pyspark.sql.streaming.query import StreamingQuery

# Import Kafka admin for topic creation
try:
    from kafka.admin import KafkaAdminClient, NewTopic
    from kafka.errors import TopicAlreadyExistsError
    KAFKA_ADMIN_AVAILABLE: bool = True
except ImportError:
    KAFKA_ADMIN_AVAILABLE: bool = False
    logging.warning("kafka-python not available. Topic auto-creation disabled.")


@dataclass
class StreamingConfig:
    """
    Configuration dataclass for Spark streaming application.

    Holds all configuration parameters passed via CLI or defaults.
    """
    # Kafka configuration
    kafka_brokers: str
    source_topic: str
    dest_topic: str
    starting_offsets: str

    # Checkpoint locations
    checkpoint_kafka: str
    checkpoint_iceberg: str

    # Iceberg configuration
    iceberg_table: str
    iceberg_catalog: str
    iceberg_warehouse: str

    # Processing configuration
    processing_time: str

    # S3/MinIO configuration
    s3_endpoint: str
    s3_access_key: str
    s3_secret_key: str

    # Spark configuration
    shuffle_partitions: int
    app_name: str

    # Output configuration
    output_mode: str
    log_level: str


class SchemaDefinitions:
    """
    Defines schemas for parsing Kafka JSON data.

    Stock tick schema matches IEX API format with OHLC data.
    """

    @staticmethod
    def get_stock_tick_schema() -> StructType:
        """
        Define schema for individual stock tick record.

        Fields:
          T: Trade type indicator
          S: Stock symbol (e.g., "AAPL")
          o: Open price
          h: High price
          l: Low price
          c: Close price
          v: Volume (number of shares)
          t: Timestamp (ISO 8601 format)
          n: Number of trades
          vw: Volume weighted average price

        Returns:
            StructType schema for stock tick
        """
        return StructType([
            StructField("T", StringType(), True),
            StructField("S", StringType(), True),
            StructField("o", DoubleType(), True),
            StructField("h", DoubleType(), True),
            StructField("l", DoubleType(), True),
            StructField("c", DoubleType(), True),
            StructField("v", LongType(), True),
            StructField("t", StringType(), True),
            StructField("n", LongType(), True),
            StructField("vw", DoubleType(), True)
        ])

    @staticmethod
    def get_array_schema() -> ArrayType:
        """
        Define schema for JSON array of stock ticks.

        Returns:
            ArrayType schema containing stock tick objects
        """
        return ArrayType(SchemaDefinitions.get_stock_tick_schema())


class KafkaStreamProcessor:
    """
    Processes Kafka streams: reads, transforms, and writes to multiple sinks.

    Handles the complete data pipeline from Kafka source to Kafka/Iceberg sinks.
    """

    def __init__(self, config: StreamingConfig) -> None:
        """
        Initialize the stream processor.

        Args:
            config: StreamingConfig object with all parameters
        """
        self.config: StreamingConfig = config
        self.spark: Optional[SparkSession] = None
        self.logger: logging.Logger = logging.getLogger(__name__)
        self.stock_tick_schema: StructType
        self.array_schema: ArrayType

        # Initialize Spark session
        self._init_spark_session()

        # Get schemas
        self.stock_tick_schema = SchemaDefinitions.get_stock_tick_schema()
        self.array_schema = SchemaDefinitions.get_array_schema()

        self.logger.info("KafkaStreamProcessor initialized successfully")

    def _init_spark_session(self) -> None:
        """
        Initialize Spark session with Kafka, Iceberg, and S3 configurations.

        Configures:
          - Spark packages (Kafka, Iceberg, AWS S3)
          - S3/MinIO connection settings
          - Iceberg catalog configuration
          - Shuffle partitions and case sensitivity
        """
        self.logger.info("Initializing Spark session...")

        # Define required packages
        packages: str = ",".join([
            "org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.9.0",
            "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1",
            "com.amazonaws:aws-java-sdk-bundle:1.12.262",
            "org.apache.hadoop:hadoop-aws:3.3.4"
        ])

        # Build Spark session with all configurations
        self.spark = (SparkSession.builder
            .appName(self.config.app_name)

            # Spark SQL configurations
            .config("spark.sql.shuffle.partitions", str(self.config.shuffle_partitions))
            .config("spark.sql.caseSensitive", "true")

            # Package dependencies
            .config("spark.jars.packages", packages)

            # S3/MinIO connection settings
            .config("spark.hadoop.fs.s3a.endpoint", self.config.s3_endpoint)
            .config("spark.hadoop.fs.s3a.access.key", self.config.s3_access_key)
            .config("spark.hadoop.fs.s3a.secret.key", self.config.s3_secret_key)
            .config("spark.hadoop.fs.s3a.path.style.access", "true")
            .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
            .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
            .config("spark.hadoop.fs.s3a.aws.credentials.provider",
                   "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider")

            # S3 multipart upload settings
            .config("spark.hadoop.fs.s3a.fast.upload", "true")
            .config("spark.hadoop.fs.s3a.multipart.size", "52428800")  # 50MB
            .config("spark.hadoop.fs.s3a.multipart.threshold", "52428800")

            # Iceberg catalog configuration
            .config("spark.sql.extensions",
                   "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
            .config(f"spark.sql.catalog.{self.config.iceberg_catalog}",
                   "org.apache.iceberg.spark.SparkCatalog")
            .config(f"spark.sql.catalog.{self.config.iceberg_catalog}.type", "hadoop")
            .config(f"spark.sql.catalog.{self.config.iceberg_catalog}.warehouse",
                   self.config.iceberg_warehouse)

            .getOrCreate()
        )

        # Set Spark log level
        self.spark.sparkContext.setLogLevel(self.config.log_level)

        self.logger.info(f"Spark session initialized: {self.config.app_name}")

    def create_source_stream(self) -> DataFrame:
        """
        Create streaming DataFrame from Kafka source topic.

        Returns:
            DataFrame representing Kafka source stream
        """
        self.logger.info(f"Creating source stream from topic: {self.config.source_topic}")

        source_df = (self.spark.readStream
            .format("kafka")
            .option("kafka.bootstrap.servers", self.config.kafka_brokers)
            .option("subscribe", self.config.source_topic)
            .option("startingOffsets", self.config.starting_offsets)
            .option("failOnDataLoss", "false")  # Handle data loss gracefully
            .load()
        )

        self.logger.info("Source stream created successfully")
        return source_df

    def parse_and_flatten(self, source_df: DataFrame) -> DataFrame:
        """
        Parse JSON arrays and flatten into individual records.

        Steps:
          1. Cast Kafka value to string (JSON format)
          2. Parse JSON string as array of stock ticks
          3. Explode array into individual rows

        Args:
            source_df: Raw Kafka DataFrame

        Returns:
            Flattened DataFrame with individual stock tick records
        """
        self.logger.info("Parsing and flattening JSON data...")

        # Cast binary Kafka value to JSON string
        json_df = source_df.selectExpr("CAST(value AS STRING) as json_string")

        # Parse JSON array and explode into rows
        flattened_df = (json_df
            .withColumn("data_array", from_json(col("json_string"), self.array_schema))
            .select(explode(col("data_array")).alias("data_struct"))
        )

        self.logger.debug("Flattened schema:")
        flattened_df.printSchema()

        return flattened_df

    def restructure_data(self, flattened_df: DataFrame) -> DataFrame:
        """
        Restructure flattened data for output.

        Renames 't' field to 'timestamp' and reorganizes field order.
        Converts the struct back to JSON string format for Kafka output.

        Args:
            flattened_df: Flattened DataFrame with 'data_struct' column

        Returns:
            DataFrame with 'value' column containing JSON string
        """
        self.logger.info("Restructuring data...")

        # Rename and reorder fields within the struct
        restructured_df = flattened_df.withColumn(
            "data_struct",
            struct(
                col("data_struct").getField("t").alias("timestamp"),  # Rename t -> timestamp
                col("data_struct").getField("T"),
                col("data_struct").getField("o"),
                col("data_struct").getField("h"),
                col("data_struct").getField("l"),
                col("data_struct").getField("c"),
                col("data_struct").getField("v"),
                col("data_struct").getField("n"),
                col("data_struct").getField("vw"),
                col("data_struct").getField("S")
            )
        )

        # Convert struct back to JSON string for Kafka
        output_df = restructured_df.select(
            to_json(col("data_struct")).alias("value")
        )

        return output_df

    def write_to_kafka(self, output_df: DataFrame) -> StreamingQuery:
        """
        Write streaming data to Kafka destination topic.

        Args:
            output_df: DataFrame with 'value' column containing JSON

        Returns:
            Streaming query object
        """
        self.logger.info(f"Writing to Kafka topic: {self.config.dest_topic}")

        query: StreamingQuery = (output_df.writeStream
            .format("kafka")
            .option("kafka.bootstrap.servers", self.config.kafka_brokers)
            .option("topic", self.config.dest_topic)
            .option("checkpointLocation", self.config.checkpoint_kafka)
            .start()
        )

        self.logger.info("Kafka write stream started")
        return query

    def write_to_iceberg(self, source_df: DataFrame) -> StreamingQuery:
        """
        Write raw streaming data to Iceberg table.

        Note: Writes the RAW source stream (before flattening) to Iceberg.

        Args:
            source_df: Raw source DataFrame from Kafka

        Returns:
            Streaming query object
        """
        # Parse database.table format
        full_table_name: str = f"{self.config.iceberg_catalog}.{self.config.iceberg_table}"
        self.logger.info(f"Writing to Iceberg table: {full_table_name}")

        query: StreamingQuery = (source_df.writeStream
            .format("iceberg")
            .outputMode("append")
            .trigger(processingTime=self.config.processing_time)
            .option("checkpointLocation", self.config.checkpoint_iceberg)
            .option("fanout-enabled", "true")
            .option("create-table-if-not-exists", "true")  # Auto-create table
            .toTable(full_table_name)
        )

        self.logger.info("Iceberg write stream started")
        return query

    def write_to_console(self, output_df: DataFrame) -> StreamingQuery:
        """
        Write streaming data to console for debugging.

        Args:
            output_df: DataFrame to display

        Returns:
            Streaming query object
        """
        self.logger.info("Writing to console (debug mode)")

        query: StreamingQuery = (output_df.writeStream
            .outputMode("append")
            .format("console")
            .option("truncate", "false")
            .start()
        )

        return query

    def run(self) -> None:
        """
        Main method to run the streaming pipeline.

        Steps:
          1. Create source stream from Kafka
          2. Parse and flatten JSON arrays
          3. Restructure data
          4. Write to configured sinks (Kafka/Iceberg/Console)
          5. Wait for termination

        Output modes:
          - 'both': Write to both Kafka and Iceberg (default)
          - 'kafka-only': Write only to Kafka
          - 'iceberg-only': Write only to Iceberg
          - 'console-debug': Write to console for debugging
        """
        try:
            self.logger.info("=" * 70)
            self.logger.info("STARTING KAFKA STREAM FLATTENER")
            self.logger.info("=" * 70)
            self.logger.info(f"Source Topic:      {self.config.source_topic}")
            self.logger.info(f"Dest Topic:        {self.config.dest_topic}")
            self.logger.info(f"Iceberg Table:     {self.config.iceberg_catalog}.{self.config.iceberg_table}")
            self.logger.info(f"Output Mode:       {self.config.output_mode}")
            self.logger.info(f"Processing Time:   {self.config.processing_time}")
            self.logger.info("=" * 70)

            # Create source stream
            source_stream: DataFrame = self.create_source_stream()

            # Parse and flatten
            flattened_stream: DataFrame = self.parse_and_flatten(source_stream)

            # Restructure for output
            output_stream: DataFrame = self.restructure_data(flattened_stream)

            # Start appropriate write streams based on output mode
            queries: List[StreamingQuery] = []

            if self.config.output_mode == "both":
                # Write to both Kafka and Iceberg
                kafka_query = self.write_to_kafka(output_stream)
                iceberg_query = self.write_to_iceberg(source_stream)
                queries.extend([kafka_query, iceberg_query])

            elif self.config.output_mode == "kafka-only":
                # Write only to Kafka
                kafka_query = self.write_to_kafka(output_stream)
                queries.append(kafka_query)

            elif self.config.output_mode == "iceberg-only":
                # Write only to Iceberg
                iceberg_query = self.write_to_iceberg(source_stream)
                queries.append(iceberg_query)

            elif self.config.output_mode == "console-debug":
                # Write to console for debugging
                console_query = self.write_to_console(output_stream)
                queries.append(console_query)

            else:
                raise ValueError(f"Invalid output mode: {self.config.output_mode}")

            self.logger.info(f"Started {len(queries)} streaming query/queries")
            self.logger.info("Press Ctrl+C to stop streaming...")

            # Wait for any stream to terminate
            self.spark.streams.awaitAnyTermination()

        except KeyboardInterrupt:
            self.logger.info("\nStreaming job interrupted by user (Ctrl+C)")

        except Exception as e:
            self.logger.error(f"Error in streaming job: {e}", exc_info=True)
            raise

        finally:
            self.stop()

    def stop(self) -> None:
        """
        Stop the Spark session and cleanup resources.
        """
        if self.spark:
            self.logger.info("Stopping Spark session...")
            self.spark.stop()
            self.logger.info("Spark session stopped")


def ensure_topic_exists(brokers: str, topic: str) -> None:
    """
    Ensure Kafka topic exists, creating it if necessary.

    Creates topic with 3 partitions and replication factor 1.
    Only attempts creation if kafka-python is available.

    Args:
        brokers: Kafka bootstrap servers
        topic: Topic name to check/create
    """
    if not KAFKA_ADMIN_AVAILABLE:
        logging.warning("kafka-python not available, skipping topic creation check")
        return

    logger: logging.Logger = logging.getLogger(__name__)

    try:
        # Create admin client
        admin_client: KafkaAdminClient = KafkaAdminClient(
            bootstrap_servers=brokers,
            client_id='spark_flattener_admin'
        )

        # Check if topic exists
        existing_topics: List[str] = admin_client.list_topics()

        if topic in existing_topics:
            logger.info(f"Destination topic '{topic}' already exists")
        else:
            logger.info(f"Creating destination topic '{topic}'...")

            # Create topic with 3 partitions
            new_topic: NewTopic = NewTopic(
                name=topic,
                num_partitions=3,
                replication_factor=1
            )

            admin_client.create_topics(
                new_topics=[new_topic],
                validate_only=False
            )

            logger.info(f"Topic '{topic}' created (partitions=3, replication=1)")

        admin_client.close()

    except TopicAlreadyExistsError:
        logger.info(f"Topic '{topic}' already exists")

    except Exception as e:
        logger.warning(f"Could not check/create topic: {e}")
        logger.warning("Continuing anyway - topic may already exist")


def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.

    Returns:
        Namespace object with parsed arguments
    """
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description='Kafka Stream Flattener - Spark Structured Streaming CLI',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with defaults
  spark-submit %(prog)s

  # Custom topics and table
  spark-submit %(prog)s \\
    --source-topic raw-data \\
    --dest-topic processed-data \\
    --iceberg-table analytics_db.stock_ticks

  # Kafka-only mode
  spark-submit %(prog)s --output-mode kafka-only

  # High-frequency processing
  spark-submit %(prog)s --processing-time "30 seconds"
        """
    )

    # Kafka Configuration
    kafka_group = parser.add_argument_group('Kafka Configuration')
    kafka_group.add_argument(
        '--kafka-brokers',
        default='my-cluster-kafka-bootstrap.kafka.svc.cluster.local:9092',
        help='Kafka bootstrap servers (default: my-cluster-kafka-bootstrap.kafka.svc.cluster.local:9092)'
    )
    kafka_group.add_argument(
        '--source-topic',
        default='iex-topic-1',
        help='Source Kafka topic to read from (default: iex-topic-1)'
    )
    kafka_group.add_argument(
        '--dest-topic',
        default='iex-topic-1-flattened',
        help='Destination Kafka topic to write to (default: iex-topic-1-flattened)'
    )
    kafka_group.add_argument(
        '--starting-offsets',
        default='latest',
        choices=['earliest', 'latest'],
        help='Starting offsets for Kafka consumer (default: latest)'
    )

    # Checkpoint Configuration
    checkpoint_group = parser.add_argument_group('Checkpoint Configuration')
    checkpoint_group.add_argument(
        '--checkpoint-kafka',
        default='s3a://data/chkpt1',
        help='Checkpoint location for Kafka sink (default: s3a://data/chkpt1)'
    )
    checkpoint_group.add_argument(
        '--checkpoint-iceberg',
        default='s3a://data/chkpt-iceberg-2',
        help='Checkpoint location for Iceberg sink (default: s3a://data/chkpt-iceberg-2)'
    )

    # Iceberg Configuration
    iceberg_group = parser.add_argument_group('Iceberg Configuration')
    iceberg_group.add_argument(
        '--iceberg-table',
        default='iex_db.raw_stream_iex_2',
        help='Iceberg table in database.table format (default: iex_db.raw_stream_iex_2)'
    )
    iceberg_group.add_argument(
        '--iceberg-catalog',
        default='my_catalog',
        help='Iceberg catalog name (default: my_catalog)'
    )
    iceberg_group.add_argument(
        '--iceberg-warehouse',
        default='s3a://test2/mywarehouse',
        help='Iceberg warehouse S3 location (default: s3a://test2/mywarehouse)'
    )

    # Processing Configuration
    processing_group = parser.add_argument_group('Processing Configuration')
    processing_group.add_argument(
        '--processing-time',
        default='1 minute',
        help='Processing time trigger for Iceberg (default: "1 minute")'
    )

    # S3/MinIO Configuration
    s3_group = parser.add_argument_group('S3/MinIO Configuration')
    s3_group.add_argument(
        '--s3-endpoint',
        default='http://minio-api.192.168.49.2.nip.io',
        help='S3/MinIO endpoint URL (default: http://minio-api.192.168.49.2.nip.io)'
    )
    s3_group.add_argument(
        '--s3-access-key',
        default='minio',
        help='S3/MinIO access key (default: minio)'
    )
    s3_group.add_argument(
        '--s3-secret-key',
        default='minio123',
        help='S3/MinIO secret key (default: minio123)'
    )

    # Spark Configuration
    spark_group = parser.add_argument_group('Spark Configuration')
    spark_group.add_argument(
        '--shuffle-partitions',
        type=int,
        default=4,
        help='Number of shuffle partitions (default: 4)'
    )
    spark_group.add_argument(
        '--app-name',
        default='KafkaStreamFlattener',
        help='Spark application name (default: KafkaStreamFlattener)'
    )

    # Output Configuration
    output_group = parser.add_argument_group('Output Configuration')
    output_group.add_argument(
        '--output-mode',
        choices=['both', 'kafka-only', 'iceberg-only', 'console-debug'],
        default='both',
        help='Output mode (default: both)'
    )

    # Logging Configuration
    logging_group = parser.add_argument_group('Logging Configuration')
    logging_group.add_argument(
        '--log-level',
        choices=['DEBUG', 'INFO', 'WARN', 'ERROR'],
        default='INFO',
        help='Spark and application log level (default: INFO)'
    )

    return parser.parse_args()


def main() -> None:
    """
    Main entry point for Spark streaming application.

    Parses CLI arguments, validates configuration, creates destination topic,
    and runs the streaming pipeline.
    """
    # Parse arguments
    args: argparse.Namespace = parse_arguments()

    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    logger: logging.Logger = logging.getLogger(__name__)

    # Validate Iceberg table format (must contain database.table)
    if '.' not in args.iceberg_table:
        logger.error(
            "Invalid --iceberg-table format. Must be 'database.table' "
            f"(got: '{args.iceberg_table}')"
        )
        sys.exit(1)

    # Create configuration object
    config: StreamingConfig = StreamingConfig(
        kafka_brokers=args.kafka_brokers,
        source_topic=args.source_topic,
        dest_topic=args.dest_topic,
        starting_offsets=args.starting_offsets,
        checkpoint_kafka=args.checkpoint_kafka,
        checkpoint_iceberg=args.checkpoint_iceberg,
        iceberg_table=args.iceberg_table,
        iceberg_catalog=args.iceberg_catalog,
        iceberg_warehouse=args.iceberg_warehouse,
        processing_time=args.processing_time,
        s3_endpoint=args.s3_endpoint,
        s3_access_key=args.s3_access_key,
        s3_secret_key=args.s3_secret_key,
        shuffle_partitions=args.shuffle_partitions,
        app_name=args.app_name,
        output_mode=args.output_mode,
        log_level=args.log_level
    )

    try:
        # Ensure destination Kafka topic exists (if writing to Kafka)
        if config.output_mode in ['both', 'kafka-only']:
            logger.info("Checking destination Kafka topic...")
            ensure_topic_exists(config.kafka_brokers, config.dest_topic)

        # Create and run stream processor
        processor: KafkaStreamProcessor = KafkaStreamProcessor(config)
        processor.run()

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
