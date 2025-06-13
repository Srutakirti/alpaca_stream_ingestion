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
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

def get_config():
    """Load configuration from environment variables."""
    config = {
        "KAFKA_TOPIC": os.getenv("KAFKA_TOPIC", "iex_raw_0"),
        "KAFKA_BOOTSTRAP_SERVERS": os.getenv("KAFKA_BOOTSTRAP_SERVERS", "instance-20250325-162745:9095"),
        "ALPACA_KEY": os.getenv("ALPACA_KEY"),
        "ALPACA_SECRET": os.getenv("ALPACA_SECRET"),
        "ALPACA_WS_URI": os.getenv("ALPACA_WS_URI", "wss://stream.data.alpaca.markets/v2/iex"),
        "SYMBOL_LIST": json.loads(os.getenv("SYMBOL_LIST", '["*"]')),
        "WEBSOCKET_TIMEOUT": int(os.getenv("WEBSOCKET_TIMEOUT", "120")),
        "MAX_RETRIES": int(os.getenv("MAX_RETRIES", "20")),
        "LOG_NAME": os.getenv("LOG_NAME", "websocket-kafka-logger"),
    }
    # Validate required configs
    if not config["ALPACA_KEY"] or not config["ALPACA_SECRET"]:
        raise ValueError("ALPACA_KEY and/or ALPACA_SECRET environment variables not set.")
    return config

def setup_logging(log_name):
    """Setup GCP Cloud Logging and local logging."""
    gcp_client = google.cloud.logging.Client()
    cloud_handler = CloudLoggingHandler(
        gcp_client, name=log_name, transport=BackgroundThreadTransport
    )
    logging.basicConfig(
        level=logging.INFO,
        handlers=[cloud_handler, logging.StreamHandler(sys.stdout)],
        format="%(asctime)s %(levelname)s: %(message)s"
    )
    return cloud_handler

shutdown_event = asyncio.Event()

def handle_shutdown(*_):
    logging.info("Shutdown signal received.")
    shutdown_event.set()

signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)

async def consume_websocket_and_send_to_kafka(producer, config, cloud_handler):
    """Consume messages from Alpaca WebSocket and send to Kafka."""
    backoff = 1
    retry_count = 0
    while not shutdown_event.is_set() and retry_count <= config["MAX_RETRIES"]:
        try:
            async with websockets.connect(config["ALPACA_WS_URI"]) as websocket:
                logging.info("Connected to Alpaca WebSocket")

                await websocket.recv()  # initial hello from server

                await websocket.send(json.dumps({
                    "action": "auth",
                    "key": config["ALPACA_KEY"],
                    "secret": config["ALPACA_SECRET"]
                }))
                auth_response = await websocket.recv()
                logging.info(f"Auth Response: {auth_response}")

                await websocket.send(json.dumps({
                    "action": "subscribe",
                    "bars": config["SYMBOL_LIST"]
                }))
                subscribe_response = await websocket.recv()
                logging.info(f"Subscribe Response: {subscribe_response}")

                logging.info("Receiving messages...")
                backoff = 1  # reset backoff after success

                while not shutdown_event.is_set():
                    try:
                        message = await asyncio.wait_for(
                            websocket.recv(), timeout=config["WEBSOCKET_TIMEOUT"]
                        )
                        # Log message type/length, not full content
                        logging.info(f"Received message of length {len(message)}")
                        await producer.send_and_wait(
                            config["KAFKA_TOPIC"],
                            json.dumps(json.loads(message)).encode("utf-8")
                        )
                        logging.info("Message sent to Kafka")
                    except asyncio.TimeoutError:
                        logging.warning("Timeout: No message from WebSocket. Reconnecting.")
                        break
        except websockets.ConnectionClosed as e:
            retry_count += 1
            logging.error(f"WebSocket closed: {e}. Retrying ({retry_count}/{config['MAX_RETRIES']}) in {backoff}s...")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, config["WEBSOCKET_TIMEOUT"])
        except Exception as e:
            retry_count += 1
            logging.error(f"Error: {e}. Retrying ({retry_count}/{config['MAX_RETRIES']}) in {backoff}s...")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, config["WEBSOCKET_TIMEOUT"])

    logging.info(f"Exiting message loop. Retry count: {retry_count}")

async def main():
    """Main entry point for the producer."""
    try:
        config = get_config()
    except Exception as e:
        logging.error(f"Configuration error: {e}")
        sys.exit(1)

    cloud_handler = setup_logging(config["LOG_NAME"])

    producer = AIOKafkaProducer(bootstrap_servers=config["KAFKA_BOOTSTRAP_SERVERS"])
    await producer.start()
    try:
        await consume_websocket_and_send_to_kafka(producer, config, cloud_handler)
    except Exception as e:
        logging.error(f"Fatal error in main: {e}")
    finally:
        await producer.stop()
        logging.info("Kafka producer stopped cleanly.")
        cloud_handler.flush()
        cloud_handler.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as e:
        logging.error(f"Unhandled exception: {e}")