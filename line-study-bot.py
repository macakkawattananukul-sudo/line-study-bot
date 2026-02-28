import os
import json
import datetime
import tempfile
import requests
import pytesseract

from flask import Flask, request, abort
from PIL import Image

from linebot.v3.webhook import WebhookHandler
from linebot.v3.messaging import (
    MessagingApi,
    Configuration,
    ApiClient,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import (
    MessageEvent,
    TextMessageContent,
    ImageMessageContent
)

# ====================================
# CONFIG
# ====================================

CHANNEL_ACCESS_TOKEN = os.getenv("CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("CHANNEL_SECRET")

if not CHANNEL_ACCESS_TOKEN or not CHANNEL_SECRET:
    raise Exception("Missing LINE credentials in Render Environment Variables")

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

app = Flask(__name__)

DATA_FILE = "streak.json"

# ====================================
# STREAK FUNCTIONS
# ====================================

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

    today = datetime.date.today()

    if user_id not in data:

        data[user_id] = {
            "streak": 1,
            "last_date": today.isoformat()
        }

    else:

        last_date = datetime.date.fromisoformat(data[user_id]["last_date"])

        if today == last_date:
            pass

        elif today == last_date + datetime.timedelta(days=1):
            data[user_id]["streak"] += 1

        else:
            data[user_id]["streak"] = 1

        data[user_id]["last_date"] = today.isoformat()

    save_data(data)

    return data[user_id]["streak"]

def get_streak(user_id):

    data = load_data()

    if user_id not in data:
        return 0

    return data[user_id]["streak"]

# ====================================
# OCR FUNCTION
# ====================================

def extract_text_from_image(image_path):

    try:

        img = Image.open(image_path)

        text = pytesseract.image_to_string(img)

        return text.strip()

    except:
        return ""

# ====================================
# ROUTES
# ====================================

@app.route("/")
def home():
    return "LINE Study Bot Running"

@app.route("/callback", methods=["POST"])
def callback():

    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK"

# ====================================
# HANDLE TEXT
# ====================================

@handler.add(MessageEvent, message=TextMessageContent)
def handle_text(event):

    user_id = event.source.user_id
    text = event.message.text.lower()

    with ApiClient(configuration) as api_client:

        line_bot_api = MessagingApi(api_client)

        if text == "study":

            streak = update_streak(user_id)

            reply = (
                "✅ Study recorded!\n"
                f"🔥 Current streak: {streak} days"
            )

        elif text == "streak":

            streak = get_streak(user_id)

            reply = f"🔥 Your streak: {streak} days"

        elif text == "hello":

            reply = (
                "Hello!\n\n"
                "Commands:\n"
                "study → record study\n"
                "streak → check streak\n"
                "or send study screenshot"
            )

        else:

            reply = (
                "Commands:\n"
                "study\n"
                "streak"
            )

        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply)]
            )
        )

# ====================================
# HANDLE IMAGE (OCR)
# ====================================

@handler.add(MessageEvent, message=ImageMessageContent)
def handle_image(event):

    user_id = event.source.user_id
    message_id = event.message.id

    headers = {
        "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}"
    }

    url = f"https://api-data.line.me/v2/bot/message/{message_id}/content"

    response = requests.get(url, headers=headers)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as f:

        f.write(response.content)

        temp_path = f.name

    extracted_text = extract_text_from_image(temp_path)

    streak = update_streak(user_id)

    reply = (
        "📷 Study image recorded!\n"
        f"🔥 Current streak: {streak} days\n\n"
        f"OCR detected:\n{extracted_text[:100]}"
    )

    with ApiClient(configuration) as api_client:

        line_bot_api = MessagingApi(api_client)

        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply)]
            )
        )

# ====================================

if __name__ == "__main__":
    app.run()