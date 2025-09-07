kubectl -n spark create secret generic minio-s3-credentials \
  --from-literal=AWS_ACCESS_KEY_ID='minio' \
  --from-literal=AWS_SECRET_ACCESS_KEY='minio123'