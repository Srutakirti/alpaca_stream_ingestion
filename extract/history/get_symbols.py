import requests

API_KEY = 'YOUR_API_KEY'
API_SECRET = 'YOUR_API_SECRET'
ASSETS_URL = 'https://paper-api.alpaca.markets/v2/assets'

HEADERS = {
    "APCA-API-KEY-ID": "***REMOVED***",
    "APCA-API-SECRET-KEY": "***REMOVED***"
}

def get_iex_symbols():
    symbols = []
    page_token = None
    while True:
        params = {
            "status": "active",
            "tradable": "true",
            "exchange": "IEX",
            "asset_class":"us_equity",
            "limit": 1000
        }
        if page_token:
            params['page_token'] = page_token
        resp = requests.get(ASSETS_URL, headers=HEADERS, params=params)
        if resp.status_code != 200:
            print(f"Error: {resp.status_code} - {resp.text}")
            break
        data = resp.json()
        if not data:
            break
        symbols.extend([a['symbol'] for a in data if a['tradable']])
        if len(data) < 1000:
            break
        # If Alpaca implements pagination, extract next page token if/when available.
        page_token = None
    return symbols

iex_symbols = get_iex_symbols()
print(f"Fetched {len(iex_symbols)} IEX symbols.")

with open('iex_symbols.txt', 'w') as f:
    for symbol in iex_symbols:
        f.write(symbol + "\n")