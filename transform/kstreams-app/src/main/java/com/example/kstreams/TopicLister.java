package com.example.kstreams;

import org.apache.kafka.clients.admin.AdminClient;
import org.apache.kafka.clients.admin.AdminClientConfig;
import org.apache.kafka.clients.admin.ListTopicsResult;

import java.util.Properties;
import java.util.Set;

public class TopicLister {
    public static void main(String[] args) {
        String bootstrapServers = "192.168.49.2:32100";

        Properties config = new Properties();
        config.put(AdminClientConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);
        config.put(AdminClientConfig.REQUEST_TIMEOUT_MS_CONFIG, "5000");
        config.put(AdminClientConfig.DEFAULT_API_TIMEOUT_MS_CONFIG, "5000");

        try (AdminClient adminClient = AdminClient.create(config)) {
            System.out.println("Connecting to Kafka at: " + bootstrapServers);
            System.out.println("Fetching topics...\n");

            ListTopicsResult topics = adminClient.listTopics();
            Set<String> topicNames = topics.names().get();

            if (topicNames.isEmpty()) {
                System.out.println("No topics found.");
            } else {
                System.out.println("Found " + topicNames.size() + " topic(s):");
                System.out.println("================================");
                topicNames.stream().sorted().forEach(topic ->
                    System.out.println("  - " + topic)
                );
            }
        } catch (Exception e) {
            System.err.println("Error connecting to Kafka: " + e.getMessage());
            e.printStackTrace();
        }
    }
}
