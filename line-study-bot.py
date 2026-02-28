import os
import json
import requests
from datetime import datetime, timedelta

from flask import Flask, request, abort

from linebot.v3.webhook import WebhookHandler

from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    ImageMessageContent
)

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

if not LINE_CHANNEL_ACCESS_TOKEN or not LINE_CHANNEL_SECRET:
    raise Exception("Missing LINE credentials")

configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# =========================
# FLASK APP
# =========================

app = Flask(__name__)

@app.route("/")
def home():
    return "Study bot running"

@app.route("/callback", methods=['POST'])
def callback():

    signature = request.headers.get('X-Line-Signature')

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

    last_date = datetime.strptime(data[user_id]["last_date"], "%Y-%m-%d").date()

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
# TEXT MESSAGE HANDLER
# =========================

@handler.add(MessageEvent, message=TextMessageContent)
def handle_text(event):

    user_id = event.source.user_id
    text = event.message.text.lower()

    if text == "study":

        streak = update_streak(user_id)

        reply = f"📚 Study recorded!\n🔥 Current streak: {streak} days"

    elif text == "streak":

        data = load_data()

        if user_id in data:
            reply = f"🔥 Your streak: {data[user_id]['streak']} days"
        else:
            reply = "No streak yet. Send 'study' to start!"

    else:

        reply = "Send 'study' to record your study streak 📚\nOr send a screenshot."

    with ApiClient(configuration) as api_client:

        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply)]
            )
        )


# =========================
# IMAGE HANDLER WITH OCR
# =========================

@handler.add(MessageEvent, message=ImageMessageContent)
def handle_image(event):

    try:

        message_id = event.message.id
        user_id = event.source.user_id

        # download image from LINE
        with ApiClient(configuration) as api_client:

            blob_api = MessagingApiBlob(api_client)

            content = blob_api.get_message_content(message_id)

            image_data = content.read()

        # send to OCR API
        response = requests.post(
            "https://api.ocr.space/parse/image",
            files={"file": ("image.jpg", image_data)},
            data={
                "apikey": OCR_API_KEY,
                "language": "eng"
            },
        )

        result = response.json()

        extracted_text = ""

        if result.get("ParsedResults"):
            extracted_text = result["ParsedResults"][0]["ParsedText"]

        print("OCR TEXT:", extracted_text)

        # check if contains study indicators
        keywords = ["study", "goodnotes", "classroom", "revision", "notes"]

        if any(word in extracted_text.lower() for word in keywords):

            streak = update_streak(user_id)

            reply = f"📷 Study detected from screenshot!\n🔥 Streak: {streak} days"

        else:

            reply = "📷 Screenshot received, but no study detected."

    except Exception as e:

        print("OCR ERROR:", e)
        reply = "Error reading image."

    with ApiClient(configuration) as api_client:

        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply)]
            )
        )


# =========================
# START SERVER (RENDER)
# =========================

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)