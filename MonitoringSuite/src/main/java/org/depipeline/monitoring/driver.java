package org.depipeline.monitoring;

import java.util.Map;

public class driver {

    String bootstrapServers = "192.168.49.2:32100";  // Change to your Kafka brokers
    String sourceTopicName = "iex-topic-1";
    String sinkTopicName = "iex-topic-1-flattened";
    String minioEndPoint = "http://minio-api.192.168.49.2.nip.io";
    String accessKey = "minio";
    String secretKey = "minio123";
    String s3Bucket = "data";
    String s3object = "chkpt1/offsets/";
    String pinotControllerUrl = "http://localhost:9000/tables/";
    String pinotTable = "stock_ticks_latest_1_REALTIME";

//    var s = new SparkOffsetMonitor("http://minio-api.192.168.49.2.nip.io","minio","minio123");
//    var j = s.sparkConsumingOffsetChecker("data","chkpt1/offsets/449");

    KafkaOffsetMonitor TopicMonitor = new KafkaOffsetMonitor(bootstrapServers);
    SparkOffsetMonitor consumingOffsetMonitor = new SparkOffsetMonitor(
            minioEndPoint,
            accessKey,
            secretKey
    );
    PinotConsumerChecker pinotOffsetMonitor = new PinotConsumerChecker(pinotControllerUrl);

    public static void main(String[] args) throws Exception {
        driver driver = new driver();
        Long oldValueSourceOffset =0L;
        Long oldValueSinkOffset = 0L;
        Long OldValueSparkOffset = 0L;
        Long OldValuePinotOffset=0L;
        while (true){
            Map<Integer, Long> sourceOffsetMap = driver.TopicMonitor.checkOffsets(driver.sourceTopicName);
            Map<Integer, Long> sinkOffsetMap = driver.TopicMonitor.checkOffsets(driver.sinkTopicName);
            Map<Integer, Long> sparkConsumingOffsetMap = driver.consumingOffsetMonitor.sparkConsumingOffsetChecker(driver.s3Bucket, driver.s3object);
            Map<Integer, Long> pinotConsumingOffsetMap = driver.pinotOffsetMonitor.pinotConsumingOffsetChecker(driver.pinotTable);

            Long latestValueSourceOffset = sourceOffsetMap.values().stream().mapToLong(Long::longValue).sum();
            Long latestValueSinkOffset = sinkOffsetMap.values().stream().mapToLong(Long::longValue).sum();
            Long latestValueSparkOffset = sparkConsumingOffsetMap.values().stream().mapToLong(Long::longValue).sum();
            Long latestValuesPinotOffset = pinotConsumingOffsetMap.values().stream().mapToLong(Long::longValue).sum();

            String toPrint = """
                    Source topic has moved %d messages.
                    Destination topic has sent %d messages.
                    Spark has processed %d messages.
                    Pinot has processed %d messages.
                    """.formatted(latestValueSourceOffset - oldValueSourceOffset,
                    latestValueSinkOffset - oldValueSinkOffset,
                    latestValueSparkOffset - OldValueSparkOffset,
                    latestValuesPinotOffset - OldValuePinotOffset);

            oldValueSourceOffset =latestValueSourceOffset;
            oldValueSinkOffset = latestValueSinkOffset;
            OldValueSparkOffset = latestValueSparkOffset;
            OldValuePinotOffset = latestValuesPinotOffset;

            System.out.println(toPrint);
            Thread.sleep(30000);

        }
    }

}
