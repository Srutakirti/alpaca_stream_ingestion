package org.depipeline.monitoring.config;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.dataformat.yaml.YAMLFactory;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.io.InputStream;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

/**
 * Loads monitoring configuration from YAML file with environment variable override support.
 *
 * Configuration loading priority:
 * 1. External file specified via -Dconfig.file system property
 * 2. External file at ./monitoring-config.yaml
 * 3. Classpath resource /monitoring-config.yaml
 *
 * Environment variable override format:
 * MONITORING_KAFKA_BOOTSTRAPSERVERS=localhost:9092
 * MONITORING_MINIO_ENDPOINT=http://localhost:9000
 * etc.
 */
public class ConfigLoader {

    private static final Logger logger = LoggerFactory.getLogger(ConfigLoader.class);
    private static final String DEFAULT_CONFIG_FILE = "monitoring-config.yaml";
    private static final String ENV_PREFIX = "MONITORING_";

    /**
     * Load configuration from file or classpath, then apply environment variable overrides
     */
    public static MonitoringConfig loadConfig() throws IOException {
        MonitoringConfig config = loadFromFile();
        applyEnvironmentOverrides(config);
        validateConfig(config);
        return config;
    }

    /**
     * Load configuration from file
     */
    private static MonitoringConfig loadFromFile() throws IOException {
        ObjectMapper mapper = new ObjectMapper(new YAMLFactory());

        // Try system property first
        String configPath = System.getProperty("config.file");
        if (configPath != null) {
            Path path = Paths.get(configPath);
            if (Files.exists(path)) {
                logger.info("Loading configuration from: {}", configPath);
                return mapper.readValue(path.toFile(), MonitoringConfig.class);
            } else {
                throw new IOException("Config file not found: " + configPath);
            }
        }

        // Try current directory
        Path currentDirPath = Paths.get(DEFAULT_CONFIG_FILE);
        if (Files.exists(currentDirPath)) {
            logger.info("Loading configuration from current directory: {}", DEFAULT_CONFIG_FILE);
            return mapper.readValue(currentDirPath.toFile(), MonitoringConfig.class);
        }

        // Try classpath
        InputStream is = ConfigLoader.class.getClassLoader().getResourceAsStream(DEFAULT_CONFIG_FILE);
        if (is != null) {
            logger.info("Loading configuration from classpath: {}", DEFAULT_CONFIG_FILE);
            return mapper.readValue(is, MonitoringConfig.class);
        }

        throw new IOException("Configuration file not found: " + DEFAULT_CONFIG_FILE);
    }

    /**
     * Apply environment variable overrides
     *
     * Supported overrides:
     * - MONITORING_KAFKA_BOOTSTRAPSERVERS
     * - MONITORING_MINIO_ENDPOINT
     * - MONITORING_MINIO_ACCESSKEY
     * - MONITORING_MINIO_SECRETKEY
     * - MONITORING_PINOT_CONTROLLERURL
     * - MONITORING_MONITORING_INTERVALSECONDS
     */
    private static void applyEnvironmentOverrides(MonitoringConfig config) {
        // Kafka overrides
        String kafkaBootstrap = getEnv("KAFKA_BOOTSTRAPSERVERS");
        if (kafkaBootstrap != null) {
            config.getKafka().setBootstrapServers(kafkaBootstrap);
            logger.info("Override: Kafka bootstrap servers from environment");
        }

        // MinIO overrides
        String minioEndpoint = getEnv("MINIO_ENDPOINT");
        if (minioEndpoint != null) {
            config.getMinio().setEndpoint(minioEndpoint);
            logger.info("Override: MinIO endpoint from environment");
        }

        String minioAccessKey = getEnv("MINIO_ACCESSKEY");
        if (minioAccessKey != null) {
            config.getMinio().setAccessKey(minioAccessKey);
            logger.info("Override: MinIO access key from environment");
        }

        String minioSecretKey = getEnv("MINIO_SECRETKEY");
        if (minioSecretKey != null) {
            config.getMinio().setSecretKey(minioSecretKey);
            logger.info("Override: MinIO secret key from environment");
        }

        // Pinot overrides
        String pinotUrl = getEnv("PINOT_CONTROLLERURL");
        if (pinotUrl != null) {
            config.getPinot().setControllerUrl(pinotUrl);
            logger.info("Override: Pinot controller URL from environment");
        }

        // Monitoring settings overrides
        String intervalSeconds = getEnv("MONITORING_INTERVALSECONDS");
        if (intervalSeconds != null) {
            config.getMonitoring().setIntervalSeconds(Integer.parseInt(intervalSeconds));
            logger.info("Override: Monitoring interval from environment");
        }

        String maxRetries = getEnv("MONITORING_MAXRETRIES");
        if (maxRetries != null) {
            config.getMonitoring().setMaxRetries(Integer.parseInt(maxRetries));
            logger.info("Override: Max retries from environment");
        }
    }

    /**
     * Get environment variable with prefix
     */
    private static String getEnv(String key) {
        return System.getenv(ENV_PREFIX + key);
    }

    /**
     * Validate loaded configuration
     */
    private static void validateConfig(MonitoringConfig config) {
        if (config.getKafka() == null || config.getKafka().getBootstrapServers() == null) {
            throw new IllegalStateException("Kafka bootstrap servers not configured");
        }

        if (config.getMinio() == null || config.getMinio().getEndpoint() == null) {
            throw new IllegalStateException("MinIO endpoint not configured");
        }

        if (config.getPinot() == null || config.getPinot().getControllerUrl() == null) {
            throw new IllegalStateException("Pinot controller URL not configured");
        }

        if (config.getPipelines() == null || config.getPipelines().isEmpty()) {
            throw new IllegalStateException("No pipelines configured");
        }

        logger.info("Configuration validated successfully");
        logger.info("Loaded {} pipeline(s), {} enabled",
                   config.getPipelines().size(),
                   config.getEnabledPipelines().size());
    }
}
