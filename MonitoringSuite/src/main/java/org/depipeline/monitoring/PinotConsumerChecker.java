package org.depipeline.monitoring;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.util.HashMap;
import java.util.Iterator;
import java.util.Map;

public class PinotConsumerChecker {

    private final String controllerUrl;

    public PinotConsumerChecker(String controllerUrl) {
        this.controllerUrl = controllerUrl;
    }

    public  Map<Integer, Long> pinotConsumingOffsetChecker(String tableName) throws Exception {

//        String url = "http://localhost:9000/tables/stock_ticks_latest_1_REALTIME/consumingSegmentsInfo";
        String url = controllerUrl + tableName + "/consumingSegmentsInfo";

        HttpClient client = HttpClient.newHttpClient();

        var request = HttpRequest.newBuilder().uri(URI.create(url)).GET().build();

        var response = client.send(request, HttpResponse.BodyHandlers.ofString());

        if (response.statusCode() == 200) {

            ObjectMapper mapper = new ObjectMapper();
            JsonNode root = mapper.readTree(response.body());

            Map<Integer, Long> partitionOffsets = new HashMap<>();

            JsonNode segments = root.path("_segmentToConsumingInfoMap");
            Iterator<String> fieldNames = segments.fieldNames();

            while (fieldNames.hasNext()) {
                String segmentName = fieldNames.next();
                JsonNode array = segments.get(segmentName);

                if (array.isArray() && !array.isEmpty()) {
                    JsonNode partitionMap = array.get(0).path("partitionToOffsetMap");

                    Iterator<String> partitions = partitionMap.fieldNames();
                    while (partitions.hasNext()) {
                        String partition = partitions.next();
                        long offset = partitionMap.get(partition).asLong();
                        partitionOffsets.put(Integer.parseInt(partition), offset);
                    }
                }
            }

        return partitionOffsets;
        }
        else {
            throw new Exception("Status code: " + response.statusCode());
        }

    }

    public static void main(String[] args)  throws Exception {
        var pinotChecker = new PinotConsumerChecker("http://localhost:9000/tables/");
        var x = pinotChecker.pinotConsumingOffsetChecker("stock_ticks_latest_1_REALTIME");
        System.out.println(x);

    }
}
