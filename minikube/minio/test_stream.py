from pyspark.sql import SparkSession
from pyspark.sql.functions import expr

# -------------------------
# Create Spark session
# -------------------------
spark = SparkSession.builder \
    .appName("NoOpStreaming") \
    .getOrCreate()

# -------------------------
# Create an empty streaming source
# -------------------------
# We'll use the "rate" source which generates a row every second
# But we won't do anything meaningful with it
streaming_df = spark.readStream.format("rate").option("rowsPerSecond", 1).load()

# Apply a dummy transformation
noop_df = streaming_df.select(expr("value AS dummy"))

# -------------------------
# Write to an in-memory sink
# -------------------------
query = noop_df.writeStream \
    .format("memory") \
    .queryName("noop_stream") \
    .outputMode("append") \
    .start()

print("✅ No-op Spark Streaming app started. Press Ctrl+C to stop.")

# Keep the app running indefinitely
query.awaitTermination()
