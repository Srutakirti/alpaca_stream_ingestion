package org.depipeline.monitoring;


import java.io.InputStream;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.util.Iterator;
import java.util.Map;


import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

import io.minio.DownloadObjectArgs;
import io.minio.GetObjectArgs;
import io.minio.MinioClient;
import io.minio.ServerSideEncryptionCustomerKey;
import io.minio.errors.MinioException;
import java.io.IOException;
import java.security.InvalidKeyException;
import java.security.NoSuchAlgorithmException;
import java.util.Scanner;
import javax.crypto.KeyGenerator;


public class Utils {
    public static String pinotConsumingOffsetChecker(String tableName, String controllerURL) throws Exception {

//        String url = "http://localhost:9000/tables/stock_ticks_latest_1_REALTIME/consumingSegmentsInfo";
        String url = controllerURL + tableName + "/consumingSegmentsInfo";

        HttpClient client = HttpClient.newHttpClient();

        var request = HttpRequest.newBuilder().uri(URI.create(url)).GET().build();

        var response = client.send(request, HttpResponse.BodyHandlers.ofString());

        if (response.statusCode() == 200) {

            System.out.println(response.body());

            ObjectMapper mapper = new ObjectMapper();
            JsonNode root = mapper.readTree(response.body());
            ObjectNode combinedNode = mapper.createObjectNode();

            JsonNode segmentMap = root.get("_segmentToConsumingInfoMap");
            if (segmentMap != null) {
                Iterator<Map.Entry<String, JsonNode>> fields = segmentMap.fields();
                while (fields.hasNext()) {
                    Map.Entry<String, JsonNode> entry = fields.next();
                    String segmentName = entry.getKey();
                    JsonNode serversArray = entry.getValue();

                    // Usually array of one element (server info)
                    for (JsonNode serverInfo : serversArray) {
                        JsonNode partitionToOffsetMap = serverInfo.get("partitionToOffsetMap");
                        if (partitionToOffsetMap != null) {
//                            var offsetMap = partitionToOffsetMap.fields();
//                            var elem = offsetMap.next();
//                            var key = elem.getKey();
//                            var value = elem.getValue();
                            String jsonString = mapper.writeValueAsString(partitionToOffsetMap);
                            combinedNode.setAll((ObjectNode) partitionToOffsetMap);

                            System.out.println(jsonString);
                        }
                    }
                    return combinedNode.toString();
                }

            }
            }
        else {
            throw new Exception("Status code: " + response.statusCode());
        }
        return "None";
    }
    public static String sparkConsumingOffsetChecker(String s3Bucket, String s3Prefix) throws Exception {

        try (MinioClient minioClient = MinioClient.builder()
                .endpoint("http://minio-api.192.168.49.2.nip.io")
                .credentials("minio", "minio123")
                .build()) {

            InputStream stream = minioClient.getObject(
                    GetObjectArgs.builder().bucket(s3Bucket).object(s3Prefix).build());
            {

                return new String(stream.readAllBytes(), StandardCharsets.UTF_8);

            }
        }


    }

    public static void parseSparkChkptText(String sparkChkptText) throws Exception {
        ObjectMapper mapper = new ObjectMapper();
        String[] lines = sparkChkptText.split("\n");
            //picks the last json line as it has the offset json
            String line = lines[lines.length - 1];
            //this json node has topic name and then the partionwise offset
            JsonNode jsonNode = mapper.readTree(line);
            System.out.println("Parsed JSON " +  jsonNode.toPrettyString());


    }

    public static void main(String[] args) throws Exception {
        parseSparkChkptText(sparkConsumingOffsetChecker("data","chkpt1/offsets/449"));
        return;
    }
}
