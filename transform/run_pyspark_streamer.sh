    # .config("spark.hadoop.fs.s3a.endpoint", MINIO_ENDPOINT)
    # .config("spark.hadoop.fs.s3a.access.key", MINIO_ACCESS_KEY)
    # .config("spark.hadoop.fs.s3a.secret.key", MINIO_SECRET_KEY)
    # .config("spark.hadoop.fs.s3a.path.style.access", "true")
    # .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem")
    # .config("spark.hadoop.fs.s3a.connection.ssl.enabled", "false")
    # .config("spark.hadoop.fs.s3a.aws.credentials.provider", "org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider")
#!/bin/bash
spark-submit \
  --master k8s://192.168.49.2:8443 \
  --deploy-mode cluster \
  --name sp-pyspark \
  --jars local:///shr/dep_jars/jars/aws-java-sdk-bundle-1.12.262.jar,local:///shr/dep_jars/jars/hadoop-aws-3.3.4.jar,local:///shr/dep_jars/jars/spark-sql-kafka-0-10_2.12-3.5.1.jar,local:///shr/dep_jars/jars/kafka-clients-3.4.0.jar,local:///shr/dep_jars/jars/spark-token-provider-kafka-0-10_2.12-3.5.1.jar,local:///shr/dep_jars/jars/commons-pool2-2.11.1.jar \
  --conf spark.kubernetes.container.image=pyspark:v3.5.2.3 \
  --conf spark.kubernetes.context=minikube \
  --conf spark.kubernetes.namespace=spark \
  --conf spark.kubernetes.authenticate.driver.serviceAccountName=spark \
  --conf spark.kubernetes.driver.volumes.hostPath.data.mount.path=/shr \
  --conf spark.kubernetes.driver.volumes.hostPath.data.options.path=/shr\
  --conf spark.kubernetes.driver.volumes.hostPath.data.options.type=Directory \
  --conf spark.kubernetes.executor.volumes.hostPath.data.mount.path=/shr \
  --conf spark.kubernetes.executor.volumes.hostPath.data.options.path=/shr \
  --conf spark.kubernetes.executor.volumes.hostPath.data.options.type=Directory \
  --conf spark.ui.enabled=false \
  --conf spark.eventLog.enabled=true \
  --conf spark.jars.ivy=/tmp/.ivy2 \
  --conf spark.hadoop.fs.s3a.endpoint=minio-api.192.168.49.2.nip.io \
  --conf spark.hadoop.fs.s3a.access.key=minio \
    --conf spark.hadoop.fs.s3a.secret.key=minio123 \
    --conf spark.hadoop.fs.s3a.path.style.access=true \
    --conf spark.hadoop.fs.s3a.impl=org.apache.hadoop.fs.s3a.S3AFileSystem \
    --conf spark.hadoop.fs.s3a.connection.ssl.enabled=false \
    --conf spark.hadoop.fs.s3a.aws.credentials.provider=org.apache.hadoop.fs.s3a.SimpleAWSCredentialsProvider \
  --conf spark.eventLog.dir=s3a://spark-logs/events \
  local:///shr/python/spark_streaming_flattener.py