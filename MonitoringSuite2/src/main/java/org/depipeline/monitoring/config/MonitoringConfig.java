package org.depipeline.monitoring.config;

import com.fasterxml.jackson.annotation.JsonProperty;

import java.util.ArrayList;
import java.util.List;

/**
 * Main configuration class for the monitoring application.
 * Maps to the monitoring-config.yaml file structure.
 */
public class MonitoringConfig {

    private KafkaConfig kafka;
    private MinioConfig minio;
    private PinotConfig pinot;
    private MonitoringSettings monitoring;
    private List<PipelineConfig> pipelines = new ArrayList<>();

    // Inner configuration classes
    public static class KafkaConfig {
        private String bootstrapServers;

        public String getBootstrapServers() {
            return bootstrapServers;
        }

        public void setBootstrapServers(String bootstrapServers) {
            this.bootstrapServers = bootstrapServers;
        }
    }

    public static class MinioConfig {
        private String endpoint;
        private String accessKey;
        private String secretKey;

        public String getEndpoint() {
            return endpoint;
        }

        public void setEndpoint(String endpoint) {
            this.endpoint = endpoint;
        }

        public String getAccessKey() {
            return accessKey;
        }

        public void setAccessKey(String accessKey) {
            this.accessKey = accessKey;
        }

        public String getSecretKey() {
            return secretKey;
        }

        public void setSecretKey(String secretKey) {
            this.secretKey = secretKey;
        }
    }

    public static class PinotConfig {
        private String controllerUrl;

        public String getControllerUrl() {
            return controllerUrl;
        }

        public void setControllerUrl(String controllerUrl) {
            this.controllerUrl = controllerUrl;
        }
    }

    public static class MonitoringSettings {
        private int intervalSeconds = 30;
        private int maxRetries = 3;
        private long retryBackoffMs = 1000;
        private long requestTimeoutMs = 10000;

        public int getIntervalSeconds() {
            return intervalSeconds;
        }

        public void setIntervalSeconds(int intervalSeconds) {
            this.intervalSeconds = intervalSeconds;
        }

        public int getMaxRetries() {
            return maxRetries;
        }

        public void setMaxRetries(int maxRetries) {
            this.maxRetries = maxRetries;
        }

        public long getRetryBackoffMs() {
            return retryBackoffMs;
        }

        public void setRetryBackoffMs(long retryBackoffMs) {
            this.retryBackoffMs = retryBackoffMs;
        }

        public long getRequestTimeoutMs() {
            return requestTimeoutMs;
        }

        public void setRequestTimeoutMs(long requestTimeoutMs) {
            this.requestTimeoutMs = requestTimeoutMs;
        }
    }

    // Main class getters and setters
    public KafkaConfig getKafka() {
        return kafka;
    }

    public void setKafka(KafkaConfig kafka) {
        this.kafka = kafka;
    }

    public MinioConfig getMinio() {
        return minio;
    }

    public void setMinio(MinioConfig minio) {
        this.minio = minio;
    }

    public PinotConfig getPinot() {
        return pinot;
    }

    public void setPinot(PinotConfig pinot) {
        this.pinot = pinot;
    }

    public MonitoringSettings getMonitoring() {
        return monitoring;
    }

    public void setMonitoring(MonitoringSettings monitoring) {
        this.monitoring = monitoring;
    }

    public List<PipelineConfig> getPipelines() {
        return pipelines;
    }

    public void setPipelines(List<PipelineConfig> pipelines) {
        this.pipelines = pipelines;
    }

    /**
     * Get only enabled pipelines
     */
    public List<PipelineConfig> getEnabledPipelines() {
        return pipelines.stream()
                .filter(PipelineConfig::isEnabled)
                .toList();
    }
}
