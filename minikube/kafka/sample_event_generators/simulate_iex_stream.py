import json
import random
import time
from datetime import datetime, timezone
from typing import List, Dict
from kafka import KafkaProducer
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StockDataSimulator:
    def __init__(self, bootstrap_servers: str = "192.168.49.2:32100", topic: str = "iex-topic-1"):
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.producer = None
        
        # Sample stock symbols
        self.symbols = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "NFLX", "AMD", "INTC"]
        
        # Initialize base prices for each symbol (realistic starting points)
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
        
        # Track current prices for realistic price movement
        self.current_prices = self.base_prices.copy()
    
    def connect(self):
        """Initialize Kafka producer"""
        try:
            self.producer = KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                acks='all',
                retries=3,
                max_in_flight_requests_per_connection=1
            )
            logger.info(f"Connected to Kafka at {self.bootstrap_servers}")
        except Exception as e:
            logger.error(f"Failed to connect to Kafka: {e}")
            raise
    
    def generate_single_stock_record(self, symbol: str) -> Dict:
        """Generate a single stock data record matching the expected schema"""
        current_price = self.current_prices[symbol]
        
        # Simulate realistic price movement (±2% typical change)
        price_change_percent = random.uniform(-0.02, 0.02)
        new_price = current_price * (1 + price_change_percent)
        
        # Ensure price doesn't go below $1
        new_price = max(new_price, 1.0)
        self.current_prices[symbol] = new_price
        
        # Generate realistic OHLC data
        high_price = new_price * random.uniform(1.0, 1.005)  # Up to 0.5% higher
        low_price = new_price * random.uniform(0.995, 1.0)   # Up to 0.5% lower
        open_price = current_price
        close_price = new_price
        
        # Generate realistic volume (between 1M and 50M shares)
        volume = random.randint(1000000, 50000000)
        
        # Generate number of trades (roughly volume/100 to volume/1000)
        num_trades = random.randint(volume // 1000, volume // 100)
        
        # Calculate volume weighted average price
        vwap = (high_price + low_price + close_price) / 3
        
        # Current timestamp in ISO format
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        
        return {
            "T": "T",  # Trade type indicator
            "S": symbol,  # Symbol
            "o": round(open_price, 2),  # Open price
            "h": round(high_price, 2),  # High price
            "l": round(low_price, 2),   # Low price
            "c": round(close_price, 2), # Close price
            "v": volume,  # Volume
            "t": timestamp,  # Timestamp
            "n": num_trades,  # Number of trades
            "vw": round(vwap, 2)  # Volume weighted average price
        }
    
    def generate_batch_records(self, batch_size: int = None) -> List[Dict]:
        """Generate a batch of stock records (JSON array as expected by Spark app)"""
        if batch_size is None:
            batch_size = random.randint(1, 5)  # Random batch size 1-5
        
        records = []
        for _ in range(batch_size):
            # Randomly select a symbol
            symbol = random.choice(self.symbols)
            record = self.generate_single_stock_record(symbol)
            records.append(record)
        
        return records
    
    def send_message(self, records: List[Dict], key: str = None):
        """Send a batch of records to Kafka"""
        if not self.producer:
            raise RuntimeError("Producer not initialized. Call connect() first.")
        
        try:
            future = self.producer.send(
                topic=self.topic,
                value=records,  # Send as JSON array
                key=key
            )
            
            # Wait for the message to be sent
            record_metadata = future.get(timeout=10)
            logger.info(f"Sent {len(records)} records to {record_metadata.topic}:{record_metadata.partition}:{record_metadata.offset}")
            
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            raise
    
    def simulate_continuous_stream(self, duration_seconds: int = 300, 
                                 messages_per_minute: int = 60, 
                                 batch_size_range: tuple = (1, 5)):
        """
        Simulate continuous stream of stock data
        
        Args:
            duration_seconds: How long to run the simulation
            messages_per_minute: How many message batches to send per minute
            batch_size_range: Range for number of records per batch (min, max)
        """
        logger.info(f"Starting simulation for {duration_seconds} seconds")
        logger.info(f"Sending {messages_per_minute} batches per minute")
        logger.info(f"Batch size range: {batch_size_range}")
        
        interval = 60.0 / messages_per_minute  # Seconds between messages
        start_time = time.time()
        message_count = 0
        
        try:
            while time.time() - start_time < duration_seconds:
                # Generate batch
                batch_size = random.randint(*batch_size_range)
                records = self.generate_batch_records(batch_size)
                
                # Send to Kafka
                self.send_message(records, key=f"batch_{message_count}")
                message_count += 1
                
                # Log sample of what was sent
                if message_count % 10 == 0:
                    sample_symbols = [r['S'] for r in records]
                    sample_prices = [r['c'] for r in records]
                    logger.info(f"Batch #{message_count}: {sample_symbols} at prices {sample_prices}")
                
                # Wait for next interval
                time.sleep(interval)
                
        except KeyboardInterrupt:
            logger.info("Simulation interrupted by user")
        finally:
            logger.info(f"Simulation completed. Sent {message_count} message batches")
    
    def send_sample_batches(self, num_batches: int = 5):
        """Send a few sample batches for testing"""
        logger.info(f"Sending {num_batches} sample batches")
        
        for i in range(num_batches):
            records = self.generate_batch_records()
            self.send_message(records, key=f"sample_batch_{i}")
            
            # Print what we're sending
            print(f"\nBatch {i+1}:")
            for record in records:
                print(f"  {record['S']}: ${record['c']} (vol: {record['v']:,})")
            
            time.sleep(1)  # Small delay between batches
    
    def close(self):
        """Close the Kafka producer"""
        if self.producer:
            self.producer.flush()
            self.producer.close()
            logger.info("Kafka producer closed")

def main():
    # Configuration
    KAFKA_SERVERS = "192.168.49.2:32100"
    KAFKA_TOPIC = "iex-topic-1"
    
    simulator = StockDataSimulator(KAFKA_SERVERS, KAFKA_TOPIC)
    
    try:
        simulator.connect()
        
        print("Choose simulation mode:")
        print("1. Send 5 sample batches (for quick testing)")
        print("2. Continuous stream simulation")
        
        choice = input("Enter choice (1 or 2): ").strip()
        
        if choice == "1":
            simulator.send_sample_batches()
        elif choice == "2":
            duration = int(input("Duration in seconds (default 300): ") or 300)
            rate = int(input("Messages per minute (default 60): ") or 60)
            simulator.simulate_continuous_stream(duration, rate)
        else:
            print("Invalid choice")
            
    except Exception as e:
        logger.error(f"Simulation failed: {e}")
    finally:
        simulator.close()

if __name__ == "__main__":
    main()