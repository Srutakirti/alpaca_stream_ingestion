package org.depipeline.monitoring.metrics;

import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.assertj.core.api.Assertions.*;

class PipelineLagMetricsTest {

    @Test
    void shouldCalculateTotalOffsets() {
        Map<Integer, Long> sourceOffsets = Map.of(0, 100L, 1, 200L, 2, 150L);
        Map<Integer, Long> sinkOffsets = Map.of(0, 80L, 1, 180L, 2, 140L);
        Map<Integer, Long> sparkOffsets = Map.of(0, 90L, 1, 190L, 2, 145L);
        Map<Integer, Long> pinotOffsets = Map.of(0, 75L, 1, 175L, 2, 135L);

        PipelineLagMetrics metrics = new PipelineLagMetrics(
            "test-pipeline",
            sourceOffsets,
            sinkOffsets,
            sparkOffsets,
            pinotOffsets
        );

        assertThat(metrics.getSourceTotalOffset()).isEqualTo(450L); // 100+200+150
        assertThat(metrics.getSinkTotalOffset()).isEqualTo(400L);   // 80+180+140
        assertThat(metrics.getSparkTotalOffset()).isEqualTo(425L);  // 90+190+145
        assertThat(metrics.getPinotTotalOffset()).isEqualTo(385L);  // 75+175+135
    }

    @Test
    void shouldCalculateLag() {
        Map<Integer, Long> sourceOffsets = Map.of(0, 1000L);
        Map<Integer, Long> sinkOffsets = Map.of(0, 900L);
        Map<Integer, Long> sparkOffsets = Map.of(0, 850L);
        Map<Integer, Long> pinotOffsets = Map.of(0, 800L);

        PipelineLagMetrics metrics = new PipelineLagMetrics(
            "test-pipeline",
            sourceOffsets,
            sinkOffsets,
            sparkOffsets,
            pinotOffsets
        );

        assertThat(metrics.getSparkLag()).isEqualTo(150L);  // 1000 - 850
        assertThat(metrics.getPinotLag()).isEqualTo(100L);  // 900 - 800
    }

    @Test
    void shouldCalculateDelta() {
        Map<Integer, Long> sourceOffsets1 = Map.of(0, 100L);
        Map<Integer, Long> sinkOffsets1 = Map.of(0, 90L);
        Map<Integer, Long> sparkOffsets1 = Map.of(0, 80L);
        Map<Integer, Long> pinotOffsets1 = Map.of(0, 70L);

        PipelineLagMetrics previous = new PipelineLagMetrics(
            "test-pipeline",
            sourceOffsets1,
            sinkOffsets1,
            sparkOffsets1,
            pinotOffsets1
        );

        Map<Integer, Long> sourceOffsets2 = Map.of(0, 150L);
        Map<Integer, Long> sinkOffsets2 = Map.of(0, 130L);
        Map<Integer, Long> sparkOffsets2 = Map.of(0, 120L);
        Map<Integer, Long> pinotOffsets2 = Map.of(0, 110L);

        PipelineLagMetrics current = new PipelineLagMetrics(
            "test-pipeline",
            sourceOffsets2,
            sinkOffsets2,
            sparkOffsets2,
            pinotOffsets2
        );

        PipelineLagMetrics.MetricsDelta delta = current.calculateDelta(previous);

        assertThat(delta.getSourceMessagesMoved()).isEqualTo(50L);      // 150 - 100
        assertThat(delta.getSinkMessagesMoved()).isEqualTo(40L);        // 130 - 90
        assertThat(delta.getSparkMessagesProcessed()).isEqualTo(40L);   // 120 - 80
        assertThat(delta.getPinotMessagesIngested()).isEqualTo(40L);    // 110 - 70
    }

    @Test
    void shouldHandleNullPreviousMetricsInDelta() {
        Map<Integer, Long> offsets = Map.of(0, 100L);

        PipelineLagMetrics current = new PipelineLagMetrics(
            "test-pipeline",
            offsets,
            offsets,
            offsets,
            offsets
        );

        PipelineLagMetrics.MetricsDelta delta = current.calculateDelta(null);

        assertThat(delta.getSourceMessagesMoved()).isEqualTo(0L);
        assertThat(delta.getSinkMessagesMoved()).isEqualTo(0L);
        assertThat(delta.getSparkMessagesProcessed()).isEqualTo(0L);
        assertThat(delta.getPinotMessagesIngested()).isEqualTo(0L);
    }
}
