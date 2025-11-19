
import threading
from flask import Flask
import os
import time
import zipfile
import requests
from telegram import Update, InputFile
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from lottie import import_tgs, export_tgs

app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_flask).start()

def fix_tgs_format(input_path, output_path):
    try:
        anim = import_tgs(input_path)
        export_tgs(anim, output_path)
        return True
    except Exception as e:
        print("Error converting TGS:", e)
        return False

BOT_TOKEN = "YOUR_TOKEN"
bot_username = "MahdiStickerPack_bot"

user_states = {}
temp_dir = "temp"
os.makedirs(temp_dir, exist_ok=True)

def start(update: Update, context: CallbackContext):
    user_id = update.message.chat_id
    user_states[user_id] = {"step": "awaiting_title"}
    update.message.reply_text("✏️ لطفا عنوان پک استیکر را وارد کنید:")

def handle_text(update: Update, context: CallbackContext):
    user_id = update.message.chat_id
    text = update.message.text.strip()
    if user_id not in user_states or user_states[user_id].get("step") != "awaiting_title":
        return
    user_states[user_id]["pack_title"] = text
    user_states[user_id]["step"] = "awaiting_zip"
    update.message.reply_text("📦 حالا فایل ZIP شامل JSONهای استیکر را ارسال کنید.")

def handle_document(update: Update, context: CallbackContext):
    user_id = update.message.chat_id
    if user_id not in user_states or user_states[user_id].get("step") != "awaiting_zip":
        update.message.reply_text("❗ ابتدا عنوان پک را وارد کنید.")
        return

    file = update.message.document
    if not file.file_name.endswith(".zip"):
        update.message.reply_text("❗ لطفا فقط فایل ZIP ارسال کنید.")
        return

    zip_path = os.path.join(temp_dir, f"{user_id}.zip")
    tgs_output_path = os.path.join(temp_dir, f"{user_id}_converted.zip")
    extract_path = os.path.join(temp_dir, str(user_id))
    converted_path = os.path.join(extract_path, "converted")
    os.makedirs(converted_path, exist_ok=True)

    file_obj = file.get_file()
    file_obj.download(zip_path)
    update.message.reply_text("✅ فایل ZIP دریافت شد. در حال ارسال برای تبدیل...")

    with open(zip_path, "rb") as f:
        response = requests.post("https://novinpay.io/lottie/", files={"zipfile": f})

    if response.status_code != 200 or "application/zip" not in response.headers.get("Content-Type", ""):
        update.message.reply_text("❌ خطا در تبدیل فایل‌ها. لطفا دوباره تلاش کنید.")
        return

    with open(tgs_output_path, "wb") as f:
        f.write(response.content)

    with zipfile.ZipFile(tgs_output_path, "r") as zip_ref:
        zip_ref.extractall(converted_path)

    tgs_files = sorted([os.path.join(converted_path, f) for f in os.listdir(converted_path) if f.endswith(".tgs")])
    if not tgs_files:
        update.message.reply_text("❌ هیچ فایل TGS یافت نشد.")
        return

    old_first = tgs_files[0]
    new_first = old_first + "_fixed.tgs"
    fix_tgs_format(old_first, new_first)

    pack_name = f"lottie{int(time.time())}_by_{bot_username}"
    pack_title = user_states[user_id].get("pack_title", "استیکر من")
    emoji = "📅"

    try:
        with open(new_first, "rb") as f:
            first_sticker = InputFile(f, filename="sticker0.tgs")
            context.bot.create_new_sticker_set(
                user_id=user_id,
                name=pack_name,
                title=pack_title,
                tgs_sticker=first_sticker,
                emojis=emoji,
            )
    except Exception:
        update.message.reply_text("❌ خطا در ساخت استیکر اول.")
        return

    for i, path in enumerate(tgs_files[1:], start=1):
        old_tgs = path
        new_tgs = path + "_fixed.tgs"
        ok = fix_tgs_format(old_tgs, new_tgs)
        use_path = new_tgs if ok else old_tgs

        try:
            with open(use_path, "rb") as f:
                sticker = InputFile(f, filename=f"sticker{i}.tgs")
                context.bot.add_sticker_to_set(
                    user_id=user_id,
                    name=pack_name,
                    tgs_sticker=sticker,
                    emojis=emoji,
                )
        except:
            continue

    link = f"https://t.me/addstickers/{pack_name}"
    update.message.reply_text("✅ پک استیکر شما آماده شد.")
    update.message.reply_text(link)

def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))
    dp.add_handler(MessageHandler(Filters.document.zip, handle_document))
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
