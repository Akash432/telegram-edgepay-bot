Telegram Bot Deployment Guide (Render)

1. Upload all these files to a GitHub repo.
2. Go to https://render.com → New Web Service.
3. Connect your GitHub and select the repo.
4. Build Command: pip install -r requirements.txt
5. Start Command: python bot.py
6. Add Environment Variable (if needed): BOT_TOKEN
7. Click "Create Web Service" to deploy.

OR
Run locally:
pip install -r requirements.txt
python bot.py