-- pyspark --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.5,org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.8.1 --conf spark.sql.catalog.spark_catalog=org.apache.iceberg.spark.SparkCatalog --conf spark.sql.catalog.spark_catalog.type=hadoop --conf spark.sql.catalog.spark_catalog.warehouse=gs://alpaca-streamer/warehouse_poc

CREATE TABLE spark_catalog.test2.raw_stream (
  key BINARY,
  value BINARY,
  topic STRING,
  partition INT,
  offset BIGINT,
  timestamp TIMESTAMP,
  timestampType INT)
USING iceberg
LOCATION 'gs://alpaca-streamer/warehouse_poc/test2/raw_stream'
TBLPROPERTIES (
  'format' = 'iceberg/parquet',
  'write.parquet.compression-codec' = 'zstd',
  'write.metadata.delete-after-commit.enabled' = 'true',
  'write.metadata.previous-versions-max' = 10);
