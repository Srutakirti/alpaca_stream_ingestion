#!/usr/bin/env python3
"""
Infrastructure Setup Script

Creates:
- Kafka topics (from config.yaml)
- Pinot schema (from load/schema.json)
- Pinot table (from load/table.json)

Usage:
    # Setup everything
    python3 scripts/setup_infrastructure.py

    # Dry run (show what would be created)
    python3 scripts/setup_infrastructure.py --dry-run

    # Custom config
    python3 scripts/setup_infrastructure.py --config path/to/config.yaml

Requirements:
    pip install kafka-python pyyaml requests
"""

import argparse
import logging
import sys
import yaml
import json
import requests
from pathlib import Path
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import TopicAlreadyExistsError, NoBrokersAvailable

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)
logging.getLogger('kafka').setLevel(logging.WARNING)


def load_config(config_path):
    """Load config from YAML file."""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description='Setup Kafka topics and Pinot schema/table from config.yaml',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--config', default='config/config.yaml', help='Path to config.yaml')
    parser.add_argument('--dry-run', action='store_true', help='Show what would be created')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose logging')
    return parser.parse_args()


def setup_kafka_topics(config, dry_run=False):
    """Create Kafka topics from config."""
    logger.info("=" * 70)
    logger.info("STEP 1: Setting up Kafka Topics")
    logger.info("=" * 70)

    bootstrap_servers = config['kafka']['bootstrap_servers_local']
    logger.info(f"Connecting to Kafka at: {bootstrap_servers}")

    topics_config = config['kafka']['topics']
    topic_names = list(topics_config.values())

    logger.info(f"Found {len(topic_names)} topics in config:")
    for key, topic_name in topics_config.items():
        logger.info(f"  - {key}: {topic_name}")

    if dry_run:
        logger.info("DRY RUN: Would create topics but skipping")
        return True

    try:
        admin_client = KafkaAdminClient(
            bootstrap_servers=[bootstrap_servers],
            client_id='infrastructure_setup',
            request_timeout_ms=10000,
            api_version_auto_timeout_ms=5000
        )

        existing_topics = set(admin_client.list_topics())
        topics_to_create = [name for name in topic_names if name not in existing_topics]
        topics_already_exist = [name for name in topic_names if name in existing_topics]

        if topics_already_exist:
            logger.info(f"Topics already exist: {', '.join(topics_already_exist)}")

        if not topics_to_create:
            logger.info("All topics already exist.")
            admin_client.close()
            return True

        logger.info(f"Creating {len(topics_to_create)} new topics...")
        new_topics = [
            NewTopic(name=topic_name, num_partitions=3, replication_factor=1)
            for topic_name in topics_to_create
        ]

        admin_client.create_topics(new_topics=new_topics, validate_only=False)

        logger.info("✓ Successfully created topics:")
        for topic_name in topics_to_create:
            logger.info(f"  ✓ {topic_name}")

        admin_client.close()
        return True

    except NoBrokersAvailable:
        logger.error(f"Could not connect to Kafka at {bootstrap_servers}")
        return False
    except Exception as e:
        logger.error(f"Failed to create Kafka topics: {e}")
        return False


def setup_pinot_schema(config, dry_run=False):
    """Create Pinot schema from JSON file."""
    logger.info("")
    logger.info("=" * 70)
    logger.info("STEP 2: Setting up Pinot Schema")
    logger.info("=" * 70)

    controller_url = config['pinot']['controller_url']
    schema_file = config['pinot']['schema_file']

    logger.info(f"Pinot Controller: {controller_url}")
    logger.info(f"Schema File: {schema_file}")

    # Load schema from file
    with open(schema_file, 'r') as f:
        schema = json.load(f)

    schema_name = schema['schemaName']
    logger.info(f"Schema Name: {schema_name}")

    if dry_run:
        logger.info("DRY RUN: Would create schema:")
        logger.info(json.dumps(schema, indent=2))
        return True

    try:
        # Check if schema exists
        response = requests.get(f"{controller_url}/schemas/{schema_name}")
        if response.status_code == 200:
            logger.info(f"Schema '{schema_name}' already exists. Skipping.")
            return True

        # Create schema
        response = requests.post(
            f"{controller_url}/schemas",
            json=schema,
            headers={'Content-Type': 'application/json'}
        )

        if response.status_code in [200, 201]:
            logger.info(f"✓ Successfully created schema: {schema_name}")
            return True
        else:
            logger.error(f"Failed to create schema. Status: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return False

    except requests.exceptions.ConnectionError:
        logger.error(f"Could not connect to Pinot at {controller_url}")
        return False
    except Exception as e:
        logger.error(f"Failed to create Pinot schema: {e}")
        return False


def setup_pinot_table(config, dry_run=False):
    """Create Pinot table from JSON file."""
    logger.info("")
    logger.info("=" * 70)
    logger.info("STEP 3: Setting up Pinot Table")
    logger.info("=" * 70)

    controller_url = config['pinot']['controller_url']
    table_file = config['pinot']['table_file']

    logger.info(f"Pinot Controller: {controller_url}")
    logger.info(f"Table File: {table_file}")

    # Load table config from file
    with open(table_file, 'r') as f:
        table = json.load(f)

    table_name = table['tableName']
    logger.info(f"Table Name: {table_name}")

    # Show Kafka connection info from table config
    kafka_config = table['ingestionConfig']['streamIngestionConfig']['streamConfigMaps'][0]
    logger.info(f"Source Topic: {kafka_config['stream.kafka.topic.name']}")
    logger.info(f"Kafka Bootstrap: {kafka_config['stream.kafka.broker.list']}")

    if dry_run:
        logger.info("DRY RUN: Would create table:")
        logger.info(json.dumps(table, indent=2))
        return True

    try:
        # Check if table exists
        response = requests.get(f"{controller_url}/tables/{table_name}")
        if response.status_code == 200:
            logger.info(f"Table '{table_name}' already exists. Skipping.")
            logger.info("To recreate, delete first:")
            logger.info(f"  curl -X DELETE {controller_url}/tables/{table_name}?type=realtime")
            return True

        # Create table
        response = requests.post(
            f"{controller_url}/tables",
            json=table,
            headers={'Content-Type': 'application/json'}
        )

        if response.status_code in [200, 201]:
            logger.info(f"✓ Successfully created table: {table_name}")
            return True
        else:
            logger.error(f"Failed to create table. Status: {response.status_code}")
            logger.error(f"Response: {response.text}")
            return False

    except requests.exceptions.ConnectionError:
        logger.error(f"Could not connect to Pinot at {controller_url}")
        return False
    except Exception as e:
        logger.error(f"Failed to create Pinot table: {e}")
        return False


def verify_setup(config):
    """Verify the setup was successful."""
    logger.info("")
    logger.info("=" * 70)
    logger.info("Verification")
    logger.info("=" * 70)

    # Verify Kafka topics
    try:
        bootstrap_servers = config['kafka']['bootstrap_servers_local']
        admin_client = KafkaAdminClient(
            bootstrap_servers=[bootstrap_servers],
            request_timeout_ms=5000
        )
        existing_topics = set(admin_client.list_topics())

        topics_config = config['kafka']['topics']
        for key, topic_name in topics_config.items():
            if topic_name in existing_topics:
                logger.info(f"✓ Kafka topic exists: {topic_name}")
            else:
                logger.warning(f"✗ Kafka topic missing: {topic_name}")

        admin_client.close()
    except Exception as e:
        logger.warning(f"Could not verify Kafka topics: {e}")

    # Verify Pinot schema and table
    try:
        controller_url = config['pinot']['controller_url']

        # Load schema and table names from files
        with open(config['pinot']['schema_file'], 'r') as f:
            schema_name = json.load(f)['schemaName']

        with open(config['pinot']['table_file'], 'r') as f:
            table_name = json.load(f)['tableName']

        # Check schema
        response = requests.get(f"{controller_url}/schemas/{schema_name}", timeout=5)
        if response.status_code == 200:
            logger.info(f"✓ Pinot schema exists: {schema_name}")
        else:
            logger.warning(f"✗ Pinot schema missing: {schema_name}")

        # Check table
        response = requests.get(f"{controller_url}/tables/{table_name}", timeout=5)
        if response.status_code == 200:
            logger.info(f"✓ Pinot table exists: {table_name}")
        else:
            logger.warning(f"✗ Pinot table missing: {table_name}")

    except Exception as e:
        logger.warning(f"Could not verify Pinot resources: {e}")


def main():
    """Main entry point."""
    args = parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    logger.info("=" * 70)
    logger.info("Infrastructure Setup Script")
    logger.info("=" * 70)
    logger.info(f"Config File: {args.config}")
    logger.info(f"Dry Run: {args.dry_run}")
    logger.info("=" * 70)

    try:
        config = load_config(args.config)

        success = True

        # Step 1: Kafka topics
        if not setup_kafka_topics(config, args.dry_run):
            success = False

        # Step 2: Pinot schema
        if not setup_pinot_schema(config, args.dry_run):
            success = False

        # Step 3: Pinot table
        if not setup_pinot_table(config, args.dry_run):
            success = False

        # Verify
        if not args.dry_run and success:
            verify_setup(config)

        logger.info("")
        logger.info("=" * 70)
        if success:
            logger.info("✓ Infrastructure setup completed successfully!")
        else:
            logger.error("✗ Infrastructure setup completed with errors")
        logger.info("=" * 70)

        sys.exit(0 if success else 1)

    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
