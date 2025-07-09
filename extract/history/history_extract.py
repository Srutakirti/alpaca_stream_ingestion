from datetime import datetime, timedelta
import os
import logging
import requests
import pandas as pd
from typing import List, Dict, Any, Generator
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, TimestampType, DoubleType, LongType
import time
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import yaml

@dataclass
class AlpacaConfig:
    """Configuration for Alpaca API"""
    api_key: str
    api_secret: str
    base_url: str = "https://data.alpaca.markets/v2"
    earliest_date: str = "2015-01-01"  # Alpaca's earliest available data

@dataclass
class IcebergConfig:
    """Configuration for Iceberg table"""
    warehouse_path: str
    database: str
    table: str

class StockDataIngestion:
    def __init__(self, alpaca_config: AlpacaConfig, iceberg_config: IcebergConfig):
        # Store configs and set up logger and Spark session
        self.alpaca_config = alpaca_config
        self.iceberg_config = iceberg_config
        self.logger = self._setup_logging()
        self.spark = self._setup_spark()

    @staticmethod
    def _setup_logging() -> logging.Logger:
        """Set up logging configuration"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger(__name__)

    def _setup_spark(self) -> SparkSession:
        """Initialize Spark session with Iceberg support"""
        return (SparkSession.builder
                .appName("Alpaca-Stock-Bars-Ingestion")
                .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
                .config("spark.sql.catalog.spark_catalog", "org.apache.iceberg.spark.SparkSessionCatalog")
                .config("spark.sql.catalog.spark_catalog.type", "hive")
                .config("spark.sql.catalog.local", "org.apache.iceberg.spark.SparkCatalog")
                .config("spark.sql.catalog.local.type", "hadoop")
                .config("spark.sql.catalog.local.warehouse", self.iceberg_config.warehouse_path)
                .getOrCreate())

    def _get_headers(self) -> Dict[str, str]:
        """Get API headers with authentication"""
        return {
            "APCA-API-KEY-ID": self.alpaca_config.api_key,
            "APCA-API-SECRET-KEY": self.alpaca_config.api_secret
        }

    def get_all_symbols(self) -> List[str]:
        """Fetch all available trading symbols from Alpaca"""
        url = f"{self.alpaca_config.base_url}/stocks/snapshots"
        response = requests.get(url, headers=self._get_headers())
        if response.status_code == 200:
            return list(response.json().keys())
        else:
            raise Exception(f"Failed to fetch symbols: {response.text}")

    def fetch_bars(self, symbols: List[str], start_date: str, end_date: str) -> Generator[Dict[str, Any], None, None]:
        """
        Fetch historical bars for given symbols from Alpaca API.
        Handles pagination using next_page_token.
        """
        url = f"{self.alpaca_config.base_url}/stocks/bars"
        params = {
            "symbols": ",".join(symbols),
            "start": start_date,
            "end": end_date,
            "timeframe": "1Day",
            "adjustment": "raw",
            "limit": 10000
        }

        while True:
            response = requests.get(url, headers=self._get_headers(), params=params)
            if response.status_code != 200:
                raise Exception(f"API request failed: {response.text}")

            data = response.json()
            yield from data.get("bars", {}).items()

            next_page_token = data.get("next_page_token")
            if not next_page_token:
                break

            params["page_token"] = next_page_token
            time.sleep(0.5)  # Rate limiting

    def create_iceberg_table(self):
        """
        Create Iceberg table if it doesn't exist.
        Defines schema and creates empty table if needed.
        """
        schema = StructType([
            StructField("symbol", StringType(), False),
            StructField("timestamp", TimestampType(), False),
            StructField("open", DoubleType(), False),
            StructField("high", DoubleType(), False),
            StructField("low", DoubleType(), False),
            StructField("close", DoubleType(), False),
            StructField("volume", LongType(), False),
            StructField("trade_count", LongType(), False),
            StructField("vwap", DoubleType(), False)
        ])

        self.spark.sql(f"CREATE DATABASE IF NOT EXISTS {self.iceberg_config.database}")

        table_path = f"{self.iceberg_config.database}.{self.iceberg_config.table}"
        # Check if table exists, if not, create it
        if not self.spark._jsparkSession.catalog().tableExists(table_path):
            empty_df = self.spark.createDataFrame([], schema)
            empty_df.writeTo(table_path).using("iceberg").createOrReplace()

    def process_batch(self, symbols: List[str], start_date: str, end_date: str):
        """
        Process a batch of symbols and write their bar data to Iceberg.
        Fetches bars, transforms to DataFrame, and appends to Iceberg table.
        """
        try:
            bars_data = []
            for symbol, bars in self.fetch_bars(symbols, start_date, end_date):
                for bar in bars:
                    bars_data.append({
                        "symbol": symbol,
                        "timestamp": datetime.fromisoformat(bar["t"].replace('Z', '+00:00')),
                        "open": bar["o"],
                        "high": bar["h"],
                        "low": bar["l"],
                        "close": bar["c"],
                        "volume": bar["v"],
                        "trade_count": bar["n"],
                        "vwap": bar["vw"]
                    })

            if bars_data:
                df = pd.DataFrame(bars_data)
                spark_df = self.spark.createDataFrame(df)
                spark_df.writeTo(f"{self.iceberg_config.database}.{self.iceberg_config.table}").append()

            self.logger.info(f"Processed batch of {len(symbols)} symbols from {start_date} to {end_date}")

        except Exception as e:
            self.logger.error(f"Error processing batch: {str(e)}")

    def run_ingestion(self):
        """
        Main ingestion process.
        Creates table, fetches all symbols, and processes them in yearly and batch-wise chunks using threads.
        """
        try:
            self.create_iceberg_table()

            symbols = self.get_all_symbols()
            self.logger.info(f"Found {len(symbols)} symbols to process")

            # Process in batches of 100 symbols
            batch_size = 100
            symbol_batches = [symbols[i:i + batch_size] for i in range(0, len(symbols), batch_size)]

            # Process each year separately to handle large amounts of data
            current_year = datetime.now().year
            start_year = int(self.alpaca_config.earliest_date.split('-')[0])

            for year in range(start_year, current_year + 1):
                start_date = f"{year}-01-01"
                end_date = f"{year}-12-31" if year != current_year else datetime.now().strftime('%Y-%m-%d')

                self.logger.info(f"Processing year {year}")

                # Use ThreadPoolExecutor to process batches in parallel
                with ThreadPoolExecutor(max_workers=5) as executor:
                    for batch in symbol_batches:
                        executor.submit(self.process_batch, batch, start_date, end_date)

        except Exception as e:
            self.logger.error(f"Ingestion failed: {str(e)}")
        finally:
            self.spark.stop()

def load_config(config_path: str) -> Dict[str, Any]:
    """Load configuration from YAML file"""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)

def main():
    # Load configuration from YAML file
    config = load_config('config/config.yaml')

    # Set up Alpaca and Iceberg configs
    alpaca_config = AlpacaConfig(
        api_key=os.getenv('ALPACA_API_KEY'),
        api_secret=os.getenv('ALPACA_API_SECRET')
    )

    iceberg_config = IcebergConfig(
        warehouse_path=config['iceberg']['warehouse_path'],
        database=config['iceberg']['database'],
        table=config['iceberg']['table']
    )

    # Run ingestion process
    ingestion = StockDataIngestion(alpaca_config, iceberg_config)
    ingestion.run_ingestion()

if __name__ == "__main__":
    main()