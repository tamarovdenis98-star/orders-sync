#!/usr/bin/env bash
# Однократная подготовка VPS (Ubuntu/Debian). Запускать на сервере от root:
#   ssh myvps 'bash -s' < scripts/server-setup.sh
set -euo pipefail

if ! command -v docker >/dev/null; then
  curl -fsSL https://get.docker.com | sh
fi
systemctl enable --now docker

# Фаервол: ssh + http/https
if command -v ufw >/dev/null; then
  ufw allow OpenSSH || true
  ufw allow 80/tcp || true
  ufw allow 443/tcp || true
  ufw --force enable || true
fi

mkdir -p /opt/app
docker --version
docker compose version
echo "Server ready."
