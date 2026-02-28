import os
import json
import requests
from datetime import datetime, date

from flask import Flask, request, abort

# LINE SDK v3
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    MessagingApiBlob,
    ReplyMessageRequest,
    TextMessage
)

from linebot.v3.webhook import WebhookHandler

from linebot.v3.webhooks import (
    MessageEvent,
    ImageMessageContent,
    TextMessageContent
)

# =====================
# ENV
# =====================

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
OCR_API_KEY = os.getenv("OCR_API_KEY")

# =====================
# LINE CONFIG
# =====================

configuration = Configuration(access_token=LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# =====================
# APP
# =====================

app = Flask(__name__)

# =====================
# STREAK FILE
# =====================

STREAK_FILE = "streaks.json"


def load_streaks():
    if not os.path.exists(STREAK_FILE):
        return {}

    with open(STREAK_FILE, "r") as f:
        return json.load(f)


def save_streaks(data):
    with open(STREAK_FILE, "w") as f:
        json.dump(data, f)


# =====================
# STREAK SYSTEM
# =====================

def update_streak(user_id):

    streaks = load_streaks()

    today = date.today()

    if user_id not in streaks:

        streaks[user_id] = {
            "streak": 1,
            "last_date": str(today)
        }

        save_streaks(streaks)
        return 1, True


    last_date = datetime.strptime(
        streaks[user_id]["last_date"],
        "%Y-%m-%d"
    ).date()

    diff = (today - last_date).days

    if diff == 0:

        return streaks[user_id]["streak"], False

    elif diff == 1:

        streaks[user_id]["streak"] += 1

    else:

        streaks[user_id]["streak"] = 1


    streaks[user_id]["last_date"] = str(today)

    save_streaks(streaks)

    return streaks[user_id]["streak"], True


# =====================
# OCR
# =====================

def ocr_space_file(image_bytes):

    url = "https://api.ocr.space/parse/image"

    payload = {
        "apikey": OCR_API_KEY,
        "language": "eng"
    }

    files = {
        "file": ("image.jpg", image_bytes)
    }

    response = requests.post(
        url,
        files=files,
        data=payload
    )

    result = response.json()

    if result.get("ParsedResults"):
        return result["ParsedResults"][0]["ParsedText"].strip()

    return ""


# =====================
# ROUTES
# =====================

@app.route("/")
def home():
    return "Study Bot Running 🔥"


@app.route("/callback", methods=["POST"])
def callback():

    signature = request.headers.get("X-Line-Signature")
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except Exception as e:
        print(e)
        abort(400)

    return "OK"


# =====================
# HANDLE IMAGE
# =====================

@handler.add(MessageEvent, message=ImageMessageContent)
def handle_image(event):

    user_id = event.source.user_id

    try:

        with ApiClient(configuration) as api_client:

            blob_api = MessagingApiBlob(api_client)

            image_bytes = blob_api.get_message_content(
                event.message.id
            )


        text = ocr_space_file(image_bytes)

        if text:

            streak, updated = update_streak(user_id)

            reply = (
                "📚 Study detected!\n\n"
                f"🔥 Streak: {streak} days\n\n"
                f"Detected:\n{text[:200]}"
            )

        else:

            reply = "❌ No study text detected."

    except Exception as e:

        print(e)
        reply = "⚠️ OCR Error."


    with ApiClient(configuration) as api_client:

        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply)]
            )
        )


# =====================
# HANDLE TEXT
# =====================

@handler.add(MessageEvent, message=TextMessageContent)
def handle_text(event):

    text = event.message.text.lower()

    if text == "streak":

        streaks = load_streaks()

        user_id = event.source.user_id

        if user_id in streaks:
            streak = streaks[user_id]["streak"]
        else:
            streak = 0

        reply = f"🔥 Your streak: {streak} days"

    else:

        reply = "Send study image to gain streak 🔥"


    with ApiClient(configuration) as api_client:

        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply)]
            )
        )


# =====================
# RUN
# =====================

if __name__ == "__main__":

    port = int(os.environ.get("PORT", 10000))

    app.run(host="0.0.0.0", port=port)