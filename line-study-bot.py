from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage, ImageMessage
from linebot.exceptions import InvalidSignatureError

from datetime import datetime
import sqlite3
import pytesseract
from PIL import Image
import requests
import os

# ========================
# CONFIG
# ========================

LINE_CHANNEL_ACCESS_TOKEN = "gLu4qNbaDvdsk3Nz9ZUvsnkGAN8TClRHISpHVU8V9DCpgMa0THfI+f1FYhGbOYGhyixjcYe+sySlKMGzYIU2X947sJ1CSO+1oJHgUJjj3VFa+5d+tay4465pvGxS+dVGXDP5maymdAyVEhvnYVQiFQdB04t89/1O/w1cDnyilFU="
LINE_CHANNEL_SECRET = "10e34695e0d031f358ac1b6caeb1e118"

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

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

    today = datetime.now().date()

    conn = sqlite3.connect("streak.db")
    c = conn.cursor()

    c.execute("SELECT streak, last_date FROM users WHERE user_id=?",
              (user_id,))
    result = c.fetchone()

    if result is None:
        streak = 1
        c.execute("INSERT INTO users VALUES (?, ?, ?)",
                  (user_id, streak, str(today)))

    else:
        streak, last_date = result
        last_date = datetime.strptime(last_date, "%Y-%m-%d").date()

        if (today - last_date).days == 1:
            streak += 1
        elif (today - last_date).days == 0:
            pass
        else:
            streak = 1

        c.execute("UPDATE users SET streak=?, last_date=? WHERE user_id=?",
                  (streak, str(today), user_id))

    conn.commit()
    conn.close()

    return streak

# ========================
# OCR FUNCTION
# ========================

def extract_text(image_url):

    response = requests.get(image_url)

    with open("temp.jpg", "wb") as f:
        f.write(response.content)

    img = Image.open("temp.jpg")

    text = pytesseract.image_to_string(img)

    return text.lower()

# ========================
# WEBHOOK
# ========================

@app.route("/callback", methods=['POST'])
def callback():

    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

# ========================
# HANDLE TEXT
# ========================

@handler.add(MessageEvent, message=TextMessage)
def handle_text(event):

    if event.message.text.lower() == "streak":

        conn = sqlite3.connect("streak.db")
        c = conn.cursor()

        c.execute("SELECT streak FROM users WHERE user_id=?",
                  (event.source.user_id,))
        result = c.fetchone()

        if result:
            streak = result[0]
        else:
            streak = 0

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(f"🔥 Your streak: {streak} days")
        )

# ========================
# HANDLE IMAGE
# ========================

@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):

    message_content = line_bot_api.get_message_content(
        event.message.id
    )

    with open("temp.jpg", "wb") as f:
        for chunk in message_content.iter_content():
            f.write(chunk)

    text = extract_text("temp.jpg")

    keywords = ["forest", "kindle", "books", "reading"]

    if any(word in text for word in keywords):

        streak = update_streak(event.source.user_id)

        reply = f"✅ Study verified!\n🔥 Streak: {streak}"

    else:

        reply = "❌ Could not verify study app"

    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(reply)
    )

# ========================
# RUN
# ========================

if __name__ == "__main__":
    app.run(port=5000)