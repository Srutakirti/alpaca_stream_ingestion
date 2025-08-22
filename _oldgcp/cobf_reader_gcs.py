import os
import yaml
from typing import Any
from google.cloud import storage
from io import StringIO

class Config:
    def __init__(self, config_path: str):
        self.config = self._load_config(config_path)
        self._override_from_env()

    def _load_config(self, config_path: str):
        if config_path.startswith("gs://"):
            return self._load_from_gcs(config_path)
        else:
            with open(config_path, "r") as f:
                return yaml.safe_load(f)

    def _load_from_gcs(self, gcs_path: str):
        # Extract bucket and blob
        path_parts = gcs_path.replace("gs://", "").split("/", 1)
        bucket_name, blob_name = path_parts[0], path_parts[1]

        # Create a GCS client and download the blob as text
        client = storage.Client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(blob_name)
        content = blob.download_as_text()
        return yaml.safe_load(StringIO(content))

    def _override_from_env(self):
        if os.getenv("KAFKA_BOOTSTRAP_SERVERS"):
            self.config["kafka"]["bootstrap_servers"] = os.getenv("KAFKA_BOOTSTRAP_SERVERS")
        if os.getenv("ALPACA_KEY"):
            self.config["alpaca"]["key"] = os.getenv("ALPACA_KEY")
        if os.getenv("ALPACA_SECRET"):
            self.config["alpaca"]["secret"] = os.getenv("ALPACA_SECRET")

    def get(self, path: str, default: Any = None) -> Any:
        try:
            value = self.config
            for key in path.split('.'):
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
