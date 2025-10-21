#!/bin/bash
LOG_FILE="/tmp/cron_trigger.log"
DATE=$(date '+%Y-%m-%d %H:%M:%S')
POD_DATE=$(date '+%Y%m%d')

echo "[$DATE] Starting script execution" >> "$LOG_FILE"

# Create a temporary YAML with the date-based pod name
TEMP_YAML="/tmp/extractor_deploy_${POD_DATE}.yaml"
sed "s/name: ws-scraper/name: ws-scraper-${POD_DATE}/" /home/srutakirti_mangaraj_fractal_ai/alpaca_stream_ingestion/minikube/extractor_deploy/extractor_deploy.yaml > $TEMP_YAML

# Deploy the extractor with the modified YAML
kubectl apply -f $TEMP_YAML
if [ $? -eq 0 ]; then
    echo "[$DATE] Extractor deployment successful with pod name: ws-scraper-${POD_DATE}" >> "$LOG_FILE"
else
    echo "[$DATE] Extractor deployment failed" >> "$LOG_FILE"
    exit 1
fi

# Clean up temporary YAML
rm $TEMP_YAML

# Submit Spark job in background
nohup /home/srutakirti_mangaraj_fractal_ai/spark-3.5.1/bin/spark-submit \
    --master k8s://192.168.49.2:8443 \
    --deploy-mode cluster \
    --name sp-pyspark-${POD_DATE} \
    --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1 \
    --conf spark.kubernetes.container.image=pyspark:v3.5.2.3 \
    --conf spark.kubernetes.context=minikube \
    --conf spark.kubernetes.namespace=spark \
    --conf spark.kubernetes.authenticate.driver.serviceAccountName=spark \
    --conf spark.kubernetes.driver.volumes.hostPath.data.mount.path=/mnt \
    --conf spark.kubernetes.driver.volumes.hostPath.data.options.path=/mnt \
    --conf spark.kubernetes.driver.volumes.hostPath.data.options.type=Directory \
    --conf spark.kubernetes.executor.volumes.hostPath.data.mount.path=/mnt \
    --conf spark.kubernetes.executor.volumes.hostPath.data.options.path=/mnt \
    --conf spark.kubernetes.executor.volumes.hostPath.data.options.type=Directory \
    --conf spark.ui.enabled=false \
    --conf spark.eventLog.enabled=false \
    --conf spark.jars.ivy=/tmp/.ivy2 \
    local:///mnt/shr/spark_streaming_flattener.py > /dev/null 2>&1 &

echo "[$DATE] Script completed" >> "$LOG_FILE"