#!/usr/bin/env python3
"""
Simple script to fetch Alpaca bars data and save raw JSON response.
Just for testing/inspecting API responses.
"""

import requests
import json
import os
from datetime import datetime

# Configuration - Edit these values
SYMBOLS = "AAPL,MSFT,TSLA"  # Comma-separated symbols
START_DATE = "2024-11-01"
END_DATE = "2024-11-05"
TIMEFRAME = "1Hour"
FEED = "iex"
OUTPUT_FILE = "/nvmewd/data/iex/test_response.json"

# API Configuration
API_URL = "https://data.alpaca.markets/v2/stocks/bars"
HEADERS = {
    "APCA-API-KEY-ID": os.getenv("ALPACA_KEY", ""),
    "APCA-API-SECRET-KEY": os.getenv("ALPACA_SECRET", "")
}

def main():
    print(f"Fetching bars for: {SYMBOLS}")
    print(f"Date range: {START_DATE} to {END_DATE}")
    print(f"Timeframe: {TIMEFRAME}")
    print(f"Feed: {FEED}")
    print()

    # Build request parameters
    params = {
        "symbols": SYMBOLS,
        "start": START_DATE,
        "end": END_DATE,
        "timeframe": TIMEFRAME,
        "feed": FEED,
        "limit": 10000
    }

    # Make API request
    print("Making API request...")
    response = requests.get(API_URL, headers=HEADERS, params=params)

    print(f"Response status: {response.status_code}")
    print()

    if response.status_code != 200:
        print(f"Error: {response.text}")
        return

    # Get JSON response
    data = response.json()

    # Print summary
    if 'bars' in data:
        print("Response structure:")
        for symbol, bars in data['bars'].items():
            print(f"  {symbol}: {len(bars)} bars")
    print()

    # Save to file
    print(f"Saving response to: {OUTPUT_FILE}")
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(data, f, indent=2)

    print("Done!")
    print()
    print("Sample bar (first symbol):")
    if 'bars' in data and data['bars']:
        first_symbol = list(data['bars'].keys())[0]
        if data['bars'][first_symbol]:
            print(json.dumps(data['bars'][first_symbol][0], indent=2))

if __name__ == "__main__":
    main()
