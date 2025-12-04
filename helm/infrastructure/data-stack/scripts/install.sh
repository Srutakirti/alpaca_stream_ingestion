#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHART_DIR="$(dirname "$SCRIPT_DIR")"

echo "========================================="
echo "Installing Alpaca Data Stack"
echo "========================================="
echo ""

# Create storage directory for MinIO
echo "📁 Creating MinIO storage directory..."
minikube ssh "sudo mkdir -p /mnt/minio && sudo chmod 777 /mnt/minio"
echo ""

# Install Kafka
echo "🔄 Installing Kafka..."
cd "$CHART_DIR/../kafka"
helm install kafka . --namespace kafka --create-namespace --wait --timeout 5m
echo "✅ Kafka installed"
echo ""

# Install MinIO
echo "🔄 Installing MinIO..."
cd "$CHART_DIR/../minio"
helm install minio-infra . --namespace minio-tenant --create-namespace --wait --timeout 5m
echo "✅ MinIO installed"
echo ""

# Install Pinot
echo "🔄 Installing Pinot..."
cd "$CHART_DIR/../pinot"
helm install pinot . --namespace pinot --create-namespace --wait --timeout 5m
echo "✅ Pinot installed"
echo ""

echo "========================================="
echo "✅ Data Stack Installation Complete!"
echo "========================================="
echo ""
echo "📊 Check status:"
echo "  kubectl get pods --all-namespaces | grep -E 'kafka|minio|pinot'"
echo ""
echo "📚 For more info: helm status <release-name> -n <namespace>"
