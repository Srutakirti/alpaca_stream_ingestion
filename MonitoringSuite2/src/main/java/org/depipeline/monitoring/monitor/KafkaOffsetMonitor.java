package org.depipeline.monitoring.monitor;

import org.apache.kafka.clients.admin.AdminClient;
import org.apache.kafka.clients.admin.AdminClientConfig;
import org.apache.kafka.clients.admin.ListOffsetsResult;
import org.apache.kafka.clients.admin.OffsetSpec;
import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.clients.consumer.KafkaConsumer;
import org.apache.kafka.common.PartitionInfo;
import org.apache.kafka.common.TopicPartition;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.depipeline.monitoring.util.RetryHelper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.time.Duration;
import java.util.*;
import java.util.concurrent.ExecutionException;

/**
 * Monitors Kafka topic offsets using Kafka AdminClient API.
 * Implements AutoCloseable for proper resource management.
 */
public class KafkaOffsetMonitor implements OffsetMonitor {

    private static final Logger logger = LoggerFactory.getLogger(KafkaOffsetMonitor.class);

    private final AdminClient adminClient;
    private final KafkaConsumer<String, String> consumer;
    private final int maxRetries;
    private final long retryBackoffMs;
    private final Duration requestTimeout;

    public KafkaOffsetMonitor(String bootstrapServers, int maxRetries, long retryBackoffMs, long requestTimeoutMs) {
        // Configure Admin Client
        Properties adminProps = new Properties();
        adminProps.put(AdminClientConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);
        adminProps.put(AdminClientConfig.REQUEST_TIMEOUT_MS_CONFIG, requestTimeoutMs);
        this.adminClient = AdminClient.create(adminProps);

        // Configure Consumer (used to get partition info)
        Properties consumerProps = new Properties();
        consumerProps.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);
        consumerProps.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName());
        consumerProps.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName());
        consumerProps.put(ConsumerConfig.GROUP_ID_CONFIG, "offset-monitor-" + UUID.randomUUID());
        consumerProps.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "earliest");
        consumerProps.put(ConsumerConfig.REQUEST_TIMEOUT_MS_CONFIG, requestTimeoutMs);
        this.consumer = new KafkaConsumer<>(consumerProps);

        this.maxRetries = maxRetries;
        this.retryBackoffMs = retryBackoffMs;
        this.requestTimeout = Duration.ofMillis(requestTimeoutMs);

        logger.info("Initialized KafkaOffsetMonitor for {}", bootstrapServers);
    }

    @Override
    public Optional<Map<Integer, Long>> getOffsets(String topicName) {
        try {
            return RetryHelper.executeWithRetry(
                () -> Optional.of(fetchOffsets(topicName)),
                maxRetries,
                retryBackoffMs,
                "Kafka offset check for topic: " + topicName
            );
        } catch (Exception e) {
            logger.error("Failed to get offsets for topic: {}", topicName, e);
            return Optional.empty();
        }
    }

    /**
     * Fetch latest offsets for all partitions of a topic
     */
    private Map<Integer, Long> fetchOffsets(String topicName) {
        // Get partition information for the topic
        List<PartitionInfo> partitions = consumer.partitionsFor(topicName, requestTimeout);

        if (partitions == null || partitions.isEmpty()) {
            logger.warn("Topic '{}' not found or has no partitions", topicName);
            return Collections.emptyMap();
        }

        // Create TopicPartition objects and OffsetSpec for latest offsets
        Map<TopicPartition, OffsetSpec> offsetSpecs = new HashMap<>();
        for (PartitionInfo partition : partitions) {
            TopicPartition tp = new TopicPartition(partition.topic(), partition.partition());
            offsetSpecs.put(tp, OffsetSpec.latest());
        }

        // Get latest offsets using admin client
        ListOffsetsResult offsetsResult = adminClient.listOffsets(offsetSpecs);

        Map<Integer, Long> partitionOffsets = new HashMap<>();
        for (TopicPartition tp : offsetSpecs.keySet()) {
            try {
                long latestOffset = offsetsResult.partitionResult(tp).get().offset();
                partitionOffsets.put(tp.partition(), latestOffset);
                logger.debug("Topic: {}, Partition: {}, Offset: {}", tp.topic(), tp.partition(), latestOffset);
            } catch (InterruptedException | ExecutionException e) {
                logger.warn("Failed to get offset for partition {}: {}", tp.partition(), e.getMessage());
                // Continue with other partitions
            }
        }

        logger.debug("Fetched offsets for topic '{}': {} partitions", topicName, partitionOffsets.size());
        return partitionOffsets;
    }

    @Override
    public void close() {
        try {
            if (consumer != null) {
                consumer.close();
                logger.debug("Closed Kafka consumer");
            }
        } catch (Exception e) {
            logger.warn("Error closing Kafka consumer", e);
        }

        try {
            if (adminClient != null) {
                adminClient.close();
                logger.debug("Closed Kafka admin client");
            }
        } catch (Exception e) {
            logger.warn("Error closing Kafka admin client", e);
        }

        logger.info("KafkaOffsetMonitor closed");
    }
}
