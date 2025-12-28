#!/usr/bin/env python3
"""
Kafka Topics Creator - Reads from config.yaml and creates all topics

This script reads the topics from config/config.yaml and creates them in Kafka.
It automatically determines the Kafka bootstrap server from the config.

Usage:
    python create_all_topics.py
    python create_all_topics.py --config path/to/config.yaml
    python create_all_topics.py --partitions 5 --replication-factor 3
    python create_all_topics.py --dry-run

Author: Claude Code
"""

import argparse
import logging
import sys
from pathlib import Path
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError, NoBrokersAvailable

# Import shared config loader
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
from old_archive.common_config import load_config

# Configure Kafka client logging (reduce noise)
logging.getLogger('kafka').setLevel(logging.WARNING)

# Setup application logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)


# load_config now imported from common_config module


def parse_arguments():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Create all Kafka topics defined in config.yaml',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create all topics with defaults
  %(prog)s

  # Use custom config file
  %(prog)s --config /path/to/config.yaml

  # Create topics with 5 partitions
  %(prog)s --partitions 5

  # Dry run - check config without creating
  %(prog)s --dry-run
        """
    )

    parser.add_argument(
        '--config',
        default='config/config.yaml',
        help='Path to config.yaml file (default: config/config.yaml)'
    )

    parser.add_argument(
        '-p', '--partitions',
        type=int,
        default=3,
        help='Number of partitions for each topic (default: 3)'
    )

    parser.add_argument(
        '-r', '--replication-factor',
        type=int,
        default=1,
        help='Replication factor for each topic (default: 1)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be created without actually creating topics'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    return parser.parse_args()


def create_topics_from_config(config, partitions, replication_factor, dry_run=False):
    """
    Create all topics defined in the configuration.

    Args:
        config (dict): Configuration dictionary with kafka.topics and kafka.bootstrap_servers
        partitions (int): Number of partitions for each topic
        replication_factor (int): Replication factor for each topic
        dry_run (bool): If True, only show what would be created

    Returns:
        bool: True if all topics were created successfully, False otherwise
    """
    # Extract Kafka configuration
    try:
        kafka_config = config['kafka']
        bootstrap_servers = kafka_config['bootstrap_servers']
        topics_config = kafka_config['topics']
    except KeyError as e:
        logger.error(f"Missing required config key: {e}")
        logger.error(f"Expected structure: kafka.bootstrap_servers and kafka.topics")
        return False

    # Extract topic names from config
    # topics_config is a dict like: {"raw_trade": "iex-topic-1", "flattened_trade": "iex-topic-1-flattened"}
    topic_names = list(topics_config.values())

    if not topic_names:
        logger.warning("No topics found in config")
        return True

    logger.info(f"Found {len(topic_names)} topics in config:")
    for key, topic_name in topics_config.items():
        logger.info(f"  {key}: {topic_name}")

    if dry_run:
        logger.info("Dry run mode - exiting without creating topics")
        return True

    # Connect to Kafka
    admin_client = None
    try:
        logger.info(f"Connecting to Kafka broker at {bootstrap_servers}...")
        admin_client = KafkaAdminClient(
            bootstrap_servers=[bootstrap_servers],
            client_id='kafka_topics_creator',
            request_timeout_ms=10000,
            api_version_auto_timeout_ms=5000
        )
        logger.info("Successfully connected to Kafka broker")

        # Get existing topics
        existing_topics = set(admin_client.list_topics())
        logger.info(f"Found {len(existing_topics)} existing topics")

        # Filter out topics that already exist
        topics_to_create = [name for name in topic_names if name not in existing_topics]
        topics_already_exist = [name for name in topic_names if name in existing_topics]

        # Report on existing topics
        if topics_already_exist:
            logger.info(f"Topics already exist (skipping): {', '.join(topics_already_exist)}")

        if not topics_to_create:
            logger.info("All topics already exist. No action needed.")
            return True

        # Create new topics
        logger.info(f"Creating {len(topics_to_create)} new topics...")
        logger.info(f"  Partitions: {partitions}")
        logger.info(f"  Replication Factor: {replication_factor}")

        new_topics = [
            NewTopic(
                name=topic_name,
                num_partitions=partitions,
                replication_factor=replication_factor
            )
            for topic_name in topics_to_create
        ]

        admin_client.create_topics(new_topics=new_topics, validate_only=False)

        logger.info(f"✓ Successfully created {len(topics_to_create)} topics:")
        for topic_name in topics_to_create:
            logger.info(f"  ✓ {topic_name}")

        return True

    except NoBrokersAvailable:
        logger.error(
            f"Could not connect to Kafka broker at {bootstrap_servers}. "
            "Please check:\n"
            "  1. The broker address is correct\n"
            "  2. Kafka is running\n"
            "  3. Network connectivity to the broker"
        )
        return False

    except Exception as e:
        logger.error(f"Failed to create topics: {type(e).__name__}: {e}")
        return False

    finally:
        if admin_client:
            admin_client.close()
            logger.info("Closed Kafka admin client connection")


def main():
    """Main entry point for the script."""
    args = parse_arguments()

    # Enable verbose logging if requested
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        logging.getLogger('kafka').setLevel(logging.INFO)

    # Print configuration summary
    logger.info("=" * 60)
    logger.info("Kafka Topics Creator (from config.yaml)")
    logger.info("=" * 60)
    logger.info(f"Config File:        {args.config}")
    logger.info(f"Partitions:         {args.partitions}")
    logger.info(f"Replication Factor: {args.replication_factor}")
    logger.info(f"Dry Run:            {args.dry_run}")
    logger.info("=" * 60)

    try:
        # Load configuration
        config = load_config(args.config)

        # Create topics
        success = create_topics_from_config(
            config=config,
            partitions=args.partitions,
            replication_factor=args.replication_factor,
            dry_run=args.dry_run
        )

        if success:
            logger.info("✓ Operation completed successfully")
            sys.exit(0)
        else:
            logger.error("✗ Operation failed")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
