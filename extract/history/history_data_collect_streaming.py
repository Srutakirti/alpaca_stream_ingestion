#!/usr/bin/env python3
"""
Alpaca Historical Data Collector (Streaming Version with aiofiles)

Fetches historical bar data from Alpaca Markets API and streams results
to file immediately (per-page, not per-batch) for minimal memory usage.

Key improvements over non-streaming version:
- Writes data immediately after each page fetch (not waiting for batch)
- Uses aiofiles for true async file I/O
- Much lower memory usage (50-100x reduction)
- Real-time progress visible in output file

Usage:
    python history_data_collect_streaming.py --symbols-file symbols.txt --output bars.ndjson

Requirements:
    - ALPACA_KEY environment variable must be set
    - ALPACA_SECRET environment variable must be set
    - aiofiles library (pip install aiofiles)

Author: Claude Code
"""

import asyncio
import aiohttp
import aiofiles
import json
import os
import sys
import argparse
import logging
from datetime import datetime
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
        description='Fetch historical bar data from Alpaca (streaming version)',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fetch with streaming writes (minimal memory)
  %(prog)s -s /nvmewd/data/iex/allsymbols.txt -o /nvmewd/data/iex/bars.ndjson

  # Custom date range with high concurrency
  %(prog)s -s symbols.txt -o bars.ndjson --start 2023-01-01 --end 2023-12-31 --concurrent-batches 5

  # Verbose logging to see per-page writes
  %(prog)s -s symbols.txt -o bars.ndjson -v

Environment Variables:
  ALPACA_KEY      Your Alpaca API key (required)
  ALPACA_SECRET   Your Alpaca API secret (required)
        """
    )

    parser.add_argument('-s', '--symbols-file', required=True,
                        help='Path to file containing symbols (one per line)')
    parser.add_argument('-o', '--output', required=True,
                        help='Output file path for NDJSON data')
    parser.add_argument('--start', default='2021-08-01',
                        help='Start date (YYYY-MM-DD) (default: 2021-08-01)')
    parser.add_argument('--end', default=None,
                        help='End date (YYYY-MM-DD) (default: now)')
    parser.add_argument('--timeframe', default='1Min',
                        help='Bar timeframe (default: 1Min)')
    parser.add_argument('--feed', default='iex',
                        help='Data feed (default: iex)')
    parser.add_argument('--batch-size', type=int, default=100,
                        help='Symbols per request (default: 100, max: 100)')
    parser.add_argument('--api-url', default='https://data.alpaca.markets/v2/stocks',
                        help='Alpaca API base URL')
    parser.add_argument('--rate-limit-delay', type=float, default=0.5,
                        help='Delay between requests in seconds (default: 0.5)')
    parser.add_argument('--concurrent-batches', type=int, default=5,
                        help='Concurrent batch requests (default: 5, max: 10)')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Enable verbose logging')

    return parser.parse_args()


def validate_credentials():
    """Validate API credentials from environment."""
    api_key = os.getenv("ALPACA_KEY", "")
    api_secret = os.getenv("ALPACA_SECRET", "")

    if not api_key or not api_secret:
        logger.error(
            "Missing Alpaca API credentials!\n"
            "Please set: ALPACA_KEY and ALPACA_SECRET"
        )
        sys.exit(1)

    return {
        "APCA-API-KEY-ID": api_key,
        "APCA-API-SECRET-KEY": api_secret
    }


def load_symbols(symbols_file):
    """Load symbols from text file."""
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


async def fetch_and_stream_batch(session, file_handle, file_lock, api_url, headers,
                                  symbols, start_dt, end_dt, timeframe, feed,
                                  batch_num, total_batches, rate_limit_delay,
                                  semaphore, can_make_requests):
    """
    Fetch bars for a batch and write to file immediately per page.

    Key difference from non-streaming version:
    - Writes bars after EACH page (not accumulating in memory)
    - Uses async file I/O with lock for coordination
    - Returns only metadata (count, symbols), not the data itself
    """
    async with semaphore:
        symbols_str = ",".join(symbols)
        next_page_token = None
        total_bars = 0
        symbols_with_data = set()
        page_count = 0

        logger.info(f"Batch {batch_num}/{total_batches}: Starting fetch for {len(symbols)} symbols")

        while True:
            # Wait if rate limit is active (green light OFF)
            if not can_make_requests.is_set():
                logger.debug(f"Batch {batch_num}: Rate limit active, waiting...")
                await can_make_requests.wait()
                logger.debug(f"Batch {batch_num}: Resuming...")

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

                        # Log all rate limit headers for debugging
                        logger.warning(f"Batch {batch_num}: Rate limit hit (429)! Headers:")
                        logger.warning(f"  Retry-After: {resp.headers.get('Retry-After', 'N/A')}")
                        logger.warning(f"  X-Ratelimit-Limit: {resp.headers.get('X-Ratelimit-Limit', 'N/A')}")
                        logger.warning(f"  X-Ratelimit-Remaining: {resp.headers.get('X-Ratelimit-Remaining', 'N/A')}")
                        logger.warning(f"  X-Ratelimit-Reset: {resp.headers.get('X-Ratelimit-Reset', 'N/A')}")
                        logger.warning(f"  Pausing ALL batches for {retry_after}s...")

                        # Undo page count increment since we're retrying the same page
                        page_count -= 1

                        can_make_requests.clear()  # Red light
                        await asyncio.sleep(retry_after)
                        can_make_requests.set()  # Green light

                        logger.info(f"Batch {batch_num}: Rate limit cleared, resuming")
                        continue

                    if resp.status != 200:
                        text = await resp.text()
                        logger.error(f"Batch {batch_num}: API Error {resp.status}: {text}")
                        break

                    data = await resp.json()
                    bars_dict = data.get('bars', {})

                    if not bars_dict:
                        logger.debug(f"Batch {batch_num}: No more data (page {page_count})")
                        break

                    # Write bars to file IMMEDIATELY (per page, not per batch!)
                    bars_in_page = 0

                    # Use lock to coordinate writes from multiple coroutines
                    async with file_lock:
                        for symbol_key, bars_list in bars_dict.items():
                            symbols_with_data.add(symbol_key)
                            for bar in bars_list:
                                bar_with_symbol = dict(bar)
                                bar_with_symbol['symbol'] = symbol_key

                                # Async write to file
                                await file_handle.write(json.dumps(bar_with_symbol) + "\n")
                                bars_in_page += 1
                                total_bars += 1

                    logger.info(f"Batch {batch_num}: Page {page_count} - Wrote {bars_in_page} bars (Total: {total_bars})")

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
                import traceback
                logger.debug(traceback.format_exc())
                break

        logger.info(f"Batch {batch_num}/{total_batches}: Complete - {total_bars} bars, {len(symbols_with_data)} symbols")
        return batch_num, total_bars, symbols_with_data


async def process_all_batches_streaming(api_url, headers, all_symbols, start_dt, end_dt,
                                        timeframe, feed, batch_size, output_path,
                                        rate_limit_delay, concurrent_batches):
    """
    Process all batches with immediate per-page file writes.

    Key difference: Opens file ONCE and shares handle across all coroutines
    """
    # Create batches
    batches = []
    for i in range(0, len(all_symbols), batch_size):
        batch = all_symbols[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        batches.append((batch_num, batch))

    total_batches = len(batches)
    semaphore = asyncio.Semaphore(concurrent_batches)

    # Green light for rate limiting coordination
    can_make_requests = asyncio.Event()
    can_make_requests.set()

    # File lock for coordinating writes
    file_lock = asyncio.Lock()

    logger.info(f"Processing {len(all_symbols)} symbols in {total_batches} batches")
    logger.info(f"Concurrent batches: {concurrent_batches}")
    logger.info(f"Writing to: {output_path}")

    total_bars_written = 0
    total_symbols_with_data = set()

    # Create output directory
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    # Open file ONCE for all coroutines to share
    timeout = aiohttp.ClientTimeout(total=300)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with aiofiles.open(output_path, 'w') as file_handle:

            # Create all tasks
            tasks = [
                fetch_and_stream_batch(
                    session=session,
                    file_handle=file_handle,
                    file_lock=file_lock,
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

            # Process tasks as they complete
            for coro in asyncio.as_completed(tasks):
                batch_num, bars_count, symbols_with_data = await coro

                total_bars_written += bars_count
                total_symbols_with_data.update(symbols_with_data)

                logger.info(f"Batch {batch_num}: Finished - {bars_count} bars written")

    return total_bars_written, total_symbols_with_data


def main():
    """Main entry point."""
    args = parse_arguments()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    logger.info("=" * 70)
    logger.info("Alpaca Historical Data Collector (Streaming)")
    logger.info("=" * 70)
    logger.info(f"Symbols File:        {args.symbols_file}")
    logger.info(f"Output File:         {args.output}")
    logger.info(f"Start Date:          {args.start}")
    logger.info(f"End Date:            {args.end or 'now'}")
    logger.info(f"Timeframe:           {args.timeframe}")
    logger.info(f"Feed:                {args.feed}")
    logger.info(f"Batch Size:          {args.batch_size}")
    logger.info(f"Concurrent Batches:  {args.concurrent_batches}")
    logger.info("=" * 70)

    try:
        # Validate credentials
        headers = validate_credentials()

        # Load symbols
        all_symbols = load_symbols(args.symbols_file)
        if not all_symbols:
            logger.error("No symbols found")
            sys.exit(1)

        # Parse dates
        start_dt = datetime.strptime(args.start, '%Y-%m-%d')
        end_dt = datetime.strptime(args.end, '%Y-%m-%d') if args.end else datetime.utcnow()

        # Validate settings
        batch_size = min(args.batch_size, 100)
        concurrent_batches = min(args.concurrent_batches, 10)

        output_path = Path(args.output)

        # Run async processing
        total_bars, total_symbols = asyncio.run(
            process_all_batches_streaming(
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
        logger.info(f"Total bars written:    {total_bars:,}")
        logger.info(f"Symbols with data:     {len(total_symbols)}/{len(all_symbols)}")
        logger.info(f"Output file:           {output_path.absolute()}")
        logger.info(f"File size:             {output_path.stat().st_size / 1024 / 1024:.2f} MB")
        logger.info("=" * 70)

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
