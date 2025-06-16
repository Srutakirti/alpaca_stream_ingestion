import argparse
from pyspark.sql import SparkSession
from pyspark.sql.functions import col

#gcloud dataproc jobs submit pyspark transform/spark_kafka_to_iceberg.py --cluster alpaca-streamer --async --region us-east1 --properties=^%^spark.jars.packages=org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.5,org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.8.1 -- --bootstrap_servers instance-20250325-162745:9095 --topic iex_raw_0 --table_path gs://alpaca-streamer/warehouse_poc/test2/raw_stream --processing_time "60 seconds"

def main(bootstrap_servers, topic, table_path, processing_time,checkpoint_gcs_location,bq_table):
    spark = SparkSession.builder \
        .appName("KafkaToIcebergStreamer") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.iceberg.spark.SparkCatalog") \
        .config("spark.sql.catalog.spark_catalog.type", "hadoop") \
        .config("spark.sql.catalog.spark_catalog.warehouse", "gs://alpaca-streamer/warehouse_poc") \
        .getOrCreate()

    kafka_raw_df = spark.readStream \
        .format("kafka") \
        .option("kafka.bootstrap.servers", bootstrap_servers) \
        .option("subscribe", topic) \
        .option("startingOffsets", "earliest") \
        .load()

    # (kafka_raw_df.writeStream
    #     .format("iceberg")
    #     #f"gs://alpaca-streamer/checkpoints/a/{topic}"
    #     .option("checkpointLocation", checkpoint_gcs_location )
    #     .outputMode("append")
    #     .trigger(processingTime=processing_time)
    #     .option("path", f"{table_path}")  # Use Iceberg table identifier
    #     .start()
    #     .awaitTermination())

    def write_to_bq(batch_df, batch_id):
        batch_df = batch_df.withColumn("value", col("value").cast("string"))
        (batch_df.write
            .format("bigquery")
            .option("table", bq_table)
            .option("writeMethod", "direct")
            .option("writeAtLeastOnce", "true")
            # .option("temporaryGcsBucket", spark_temp_bucket)
            .mode("append")
            .save()
        )

    (kafka_raw_df.writeStream
        .foreachBatch(write_to_bq)
        .option("checkpointLocation", checkpoint_gcs_location)
        .trigger(processingTime=processing_time)
        .start()
        .awaitTermination())

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stream Kafka to Iceberg with Spark Structured Streaming.")
    parser.add_argument("--bootstrap_servers", required=True, help="Kafka bootstrap servers (e.g. host:port)")
    parser.add_argument("--topic", required=True, help="Kafka topic name")
    parser.add_argument("--table_path", required=True, help="Iceberg table path (e.g. database.table)")
    parser.add_argument("--processing_time", default="4 seconds", help="Processing interval (e.g. '4 seconds')")
    parser.add_argument("--checkpoint_gcs_location", required=True, help="GCS location for Spark checkpointing")
    parser.add_argument("--bq_table", required=True, help="BigQuery table to write to (e.g. project.dataset.table)")

    args = parser.parse_args()
    
    print(f"bootstrap_servers - {args.bootstrap_servers}")
    print(f"path - {args.table_path}")
    print(f"topic - {args.topic}")
    print(f"processing_time - {args.processing_time}")
    print(f"checkpoint_gcs_location - {args.checkpoint_gcs_location}")
    print(f"bq_table - {args.bq_table}")

    main(
        bootstrap_servers=args.bootstrap_servers,
        topic=args.topic,
        table_path=args.table_path,
        processing_time=args.processing_time,
        checkpoint_gcs_location=args.checkpoint_gcs_location,
        bq_table=args.bq_table
    )

