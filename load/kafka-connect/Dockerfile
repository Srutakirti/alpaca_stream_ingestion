# Start from Strimzi Kafka base image
FROM quay.io/strimzi/kafka:0.47.0-kafka-3.9.0

USER root:root

# Download and install Aiven S3 Sink Connector v3.4.1 (Open Source, Apache License)
RUN mkdir -p /opt/kafka/plugins/aiven-s3-sink \
    && cd /opt/kafka/plugins/aiven-s3-sink \
    && curl -fL -o connector.tar https://github.com/Aiven-Open/cloud-storage-connectors-for-apache-kafka/releases/download/v3.4.1/s3-sink-connector-for-apache-kafka-3.4.1.tar \
    && tar -xf connector.tar --strip-components=1 \
    && rm connector.tar \
    && find . -type l -delete

# Switch back to kafka user
USER 1001
