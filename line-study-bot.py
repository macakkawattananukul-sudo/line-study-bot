import os
import re
import json
import datetime
import requests

from flask import Flask, request, abort

# LINE SDK v3 imports
from linebot.v3.webhook import WebhookHandler
from linebot.v3.messaging import (
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    Configuration,
    ApiClient
)
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    ImageMessageContent
)

# ========================
# ENV VARIABLES
# ========================

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
OCR_API_KEY = os.getenv("OCR_API_KEY")

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise Exception("Missing LINE credentials")

# ========================
# LINE setup
# ========================

configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
api_client = ApiClient(configuration)
line_bot_api = MessagingApi(api_client)

handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ========================
# Flask app
# ========================

app = Flask(__name__)

# ========================
# Database (JSON file)
# ========================

DB_FILE = "study_data.json"


def load_db():
    if not os.path.exists(DB_FILE):
        return {}
    with open(DB_FILE, "r") as f:
        return json.load(f)


def save_db(db):
    with open(DB_FILE, "w") as f:
        json.dump(db, f)


# ========================
# Extract hours from text
# ========================

def extract_hours(text):

    text = text.lower()

    patterns = [
        r"(\d+)\s*h",
        r"(\d+)\s*hour",
        r"study\s*(\d+)",
        r"(\d+)"
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return int(match.group(1))

    return 0


# ========================
# Streak system
# ========================

def update_streak(user_id):

    db = load_db()

    today = datetime.date.today()

    if user_id not in db:

        db[user_id] = {
            "streak": 1,
            "last_date": str(today)
        }

        save_db(db)
        return 1

    last_date = datetime.date.fromisoformat(db[user_id]["last_date"])
    streak = db[user_id]["streak"]

    if today == last_date:

        return streak

    elif today == last_date + datetime.timedelta(days=1):

        streak += 1

    else:

        streak = 1

    db[user_id]["streak"] = streak
    db[user_id]["last_date"] = str(today)

    save_db(db)

    return streak


# ========================
# OCR API
# ========================

    from linebot.v3.messaging import ApiClient, MessagingApiBlob
    import requests

    @handler.add(MessageEvent, message=ImageMessageContent)
    def handle_image(event):

        try:
            message_id = event.message.id

            # Download image from LINE (CORRECT METHOD)
            with ApiClient(configuration) as api_client:
                blob_api = MessagingApiBlob(api_client)
                content = blob_api.get_message_content(message_id)

            image_bytes = b''.join(content.iter_bytes())

            # Send image to OCR API
            response = requests.post(
                "https://api.ocr.space/parse/image",
                files={"file": ("image.jpg", image_bytes)},
                data={
                    "apikey": OCR_API_KEY,
                    "language": "eng"
                }
            )

            result = response.json()

            if result["IsErroredOnProcessing"]:
                reply_text(event.reply_token, "❌ OCR failed")
                return

            text = result["ParsedResults"][0]["ParsedText"]

            hours = extract_hours(text)

            if hours == 0:
                reply_text(event.reply_token, "❌ No study time detected")
                return

            streak = update_streak(event.source.user_id)

            reply_text(
                event.reply_token,
                f"📷 Study detected: {hours} hour(s)\n🔥 Streak: {streak} day(s)"
            )

        except Exception as e:
            print("Image error:", e)
            reply_text(event.reply_token, "❌ Image processing failed")

# ========================
# Routes
# ========================

    from linebot.v3.messaging import ApiClient, MessagingApiBlob
    import requests

    @handler.add(MessageEvent, message=ImageMessageContent)
    def handle_image(event):

        try:
            message_id = event.message.id

            # Download image from LINE (CORRECT METHOD)
            with ApiClient(configuration) as api_client:
                blob_api = MessagingApiBlob(api_client)
                content = blob_api.get_message_content(message_id)

            image_bytes = b''.join(content.iter_bytes())

            # Send image to OCR API
            response = requests.post(
                "https://api.ocr.space/parse/image",
                files={"file": ("image.jpg", image_bytes)},
                data={
                    "apikey": OCR_API_KEY,
                    "language": "eng"
                }
            )

            result = response.json()

            if result["IsErroredOnProcessing"]:
                reply_text(event.reply_token, "❌ OCR failed")
                return

            text = result["ParsedResults"][0]["ParsedText"]

            hours = extract_hours(text)

            if hours == 0:
                reply_text(event.reply_token, "❌ No study time detected")
                return

            streak = update_streak(event.source.user_id)

            reply_text(
                event.reply_token,
                f"📷 Study detected: {hours} hour(s)\n🔥 Streak: {streak} day(s)"
            )

        except Exception as e:
            print("Image error:", e)
            reply_text(event.reply_token, "❌ Image processing failed")
    # ========================
    # TEXT MESSAGE
    # ========================

    if isinstance(event.message, TextMessageContent):

        text = event.message.text.lower()

        if text.startswith("study"):

            hours = extract_hours(text)

            if hours > 0:

                streak = update_streak(user_id)

                reply = (
                    f"📚 Logged {hours} hour(s)\n"
                    f"🔥 Streak: {streak} day(s)"
                )

            else:

                reply = "Example: study 2h"

        elif text == "streak":

            db = load_db()

            if user_id in db:
                reply = f"🔥 Current streak: {db[user_id]['streak']} day(s)"
            else:
                reply = "No streak yet"

        else:

            reply = (
                "Commands:\n"
                "study 2h\n"
                "streak\n"
                "or send study screenshot"
            )

        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply)]
            )
        )

    # ========================
    # IMAGE MESSAGE (FIXED)
    # ========================

    elif isinstance(event.message, ImageMessageContent):

        try:

            message_id = event.message.id

            message_content = line_bot_api.get_message_content(message_id)

            image_bytes = b""

            for chunk in message_content.iter_content():
                image_bytes += chunk

            text = extract_text_from_image(image_bytes)

            hours = extract_hours(text)

            if hours > 0:

                streak = update_streak(user_id)

                reply = (
                    f"📷 Study detected: {hours} hour(s)\n"
                    f"🔥 Streak: {streak} day(s)"
                )

            else:

                reply = "Could not detect study hours"

        except Exception as e:

            print("Image error:", e)

            reply = "Failed to read image"

        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply)]
            )
        )


# ========================
# Run
# ========================

if __name__ == "__main__":
    app.run()