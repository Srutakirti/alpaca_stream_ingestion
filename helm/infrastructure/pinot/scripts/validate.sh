#!/bin/bash
# Validation script for Pinot Helm chart

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CHART_DIR="$(dirname "$SCRIPT_DIR")"

echo "Validating Pinot Helm chart..."

# Lint the chart
echo "Running helm lint..."
helm lint "$CHART_DIR"

# Update dependencies
echo "Updating chart dependencies..."
helm dependency update "$CHART_DIR"

# Template the chart
echo "Templating chart..."
helm template pinot-test "$CHART_DIR" \
  --namespace pinot \
  --debug > /dev/null

echo "Validation successful!"
