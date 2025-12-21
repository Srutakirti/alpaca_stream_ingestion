#!/usr/bin/env python3
"""
Alpaca IEX Symbols Fetcher - CLI Tool

Fetches all active, tradable IEX symbols from Alpaca Markets API and saves them
to a specified output file (one symbol per line).

Usage:
    python get_symbols.py
    python get_symbols.py --output /path/to/symbols.txt
    python get_symbols.py -o symbols.txt --exchange NASDAQ
    python get_symbols.py --api-url https://api.alpaca.markets/v2/assets

Requirements:
    - ALPACA_KEY environment variable must be set
    - ALPACA_SECRET environment variable must be set

Author: Claude Code
"""

import requests
import os
import sys
import argparse
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


def parse_arguments():
    """
    Parse command-line arguments.

    Returns:
        Namespace: Parsed arguments containing output path, exchange, etc.
    """
    parser = argparse.ArgumentParser(
        description='Fetch tradable symbols from Alpaca Markets API',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fetch IEX symbols to default file
  %(prog)s

  # Fetch to custom output path
  %(prog)s --output /data/iex_symbols.txt

  # Fetch NASDAQ symbols
  %(prog)s -o nasdaq.txt --exchange NASDAQ

  # Use production API instead of paper
  %(prog)s --api-url https://api.alpaca.markets/v2/assets

Environment Variables:
  ALPACA_KEY      Your Alpaca API key (required)
  ALPACA_SECRET   Your Alpaca API secret (required)
        """
    )

    parser.add_argument(
        '-o', '--output',
        default='iex_symbols.txt',
        help='Output file path for symbols (default: iex_symbols.txt)'
    )

    parser.add_argument(
        '-e', '--exchange',
        default=None,
        help='Exchange to filter symbols (default: None = all exchanges). Options: NASDAQ, NYSE, ARCA, AMEX, etc. Note: IEX filtering may not work via API parameter.'
    )

    parser.add_argument(
        '--api-url',
        default='https://paper-api.alpaca.markets/v2/assets',
        help='Alpaca API URL (default: paper-api.alpaca.markets)'
    )

    parser.add_argument(
        '--status',
        default='active',
        help='Asset status filter (default: active)'
    )

    parser.add_argument(
        '--asset-class',
        default='us_equity',
        help='Asset class filter (default: us_equity)'
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

    if not api_key or not api_secret:
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


def fetch_and_stream_symbols(api_url, headers, exchange, status, asset_class, output_path):
    """
    Fetch symbols from Alpaca API and stream directly to file.

    Args:
        api_url (str): Alpaca API URL
        headers (dict): API request headers with credentials
        exchange (str): Exchange filter (e.g., 'IEX', 'NASDAQ', 'NYSE', or None for all)
        status (str): Asset status filter (e.g., 'active')
        asset_class (str): Asset class filter (e.g., 'us_equity')
        output_path (str): File path to write symbols to

    Returns:
        int: Number of symbols written

    Raises:
        Exception: If API request fails
    """
    logger.info(f"Fetching {exchange if exchange else 'all'} symbols from Alpaca API...")

    # Build request parameters
    params = {
        "status": status,
        "asset_class": asset_class
    }

    # Only add exchange filter if specified
    if exchange:
        params["exchange"] = exchange

    logger.debug(f"Request URL: {api_url}")
    logger.debug(f"Request params: {params}")

    try:
        resp = requests.get(api_url, headers=headers, params=params)
        logger.debug(f"Response status: {resp.status_code}")

        if resp.status_code != 200:
            logger.error(f"API Error: {resp.status_code} - {resp.text}")
            raise Exception(f"API request failed with status {resp.status_code}")

        data = resp.json()
        logger.debug(f"Received {len(data)} assets from API")

        if not data:
            logger.warning("No assets returned from API")
            return 0

        # Show sample asset for debugging
        if data and len(data) > 0:
            logger.debug(f"Sample asset: {data[0]}")

        # Create output directory if needed
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        # Stream symbols to file as we process them
        symbols_count = 0
        with open(output_file, 'w') as f:
            for asset in data:
                # Only write tradable assets
                if asset.get('tradable', False):
                    # Additional exchange filter (API exchange param doesn't always work)
                    if exchange is None or asset.get('exchange') == exchange:
                        f.write(asset['symbol'] + "\n")
                        symbols_count += 1

        logger.info(f"Fetched {symbols_count} tradable symbols (out of {len(data)} total assets)")
        logger.info(f"Saved symbols to {output_file.absolute()}")
        return symbols_count

    except requests.exceptions.RequestException as e:
        logger.error(f"Network error: {e}")
        raise
    except IOError as e:
        logger.error(f"Failed to write to file {output_path}: {e}")
        raise


def main():
    """Main entry point for the script."""
    args = parse_arguments()

    # Enable verbose logging if requested
    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Print configuration summary
    logger.info("=" * 60)
    logger.info("Alpaca IEX Symbols Fetcher")
    logger.info("=" * 60)
    logger.info(f"Exchange:     {args.exchange}")
    logger.info(f"Status:       {args.status}")
    logger.info(f"Asset Class:  {args.asset_class}")
    logger.info(f"Output File:  {args.output}")
    logger.info(f"API URL:      {args.api_url}")
    logger.info("=" * 60)

    try:
        # Validate API credentials
        headers = validate_credentials()

        # Fetch symbols and stream directly to file
        symbols_count = fetch_and_stream_symbols(
            api_url=args.api_url,
            headers=headers,
            exchange=args.exchange,
            status=args.status,
            asset_class=args.asset_class,
            output_path=args.output
        )

        if symbols_count == 0:
            logger.warning("No symbols found matching the criteria")
            sys.exit(0)

        logger.info(f"Operation completed successfully - {symbols_count} symbols saved")
        sys.exit(0)

    except KeyboardInterrupt:
        logger.info("\nOperation cancelled by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()