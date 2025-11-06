package org.depipeline.monitoring.monitor;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.depipeline.monitoring.util.RetryHelper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.*;

/**
 * Monitors Pinot real-time table consuming offsets via Pinot Controller API.
 * Implements AutoCloseable for proper resource management.
 */
public class PinotOffsetMonitor implements OffsetMonitor {

    private static final Logger logger = LoggerFactory.getLogger(PinotOffsetMonitor.class);

    private final String controllerBaseUrl;
    private final HttpClient httpClient;
    private final int maxRetries;
    private final long retryBackoffMs;
    private final ObjectMapper objectMapper;

    public PinotOffsetMonitor(String controllerBaseUrl, int maxRetries, long retryBackoffMs, long requestTimeoutMs) {
        // Ensure base URL ends with /
        this.controllerBaseUrl = controllerBaseUrl.endsWith("/") ? controllerBaseUrl : controllerBaseUrl + "/";

        this.httpClient = HttpClient.newBuilder()
                .connectTimeout(Duration.ofMillis(requestTimeoutMs))
                .build();

        this.maxRetries = maxRetries;
        this.retryBackoffMs = retryBackoffMs;
        this.objectMapper = new ObjectMapper();

        logger.info("Initialized PinotOffsetMonitor for controller: {}", controllerBaseUrl);
    }

    @Override
    public Optional<Map<Integer, Long>> getOffsets(String tableName) {
        try {
            return RetryHelper.executeWithRetry(
                () -> Optional.of(fetchPinotOffsets(tableName)),
                maxRetries,
                retryBackoffMs,
                "Pinot offset check for table: " + tableName
            );
        } catch (Exception e) {
            logger.error("Failed to get Pinot offsets for table: {}", tableName, e);
            return Optional.empty();
        }
    }

    /**
     * Fetch consuming offsets from Pinot Controller API
     *
     * API endpoint: /tables/{tableName}/consumingSegmentsInfo
     */
    private Map<Integer, Long> fetchPinotOffsets(String tableName) throws Exception {
        String url = controllerBaseUrl + tableName + "/consumingSegmentsInfo";

        HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(url))
                .GET()
                .timeout(Duration.ofSeconds(10))
                .build();

        HttpResponse<String> response = httpClient.send(request, HttpResponse.BodyHandlers.ofString());

        if (response.statusCode() != 200) {
            throw new Exception("Pinot API returned status code: " + response.statusCode());
        }

        return parseConsumingSegmentsInfo(response.body());
    }

    /**
     * Parse Pinot consumingSegmentsInfo API response to extract partition offsets.
     *
     * Response structure:
     * {
     *   "_segmentToConsumingInfoMap": {
     *     "segment_name__0__0__timestamp": [
     *       {
     *         "partitionToOffsetMap": {
     *           "0": "12345",
     *           "1": "67890"
     *         }
     *       }
     *     ]
     *   }
     * }
     */
    private Map<Integer, Long> parseConsumingSegmentsInfo(String responseBody) throws Exception {
        JsonNode root = objectMapper.readTree(responseBody);
        Map<Integer, Long> partitionOffsets = new HashMap<>();

        JsonNode segmentsMap = root.path("_segmentToConsumingInfoMap");

        if (segmentsMap.isMissingNode()) {
            logger.warn("No consuming segments found in Pinot response");
            return Collections.emptyMap();
        }

        Iterator<String> segmentNames = segmentsMap.fieldNames();

        while (segmentNames.hasNext()) {
            String segmentName = segmentNames.next();
            JsonNode segmentInfoArray = segmentsMap.get(segmentName);

            if (segmentInfoArray.isArray() && !segmentInfoArray.isEmpty()) {
                JsonNode partitionToOffsetMap = segmentInfoArray.get(0).path("partitionToOffsetMap");

                if (!partitionToOffsetMap.isMissingNode()) {
                    Iterator<String> partitions = partitionToOffsetMap.fieldNames();

                    while (partitions.hasNext()) {
                        String partition = partitions.next();
                        long offset = partitionToOffsetMap.get(partition).asLong();

                        // Update to the maximum offset if partition already exists
                        // (in case of multiple consuming segments for the same partition)
                        int partitionNum = Integer.parseInt(partition);
                        partitionOffsets.merge(partitionNum, offset, Math::max);

                        logger.debug("Segment: {}, Partition: {}, Offset: {}", segmentName, partition, offset);
                    }
                }
            }
        }

        logger.debug("Parsed Pinot offsets: {} partitions", partitionOffsets.size());
        return partitionOffsets;
    }

    @Override
    public void close() {
        // HttpClient doesn't require explicit closing
        logger.info("PinotOffsetMonitor closed");
    }
}
