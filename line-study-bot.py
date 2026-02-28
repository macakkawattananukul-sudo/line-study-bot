import os
import sqlite3
import requests
from datetime import datetime

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

# =========================
# CONFIG
# =========================

CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
OCR_API_KEY = os.getenv("OCR_API_KEY")

if not CHANNEL_ACCESS_TOKEN or not CHANNEL_SECRET:
    print("Missing LINE credentials")
    exit()

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

app = Flask(__name__)

MAX_DAILY_STREAK = 3

# =========================
# DATABASE
# =========================

conn = sqlite3.connect("streak.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,
    streak INTEGER,
    last_date TEXT
)
""")

conn.commit()

# =========================
# STUDY APPS
# =========================

STUDY_APPS = [
    "goodnotes",
    "notability",
    "onenote",
    "collanote",
    "notion",
    "forest",
    "quizlet",
    "duolingo",
    "canvas",
    "moodle",
    "study"
]

# =========================
# OCR USING OCR.SPACE API
# =========================

def extract_text_ocr_space(image_path):

    with open(image_path, 'rb') as f:

        response = requests.post(
            'https://api.ocr.space/parse/image',
            files={'file': f},
            data={
                'apikey': OCR_API_KEY,
                'language': 'eng'
            }
        )

    result = response.json()

    if result["IsErroredOnProcessing"]:
        return ""

    return result["ParsedResults"][0]["ParsedText"].lower()


# =========================
# DETECT HOURS
# =========================

def detect_hours(text):

    total = 0

    lines = text.split("\n")

    for line in lines:

        if any(app in line for app in STUDY_APPS):

            words = line.split()

            for w in words:

                if w.isdigit():
                    total += int(w)
                    break

    return min(total, MAX_DAILY_STREAK)


# =========================
# UPDATE STREAK
# =========================

def update_streak(user_id, hours):

    today = datetime.now().date()

    cursor.execute(
        "SELECT streak, last_date FROM users WHERE user_id=?",
        (user_id,)
    )

    row = cursor.fetchone()

    if row is None:

        cursor.execute(
            "INSERT INTO users VALUES (?, ?, ?)",
            (user_id, hours, today)
        )

        conn.commit()

        return hours

    streak, last_date = row

    last_date = datetime.strptime(last_date, "%Y-%m-%d").date()

    days_missed = (today - last_date).days

    if days_missed >= 1:
        streak = max(streak - 1, 0)

    streak += hours

    cursor.execute(
        "UPDATE users SET streak=?, last_date=? WHERE user_id=?",
        (streak, today, user_id)
    )

    conn.commit()

    return streak


# =========================
# CALLBACK
# =========================

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
# TEXT COMMAND HANDLER
# =========================

@handler.add(MessageEvent, message=TextMessageContent)
def handle_text(event):

    text = event.message.text.lower()

    user_id = event.source.user_id

    if text == "study":

        streak = update_streak(user_id, 1)

        reply = f"🔥 Study +1 streak!\nTotal streak: {streak}"

    else:

        reply = "Send 'study' or upload study screenshot"

    with ApiClient(configuration) as api_client:

        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply)]
            )
        )


# =========================
# IMAGE HANDLER
# =========================

@handler.add(MessageEvent, message=ImageMessageContent)
def handle_image(event):

    user_id = event.source.user_id

    message_id = event.message.id

    with ApiClient(configuration) as api_client:

        image = MessagingApi(api_client).get_message_content(message_id)

        path = f"{user_id}.jpg"

        with open(path, "wb") as f:

            for chunk in image.iter_content():
                f.write(chunk)

    text = extract_text_ocr_space(path)

    hours = detect_hours(text)

    if hours == 0:

        reply = "❌ No study apps detected"

    else:

        streak = update_streak(user_id, hours)

        reply = f"✅ Study detected: {hours} hour(s)\n🔥 Total streak: {streak}"

    with ApiClient(configuration) as api_client:

        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply)]
            )
        )


# =========================
# HOME
# =========================

@app.route("/")
def home():
    return "Study Streak Bot Running"


# =========================
# START
# =========================

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)