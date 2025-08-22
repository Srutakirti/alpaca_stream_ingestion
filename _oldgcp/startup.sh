#!/bin/bash

# Set PROJECT_DIR to the absolute path of your project
PROJECT_DIR="/home/srutakirti_mangaraj_fractal_ai/alpaca_stream_ingestion"
UV_PATH="/home/srutakirti_mangaraj_fractal_ai/.local/bin/uv"
WEBSCOKET_SCRIPT="alpaca_ws_updated_conf.py"
COMPARATOR_SCRIPT="compare_spark_kafka_offsets.py"


# Create log directory if it doesn't exist
LOG_DIR="/tmp/alpaca_logs"
mkdir -p $LOG_DIR

# Get current date in YYYYMMDD format
DATE=$(date +%Y%m%d)

# Change to project directory
cd $PROJECT_DIR || exit 1

export PYTHONPATH=$PROJECT_DIR

# Source environment variables and any other initialization
source init.sh || {
    echo "Failed to source init.sh" >> "${LOG_DIR}/startup_error_${DATE}.log"
    exit 1
}

# Function to check if a process is already running and log status
check_process() {
    local script_name=$1
    if pgrep -f "$script_name" > /dev/null; then
        echo "$(date): Process $script_name is already running, skipping start" | tee -a "${LOG_DIR}/startup_${DATE}.log"
        return 0
    fi
    return 1
}

# Start offset comparison script if not already running
if ! check_process "${COMPARATOR_SCRIPT}"; then
    nohup ${UV_PATH} run extract/${COMPARATOR_SCRIPT} \
        > "${LOG_DIR}/offset_compare_${DATE}.log" 2>&1 &
    echo "$(date): staring script ${COMPARATOR_SCRIPT}" | tee -a "${LOG_DIR}/startup_${DATE}.log"
fi

# Start Kafka producer script if not already running
if ! check_process "${WEBSCOKET_SCRIPT}"; then
    nohup ${UV_PATH} run python extract/${WEBSCOKET_SCRIPT}  > "${LOG_DIR}/kafka_producer_${DATE}.log" 2>&1 &
    echo "$(date): starting script ${WEBSCOKET_SCRIPT}" | tee -a "${LOG_DIR}/startup_${DATE}.log"
fi