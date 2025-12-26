import pandas as pd
import requests
import json
import time
from tabulate import tabulate
import argparse
import subprocess

##pd options
pd.set_option('display.float_format', lambda x: '%.0f' % x)
pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)


def get_minikube_ip():
    """Get Minikube IP address."""
    try:
        result = subprocess.run(
            ['minikube', 'ip'],
            capture_output=True,
            text=True,
            timeout=5
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def detect_pinot_controller_nodeport(namespace='pinot', service_name='pinot-pinot-chart-controller'):
    """
    Dynamically detect the Pinot controller NodePort by querying Kubernetes.

    Returns:
        tuple: (minikube_ip, nodeport) or (None, None) if detection fails
    """
    try:
        # Get the service details as JSON
        result = subprocess.run(
            ['kubectl', 'get', 'svc', service_name, '-n', namespace, '-o', 'json'],
            capture_output=True,
            text=True,
            timeout=10
        )

        if result.returncode != 0:
            return None, None

        service_data = json.loads(result.stdout)

        # Extract NodePort from service spec
        if service_data['spec']['type'] == 'NodePort':
            ports = service_data['spec']['ports']
            if ports:
                node_port = ports[0].get('nodePort')
                if node_port:
                    # Get minikube IP
                    minikube_ip = get_minikube_ip()
                    if minikube_ip:
                        return minikube_ip, node_port
                    else:
                        return "192.168.49.2", node_port

        return None, None

    except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception):
        return None, None


def get_pinot_controller_url():
    """
    Get Pinot controller URL by dynamically detecting NodePort.

    Returns:
        str: The Pinot controller URL
    """
    # Try to dynamically detect the NodePort
    minikube_ip, node_port = detect_pinot_controller_nodeport()

    if minikube_ip and node_port:
        url = f"http://{minikube_ip}:{node_port}"
        print(f"Auto-detected Pinot controller: {url}")
        return url

    # Fall back to default
    default_url = "http://192.168.49.2:30900"
    print(f"Could not auto-detect Pinot controller, using default: {default_url}")
    return default_url

def query_pinot(pinot_url, query, debug=False):
    """Execute query against Pinot and return results as pandas DataFrame"""
    headers = {'Content-Type': 'application/json'}
    payload = {'sql': query}

    try:
        response = requests.post(f"{pinot_url}/sql", headers=headers, json=payload)
        response.raise_for_status()

        # Parse JSON response
        result = response.json()

        # Check for exceptions in response
        if 'exceptions' in result and result['exceptions']:
            if debug:
                print(f"Query error: {result['exceptions']}")
            return pd.DataFrame()

        # Convert to DataFrame
        if 'resultTable' in result:
            columns = result['resultTable']['dataSchema']['columnNames']
            data = result['resultTable']['rows']
            df = pd.DataFrame(data, columns=columns)
            # Convert numeric columns to integers
            numeric_columns = df.select_dtypes(include=['float64', 'int64']).columns
            for col in numeric_columns:
                df[col] = df[col].astype('int64')
            return df
        return pd.DataFrame()

    except requests.exceptions.RequestException as e:
        if debug:
            print(f"Error querying Pinot: {e}")
        return pd.DataFrame()

def format_large_number(x):
    return f"{int(x):,}"

def main():
    parser = argparse.ArgumentParser(description='Query Pinot table continuously')
    parser.add_argument('--interval', type=int, default=60, help='Query interval in seconds')
    args = parser.parse_args()

    # Auto-detect Pinot controller URL
    pinot_url = get_pinot_controller_url()

    # Count query
    count_query = """
    select count(*) as total_events from stock_ticks_latest_2
    """

    # Sample records query - get latest 10 records
    # Schema columns: S (symbol), o/h/l/c (prices), v (volume), timestamp
    # Note: 'timestamp' is a reserved keyword, use backticks
    records_query = """
    select S, o, h, l, c, v, `timestamp`
    from stock_ticks_latest_2
    order by "timestamp" desc
    limit 10
    """

    print(f"Starting continuous query with {args.interval} second interval...")
    print(f"Pinot URL: {pinot_url}")
    print("-" * 80)

    try:
        while True:
            # Clear screen (works on both Windows and Unix)
            print("\033[H\033[J")

            # Print timestamp
            print(f"Last updated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            print("=" * 80)

            # Execute count query
            count_df = query_pinot(pinot_url, count_query)

            if not count_df.empty:
                print("\n📊 TOTAL EVENT COUNT")
                print("-" * 80)

                # Format numbers with commas for readability
                for col in count_df.columns:
                    if pd.api.types.is_numeric_dtype(count_df[col]):
                        count_df[col] = count_df[col].apply(format_large_number)

                print(tabulate(count_df, headers='keys', tablefmt='psql', showindex=False))
            else:
                print("\n📊 TOTAL EVENT COUNT")
                print("-" * 80)
                print("No results returned")

            # Execute records query
            records_df = query_pinot(pinot_url, records_query, debug=True)

            if not records_df.empty:
                print("\n📝 LATEST 10 RECORDS")
                print("-" * 80)

                # Format timestamp column to readable format
                if 'timestamp' in records_df.columns:
                    records_df['time'] = pd.to_datetime(records_df['timestamp'], unit='ms').dt.strftime('%Y-%m-%d %H:%M:%S')

                # Rename columns for better display
                column_mapping = {
                    'S': 'symbol',
                    'o': 'open',
                    'h': 'high',
                    'l': 'low',
                    'c': 'close',
                    'v': 'volume'
                }
                records_df = records_df.rename(columns=column_mapping)

                # Select and reorder columns for display
                display_cols = []
                for col in ['symbol', 'open', 'high', 'low', 'close', 'volume', 'time']:
                    if col in records_df.columns:
                        display_cols.append(col)

                if display_cols:
                    records_df = records_df[display_cols]

                # Format numbers with commas for readability (only for volume)
                if 'volume' in records_df.columns:
                    records_df['volume'] = records_df['volume'].apply(format_large_number)

                # Round price columns to 2 decimal places
                for col in ['open', 'high', 'low', 'close']:
                    if col in records_df.columns:
                        records_df[col] = records_df[col].round(2)

                print(tabulate(records_df, headers='keys', tablefmt='psql', showindex=False))
            else:
                print("\n📝 LATEST 10 RECORDS")
                print("-" * 80)
                print("No results returned")

            print("\n" + "=" * 80)
            print(f"Next refresh in {args.interval} seconds... (Press Ctrl+C to stop)")

            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\nStopping query execution...")

if __name__ == "__main__":
    main()