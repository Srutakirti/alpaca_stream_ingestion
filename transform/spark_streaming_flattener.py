from pyspark.sql import SparkSession
from pyspark.sql.functions import (
    col, from_json, explode, to_json, struct
)
from pyspark.sql.types import (
    StructType, StructField, StringType, DoubleType, 
    LongType, ArrayType
)
import logging

# Configure logging
logging.basicConfig(level=logging.ERROR)

class KafkaStreamFlattener:
    def __init__(self):
        # Configuration
        self.KAFKA_BOOTSTRAP_SERVERS = "my-cluster-kafka-bootstrap.kafka.svc.cluster.local:9092"
        self.SOURCE_KAFKA_TOPIC = "iex-topic-1"
        self.DESTINATION_KAFKA_TOPIC = "iex-topic-1-flattened"
        self.CHECKPOINT_LOCATION = "s3a://data/chkpt1"
        self.OUTPUT_MODE = "kafka"  # change to "console" for debugging
        self.STARTING_OFFSETS = "earliest"
        
        # Initialize Spark Session
        self.spark = None
        self._init_spark_session()
        
        # Define schemas
        self._define_schemas()
    
    def _init_spark_session(self):
        """Initialize Spark Session with appropriate configurations"""
        self.spark = (SparkSession.builder
                     .master("local[*]")
                     .appName("KafkaStreamFlattener")
                     .config("spark.sql.shuffle.partitions", "4")
                     .config("spark.sql.caseSensitive", "true")
                     .getOrCreate())
        
        # Set log level to ERROR
        self.spark.sparkContext.setLogLevel("INFO")
        
        print("Spark Session initialized successfully")
    
    def _define_schemas(self):
        """Define the JSON schemas for parsing"""
        # Schema for the individual JSON object
        self.json_object_schema = StructType([
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
        
        # Schema for the incoming JSON array
        self.json_array_schema = ArrayType(self.json_object_schema)
        
        print("Schemas defined successfully")
    
    def create_source_stream(self):
        """Create the source stream from Kafka"""
        print(f"Reading from Kafka topic: {self.SOURCE_KAFKA_TOPIC}")
        
        source_stream_df = (self.spark.readStream
                           .format("kafka")
                           .option("kafka.bootstrap.servers", self.KAFKA_BOOTSTRAP_SERVERS)
                           .option("subscribe", self.SOURCE_KAFKA_TOPIC)
                           # .option("startingOffsets", self.STARTING_OFFSETS)  # Commented out like in original
                           .load())
        
        return source_stream_df
    
    def parse_and_flatten(self, source_stream_df):
        """Parse JSON and flatten the data"""
        # Parse the Kafka value as JSON string
        json_df = source_stream_df.selectExpr("CAST(value AS STRING) as json_string")
        
        # Parse JSON array and explode it
        flattened_df = (json_df
                       .withColumn("data_array", from_json(col("json_string"), self.json_array_schema))
                       .select(explode(col("data_array")).alias("data_struct")))
        
        # Print schema for debugging
        print("Flattened DataFrame Schema:")
        flattened_df.printSchema()
        
        return flattened_df
    
    def rename_and_restructure(self, flattened_df):
        """Rename fields and restructure the data"""
        renamed_df = flattened_df.withColumn(
            "data_struct",
            struct(
                col("data_struct").getField("t").alias("timestamp"),
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
        
        # Convert back to JSON for output
        output_df = renamed_df.select(to_json(col("data_struct")).alias("value"))
        
        return output_df
    
    def create_output_stream(self, output_df):
        """Create the output stream based on OUTPUT_MODE"""
        if self.OUTPUT_MODE.lower() == "console":
            query = (output_df.writeStream
                    .outputMode("append")
                    .format("console")
                    .option("truncate", "false")
                    .start())
        elif self.OUTPUT_MODE.lower() == "kafka":
            query = (output_df.writeStream
                    .format("kafka")
                    .option("kafka.bootstrap.servers", self.KAFKA_BOOTSTRAP_SERVERS)
                    .option("topic", self.DESTINATION_KAFKA_TOPIC)
                    .option("checkpointLocation", self.CHECKPOINT_LOCATION)
                    # .option("checkpointLocation", "/tmp/tmp1")
                    .start())
        else:
            raise ValueError(f"Invalid OUTPUT_MODE: '{self.OUTPUT_MODE}'. Use 'kafka' or 'console'.")
        
        return query
    
    def run_streaming_job(self):
        """Main method to run the streaming job"""
        try:
            print("Starting Kafka Stream Flattener...")
            
            # Create source stream
            source_stream = self.create_source_stream()
            
            # Parse and flatten
            flattened_stream = self.parse_and_flatten(source_stream)
            
            # Rename and restructure
            output_stream = self.rename_and_restructure(flattened_stream)
            
            # Create output stream
            query = self.create_output_stream(output_stream)
            
            print("Streaming query started. Waiting for termination...")
            print(f"Output mode: {self.OUTPUT_MODE}")
            print(f"Source topic: {self.SOURCE_KAFKA_TOPIC}")
            if self.OUTPUT_MODE.lower() == "kafka":
                print(f"Destination topic: {self.DESTINATION_KAFKA_TOPIC}")
            
            # Wait for termination
            query.awaitTermination()
            
        except KeyboardInterrupt:
            print("\nStreaming job interrupted by user")
        except Exception as e:
            print(f"Error in streaming job: {str(e)}")
            raise
        finally:
            self.stop()
    
    def stop(self):
        """Stop the Spark session"""
        if self.spark:
            self.spark.stop()
            print("Spark session stopped")

def main():
    """Main function"""
    # You can modify these settings before running
    flattener = KafkaStreamFlattener()
    
    # Uncomment this line to switch to console output for debugging
    # flattener.OUTPUT_MODE = "console"
    
    # Run the streaming job
    flattener.run_streaming_job()

if __name__ == "__main__":
    main()