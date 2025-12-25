#!/bin/bash
#
# Script to rebuild and push Kafka Connect image to Minikube registry
# Run this after Minikube restart to restore the image
#
# Usage: ./rebuild-and-push.sh

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
IMAGE_NAME="localhost:5000/kafka-connect-s3:latest"

echo "================================================"
echo "Kafka Connect Image Rebuild & Push"
echo "================================================"
echo ""

# Step 1: Point to Minikube's Docker daemon
echo "[1/4] Configuring Docker to use Minikube's daemon..."
eval $(minikube docker-env)
echo "✓ Docker configured"
echo ""

# Step 2: Build the image
echo "[2/4] Building Kafka Connect image with Aiven S3 connector..."
cd "$SCRIPT_DIR"
docker build -t "$IMAGE_NAME" .
echo "✓ Image built: $IMAGE_NAME"
echo ""

# Step 3: Push to Minikube registry
echo "[3/4] Pushing image to Minikube registry..."
docker push "$IMAGE_NAME"
echo "✓ Image pushed to registry"
echo ""

# Step 4: Check if Kafka Connect pod needs restart
echo "[4/4] Checking Kafka Connect pod status..."
POD_STATUS=$(kubectl get pod kafka-connect-cluster-connect-0 -n kafka -o jsonpath='{.status.phase}' 2>/dev/null || echo "NotFound")

if [ "$POD_STATUS" = "NotFound" ]; then
    echo "⚠ Kafka Connect pod not found. Deploy it with:"
    echo "  kubectl apply -f $SCRIPT_DIR/kafkaconnect.yaml"
elif [[ "$POD_STATUS" == *"Pull"* ]] || kubectl get pod kafka-connect-cluster-connect-0 -n kafka -o jsonpath='{.status.containerStatuses[0].state.waiting.reason}' 2>/dev/null | grep -q "ImagePullBackOff"; then
    echo "⚠ Pod is in ImagePullBackOff. Restarting..."
    kubectl delete pod kafka-connect-cluster-connect-0 -n kafka
    echo "✓ Pod restarted. Waiting for it to be ready..."
    kubectl wait --for=condition=Ready pod/kafka-connect-cluster-connect-0 -n kafka --timeout=120s 2>/dev/null || true
    echo "✓ Pod should be running now"
else
    echo "✓ Kafka Connect pod is running ($POD_STATUS)"
fi

echo ""
echo "================================================"
echo "✓ Complete! Image is ready in Minikube registry"
echo "================================================"
echo ""
echo "Verify with:"
echo "  kubectl get pods -n kafka | grep connect"
echo "  kubectl get kafkaconnector -n kafka"
