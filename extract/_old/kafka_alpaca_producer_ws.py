import asyncio
import websockets
import json
import logging
import signal
import sys
import os
from aiokafka import AIOKafkaProducer
import google.cloud.logging
from google.cloud.logging_v2.handlers import CloudLoggingHandler
from google.cloud.logging_v2.handlers.transports.background_thread import BackgroundThreadTransport

# Kafka configuration
KAFKA_TOPIC = "iex_raw_0"
KAFKA_BOOTSTRAP_SERVERS = "instance-20250325-162745:9095"

# Alpaca credentials and WebSocket endpoint
key = os.getenv("ALPACA_KEY")
secret = os.getenv("ALPACA_SECRET")
uri = "wss://stream.data.alpaca.markets/v2/iex"
symbol_list = ["*"]
timeout = 120  # seconds

# Graceful shutdown flag
shutdown_event = asyncio.Event()

# Setup GCP Cloud Logging (non-blocking)
gcp_client = google.cloud.logging.Client()
cloud_handler = CloudLoggingHandler(gcp_client, name="websocket-kafka-logger", transport=BackgroundThreadTransport)

# Attach GCP handler to root logger
logging.basicConfig(
    level=logging.INFO,
    handlers=[cloud_handler, logging.StreamHandler(sys.stdout)],
    format="%(asctime)s %(levelname)s: %(message)s"
)

def handle_shutdown(*_):
    logging.info("Shutdown signal received.")
    cloud_handler.flush()
    cloud_handler.close()
    shutdown_event.set()

signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)

async def consume_websocket_and_send_to_kafka(producer):
    backoff = 1
    retry_count = 0
    while not shutdown_event.is_set() and retry_count < 10:
        try:
            async with websockets.connect(uri) as websocket:
                logging.info("Connected to Alpaca WebSocket")

                await websocket.recv()  # initial hello from server

                await websocket.send(json.dumps({"action": "auth", "key": key, "secret": secret}))
                logging.info(f"Auth Response: {await websocket.recv()}")

                await websocket.send(json.dumps({"action": "subscribe", "bars": symbol_list}))
                logging.info(f"Subscribe Response: {await websocket.recv()}")

                logging.info("Receiving messages...")
                backoff = 1  # reset backoff after success

                while not shutdown_event.is_set():
                    try:
                        message = await asyncio.wait_for(websocket.recv(), timeout)
                        await producer.send(KAFKA_TOPIC, json.dumps(json.loads(message)).encode("utf-8"))
                        logging.info("Message sent to Kafka")
                    except asyncio.TimeoutError:
                        retry_count += 1
                        logging.warning(f"Timeout: No message from WebSocket for 120s. Retrying in {backoff}s... with retry count - {retry_count}.")
                        await asyncio.sleep(backoff)
                        backoff = min(backoff * 2, timeout)
                        if retry_count >= 20:
                            logging.error("Max retries reached. Exiting.")
                            break
        except Exception as e:
            retry_count += 1
            if retry_count >= 20:
                logging.error("Max retries reached. Exiting.")
                break
            logging.warning(f"Connection error: {e}. Retrying in {backoff}s... with retry count - {retry_count}.")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, timeout)
        finally:
                cloud_handler.flush()
                cloud_handler.close()
    logging.info("Exiting message loop.")


async def main():
    producer = AIOKafkaProducer(bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS)
    await producer.start()
    try:
        await consume_websocket_and_send_to_kafka(producer)
    finally:
        await producer.stop()
        logging.info("Kafka producer stopped cleanly.")
        cloud_handler.flush()
        cloud_handler.close()

if __name__ == "__main__":
    asyncio.run(main())