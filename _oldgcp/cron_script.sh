#!/bin/bash
##0 12 * * 1-5 /home/srutakirti_mangaraj_fractal_ai/alpaca_stream_ingestion/cron_script.sh >> /tmp/output_startup_shell.log 2>&1

# Absolute paths
GCLOUD_BIN=/usr/bin/gcloud  # Change if your gcloud is installed elsewhere
SCRIPT_DIR=/home/srutakirti_mangaraj_fractal_ai/alpaca_stream_ingestion  # Change this to your actual script location

$GCLOUD_BIN dataproc batches submit pyspark $SCRIPT_DIR/transform/spark_kafka_to_iceberg.py \
  --region=us-east1 \
  --deps-bucket=gs://alpaca-streamer \
  --service-account=610376955765-compute@developer.gserviceaccount.com \
  --subnet=coe-composer-subnet \
  --version=2.2 \
  --async \
  --properties=^%^spark.jars.packages=org.apache.spark:spark-sql-kafka-0-10_2.13:3.5.1,org.apache.iceberg:iceberg-spark-runtime-3.5_2.13:1.8.1 \
  -- \
  --bootstrap_servers instance-20250325-162745:9095 \
  --topic iex_raw_0 \
  --table_path gs://alpaca-streamer/warehouse_poc/test2/raw_stream \
  --processing_time "60 seconds"
