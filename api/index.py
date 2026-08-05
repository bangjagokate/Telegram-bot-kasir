import os
from flask import Flask, request
import telebot

TOKEN = os.getenv("BOT_TOKEN", "7614899277:AAGhUBOI3atXqRb2IyHmO45CxC0elgDK16M")
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# Masukkan semua fungsi bot kamu (handle_start, create_pdf_thermal, dll) di sini...

@bot.message_handler(commands=['start'])
def handle_start(message):
    bot.send_message(message.chat.id, "Bot Hanifa Laundry Aktif di Vercel!")

# Route untuk menerima Webhook dari Telegram
@app.route('/', methods=['POST'])
def webhook():
    if request.headers.get('content-type') == 'application/json':
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return ''
    return 'Unauthorized', 403

@app.route('/', methods=['GET'])
def index():
    return "Server Bot Active!"
  
