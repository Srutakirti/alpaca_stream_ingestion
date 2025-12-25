import logging
from kafka import KafkaConsumer
from kafka.errors import NoBrokersAvailable

# --- Configuration ---
# 1. Kafka bootstrap servers. Replace with your Kafka broker(s).
KAFKA_BOOTSTRAP_SERVERS = ['192.168.49.2:32100']

# 2. The Kafka topic to consume messages from.
KAFKA_TOPIC = 'iex-topic-1-flattened'
KAFKA_TOPIC = 'iex-topic-1'
# KAFKA_TOPIC = 'stream_test'
# KAFKA_TOPIC ="kstreams-test-1"

# 3. Consumer group ID. Using a group ID allows for offset management.
#    Set to None to be an independent consumer (will always start from the beginning or end).
CONSUMER_GROUP_ID =  None

# 4. Where to start consuming from if no offset is stored for the group.
#    'earliest': Start from the very beginning of the topic. (like --from-beginning)
#    'latest': Start from the most recent message. (default)
AUTO_OFFSET_RESET = 'earliest'

# --- Logging Setup ---
# Suppress noisy INFO logs from the kafka-python library
logging.getLogger('kafka').setLevel(logging.WARNING)

# Configure the root logger for your application's messages
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


def consume_messages():
    """
    Connects to a Kafka topic and prints messages to the console.
    """
    consumer = None
    try:
        # Initialize the KafkaConsumer
        consumer = KafkaConsumer(
            KAFKA_TOPIC,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            group_id=CONSUMER_GROUP_ID,
            auto_offset_reset=AUTO_OFFSET_RESET,
            # The value_deserializer decodes message values from bytes to a UTF-8 string.
            # If your messages are in another format (like JSON), you can adjust this.
            value_deserializer=lambda v: v.decode('utf-8')
        )

        logging.info(f"Listening for messages on topic '{KAFKA_TOPIC}'... Press Ctrl+C to stop.")

        # The consumer is an iterator, so we can loop through it to get messages.
        # This loop will block and wait for new messages.
        for message in consumer:
            # The deserializer has already converted the value to a string.
            print(message.value)

    except NoBrokersAvailable:
        logging.error(f"Could not connect to any Kafka brokers at {KAFKA_BOOTSTRAP_SERVERS}.")
    except KeyboardInterrupt:
        logging.info("Consumer stopped by user.")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")
    finally:
        # Ensure the consumer is closed properly
        if consumer:
            consumer.close()
            logging.info("Kafka consumer closed.")


if __name__ == "__main__":
    consume_messages()