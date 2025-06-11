#!/bin/bash

SERVICE_NAME=trigger
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
SCRIPT_DIR="/home/srutakirti_mangaraj_fractal_ai/alpaca_stream_ingestion"
PYTHON_SCRIPT="startup.py"
RUN_USER="srutakirti_mangaraj_fractal_ai"

echo "🔧 Creating systemd service file at $SERVICE_FILE..."

sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=Run Alpaca Stream Ingestion Startup Script at Boot
After=network.target

[Service]
Type=simple
User=$RUN_USER
WorkingDirectory=$SCRIPT_DIR
ExecStart=/usr/bin/python3 $SCRIPT_DIR/$PYTHON_SCRIPT
Restart=no

[Install]
WantedBy=multi-user.target
EOF

echo "🔄 Reloading systemd daemon..."
sudo systemctl daemon-reexec
sudo systemctl daemon-reload

echo "✅ Enabling service to start on reboot only..."
sudo systemctl enable "$SERVICE_NAME"

echo -e "\n✅ Service '$SERVICE_NAME' installed and will run at next boot."
echo "ℹ️ It has NOT been started now (per your request)."
echo "👉 To manually start: sudo systemctl start $SERVICE_NAME"
echo "👉 To check logs later: sudo journalctl -u $SERVICE_NAME -e"
