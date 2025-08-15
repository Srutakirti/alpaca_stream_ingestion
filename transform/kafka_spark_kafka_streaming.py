import logging
from pyspark.sql import SparkSession
from pyspark.sql.functions import from_json, to_json, col, explode
from pyspark.sql.types import StructType, StructField, StringType, DoubleType, LongType, ArrayType

# --- Configuration ---
# 1. Kafka bootstrap servers. Replace with your Kafka broker(s).
KAFKA_BOOTSTRAP_SERVERS = '192.168.49.2:32100'

# 2. The source topic containing arrays of JSON objects.
SOURCE_KAFKA_TOPIC = 'test-iex'

# 3. The destination topic to write flattened, individual JSON objects to.
DESTINATION_KAFKA_TOPIC = 'test-iex-consumer'

# 4. A directory for Spark to save checkpointing information.
#    This must be a path on a distributed file system like HDFS or S3 in a real cluster.
#    For local testing, a local path is fine.
CHECKPOINT_LOCATION = '/tmp/spark_checkpoints/kafka_flattener'

# 5. Define the output mode for the stream.
#    'kafka': Write to the destination Kafka topic.
#    'console': Write to the console for testing and debugging.
OUTPUT_MODE = 'kafka'  # Change to 'kafka' for production

STARTING_OFFSETS = 'earliest'  # Start from the earliest message in the topic

# --- Logging Setup ---
# Suppress verbose Spark logs for better readability
logging.getLogger('py4j').setLevel(logging.WARNING)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


def process_kafka_stream(spark):
    """
    Sets up and runs the Spark Structured Streaming job.
    """
    try:
        # Define the schema for the individual JSON objects inside the array
        json_object_schema = StructType([
            StructField("c", DoubleType(), True),
            StructField("h", DoubleType(), True),
            StructField("l", DoubleType(), True),
            StructField("n", LongType(), True),
            StructField("o", DoubleType(), True),
            StructField("t", StringType(), True),
            StructField("v", LongType(), True),
            StructField("vw", DoubleType(), True),
            StructField("symbol", StringType(), True)
        ])

        # Define the schema for the incoming Kafka message value (an array of the above objects)
        json_array_schema = ArrayType(json_object_schema)

        # 1. Read messages from the source Kafka topic
        logging.info(f"Reading from Kafka topic: {SOURCE_KAFKA_TOPIC}")
        source_stream_df = spark \
            .readStream \
            .format("kafka") \
            .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
            .option("subscribe", SOURCE_KAFKA_TOPIC) \
            .option("startingOffsets", STARTING_OFFSETS) \
            .load()

        # 2. Flatten the messages
        # First, cast the binary 'value' column from Kafka into a string
        json_df = source_stream_df.selectExpr("CAST(value AS STRING) as json_string")

        # Parse the JSON string into an array of structs, then explode the array
        # to create a new row for each JSON object in the array.
        flattened_df = json_df \
            .withColumn("data_array", from_json(col("json_string"), json_array_schema)) \
            .select(explode(col("data_array")).alias("data_struct"))

        # Convert the struct column back into a JSON string to be used as the value
        # for the outgoing Kafka message.
        output_df = flattened_df.select(to_json(col("data_struct")).alias("value"))

        # 3. Write the stream based on the configured OUTPUT_MODE
        logging.info(f"Output mode set to: '{OUTPUT_MODE}'")
        if OUTPUT_MODE.lower() == 'console':
            # Writing to console for debugging purposes
            query = output_df \
                .writeStream \
                .outputMode("append") \
                .format("console") \
                .option("truncate", "false") \
                .start()
        elif OUTPUT_MODE.lower() == 'kafka':
            # Writing to the destination Kafka topic
            query = output_df \
                .writeStream \
                .format("kafka") \
                .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS) \
                .option("topic", DESTINATION_KAFKA_TOPIC) \
                .option("checkpointLocation", CHECKPOINT_LOCATION) \
                .start()
        else:
            raise ValueError(f"Invalid OUTPUT_MODE: '{OUTPUT_MODE}'. Supported modes are 'kafka' or 'console'.")

        logging.info("Streaming query started. Waiting for termination...")
        query.awaitTermination()

    except Exception as e:
        logging.error(f"An error occurred during the streaming process: {e}", exc_info=True)


if __name__ == "__main__":
    # Initialize Spark Session
    spark_session = SparkSession \
        .builder \
        .config("spark.sql.shuffle.partitions", "4") \
        .config("spark.jars.packages", "org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1") \
        .appName("KafkaStreamFlattener") \
        .getOrCreate()

    # Set Spark's logging level to ERROR to reduce console noise
    spark_session.sparkContext.setLogLevel("ERROR")

    process_kafka_stream(spark_session)