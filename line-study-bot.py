import pytesseract
pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"
import os
import sys
import json
from datetime import datetime, date
from flask import Flask, request, abort

from linebot.v3.webhook import WebhookHandler
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import MessageEvent, TextMessageContent


# ========================
# ENV VARIABLES
# ========================

CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")

if not CHANNEL_ACCESS_TOKEN or not CHANNEL_SECRET:
    print("ERROR: Missing LINE credentials")
    sys.exit(1)


# ========================
# FILE STORAGE
# ========================

DATA_FILE = "streak_data.json"

if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump({}, f)


def load_data():
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)


# ========================
# LINE CONFIG
# ========================

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

app = Flask(__name__)


# ========================
# ROUTES
# ========================

@app.route("/")
def home():
    return "Study bot running with streak system."


@app.route("/callback", methods=["POST"])
def callback():

    signature = request.headers.get("X-Line-Signature")
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK"


# ========================
# STREAK FUNCTION
# ========================

def update_streak(user_id):

    data = load_data()

    today = date.today()

    if user_id not in data:

        data[user_id] = {
            "streak": 1,
            "last_date": str(today)
        }

        save_data(data)

        return 1, True

    last_date = date.fromisoformat(data[user_id]["last_date"])
    streak = data[user_id]["streak"]

    if last_date == today:
        return streak, False

    elif (today - last_date).days == 1:
        streak += 1

    else:
        streak = 1

    data[user_id]["streak"] = streak
    data[user_id]["last_date"] = str(today)

    save_data(data)

    return streak, True


# ========================
# MESSAGE HANDLER
# ========================

@handler.add(MessageEvent, message=TextMessageContent)
def handle_message(event):

    user_id = event.source.user_id
    text = event.message.text.lower()

    reply = ""

    if text == "study":

        streak, updated = update_streak(user_id)

        if updated:
            reply = f"🔥 Study recorded!\nYour streak: {streak} days"
        else:
            reply = f"✅ Already studied today!\nCurrent streak: {streak} days"

    elif text == "streak":

        data = load_data()

        if user_id in data:
            reply = f"🔥 Your streak: {data[user_id]['streak']} days"
        else:
            reply = "No streak yet. Send 'study' to start!"

    else:
        reply = "Send 'study' to record your study."

    with ApiClient(configuration) as api_client:

        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply)]
            )
        )


# ========================
# RUN SERVER
# ========================

if __name__ == "__main__":

    port = int(os.environ.get("PORT", 10000))

    app.run(host="0.0.0.0", port=port)