# 🤖 Referral Bot — Setup Guide

## ✅ Prerequisites
- Python 3.10+
- A Telegram Bot Token (from @BotFather)
- Your Telegram channel username/ID

---

## ⚙️ Step 1 — Edit Config in bot.py

Open `bot.py` and update the CONFIG section at the top:

```python
BOT_TOKEN      = "123456789:ABCDEFabcdef..."   # From @BotFather
CHANNEL_ID     = "@YourChannelUsername"          # e.g. @mychannel
CHANNEL_LINK   = "https://t.me/YourChannel"
BOT_USERNAME   = "YourBotUsername"               # without @
ADMIN_IDS      = [123456789]                     # Your Telegram user ID
USDT_TO_INR    = 83.50                           # Update this rate as needed
```

To find your Telegram user ID: message @userinfobot on Telegram.

---

## 📦 Step 2 — Install Dependencies

```bash
pip install -r requirements.txt
```

---

## 🚀 Step 3 — Run the Bot

```bash
python bot.py
```

---

## 🛡 Admin Commands

| Command | Description |
|---|---|
| `/approve <user_id>` | Approve a pending withdrawal |
| `/reject <user_id>` | Reject & refund a withdrawal |
| `/astats` | View overall bot statistics |
| `/ban <user_id>` | Ban a user |
| `/broadcast <msg>` | Send message to all users |

---

## 👤 User Commands

| Command | Description |
|---|---|
| `/start` | Start the bot / main menu |
| `/profile` | View your profile & balance |
| `/leaderboard` | Top 10 referrers |
| `/rate` | Current INR/USDT rate |

---

## 💸 Withdrawal Flow

1. User taps **Withdraw** in menu
2. Selects method: UPI / PayPal / USDT BEP-20
3. Sends their address/ID
4. Request saved as **pending**, admin notified
5. Admin runs `/approve <user_id>` or `/reject <user_id>`
6. User notified of result

---

## 🔄 Keeping Rate Updated

Edit `USDT_TO_INR` in `bot.py` periodically, or integrate a live price API like CoinGecko for automatic updates.

---

## 📁 Database

SQLite file: `referral_bot.db` (auto-created on first run)  
Tables: `users`, `referrals`, `withdrawals`

---

## ☁️ Deployment (24/7)

**Option A — VPS (recommended)**
```bash
# Install screen or tmux
screen -S bot
python bot.py
# Ctrl+A, D to detach
```

**Option B — systemd service**
```ini
[Unit]
Description=Referral Bot
After=network.target

[Service]
ExecStart=/usr/bin/python3 /path/to/bot.py
Restart=always

[Install]
WantedBy=multi-user.target
```

**Option C — Railway / Render / Heroku** (free tier available)

---

## ⚠️ Important Notes

- Make your bot an **admin** in the channel (needed to check membership)
- Keep your `BOT_TOKEN` secret — never share it
- Back up `referral_bot.db` regularly
