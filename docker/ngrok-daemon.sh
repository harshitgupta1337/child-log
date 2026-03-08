#!/bin/bash

ngrok config add-authtoken ${NGROK_AUTH_TOKEN}

ngrok http 8000 >/ngrok.log 2>&1 &

sleep 2

ngrokPublicUrl=$(curl http://127.0.0.1:4040/api/tunnels | jq -r ".tunnels[0].public_url")

curl -X POST \
  https://api.telegram.org/bot${TELEGRAM_BOT_TOKEN}/setWebhook \
  -d url=${ngrokPublicUrl}/telegram/webhook
