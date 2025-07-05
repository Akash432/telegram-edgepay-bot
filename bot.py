from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
import pandas as pd

# In-memory storage for user configs
user_settings = {}

def parse_config_lines(lines):
    slabs = []
    for line in lines:
        line = line.strip()
        if '-' in line and '=' in line:
            range_part, rate = line.split('=')
            min_amt, max_amt = map(float, range_part.split('-'))
            slabs.append({'min': min_amt, 'max': max_amt, 'rate': float(rate)})
        elif line.startswith('>') and '%' in line:
            amt = float(line.split('=')[0].replace('>', ''))
            percent = float(line.split('=')[1].replace('%', ''))
            slabs.append({'min': amt, 'max': float('inf'), 'percent': percent})
    return slabs

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        """👋 *Welcome to the EdgePay Bot!*

📌 Upload an Excel or CSV file with your transaction data.

🔧 Before uploading, you can configure:
1. Slabs & charges → `/setconfig`
2. Column name → `/setcolumn <name>`
3. View current config → `/viewconfig`

✅ Example for /setconfig:
`100-1000=5
1001-5000=10
>5000=1%`

Default column is: `Amount`
""",
        parse_mode='Markdown'
    )

async def set_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lines = update.message.text.split('\n')[1:]  # Skip command line
    slabs = parse_config_lines(lines)
    if user_id not in user_settings:
        user_settings[user_id] = {}
    user_settings[user_id]['slabs'] = slabs
    await update.message.reply_text("✅ Slab configuration updated!")

async def set_column(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    parts = update.message.text.split()
    if len(parts) < 2:
        await update.message.reply_text("❌ Usage: /setcolumn <Column Name>")
        return
    column_name = ' '.join(parts[1:])
    if user_id not in user_settings:
        user_settings[user_id] = {}
    user_settings[user_id]['column'] = column_name
    await update.message.reply_text(f"✅ Column name set to: *{column_name}*", parse_mode='Markdown')

async def view_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    config = user_settings.get(user_id, {})
    slabs = config.get('slabs', [])
    column = config.get('column', 'Amount')
    msg = f"""🛠 *Your Current Config:*
📊 Column: `{column}`

💸 Slabs:"""
    for slab in slabs:
        if 'rate' in slab:
            msg += f"\n• ₹{int(slab['min'])}–₹{int(slab['max'])} → ₹{slab['rate']}/txn"
        elif 'percent' in slab:
            msg += f"\n• >₹{int(slab['min'])} → {slab['percent']}% volume"
    await update.message.reply_text(msg, parse_mode='Markdown')

async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    file = await update.message.document.get_file()
    file_path = f"{file.file_unique_id}_{update.message.document.file_name}"
    await file.download_to_drive(file_path)

    config = user_settings.get(user_id, {})
    column_name = config.get('column', 'Amount')
    slabs = config.get('slabs', [
        {'min': 100, 'max': 1000, 'rate': 5},
        {'min': 1001, 'max': 7000, 'rate': 7},
        {'min': 7001, 'max': float('inf'), 'percent': 1}
    ])

    try:
        if file_path.endswith(".csv"):
            df = pd.read_csv(file_path)
        elif file_path.endswith(".xlsx"):
            df = pd.read_excel(file_path)
        else:
            await update.message.reply_text("⚠️ Please send a valid .csv or .xlsx file.")
            return

        if column_name not in df.columns:
            await update.message.reply_text(f"❌ Column '{column_name}' not found in file.")
            return

        charge_total = 0
        detail_lines = []
        total_volume = 0

        for slab in slabs:
            if 'rate' in slab:
                count = df[(df[column_name] >= slab['min']) & (df[column_name] <= slab['max'])].shape[0]
                amount = count * slab['rate']
                charge_total += amount
                detail_lines.append(f"💸 ₹{int(slab['min'])}–₹{int(slab['max'])}: `{count}` × ₹{slab['rate']} = ₹{amount}")
            elif 'percent' in slab:
                volume = df[df[column_name] > slab['min']][column_name].sum()
                amount = volume * (slab['percent'] / 100)
                charge_total += amount
                total_volume += volume
                detail_lines.append(f"💰 >₹{int(slab['min'])}: ₹{volume:,.2f} × {slab['percent']}% = ₹{amount:,.2f}")

        reply = "*📊 Transaction Charge Summary:*\n\n"
        reply += "\n".join(detail_lines)
        reply += f"\n━━━━━━━━━━━━━━━━━━━━\n🔢 *Total Charge:* ₹{charge_total:,.2f} ✅"

        await update.message.reply_text(reply, parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {str(e)}")

if __name__ == '__main__':
    import os
    BOT_TOKEN = os.getenv("BOT_TOKEN", "8122421723:AAGzgm4MCqnO2q4dA9T9JpwOnxIA0Ve19LU")
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setconfig", set_config))
    app.add_handler(CommandHandler("setcolumn", set_column))
    app.add_handler(CommandHandler("viewconfig", view_config))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))
    print("Bot is running...")
    app.run_polling()
