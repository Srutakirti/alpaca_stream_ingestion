#!/bin/bash
###############################################################################
# Complete Infrastructure Setup - Orchestrator Script
#
# Runs all 3 parts of the infrastructure setup in sequence:
#   1. Install dependencies
#   2. Setup Kubernetes resources
#   3. Setup applications
#
# Prerequisites:
#   - Ubuntu Linux
#   - sudo access
#   - ALPACA_KEY and ALPACA_SECRET env vars (optional - for extractor)
#
# Exit codes:
#   0 - Success
#   1 - Error occurred
#   3 - Docker group needs activation (manual intervention required)
#
# Usage:
#   # Without extractor
#   ./scripts/setup_all.sh
#
#   # With extractor
#   ALPACA_KEY=xxx ALPACA_SECRET=yyy ./scripts/setup_all.sh
###############################################################################

set -e  # Exit on error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ============================================================================
# MAIN EXECUTION
# ============================================================================

echo ""
echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}     Alpaca Stream Ingestion - Complete Infrastructure Setup${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo ""
echo "This will install and configure the complete data engineering stack:"
echo "  • Docker, Minikube, Helm, Kubectl, Java, UV"
echo "  • Kafka, Pinot, MinIO (Kubernetes)"
echo "  • KStreams processing application"
if [ -n "$ALPACA_KEY" ] && [ -n "$ALPACA_SECRET" ]; then
    echo "  • WebSocket extractor (ALPACA credentials detected)"
else
    echo "  • WebSocket extractor (SKIPPED - no ALPACA credentials)"
fi
echo ""
echo -e "${YELLOW}Note: This may require a shell restart if Docker group is added.${NC}"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Setup cancelled."
    exit 0
fi

echo ""
echo -e "${GREEN}Starting complete setup...${NC}"
echo ""

# ============================================================================
# PART 1: Install Dependencies
# ============================================================================

echo ""
echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}     Part 1/3: Installing Dependencies${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo ""

if ! "$SCRIPT_DIR/1_install_dependencies.sh"; then
    EXIT_CODE=$?

    if [ $EXIT_CODE -eq 3 ]; then
        # Docker group was added, need shell restart
        echo ""
        echo -e "${YELLOW}======================================================================${NC}"
        echo -e "${YELLOW}     Shell Restart Required${NC}"
        echo -e "${YELLOW}======================================================================${NC}"
        echo ""
        echo "Part 1 completed, but Docker group needs activation."
        echo ""
        echo "Please run ONE of these commands:"
        echo ""
        echo "  1. newgrp docker"
        echo "  2. su - $USER"
        echo "  3. logout and login"
        echo ""
        echo "Then continue with:"
        echo ""
        echo "  $SCRIPT_DIR/2_setup_kubernetes.sh"
        echo "  $SCRIPT_DIR/3_setup_apps.sh"
        echo ""
        echo "Or run this script again after activating docker group:"
        echo "  $0"
        echo ""
        exit 0
    else
        echo -e "${RED}Part 1 failed with exit code $EXIT_CODE${NC}"
        exit $EXIT_CODE
    fi
fi

echo ""
echo -e "${GREEN}✓ Part 1 completed successfully${NC}"
echo ""

# ============================================================================
# PART 2: Setup Kubernetes Resources
# ============================================================================

echo ""
echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}     Part 2/3: Setting Up Kubernetes Resources${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo ""

if ! "$SCRIPT_DIR/2_setup_kubernetes.sh"; then
    EXIT_CODE=$?
    echo -e "${RED}Part 2 failed with exit code $EXIT_CODE${NC}"
    exit $EXIT_CODE
fi

echo ""
echo -e "${GREEN}✓ Part 2 completed successfully${NC}"
echo ""

# ============================================================================
# PART 3: Setup Applications
# ============================================================================

echo ""
echo -e "${BLUE}======================================================================${NC}"
echo -e "${BLUE}     Part 3/3: Setting Up Applications${NC}"
echo -e "${BLUE}======================================================================${NC}"
echo ""

if ! "$SCRIPT_DIR/3_setup_apps.sh"; then
    EXIT_CODE=$?
    echo -e "${RED}Part 3 failed with exit code $EXIT_CODE${NC}"
    exit $EXIT_CODE
fi

echo ""
echo -e "${GREEN}✓ Part 3 completed successfully${NC}"
echo ""

# ============================================================================
# COMPLETION
# ============================================================================

echo ""
echo -e "${GREEN}======================================================================${NC}"
echo -e "${GREEN}     ✓ Complete Setup Finished Successfully!${NC}"
echo -e "${GREEN}======================================================================${NC}"
echo ""
echo "Your data engineering stack is ready!"
echo ""
echo "Access Information:"
MINIKUBE_IP=$(minikube ip 2>/dev/null || echo "192.168.49.2")
echo "  Kafka:     ${MINIKUBE_IP}:32100"
echo "  MinIO API: http://minio-api.${MINIKUBE_IP}.nip.io"
echo "  MinIO UI:  http://minio.${MINIKUBE_IP}.nip.io (user: minio, pass: minio123)"
echo "  Pinot:     kubectl port-forward -n pinot svc/pinot-pinot-chart-controller 9000:9000"
echo ""
echo "Check Deployment Status:"
echo "  kubectl get pods -n kafka"
echo "  kubectl get pods -n pinot"
echo "  kubectl get pods -n minio-tenant"
echo ""
echo "Useful Commands:"
echo "  # Query Pinot data"
echo "  uv run load/pinot_qeury_display.py"
echo ""
echo "  # Check KStreams logs"
echo "  kubectl logs -n kafka -l app=kstreams-flatten -f"
echo ""
if [ -n "$ALPACA_KEY" ]; then
    echo "  # Check extractor logs"
    echo "  kubectl logs -l app=websocket-extractor -f"
    echo ""
fi
echo "  # MinIO CLI"
echo "  mc ls s3/"
echo ""
echo "State markers: ~/.alpaca_infra_state/"
echo ""

exit 0
