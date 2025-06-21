import argparse
from pyspark.sql import SparkSession
from conf_reader import Config


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

def main(processing_time, conf: Config, bq_table=None, batch_mode=False):
    spark = SparkSession.builder \
        .appName(conf.get('spark.app_name')) \
        .config("spark.sql.catalog.spark_catalog", conf.get("spark.spark_catalog")) \
        .config("spark.sql.catalog.spark_catalog.type", conf.get('spark.spark_catalog_type')) \
        .config("spark.sql.catalog.spark_catalog.warehouse", f"gs://{conf.get('gcp.storage.bucket')}/{conf.get('gcp.storage.warehouse_prefix')}") \
        .getOrCreate()

    if batch_mode:
        print("Running in batch mode: reading from Kafka and writing to BigQuery.")
        kafka_df = spark.read \
            .format("kafka") \
            .option("kafka.bootstrap.servers", conf.get('kafka.bootstrap_servers')) \
            .option("subscribe", conf.get('kafka.topics')) \
            .option("startingOffsets", "earliest") \
            .option("endingOffsets", "latest") \
            .load()
        
        write_batch_to_bq(kafka_df, 0, bq_table)
    else:
        kafka_raw_df = spark.readStream \
            .format("kafka") \
            .option("kafka.bootstrap.servers", conf.get('kafka.bootstrap_servers')) \
            .option("subscribe", conf.get('kafka.topics')) \
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
                .option("checkpointLocation", f"gs://{conf.get('gcp.bucket')}/{conf.get('gcp.checkpoints_prefix')}/{conf.get('kafka.topics')}")
                .trigger(processingTime=processing_time)
                .start())

        spark.streams.awaitAnyTermination()

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Stream or batch Kafka to Iceberg and/or BigQuery with Spark.")
    parser.add_argument("--processing_time", default="4 seconds", help="Processing interval (e.g. '4 seconds')")
    parser.add_argument("--bq_table", help="BigQuery table (project.dataset.table)")
    parser.add_argument("--batch_mode", action="store_true", help="If set, runs Kafka to BigQuery as a batch job instead of streaming.")

    args = parser.parse_args()
    config = Config('config/config.yaml')


    print(f"processing_time - {args.processing_time}")
    print(f"bq_table - {args.bq_table}")
    print(f"batch_mode - {args.batch_mode}")

    main(
        processing_time=args.processing_time,
        bq_table=args.bq_table,
        batch_mode=args.batch_mode,
        conf=config)