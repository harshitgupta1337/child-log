import json
import requests
from fastapi import FastAPI, Request
from datetime import datetime, timedelta
import asyncio
from zoneinfo import ZoneInfo
from parser import parse_message

app = FastAPI()

BOT_TOKEN = "8686910871:AAFP9rL4wQq4MFYFtp0yn_24BSJXPlnplsQ"
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
TIMEZONE="America/New_York"

# -----------------------------
# In-memory pending store
# -----------------------------
pending_confirmations = {}

CONFIRM_TTL_MINUTES = 10

# -----------------------------
# DSL Parser
# -----------------------------
def parse_dsl(text: str):
    print ("parsing text:", text)
    events, errs = parse_message(text, datetime.now())
    if len(errs) > 0:
        print ("Errors:", errs)
        return None
    return events

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
def format_confirmation(events):
    # pretty-print each event
    text = "Please confirm the following events:\n\n"
    timestamp_added = False
    for event in events:
        if event is not None:
            if not timestamp_added:
                text += "%s \n" % str(event.timestamp.astimezone(ZoneInfo(TIMEZONE)).strftime("%m-%d %H:%M"))
                timestamp_added = True
            text += "%s\n" % str(event)
    text += "\nConfirm upload?"
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

    parsed_events = parse_dsl(text)
    print ("parsed_events:", parsed_events)
    if parsed_events == None:
        return {"ok": True}

    print ("chat_id:", chat_id)
    print ("user_id:", user_id)
    print ("text:", text)

    send_message(chat_id, "🔍 Parsing your message...")

    if not parsed_events:
        send_message(chat_id, "❌ Could not parse event.")
        return {"ok": True}

    confirmation_text = format_confirmation(parsed_events)

    response = send_confirmation(chat_id, confirmation_text)

    message_id = response["result"]["message_id"]

    # Store pending event
    pending_confirmations[message_id] = {
        "user_id": user_id,
        "parsed_events": parsed_events,
        "timestamp": datetime.now()
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
        success = upload_to_huckleberry(pending["parsed_events"])

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

