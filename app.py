import os
import json
import requests
import re
from datetime import datetime, timedelta

from flask import Flask, request, abort

# LINE SDK v3 FIXED IMPORTS
from linebot.v3.webhook import WebhookHandler
from linebot.v3.webhooks import MessageEvent, TextMessageContent, ImageMessageContent

from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    MessagingApiBlob,
    ReplyMessageRequest,
    TextMessage
)

# =========================
# CONFIGURATION
# =========================

LINE_CHANNEL_ACCESS_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.environ.get("LINE_CHANNEL_SECRET")
OCR_API_KEY = os.environ.get("OCR_API_KEY")

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET or not OCR_API_KEY:
    raise Exception("Missing environment variables")

configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# =========================
# FLASK APP
# =========================

app = Flask(__name__)

@app.route("/")
def home():
    return "Study ScreenTime Bot Running ✅"

@app.route("/callback", methods=["POST"])
def callback():

    signature = request.headers.get("X-Line-Signature")
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except Exception as e:
        print("Webhook error:", e)
        abort(400)

    return "OK"


# =========================
# STREAK SYSTEM
# =========================

DATA_FILE = "streak.json"


def load_data():

    if not os.path.exists(DATA_FILE):
        return {}

    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_data(data):

    with open(DATA_FILE, "w") as f:
        json.dump(data, f)


def update_streak(user_id):

    data = load_data()
    today = datetime.now().date()

    if user_id not in data:

        data[user_id] = {
            "streak": 1,
            "last_date": str(today)
        }

        save_data(data)
        return 1

    last_date = datetime.strptime(
        data[user_id]["last_date"], "%Y-%m-%d"
    ).date()

    if last_date == today:
        return data[user_id]["streak"]

    if last_date == today - timedelta(days=1):
        data[user_id]["streak"] += 1
    else:
        data[user_id]["streak"] = 1

    data[user_id]["last_date"] = str(today)

    save_data(data)

    return data[user_id]["streak"]


# =========================
# SCREEN TIME DETECTION
# =========================

def detect_study_from_screentime(text):

    text = text.lower()

    categories = [
        "productivity & finance",
        "productivity",
        "education",
        "reference",
        "books"
    ]

    category_detected = any(cat in text for cat in categories)

    time_detected = bool(re.search(r"\d+h|\d+m", text))

    return category_detected and time_detected


# =========================
# TEXT HANDLER
# =========================

@handler.add(MessageEvent, message=TextMessageContent)
def handle_text(event):

    user_id = event.source.user_id
    text = event.message.text.lower()

    if text == "study":

        streak = update_streak(user_id)

        reply = f"📚 Study recorded!\n🔥 Streak: {streak} days"

    elif text == "streak":

        data = load_data()

        if user_id in data:
            reply = f"🔥 Your streak: {data[user_id]['streak']} days"
        else:
            reply = "No streak yet."

    else:

        reply = (
            "Send Screen Time screenshot 📷\n"
            "Or type 'study' to manually record."
        )

    with ApiClient(configuration) as api_client:

        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply)]
            )
        )


# =========================
# IMAGE HANDLER (FINAL FIXED)
# =========================

@handler.add(MessageEvent, message=ImageMessageContent)
def handle_image(event):

    try:

        user_id = event.source.user_id
        message_id = event.message.id

        # download image correctly
        with ApiClient(configuration) as api_client:

            blob_api = MessagingApiBlob(api_client)

            image_data = blob_api.get_message_content(message_id)

        # OCR request
        response = requests.post(
            "https://api.ocr.space/parse/image",
            files={"file": ("image.jpg", image_data)},
            data={
                "apikey": OCR_API_KEY,
                "language": "eng"
            }
        )

        result = response.json()

        extracted_text = ""

        if result.get("ParsedResults"):
            extracted_text = result["ParsedResults"][0]["ParsedText"]

        print("OCR TEXT:", extracted_text)

        # DETECT SCREEN TIME
        if detect_study_from_screentime(extracted_text):

            streak = update_streak(user_id)

            reply = (
                "✅ Screen Time Study detected!\n"
                f"🔥 Streak: {streak} days"
            )

        else:

            reply = (
                "❌ No Productivity/Education detected.\n"
                "Send Screen Time screenshot."
            )

    except Exception as e:

        print("IMAGE ERROR:", e)
        reply = "❌ Error reading screenshot."

    with ApiClient(configuration) as api_client:

        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply)]
            )
        )


# =========================
# RENDER START
# =========================

if __name__ == "__main__":

    port = int(os.environ.get("PORT", 10000))

    app.run(
        host="0.0.0.0",
        port=port
    )