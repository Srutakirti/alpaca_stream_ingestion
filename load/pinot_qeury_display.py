import pandas as pd
import requests
import json
import time
from tabulate import tabulate
import argparse

##pd opttions
pd.set_option('display.float_format', lambda x: '%.0f' % x)
pd.set_option('display.max_rows', None)
pd.set_option('display.max_columns', None)

def query_pinot(pinot_url, query):
    """Execute query against Pinot and return results as pandas DataFrame"""
    headers = {'Content-Type': 'application/json'}
    payload = {'sql': query}
    
    try:
        response = requests.post(f"{pinot_url}/sql", headers=headers, json=payload)
        response.raise_for_status()
        
        # Parse JSON response
        result = response.json()
        
        # Convert to DataFrame
                # Convert to DataFrame and format numbers
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
        print(f"Error querying Pinot: {e}")
        return pd.DataFrame()

def format_large_number(x):
    return f"{int(x):,}"

def main():
    parser = argparse.ArgumentParser(description='Query Pinot table continuously')
    parser.add_argument('--url', default='http://192.168.49.2:30697', help='Pinot controller URL')
    #parser.add_argument('--query', required=True, help='SQL query to execute')
    parser.add_argument('--interval', type=int, default=60, help='Query interval in seconds')
    args = parser.parse_args()

    # query = """select S stock_ticker, sum(V) as traded_volume 
    # from stock_ticks_latest_1 
    # group by S
    # order by traded_volume desc
    # limit 5
    # """
            
    query = """
    select count(*) as total_events from stock_ticks_latest_2
    """

    print(f"Starting continuous query with {args.interval} second interval...")
    print(f"Query: {query}")
    print(f"Pinot URL: {args.url}")
    print("-" * 80)

    try:
        while True:
            # Execute query and get results as DataFrame
            df = query_pinot(args.url, query)
            
            if not df.empty:
                # Clear screen (works on both Windows and Unix)
                print("\033[H\033[J")
                
                # Print timestamp and query
                print(f"Last updated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"Query: {query}")
                print("-" * 80)

                # Format numbers with commas for readability
                for col in df.columns:
                    if pd.api.types.is_numeric_dtype(df[col]):
                        df[col] = df[col].apply(format_large_number)
                
                # Print DataFrame in a nice table format
                print(tabulate(df, headers='keys', tablefmt='psql', showindex=False))
            else:
                print("No results returned")
            
            time.sleep(args.interval)

    except KeyboardInterrupt:
        print("\nStopping query execution...")

if __name__ == "__main__":
    main()