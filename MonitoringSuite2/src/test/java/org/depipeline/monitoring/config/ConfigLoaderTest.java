package org.depipeline.monitoring.config;

import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.*;

class ConfigLoaderTest {

    @Test
    void shouldLoadConfigFromClasspath() throws Exception {
        MonitoringConfig config = ConfigLoader.loadConfig();

        assertThat(config).isNotNull();
        assertThat(config.getKafka()).isNotNull();
        assertThat(config.getKafka().getBootstrapServers()).isEqualTo("192.168.49.2:32100");
        assertThat(config.getMinio()).isNotNull();
        assertThat(config.getMinio().getEndpoint()).isEqualTo("http://minio-api.192.168.49.2.nip.io");
        assertThat(config.getPinot()).isNotNull();
        assertThat(config.getPinot().getControllerUrl()).isEqualTo("http://localhost:9000/tables/");
    }

    @Test
    void shouldLoadMonitoringSettings() throws Exception {
        MonitoringConfig config = ConfigLoader.loadConfig();

        assertThat(config.getMonitoring()).isNotNull();
        assertThat(config.getMonitoring().getIntervalSeconds()).isEqualTo(30);
        assertThat(config.getMonitoring().getMaxRetries()).isEqualTo(3);
        assertThat(config.getMonitoring().getRetryBackoffMs()).isEqualTo(1000);
        assertThat(config.getMonitoring().getRequestTimeoutMs()).isEqualTo(10000);
    }

    @Test
    void shouldLoadPipelines() throws Exception {
        MonitoringConfig config = ConfigLoader.loadConfig();

        assertThat(config.getPipelines()).isNotEmpty();
        assertThat(config.getEnabledPipelines()).hasSize(1);

        PipelineConfig pipeline = config.getEnabledPipelines().get(0);
        assertThat(pipeline.getName()).isEqualTo("stock-ticks-pipeline");
        assertThat(pipeline.getSourceKafkaTopic()).isEqualTo("iex-topic-1");
        assertThat(pipeline.getSinkKafkaTopic()).isEqualTo("iex-topic-1-flattened");
        assertThat(pipeline.getPinotTable()).isEqualTo("stock_ticks_latest_1_REALTIME");
        assertThat(pipeline.isEnabled()).isTrue();
    }
}
