# Kafka Streams JSON Flattener

A Kafka Streams application that reads JSON arrays from a source topic, flattens them into individual records, and writes them to an output topic.

## Overview

This application processes stock market data in JSON array format, flattening each array element into separate Kafka messages. It's built using Kafka Streams with modern Java patterns and picocli for command-line argument parsing.

## Architecture

### Data Flow

```
Input Topic                    Kafka Streams App                    Output Topic
-----------                    -----------------                    ------------
JSON Array          ──>        Parse & Flatten         ──>         Individual JSON
[{...}, {...}]                 + Transform                         {...}
                                                                   {...}
```

### Example Transformation

**Input Message:**
```json
[
  {"T": "T", "S": "NVDA", "o": 187.87, "h": 185.67, "l": 184.94, "c": 185.47, "v": 44481045, "t": "2025-11-13T00:35:21.076148Z", "n": 145488, "vw": 185.36},
  {"T": "T", "S": "AAPL", "o": 150.0, "h": 152.0, "l": 149.5, "c": 151.0, "v": 30000000, "t": "2025-11-13T00:35:21.076148Z", "n": 100000, "vw": 150.5}
]
```

**Output Messages:**
```json
{"T": "T", "S": "NVDA", "o": 187.87, "h": 185.67, "l": 184.94, "c": 185.47, "v": 44481045, "t": "2025-11-13T00:35:21.076148Z", "n": 145488, "vw": 185.36}
```
```json
{"T": "T", "S": "AAPL", "o": 150.0, "h": 152.0, "l": 149.5, "c": 151.0, "v": 30000000, "t": "2025-11-13T00:35:21.076148Z", "n": 100000, "vw": 150.5}
```

## Project Structure

```
src/main/java/com/example/kstreams/
├── StreamProcessor.java       # Main application with CLI handling
├── StockData.java            # POJO for stock market data
├── JsonSerializer.java       # Custom JSON serializer for Kafka
├── JsonDeserializer.java     # Custom JSON deserializer for Kafka
├── JsonSerde.java            # Combines serializer and deserializer
└── TopicLister.java          # Utility to list Kafka topics
```

## Key Components

### 1. StreamProcessor (`StreamProcessor.java`)
Main application class that:
- Parses CLI arguments using picocli
- Configures Kafka Streams
- Reads from source topic
- Flattens JSON arrays using `flatMapValues()`
- Writes individual records to output topic

**Key Methods:**
- `main()` - Entry point, delegates to picocli
- `call()` - Main processing logic (lines 54-111)
- Flattening logic at lines 78-89

### 2. StockData (`StockData.java`)
POJO representing stock market data with fields:
- `T` - Type
- `S` - Symbol (e.g., "NVDA", "AAPL")
- `o` - Open price
- `h` - High price
- `l` - Low price
- `c` - Close price
- `v` - Volume
- `t` - Timestamp
- `n` - Number of trades
- `vw` - Volume weighted average price

### 3. Custom Serdes (`JsonSerializer.java`, `JsonDeserializer.java`, `JsonSerde.java`)
Jackson-based serialization/deserialization for Kafka Streams:
- Type-safe JSON handling
- Error handling with SerializationException
- Reusable across different data types

## Dependencies

| Library | Version | Purpose |
|---------|---------|---------|
| kafka-streams | 3.6.1 | Core streaming functionality |
| jackson-databind | 2.16.0 | JSON processing |
| picocli | 4.7.5 | CLI argument parsing |
| slf4j-simple | 2.0.9 | Logging |

## Usage

### Basic Usage

```bash
./gradlew run --args="--broker 192.168.49.2:32100 --input-topic stream_test --output-topic stream_test_flattened"
```

### With Short Flags

```bash
./gradlew run --args="-b 192.168.49.2:32100 -i stream_test -o stream_test_flattened"
```

### CLI Options

| Flag | Short | Description | Required |
|------|-------|-------------|----------|
| `--broker` | `-b` | Kafka broker address | Yes |
| `--input-topic` | `-i` | Source topic name | Yes |
| `--output-topic` | `-o` | Destination topic name | Yes |
| `--help` | `-h` | Show help message | No |
| `--version` | `-V` | Show version | No |

### Help

```bash
./gradlew run --args="--help"
```

Output:
```
Usage: StreamProcessor [-hV] -b=<broker> -i=<inputTopic> -o=<outputTopic>
Kafka Streams application that flattens JSON arrays
  -b, --broker=<broker>          Kafka broker address (e.g., 192.168.49.2:32100)
  -h, --help                     Show this help message and exit.
  -i, --input-topic=<inputTopic> Input topic name
  -o, --output-topic=<outputTopic>
                                 Output topic name
  -V, --version                  Print version information and exit.
```

## Building

### Compile

```bash
./gradlew build
```

### Run Tests

```bash
./gradlew test
```

### Create JAR

```bash
./gradlew jar
```

Output: `build/libs/kstreams-test-1.0.0.jar`

## How It Works

### 1. Initialization
- Parses CLI arguments (broker, input topic, output topic)
- Configures Kafka Streams properties
- Creates ObjectMapper for JSON processing

### 2. Stream Processing Pipeline

```java
sourceStream.stream(inputTopic)           // Read from Kafka
    .flatMapValues(json -> {              // Flatten array
        StockData[] array = parse(json);
        return Arrays.asList(array);
    })
    .foreach(print)                       // Debug output
    .to(outputTopic, jsonSerde)           // Write to Kafka
```

### 3. Key Operations

**flatMapValues()** - The core flattening operation:
- Takes a JSON array string as input
- Parses it into `StockData[]` using Jackson
- Returns a `List<StockData>` which emits each element as a separate message
- Handles errors gracefully (returns empty list on parse failure)

### 4. Error Handling
- JSON parse errors are caught and logged
- Invalid messages don't crash the application
- Empty lists returned for unparseable messages

### 5. Shutdown
- Graceful shutdown hook added
- Streams closed properly on SIGTERM/SIGINT

## Configuration

### Kafka Streams Properties

Located in `StreamProcessor.java:62-66`:

```java
props.put(StreamsConfig.APPLICATION_ID_CONFIG, "kstreams-flatten-app");
props.put(StreamsConfig.BOOTSTRAP_SERVERS_CONFIG, broker);
props.put(StreamsConfig.DEFAULT_KEY_SERDE_CLASS_CONFIG, Serdes.StringSerde.class);
props.put(StreamsConfig.DEFAULT_VALUE_SERDE_CLASS_CONFIG, Serdes.StringSerde.class);
```

### Customization

To modify application behavior:
1. **Change application ID**: Line 63 (affects consumer group)
2. **Adjust serdes**: Lines 65-66 (for different key/value types)
3. **Add processing logic**: Between lines 77-95

## Troubleshooting

### Common Issues

**Issue**: "Unknown class: StreamsConfig"
- **Solution**: Ensure all imports are correct and dependencies are downloaded

**Issue**: Connection refused to Kafka
- **Solution**: Verify broker address and port are correct
- Check Kafka is running: `kubectl get pods -n kafka`

**Issue**: No messages appearing in output topic
- **Solution**: Check input topic has data
- Verify JSON format matches expected schema
- Check application logs for parsing errors

### Debugging

Enable debug output by checking console for:
```
Flattened - Key: null, StockData: StockData{T='T', S='NVDA', ...}
```

### Verifying Topics

List available topics:
```bash
kubectl exec -n kafka my-cluster-dual-role-0 -- /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list
```

## Development

### Adding New Fields

1. Update `StockData.java` with new field:
```java
@JsonProperty("newField")
private String newField;
```

2. Add getter/setter
3. Update `toString()` method
4. Rebuild and test

### Changing Processing Logic

Edit the `flatMapValues()` lambda at `StreamProcessor.java:78-89`:
```java
.flatMapValues(jsonArrayString -> {
    // Your custom logic here
})
```

## Performance Considerations

- **Throughput**: Handles thousands of messages/second
- **Memory**: Depends on JSON array size (each array loaded into memory)
- **Parallelism**: Controlled by number of input topic partitions
- **State**: Stateless application (no state stores)

## License

This project is for educational purposes.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request
