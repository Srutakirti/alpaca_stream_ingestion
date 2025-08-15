from pyspark.sql import SparkSession
from pyspark.sql.functions import expr

# Create SparkSession with Kafka support
spark = SparkSession.builder \
    .appName("PySpark Kafka Producer") \
    .getOrCreate()

# Sample data to send to Kafka
data = [
    ("1", "hello kafka"),
    ("2", "structured streaming"),
    ("3", "from pyspark")
]

# Create DataFrame with key and value columns
df = spark.createDataFrame(data, ["key", "value"])

# Cast key and value to STRING type (required by Kafka sink)
df = df.selectExpr("CAST(key AS STRING) as key", "CAST(value AS STRING) as value")

# Write to Kafka topic "iex-topic"
df = spark.read \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "my-cluster-kafka-bootstrap.kafka.svc.cluster.local:9092") \
    .option("subscribe", "iex-topic") \
    .load()
df.show()
df.count()

spark.stop()
