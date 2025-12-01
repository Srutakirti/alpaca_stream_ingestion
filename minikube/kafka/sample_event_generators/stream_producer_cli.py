#!/usr/bin/env python3
"""
Continuous Stock Data Stream Producer - CLI Tool

This script generates and streams realistic stock market data to a Kafka topic.
It runs continuously until interrupted (Ctrl+C) and provides real-time statistics.

Features:
  - Automatic topic creation (3 partitions, replication factor 1)
  - Non-blocking Kafka producer for high throughput
  - Configurable message rate and batch sizes
  - Error handling with success/failure callbacks
  - Real-time statistics tracking
  - Graceful shutdown handling

Requirements:
  - kafka-python: pip install kafka-python

Usage Examples:
  # Run with defaults (192.168.49.2:32100, topic: iex-topic-1, 60 msg/min)
  python stream_producer_cli.py

  # Custom broker and topic
  python stream_producer_cli.py --brokers localhost:9092 --topic stock-data

  # High-frequency streaming (300 messages per minute)
  python stream_producer_cli.py --rate 300

  # Larger batches (5-10 records per message)
  python stream_producer_cli.py --batch-min 5 --batch-max 10

  # Debug logging
  python stream_producer_cli.py --log-level DEBUG

Author: Generated with Claude Code
"""

import argparse
import json
import random
import signal
import sys
import time
from datetime import datetime, timezone
from typing import Dict, List

from kafka import KafkaProducer
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError
import logging

# Global reference for signal handler
producer_instance = None


class StockStreamProducer:
    """
    Produces continuous stream of stock market data to Kafka.

    Generates realistic OHLC (Open, High, Low, Close) stock data with volume
    and other market indicators. Uses non-blocking Kafka producer with callbacks
    for error handling and statistics tracking.
    """

    def __init__(self, bootstrap_servers: str, topic: str, rate: int,
                 batch_min: int, batch_max: int):
        """
        Initialize the stock stream producer.

        Args:
            bootstrap_servers: Kafka broker addresses (e.g., "localhost:9092")
            topic: Kafka topic to produce messages to
            rate: Number of message batches to send per minute
            batch_min: Minimum number of records per batch
            batch_max: Maximum number of records per batch
        """
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.rate = rate
        self.batch_range = (batch_min, batch_max)
        self.producer = None
        self.logger = logging.getLogger(__name__)

        # Stock symbols to simulate
        self.symbols = [
            "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA",
            "NVDA", "META", "NFLX", "AMD", "INTC"
        ]

        # Realistic base prices for each symbol (USD)
        self.base_prices = {
            "AAPL": 175.00,
            "GOOGL": 140.00,
            "MSFT": 350.00,
            "AMZN": 145.00,
            "TSLA": 250.00,
            "NVDA": 450.00,
            "META": 320.00,
            "NFLX": 450.00,
            "AMD": 110.00,
            "INTC": 45.00
        }

        # Track current prices for realistic price movement simulation
        self.current_prices = self.base_prices.copy()

        # Statistics tracking
        self.stats = {
            'messages_sent': 0,      # Number of successful message sends
            'messages_failed': 0,    # Number of failed message sends
            'records_sent': 0,       # Total number of records sent
            'start_time': None       # Timestamp when streaming started
        }

    def ensure_topic_exists(self):
        """
        Check if the Kafka topic exists, and create it if it doesn't.

        Creates the topic with:
          - 3 partitions: Allows parallel consumption by multiple consumers
          - Replication factor of 1: Single replica (suitable for dev/test)

        Raises:
            Exception: If topic creation fails (except when topic already exists)
        """
        try:
            # Create admin client to manage topics
            admin_client = KafkaAdminClient(
                bootstrap_servers=self.bootstrap_servers,
                client_id='stream_producer_admin'
            )

            # Get list of existing topics
            existing_topics = admin_client.list_topics()

            if self.topic in existing_topics:
                self.logger.info(f"Topic '{self.topic}' already exists")
            else:
                self.logger.info(f"Topic '{self.topic}' does not exist, creating it...")

                # Define new topic configuration
                topic = NewTopic(
                    name=self.topic,
                    num_partitions=3,           # 3 partitions for parallel processing
                    replication_factor=1        # Single replica (dev/test setup)
                )

                # Create the topic
                admin_client.create_topics(
                    new_topics=[topic],
                    validate_only=False         # Actually create the topic
                )

                self.logger.info(
                    f"Topic '{self.topic}' created successfully "
                    f"(partitions=3, replication=1)"
                )

            # Close admin client
            admin_client.close()

        except TopicAlreadyExistsError:
            # Topic was created between check and creation (race condition)
            self.logger.info(f"Topic '{self.topic}' already exists")

        except Exception as e:
            self.logger.error(f"Failed to check/create topic: {e}")
            raise

    def connect(self):
        """
        Initialize and connect the Kafka producer.

        Also ensures the target topic exists, creating it if necessary.

        Producer Configuration:
          - acks=1: Leader acknowledges, good balance of speed and reliability
          - linger_ms=10: Batch messages for 10ms to improve throughput
          - compression_type='snappy': Compress messages for efficiency
          - Non-blocking: No max_in_flight_requests limit for better performance

        Raises:
            Exception: If connection to Kafka fails
        """
        try:
            # First, ensure the topic exists (create if needed)
            self.ensure_topic_exists()

            # Now create the producer
            self.producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                # JSON serializer for message values
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                # Key serializer for partition routing
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                # Wait for leader acknowledgment (balance of speed vs reliability)
                acks=1,
                # Retry failed sends up to 3 times
                retries=3,
                # Batch messages for up to 10ms to improve throughput
                linger_ms=10,
                # Compress messages using Snappy for efficiency
                compression_type='snappy'
            )
            self.logger.info(f"Connected to Kafka at {self.bootstrap_servers}")
            self.logger.info(f"Producing to topic: {self.topic}")
        except Exception as e:
            self.logger.error(f"Failed to connect to Kafka: {e}")
            raise

    def _on_send_success(self, record_metadata):
        """
        Callback invoked when a message is successfully sent to Kafka.

        Args:
            record_metadata: Metadata about the sent record (topic, partition, offset)
        """
        self.stats['messages_sent'] += 1
        self.logger.info(
            f"✓ Message sent: topic={record_metadata.topic} "
            f"partition={record_metadata.partition} "
            f"offset={record_metadata.offset}"
        )

    def _on_send_error(self, exception):
        """
        Callback invoked when a message fails to send to Kafka.

        Args:
            exception: The exception that caused the send failure
        """
        self.stats['messages_failed'] += 1
        self.logger.error(f"Message send failed: {exception}")

    def generate_stock_record(self, symbol: str) -> Dict:
        """
        Generate a single realistic stock data record.

        Simulates realistic stock price movements and trading activity:
          - Price changes: ±2% typical variation
          - OHLC data: Open, High, Low, Close prices
          - Volume: Between 1M and 50M shares
          - VWAP: Volume-weighted average price

        Args:
            symbol: Stock ticker symbol (e.g., "AAPL")

        Returns:
            Dictionary containing stock data matching expected schema
        """
        current_price = self.current_prices[symbol]

        # Simulate realistic price movement (±2% typical change)
        price_change_percent = random.uniform(-0.02, 0.02)
        new_price = current_price * (1 + price_change_percent)

        # Ensure price doesn't go below $1 (prevent negative/zero prices)
        new_price = max(new_price, 1.0)
        self.current_prices[symbol] = new_price

        # Generate realistic OHLC (Open, High, Low, Close) data
        high_price = new_price * random.uniform(1.0, 1.005)  # Up to 0.5% higher than close
        low_price = new_price * random.uniform(0.995, 1.0)   # Up to 0.5% lower than close
        open_price = current_price                           # Previous price
        close_price = new_price                              # New price

        # Generate realistic volume (between 1M and 50M shares)
        volume = random.randint(1_000_000, 50_000_000)

        # Generate number of trades (roughly volume/100 to volume/1000)
        num_trades = random.randint(volume // 1000, volume // 100)

        # Calculate volume weighted average price
        vwap = (high_price + low_price + close_price) / 3

        # Current timestamp in ISO 8601 format
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")

        return {
            "T": "T",                       # Trade type indicator
            "S": symbol,                    # Stock symbol
            "o": round(open_price, 2),      # Open price
            "h": round(high_price, 2),      # High price
            "l": round(low_price, 2),       # Low price
            "c": round(close_price, 2),     # Close price
            "v": volume,                    # Trading volume
            "t": timestamp,                 # Timestamp
            "n": num_trades,                # Number of trades
            "vw": round(vwap, 2)            # Volume weighted average price
        }

    def generate_batch(self, batch_size: int) -> List[Dict]:
        """
        Generate a batch of stock records.

        Args:
            batch_size: Number of records to generate

        Returns:
            List of stock data records
        """
        records = []
        for _ in range(batch_size):
            # Randomly select a stock symbol
            symbol = random.choice(self.symbols)
            record = self.generate_stock_record(symbol)
            records.append(record)

        return records

    def send_batch(self, records: List[Dict], batch_id: int):
        """
        Send a batch of records to Kafka (non-blocking).

        Uses fire-and-forget approach with callbacks for success/error handling.
        This is non-blocking - the method returns immediately without waiting
        for Kafka acknowledgment.

        Args:
            records: List of stock data records to send
            batch_id: Identifier for this batch (used as Kafka key)
        """
        if not self.producer:
            raise RuntimeError("Producer not initialized. Call connect() first.")

        # Log the batch being sent
        symbols = [r['S'] for r in records]
        prices = [r['c'] for r in records]
        self.logger.info(
            f"→ Sending batch_{batch_id}: {len(records)} records "
            f"[{', '.join(f'{s}@${p}' for s, p in zip(symbols, prices))}]"
        )

        # Send message with callbacks (non-blocking)
        future = self.producer.send(
            topic=self.topic,
            value=records,  # Send as JSON array
            key=f"batch_{batch_id}"
        )

        # Attach callbacks for success and error handling
        future.add_callback(self._on_send_success)
        future.add_errback(self._on_send_error)

        # Update statistics
        self.stats['records_sent'] += len(records)

    def print_stats(self):
        """
        Print current streaming statistics.

        Displays:
          - Messages sent/failed counts and success rate
          - Total records sent
          - Runtime and average throughput
        """
        elapsed = time.time() - self.stats['start_time']
        total_messages = self.stats['messages_sent'] + self.stats['messages_failed']
        success_rate = (self.stats['messages_sent'] / total_messages * 100) if total_messages > 0 else 0

        # Calculate throughput (messages and records per minute)
        msgs_per_min = (self.stats['messages_sent'] / elapsed * 60) if elapsed > 0 else 0
        records_per_min = (self.stats['records_sent'] / elapsed * 60) if elapsed > 0 else 0

        self.logger.info("=" * 70)
        self.logger.info(f"STATISTICS (Runtime: {elapsed:.1f}s)")
        self.logger.info("-" * 70)
        self.logger.info(f"  Messages Sent:     {self.stats['messages_sent']:,}")
        self.logger.info(f"  Messages Failed:   {self.stats['messages_failed']:,}")
        self.logger.info(f"  Success Rate:      {success_rate:.2f}%")
        self.logger.info(f"  Total Records:     {self.stats['records_sent']:,}")
        self.logger.info(f"  Throughput:        {msgs_per_min:.1f} msg/min, {records_per_min:.1f} records/min")
        self.logger.info("=" * 70)

    def run_continuous_stream(self):
        """
        Run continuous streaming until interrupted (Ctrl+C).

        Generates and sends batches of stock data at the configured rate.
        Provides periodic logging of sample data and statistics.

        The loop runs indefinitely until:
          - User interrupts with Ctrl+C (KeyboardInterrupt)
          - An unrecoverable error occurs
        """
        # Calculate time interval between messages (in seconds)
        interval = 60.0 / self.rate

        self.logger.info("=" * 70)
        self.logger.info("STARTING CONTINUOUS STREAM")
        self.logger.info("-" * 70)
        self.logger.info(f"  Rate:              {self.rate} batches/minute")
        self.logger.info(f"  Interval:          {interval:.2f} seconds between batches")
        self.logger.info(f"  Batch Size:        {self.batch_range[0]}-{self.batch_range[1]} records")
        self.logger.info(f"  Symbols:           {', '.join(self.symbols)}")
        self.logger.info("=" * 70)
        self.logger.info("Press Ctrl+C to stop streaming")
        self.logger.info("")

        # Record start time
        self.stats['start_time'] = time.time()
        message_count = 0

        try:
            # Infinite loop - runs until Ctrl+C
            while True:
                # Generate random batch size within configured range
                batch_size = random.randint(*self.batch_range)

                # Generate stock data records
                records = self.generate_batch(batch_size)

                # Send to Kafka (non-blocking)
                self.send_batch(records, message_count)
                message_count += 1

                # Print detailed statistics every 100 batches
                if message_count % 100 == 0:
                    self.print_stats()

                # Wait for next interval (rate limiting)
                time.sleep(interval)

        except KeyboardInterrupt:
            self.logger.info("\nStreaming interrupted by user (Ctrl+C)")

        except Exception as e:
            self.logger.error(f"Streaming failed with error: {e}", exc_info=True)
            raise

    def close(self):
        """
        Close the Kafka producer and cleanup resources.

        Flushes any pending messages and prints final statistics.
        """
        if self.producer:
            self.logger.info("Flushing pending messages...")
            # Flush any buffered messages
            self.producer.flush(timeout=10)
            # Close the producer
            self.producer.close()
            self.logger.info("Kafka producer closed")

        # Print final statistics
        if self.stats['start_time']:
            self.logger.info("\nFINAL STATISTICS:")
            self.print_stats()


def signal_handler(signum, frame):
    """
    Handle interrupt signal (Ctrl+C) for graceful shutdown.

    Args:
        signum: Signal number
        frame: Current stack frame
    """
    print("\n\nReceived interrupt signal, shutting down...")
    if producer_instance:
        producer_instance.close()
    sys.exit(0)


def parse_arguments():
    """
    Parse command-line arguments.

    Returns:
        Namespace object containing parsed arguments
    """
    parser = argparse.ArgumentParser(
        description='Continuous Stock Data Stream Producer for Kafka',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with defaults
  %(prog)s

  # Custom broker and topic
  %(prog)s --brokers localhost:9092 --topic stock-data

  # High-frequency streaming (300 messages per minute)
  %(prog)s --rate 300

  # Larger batches (5-10 records per message)
  %(prog)s --batch-min 5 --batch-max 10
        """
    )

    parser.add_argument(
        '-b', '--brokers',
        default='192.168.49.2:32100',
        help='Kafka bootstrap servers (default: 192.168.49.2:32100)'
    )

    parser.add_argument(
        '-t', '--topic',
        default='iex-topic-1',
        help='Kafka topic name (default: iex-topic-1)'
    )

    parser.add_argument(
        '-r', '--rate',
        type=int,
        default=60,
        help='Number of message batches per minute (default: 60)'
    )

    parser.add_argument(
        '--batch-min',
        type=int,
        default=1,
        help='Minimum records per batch (default: 1)'
    )

    parser.add_argument(
        '--batch-max',
        type=int,
        default=5,
        help='Maximum records per batch (default: 5)'
    )

    parser.add_argument(
        '-l', '--log-level',
        choices=['DEBUG', 'INFO', 'WARNING', 'ERROR'],
        default='INFO',
        help='Logging level (default: INFO)'
    )

    return parser.parse_args()


def main():
    """
    Main entry point for the stream producer.

    Parses CLI arguments, initializes the producer, and runs continuous streaming.
    Handles graceful shutdown on Ctrl+C and exceptions.
    """
    # Parse command-line arguments
    args = parse_arguments()

    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    logger = logging.getLogger(__name__)

    # Register signal handler for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)

    # Validate arguments
    if args.batch_min > args.batch_max:
        logger.error("Error: --batch-min cannot be greater than --batch-max")
        sys.exit(1)

    if args.rate <= 0:
        logger.error("Error: --rate must be greater than 0")
        sys.exit(1)

    # Create producer instance
    global producer_instance
    producer_instance = StockStreamProducer(
        bootstrap_servers=args.brokers,
        topic=args.topic,
        rate=args.rate,
        batch_min=args.batch_min,
        batch_max=args.batch_max
    )

    try:
        # Connect to Kafka
        producer_instance.connect()

        # Start continuous streaming
        producer_instance.run_continuous_stream()

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)

    finally:
        # Cleanup
        producer_instance.close()


if __name__ == "__main__":
    main()
