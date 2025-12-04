from pyspark.sql import SparkSession
import pyspark
import os   
import sys

os.environ['PYSPARK_PYTHON'] = sys.executable
os.environ['PYSPARK_DRIVER_PYTHON'] = sys.executable
os.environ['JAVA_HOME'] = "/usr/lib/jvm/java-17-openjdk-amd64"

print("Python executable being used:", sys.executable)
print("java home:", os.environ.get('JAVA_HOME'))

packages=",".join(["org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.9.0",
"org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1",
"com.amazonaws:aws-java-sdk-bundle:1.12.262",
"org.apache.hadoop:hadoop-aws:3.3.4"])

# spark = (SparkSession.builder
#     .appName("KafkaSparkLocal")
#     .master("local[4]")
#     .config("spark.jars.packages", packages) 
#     .config("spark.hadoop.fs.s3a.endpoint", "http://minio-api.192.168.49.2.nip.io")
#     .config("spark.hadoop.fs.s3a.access.key", "minio")
#     .config("spark.hadoop.fs.s3a.secret.key", "minio123")
#     .config("spark.hadoop.fs.s3a.path.style.access", "true")
#     .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
#     .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
#     .config("spark.hadoop.fs.s3a.aws.credentials.provider", 
#             "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider")
    
#     # CRITICAL: Force multipart uploads with small threshold
#     .config("spark.hadoop.fs.s3a.fast.upload", "true")
#     .config("spark.hadoop.fs.s3a.fast.upload.buffer", "disk")  # Use disk buffering
#     .config("spark.hadoop.fs.s3a.multipart.size", "5242880")  # 5MB parts (MinIO safe)
#     .config("spark.hadoop.fs.s3a.multipart.threshold", "5242880")  # Start at 5MB
#     .config("spark.hadoop.fs.s3a.multipart.purge", "true")
#     .config("spark.hadoop.fs.s3a.multipart.purge.age", "86400")
    
#     # Reduce buffer size to avoid 413 errors
#     .config("spark.hadoop.fs.s3a.block.size", "5242880")  # 5MB blocks
#     .config("spark.hadoop.fs.s3a.buffer.dir", "/tmp/spark-s3a")  # Local buffer directory
    
#     # Control Parquet file sizes - VERY IMPORTANT
#     .config("spark.sql.files.maxRecordsPerFile", "50000")  # Smaller files
#     .config("parquet.block.size", "5242880")  # 5MB Parquet blocks
#     .config("spark.sql.parquet.compression.codec", "snappy")  # Better compression
    
#     # Iceberg-specific settings to control file sizes
#     .config("write.parquet.row-group-size-bytes", "5242880")  # 5MB row groups
#     .config("write.target-file-size-bytes", "10485760")  # 10MB target file size
    
#     # S3A performance tuning
#     .config("spark.hadoop.fs.s3a.threads.max", "20")
#     .config("spark.hadoop.fs.s3a.connection.maximum", "100")
#     .config("spark.hadoop.fs.s3a.attempts.maximum", "5")
#     .config("spark.hadoop.fs.s3a.retry.limit", "5")
    
#     .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
#     .config("spark.sql.catalog.my_catalog", "org.apache.iceberg.spark.SparkCatalog")
#     .config("spark.sql.catalog.my_catalog.type", "hadoop")
#     .config("spark.sql.catalog.my_catalog.warehouse", "s3a://test2/mywarehouse")
#     .config("spark.hadoop.mapreduce.fileoutputcommitter.algorithm.version", "2")
#     .getOrCreate()
# )

spark = (SparkSession.builder
    .appName("KafkaSparkLocal")
    .master("local[4]")
    .config("spark.jars.packages", packages) 
    
    # S3A/MinIO connection settings
    .config("spark.hadoop.fs.s3a.endpoint", "http://minio-api.192.168.49.2.nip.io")
    .config("spark.hadoop.fs.s3a.access.key", "minio")
    .config("spark.hadoop.fs.s3a.secret.key", "minio123")
    .config("spark.hadoop.fs.s3a.path.style.access", "true")
    .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
    .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
    .config("spark.hadoop.fs.s3a.aws.credentials.provider", 
            "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider")
    
    # Multipart upload settings (simple for small files)
    .config("spark.hadoop.fs.s3a.fast.upload", "true")
    .config("spark.hadoop.fs.s3a.multipart.size", "52428800")  # 50MB (won't be reached)
    .config("spark.hadoop.fs.s3a.multipart.threshold", "52428800")  # Start multipart at 50MB
    
    # Iceberg catalog configuration
    .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
    .config("spark.sql.catalog.my_catalog", "org.apache.iceberg.spark.SparkCatalog")
    .config("spark.sql.catalog.my_catalog.type", "hadoop")
    .config("spark.sql.catalog.my_catalog.warehouse", "s3a://test2/mywarehouse")
    
    .getOrCreate()
)

create_query="""
CREATE TABLE my_catalog.nyc.taxis
(
  vendor_id bigint,
  trip_id bigint,
  trip_distance float,
  fare_amount double,
  store_and_fwd_flag string
)
PARTITIONED BY (vendor_id);
"""

insert_query = """
INSERT INTO my_catalog.nyc.taxis
VALUES (1, 1000371, 1.8, 15.32, 'N'), (2, 1000372, 2.5, 22.15, 'N'), (2, 1000373, 0.9, 9.01, 'N'), (1, 1000374, 8.4, 42.13, 'Y');
"""
# spark.sql(insert_query)
# spark.sql("select * from my_catalog.nyc.taxis").show()

df = spark.read.format("json").load("/nvmewd/data/iex/bars.ndjson")
df.createOrReplaceTempView("iex_bars")
spark.sql("""
create table my_catalog.iex_db.raw_iex_bars_iceberg_history_1
using iceberg
          as select * from iex_bars
""")