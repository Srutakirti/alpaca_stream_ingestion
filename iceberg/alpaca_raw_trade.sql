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
