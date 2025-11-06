package org.depipeline.monitoring.config;

import com.fasterxml.jackson.annotation.JsonProperty;

/**
 * Configuration for a single data pipeline to monitor.
 * Represents the flow: Kafka Source -> Spark -> Kafka Sink -> Pinot
 */
public class PipelineConfig {

    private String name;

    @JsonProperty("sourceKafkaTopic")
    private String sourceKafkaTopic;

    @JsonProperty("sinkKafkaTopic")
    private String sinkKafkaTopic;

    @JsonProperty("sparkCheckpointPath")
    private String sparkCheckpointPath;

    @JsonProperty("sparkCheckpointBucket")
    private String sparkCheckpointBucket;

    @JsonProperty("pinotTable")
    private String pinotTable;

    private boolean enabled = true;

    // Constructors
    public PipelineConfig() {
    }

    public PipelineConfig(String name, String sourceKafkaTopic, String sinkKafkaTopic,
                         String sparkCheckpointPath, String sparkCheckpointBucket,
                         String pinotTable, boolean enabled) {
        this.name = name;
        this.sourceKafkaTopic = sourceKafkaTopic;
        this.sinkKafkaTopic = sinkKafkaTopic;
        this.sparkCheckpointPath = sparkCheckpointPath;
        this.sparkCheckpointBucket = sparkCheckpointBucket;
        this.pinotTable = pinotTable;
        this.enabled = enabled;
    }

    // Getters and Setters
    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public String getSourceKafkaTopic() {
        return sourceKafkaTopic;
    }

    public void setSourceKafkaTopic(String sourceKafkaTopic) {
        this.sourceKafkaTopic = sourceKafkaTopic;
    }

    public String getSinkKafkaTopic() {
        return sinkKafkaTopic;
    }

    public void setSinkKafkaTopic(String sinkKafkaTopic) {
        this.sinkKafkaTopic = sinkKafkaTopic;
    }

    public String getSparkCheckpointPath() {
        return sparkCheckpointPath;
    }

    public void setSparkCheckpointPath(String sparkCheckpointPath) {
        this.sparkCheckpointPath = sparkCheckpointPath;
    }

    public String getSparkCheckpointBucket() {
        return sparkCheckpointBucket;
    }

    public void setSparkCheckpointBucket(String sparkCheckpointBucket) {
        this.sparkCheckpointBucket = sparkCheckpointBucket;
    }

    public String getPinotTable() {
        return pinotTable;
    }

    public void setPinotTable(String pinotTable) {
        this.pinotTable = pinotTable;
    }

    public boolean isEnabled() {
        return enabled;
    }

    public void setEnabled(boolean enabled) {
        this.enabled = enabled;
    }

    @Override
    public String toString() {
        return "PipelineConfig{" +
                "name='" + name + '\'' +
                ", sourceKafkaTopic='" + sourceKafkaTopic + '\'' +
                ", sinkKafkaTopic='" + sinkKafkaTopic + '\'' +
                ", sparkCheckpointPath='" + sparkCheckpointPath + '\'' +
                ", sparkCheckpointBucket='" + sparkCheckpointBucket + '\'' +
                ", pinotTable='" + pinotTable + '\'' +
                ", enabled=" + enabled +
                '}';
    }
}
