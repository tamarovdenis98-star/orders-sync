#!/usr/bin/env bash
# Деплой одной командой: ./deploy.sh
# Работает из Git Bash на Windows, macOS и Linux (нужны ssh, tar, curl).
set -euo pipefail
cd "$(dirname "$0")"
source ./deploy.conf

echo "==> Uploading to $SSH_HOST:$REMOTE_DIR"
tar czf - \
  --exclude=.git --exclude=data --exclude=.env --exclude=__pycache__ \
  --exclude=.venv --exclude=node_modules --exclude=.claude \
  . | ssh "$SSH_HOST" "mkdir -p '$REMOTE_DIR' && tar xzf - -C '$REMOTE_DIR'"

echo "==> Building & starting containers"
ssh "$SSH_HOST" "set -e; cd '$REMOTE_DIR'; touch .env; \
  grep -v '^SITE_ADDRESS=' .env > .env.tmp || true; \
  echo 'SITE_ADDRESS=$SITE_ADDRESS' >> .env.tmp; mv .env.tmp .env; \
  docker compose up -d --build --remove-orphans; \
  docker image prune -f >/dev/null"

echo "==> Waiting for $PUBLIC_URL/health"
for i in $(seq 1 30); do
  if curl -fsS --max-time 5 "$PUBLIC_URL/health" >/dev/null 2>&1; then
    echo "OK: $PUBLIC_URL"
    exit 0
  fi
  sleep 2
done

echo "!! Health check failed. Last logs:"
ssh "$SSH_HOST" "cd '$REMOTE_DIR' && docker compose logs --tail=50 app"
exit 1
