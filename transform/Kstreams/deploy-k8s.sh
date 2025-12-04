#!/bin/bash
# Deploy Kafka Streams application to Kubernetes
set -e

echo "=========================================="
echo "Deploying Kafka Streams to Kubernetes"
echo "=========================================="

# Check if kubectl is configured
if ! kubectl cluster-info &> /dev/null; then
    echo "Error: kubectl is not configured or cluster is not accessible"
    exit 1
fi

# Create namespace if it doesn't exist
echo "Ensuring 'kafka' namespace exists..."
kubectl create namespace kafka --dry-run=client -o yaml | kubectl apply -f -

# Apply ConfigMap and Deployment
echo "Applying Kubernetes manifests..."
kubectl apply -f k8s/deployment.yaml

echo ""
echo "=========================================="
echo "Deployment Complete!"
echo "=========================================="
echo ""
echo "Check deployment status:"
echo "  kubectl get pods -n kafka -l app=kstreams-flatten"
echo ""
echo "View logs:"
echo "  kubectl logs -n kafka -l app=kstreams-flatten -f"
echo ""
echo "Delete deployment:"
echo "  kubectl delete -f k8s/deployment.yaml"
