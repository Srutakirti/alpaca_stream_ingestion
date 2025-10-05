package org.depipeline.monitoring;

import org.apache.kafka.clients.admin.AdminClient;
import org.apache.kafka.clients.admin.AdminClientConfig;
import org.apache.kafka.clients.admin.ListOffsetsResult;
import org.apache.kafka.clients.admin.OffsetSpec;
import org.apache.kafka.clients.consumer.KafkaConsumer;
import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.common.TopicPartition;
import org.apache.kafka.common.serialization.StringDeserializer;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;

public class KafkaOffsetMonitor {

    private final AdminClient adminClient;
    private final KafkaConsumer<String, String> consumer;
    private final DateTimeFormatter formatter = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

    public KafkaOffsetMonitor(String bootstrapServers) {

        // Configure Admin Client
        Properties adminProps = new Properties();
        adminProps.put(AdminClientConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);
        this.adminClient = AdminClient.create(adminProps);

        // Configure Consumer (used to get partition info)
        Properties consumerProps = new Properties();
        consumerProps.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);
        consumerProps.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName());
        consumerProps.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName());
        consumerProps.put(ConsumerConfig.GROUP_ID_CONFIG, "offset-monitor-" + UUID.randomUUID().toString());
        consumerProps.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "earliest");
        this.consumer = new KafkaConsumer<>(consumerProps);

    }



    public  Map<Integer,Long>  checkOffsets(String topicName) {
        try {
            // Get partition information for the topic
            List<org.apache.kafka.common.PartitionInfo> partitions = consumer.partitionsFor(topicName);

            if (partitions == null || partitions.isEmpty()) {
                System.out.println("[" + LocalDateTime.now().format(formatter) + "] Topic '" + topicName + "' not found or has no partitions");
                return null;
            }

            // Create TopicPartition objects
            //partitionInfo is more about discovery while the topicPartition is used for querying the Admin api.
            Map<TopicPartition, OffsetSpec> offsetSpecs = new HashMap<>();
            for (org.apache.kafka.common.PartitionInfo partition : partitions) {
                /*
                * topic partition object is used to query along with offsetSpec
                * the offset spec map is used to query the api
                * */
                TopicPartition tp = new TopicPartition(partition.topic(), partition.partition());
                offsetSpecs.put(tp, OffsetSpec.latest());
            }

            // Get latest offsets using admin client
            ListOffsetsResult offsetsResult = adminClient.listOffsets(offsetSpecs);

            Map<Integer,Long>  partitionOffsets = new HashMap<>();
            //looping through the keys of the query hashmap ake the
            for (TopicPartition tp : offsetSpecs.keySet()) {
                try {
                    long latestOffset = offsetsResult.partitionResult(tp).get().offset();
                    partitionOffsets.put(tp.partition(), latestOffset);
                } catch (Exception e) {
                    System.out.printf("Partition %d: Error getting offset - %s%n", tp.partition(), e.getMessage());
                }
            }

            return partitionOffsets;

        } catch (Exception e) {
            System.err.println("[" + LocalDateTime.now().format(formatter) + "] Error checking offsets: " + e.getMessage());
            e.printStackTrace();
        }
        return null;
    }



    public static void main(String[] args) {
        // Configuration - modify these values as needed
        String bootstrapServers = "192.168.49.2:32100";  // Change to your Kafka brokers
        String topicName = "iex-topic-1";        // Change to your topic name

        KafkaOffsetMonitor monitor = new KafkaOffsetMonitor(bootstrapServers);
        var out = monitor.checkOffsets(topicName);


        System.out.println(out);

    }

}