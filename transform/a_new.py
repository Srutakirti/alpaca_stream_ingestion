import argparse
from pyspark.sql import SparkSession

def write_batch_to_bq(df, batch_id, bq_table):
    # Cast value to string for BQ compatibility
    bq_df = df.withColumn("value", df["value"].cast("string"))
    bq_df.write \
        .format("bigquery") \
        .option("table", bq_table) \
        .option("writeMethod", "direct") \
        .option("writeAtLeastOnce", "true") \
        .mode("append") \
        .save()
    print(f"Batch {batch_id} written to BigQuery.")

def main(bootstrap_servers, topic, table_path, processing_time, bq_table=None, checkpoint_gcs_location=None, batch_mode=False):
    spark = SparkSession.builder \
        .appName("KafkaToIcebergAndBQStreamer") \
        .config("spark.sql.catalog.spark_catalog", "org.apache.iceberg.spark.SparkCatalog") \
        .config("spark.sql.catalog.spark_catalog.type", "hadoop") \
        .config("spark.sql.catalog.spark_catalog.warehouse", "gs://alpaca-streamer/warehouse_poc") \
        .getOrCreate()

    if batch_mode:
        print("Running in batch mode: reading from Kafka and writing to BigQuery.")
        kafka_df = spark.read \
            .format("kafka") \
            .option("kafka.bootstrap.servers", bootstrap_servers) \
            .option("subscribe", topic) \
            .option("startingOffsets", "earliest") \
            .option("endingOffsets", "latest") \
            .load()
        
        write_batch_to_bq(kafka_df, 0, bq_table)
    else:
        kafka_raw_df = spark.readStream \
            .format("kafka") \
            .option("kafka.bootstrap.servers", bootstrap_servers) \
            .option("subscribe", topic) \
            .option("startingOffsets", "earliest") \
            .load()

        # Write to Iceberg as before
        # (kafka_raw_df.writeStream
        #     .format("iceberg")
        #     .option("checkpointLocation", f"gs://alpaca-streamer/checkpoints/a/{topic}")
        #     .outputMode("append")
        #     .trigger(processingTime=processing_time)
        #     .option("path", f"{table_path}")
        #     .start())

        # Write to BigQuery using foreachBatch
        
        def foreach_batch_function(df, batch_id):
            write_batch_to_bq(df, batch_id, bq_table)

        (kafka_raw_df.writeStream
                .foreachBatch(foreach_batch_function)
                .option("checkpointLocation", checkpoint_gcs_location)
                .trigger(processingTime=processing_time)
                .start())

        spark.streams.awaitAnyTermination()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stream or batch Kafka to Iceberg and/or BigQuery with Spark.")
    parser.add_argument("--bootstrap_servers", required=True, help="Kafka bootstrap servers (e.g. host:port)")
    parser.add_argument("--topic", required=True, help="Kafka topic name")
    parser.add_argument("--table_path", required=True, help="Iceberg table path (e.g. database.table)")
    parser.add_argument("--processing_time", default="4 seconds", help="Processing interval (e.g. '4 seconds')")
    parser.add_argument("--bq_table", help="BigQuery table (project.dataset.table)")
    parser.add_argument("--checkpoint_gcs_location", required=True, help="GCS location for Spark checkpointing")
    parser.add_argument("--batch_mode", action="store_true", help="If set, runs Kafka to BigQuery as a batch job instead of streaming.")

    args = parser.parse_args()

    print(f"bootstrap_servers - {args.bootstrap_servers}")
    print(f"path - {args.table_path}")
    print(f"topic - {args.topic}")
    print(f"processing_time - {args.processing_time}")
    print(f"checkpoint_gcs_location - {args.checkpoint_gcs_location}")
    print(f"bq_table - {args.bq_table}")
    print(f"batch_mode - {args.batch_mode}")

    main(
        bootstrap_servers=args.bootstrap_servers,
        topic=args.topic,
        table_path=args.table_path,
        processing_time=args.processing_time,
        bq_table=args.bq_table,
        checkpoint_gcs_location=args.checkpoint_gcs_location,
        batch_mode=args.batch_mode)