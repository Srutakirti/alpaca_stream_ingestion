#!/bin/bash
# Validation script for Data Stack umbrella chart

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHART_DIR="$(dirname "$SCRIPT_DIR")"

echo "========================================="
echo "Validating Alpaca Data Stack"
echo "========================================="
echo ""

# Lint the umbrella chart
echo "📋 Linting data-stack umbrella chart..."
helm lint "$CHART_DIR"
echo "✅ Lint passed"
echo ""

# Update dependencies
echo "📦 Updating chart dependencies..."
helm dependency update "$CHART_DIR"
echo "✅ Dependencies updated"
echo ""

# Validate Kafka chart
echo "🔍 Validating Kafka chart..."
cd "$CHART_DIR/../kafka" && ./scripts/validate.sh
echo "✅ Kafka chart validated"
echo ""

# Validate MinIO chart
echo "🔍 Validating MinIO chart..."
cd "$CHART_DIR/../minio" && ./scripts/validate.sh
echo "✅ MinIO chart validated"
echo ""

# Validate Pinot chart
echo "🔍 Validating Pinot chart..."
cd "$CHART_DIR/../pinot" && ./scripts/validate.sh
echo "✅ Pinot chart validated"
echo ""

# Template the umbrella chart
echo "📝 Templating data-stack chart..."
cd "$CHART_DIR"
helm template data-stack . --debug > /dev/null
echo "✅ Template rendered successfully"
echo ""

echo "========================================="
echo "✅ All validations passed!"
echo "========================================="
