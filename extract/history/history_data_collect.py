#!/usr/bin/env python3
"""
Alpaca Historical Data Collector - CLI Tool

Fetches historical bar data for multiple symbols from Alpaca Markets API
and streams the results to an NDJSON file.

Usage:
    python history_data_collect.py --symbols-file /path/to/symbols.txt --output /path/to/bars.ndjson
    python history_data_collect.py -s symbols.txt -o bars.ndjson --start 2023-01-01 --end 2023-12-31
    python history_data_collect.py -s symbols.txt -o bars.ndjson --timeframe 1Hour --batch-size 50

Requirements:
    - ALPACA_KEY environment variable must be set
    - ALPACA_SECRET environment variable must be set

Author: Claude Code
"""

import asyncio
import aiohttp
import json
import os
import sys
import argparse
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Fetch historical bar data from Alpaca Markets API',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fetch data for all symbols in file (async with 5 concurrent batches)
  %(prog)s -s /nvmewd/data/iex/allsymbols.txt -o /nvmewd/data/iex/bars.ndjson

  # Fetch data for specific date range
  %(prog)s -s symbols.txt -o bars.ndjson --start 2023-01-01 --end 2023-12-31

  # Fetch hourly data instead of minute bars
  %(prog)s -s symbols.txt -o bars.ndjson --timeframe 1Hour

  # Use more concurrent batches for faster processing (max: 10)
  %(prog)s -s symbols.txt -o bars.ndjson --concurrent-batches 10

  # Process in smaller batches with fewer concurrent requests
  %(prog)s -s symbols.txt -o bars.ndjson --batch-size 50 --concurrent-batches 3

  # Use verbose logging to see detailed progress
  %(prog)s -s symbols.txt -o bars.ndjson -v

Environment Variables:
  ALPACA_KEY      Your Alpaca API key (required)
  ALPACA_SECRET   Your Alpaca API secret (required)
        """
    )

    parser.add_argument(
        '-s', '--symbols-file',
        required=True,
        help='Path to file containing symbols (one per line)'
    )

    parser.add_argument(
        '-o', '--output',
        required=True,
        help='Output file path for NDJSON data'
    )

    parser.add_argument(
        '--start',
        default='2021-08-01',
        help='Start date (YYYY-MM-DD) (default: 2021-08-01)'
    )

    parser.add_argument(
        '--end',
        default=None,
        help='End date (YYYY-MM-DD) (default: now)'
    )

    parser.add_argument(
        '--timeframe',
        default='1Min',
        help='Bar timeframe (default: 1Min). Options: 1Min, 5Min, 15Min, 1Hour, 1Day'
    )

    parser.add_argument(
        '--feed',
        default='iex',
        help='Data feed (default: iex). Options: iex, sip'
    )

    parser.add_argument(
        '--batch-size',
        type=int,
        default=100,
        help='Number of symbols to fetch per request (default: 100, max: 100)'
    )

    parser.add_argument(
        '--api-url',
        default='https://data.alpaca.markets/v2/stocks',
        help='Alpaca API base URL (default: data.alpaca.markets)'
    )

    parser.add_argument(
        '--rate-limit-delay',
        type=float,
        default=0.5,
        help='Delay between API requests in seconds (default: 0.5)'
    )

    parser.add_argument(
        '--concurrent-batches',
        type=int,
        default=5,
        help='Number of concurrent batch requests (default: 5, max: 10)'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    return parser.parse_args()


def validate_credentials():
    """
    Validate that required API credentials are set in environment variables.

    Returns:
        dict: Headers dictionary with API credentials

    Raises:
        SystemExit: If credentials are not set
    """
    api_key = os.getenv("ALPACA_KEY", "")
    api_secret = os.getenv("ALPACA_SECRET", "")

    if api_key == "" or api_secret == "":
        logger.error(
            "Missing Alpaca API credentials!\n"
            "Please set environment variables:\n"
            "  export ALPACA_KEY='your_key'\n"
            "  export ALPACA_SECRET='your_secret'"
        )
        sys.exit(1)

    return {
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": api_secret
    }


def load_symbols(symbols_file):
    """
    Load symbols from a text file (one symbol per line).

    Args:
        symbols_file (str): Path to symbols file

    Returns:
        list: List of symbol strings

    Raises:
        FileNotFoundError: If symbols file doesn't exist
    """
    symbols_path = Path(symbols_file)

    if not symbols_path.exists():
        raise FileNotFoundError(f"Symbols file not found: {symbols_file}")

    with open(symbols_path, 'r') as f:
        symbols = [line.strip() for line in f if line.strip()]

    logger.info(f"Loaded {len(symbols)} symbols from {symbols_file}")
    return symbols


def isoformat(dt):
    """Convert datetime to ISO format string."""
    return dt.isoformat(timespec='seconds') + 'Z'


async def fetch_bars_for_symbols(session, api_url, headers, symbols, start_dt, end_dt, timeframe, feed, batch_num, total_batches, rate_limit_delay, semaphore, can_make_requests):
    """
    Async fetch historical bars for a batch of symbols.

    Args:
        session (aiohttp.ClientSession): HTTP session
        api_url (str): Alpaca API base URL
        headers (dict): API request headers
        symbols (list): List of symbols to fetch
        start_dt (datetime): Start date
        end_dt (datetime): End date
        timeframe (str): Bar timeframe
        feed (str): Data feed
        batch_num (int): Batch number for logging
        total_batches (int): Total batches for logging
        rate_limit_delay (float): Delay between requests
        semaphore (asyncio.Semaphore): Concurrency limiter
        can_make_requests (asyncio.Event): Green light flag (set=go, clear=stop)

    Returns:
        tuple: (batch_num, bars_data_list, symbols_with_data)
    """
    async with semaphore:  # Limit concurrent requests
        symbols_str = ",".join(symbols)
        next_page_token = None
        all_bars = []
        symbols_with_data = set()
        page_count = 0

        logger.info(f"Batch {batch_num}/{total_batches}: Fetching data for {len(symbols)} symbols...")

        while True:
            # Wait if rate limit is active (green light OFF)
            if not can_make_requests.is_set():
                logger.debug(f"Batch {batch_num}: Rate limit active, waiting for green light...")
                await can_make_requests.wait()  # Block until green light turns ON
                logger.debug(f"Batch {batch_num}: Green light ON, resuming...")

            page_count += 1
            params = {
                "start": isoformat(start_dt),
                "end": isoformat(end_dt),
                "timeframe": timeframe,
                "limit": 10000,
                "feed": feed,
                "symbols": symbols_str
            }

            if next_page_token:
                params['page_token'] = next_page_token

            url = f"{api_url}/bars"

            try:
                async with session.get(url, params=params, headers=headers) as resp:
                    # Handle rate limiting
                    if resp.status == 429:
                        retry_after = int(resp.headers.get('Retry-After', 60))
                        logger.warning(f"Batch {batch_num}: Rate limit hit! Pausing ALL batches for {retry_after}s...")

                        # Turn OFF green light → ALL batches stop at next check
                        can_make_requests.clear()

                        # Wait for rate limit to expire (non-blocking)
                        await asyncio.sleep(retry_after)

                        # Turn ON green light → ALL batches resume
                        can_make_requests.set()
                        logger.info(f"Batch {batch_num}: Rate limit expired, resuming all batches")
                        continue  # Retry this page

                    if resp.status != 200:
                        text = await resp.text()
                        logger.error(f"Batch {batch_num}: API Error {resp.status}: {text}")
                        break

                    data = await resp.json()
                    bars_dict = data.get('bars', {})

                    if not bars_dict:
                        logger.debug(f"Batch {batch_num}: No more data (page {page_count})")
                        break

                    # Collect bars for this page
                    bars_in_page = 0
                    for symbol_key, bars_list in bars_dict.items():
                        symbols_with_data.add(symbol_key)
                        for bar in bars_list:
                            bar_with_symbol = dict(bar)
                            bar_with_symbol['symbol'] = symbol_key
                            all_bars.append(bar_with_symbol)
                            bars_in_page += 1

                    logger.info(f"Batch {batch_num}: Page {page_count} - {bars_in_page} bars for {len(bars_dict)} symbols")

                    next_page_token = data.get('next_page_token')
                    if not next_page_token:
                        break

                    # Rate limiting between pages
                    await asyncio.sleep(rate_limit_delay)

            except aiohttp.ClientError as e:
                logger.error(f"Batch {batch_num}: Network error: {e}")
                break
            except Exception as e:
                logger.error(f"Batch {batch_num}: Error: {e}")
                break

        logger.info(f"Batch {batch_num}/{total_batches}: Fetched {len(all_bars)} bars for {len(symbols_with_data)} symbols")
        return batch_num, all_bars, symbols_with_data


async def process_all_batches(api_url, headers, all_symbols, start_dt, end_dt, timeframe, feed, batch_size, output_path, rate_limit_delay, concurrent_batches):
    """
    Process all symbol batches concurrently and stream to file.

    Args:
        api_url (str): Alpaca API base URL
        headers (dict): API request headers
        all_symbols (list): All symbols to fetch
        start_dt (datetime): Start date
        end_dt (datetime): End date
        timeframe (str): Bar timeframe
        feed (str): Data feed
        batch_size (int): Symbols per batch
        output_path (Path): Output file path
        rate_limit_delay (float): Delay between requests
        concurrent_batches (int): Max concurrent batches

    Returns:
        tuple: (total_bars_written, total_symbols_with_data)
    """
    # Create batches
    batches = []
    for i in range(0, len(all_symbols), batch_size):
        batch = all_symbols[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        batches.append((batch_num, batch))

    total_batches = len(batches)
    semaphore = asyncio.Semaphore(concurrent_batches)

    # Event flag: when SET = can proceed, when CLEAR = must wait
    # Think of it as a "green light" - ON = go, OFF = stop
    can_make_requests = asyncio.Event()
    can_make_requests.set()  # Start with green light (can proceed)

    logger.info(f"Processing {len(all_symbols)} symbols in {total_batches} batches with {concurrent_batches} concurrent requests...")

    total_bars_written = 0
    total_symbols_with_data = set()

    # Create aiohttp session
    timeout = aiohttp.ClientTimeout(total=300)  # 5 minute timeout per request
    async with aiohttp.ClientSession(timeout=timeout) as session:
        # Process batches concurrently
        tasks = [
            fetch_bars_for_symbols(
                session=session,
                api_url=api_url,
                headers=headers,
                symbols=batch,
                start_dt=start_dt,
                end_dt=end_dt,
                timeframe=timeframe,
                feed=feed,
                batch_num=batch_num,
                total_batches=total_batches,
                rate_limit_delay=rate_limit_delay,
                semaphore=semaphore,
                can_make_requests=can_make_requests
            )
            for batch_num, batch in batches
        ]

        # Open output file for streaming
        with open(output_path, 'w') as output_file:
            # Process tasks as they complete
            for coro in asyncio.as_completed(tasks):
                batch_num, bars_data, symbols_with_data = await coro

                # Stream bars to file
                for bar in bars_data:
                    output_file.write(json.dumps(bar) + "\n")

                total_bars_written += len(bars_data)
                total_symbols_with_data.update(symbols_with_data)

                logger.info(f"Batch {batch_num}/{total_batches}: Wrote {len(bars_data)} bars to file (Total: {total_bars_written:,})")

    return total_bars_written, total_symbols_with_data


def main():
    """Main entry point for the script."""
    args = parse_arguments()

    # Enable verbose logging if requested
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Print configuration summary
    logger.info("=" * 70)
    logger.info("Alpaca Historical Data Collector (Async)")
    logger.info("=" * 70)
    logger.info(f"Symbols File:        {args.symbols_file}")
    logger.info(f"Output File:         {args.output}")
    logger.info(f"Start Date:          {args.start}")
    logger.info(f"End Date:            {args.end or 'now'}")
    logger.info(f"Timeframe:           {args.timeframe}")
    logger.info(f"Feed:                {args.feed}")
    logger.info(f"Batch Size:          {args.batch_size}")
    logger.info(f"Concurrent Batches:  {args.concurrent_batches}")
    logger.info(f"API URL:             {args.api_url}")
    logger.info("=" * 70)

    try:
        # Validate API credentials
        headers = validate_credentials()

        # Load symbols from file
        all_symbols = load_symbols(args.symbols_file)

        if not all_symbols:
            logger.error("No symbols found in file")
            sys.exit(1)

        # Parse dates
        start_dt = datetime.strptime(args.start, '%Y-%m-%d')
        end_dt = datetime.strptime(args.end, '%Y-%m-%d') if args.end else datetime.utcnow()

        # Validate batch size and concurrent batches
        batch_size = min(args.batch_size, 100)  # Alpaca limit
        if batch_size != args.batch_size:
            logger.warning(f"Batch size reduced to maximum allowed: {batch_size}")

        concurrent_batches = min(args.concurrent_batches, 10)  # Limit concurrency
        if concurrent_batches != args.concurrent_batches:
            logger.warning(f"Concurrent batches reduced to maximum allowed: {concurrent_batches}")

        # Create output directory if needed
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Process all batches concurrently using asyncio
        total_bars_written, total_symbols_with_data = asyncio.run(
            process_all_batches(
                api_url=args.api_url,
                headers=headers,
                all_symbols=all_symbols,
                start_dt=start_dt,
                end_dt=end_dt,
                timeframe=args.timeframe,
                feed=args.feed,
                batch_size=batch_size,
                output_path=output_path,
                rate_limit_delay=args.rate_limit_delay,
                concurrent_batches=concurrent_batches
            )
        )

        # Summary
        logger.info("=" * 70)
        logger.info("Collection Complete")
        logger.info("=" * 70)
        logger.info(f"Total bars written:        {total_bars_written:,}")
        logger.info(f"Symbols with data:         {len(total_symbols_with_data)}/{len(all_symbols)}")
        logger.info(f"Symbols without data:      {len(all_symbols) - len(total_symbols_with_data)}")
        logger.info(f"Output file:               {output_path.absolute()}")
        logger.info(f"Output file size:          {output_path.stat().st_size / 1024 / 1024:.2f} MB")
        logger.info("=" * 70)

        if total_bars_written == 0:
            logger.warning("No data was written. Check date range and symbol availability.")
            sys.exit(0)

        logger.info("Operation completed successfully")
        sys.exit(0)

    except KeyboardInterrupt:
        logger.info("\nOperation cancelled by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        logger.debug(traceback.format_exc())
        sys.exit(1)


if __name__ == "__main__":
    main()
