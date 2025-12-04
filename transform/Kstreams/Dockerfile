# Multi-stage Dockerfile for Kafka Streams Application
# Stage 1: Build the application
FROM gradle:8.5-jdk17 AS builder

WORKDIR /app

# Copy Gradle files first (for better caching)
COPY build.gradle settings.gradle gradlew ./
COPY gradle ./gradle

# Download dependencies (cached layer)
RUN ./gradlew dependencies --no-daemon

# Copy source code
COPY src ./src

# Build the fat JAR
RUN ./gradlew shadowJar --no-daemon

# Stage 2: Runtime image
FROM eclipse-temurin:17-jre-alpine

# Add metadata
LABEL maintainer="your-email@example.com"
LABEL description="Kafka Streams JSON Flattener Application"
LABEL version="1.0.0"

# Create non-root user for security
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

WORKDIR /app

# Copy the fat JAR from builder stage
# Shadow plugin creates: {baseName}-{version}-{classifier}.jar
COPY --from=builder /app/build/libs/kstreams-test-1.0.0-all.jar ./app.jar

# Change ownership to non-root user
RUN chown -R appuser:appgroup /app

# Switch to non-root user
USER appuser

# Expose any ports if needed (for metrics, health checks, etc.)
# EXPOSE 8080

# Set entrypoint
ENTRYPOINT ["java", "-jar", "app.jar"]

# Default command (can be overridden)
CMD ["--help"]
