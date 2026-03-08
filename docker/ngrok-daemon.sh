#!/bin/bash

set -e

ngrok config add-authtoken ${NGROK_AUTH_TOKEN}

ngrok http 8000 >/ngrok.log 2>&1 &
ngrokPid=$!

sleep 2

if kill -0 "$ngrokPid" 2>/dev/null; then
  echo "Process $ngrokPid is running. Safe to continue"
else
  echo "Process $ngrokPid is not running. Exiting."
  exit 1
fi

ngrokPublicUrl=$(curl http://127.0.0.1:4040/api/tunnels | jq -r ".tunnels[0].public_url")

curl -X POST \
  https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook \
  -d url=${ngrokPublicUrl}/telegram/webhook
