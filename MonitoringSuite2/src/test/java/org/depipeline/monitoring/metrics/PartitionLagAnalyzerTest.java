package org.depipeline.monitoring.metrics;

import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.assertj.core.api.Assertions.*;

class PartitionLagAnalyzerTest {

    @Test
    void shouldAnalyzePartitionLag() {
        Map<Integer, Long> sourceOffsets = Map.of(0, 1000L, 1, 2000L, 2, 1500L);
        Map<Integer, Long> consumerOffsets = Map.of(0, 900L, 1, 1800L, 2, 1400L);

        Map<Integer, PartitionLagAnalyzer.PartitionLag> result =
            PartitionLagAnalyzer.analyzePartitionLag(sourceOffsets, consumerOffsets, "Spark");

        assertThat(result).hasSize(3);
        assertThat(result.get(0).getLag()).isEqualTo(100L);  // 1000 - 900
        assertThat(result.get(1).getLag()).isEqualTo(200L);  // 2000 - 1800
        assertThat(result.get(2).getLag()).isEqualTo(100L);  // 1500 - 1400
    }

    @Test
    void shouldHandleMissingConsumerOffsets() {
        Map<Integer, Long> sourceOffsets = Map.of(0, 1000L, 1, 2000L);
        Map<Integer, Long> consumerOffsets = Map.of(0, 900L); // Missing partition 1

        Map<Integer, PartitionLagAnalyzer.PartitionLag> result =
            PartitionLagAnalyzer.analyzePartitionLag(sourceOffsets, consumerOffsets, "Spark");

        assertThat(result).hasSize(2);
        assertThat(result.get(0).getLag()).isEqualTo(100L);   // 1000 - 900
        assertThat(result.get(1).getLag()).isEqualTo(2000L);  // 2000 - 0 (default)
    }

    @Test
    void shouldDetectLaggingPartitions() {
        // Create partition lags where partition 1 is significantly behind
        Map<Integer, PartitionLagAnalyzer.PartitionLag> partitionLags = Map.of(
            0, new PartitionLagAnalyzer.PartitionLag(0, 1000L, 900L, 100L, "Spark"),
            1, new PartitionLagAnalyzer.PartitionLag(1, 2000L, 1200L, 800L, "Spark"),
            2, new PartitionLagAnalyzer.PartitionLag(2, 1500L, 1400L, 100L, "Spark")
        );

        // Average lag = (100 + 800 + 100) / 3 = 333.33
        // Threshold (1.5x) = 500
        // Only partition 1 (lag=800) should be detected
        Map<Integer, PartitionLagAnalyzer.PartitionLag> lagging =
            PartitionLagAnalyzer.detectLaggingPartitions(partitionLags, 1.5);

        assertThat(lagging).hasSize(1);
        assertThat(lagging).containsKey(1);
        assertThat(lagging.get(1).getLag()).isEqualTo(800L);
    }

    @Test
    void shouldReturnEmptyWhenNoLaggingPartitions() {
        // All partitions have similar lag
        Map<Integer, PartitionLagAnalyzer.PartitionLag> partitionLags = Map.of(
            0, new PartitionLagAnalyzer.PartitionLag(0, 1000L, 900L, 100L, "Spark"),
            1, new PartitionLagAnalyzer.PartitionLag(1, 2000L, 1900L, 100L, "Spark"),
            2, new PartitionLagAnalyzer.PartitionLag(2, 1500L, 1400L, 100L, "Spark")
        );

        Map<Integer, PartitionLagAnalyzer.PartitionLag> lagging =
            PartitionLagAnalyzer.detectLaggingPartitions(partitionLags, 1.5);

        assertThat(lagging).isEmpty();
    }

    @Test
    void shouldHandleEmptyPartitionLags() {
        Map<Integer, PartitionLagAnalyzer.PartitionLag> lagging =
            PartitionLagAnalyzer.detectLaggingPartitions(Map.of(), 1.5);

        assertThat(lagging).isEmpty();
    }
}
