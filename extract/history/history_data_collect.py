import requests
import json
from datetime import datetime
import time

API_KEY = 'YOUR_API_KEY'
API_SECRET = 'YOUR_API_SECRET'
BASE_URL = 'https://data.alpaca.markets/v2/stocks'
SYMBOL = "AAPL,MSFT,TSLA,AMZN,NFLX"

HEADERS = {
    "APCA-API-KEY-ID": "***REMOVED***",
    "APCA-API-SECRET-KEY": "***REMOVED***"
}

# Earliest available date for IEX is much more limited (~2020+)
# Adjust as needed; using latest info: 2021-08-01
start_dt = datetime(2021, 8, 1)
end_dt = datetime.utcnow()

def isoformat(dt):
    return dt.isoformat(timespec='seconds') + 'Z'

out_file = '/nvmewd/data/iex/bars.ndjson'

with open(out_file, 'w') as f:
    next_page_token = None
    while True:
        params = {
            "start": isoformat(start_dt),
            "end": isoformat(end_dt),
            "timeframe": "1Min",
            "limit": 10000,
            "feed": "iex",
            "symbols": SYMBOL
        }
        if next_page_token:
            params['page_token'] = next_page_token

        url = f"{BASE_URL}/bars"
        resp = requests.get(url, params=params, headers=HEADERS)
        if resp.status_code != 200:
            print(f"Error: {resp.status_code} - {resp.text}")
            break

        data = resp.json()
        bars_dict = data.get('bars', {})
        if not bars_dict:
            print("No more data.")
            break

        for symbol_key, bars_list in bars_dict.items():
            for bar in bars_list:
                bar_with_symbol = dict(bar)
                bar_with_symbol['symbol'] = symbol_key  # annotate symbol
                f.write(json.dumps(bar_with_symbol) + "\n")

        next_page_token = data.get('next_page_token')
        if not next_page_token:
            break

        time.sleep(0.5)
