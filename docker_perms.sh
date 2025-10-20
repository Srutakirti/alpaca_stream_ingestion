#!/bin/bash

# Set up color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Add user to docker group if not already in it
if ! groups $USER | grep -q docker; then
    sudo usermod -aG docker $USER
    sudo systemctl restart docker
fi

# Use sg to run a new shell with docker group
exec sg docker -c '
    if docker info >/dev/null 2>&1; then
        echo -e "${GREEN}[INFO]${NC} Docker permissions activated successfully"
        exec "$SHELL"
    else
        echo -e "${RED}[ERROR]${NC} Failed to activate docker permissions"
        exit 1
    fi
'