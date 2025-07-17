from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
import pandas as pd
import threading
from flask import Flask
import os

# Dummy HTTP server
app_flask = Flask(__name__)

@app_flask.route('/')
def home():
    return "✅ EdgePay Bot is running!"

def run_flask():
    port = int(os.environ.get('PORT', 10000))
    app_flask.run(host='0.0.0.0', port=port)

# Start Flask in a thread
threading.Thread(target=run_flask).start()

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
    file = await context.bot.get_file(update.message.document.file_id)
    file_bytes = await file.download_as_bytearray()
    df = pd.read_csv(BytesIO(file_bytes))

    # Clean up columns
    df.columns = df.columns.str.strip().str.lower()
    
    if 'status' not in df.columns or 'amount' not in df.columns:
        await update.message.reply_text("❌ The uploaded file must contain 'status' and 'amount' columns.")
        return

    df['amount'] = pd.to_numeric(df['amount'], errors='coerce')
    df = df.dropna(subset=['amount'])

    # Filter
    success_df = df[df['status'].str.lower() == 'success']
    failed_df = df[df['status'].str.lower() == 'failed']
    refunded_df = df[df['status'].str.lower() == 'refunded']

    total_success = len(success_df)
    total_failed = len(failed_df)
    total_refunded = len(refunded_df)

    success_amount = success_df['amount'].sum()
    refunded_amount = refunded_df['amount'].sum()
    chargeable_amount = success_amount - refunded_amount

    # Apply configs
    amounts = success_df['amount'].tolist()

    our = calculate_charges(amounts, our_config)
    castler = calculate_charges(amounts, castler_config)

    our_total = round(our["fixed_total"] + our["percent_total"], 2)
    castler_total = round(castler["fixed_total"] + castler["percent_total"], 2)
    grand_profit = round(our_total - castler_total, 2)

    # Format message
    message = f"""
📊 <b>Transaction Charge Summary</b>:

✅ Successful Transactions: {total_success}
❌ Failed Transactions: {total_failed}
↩️ Refunded Transactions: {total_refunded}

💼 Total Success Amount: ₹{success_amount:,.2f}
↩️ Refunded Amount: ₹{refunded_amount:,.2f}
💳 Chargeable Amount: ₹{chargeable_amount:,.2f}

━━━━━━━━━━━━━━━━━━━━
<b>💼 Our Charges:</b>
💸 ₹100–₹1000: {our['count_fixed_1']} × ₹{our_config['100-1000']} = ₹{our['count_fixed_1'] * our_config['100-1000']:.2f}
💰 >₹1001: ₹{our['amount_percent']:,.2f} × {our_config['>1001']}% = ₹{our['percent_total']:.2f}
<b>Total (Our Charges): ₹{our_total:.2f}</b>

━━━━━━━━━━━━━━━━━━━━
<b>🏦 Castler Charges:</b>
💸 ₹100–₹1000: {castler['count_fixed_1']} × ₹{castler_config['100-1000']} = ₹{castler['count_fixed_1'] * castler_config['100-1000']:.2f}
💸 ₹1001–₹7000: {castler['count_fixed_2']} × ₹{castler_config['1001-7000']} = ₹{castler['count_fixed_2'] * castler_config['1001-7000']:.2f}
💰 >₹7001: ₹{castler['amount_percent']:,.2f} × {castler_config['>7001']}% = ₹{castler['percent_total']:.2f}
<b>Total (Castler Charges): ₹{castler_total:.2f}</b>

━━━━━━━━━━━━━━━━━━━━
💹 <b>Grand Profit</b> = Our Charges − Castler Charges  
🧾 ₹{our_total:.2f} − ₹{castler_total:.2f} = <b>₹{grand_profit:.2f} ✅</b>
"""

    await update.message.reply_text(message, parse_mode="HTML")


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
