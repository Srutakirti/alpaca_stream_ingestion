import org.apache.spark.sql.SparkSession
import org.apache.spark.sql.functions._
import org.apache.spark.sql.types._

// run with extra_java_options conf from intellijs
object Test {

  // --- Configuration ---
  val KAFKA_BOOTSTRAP_SERVERS = "192.168.49.2:32100"
  val SOURCE_KAFKA_TOPIC = "iex-topic-1"
  val DESTINATION_KAFKA_TOPIC = "iex-topic-1-flattened-latest"
  val CHECKPOINT_LOCATION = "/tmp/spark_checkpoints/kafka_flattener_1"
  val OUTPUT_MODE = "kafka" // change to "console" for debugging
  val STARTING_OFFSETS = "earliest"

  def main(args: Array[String]): Unit = {
    val spark = SparkSession
      .builder()
      .master("local[*]")
      .appName("KafkaStreamFlattener")
      .config("spark.sql.shuffle.partitions", "4")
      .getOrCreate()

    spark.sparkContext.setLogLevel("ERROR")
    spark.conf.set("spark.sql.caseSensitive", "true")

    // --- Schema for the individual JSON object ---
  val jsonObjectSchema = StructType(Array(
    StructField("T", StringType, true),
    StructField("S", StringType, true),
    StructField("o", DoubleType, true),
    StructField("h", DoubleType, true),
    StructField("l", DoubleType, true),
    StructField("c", DoubleType, true),
    StructField("v", LongType, true),
    StructField("t", StringType, true),
    StructField("n", LongType, true),
    StructField("vw", DoubleType, true)
  ))

    // Schema for the incoming JSON array
    val jsonArraySchema = ArrayType(jsonObjectSchema)

    // 1. Read from Kafka
    println(s"Reading from Kafka topic: $SOURCE_KAFKA_TOPIC")
    val sourceStreamDF = spark.readStream
      .format("kafka")
      .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS)
      .option("subscribe", SOURCE_KAFKA_TOPIC)
//      .option("startingOffsets", STARTING_OFFSETS)
      .load()

    // 2. Parse and flatten
    val jsonDF = sourceStreamDF
      .selectExpr("CAST(value AS STRING) as json_string")

    val flattenedDF = jsonDF
      .withColumn("data_array", from_json(col("json_string"), jsonArraySchema))
      .select(explode(col("data_array")).alias("data_struct"))

    flattenedDF.printSchema()

    
      val renamedDF = flattenedDF.withColumn(
        "data_struct",
        struct(
          col("data_struct").getField("t").alias("timestamp"),
          col("data_struct").getField("T"),
          col("data_struct").getField("o"),
          col("data_struct").getField("h"),
          col("data_struct").getField("l"),
          col("data_struct").getField("c"),
          col("data_struct").getField("v"),
          col("data_struct").getField("n"),
          col("data_struct").getField("vw"),
          col("data_struct").getField("S")
        )
      )

    val outputDF = renamedDF
        .select(to_json(col("data_struct")).alias("value"))

    // 3. Write stream
    val query = OUTPUT_MODE.toLowerCase match {
      case "console" =>
        outputDF.writeStream
          .outputMode("append")
          .format("console")
          .option("truncate", "false")
          .start()

      case "kafka" =>
        outputDF.writeStream
          .format("kafka")
          .option("kafka.bootstrap.servers", KAFKA_BOOTSTRAP_SERVERS)
          .option("topic", DESTINATION_KAFKA_TOPIC)
          .option("checkpointLocation", CHECKPOINT_LOCATION)
          .start()

      case _ =>
        throw new IllegalArgumentException(s"Invalid OUTPUT_MODE: '$OUTPUT_MODE'. Use 'kafka' or 'console'.")
    }

    println("Streaming query started. Waiting for termination...")
    query.awaitTermination()
  }
}
