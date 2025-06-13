from google.cloud import storage
from datetime import datetime
import json,time
from confluent_kafka import TopicPartition, KafkaException, Consumer
import logging
from google.cloud import logging as cloud_logging
from google.cloud.logging.handlers import CloudLoggingHandler

client = cloud_logging.Client()
logger = logging.getLogger("my-python-logger")
logger.setLevel(logging.INFO)

handler = CloudLoggingHandler(client, name="test_log_alpaca")
logger.addHandler(handler)
logger.propagate = False


# GCS path details
bucket_name = 'alpaca-streamer'
prefix = 'checkpoints/a/iex_raw_0/offsets/'
topic = 'iex_raw_0'
broker = "instance-20250325-162745:9095" 

def get_latest_offsets_gcs(bucket_name, prefix, topic):
    client = storage.Client()
    bucket = client.bucket(bucket_name)

    # List all blobs under the given prefix
    blobs = list(bucket.list_blobs(prefix=prefix))

    # Filter out only files (not "directories")
    files = [blob for blob in blobs if not blob.name.endswith('/')]

    # Find the newest file (by updated timestamp)
    newest_blob = max(files, key=lambda b: b.updated)

    # Download content
    content: str = newest_blob.download_as_text()

    # ---- Parse file content ----
    lines = [line for line in content.strip().splitlines() if line.strip() != 'v1']
    parsed_jsons = [json.loads(line) for line in lines]

    # First line is metadata, second is offset
    metadata = parsed_jsons[0]
    offsets = parsed_jsons[1]
    print(offsets[topic])
    return offsets[topic]




def get_latest_offsets_kafka(broker, topic):
    # Create a dummy consumer (used only to get metadata and offsets)
    consumer = Consumer({
        'bootstrap.servers': broker,
        'group.id': 'offset-checker',
        'enable.auto.commit': False
    })
    print("consumer inititated")
    try:
        # Get metadata to find all partitions of the topic
        metadata = consumer.list_topics(topic, timeout=10)
        if topic not in metadata.topics:
            raise Exception(f"Topic '{topic}' not found.")

        partitions = metadata.topics[topic].partitions.keys()
        topic_partitions = [TopicPartition(topic, p) for p in partitions]

        print(topic_partitions)
        # Get latest offsets
        latest_offsets = {}

        for tp in topic_partitions:
            low, high = consumer.get_watermark_offsets(tp, timeout=5)
            latest_offsets[str(tp.partition)] = high
        print(latest_offsets)
        return latest_offsets

    finally:
        consumer.close()



while True:
    print("starting log collect")
    latest_gcs_offsets = get_latest_offsets_gcs(bucket_name,prefix,topic)
    latest_kafka_offsets = get_latest_offsets_kafka(broker,topic)

    lag_dict = {}
    
    for partition in latest_kafka_offsets.keys():
        lag = latest_kafka_offsets[partition] - latest_gcs_offsets[partition]
        lag_dict[f"partition_{partition}"] =  lag 
    lag_dict["source"] = "live_alpaca"
    print(json.dumps(lag_dict))
    logger.info(json.dumps(lag_dict))
    
# ✅ Flush and close the handler
    handler.flush()
    handler.close()
    print("sent logs")
    time.sleep(60)

    
