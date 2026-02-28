import os
import sqlite3
import cv2
import pytesseract
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
from linebot.v3.webhooks import MessageEvent, ImageMessageContent


# =========================
# CONFIG
# =========================

CHANNEL_ACCESS_TOKEN = os.getenv("gLu4qNbaDvdsk3Nz9ZUvsnkGAN8TClRHISpHVU8V9DCpgMa0THfI+f1FYhGbOYGhyixjcYe+sySlKMGzYIU2X947sJ1CSO+1oJHgUJjj3VFa+5d+tay4465pvGxS+dVGXDP5maymdAyVEhvnYVQiFQdB04t89/1O/w1cDnyilFU=")
CHANNEL_SECRET = os.getenv("10e34695e0d031f358ac1b6caeb1e118")

if not CHANNEL_ACCESS_TOKEN or not CHANNEL_SECRET:
    print("Missing LINE credentials")
    exit()

configuration = Configuration(access_token=CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)

app = Flask(__name__)

# Render Tesseract path
pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"

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

    # International
    "goodnotes", "notability", "onenote", "notion",
    "forest", "focus", "study", "quizlet", "canvas",
    "moodle", "teams", "zoom", "google classroom",

    # Thai apps
    "dek-d", "trueplookpanya", "thai mooc",
    "khan academy", "edpuzzle"
]


# =========================
# OCR FUNCTIONS
# =========================

def extract_text(image_path):

    img = cv2.imread(image_path)

    if img is None:
        return ""

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    text = pytesseract.image_to_string(gray)

    return text.lower()


def detect_hours(text):

    total = 0

    lines = text.split("\n")

    for line in lines:

        if any(app in line for app in STUDY_APPS):

            words = line.split()

            for word in words:
                if word.isdigit():
                    total += int(word)
                    break

    return min(total, MAX_DAILY_STREAK)


# =========================
# STREAK LOGIC
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
            (user_id, hours, str(today))
        )

        conn.commit()

        return hours


    streak, last_date = row

    last_date = datetime.strptime(last_date, "%Y-%m-%d").date()

    days_missed = (today - last_date).days


    # decrease by 1 if missed day
    if days_missed >= 1:
        streak = max(streak - 1, 0)


    streak += hours

    cursor.execute(
        "UPDATE users SET streak=?, last_date=? WHERE user_id=?",
        (streak, str(today), user_id)
    )

    conn.commit()

    return streak


# =========================
# IMPORTANT ROUTES
# =========================

@app.route("/", methods=["GET"])
def home():
    return "LINE Study Bot is running", 200


@app.route("/callback", methods=["POST"])
def webhook():

    signature = request.headers.get("X-Line-Signature")

    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)

    except Exception as e:
        print("Webhook error:", e)
        abort(400)

    return "OK", 200


# =========================
# IMAGE HANDLER
# =========================

@handler.add(MessageEvent, message=ImageMessageContent)
def handle_image(event):

    user_id = event.source.user_id
    message_id = event.message.id

    image_path = f"{user_id}.jpg"


    # download image
    headers = {
        "Authorization": f"Bearer {CHANNEL_ACCESS_TOKEN}"
    }

    url = f"https://api-data.line.me/v2/bot/message/{message_id}/content"

    response = requests.get(url, headers=headers)

    with open(image_path, "wb") as f:
        f.write(response.content)


    text = extract_text(image_path)

    hours = detect_hours(text)


    if hours == 0:

        reply = "❌ No study apps detected"

    else:

        streak = update_streak(user_id, hours)

        reply = f"""
✅ Study detected: {hours} hour(s)
🔥 Total streak: {streak}
"""


    with ApiClient(configuration) as api_client:

        MessagingApi(api_client).reply_message(
            ReplyMessageRequest(
                reply_token=event.reply_token,
                messages=[TextMessage(text=reply)]
            )
        )


# =========================
# START SERVER (CRITICAL FOR RENDER)
# =========================

if __name__ == "__main__":

    port = int(os.environ.get("PORT", 10000))

    app.run(host="0.0.0.0", port=port)