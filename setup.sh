#!/bin/bash
set -euo pipefail

# Project SQLi-Universal: Master Setup Script
# Targets: Ubuntu WSL2

echo "[*] Initializing SQLi-Universal Agent Setup..."

# 1. System Dependencies
echo "[*] Updating system and installing base dependencies..."
sudo apt update && sudo apt install -y python3-venv git curl ca-certificates
sudo update-ca-certificates

echo "[*] Installing production-grade sqlmap..."
sudo apt remove -y sqlmap
if [ ! -d "/opt/sqlmap" ]; then
    sudo git clone --depth 1 https://github.com/sqlmapproject/sqlmap.git /opt/sqlmap
    sudo ln -sf /opt/sqlmap/sqlmap.py /usr/local/bin/sqlmap
fi

# 2. Networking Bridge
echo "[*] Configuring WSL2 to Windows Host Bridge..."
WIN_IP=$(ip route show default | awk '{print $3}')
if ! grep -q "WIN_HOST_IP" ~/.bashrc; then
    echo "export WIN_HOST_IP=$WIN_IP" >> ~/.bashrc
    echo "export TARGET_IP=172.18.0.1" >> ~/.bashrc
    echo "export no_proxy=\"localhost,127.0.0.1,172.18.0.1\"" >> ~/.bashrc
    echo "export NO_PROXY=\"localhost,127.0.0.1,172.18.0.1\"" >> ~/.bashrc
    echo "export PATH=\"\$PATH:/mnt/c/Program Files/Mozilla Firefox/\"" >> ~/.bashrc
fi

# 3. Python Environment
echo "[*] Setting up Python Virtual Environment..."
python3 -m venv venv --without-pip
PIP_TMP="$(mktemp -d)"
curl -fsSL https://bootstrap.pypa.io/get-pip.py -o "$PIP_TMP/get-pip.py"
./venv/bin/python3 "$PIP_TMP/get-pip.py"
rm -rf "$PIP_TMP"

echo "[*] Installing project dependencies..."
./venv/bin/pip install -r requirements.txt

# 4. Playwright Setup
echo "[*] Installing Playwright Browsers..."
./venv/bin/python3 -m playwright install chromium

echo "[*] opencode.json ships with the repository; edit it in place if you change agents or MCP servers."

echo "[+] Setup Complete! Please run 'source ~/.bashrc' and then 'opencode .'"
