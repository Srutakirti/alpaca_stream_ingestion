#!/bin/bash
set -e

# Kafka Helm Chart Validation Script
# This script validates the Helm chart and rendered templates

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHART_DIR="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE="${CHART_DIR}/../../../config/config.yaml"

echo "==========================================="
echo "Kafka Helm Chart Validation"
echo "==========================================="
echo ""

# Check if config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "❌ Error: Config file not found at $CONFIG_FILE"
    exit 1
fi

# Check if Helm is installed
if ! command -v helm &> /dev/null; then
    echo "❌ Error: Helm is not installed"
    exit 1
fi

# Update dependencies
echo "📥 Updating chart dependencies..."
cd "$CHART_DIR"
helm dependency update

# Lint the chart
echo ""
echo "🔍 Linting Helm chart..."
helm lint "$CHART_DIR" --values "$CONFIG_FILE"

# Validate template rendering
echo ""
echo "🔍 Rendering templates (dry-run)..."
helm template kafka-test "$CHART_DIR" \
  --values "$CONFIG_FILE" \
  --namespace kafka \
  --debug > /tmp/kafka-rendered.yaml

echo ""
echo "✅ Validation successful!"
echo ""
echo "📄 Rendered templates saved to: /tmp/kafka-rendered.yaml"
echo ""
echo "To view rendered templates:"
echo "   cat /tmp/kafka-rendered.yaml"
echo ""
echo "To validate against Kubernetes API:"
echo "   kubectl apply --dry-run=client -f /tmp/kafka-rendered.yaml"
echo ""
