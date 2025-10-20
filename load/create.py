import requests
import json
import os

# --- Parameters ---
controller_url = "http://localhost:9000"   # Pinot Controller URL
table_file = "load/table.json"  
schema_file = "load/schema.json"            # Path to schema JSON file
# ------------------

def create_schema_and_table(controller_url: str, schema_json_path: str, table_json_path:str):
    if not (os.path.isfile(schema_json_path) and  os.path.isfile(table_json_path)):
        raise FileNotFoundError(f"File not found")

    with open(schema_json_path, "r") as f:
        schema_data = json.load(f)

        url = f"{controller_url}/schemas" ##use schemas or tables based on need
        headers = {"Content-Type": "application/json"}

        response = requests.post(url, headers=headers, json=schema_data)

        if response.status_code == 200:
            print("✅ Schema created successfully!")
        else:
            print(f"❌ Failed to create schema. Status: {response.status_code}")
            print(response.text)
    with open(table_json_path, "r") as f:
        table_data = json.load(f)

        url = f"{controller_url}/tables" ##use schemas or tables based on need
        headers = {"Content-Type": "application/json"}

        response = requests.post(url, headers=headers, json=table_data)

        if response.status_code == 200:
            print("✅ Table created successfully!")
        else:
            print(f"❌ Failed to create Table. Status: {response.status_code}")
            print(response.text)

if __name__ == "__main__":
    create_schema_and_table(controller_url, schema_file,table_file)
