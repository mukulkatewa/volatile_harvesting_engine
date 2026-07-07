#!/usr/bin/env bash
#
# VHE deployment bootstrap for an Oracle Cloud "Always Free" Ubuntu 24.04 VM.
#
# Usage (run as the default `ubuntu` user, from the cloned repo root):
#   cd ~/volatile_harvesting_engine
#   VHE_DOMAIN=yourname.duckdns.org bash deploy/setup.sh
#
# What it does:
#   1. Installs system deps (Python 3.12, venv, git, Caddy)
#   2. Creates a virtualenv and installs the package
#   3. Installs a systemd service so the engine runs 24/7 and auto-restarts
#   4. Configures Caddy as an HTTPS reverse proxy (auto Let's Encrypt cert)
#
# Ports 80 and 443 must be open in the Oracle VCN security list AND on the VM
# firewall (this script opens the VM firewall via iptables/ufw where present).

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_USER="$(id -un)"
PORT="${VHE_PORT:-8765}"

echo "==> Repo:    ${REPO_DIR}"
echo "==> User:    ${SERVICE_USER}"
echo "==> Domain:  ${VHE_DOMAIN:-<none: HTTPS/OAuth will not work until set>}"
echo "==> App port: ${PORT}"

echo "==> Installing system packages..."
sudo apt-get update -y
sudo apt-get install -y python3 python3-venv python3-pip git debian-keyring debian-archive-keyring apt-transport-https curl

if ! command -v caddy >/dev/null 2>&1; then
  echo "==> Installing Caddy (reverse proxy + automatic HTTPS)..."
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
  curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list >/dev/null
  sudo apt-get update -y
  sudo apt-get install -y caddy
fi

echo "==> Creating virtualenv..."
cd "${REPO_DIR}"
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
./.venv/bin/pip install --upgrade pip
./.venv/bin/pip install -e .

if [ ! -f .env ]; then
  echo "==> No .env found — copying from .env.example. YOU MUST EDIT IT."
  cp .env.example .env
fi

echo "==> Installing systemd service..."
sudo tee /etc/systemd/system/vhe.service >/dev/null <<UNIT
[Unit]
Description=Volatility Harvesting Engine
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
WorkingDirectory=${REPO_DIR}
ExecStart=${REPO_DIR}/.venv/bin/uvicorn vhe.platform.server:app --host 127.0.0.1 --port ${PORT} --app-dir python
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
UNIT

sudo systemctl daemon-reload
sudo systemctl enable vhe.service
sudo systemctl restart vhe.service

if [ -n "${VHE_DOMAIN:-}" ]; then
  echo "==> Configuring Caddy for ${VHE_DOMAIN}..."
  sudo tee /etc/caddy/Caddyfile >/dev/null <<CADDY
${VHE_DOMAIN} {
    reverse_proxy 127.0.0.1:${PORT}
}
CADDY
  sudo systemctl restart caddy

  echo "==> Opening firewall ports 80/443 on the VM..."
  if command -v ufw >/dev/null 2>&1; then
    sudo ufw allow 80/tcp || true
    sudo ufw allow 443/tcp || true
  fi
  # Oracle Ubuntu images ship with iptables rules that block everything but SSH.
  sudo iptables -I INPUT -p tcp --dport 80 -j ACCEPT || true
  sudo iptables -I INPUT -p tcp --dport 443 -j ACCEPT || true
  sudo netfilter-persistent save 2>/dev/null || true
else
  echo "==> VHE_DOMAIN not set — skipping Caddy/HTTPS. Set it and re-run for OAuth."
fi

echo ""
echo "==> Done."
echo "    Service status:  sudo systemctl status vhe.service"
echo "    Service logs:    journalctl -u vhe.service -f"
if [ -n "${VHE_DOMAIN:-}" ]; then
  echo "    App URL:         https://${VHE_DOMAIN}"
  echo "    OAuth redirect:  https://${VHE_DOMAIN}/auth/google/callback"
fi
echo ""
echo "    Remember to edit .env (Google OAuth + JWT_SECRET) and run: sudo systemctl restart vhe.service"
