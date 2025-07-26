from flask import Flask
from threading import Thread
from telegram import Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
import os
import zipfile
import uuid

app = Flask(__name__)
user_states = {}
BOT_TOKEN = "7968702741:AAHNrYsxZ-KZs6zBfIMUetifs5ipVaz8jdw"

@app.route("/")
def ping():
    return "I'm alive!"

def start(update: Update, context: CallbackContext):
    update.message.reply_text("سلام! لطفاً فایل ZIP استیکر رو بفرست تا پردازش کنم.")

def help_command(update: Update, context: CallbackContext):
    update.message.reply_text(
        "📌 دستورهای موجود:\n"
        "/start - شروع ساخت استیکر\n"
        "/help - راهنما\n"
        "/about - درباره ربات\n"
        "/cancel - لغو عملیات فعال"
    )

def about_command(update: Update, context: CallbackContext):
    update.message.reply_text(
        "🤖 این ربات برای ساخت پک استیکر تلگرام با فرمت TGS از فایل‌های JSON ساخته شده است.\n"
        "🔹 ساخته شده با ❤️ توسط MahdiStickerPack_bot"
    )

def cancel_command(update: Update, context: CallbackContext):
    user_id = update.message.chat_id
    if user_id in user_states:
        del user_states[user_id]
        update.message.reply_text("❌ عملیات لغو شد.")
    else:
        update.message.reply_text("هیچ عملیات فعالی برای لغو وجود ندارد.")

def handle_document(update: Update, context: CallbackContext):
    document = update.message.document
    if not document.file_name.endswith(".zip"):
        update.message.reply_text("فقط فایل ZIP بفرست لطفاً.")
        return

    file = context.bot.get_file(document.file_id)
    file_id = str(uuid.uuid4())
    download_path = f"/tmp/{file_id}.zip"
    extract_path = f"/tmp/{file_id}"
    os.makedirs(extract_path, exist_ok=True)
    file.download(custom_path=download_path)

    with zipfile.ZipFile(download_path, 'r') as zip_ref:
        zip_ref.extractall(extract_path)

    files = os.listdir(extract_path)
    if not files:
        update.message.reply_text("فایل ZIP خالیه یا مشکلی داشت.")
        return

    result_zip = f"/tmp/sticker_pack_{file_id}.zip"
    with zipfile.ZipFile(result_zip, 'w') as zipf:
        for filename in files:
            zipf.write(os.path.join(extract_path, filename), filename)

    with open(result_zip, 'rb') as f:
        update.message.reply_document(f, filename=f"sticker_pack_{file_id}.zip")

    update.message.reply_text("✅ پک استیکرت آماده‌ست!")

def handle_text(update: Update, context: CallbackContext):
    update.message.reply_text("لطفاً فقط فایل ZIP ارسال کن، نه متن.")

def run_bot():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("help", help_command))
    dp.add_handler(CommandHandler("about", about_command))
    dp.add_handler(CommandHandler("cancel", cancel_command))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))
    dp.add_handler(MessageHandler(Filters.document.mime_type("application/zip"), handle_document))
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    Thread(target=run_bot).start()
    app.run(host="0.0.0.0", port=8080)
