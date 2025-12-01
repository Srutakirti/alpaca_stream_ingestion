#!/usr/bin/env python3
"""
Kafka Topic Creator - CLI Tool

Creates a Kafka topic with configurable parameters. Checks if the topic
already exists before attempting to create it.

Usage:
    python create_kafka_topic.py --topic my-topic
    python create_kafka_topic.py -t my-topic -b localhost:9092
    python create_kafka_topic.py -t my-topic -p 5 -r 3
    python create_kafka_topic.py --topic my-topic --dry-run

Author: Updated with Claude Code
"""

import argparse
import logging
import sys
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError, NoBrokersAvailable

# Configure Kafka client logging (reduce noise)
logging.getLogger('kafka').setLevel(logging.WARNING)

# Setup application logging
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
        Namespace: Parsed arguments containing topic name, broker, partitions, etc.
    """
    parser = argparse.ArgumentParser(
        description='Create a Kafka topic with specified configuration',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create topic with defaults
  %(prog)s --topic my-topic

  # Create topic with custom broker
  %(prog)s -t my-topic -b localhost:9092

  # Create topic with 5 partitions and replication factor 3
  %(prog)s -t my-topic -p 5 -r 3

  # Dry run - check if topic exists without creating
  %(prog)s -t my-topic --dry-run
        """
    )

    parser.add_argument(
        '-t', '--topic',
        required=True,
        help='Name of the Kafka topic to create'
    )

    parser.add_argument(
        '-b', '--broker',
        default='192.168.58.2:32100',
        help='Kafka bootstrap server address (default: 192.168.49.2:32100)'
    )

    parser.add_argument(
        '-p', '--partitions',
        type=int,
        default=3,
        help='Number of partitions for the topic (default: 3)'
    )

    parser.add_argument(
        '-r', '--replication-factor',
        type=int,
        default=1,
        help='Replication factor for the topic (default: 1)'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Check if topic exists without creating it'
    )

    parser.add_argument(
        '--force',
        action='store_true',
        help='Skip existence check and attempt to create (will fail if exists)'
    )

    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose logging'
    )

    return parser.parse_args()


def check_topic_exists(admin_client, topic_name):
    """
    Check if a topic already exists in Kafka.

    Args:
        admin_client (KafkaAdminClient): Connected Kafka admin client
        topic_name (str): Name of the topic to check

    Returns:
        bool: True if topic exists, False otherwise

    Raises:
        Exception: If unable to list topics from Kafka
    """
    try:
        # Get list of all existing topics
        existing_topics = admin_client.list_topics()

        # Check if our topic is in the list
        topic_exists = topic_name in existing_topics

        if topic_exists:
            logger.info(f"Topic '{topic_name}' already exists")
        else:
            logger.info(f"Topic '{topic_name}' does not exist")

        return topic_exists

    except Exception as e:
        logger.error(f"Failed to check if topic exists: {e}")
        raise


def create_topic(topic_name, broker, partitions, replication_factor, dry_run=False, force=False):
    """
    Create a Kafka topic with the specified configuration.

    This function:
    1. Connects to Kafka broker
    2. Checks if topic already exists (unless --force is used)
    3. Creates the topic if it doesn't exist (unless --dry-run is used)
    4. Handles errors gracefully

    Args:
        topic_name (str): Name of the topic to create
        broker (str): Kafka bootstrap server address
        partitions (int): Number of partitions for the topic
        replication_factor (int): Replication factor for the topic
        dry_run (bool): If True, only check existence without creating
        force (bool): If True, skip existence check and attempt creation

    Returns:
        bool: True if topic was created or already exists, False on error
    """
    admin_client = None

    try:
        # Step 1: Connect to Kafka
        logger.info(f"Connecting to Kafka broker at {broker}...")
        admin_client = KafkaAdminClient(
            bootstrap_servers=[broker],
            client_id='kafka_topic_creator',
            request_timeout_ms=10000,
            api_version_auto_timeout_ms=5000
        )
        logger.info("Successfully connected to Kafka broker")

        # Step 2: Check if topic exists (unless --force is used)
        if not force:
            topic_exists = check_topic_exists(admin_client, topic_name)

            if topic_exists:
                logger.warning(f"Topic '{topic_name}' already exists. No action needed.")
                return True

        # Step 3: Dry run mode - exit without creating
        if dry_run:
            logger.info("Dry run mode - exiting without creating topic")
            return True

        # Step 4: Validate configuration
        if partitions < 1:
            logger.error(f"Invalid partitions: {partitions}. Must be at least 1.")
            return False

        if replication_factor < 1:
            logger.error(f"Invalid replication factor: {replication_factor}. Must be at least 1.")
            return False

        # Step 5: Create the topic
        logger.info(f"Creating topic '{topic_name}'...")
        logger.info(f"  Partitions: {partitions}")
        logger.info(f"  Replication Factor: {replication_factor}")

        # Define the new topic configuration
        new_topic = NewTopic(
            name=topic_name,
            num_partitions=partitions,
            replication_factor=replication_factor
        )

        # Call Kafka admin API to create the topic
        admin_client.create_topics(
            new_topics=[new_topic],
            validate_only=False  # Actually create the topic (not just validate)
        )

        logger.info(f"✓ Successfully created topic '{topic_name}'")
        return True

    except TopicAlreadyExistsError:
        # This shouldn't happen if we checked first, but handle it anyway
        logger.warning(f"Topic '{topic_name}' already exists (caught during creation)")
        return True

    except NoBrokersAvailable:
        logger.error(
            f"Could not connect to Kafka broker at {broker}. "
            "Please check:\n"
            "  1. The broker address is correct\n"
            "  2. Kafka is running\n"
            "  3. Network connectivity to the broker"
        )
        return False

    except Exception as e:
        logger.error(f"Failed to create topic: {type(e).__name__}: {e}")
        return False

    finally:
        # Step 6: Clean up - close the admin client connection
        if admin_client:
            admin_client.close()
            logger.info("Closed Kafka admin client connection")


def main():
    """
    Main entry point for the script.

    Parses CLI arguments and calls create_topic() with the configuration.
    Exits with appropriate status code (0 for success, 1 for failure).
    """
    # Parse command-line arguments
    args = parse_arguments()

    # Enable verbose logging if requested
    if args.verbose:
        logger.setLevel(logging.DEBUG)
        logging.getLogger('kafka').setLevel(logging.INFO)

    # Print configuration summary
    logger.info("=" * 60)
    logger.info("Kafka Topic Creator")
    logger.info("=" * 60)
    logger.info(f"Topic Name:         {args.topic}")
    logger.info(f"Broker:             {args.broker}")
    logger.info(f"Partitions:         {args.partitions}")
    logger.info(f"Replication Factor: {args.replication_factor}")
    logger.info(f"Dry Run:            {args.dry_run}")
    logger.info(f"Force Create:       {args.force}")
    logger.info("=" * 60)

    # Create the topic
    success = create_topic(
        topic_name=args.topic,
        broker=args.broker,
        partitions=args.partitions,
        replication_factor=args.replication_factor,
        dry_run=args.dry_run,
        force=args.force
    )

    # Exit with appropriate status code
    if success:
        logger.info("✓ Operation completed successfully")
        sys.exit(0)
    else:
        logger.error("✗ Operation failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
