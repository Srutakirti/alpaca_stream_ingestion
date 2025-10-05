package org.depipeline.monitoring;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import io.minio.GetObjectArgs;
import io.minio.ListObjectsArgs;
import io.minio.MinioClient;
import io.minio.messages.Item;

import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.Comparator;
import java.util.Map;
import java.util.stream.StreamSupport;

public class SparkOffsetMonitor {
    private String minioEndpoint;
    private String accessKey;
    private String secretKey;

    public SparkOffsetMonitor(String minioEndpoint,String accessKey,String secretKey) {

        this.minioEndpoint = minioEndpoint;
        this.accessKey = accessKey;
        this.secretKey = secretKey;

    }

    public  Map<Integer, Long> sparkConsumingOffsetChecker(String s3Bucket, String s3Prefix) throws Exception {

        try (MinioClient minioClient = MinioClient.builder()
                .endpoint(minioEndpoint)
                .credentials(accessKey, secretKey)
                .build()) {

            var latestObject= getLatestObject(minioClient,s3Bucket,s3Prefix);
            InputStream stream = minioClient.getObject(
                    GetObjectArgs.builder().bucket(s3Bucket).object(latestObject).build());
            {

                //                System.out.println(x.getClass());
                return parseSparkChkptText(new String(stream.readAllBytes(), StandardCharsets.UTF_8));

            }
        }
    }

    public String getLatestObject(MinioClient mc, String s3Bucket, String s3Prefix ) throws Exception {
        var results =  mc.listObjects(ListObjectsArgs.builder()
                        .bucket(s3Bucket).prefix(s3Prefix).recursive(false)
                        .build());
        var latest = StreamSupport.stream(results.spliterator(), false).map(r ->
                {
                    try {
                        return r.get();
                    } catch (Exception e) {
                        throw  new RuntimeException(e);
                    }
                }
                ).max(Comparator.comparing(Item::lastModified));

        return latest.map(Item::objectName).orElse(null);

    }



    public  Map<Integer,Long> parseSparkChkptText(String sparkChkptText) throws Exception {
        ObjectMapper mapper = new ObjectMapper();
        String[] lines = sparkChkptText.split("\n");
        //picks the last json line as it has the offset json
        String line = lines[lines.length - 1];
        //this json node has topic name and then the partionwise offset
        JsonNode jsonNode = mapper.readTree(line);
        return mapper.convertValue(
                jsonNode.get("iex-topic-1"),
                new TypeReference<>() {
                }
        );

    }

    public static void main(String[] args) throws   Exception {
        var s = new SparkOffsetMonitor("http://minio-api.192.168.49.2.nip.io","minio","minio123");
        var j = s.sparkConsumingOffsetChecker("data","chkpt1/offsets/");
        System.out.println("Class: " + j);
        System.out.println("Canonical: " + j.getClass().getCanonicalName());
        System.out.println("Simple: " + j.getClass().getSimpleName());

    }
}
