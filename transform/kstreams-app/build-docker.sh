#!/bin/bash
# Build Docker image for Minikube
# This script builds the Docker image directly in Minikube's Docker environment

set -e  # Exit on error

echo "=========================================="
echo "Building Kafka Streams Docker Image"
echo "=========================================="

# Check if Minikube is running
if ! minikube status | grep -q "Running"; then
    echo "Error: Minikube is not running. Please start it with 'minikube start'"
    exit 1
fi

# Set Docker environment to Minikube
echo "Setting Docker environment to Minikube..."
eval $(minikube docker-env)

# Build the Docker image
echo "Building Docker image..."
docker build -t kstreams-flatten:1.0.0 -t kstreams-flatten:latest .

echo ""
echo "=========================================="
echo "Build Complete!"
echo "=========================================="
echo "Image: kstreams-flatten:1.0.0"
echo ""
echo "To verify the image:"
echo "  eval \$(minikube docker-env)"
echo "  docker images | grep kstreams-flatten"
echo ""
echo "To deploy to Kubernetes:"
echo "  kubectl apply -f k8s/deployment.yaml"
