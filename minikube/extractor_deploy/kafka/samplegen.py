import json
import random
import time
import sys
from datetime import datetime

# Define possible event types
EVENT_TYPES = ["click", "view", "purchase", "signup", "logout"]

def generate_event():
    return {
        "event_type": random.choice(EVENT_TYPES),
        "value": round(random.uniform(1.0, 100.0), 2),
        "ts": int(time.time() * 1000)  # current timestamp in milliseconds
    }

def main():
    while True:
        event = generate_event()
        print(json.dumps(event), flush=True)
        time.sleep(0.3)  # adjust sleep to control event rate

if __name__ == "__main__":
    main()

