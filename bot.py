
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
import pandas as pd

BOT_TOKEN = "8122421723:AAGzgm4MCqnO2q4dA9T9JpwOnxIA0Ve19LU"  # Replace this if needed

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Hi! 👋 Send me an Excel (.xlsx) or CSV file with a column named 'Amount'.\nI'll calculate the total transaction charges based on the rules."
    )

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    file = await update.message.document.get_file()
    file_path = f"{file.file_unique_id}_{update.message.document.file_name}"
    await file.download_to_drive(file_path)

    try:
        if file_path.endswith(".csv"):
            df = pd.read_csv(file_path)
        elif file_path.endswith(".xlsx"):
            df = pd.read_excel(file_path)
        else:
            await update.message.reply_text("Please send a valid .csv or .xlsx file.")
            return

        if "Amount" not in df.columns:
            await update.message.reply_text("The file must contain a column named 'Amount'.")
            return

        charge5 = charge7 = volume = 0
        for amount in df['Amount']:
            try:
                amount = float(amount)
                if 100 <= amount <= 1000:
                    charge5 += 1
                elif 1001 <= amount <= 7000:
                    charge7 += 1
                elif amount > 7000:
                    volume += amount
            except:
                continue

        percent = 1
        total = (charge5 * 5) + (charge7 * 7) + (volume * (percent / 100))

       reply = (
    "📊 *Transaction Charge Summary*\n\n"
    f"💸 ₹5 Slab (₹100–₹1000): `{charge5}` × ₹5 = ₹{charge5 * 5}\n"
    f"💸 ₹7 Slab (₹1001–₹7000): `{charge7}` × ₹7 = ₹{charge7 * 7}\n"
    f"💰 Volume > ₹7000: ₹{volume:,.2f} × 1% = ₹{(volume * percent / 100):,.2f}\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    f"🔢 *Total Charge:* ₹{total:,.2f} ✅"
)
        await update.message.reply_text(reply)
    except Exception as e:
        await update.message.reply_text(f"Error: {str(e)}")

if __name__ == '__main__':
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    print("Bot running...")
    app.run_polling()
