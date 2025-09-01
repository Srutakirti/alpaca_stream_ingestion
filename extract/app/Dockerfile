## Run it from the project root directory
## this docker build -t ws_scraper:v1.0 -f extract/Dockerfile .

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies if needed
RUN apt-get update && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .


# Ensure /app is in PYTHONPATH so conf_reader can be imported
ENV PYTHONPATH=/app

ENV PYTHONUNBUFFERED=1

CMD ["python", "/app/alpaca_ws_updated_conf.py"]