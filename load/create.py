import requests
import json
import os

# --- Parameters ---
controller_url = "http://localhost:9000"   # Pinot Controller URL
schema_file = "/home/kumararpita/alpaca_stream_ingestion/load/table.json"              # Path to schema JSON file
# ------------------

def post_schema(controller_url: str, schema_file: str):
    if not os.path.isfile(schema_file):
        raise FileNotFoundError(f"Schema file not found: {schema_file}")

    with open(schema_file, "r") as f:
        schema_data = json.load(f)

    url = f"{controller_url}/tables" ##use schemas or tables based on need
    headers = {"Content-Type": "application/json"}

    response = requests.post(url, headers=headers, json=schema_data)

    if response.status_code == 200:
        print("✅ Schema created successfully!")
    else:
        print(f"❌ Failed to create schema. Status: {response.status_code}")
        print(response.text)


if __name__ == "__main__":
    post_schema(controller_url, schema_file)
