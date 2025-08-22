import asyncio
import websockets
import json
import logging
import signal
import sys
import os
import argparse
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field
from typing import List
from aiokafka import AIOKafkaProducer
import google.cloud.logging
from google.cloud.logging_v2.handlers import CloudLoggingHandler
from google.cloud.logging_v2.handlers.transports.background_thread import BackgroundThreadTransport
# from dotenv import load_dotenv

# Load environment variables
# load_dotenv()

@dataclass
class Config:
    """Configuration settings for the application."""
    KAFKA_TOPIC: str = os.getenv("KAFKA_TOPIC", "iex_raw_0")
    KAFKA_BOOTSTRAP_SERVERS: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "instance-20250325-162745:9095")
    ALPACA_KEY: Optional[str] = os.getenv("ALPACA_KEY")
    ALPACA_SECRET: Optional[str] = os.getenv("ALPACA_SECRET")
    WEBSOCKET_URI: str = os.getenv("WEBSOCKET_URI", "wss://stream.data.alpaca.markets/v2/iex")
    SYMBOL_LIST: List[str] = field(default_factory=lambda: json.loads(os.getenv("SYMBOL_LIST", '["*"]')))
    TIMEOUT: int = int(os.getenv("TIMEOUT", "120"))
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "5"))
    BACKOFF_MAX: int = int(os.getenv("BACKOFF_MAX", "120"))

class Metrics:
    """Tracks runtime metrics for monitoring."""
    messages_received: int = 0
    messages_sent: int = 0
    errors: int = 0
    last_message_time: Optional[datetime] = None
    connection_status: bool = False

    @classmethod
    def update_received(cls) -> None:
        """Update metrics for received messages."""
        cls.messages_received += 1

    @classmethod
    def update_sent(cls) -> None:
        """Update metrics for sent messages."""
        cls.messages_sent += 1

    @classmethod
    def update_error(cls) -> None:
        """Increment error count."""
        cls.errors += 1

    @classmethod
    def set_connection_status(cls, status: bool) -> None:
        """Update connection status."""
        cls.connection_status = status

    @classmethod
    def get_metrics(cls) -> Dict[str, Any]:
        """Return current metrics as dictionary."""
        return {
            "messages_received": cls.messages_received,
            "messages_sent": cls.messages_sent,
            "errors": cls.errors,
            "last_message_time": cls.last_message_time,
            "connection_status": cls.connection_status
        }

def setup_logging(config: Config) -> CloudLoggingHandler:
    """Setup GCP Cloud Logging with stdout fallback."""
    gcp_client = google.cloud.logging.Client()
    cloud_handler = CloudLoggingHandler(
        gcp_client,
        name="websocket-kafka-logger",
        transport=BackgroundThreadTransport
    )
    logging.basicConfig(
        level=logging.INFO,
        handlers=[cloud_handler, logging.StreamHandler(sys.stdout)],
        format="%(asctime)s %(levelname)s: %(message)s"
    )
    return cloud_handler

async def consume_websocket_and_send_to_kafka(
    producer: AIOKafkaProducer,
    config: Config,
    shutdown_event: asyncio.Event
) -> None:
    """
    Consumes messages from Alpaca WebSocket and produces to Kafka.
    
    Args:
        producer: Configured AIOKafkaProducer instance
        config: Application configuration
        shutdown_event: Event to signal graceful shutdown
    """
    backoff = 1
    retry_count = 0

    while not shutdown_event.is_set() and retry_count < config.MAX_RETRIES:
        try:
            async with websockets.connect(config.WEBSOCKET_URI) as websocket:
                logging.info("Connected to Alpaca WebSocket")
                Metrics.set_connection_status(True)

                # Initial connection and authentication
                await websocket.recv()
                await websocket.send(json.dumps({
                    "action": "auth",
                    "key": config.ALPACA_KEY,
                    "secret": config.ALPACA_SECRET
                }))
                auth_response = await websocket.recv()
                logging.info(f"Auth Response: {auth_response}")

                # Subscribe to symbols
                await websocket.send(json.dumps({
                    "action": "subscribe",
                    "bars": config.SYMBOL_LIST
                }))
                subscribe_response = await websocket.recv()
                logging.info(f"Subscribe Response: {subscribe_response}")

                logging.info("Starting message processing loop...")
                backoff = 5  # Reset backoff after successful connection

                while not shutdown_event.is_set():
                    try:
                        message = await asyncio.wait_for(
                            websocket.recv(),
                            timeout=config.TIMEOUT
                        )
                        Metrics.update_received()
                        
                        # Send to Kafka
                        await producer.send_and_wait(
                            config.KAFKA_TOPIC,
                            json.dumps(json.loads(message)).encode("utf-8")
                        )
                        Metrics.update_sent()
                        
                        logging.info(f"Metrics: {Metrics.get_metrics()}")
                            
                    except asyncio.TimeoutError:
                        logging.warning(f"Timeout: No message received for {config.TIMEOUT} for retry - {retry_count}")
                        retry_count += 1
                        break
                        
        except websockets.ConnectionClosed as e:
            Metrics.set_connection_status(False)
            Metrics.update_error()
            retry_count += 1
            logging.error(f"WebSocket connection closed: {e}. Retry {retry_count}/{config.MAX_RETRIES}")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, config.BACKOFF_MAX)
            
        except Exception as e:
            Metrics.set_connection_status(False)
            Metrics.update_error()
            retry_count += 1
            logging.error(f"Unexpected error: {e}. Retry {retry_count}/{config.MAX_RETRIES}")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, config.BACKOFF_MAX)

    logging.info(f"Exiting message processing loop after retries - {retry_count}")
    Metrics.set_connection_status(False)

async def main(args: argparse.Namespace) -> None:
    """
    Main entry point for the application.
    
    Args:
        args: Command line arguments
    """
    # Load and validate configuration
    config = Config()
    if args.kafka_topic:
        config.KAFKA_TOPIC = args.kafka_topic
    if args.kafka_servers:
        config.KAFKA_BOOTSTRAP_SERVERS = args.kafka_servers
    
    if not config.ALPACA_KEY or not config.ALPACA_SECRET:
        logging.error("ALPACA_KEY and ALPACA_SECRET must be set in environment")
        sys.exit(1)

    # Setup logging
    cloud_handler = setup_logging(config)
    
    # Setup shutdown handler
    shutdown_event = asyncio.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: shutdown_event.set())

    # Initialize and start Kafka producer
    producer = AIOKafkaProducer(
        bootstrap_servers=config.KAFKA_BOOTSTRAP_SERVERS,
        retry_backoff_ms=1000,
        max_batch_size=16384
    )
    
    try:
        await producer.start()
        logging.info(f"Started Kafka producer: {config.KAFKA_BOOTSTRAP_SERVERS}")
        
        await consume_websocket_and_send_to_kafka(
            producer=producer,
            config=config,
            shutdown_event=shutdown_event
        )
        
    except Exception as e:
        logging.error(f"Fatal error in main: {e}")
        Metrics.update_error()
    
    finally:
        logging.info("Shutting down...")
        await producer.stop()
        cloud_handler.flush()
        cloud_handler.close()
        logging.info(f"Final metrics: {Metrics.get_metrics()}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Alpaca WebSocket to Kafka Producer")
    parser.add_argument("--kafka-topic", help="Override Kafka topic name")
    parser.add_argument("--kafka-servers", help="Override Kafka bootstrap servers")
    args = parser.parse_args()

    try:
        asyncio.run(main(args))
    except KeyboardInterrupt:
        logging.info("Received keyboard interrupt")
    except Exception as e:
        logging.error(f"Unhandled exception: {e}")
        sys.exit(1)