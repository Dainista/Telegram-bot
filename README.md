# SabTradeBot (Rails/Webhook-ready)

This project contains a webhook-ready Telegram bot skeleton for deployment on Railway.

## Quick steps
1. Create a new GitHub repo and upload the contents of this folder.
2. Connect the repo to Railway (New Project -> Deploy from GitHub).
3. In Railway: set variables under **Settings -> Variables**:
   - `TELEGRAM_BOT_TOKEN` (your bot token)
   - `ADMIN_ID` (your Telegram numeric id)
   - (optional) `WEBHOOK_URL` to override default
4. Deploy. Railway will provide a domain like:
   `https://sabtradebot-production.up.railway.app`
   Set `WEBHOOK_URL` to `https://<your-railway-domain>/webhook` if you want to explicitly set it.