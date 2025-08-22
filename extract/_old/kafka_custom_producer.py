import argparse
import json
import time
import random
from kafka import KafkaProducer
from google.cloud import logging as gcp_logging

# GCP logging setup
gcp_client = gcp_logging.Client()
gcp_client.setup_logging()

def produce_message_loop(broker: str, topic: str):
    try:
        # Create Kafka producer
        producer = KafkaProducer(
            bootstrap_servers=broker,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )

        gcp_logger = gcp_client.logger("kafka-producer-logs")
        message_count = 0

        while True:
            # Simulate a dynamic message
            message = {
                "event": "user_signup",
                "user_id": random.randint(1000, 9999),
                "timestamp": time.time()
            }

            # Send message
            producer.send(topic, value=message)
            producer.flush()

            print(f"[{message_count}] Sent: {message}")
            gcp_logger.log_text(f"[{message_count}] Message sent to Kafka topic '{topic}': {message}")

            message_count += 1

            # Sleep every 10 messages
            if message_count % 10 == 0:
                print("Sleeping for 4 seconds...")
                time.sleep(4)

    except Exception as e:
        print(f"Failed to produce message: {e}")
        gcp_logger = gcp_client.logger("kafka-producer-logs")
        gcp_logger.log_text(f"Kafka production error: {e}", severity="ERROR")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Continuously produce messages to Kafka and log to GCP.")
    parser.add_argument("--broker", required=True, help="Kafka broker address (e.g., localhost:9092)")
    parser.add_argument("--topic", required=True, help="Kafka topic name")

    args = parser.parse_args()

    produce_message_loop(args.broker, args.topic)

