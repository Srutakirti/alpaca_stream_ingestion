package org.depipeline.monitoring.util;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.function.Supplier;

/**
 * Utility class for retrying operations with exponential backoff.
 */
public class RetryHelper {

    private static final Logger logger = LoggerFactory.getLogger(RetryHelper.class);

    /**
     * Execute an operation with retry logic and exponential backoff.
     *
     * @param operation The operation to execute
     * @param maxRetries Maximum number of retry attempts
     * @param initialBackoffMs Initial backoff delay in milliseconds
     * @param operationName Name of the operation (for logging)
     * @param <T> Return type
     * @return Result of the operation
     * @throws Exception if all retry attempts fail
     */
    public static <T> T executeWithRetry(
            Supplier<T> operation,
            int maxRetries,
            long initialBackoffMs,
            String operationName) throws Exception {

        Exception lastException = null;
        long backoffMs = initialBackoffMs;

        for (int attempt = 1; attempt <= maxRetries; attempt++) {
            try {
                return operation.get();
            } catch (Exception e) {
                lastException = e;

                if (attempt < maxRetries) {
                    logger.warn("Attempt {}/{} failed for {}: {}. Retrying in {}ms...",
                               attempt, maxRetries, operationName, e.getMessage(), backoffMs);

                    try {
                        Thread.sleep(backoffMs);
                    } catch (InterruptedException ie) {
                        Thread.currentThread().interrupt();
                        throw new Exception("Retry interrupted", ie);
                    }

                    // Exponential backoff: double the wait time for next attempt
                    backoffMs *= 2;
                } else {
                    logger.error("All {} retry attempts failed for {}", maxRetries, operationName, e);
                }
            }
        }

        throw new Exception("Operation failed after " + maxRetries + " retries: " + operationName, lastException);
    }

    /**
     * Execute an operation with retry logic (with default operation name).
     */
    public static <T> T executeWithRetry(
            Supplier<T> operation,
            int maxRetries,
            long initialBackoffMs) throws Exception {
        return executeWithRetry(operation, maxRetries, initialBackoffMs, "operation");
    }
}
