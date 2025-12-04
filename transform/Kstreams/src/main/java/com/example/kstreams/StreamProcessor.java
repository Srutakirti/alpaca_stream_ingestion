package com.example.kstreams;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.kafka.common.serialization.Serdes;
import org.apache.kafka.streams.KafkaStreams;
import org.apache.kafka.streams.StreamsBuilder;
import org.apache.kafka.streams.StreamsConfig;
import org.apache.kafka.streams.kstream.KStream;
import org.apache.kafka.streams.kstream.Produced;
import picocli.CommandLine;
import picocli.CommandLine.Command;
import picocli.CommandLine.Option;

import java.util.Arrays;
import java.util.Collections;
import java.util.Properties;
import java.util.concurrent.Callable;
import java.util.concurrent.CountDownLatch;

@Command(
    name = "StreamProcessor",
    description = "Kafka Streams application that flattens JSON arrays",
    mixinStandardHelpOptions = true,
    version = "1.0.0"
)
public class StreamProcessor implements Callable<Integer> {

    @Option(
        names = {"-b", "--broker"},
        description = "Kafka broker address (e.g., 192.168.49.2:32100)",
        required = true
    )
    private String broker;

    @Option(
        names = {"-i", "--input-topic"},
        description = "Input topic name",
        required = true
    )
    private String inputTopic;

    @Option(
        names = {"-o", "--output-topic"},
        description = "Output topic name",
        required = true
    )
    private String outputTopic;

    @Option(
        names = {"-a", "--app-name"},
        description = "Application name/ID for Kafka Streams (default: ${DEFAULT-VALUE})",
        defaultValue = "kstreams-flatten-app"
    )
    private String appName;

    public static void main(String[] args) {
        int exitCode = new CommandLine(new StreamProcessor()).execute(args);
        System.exit(exitCode);
    }

    @Override
    public Integer call() {
        System.out.println("Starting Kafka Streams Application");
        System.out.println("Application Name: " + appName);
        System.out.println("Broker: " + broker);
        System.out.println("Input Topic: " + inputTopic);
        System.out.println("Output Topic: " + outputTopic);
        System.out.println("-----------------------------------");

        // 1. Configure Properties
        Properties props = new Properties();
        props.put(StreamsConfig.APPLICATION_ID_CONFIG, appName);
        props.put(StreamsConfig.BOOTSTRAP_SERVERS_CONFIG, broker);
        props.put(StreamsConfig.DEFAULT_KEY_SERDE_CLASS_CONFIG, Serdes.StringSerde.class);
        props.put(StreamsConfig.DEFAULT_VALUE_SERDE_CLASS_CONFIG, Serdes.StringSerde.class);

        // 2. Create ObjectMapper for JSON parsing
        ObjectMapper objectMapper = new ObjectMapper();

        // 3. Create StreamsBuilder
        StreamsBuilder builder = new StreamsBuilder();

        // 4. Read from source topic
        KStream<String, String> sourceStream = builder.stream(inputTopic);

        // 5. Flatten: Parse JSON array and emit each element as separate message
        KStream<String, StockData> flattenedStream = sourceStream.flatMapValues(jsonArrayString -> {
            try {
                // Parse JSON array string into StockData array
                StockData[] stockDataArray = objectMapper.readValue(jsonArrayString, StockData[].class);

                // Convert array to list for flatMap
                return Arrays.asList(stockDataArray);
            } catch (Exception e) {
                System.err.println("Error parsing JSON: " + e.getMessage());
                return Collections.emptyList();
            }
        });

        // 6. Print flattened records to stdout for debugging
        flattenedStream.foreach((key, stockData) ->
            System.out.println("Flattened - Key: " + key + ", StockData: " + stockData)
        );

        // 7. Write flattened data to output topic as JSON
        flattenedStream.to(outputTopic,
            Produced.with(Serdes.String(), new JsonSerde<>(StockData.class))
        );

        // 8. Build topology and create KafkaStreams instance
        KafkaStreams streams = new KafkaStreams(builder.build(), props);

        // 9. Create latch to keep application running
        final CountDownLatch latch = new CountDownLatch(1);

        // 10. Add shutdown hook for graceful shutdown
        Runtime.getRuntime().addShutdownHook(new Thread(() -> {
            System.out.println("\nShutting down gracefully...");
            streams.close();
            latch.countDown();
        }));

        // 11. Start the streams application
        streams.start();
        System.out.println("Kafka Streams application started. Press Ctrl+C to stop.");

        // 12. Keep application running until shutdown
        try {
            latch.await();
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }

        return 0;
    }
}
