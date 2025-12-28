#!/usr/bin/env python3
"""
Synthetic Stock Event Generator

Generates realistic stock bar events and sends them to Kafka for testing purposes.
Mimics the format of Alpaca WebSocket bar messages.

Usage:
    uv run python extract/helpers/synthetic_stock_generator.py --symbols AAPL TSLA GOOGL --rate 10
    uv run python extract/helpers/synthetic_stock_generator.py --help
"""

import asyncio
import json
import random
import time
import argparse
import sys
from datetime import datetime
from typing import List, Dict, Any
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from aiokafka import AIOKafkaProducer
from extract.app.conf_reader import Config


# Stock symbols with realistic price ranges
STOCK_UNIVERSE = {
    'AAPL': {'base': 175.0, 'volatility': 5.0},
    'TSLA': {'base': 242.0, 'volatility': 15.0},
    'GOOGL': {'base': 141.0, 'volatility': 8.0},
    'MSFT': {'base': 378.0, 'volatility': 10.0},
    'AMZN': {'base': 157.0, 'volatility': 8.0},
    'NVDA': {'base': 495.0, 'volatility': 25.0},
    'META': {'base': 352.0, 'volatility': 12.0},
    'NFLX': {'base': 488.0, 'volatility': 20.0},
    'AMD': {'base': 143.0, 'volatility': 10.0},
    'INTC': {'base': 48.0, 'volatility': 3.0},
    'SPY': {'base': 475.0, 'volatility': 5.0},
    'QQQ': {'base': 395.0, 'volatility': 8.0},
    'DIA': {'base': 375.0, 'volatility': 4.0},
    'IWM': {'base': 195.0, 'volatility': 5.0},
}


class StockPriceSimulator:
    """Simulates realistic stock price movements."""

    def __init__(self, symbol: str, base_price: float, volatility: float):
        self.symbol = symbol
        self.current_price = base_price
        self.volatility = volatility
        self.last_update = time.time()

    def get_next_bar(self) -> Dict[str, Any]:
        """Generate next OHLC bar with realistic price movement."""
        # Random walk with mean reversion
        change_pct = random.gauss(0, self.volatility / 100)

        # Mean reversion force (pull back towards base)
        base_price = STOCK_UNIVERSE[self.symbol]['base']
        reversion_force = (base_price - self.current_price) * 0.01

        # Apply change with mean reversion
        price_change = self.current_price * change_pct + reversion_force
        self.current_price += price_change

        # Generate OHLC for this bar
        # Open is current price with small variance
        open_price = self.current_price * (1 + random.gauss(0, 0.001))

        # High/Low with realistic spread
        spread = abs(random.gauss(0, self.volatility / 200))
        high_price = self.current_price * (1 + spread)
        low_price = self.current_price * (1 - spread)

        # Close is final price
        close_price = self.current_price

        # Ensure high >= close >= low
        high_price = max(high_price, close_price, open_price)
        low_price = min(low_price, close_price, open_price)

        # Volume: random realistic volume
        volume = int(random.lognormvariate(7, 1.5)) * 100

        # Number of trades (proportional to volume)
        num_trades = max(1, int(volume / random.randint(50, 200)))

        # Volume weighted average price
        vwap = (high_price + low_price + close_price) / 3

        # Timestamp in RFC3339 format with second precision (matching Alpaca format exactly)
        # Alpaca uses: "2020-07-27T13:35:00Z" (no fractional seconds)
        timestamp_str = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')

        return {
            'T': 'b',
            'S': self.symbol,
            'o': round(open_price, 2),
            'h': round(high_price, 2),
            'l': round(low_price, 2),
            'c': round(close_price, 2),
            'v': volume,
            't': timestamp_str,
            'n': num_trades,
            'vw': round(vwap, 2)
        }


class SyntheticEventGenerator:
    """Generates synthetic stock events and sends to Kafka."""

    def __init__(self, symbols: List[str], kafka_bootstrap: str, topic: str, rate: float):
        self.symbols = symbols
        self.kafka_bootstrap = kafka_bootstrap
        self.topic = topic
        self.rate = rate  # events per second
        self.interval = 1.0 / rate  # seconds between events

        # Initialize price simulators
        self.simulators = {}
        for symbol in symbols:
            if symbol not in STOCK_UNIVERSE:
                print(f"Warning: {symbol} not in universe, using defaults")
                self.simulators[symbol] = StockPriceSimulator(
                    symbol, 100.0, 5.0
                )
            else:
                info = STOCK_UNIVERSE[symbol]
                self.simulators[symbol] = StockPriceSimulator(
                    symbol, info['base'], info['volatility']
                )

        self.producer = None
        self.running = False
        self.total_sent = 0

    async def start_producer(self):
        """Initialize Kafka producer."""
        self.producer = AIOKafkaProducer(
            bootstrap_servers=self.kafka_bootstrap,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        await self.producer.start()
        print(f"✓ Connected to Kafka at {self.kafka_bootstrap}")
        print(f"✓ Publishing to topic: {self.topic}")

    async def stop_producer(self):
        """Stop Kafka producer."""
        if self.producer:
            await self.producer.stop()
            print(f"\n✓ Stopped. Total events sent: {self.total_sent}")

    async def generate_events(self):
        """Generate and send events continuously."""
        self.running = True
        start_time = time.time()

        print(f"\n{'='*80}")
        print(f"Starting synthetic event generation")
        print(f"{'='*80}")
        print(f"Symbols:      {', '.join(self.symbols)}")
        print(f"Rate:         {self.rate} events/sec ({self.rate * len(self.symbols)} bars/sec)")
        print(f"Interval:     {self.interval:.3f} sec")
        print(f"Press Ctrl+C to stop")
        print(f"{'='*80}\n")

        try:
            while self.running:
                batch_start = time.time()

                # Generate one bar for each symbol in round-robin
                bars = []
                for symbol in self.symbols:
                    bar = self.simulators[symbol].get_next_bar()
                    bars.append(bar)

                # Create message in Alpaca format (array of bars)
                message = bars

                # Send to Kafka
                await self.producer.send(self.topic, value=message)
                self.total_sent += len(bars)

                # Print progress every 10 events
                if self.total_sent % (len(self.symbols) * 10) == 0:
                    elapsed = time.time() - start_time
                    rate = self.total_sent / elapsed if elapsed > 0 else 0
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] "
                          f"Sent {self.total_sent:,} bars | "
                          f"Rate: {rate:.1f} bars/sec | "
                          f"Symbols: {len(self.symbols)}")

                # Sleep to maintain target rate
                elapsed = time.time() - batch_start
                sleep_time = max(0, self.interval - elapsed)
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

        except asyncio.CancelledError:
            print("\nShutting down gracefully...")
            self.running = False


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Generate synthetic stock events to Kafka',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate events for AAPL, TSLA, GOOGL at 10 events/sec
  uv run python extract/helpers/synthetic_stock_generator.py --symbols AAPL TSLA GOOGL --rate 10

  # Use custom Kafka broker and topic
  uv run python extract/helpers/synthetic_stock_generator.py --kafka localhost:9092 --topic my-topic

  # Generate high-frequency data (100 events/sec)
  uv run python extract/helpers/synthetic_stock_generator.py --rate 100

  # Use config file for Kafka settings
  uv run python extract/helpers/synthetic_stock_generator.py --config config/config.yaml
        """
    )

    parser.add_argument(
        '--symbols',
        nargs='+',
        default=['AAPL', 'TSLA', 'GOOGL', 'MSFT', 'NVDA'],
        help='Stock symbols to generate (default: AAPL TSLA GOOGL MSFT NVDA)'
    )

    parser.add_argument(
        '--rate',
        type=float,
        default=5.0,
        help='Events per second (default: 5.0)'
    )

    parser.add_argument(
        '--kafka',
        default=None,
        help='Kafka bootstrap servers (default: from config or localhost:9092)'
    )

    parser.add_argument(
        '--topic',
        default=None,
        help='Kafka topic name (default: from config or iex-topic-1)'
    )

    parser.add_argument(
        '--config',
        default='config/config.yaml',
        help='Path to config file (default: config/config.yaml)'
    )

    args = parser.parse_args()

    # Load config if available
    try:
        config = Config(args.config)
        kafka_bootstrap = args.kafka or config.get('kafka.bootstrap_servers_local', 'localhost:9092')
        topic = args.topic or config.get('kafka.topics.raw_trade', 'iex-topic-1')
    except Exception as e:
        print(f"Warning: Could not load config ({e}), using defaults")
        kafka_bootstrap = args.kafka or 'localhost:9092'
        topic = args.topic or 'iex-topic-1'

    # Validate symbols
    unknown_symbols = [s for s in args.symbols if s not in STOCK_UNIVERSE]
    if unknown_symbols:
        print(f"Warning: Unknown symbols will use default prices: {', '.join(unknown_symbols)}")
        print(f"Known symbols: {', '.join(sorted(STOCK_UNIVERSE.keys()))}\n")

    # Create generator
    generator = SyntheticEventGenerator(
        symbols=args.symbols,
        kafka_bootstrap=kafka_bootstrap,
        topic=topic,
        rate=args.rate
    )

    # Start producer and generate events
    try:
        await generator.start_producer()
        await generator.generate_events()
    except KeyboardInterrupt:
        print("\n\nReceived interrupt signal")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await generator.stop_producer()


if __name__ == '__main__':
    asyncio.run(main())
