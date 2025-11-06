package org.depipeline.monitoring.metrics;

import java.util.HashMap;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * Analyzes partition-level lag to detect issues with individual partitions.
 */
public class PartitionLagAnalyzer {

    /**
     * Calculate per-partition lag
     */
    public static Map<Integer, PartitionLag> analyzePartitionLag(
            Map<Integer, Long> sourceOffsets,
            Map<Integer, Long> consumerOffsets,
            String component) {

        Map<Integer, PartitionLag> partitionLags = new HashMap<>();

        for (Map.Entry<Integer, Long> entry : sourceOffsets.entrySet()) {
            int partition = entry.getKey();
            long sourceOffset = entry.getValue();
            long consumerOffset = consumerOffsets.getOrDefault(partition, 0L);
            long lag = sourceOffset - consumerOffset;

            partitionLags.put(partition, new PartitionLag(partition, sourceOffset, consumerOffset, lag, component));
        }

        return partitionLags;
    }

    /**
     * Detect lagging partitions (those with lag significantly higher than average)
     */
    public static Map<Integer, PartitionLag> detectLaggingPartitions(
            Map<Integer, PartitionLag> partitionLags,
            double thresholdMultiplier) {

        if (partitionLags.isEmpty()) {
            return Map.of();
        }

        // Calculate average lag
        double avgLag = partitionLags.values().stream()
                .mapToLong(PartitionLag::getLag)
                .average()
                .orElse(0.0);

        double threshold = avgLag * thresholdMultiplier;

        // Filter partitions with lag above threshold
        return partitionLags.entrySet().stream()
                .filter(entry -> entry.getValue().getLag() > threshold)
                .collect(Collectors.toMap(Map.Entry::getKey, Map.Entry::getValue));
    }

    /**
     * Represents lag information for a single partition
     */
    public static class PartitionLag {
        private final int partition;
        private final long sourceOffset;
        private final long consumerOffset;
        private final long lag;
        private final String component;

        public PartitionLag(int partition, long sourceOffset, long consumerOffset, long lag, String component) {
            this.partition = partition;
            this.sourceOffset = sourceOffset;
            this.consumerOffset = consumerOffset;
            this.lag = lag;
            this.component = component;
        }

        public int getPartition() {
            return partition;
        }

        public long getSourceOffset() {
            return sourceOffset;
        }

        public long getConsumerOffset() {
            return consumerOffset;
        }

        public long getLag() {
            return lag;
        }

        public String getComponent() {
            return component;
        }

        @Override
        public String toString() {
            return String.format("Partition %d [%s]: source=%d, consumer=%d, lag=%d",
                    partition, component, sourceOffset, consumerOffset, lag);
        }
    }
}
