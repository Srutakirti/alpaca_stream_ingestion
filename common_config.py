#!/usr/bin/env python3
"""
Shared Configuration Loader for Alpaca Stream Ingestion Project

This module provides a centralized way to load configuration from config/config.yaml
with support for environment variable overrides.

Usage:
    from common_config import load_config, get_kafka_config, get_alpaca_config

    # Load full config
    config = load_config()
    bootstrap = config['kafka']['bootstrap_servers']

    # Or use helper functions
    kafka_config = get_kafka_config()
    bootstrap = kafka_config['bootstrap_servers']
    topics = kafka_config['topics']

    alpaca_config = get_alpaca_config()
    key = alpaca_config['key']

Environment Variable Overrides:
    KAFKA_BOOTSTRAP_SERVERS - Override kafka.bootstrap_servers
    ALPACA_KEY - Override alpaca.key
    ALPACA_SECRET - Override alpaca.secret
    CONFIG_PATH - Custom path to config.yaml (default: config/config.yaml)

Author: Alpaca Team
"""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional


def load_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Load configuration from YAML file with environment variable overrides.

    Args:
        config_path: Path to config.yaml file. If None, uses CONFIG_PATH env var
                     or defaults to 'config/config.yaml'

    Returns:
        dict: Configuration dictionary

    Raises:
        FileNotFoundError: If config file doesn't exist
        yaml.YAMLError: If config file is invalid YAML

    Examples:
        >>> config = load_config()
        >>> config['kafka']['bootstrap_servers']
        'my-cluster-kafka-bootstrap.kafka.svc.cluster.local:9092'

        >>> config = load_config('path/to/custom/config.yaml')
    """
    # Determine config file path
    if config_path is None:
        config_path = os.getenv('CONFIG_PATH', 'config/config.yaml')

    config_file = Path(config_path)

    # Handle relative paths from project root
    if not config_file.is_absolute():
        # Try relative to current directory first
        if not config_file.exists():
            # Try relative to this module's location
            module_dir = Path(__file__).parent
            config_file = module_dir / config_path

    if not config_file.exists():
        raise FileNotFoundError(
            f"Config file not found: {config_path}\n"
            f"Tried: {config_file.absolute()}\n"
            f"Set CONFIG_PATH environment variable or pass config_path argument"
        )

    # Load YAML
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)

    # Apply environment variable overrides
    config = _apply_env_overrides(config)

    return config


def _apply_env_overrides(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Apply environment variable overrides to config.

    Args:
        config: Base configuration dictionary

    Returns:
        dict: Configuration with environment overrides applied
    """
    # Kafka overrides
    if 'kafka' in config:
        if os.getenv('KAFKA_BOOTSTRAP_SERVERS'):
            config['kafka']['bootstrap_servers'] = os.getenv('KAFKA_BOOTSTRAP_SERVERS')

        if os.getenv('KAFKA_RAW_TOPIC'):
            config['kafka']['topics']['raw_trade'] = os.getenv('KAFKA_RAW_TOPIC')

        if os.getenv('KAFKA_FLATTENED_TOPIC'):
            config['kafka']['topics']['flattened_trade'] = os.getenv('KAFKA_FLATTENED_TOPIC')

        if os.getenv('KAFKA_CONSUMER_GROUP'):
            config['kafka']['consumer']['group_id'] = os.getenv('KAFKA_CONSUMER_GROUP')

    # Alpaca overrides
    if 'alpaca' in config:
        if os.getenv('ALPACA_KEY'):
            config['alpaca']['key'] = os.getenv('ALPACA_KEY')

        if os.getenv('ALPACA_SECRET'):
            config['alpaca']['secret'] = os.getenv('ALPACA_SECRET')

        if os.getenv('ALPACA_WEBSOCKET_URI'):
            config['alpaca']['websocket_uri'] = os.getenv('ALPACA_WEBSOCKET_URI')

    # GCP overrides
    if 'gcp' in config:
        if os.getenv('GCP_PROJECT_ID'):
            config['gcp']['project_id'] = os.getenv('GCP_PROJECT_ID')

        if os.getenv('GCP_BUCKET'):
            config['gcp']['storage']['bucket'] = os.getenv('GCP_BUCKET')

    # Spark overrides
    if 'spark' in config:
        if os.getenv('SPARK_WAREHOUSE_PATH'):
            config['spark']['warehouse_path'] = os.getenv('SPARK_WAREHOUSE_PATH')

    return config


def get_kafka_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Get Kafka configuration section.

    Args:
        config_path: Optional custom path to config.yaml

    Returns:
        dict: Kafka configuration with keys:
              - bootstrap_servers: str
              - topics: dict with raw_trade, flattened_trade
              - consumer: dict with group_id, enable_auto_commit

    Examples:
        >>> kafka = get_kafka_config()
        >>> kafka['bootstrap_servers']
        'my-cluster-kafka-bootstrap.kafka.svc.cluster.local:9092'
        >>> kafka['topics']['raw_trade']
        'iex-topic-1'
    """
    config = load_config(config_path)
    return config.get('kafka', {})


def get_alpaca_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Get Alpaca API configuration section.

    Args:
        config_path: Optional custom path to config.yaml

    Returns:
        dict: Alpaca configuration with keys:
              - key: str (from env ALPACA_KEY)
              - secret: str (from env ALPACA_SECRET)
              - websocket_uri: str
              - symbols: list
              - timeout: int
              - max_retries: int
              - backoff_max: int

    Examples:
        >>> alpaca = get_alpaca_config()
        >>> alpaca['websocket_uri']
        'wss://stream.data.alpaca.markets/v2/iex'
    """
    config = load_config(config_path)
    return config.get('alpaca', {})


def get_spark_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Get Spark configuration section.

    Args:
        config_path: Optional custom path to config.yaml

    Returns:
        dict: Spark configuration
    """
    config = load_config(config_path)
    return config.get('spark', {})


def get_gcp_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Get GCP configuration section.

    Args:
        config_path: Optional custom path to config.yaml

    Returns:
        dict: GCP configuration
    """
    config = load_config(config_path)
    return config.get('gcp', {})


def get_logging_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """
    Get logging configuration section.

    Args:
        config_path: Optional custom path to config.yaml

    Returns:
        dict: Logging configuration with keys:
              - level: str (INFO, DEBUG, etc.)
              - name: str
              - mode: str (stdout, file, etc.)
    """
    config = load_config(config_path)
    return config.get('logging', {})


# Convenience function for dot notation access
def get_config_value(path: str, default: Any = None, config_path: Optional[str] = None) -> Any:
    """
    Get config value using dot notation path.

    Args:
        path: Dot-separated path (e.g., 'kafka.topics.raw_trade')
        default: Default value if path not found
        config_path: Optional custom path to config.yaml

    Returns:
        Config value at path, or default if not found

    Examples:
        >>> get_config_value('kafka.bootstrap_servers')
        'my-cluster-kafka-bootstrap.kafka.svc.cluster.local:9092'

        >>> get_config_value('kafka.topics.raw_trade')
        'iex-topic-1'

        >>> get_config_value('nonexistent.key', default='fallback')
        'fallback'
    """
    try:
        config = load_config(config_path)
        value = config
        for key in path.split('.'):
            value = value[key]
        return value
    except (KeyError, TypeError):
        return default


if __name__ == '__main__':
    """
    Test the config loader by printing all sections.

    Usage: python common_config.py
    """
    import json

    print("=" * 70)
    print("Configuration Loader Test")
    print("=" * 70)

    try:
        config = load_config()

        print("\n✓ Successfully loaded config\n")

        print("Kafka Configuration:")
        print("-" * 70)
        kafka = get_kafka_config()
        print(f"  Bootstrap Servers: {kafka.get('bootstrap_servers')}")
        print(f"  Topics:")
        for key, value in kafka.get('topics', {}).items():
            print(f"    {key}: {value}")
        print(f"  Consumer Group: {kafka.get('consumer', {}).get('group_id')}")

        print("\nAlpaca Configuration:")
        print("-" * 70)
        alpaca = get_alpaca_config()
        print(f"  WebSocket URI: {alpaca.get('websocket_uri')}")
        print(f"  Key: {'***' if alpaca.get('key') else 'Not set (use ALPACA_KEY env var)'}")
        print(f"  Secret: {'***' if alpaca.get('secret') else 'Not set (use ALPACA_SECRET env var)'}")

        print("\nSpark Configuration:")
        print("-" * 70)
        spark = get_spark_config()
        print(f"  Warehouse Path: {spark.get('warehouse_path')}")
        print(f"  App Name: {spark.get('app_name')}")

        print("\nGCP Configuration:")
        print("-" * 70)
        gcp = get_gcp_config()
        print(f"  Project ID: {gcp.get('project_id')}")
        print(f"  Region: {gcp.get('region')}")
        print(f"  Bucket: {gcp.get('storage', {}).get('bucket')}")

        print("\nLogging Configuration:")
        print("-" * 70)
        logging_config = get_logging_config()
        print(f"  Level: {logging_config.get('level')}")
        print(f"  Mode: {logging_config.get('mode')}")

        print("\n" + "=" * 70)
        print("✓ All configuration sections loaded successfully")
        print("=" * 70)

    except FileNotFoundError as e:
        print(f"\n✗ Error: {e}")
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}")
