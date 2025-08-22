import os
from google.cloud import dataproc_v1

PROJECT_ID = "coe-landing-zone-18-ats-2246"
REGION = "us-east1"
CLUSTER_NAME = "alpaca-streamer"

def start_cluster():
    """Start a stopped Dataproc cluster using ClusterControllerClient.start_cluster."""
    from google.cloud import dataproc_v1
    client = dataproc_v1.ClusterControllerClient(
        client_options={"api_endpoint": f"{REGION}-dataproc.googleapis.com:443"}
    )
    request = dataproc_v1.StartClusterRequest(
        project_id=PROJECT_ID,
        region=REGION,
        cluster_name=CLUSTER_NAME,
    )
    operation = client.start_cluster(request=request)
    print("Waiting for operation to complete...")
    response = operation.result()
    print("Cluster started:", response.cluster_name)

def stop_cluster():
    """Stop a running Dataproc cluster using ClusterControllerClient.stop_cluster."""
    from google.cloud import dataproc_v1
    client = dataproc_v1.ClusterControllerClient(
        client_options={"api_endpoint": f"{REGION}-dataproc.googleapis.com:443"}
    )
    request = dataproc_v1.StopClusterRequest(
        project_id=PROJECT_ID,
        region=REGION,
        cluster_name=CLUSTER_NAME,
    )
    operation = client.stop_cluster(request=request)
    print("Waiting for operation to complete...")
    response = operation.result()
    print("Cluster stopped:", response.cluster_name)

def submit_pyspark_job():
    """Submit a PySpark job to the Dataproc cluster using JobControllerClient.submit_job."""
    from google.cloud import dataproc_v1
    client = dataproc_v1.JobControllerClient(
        client_options={"api_endpoint": f"{REGION}-dataproc.googleapis.com:443"}
    )
    job = {
        "placement": {"cluster_name": CLUSTER_NAME},
        "pyspark_job": {
            "main_python_file_uri": "gs://alpaca-streamer/transform/spark_kafka_to_iceberg.py",
            "args": [
                "--bootstrap_servers", "instance-20250325-162745:9095",
                "--topic", "iex_raw_0",
                "--table_path", "gs://alpaca-streamer/warehouse_poc/test2/raw_stream",
                "--processing_time", "60 seconds"
            ],
            "properties": {
                "spark.jars.packages": "org.apache.spark:spark-sql-kafka-0-10_2.13:3.5.1,org.apache.iceberg:iceberg-spark-runtime-3.5_2.13:1.8.1"
            }
        }
    }
    request = dataproc_v1.SubmitJobRequest(
        project_id=PROJECT_ID,
        region=REGION,
        job=job
    )
    response = client.submit_job(request=request)
    print("Job submitted. Job ID:", response.reference.job_id)

if __name__ == "__main__":
    # Example usage:
    # start_cluster()
    stop_cluster()
    # submit_pyspark_job()
    pass
