import threading
from flask import Flask
import os
import time
import zipfile
import requests
from telegram import Update, InputFile
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
)
import shutil
import logging

# Flask server for Render health check
app = Flask(__name__)

@app.route("/")
def home():
    return "Bot is running!", 200

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

# Start Flask in background
threading.Thread(target=run_flask, daemon=True).start()

# Bot configuration
BOT_TOKEN = os.environ.get("BOT_TOKEN", "7506306835:AAFro1xS-iq3UKBbBZHefeSdo1DxcNKJAUg")
bot_username = "MahdiStickerPack_bot"
user_states = {}
temp_dir = "temp"
os.makedirs(temp_dir, exist_ok=True)

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command handler"""
    user_id = update.message.chat_id
    user_states[user_id] = {"step": "awaiting_title"}
    await update.message.reply_text("✏️ لطفا عنوان پک استیکر را وارد کنید:")

async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text input for pack title"""
    user_id = update.message.chat_id
    text = update.message.text.strip()
    
    if user_id not in user_states or user_states[user_id].get("step") != "awaiting_title":
        return
    
    user_states[user_id]["pack_title"] = text
    user_states[user_id]["step"] = "awaiting_zip"
    await update.message.reply_text("📦 حالا فایل ZIP شامل JSONهای استیکر را ارسال کنید.")

async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle ZIP document upload"""
    user_id = update.message.chat_id
    
    if user_id not in user_states or user_states[user_id].get("step") != "awaiting_zip":
        await update.message.reply_text("❗ ابتدا عنوان پک را وارد کنید.")
        return
    
    file = update.message.document
    if not file.file_name.endswith(".zip"):
        await update.message.reply_text("❗ لطفا فقط فایل ZIP ارسال کنید.")
        return
    
    zip_path = os.path.join(temp_dir, f"{user_id}.zip")
    tgs_output_path = os.path.join(temp_dir, f"{user_id}_converted.zip")
    extract_path = os.path.join(temp_dir, str(user_id))
    converted_path = os.path.join(extract_path, "converted")
    os.makedirs(converted_path, exist_ok=True)
    
    try:
        # Download file
        file_obj = await file.get_file()
        await file_obj.download_to_drive(zip_path)
        
        await update.message.reply_text("✅ فایل ZIP دریافت شد. در حال ارسال برای تبدیل...")
        
        # Send to LOCAL Lottie Converter API (instead of novinpay)
        with open(zip_path, "rb") as f:
            response = requests.post(
                "http://localhost:5001/lottie/", 
                files={"zipfile": f}, 
                timeout=120
            )
        
        if response.status_code != 200 or "application/zip" not in response.headers.get("Content-Type", ""):
            logger.error(f"API Error: {response.status_code} - {response.text}")
            await update.message.reply_text("❌ خطا در تبدیل فایلها. لطفا دوباره تلاش کنید.")
            return
        
        # Save converted ZIP
        with open(tgs_output_path, "wb") as f:
            f.write(response.content)
        
        # Extract TGS files
        with zipfile.ZipFile(tgs_output_path, "r") as zip_ref:
            zip_ref.extractall(converted_path)
        
        tgs_files = sorted([
            os.path.join(converted_path, f) 
            for f in os.listdir(converted_path) 
            if f.endswith(".tgs")
        ])
        
        if not tgs_files:
            await update.message.reply_text("❌ هیچ فایل TGS یافت نشد.")
            return
        
        # Create sticker pack
        pack_name = f"lottie{int(time.time())}_by_{bot_username}"
        pack_title = user_states[user_id].get("pack_title", "استیکر من")
        emoji = "📅"
        
        # First sticker - create new set
        try:
            with open(tgs_files[0], "rb") as f:
                first_sticker = InputFile(f, filename="sticker0.tgs")
                await context.bot.create_new_sticker_set(
                    user_id=user_id,
                    name=pack_name,
                    title=pack_title,
                    tgs_sticker=first_sticker,
                    emojis=emoji,
                )
                logger.info(f"Created new sticker pack: {pack_name}")
        except Exception as e:
            logger.error(f"Error creating first sticker: {str(e)}")
            await update.message.reply_text("❌ خطا در ساخت استیکر اول.")
            return
        
        # Add remaining stickers with progress bar
        total = len(tgs_files)
        success_count = 1  # First sticker already added
        failed_stickers = []
        
        progress_msg = await context.bot.send_message(chat_id=user_id, text="⬜⬜⬜⬜⬜⬜⬜⬜ 0%")
        
        for i, path in enumerate(tgs_files[1:], start=1):
            try:
                # Update progress
                done = i + 1
                percent = int((done / total) * 100)
                full_slots = 8
                filled_slots = int((percent / 100) * full_slots)
                bar = "🟩" * filled_slots + "⬜" * (full_slots - filled_slots)
                
                await context.bot.edit_message_text(
                    chat_id=user_id,
                    message_id=progress_msg.message_id,
                    text=f"{bar} {percent}%"
                )
                
                # Add sticker
                with open(path, "rb") as f:
                    sticker = InputFile(f, filename=f"sticker{i}.tgs")
                    await context.bot.add_sticker_to_set(
                        user_id=user_id,
                        name=pack_name,
                        tgs_sticker=sticker,
                        emojis=emoji,
                    )
                success_count += 1
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f"Failed to add sticker {i}: {error_msg}")
                failed_stickers.append(f"sticker{i}: {error_msg}")
                continue
        
        # Final result
        link = f"https://t.me/addstickers/{pack_name}"
        result_msg = f"✅ پک استیکر شما آماده شد!

📊 آمار:
• کل استیکرها: {total}
• موفق: {success_count}
• ناموفق: {len(failed_stickers)}"
        
        await update.message.reply_text(result_msg)
        await update.message.reply_text(link)
        
        if failed_stickers:
            await update.message.reply_text(f"⚠️ استیکرهای ناموفق:
" + "
".join(failed_stickers[:5]))
        
        # Cleanup
        try:
            shutil.rmtree(converted_path)
            os.remove(zip_path)
            os.remove(tgs_output_path)
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
        
        user_states.pop(user_id, None)
        
    except Exception as e:
        logger.error(f"Document handler error: {str(e)}")
        await update.message.reply_text("❌ خطای غیرمنتظره. لطفا دوباره تلاش کنید.")
        # Cleanup on error
        try:
            if os.path.exists(zip_path):
                os.remove(zip_path)
            if os.path.exists(tgs_output_path):
                os.remove(tgs_output_path)
        except:
            pass

def main():
    """Main bot function"""
    application = (
        ApplicationBuilder()
        .token(BOT_TOKEN)
        .build()
    )
    
    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.Document.FILE_EXTENSION("zip"), handle_document))
    
    logger.info("Starting sticker bot...")
    application.run_polling()

if __name__ == "__main__":
    # Start Lottie Converter API in background
    try:
        from lottie_converter import app as converter_app
        threading.Thread(
            target=lambda: converter_app.run(host='0.0.0.0', port=5001, debug=False),
            daemon=True
        ).start()
        time.sleep(3)  # Give API time to start
        logger.info("Lottie Converter API started on port 5001")
    except ImportError:
        logger.warning("lottie_converter not found - using external API")
    
    main()