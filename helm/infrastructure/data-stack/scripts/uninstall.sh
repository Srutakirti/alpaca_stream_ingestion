#!/bin/bash
set -e
RELEASE_NAME=${1:-data-stack}
echo "Uninstalling $RELEASE_NAME..."
helm uninstall "$RELEASE_NAME" --wait || true
kubectl delete namespace kafka --ignore-not-found=true
kubectl delete namespace minio-tenant minio-operator --ignore-not-found=true
kubectl delete namespace pinot --ignore-not-found=true
kubectl get pv | grep -E 'kafka|minio|pinot' | awk '{print $1}' | xargs -r kubectl delete pv 2>/dev/null || true
echo "✅ Complete uninstallation finished!"
