import subprocess
import time
import datetime

def run_commands():
    # Get today's date in YYYYMMDD format
    today = datetime.date.today().strftime('%Y%m%d')

    log1 = f"/tmp/output_alpaca_producer_{today}.log"
    log2 = f"/tmp/output_offset_checker_{today}.log"

    # Command 1: Alpaca producer with init.sh sourcing and nohup
    cmd1 = f'''bash -c 'source init.sh && nohup uv run python extract/kafka_alpaca_producer_ws.py >> {log1} 2>&1 &' '''
    subprocess.Popen(cmd1, shell=True)
    time.sleep(2)

    # Command 2: Offset checker with nohup
    cmd2 = f'''nohup uv run extract/compare_spark_kafka_offsets.py >> {log2} 2>&1 &'''
    subprocess.Popen(cmd2, shell=True)
    time.sleep(2)

    # Command 3: Spark batch submission (no nohup needed)
    cmd3 = '''gcloud dataproc batches submit pyspark transform/spark_kafka_to_iceberg.py \
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
--processing_time "60 seconds"'''
    subprocess.Popen(cmd3, shell=True)

if __name__ == "__main__":
    run_commands()
