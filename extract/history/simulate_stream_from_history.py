import json
import time
import logging
from kafka import KafkaProducer
from kafka.errors import KafkaError

# --- Configuration ---
# 1. Path to the source file containing JSON data on each line.
SOURCE_FILE_PATH = '/nvmewd/data/iex/bars.ndjson'

# 2. Kafka topic to send the data to.
KAFKA_TOPIC = 'test-iex'

# 3. Kafka bootstrap servers. Replace with your Kafka broker(s).
KAFKA_BOOTSTRAP_SERVERS = ['192.168.49.2:32100']

# 4. The number of JSON lines to group into a single Kafka message.
BATCH_SIZE = 100

# 5. The delay in seconds after sending each batch. Set to 0 for no delay.
DELAY_SECONDS = 5

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


def send_data_to_kafka(producer, file_path, topic, batch_size, delay):
    """
    Reads a file line by line, batches the data as a JSON array,
    and sends it to a Kafka topic.
    """
    batch = []
    lines_processed = 0
    batches_sent = 0

    try:
        with open(file_path, 'r') as f:
            logging.info(f"Starting to process file: {file_path}")
            for line in f:
                line = line.strip()
                if not line:
                    continue

                try:
                    # Each line is a JSON document, add it to our batch list
                    batch.append(json.loads(line))
                    lines_processed += 1
                except json.JSONDecodeError:
                    logging.warning(f"Skipping invalid JSON line: {line}")
                    continue

                # When the batch reaches the desired size, send it
                if len(batch) >= batch_size:
                    producer.send(topic, value=batch)
                    batches_sent += 1
                    logging.info(f"Sent batch {batches_sent} with {len(batch)} records to topic '{topic}'.")

                    # Clear the batch and wait for the configured delay
                    batch = []
                    if delay > 0:
                        time.sleep(delay)

            # Send any remaining records in the last batch
            if batch:
                producer.send(topic, value=batch)
                batches_sent += 1
                logging.info(f"Sent final batch {batches_sent} with {len(batch)} records to topic '{topic}'.")

        logging.info(f"Finished processing. Total lines: {lines_processed}, Batches sent: {batches_sent}.")

    except FileNotFoundError:
        logging.error(f"Source file not found at: {file_path}")
    except KafkaError as e:
        logging.error(f"Kafka error: {e}")
    except Exception as e:
        logging.error(f"An unexpected error occurred: {e}")


if __name__ == "__main__":
    producer = None
    try:
        # The value_serializer automatically handles converting the Python list to a JSON string and encoding it to bytes.
        producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: json.dumps(v).encode('utf-8'),
            retries=5  # Retry sending on transient errors
        )
        logging.info("Kafka producer created successfully.")

        send_data_to_kafka(
            producer=producer,
            file_path=SOURCE_FILE_PATH,
            topic=KAFKA_TOPIC,
            batch_size=BATCH_SIZE,
            delay=DELAY_SECONDS
        )

    except Exception as e:
        logging.error(f"Failed to initialize Kafka producer: {e}")
    finally:
        if producer:
            # Ensure all buffered messages are sent before exiting
            producer.flush()
            producer.close()
            logging.info("Kafka producer closed.")