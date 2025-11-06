package org.depipeline.monitoring.monitor;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.minio.GetObjectArgs;
import io.minio.ListObjectsArgs;
import io.minio.MinioClient;
import io.minio.Result;
import io.minio.messages.Item;
import org.depipeline.monitoring.util.RetryHelper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.stream.StreamSupport;

/**
 * Monitors Spark Structured Streaming checkpoint offsets stored in MinIO/S3.
 * Implements AutoCloseable for proper resource management.
 */
public class SparkOffsetMonitor implements OffsetMonitor {

    private static final Logger logger = LoggerFactory.getLogger(SparkOffsetMonitor.class);

    private final MinioClient minioClient;
    private final String bucketName;
    private final int maxRetries;
    private final long retryBackoffMs;
    private final ObjectMapper objectMapper;

    public SparkOffsetMonitor(String minioEndpoint, String accessKey, String secretKey,
                              String bucketName, int maxRetries, long retryBackoffMs) {
        this.minioClient = MinioClient.builder()
                .endpoint(minioEndpoint)
                .credentials(accessKey, secretKey)
                .build();
        this.bucketName = bucketName;
        this.maxRetries = maxRetries;
        this.retryBackoffMs = retryBackoffMs;
        this.objectMapper = new ObjectMapper();

        logger.info("Initialized SparkOffsetMonitor for MinIO: {}, bucket: {}", minioEndpoint, bucketName);
    }

    @Override
    public Optional<Map<Integer, Long>> getOffsets(String checkpointPath) {
        logger.warn("getOffsets(String) called without topic name. Use getOffsets(checkpointPath, topicName) instead.");
        return Optional.empty();
    }

    @Override
    public Optional<Map<Integer, Long>> getOffsets(String checkpointPath, String topicName) {
        try {
            return RetryHelper.executeWithRetry(
                () -> Optional.of(fetchSparkOffsets(checkpointPath, topicName)),
                maxRetries,
                retryBackoffMs,
                "Spark offset check for checkpoint: " + checkpointPath
            );
        } catch (Exception e) {
            logger.error("Failed to get Spark offsets for checkpoint: {}", checkpointPath, e);
            return Optional.empty();
        }
    }

    /**
     * Fetch Spark checkpoint offsets from MinIO
     */
    private Map<Integer, Long> fetchSparkOffsets(String checkpointPath, String topicName) throws Exception {
        // Get the latest checkpoint file
        String latestCheckpointFile = getLatestCheckpointFile(checkpointPath);

        if (latestCheckpointFile == null) {
            logger.warn("No checkpoint files found at path: {}", checkpointPath);
            return Collections.emptyMap();
        }

        logger.debug("Reading checkpoint file: {}", latestCheckpointFile);

        // Read the checkpoint file
        String checkpointContent = readCheckpointFile(latestCheckpointFile);

        // Parse the checkpoint content to extract offsets
        return parseCheckpointOffsets(checkpointContent, topicName);
    }

    /**
     * Get the latest checkpoint file from MinIO based on last modified time
     */
    private String getLatestCheckpointFile(String prefix) throws Exception {
        Iterable<Result<Item>> results = minioClient.listObjects(
            ListObjectsArgs.builder()
                .bucket(bucketName)
                .prefix(prefix)
                .recursive(false)
                .build()
        );

        Optional<Item> latest = StreamSupport.stream(results.spliterator(), false)
            .map(result -> {
                try {
                    return result.get();
                } catch (Exception e) {
                    throw new RuntimeException("Error listing checkpoint files", e);
                }
            })
            .max(Comparator.comparing(Item::lastModified));

        return latest.map(Item::objectName).orElse(null);
    }

    /**
     * Read checkpoint file content from MinIO
     */
    private String readCheckpointFile(String objectName) throws Exception {
        try (InputStream stream = minioClient.getObject(
                GetObjectArgs.builder()
                    .bucket(bucketName)
                    .object(objectName)
                    .build())) {
            return new String(stream.readAllBytes(), StandardCharsets.UTF_8);
        }
    }

    /**
     * Parse Spark checkpoint file to extract partition offsets for a specific topic.
     *
     * Spark checkpoint format (last line contains JSON):
     * v1
     * {"batchWatermarkMs":0,"batchTimestampMs":1234567890,"conf":{...}}
     * {"topic-name":{"0":100,"1":200,"2":150}}
     */
    private Map<Integer, Long> parseCheckpointOffsets(String checkpointContent, String topicName) throws Exception {
        String[] lines = checkpointContent.split("\n");

        if (lines.length == 0) {
            logger.warn("Empty checkpoint file");
            return Collections.emptyMap();
        }

        // The last line contains the offset information
        String offsetLine = lines[lines.length - 1];
        JsonNode root = objectMapper.readTree(offsetLine);

        // Extract offsets for the specified topic
        JsonNode topicOffsets = root.get(topicName);

        if (topicOffsets == null) {
            logger.warn("Topic '{}' not found in checkpoint file", topicName);
            return Collections.emptyMap();
        }

        Map<Integer, Long> offsets = objectMapper.convertValue(
            topicOffsets,
            new TypeReference<Map<Integer, Long>>() {}
        );

        logger.debug("Parsed Spark offsets for topic '{}': {} partitions", topicName, offsets.size());
        return offsets;
    }

    @Override
    public void close() {
        // MinioClient doesn't require explicit closing in newer versions
        // But we log for consistency
        logger.info("SparkOffsetMonitor closed");
    }
}
