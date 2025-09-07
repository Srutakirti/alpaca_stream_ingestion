from pyspark.sql import SparkSession

# ========= CONFIGURATION =========
MINIO_ENDPOINT   = "minio-api.192.168.49.2.nip.io"  # ingress or nodeport
MINIO_ACCESS_KEY = "minio"                       # replace with your key
MINIO_SECRET_KEY = "minio123"                       # replace with your secret
BUCKET_NAME      = "test2"                       # must exist already
OUTPUT_PATH      = f"s3a://{BUCKET_NAME}/sample_data_1" # S3A URI
# =================================

# Create Spark session with Hadoop S3A connector configs
spark = (
    SparkSession.builder
    .appName("WriteToMinIO")
    # .config("spark.jars.packages",
    #         "org.apache.hadoop:hadoop-aws:3.3.4,"
    #         "com.amazonaws:aws-java-sdk-bundle:1.12.262")
    # .config("spark.hadoop.fs.s3a.endpoint", MINIO_ENDPOINT)
    # .config("spark.hadoop.fs.s3a.access.key", MINIO_ACCESS_KEY)
    # .config("spark.hadoop.fs.s3a.secret.key", MINIO_SECRET_KEY)
    # .config("spark.hadoop.fs.s3a.path.style.access", "true")
    # .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
    # .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
    # .config("spark.hadoop.fs.s3a.aws.credentials.provider", "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider")
    .getOrCreate()
)

# Sample DataFrame
data = [(1, "Alice"), (2, "Bob"), (3, "Charlie")]
df = spark.createDataFrame(data, ["id", "name"])

# Write as Parquet
df.write.mode("overwrite").parquet(OUTPUT_PATH)

print(f"✅ Sample data written successfully to {OUTPUT_PATH}")

# Read back to verify
df_read = spark.read.parquet(OUTPUT_PATH)
df_read.show()

spark.stop()
