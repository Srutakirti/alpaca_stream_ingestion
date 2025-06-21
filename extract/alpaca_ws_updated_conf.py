import asyncio
import websockets
import json
import logging
import signal
import sys
from datetime import datetime
from typing import Optional, Dict, Any
from dataclasses import dataclass
from aiokafka import AIOKafkaProducer
import google.cloud.logging
from google.cloud.logging_v2.handlers import CloudLoggingHandler
from google.cloud.logging_v2.handlers.transports.background_thread import BackgroundThreadTransport
from conf_reader import Config

@dataclass
class Metrics:
    """Tracks runtime metrics for monitoring."""
    messages_received: int = 0
    messages_sent: int = 0
    errors: int = 0
    last_message_time: Optional[datetime] = None
    connection_status: bool = False

    @classmethod
    def get_metrics(cls) -> Dict[str, Any]:
        return {
            "messages_received": cls.messages_received,
            "messages_sent": cls.messages_sent,
            "errors": cls.errors,
            "last_message_time": cls.last_message_time,
            "connection_status": cls.connection_status
        }

def setup_logging(config: Config) -> CloudLoggingHandler:
    """Setup GCP Cloud Logging."""
    gcp_client = google.cloud.logging.Client()
    cloud_handler = CloudLoggingHandler(
        gcp_client,
        name=config.get('logging.name'),
        transport=BackgroundThreadTransport
    )
    logging.basicConfig(
        level=config.get('logging.level'),
        handlers=[cloud_handler, logging.StreamHandler(sys.stdout)],
        format="%(asctime)s %(levelname)s: %(message)s"
    )
    return cloud_handler

async def consume_websocket_and_send_to_kafka(
    producer: AIOKafkaProducer,
    config: Config,
    shutdown_event: asyncio.Event
) -> None:
    """Consumes messages from Alpaca WebSocket and produces to Kafka."""
    backoff = 1
    retry_count = 0

    while not shutdown_event.is_set() and retry_count < config.get('alpaca.max_retries', 5):
        try:
            async with websockets.connect(config.get('alpaca.websocket_uri')) as websocket:
                logging.info("Connected to Alpaca WebSocket")
                Metrics.connection_status = True

                # Initial connection and authentication
                await websocket.recv()
                await websocket.send(json.dumps({
                    "action": "auth",
                    "key": config.get('alpaca.key'),
                    "secret": config.get('alpaca.secret')
                }))
                auth_response = await websocket.recv()
                logging.info(f"Auth Response: {auth_response}")

                # Subscribe to symbols
                await websocket.send(json.dumps({
                    "action": "subscribe",
                    "bars": config.get('alpaca.symbols')
                }))
                subscribe_response = await websocket.recv()
                logging.info(f"Subscribe Response: {subscribe_response}")

                backoff = 1  # Reset backoff after successful connection

                while not shutdown_event.is_set():
                    try:
                        message = await asyncio.wait_for(
                            websocket.recv(),
                            timeout=config.get('alpaca.timeout', 120)
                        )
                        Metrics.messages_received += 1
                        
                        await producer.send_and_wait(
                            config.get('kafka.topics.raw_trade'),
                            json.dumps(json.loads(message)).encode("utf-8")
                        )
                        Metrics.messages_sent += 1
                        Metrics.last_message_time = datetime.now()
                        
                        
                        logging.info(f"Metrics: {Metrics.get_metrics()}")
                            
                    except asyncio.TimeoutError:
                        logging.warning(f"Timeout: No message received for {config.get('alpaca.timeout')}s retry_count - {retry_count}")
                        retry_count += 1
                        break
                        
        except Exception as e:
            Metrics.connection_status = False
            Metrics.errors += 1
            retry_count += 1
            logging.error(f"Error: {e}. Retry {retry_count}")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, config.get('alpaca.backoff_max', 120))

    logging.info("Exiting message processing loop")
    Metrics.connection_status = False

async def main() -> None:
    """Main entry point for the application."""
    config = Config('config/config.yaml')
    
    if not config.get('alpaca.key') or not config.get('alpaca.secret'):
        logging.error("ALPACA_KEY and ALPACA_SECRET must be set in environment")
        sys.exit(1)

    cloud_handler = setup_logging(config)
    shutdown_event = asyncio.Event()
    
    def signal_handler(*_):
        logging.info("Shutdown signal received")
        shutdown_event.set()
    
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, signal_handler)

    producer = AIOKafkaProducer(
        bootstrap_servers=config.get('kafka.bootstrap_servers'),
        retry_backoff_ms=1000,
        max_batch_size=16384
    )
    
    try:
        await producer.start()
        logging.info(f"Started Kafka producer: {config.get('kafka.bootstrap_servers')}")
        
        await consume_websocket_and_send_to_kafka(
            producer=producer,
            config=config,
            shutdown_event=shutdown_event
        )
        
    except Exception as e:
        logging.error(f"Fatal error in main: {e}")
        Metrics.errors += 1
    
    finally:
        logging.info("Shutting down...")
        await producer.stop()
        cloud_handler.flush()
        cloud_handler.close()
        logging.info(f"Final metrics: {Metrics.get_metrics()}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Received keyboard interrupt")
    except Exception as e:
        logging.error(f"Unhandled exception: {e}")
        sys.exit(1)