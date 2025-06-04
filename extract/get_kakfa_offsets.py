from confluent_kafka import TopicPartition, KafkaException, Consumer


def get_latest_offsets(broker, topic):
    # Create a dummy consumer (used only to get metadata and offsets)
    consumer = Consumer({
        'bootstrap.servers': broker,
        'group.id': 'offset-checker',
        'enable.auto.commit': False
    })

    try:
        # Get metadata to find all partitions of the topic
        metadata = consumer.list_topics(topic, timeout=10)
        if topic not in metadata.topics:
            raise Exception(f"Topic '{topic}' not found.")

        partitions = metadata.topics[topic].partitions.keys()
        topic_partitions = [TopicPartition(topic, p) for p in partitions]

        # Get latest offsets
        end_offsets = consumer.get_watermark_offsets
        latest_offsets = {}

        for tp in topic_partitions:
            low, high = consumer.get_watermark_offsets(tp, timeout=5)
            latest_offsets[tp.partition] = high

        return latest_offsets

    finally:
        consumer.close()


# === USAGE ===
if __name__ == "__main__":
    broker = "instance-20250325-162745:9095"  # Change to your Kafka broker
    topic = "iex_raw_0"          # Change to your topic

    offsets = get_latest_offsets(broker, topic)
    print(f"Latest offsets for topic '{topic}':")
    for partition, offset in offsets.items():
        print(f"Partition {partition}: Offset {offset}")
