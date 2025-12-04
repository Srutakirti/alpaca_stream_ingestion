#!/usr/bin/env python3
"""
Iceberg Table Compaction Script

Compacts small Iceberg data files into larger ones to improve query performance
and reduce metadata overhead.

Usage:
    python iceberg_compaction.py --table iex_db.raw_stream_iex_2 --target-file-size-mb 512

Features:
  - Compacts small files using Iceberg's rewrite_data_files procedure
  - Displays before/after statistics
  - Optional partition filtering for incremental compaction
  - Dry-run mode to preview compaction without executing
"""

import argparse
import logging
import sys
from dataclasses import dataclass
from typing import Optional

from pyspark.sql import SparkSession, DataFrame


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


@dataclass
class CompactionConfig:
    """
    Configuration for Iceberg table compaction.

    Holds all parameters for Spark session and compaction operation.
    """
    # Table configuration
    table: str
    target_file_size_mb: int

    # Iceberg configuration
    iceberg_catalog: str
    iceberg_warehouse: str

    # S3/MinIO configuration
    s3_endpoint: str
    s3_access_key: str
    s3_secret_key: str

    # Compaction options
    partition_filter: Optional[str]
    dry_run: bool


class IcebergCompactor:
    """
    Handles Iceberg table compaction operations.

    Provides methods to analyze table statistics and perform compaction
    using Iceberg's native procedures.
    """

    def __init__(self, config: CompactionConfig) -> None:
        """
        Initialize compactor with configuration.

        Args:
            config: CompactionConfig with all parameters
        """
        self.config: CompactionConfig = config
        self.spark: Optional[SparkSession] = None
        self.logger: logging.Logger = logging.getLogger(__name__)

        # Initialize Spark session
        self._init_spark_session()

        self.logger.info("IcebergCompactor initialized successfully")

    def _init_spark_session(self) -> None:
        """
        Initialize Spark session with Iceberg and S3 configurations.

        Configures:
          - Iceberg Spark extensions
          - Hadoop catalog
          - S3A filesystem with MinIO endpoint
          - Path-style S3 access
        """
        self.logger.info("Initializing Spark session...")

         # Define required packages
        packages: str = ",".join([
            "org.apache.iceberg:iceberg-spark-runtime-3.5_2.12:1.9.0",
            "com.amazonaws:aws-java-sdk-bundle:1.12.262",
            "org.apache.hadoop:hadoop-aws:3.3.4"
        ])

        self.spark = (
            SparkSession.builder
            .appName("IcebergCompaction")
            .config("spark.jars.packages", packages)
            .config("spark.sql.extensions", "org.apache.iceberg.spark.extensions.IcebergSparkSessionExtensions")
            .config(f"spark.sql.catalog.{self.config.iceberg_catalog}", "org.apache.iceberg.spark.SparkCatalog")
            .config(f"spark.sql.catalog.{self.config.iceberg_catalog}.type", "hadoop")
            .config(f"spark.sql.catalog.{self.config.iceberg_catalog}.warehouse", self.config.iceberg_warehouse)
            .config("spark.hadoop.fs.s3a.endpoint", self.config.s3_endpoint)
            .config("spark.hadoop.fs.s3a.access.key", self.config.s3_access_key)
            .config("spark.hadoop.fs.s3a.secret.key", self.config.s3_secret_key)
            .config("spark.hadoop.fs.s3a.path.style.access", "true")
            .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
            .config("spark.sql.catalog.spark_catalog", "org.apache.iceberg.spark.SparkSessionCatalog")
            .config("spark.sql.catalog.spark_catalog.type", "hive")
            .getOrCreate()
        )

        self.spark.sparkContext.setLogLevel("WARN")
        self.logger.info("Spark session initialized")

    def get_table_statistics(self) -> dict:
        """
        Get current table statistics including file count and sizes.

        Queries Iceberg metadata tables to get:
          - Total number of data files
          - Total data size in bytes
          - Average file size

        Returns:
            Dictionary with file_count, total_bytes, avg_file_size_mb
        """
        self.logger.info(f"Fetching statistics for table: {self.config.table}")

        # Query Iceberg files metadata table
        files_df: DataFrame = self.spark.sql(f"""
            SELECT
                COUNT(*) as file_count,
                SUM(file_size_in_bytes) as total_bytes
            FROM {self.config.iceberg_catalog}.{self.config.table}.files
        """)

        result = files_df.collect()[0]
        file_count = result['file_count']
        total_bytes = result['total_bytes'] or 0

        # Calculate average file size in MB
        avg_file_size_mb = (total_bytes / file_count / 1024 / 1024) if file_count > 0 else 0

        return {
            'file_count': file_count,
            'total_bytes': total_bytes,
            'total_mb': total_bytes / 1024 / 1024,
            'avg_file_size_mb': avg_file_size_mb
        }

    def display_statistics(self, stats: dict, label: str) -> None:
        """
        Display table statistics in a formatted way.

        Args:
            stats: Dictionary with file_count, total_bytes, avg_file_size_mb
            label: Label to display (e.g., "Before Compaction")
        """
        print(f"\n{'=' * 60}")
        print(f"{label:^60}")
        print(f"{'=' * 60}")
        print(f"  Total Files:        {stats['file_count']:>10,}")
        print(f"  Total Size:         {stats['total_mb']:>10,.2f} MB")
        print(f"  Average File Size:  {stats['avg_file_size_mb']:>10,.2f} MB")
        print(f"{'=' * 60}\n")

    def run_compaction(self) -> Optional[dict]:
        """
        Execute table compaction using Iceberg's rewrite_data_files procedure.

        Compacts small files into larger ones based on target file size.
        Optionally filters by partition for incremental compaction.

        Returns:
            Dictionary with compaction metrics if not dry-run, None otherwise
        """
        # Build compaction SQL
        target_file_size_bytes = self.config.target_file_size_mb * 1024 * 1024

        # Start with base procedure call
        sql_parts = [
            f"CALL {self.config.iceberg_catalog}.system.rewrite_data_files(",
            f"    table => '{self.config.iceberg_catalog}.{self.config.table}',",
            f"    options => map('target-file-size-bytes', '{target_file_size_bytes}')"
        ]

        # Add partition filter if specified
        if self.config.partition_filter:
            sql_parts.insert(-1, f"    where => '{self.config.partition_filter}',")

        sql_parts.append(")")
        compaction_sql = "\n".join(sql_parts)

        if self.config.dry_run:
            self.logger.info("DRY RUN MODE - Compaction SQL that would be executed:")
            print(f"\n{compaction_sql}\n")
            return None

        # Execute compaction
        self.logger.info("Starting compaction...")
        if self.config.partition_filter:
            self.logger.info(f"Partition filter: {self.config.partition_filter}")

        result_df: DataFrame = self.spark.sql(compaction_sql)

        # Show schema for debugging
        self.logger.info(f"Result columns: {result_df.columns}")

        result = result_df.collect()[0]

        # Extract metrics from result (use actual column names)
        metrics = {}
        for col_name in result_df.columns:
            metrics[col_name] = result[col_name]

        self.logger.info("Compaction completed successfully")
        return metrics

    def display_compaction_metrics(self, metrics: dict) -> None:
        """
        Display compaction operation metrics.

        Args:
            metrics: Dictionary with compaction result columns
        """
        print(f"\n{'=' * 60}")
        print(f"{'Compaction Metrics':^60}")
        print(f"{'=' * 60}")

        # Display all metrics from the result
        for key, value in metrics.items():
            # Format key for display (remove underscores, title case)
            display_key = key.replace('_', ' ').title()

            # Format value based on type
            if isinstance(value, (int, float)):
                if 'bytes' in key.lower():
                    # Convert bytes to MB
                    print(f"  {display_key:<30} {value / 1024 / 1024:>15,.2f} MB")
                else:
                    print(f"  {display_key:<30} {value:>15,}")
            else:
                print(f"  {display_key:<30} {str(value):>15}")

        print(f"{'=' * 60}\n")

    def compact(self) -> None:
        """
        Main compaction workflow.

        Steps:
          1. Display before statistics
          2. Run compaction (or dry-run)
          3. Display compaction metrics
          4. Display after statistics
        """
        # Get and display before statistics
        before_stats = self.get_table_statistics()
        self.display_statistics(before_stats, "Table Statistics (Before)")

        # Run compaction
        metrics = self.run_compaction()

        if metrics:
            # Display compaction metrics
            self.display_compaction_metrics(metrics)

            # Get and display after statistics
            after_stats = self.get_table_statistics()
            self.display_statistics(after_stats, "Table Statistics (After)")

            # Summary
            file_reduction = before_stats['file_count'] - after_stats['file_count']
            print(f"✓ Compaction complete: Reduced {file_reduction:,} files")
        else:
            print("✓ Dry-run complete: No changes made to table")

        # Stop Spark
        self.spark.stop()


def parse_arguments() -> argparse.Namespace:
    """
    Parse command-line arguments.

    Returns:
        Parsed arguments namespace
    """
    parser = argparse.ArgumentParser(
        description='Compact Iceberg table data files for improved query performance',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    # Table Configuration
    table_group = parser.add_argument_group('Table Configuration')
    table_group.add_argument(
        '--table',
        required=True,
        help='Iceberg table in format: database.table (e.g., iex_db.raw_stream_iex_2)'
    )
    table_group.add_argument(
        '--target-file-size-mb',
        type=int,
        default=512,
        help='Target size for compacted files in MB'
    )

    # Iceberg Configuration
    iceberg_group = parser.add_argument_group('Iceberg Configuration')
    iceberg_group.add_argument(
        '--iceberg-catalog',
        default='my_catalog',
        help='Iceberg catalog name'
    )
    iceberg_group.add_argument(
        '--iceberg-warehouse',
        default='s3a://test2/mywarehouse',
        help='Iceberg warehouse S3 location'
    )

    # S3/MinIO Configuration
    s3_group = parser.add_argument_group('S3/MinIO Configuration')
    s3_group.add_argument(
        '--s3-endpoint',
        default='http://minio-api.192.168.49.2.nip.io',
        help='S3/MinIO endpoint URL'
    )
    s3_group.add_argument(
        '--s3-access-key',
        default='minio',
        help='S3/MinIO access key'
    )
    s3_group.add_argument(
        '--s3-secret-key',
        default='minio123',
        help='S3/MinIO secret key'
    )

    # Compaction Options
    compaction_group = parser.add_argument_group('Compaction Options')
    compaction_group.add_argument(
        '--partition-filter',
        default=None,
        help='SQL WHERE clause to filter partitions (e.g., "date >= \'2024-11-01\'")'
    )
    compaction_group.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be compacted without executing'
    )

    return parser.parse_args()


def main() -> None:
    """
    Main entry point for compaction script.

    Parses arguments, creates compactor, and runs compaction.
    """
    args = parse_arguments()

    # Create configuration
    config = CompactionConfig(
        table=args.table,
        target_file_size_mb=args.target_file_size_mb,
        iceberg_catalog=args.iceberg_catalog,
        iceberg_warehouse=args.iceberg_warehouse,
        s3_endpoint=args.s3_endpoint,
        s3_access_key=args.s3_access_key,
        s3_secret_key=args.s3_secret_key,
        partition_filter=args.partition_filter,
        dry_run=args.dry_run
    )

    # Run compaction
    try:
        compactor = IcebergCompactor(config)
        compactor.compact()
    except Exception as e:
        logging.error(f"Compaction failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
