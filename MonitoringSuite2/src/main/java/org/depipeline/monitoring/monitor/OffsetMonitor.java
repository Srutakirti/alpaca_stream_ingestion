package org.depipeline.monitoring.monitor;

import java.util.Map;
import java.util.Optional;

/**
 * Interface for monitoring offset/progress of various components in the data pipeline.
 *
 * Implementations:
 * - KafkaOffsetMonitor: Monitors Kafka topic offsets
 * - SparkOffsetMonitor: Monitors Spark Structured Streaming checkpoint offsets
 * - PinotOffsetMonitor: Monitors Pinot real-time table consuming offsets
 */
public interface OffsetMonitor extends AutoCloseable {

    /**
     * Get current offsets for all partitions.
     *
     * @param identifier The identifier for what to monitor (e.g., topic name, table name, checkpoint path)
     * @return Map of partition number to offset, or empty if not available
     */
    Optional<Map<Integer, Long>> getOffsets(String identifier);

    /**
     * Get current offsets with additional context (e.g., topic name for Spark)
     *
     * @param identifier Primary identifier
     * @param context Additional context (e.g., topic name)
     * @return Map of partition number to offset, or empty if not available
     */
    default Optional<Map<Integer, Long>> getOffsets(String identifier, String context) {
        return getOffsets(identifier);
    }

    /**
     * Close any resources held by this monitor.
     */
    @Override
    void close();
}
