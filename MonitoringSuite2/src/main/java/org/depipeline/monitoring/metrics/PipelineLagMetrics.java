package org.depipeline.monitoring.metrics;

import java.util.Map;

/**
 * Represents lag metrics for a single data pipeline.
 *
 * Pipeline flow: Kafka Source -> Spark -> Kafka Sink -> Pinot
 *
 * Lag calculations:
 * - Spark Lag = Source Topic Total Offset - Spark Consumed Offset
 * - Pinot Lag = Sink Topic Total Offset - Pinot Consumed Offset
 */
public class PipelineLagMetrics {

    private final String pipelineName;
    private final long timestamp;

    // Raw offset data
    private final Map<Integer, Long> sourceTopicOffsets;
    private final Map<Integer, Long> sinkTopicOffsets;
    private final Map<Integer, Long> sparkOffsets;
    private final Map<Integer, Long> pinotOffsets;

    // Aggregated totals
    private final long sourceTotalOffset;
    private final long sinkTotalOffset;
    private final long sparkTotalOffset;
    private final long pinotTotalOffset;

    // Calculated lags
    private final long sparkLag;
    private final long pinotLag;

    public PipelineLagMetrics(String pipelineName,
                             Map<Integer, Long> sourceTopicOffsets,
                             Map<Integer, Long> sinkTopicOffsets,
                             Map<Integer, Long> sparkOffsets,
                             Map<Integer, Long> pinotOffsets) {
        this.pipelineName = pipelineName;
        this.timestamp = System.currentTimeMillis();

        this.sourceTopicOffsets = sourceTopicOffsets;
        this.sinkTopicOffsets = sinkTopicOffsets;
        this.sparkOffsets = sparkOffsets;
        this.pinotOffsets = pinotOffsets;

        // Calculate totals
        this.sourceTotalOffset = sumOffsets(sourceTopicOffsets);
        this.sinkTotalOffset = sumOffsets(sinkTopicOffsets);
        this.sparkTotalOffset = sumOffsets(sparkOffsets);
        this.pinotTotalOffset = sumOffsets(pinotOffsets);

        // Calculate lags
        this.sparkLag = sourceTotalOffset - sparkTotalOffset;
        this.pinotLag = sinkTotalOffset - pinotTotalOffset;
    }

    private long sumOffsets(Map<Integer, Long> offsets) {
        return offsets.values().stream()
                .mapToLong(Long::longValue)
                .sum();
    }

    // Getters
    public String getPipelineName() {
        return pipelineName;
    }

    public long getTimestamp() {
        return timestamp;
    }

    public Map<Integer, Long> getSourceTopicOffsets() {
        return sourceTopicOffsets;
    }

    public Map<Integer, Long> getSinkTopicOffsets() {
        return sinkTopicOffsets;
    }

    public Map<Integer, Long> getSparkOffsets() {
        return sparkOffsets;
    }

    public Map<Integer, Long> getPinotOffsets() {
        return pinotOffsets;
    }

    public long getSourceTotalOffset() {
        return sourceTotalOffset;
    }

    public long getSinkTotalOffset() {
        return sinkTotalOffset;
    }

    public long getSparkTotalOffset() {
        return sparkTotalOffset;
    }

    public long getPinotTotalOffset() {
        return pinotTotalOffset;
    }

    public long getSparkLag() {
        return sparkLag;
    }

    public long getPinotLag() {
        return pinotLag;
    }

    /**
     * Calculate delta (messages moved) compared to previous metrics
     */
    public MetricsDelta calculateDelta(PipelineLagMetrics previous) {
        if (previous == null) {
            return new MetricsDelta(0, 0, 0, 0);
        }

        return new MetricsDelta(
            this.sourceTotalOffset - previous.sourceTotalOffset,
            this.sinkTotalOffset - previous.sinkTotalOffset,
            this.sparkTotalOffset - previous.sparkTotalOffset,
            this.pinotTotalOffset - previous.pinotTotalOffset
        );
    }

    /**
     * Represents the delta (change) in offsets between two measurements
     */
    public static class MetricsDelta {
        private final long sourceMessagesMoved;
        private final long sinkMessagesMoved;
        private final long sparkMessagesProcessed;
        private final long pinotMessagesIngested;

        public MetricsDelta(long sourceMessagesMoved, long sinkMessagesMoved,
                           long sparkMessagesProcessed, long pinotMessagesIngested) {
            this.sourceMessagesMoved = sourceMessagesMoved;
            this.sinkMessagesMoved = sinkMessagesMoved;
            this.sparkMessagesProcessed = sparkMessagesProcessed;
            this.pinotMessagesIngested = pinotMessagesIngested;
        }

        public long getSourceMessagesMoved() {
            return sourceMessagesMoved;
        }

        public long getSinkMessagesMoved() {
            return sinkMessagesMoved;
        }

        public long getSparkMessagesProcessed() {
            return sparkMessagesProcessed;
        }

        public long getPinotMessagesIngested() {
            return pinotMessagesIngested;
        }
    }

    @Override
    public String toString() {
        return String.format(
            "PipelineLagMetrics{pipeline='%s', sourceTotal=%d, sparkTotal=%d (lag=%d), sinkTotal=%d, pinotTotal=%d (lag=%d)}",
            pipelineName, sourceTotalOffset, sparkTotalOffset, sparkLag,
            sinkTotalOffset, pinotTotalOffset, pinotLag
        );
    }
}
