import json
import requests
from fastapi import FastAPI, Request
from datetime import datetime, timedelta
import asyncio
from parser import parse_message

app = FastAPI()

BOT_TOKEN = "YOUR_BOT_TOKEN"
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"

# -----------------------------
# In-memory pending store
# -----------------------------
pending_confirmations = {}

CONFIRM_TTL_MINUTES = 10


# -----------------------------
# Dummy DSL Parser (replace with yours)
# -----------------------------
def parse_dsl(text: str):
    parse_message(text, datetime.now())


# -----------------------------
# Dummy Huckleberry Adapter
# -----------------------------
def upload_to_huckleberry(event):
    # Replace with real API call
    print("Uploading:", event)
    return True


# -----------------------------
# Utility: Send Message
# -----------------------------
def send_message(chat_id, text):
    payload = {
        "chat_id": chat_id,
        "text": text
    }
    requests.post(f"{TELEGRAM_API}/sendMessage", json=payload)


# -----------------------------
# Utility: Send Confirmation
# -----------------------------
def send_confirmation(chat_id, text):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "reply_markup": {
            "inline_keyboard": [
                [
                    {"text": "✅ Confirm", "callback_data": "confirm"},
                    {"text": "❌ Cancel", "callback_data": "cancel"}
                ]
            ]
        }
    }

    response = requests.post(f"{TELEGRAM_API}/sendMessage", json=payload)
    return response.json()


# -----------------------------
# Format Confirmation Message
# -----------------------------
def format_confirmation(event):
    text = f"🕒 Time: {event['time']}\n\n"
    for e in event["events"]:
        if e["type"] == "breastfeed":
            text += (
                "🍼 Breastfeed\n"
                f"  - Total: {e.get('duration')} min\n"
                f"  - Left: {e.get('left')} min\n"
                f"  - Right: {e.get('right')} min\n\n"
            )
    text += "Confirm upload?"
    return text


# -----------------------------
# Webhook Endpoint
# -----------------------------
@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    update = await request.json()

    print ("Hello world")

    if "message" in update:
        return await handle_message(update["message"])

    if "callback_query" in update:
        return await handle_callback(update["callback_query"])

    return {"ok": True}


# -----------------------------
# Handle New Message
# -----------------------------
async def handle_message(message):
    chat_id = message["chat"]["id"]
    user_id = message["from"]["id"]
    text = message.get("text", "")

    parsed_event = parse_dsl(text)

    if not parsed_event:
        send_message(chat_id, "❌ Could not parse event.")
        return {"ok": True}

    confirmation_text = format_confirmation(parsed_event)

    response = send_confirmation(chat_id, confirmation_text)

    message_id = response["result"]["message_id"]

    # Store pending event
    pending_confirmations[message_id] = {
        "user_id": user_id,
        "parsed_event": parsed_event,
        "timestamp": datetime.utcnow()
    }

    return {"ok": True}


# -----------------------------
# Handle Confirm / Cancel
# -----------------------------
async def handle_callback(callback):
    data = callback["data"]
    chat_id = callback["message"]["chat"]["id"]
    message_id = callback["message"]["message_id"]

    pending = pending_confirmations.get(message_id)

    if not pending:
        send_message(chat_id, "⚠️ No pending event found or expired.")
        return {"ok": True}

    if data == "confirm":
        success = upload_to_huckleberry(pending["parsed_event"])

        if success:
            send_message(chat_id, "✅ Uploaded successfully.")
        else:
            send_message(chat_id, "❌ Upload failed.")

        del pending_confirmations[message_id]

    elif data == "cancel":
        send_message(chat_id, "❌ Cancelled.")
        del pending_confirmations[message_id]

    return {"ok": True}


# -----------------------------
# Background Cleanup Task
# -----------------------------
async def cleanup_expired():
    while True:
        now = datetime.utcnow()
        expired = []

        for msg_id, data in pending_confirmations.items():
            if now - data["timestamp"] > timedelta(minutes=CONFIRM_TTL_MINUTES):
                expired.append(msg_id)

        for msg_id in expired:
            del pending_confirmations[msg_id]

        await asyncio.sleep(60)


@app.on_event("startup")
async def startup_event():
    asyncio.create_task(cleanup_expired())

