kubectl create ns kafka
##deploy controller
kubectl apply -f /home/kumararpita/alpaca_stream_ingestion/minikube/kafka/stimzi_downloaded.yaml
##ddeploy kafka cluster
kubectl apply -f /home/kumararpita/alpaca_stream_ingestion/minikube/kafka/kafka_deploy.yaml -n kafka
