import os
import sqlite3
import datetime
from flask import Flask, request, abort

from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent, ImageMessageContent

# OCR
import pytesseract
from PIL import Image
import requests
from io import BytesIO

# ========================
# CONFIG
# ========================

CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

app = Flask(__name__)

# ========================
# DATABASE
# ========================

def init_db():
    conn = sqlite3.connect("streak.db")
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            streak INTEGER,
            last_date TEXT
        )
    """)
    conn.commit()
    conn.close()

init_db()

# ========================
# STREAK FUNCTION
# ========================

def update_streak(user_id):
    conn = sqlite3.connect("streak.db")
    c = conn.cursor()

    today = str(datetime.date.today())

    c.execute("SELECT streak, last_date FROM users WHERE user_id=?", (user_id,))
    result = c.fetchone()

    if result is None:
        streak = 1
        c.execute("INSERT INTO users VALUES (?, ?, ?)", (user_id, streak, today))

    else:
        streak, last_date = result

        last_date_obj = datetime.date.fromisoformat(last_date)
        today_obj = datetime.date.fromisoformat(today)

        if today_obj == last_date_obj:
            pass

        elif today_obj == last_date_obj + datetime.timedelta(days=1):
            streak += 1

        else:
            streak = 1

        c.execute(
            "UPDATE users SET streak=?, last_date=? WHERE user_id=?",
            (streak, today, user_id)
        )

    conn.commit()
    conn.close()

    return streak

# ========================
# CALLBACK
# ========================

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature')
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except Exception as e:
        print("Error:", e)
        abort(400)

    return 'OK'


# ========================
# TEXT MESSAGE
# ========================

@handler.add(MessageEvent, message=TextMessageContent)
def handle_text(event):

    user_id = event.source.user_id
    text = event.message.text.lower()

    if text == "study":
        streak = update_streak(user_id)

        reply = f"🔥 Study streak: {streak} days!"

    else:
        reply = "Send study or upload study screenshot 📚"

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)

        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply)]
            )
        )

# ========================
# IMAGE MESSAGE (OCR)
# ========================

@handler.add(MessageEvent, message=ImageMessageContent)
def handle_image(event):

    user_id = event.source.user_id

    try:
        message_id = event.message.id

        url = f"https://api-data.line.me/v2/bot/message/{message_id}/content"

        headers = {
            "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}"
        }

        response = requests.get(url, headers=headers)

        image = Image.open(BytesIO(response.content))

        text = pytesseract.image_to_string(image)

        print("OCR TEXT:", text)

        if len(text.strip()) > 5:
            streak = update_streak(user_id)

            reply = f"📸 Study detected!\n🔥 Streak: {streak} days"
        else:
            reply = "❌ No study detected in image"

    except Exception as e:
        print("OCR Error:", e)
        reply = "OCR failed"

    with ApiClient(configuration) as api_client:
        line_bot_api = MessagingApi(api_client)

        line_bot_api.reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply)]
            )
        )


# ========================
# ROOT
# ========================

@app.route("/")
def home():
    return "Bot is running"