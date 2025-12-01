from pyspark.sql import SparkSession


spark = (SparkSession.builder \
        .appName("iceberg_cleanup") 
        .config("spark.sql.catalog.spark_catalog", "org.apache.iceberg.spark.SparkCatalog") 
        .config("spark.sql.catalog.spark_catalog.type", "hadoop") 
        .config("spark.sql.catalog.spark_catalog.warehouse", "gs://alpaca-streamer/warehouse_poc") 
        .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")   
        .getOrCreate() )

spark.sql("CALL  spark_catalog.system.rewrite_data_files('spark_catalog.test2.raw_stream')")