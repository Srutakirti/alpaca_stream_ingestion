package org.depipeline.monitoring;

import org.depipeline.monitoring.config.ConfigLoader;
import org.depipeline.monitoring.config.MonitoringConfig;
import org.depipeline.monitoring.config.PipelineConfig;
import org.depipeline.monitoring.metrics.PipelineLagMetrics;
import org.depipeline.monitoring.metrics.PartitionLagAnalyzer;
import org.depipeline.monitoring.monitor.KafkaOffsetMonitor;
import org.depipeline.monitoring.monitor.PinotOffsetMonitor;
import org.depipeline.monitoring.monitor.SparkOffsetMonitor;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.concurrent.atomic.AtomicBoolean;

/**
 * Main monitoring application for tracking data pipeline progress.
 *
 * Monitors the flow: Kafka Source -> Spark Streaming -> Kafka Sink -> Pinot
 *
 * Features:
 * - Multi-pipeline support
 * - Lag calculation (not just deltas)
 * - Graceful shutdown handling
 * - Partition-level visibility
 * - Configurable via YAML with environment variable overrides
 */
public class MonitoringApplication {

    private static final Logger logger = LoggerFactory.getLogger(MonitoringApplication.class);
    private static final DateTimeFormatter DATE_FORMATTER = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    private final AtomicBoolean running = new AtomicBoolean(true);
    private final Map<String, PipelineLagMetrics> previousMetrics = new HashMap<>();

    private final MonitoringConfig config;
    private final KafkaOffsetMonitor kafkaMonitor;
    private final SparkOffsetMonitor sparkMonitor;
    private final PinotOffsetMonitor pinotMonitor;

    public MonitoringApplication(MonitoringConfig config) {
        this.config = config;

        // Initialize monitors
        this.kafkaMonitor = new KafkaOffsetMonitor(
            config.getKafka().getBootstrapServers(),
            config.getMonitoring().getMaxRetries(),
            config.getMonitoring().getRetryBackoffMs(),
            config.getMonitoring().getRequestTimeoutMs()
        );

        this.sparkMonitor = new SparkOffsetMonitor(
            config.getMinio().getEndpoint(),
            config.getMinio().getAccessKey(),
            config.getMinio().getSecretKey(),
            "data", // bucket name from first pipeline
            config.getMonitoring().getMaxRetries(),
            config.getMonitoring().getRetryBackoffMs()
        );

        this.pinotMonitor = new PinotOffsetMonitor(
            config.getPinot().getControllerUrl(),
            config.getMonitoring().getMaxRetries(),
            config.getMonitoring().getRetryBackoffMs(),
            config.getMonitoring().getRequestTimeoutMs()
        );

        // Setup shutdown hook
        Runtime.getRuntime().addShutdownHook(new Thread(this::shutdown));
    }

    /**
     * Main monitoring loop
     */
    public void run() {
        logger.info("Starting monitoring for {} pipeline(s)", config.getEnabledPipelines().size());

        long intervalMs = config.getMonitoring().getIntervalSeconds() * 1000L;

        while (running.get()) {
            try {
                monitorAllPipelines();
                Thread.sleep(intervalMs);
            } catch (InterruptedException e) {
                logger.info("Monitoring interrupted");
                Thread.currentThread().interrupt();
                break;
            } catch (Exception e) {
                logger.error("Error in monitoring loop", e);
            }
        }

        logger.info("Monitoring loop exited");
    }

    /**
     * Monitor all enabled pipelines
     */
    private void monitorAllPipelines() {
        String timestamp = LocalDateTime.now().format(DATE_FORMATTER);
        System.out.println("\n" + "=".repeat(80));
        System.out.println("Pipeline Monitoring Report - " + timestamp);
        System.out.println("=".repeat(80));

        for (PipelineConfig pipeline : config.getEnabledPipelines()) {
            monitorPipeline(pipeline);
        }
    }

    /**
     * Monitor a single pipeline
     */
    private void monitorPipeline(PipelineConfig pipeline) {
        logger.debug("Monitoring pipeline: {}", pipeline.getName());

        try {
            // Fetch offsets from all components
            Map<Integer, Long> sourceOffsets = kafkaMonitor.getOffsets(pipeline.getSourceKafkaTopic())
                    .orElse(Collections.emptyMap());

            Map<Integer, Long> sinkOffsets = kafkaMonitor.getOffsets(pipeline.getSinkKafkaTopic())
                    .orElse(Collections.emptyMap());

            Map<Integer, Long> sparkOffsets = sparkMonitor.getOffsets(
                    pipeline.getSparkCheckpointPath(),
                    pipeline.getSourceKafkaTopic()
            ).orElse(Collections.emptyMap());

            Map<Integer, Long> pinotOffsets = pinotMonitor.getOffsets(pipeline.getPinotTable())
                    .orElse(Collections.emptyMap());

            // Calculate metrics
            PipelineLagMetrics currentMetrics = new PipelineLagMetrics(
                pipeline.getName(),
                sourceOffsets,
                sinkOffsets,
                sparkOffsets,
                pinotOffsets
            );

            // Get previous metrics for delta calculation
            PipelineLagMetrics previous = previousMetrics.get(pipeline.getName());
            PipelineLagMetrics.MetricsDelta delta = currentMetrics.calculateDelta(previous);

            // Store current metrics for next iteration
            previousMetrics.put(pipeline.getName(), currentMetrics);

            // Display results
            displayPipelineMetrics(pipeline.getName(), currentMetrics, delta);

        } catch (Exception e) {
            logger.error("Error monitoring pipeline: {}", pipeline.getName(), e);
            System.out.println("\n[ERROR] Failed to monitor pipeline: " + pipeline.getName());
        }
    }

    /**
     * Display pipeline metrics in formatted output
     */
    private void displayPipelineMetrics(String pipelineName, PipelineLagMetrics metrics,
                                       PipelineLagMetrics.MetricsDelta delta) {
        System.out.println("\n" + "-".repeat(80));
        System.out.println("Pipeline: " + pipelineName);
        System.out.println("-".repeat(80));

        // Lag Summary
        System.out.println("\n  LAG SUMMARY:");
        System.out.printf("    Spark Lag:     %,10d messages (behind source topic)%n", metrics.getSparkLag());
        System.out.printf("    Pinot Lag:     %,10d messages (behind sink topic)%n", metrics.getPinotLag());

        // Delta (messages moved since last check)
        System.out.println("\n  THROUGHPUT (last " + config.getMonitoring().getIntervalSeconds() + "s):");
        System.out.printf("    Source Topic:  %,10d messages%n", delta.getSourceMessagesMoved());
        System.out.printf("    Spark Processed: %,10d messages%n", delta.getSparkMessagesProcessed());
        System.out.printf("    Sink Topic:    %,10d messages%n", delta.getSinkMessagesMoved());
        System.out.printf("    Pinot Ingested: %,10d messages%n", delta.getPinotMessagesIngested());

        // Total Offsets
        System.out.println("\n  TOTAL OFFSETS:");
        System.out.printf("    Source Topic:  %,10d%n", metrics.getSourceTotalOffset());
        System.out.printf("    Spark Consumed: %,10d%n", metrics.getSparkTotalOffset());
        System.out.printf("    Sink Topic:    %,10d%n", metrics.getSinkTotalOffset());
        System.out.printf("    Pinot Consumed: %,10d%n", metrics.getPinotTotalOffset());

        // Partition details (if lag detected)
        if (metrics.getSparkLag() > 1000) {
            displayPartitionDetails("Spark", metrics.getSourceTopicOffsets(), metrics.getSparkOffsets());
        }

        if (metrics.getPinotLag() > 1000) {
            displayPartitionDetails("Pinot", metrics.getSinkTopicOffsets(), metrics.getPinotOffsets());
        }
    }

    /**
     * Display partition-level details for debugging
     */
    private void displayPartitionDetails(String component, Map<Integer, Long> sourceOffsets,
                                        Map<Integer, Long> consumerOffsets) {
        Map<Integer, PartitionLagAnalyzer.PartitionLag> partitionLags =
            PartitionLagAnalyzer.analyzePartitionLag(sourceOffsets, consumerOffsets, component);

        Map<Integer, PartitionLagAnalyzer.PartitionLag> laggingPartitions =
            PartitionLagAnalyzer.detectLaggingPartitions(partitionLags, 1.5);

        if (!laggingPartitions.isEmpty()) {
            System.out.println("\n  [WARNING] Lagging Partitions for " + component + ":");
            laggingPartitions.values().forEach(lag ->
                System.out.printf("    %s%n", lag)
            );
        }
    }

    /**
     * Graceful shutdown
     */
    private void shutdown() {
        logger.info("Shutting down monitoring application...");
        running.set(false);

        // Close all monitors
        try {
            kafkaMonitor.close();
            sparkMonitor.close();
            pinotMonitor.close();
            logger.info("All monitors closed successfully");
        } catch (Exception e) {
            logger.error("Error closing monitors", e);
        }

        logger.info("Shutdown complete");
    }

    /**
     * Application entry point
     */
    public static void main(String[] args) {
        try {
            logger.info("Loading configuration...");
            MonitoringConfig config = ConfigLoader.loadConfig();

            logger.info("Starting Monitoring Application");
            MonitoringApplication app = new MonitoringApplication(config);
            app.run();

        } catch (Exception e) {
            logger.error("Fatal error in monitoring application", e);
            System.err.println("ERROR: " + e.getMessage());
            System.exit(1);
        }
    }
}
