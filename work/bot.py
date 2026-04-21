import os
import sqlite3
import hashlib
import datetime
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ChatMemberUpdated
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)
from telegram.constants import ParseMode

# ─────────────────────────────────────────────
#  CONFIG  (edit these)
# ─────────────────────────────────────────────
BOT_TOKEN        = "8740751389:AAFaWHph6u8R1ofj5-d-9SDKuzHAlSWCiHI"
CHANNEL_ID       = "@allinonecreator12"   # e.g. @mychannel or -100xxxxxxxxxx
CHANNEL_LINK     = "https://t.me/allinonecreator12"
BOT_USERNAME     = "@gmail_creato_rbot"        # without @
ADMIN_IDS        = 5655294767             # your Telegram user ID(s)

REFERRAL_REWARD_INR  = 5.00                # ₹ per referral
USDT_TO_INR          = 83.50              # approx rate (update as needed)
MIN_WITHDRAW_INR     = 200.00
DB_PATH              = "referral_bot.db"

# Conversation states
WITHDRAW_METHOD, WITHDRAW_ADDRESS, WITHDRAW_CONFIRM = range(3)

# ─────────────────────────────────────────────
#  DATABASE
# ─────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            user_id     INTEGER PRIMARY KEY,
            username    TEXT,
            full_name   TEXT,
            referred_by INTEGER,
            balance_inr REAL DEFAULT 0.0,
            total_refs  INTEGER DEFAULT 0,
            joined_at   TEXT DEFAULT (datetime('now')),
            is_banned   INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS withdrawals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER,
            amount_inr  REAL,
            amount_usdt REAL,
            method      TEXT,
            address     TEXT,
            status      TEXT DEFAULT 'pending',
            requested_at TEXT DEFAULT (datetime('now')),
            processed_at TEXT
        );
        CREATE TABLE IF NOT EXISTS referrals (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            referrer_id INTEGER,
            referee_id  INTEGER,
            reward_inr  REAL,
            earned_at   TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return user

def create_user(user_id, username, full_name, referred_by=None):
    conn = get_db()
    conn.execute(
        "INSERT OR IGNORE INTO users (user_id, username, full_name, referred_by) VALUES (?,?,?,?)",
        (user_id, username, full_name, referred_by)
    )
    conn.commit()
    conn.close()

def add_balance(user_id, amount_inr):
    conn = get_db()
    conn.execute("UPDATE users SET balance_inr = balance_inr + ? WHERE user_id=?", (amount_inr, user_id))
    conn.commit()
    conn.close()

def increment_refs(user_id):
    conn = get_db()
    conn.execute("UPDATE users SET total_refs = total_refs + 1 WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()

def inr_to_usdt(inr):
    return round(inr / USDT_TO_INR, 4)

def get_referral_link(user_id):
    return f"https://t.me/{BOT_USERNAME}?start=ref{user_id}"

# ─────────────────────────────────────────────
#  CHANNEL CHECK
# ─────────────────────────────────────────────
async def is_member(bot, user_id):
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception:
        return False

# ─────────────────────────────────────────────
#  KEYBOARDS
# ─────────────────────────────────────────────
def main_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 My Balance",    callback_data="balance"),
         InlineKeyboardButton("👥 Referrals",     callback_data="referrals")],
        [InlineKeyboardButton("💸 Withdraw",      callback_data="withdraw"),
         InlineKeyboardButton("🔗 My Ref Link",   callback_data="reflink")],
        [InlineKeyboardButton("📊 Stats",         callback_data="stats"),
         InlineKeyboardButton("ℹ️ How It Works",  callback_data="howto")],
        [InlineKeyboardButton("📋 My History",    callback_data="history"),
         InlineKeyboardButton("🆘 Support",       callback_data="support")],
    ])

def back_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("« Back to Menu", callback_data="menu")]])

def withdraw_method_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏦 UPI",          callback_data="w_upi")],
        [InlineKeyboardButton("🅿️ PayPal",       callback_data="w_paypal")],
        [InlineKeyboardButton("💎 USDT BEP-20",  callback_data="w_usdt")],
        [InlineKeyboardButton("« Cancel",        callback_data="menu")],
    ])

# ─────────────────────────────────────────────
#  WELCOME / START
# ─────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = ctx.args

    # Channel membership gate
    if not await is_member(ctx.bot, user.id):
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK),
            InlineKeyboardButton("✅ I Joined", callback_data=f"check_join_{'_'.join(args) if args else ''}"),
        ]])
        await update.message.reply_text(
            "╔══════════════════════════╗\n"
            "║  🔐  *Access Required*    ║\n"
            "╚══════════════════════════╝\n\n"
            "To use this bot you must join our official channel first.\n\n"
            f"👇 Tap below, join, then press *I Joined*.",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb
        )
        return

    await _register_and_welcome(update, ctx, user, args)

async def _register_and_welcome(update, ctx, user, args):
    existing = get_user(user.id)
    referred_by = None

    if not existing:
        # Parse referral
        if args and args[0].startswith("ref"):
            try:
                ref_id = int(args[0][3:])
                if ref_id != user.id and get_user(ref_id):
                    referred_by = ref_id
            except ValueError:
                pass

        create_user(user.id, user.username, user.full_name, referred_by)

        # Credit referrer
        if referred_by:
            add_balance(referred_by, REFERRAL_REWARD_INR)
            increment_refs(referred_by)
            conn = get_db()
            conn.execute(
                "INSERT INTO referrals (referrer_id, referee_id, reward_inr) VALUES (?,?,?)",
                (referred_by, user.id, REFERRAL_REWARD_INR)
            )
            conn.commit()
            conn.close()
            try:
                await ctx.bot.send_message(
                    referred_by,
                    f"🎉 *New Referral!*\n\n"
                    f"*{user.full_name}* joined using your link!\n"
                    f"💰 *+₹{REFERRAL_REWARD_INR:.2f}* added to your balance.",
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception:
                pass

    db_user = get_user(user.id)
    usdt_bal = inr_to_usdt(db_user["balance_inr"])

    welcome = (
        f"╔══════════════════════════════╗\n"
        f"║   💎  *REFERRAL REWARDS BOT*   ║\n"
        f"╚══════════════════════════════╝\n\n"
        f"Welcome back, *{user.first_name}*! 👋\n\n"
        f"┌─────────────────────────┐\n"
        f"│  💵 Balance: *₹{db_user['balance_inr']:.2f}*\n"
        f"│  🔶 USDT:    *${usdt_bal}*\n"
        f"│  👥 Referrals: *{db_user['total_refs']}*\n"
        f"└─────────────────────────┘\n\n"
        f"📌 Earn *₹{REFERRAL_REWARD_INR:.0f}* for every friend you refer!\n"
        f"💸 Min withdrawal: *₹{MIN_WITHDRAW_INR:.0f}*\n\n"
        f"Choose an option below 👇"
    )

    msg = update.message or update.callback_query.message
    if update.message:
        await update.message.reply_text(welcome, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_kb())
    else:
        await update.callback_query.edit_message_text(welcome, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_kb())

# ─────────────────────────────────────────────
#  CHECK JOIN CALLBACK
# ─────────────────────────────────────────────
async def check_join_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = update.effective_user

    if not await is_member(ctx.bot, user.id):
        await query.answer("❌ You haven't joined yet! Please join first.", show_alert=True)
        return

    data = query.data  # "check_join_ref12345" or "check_join_"
    args = []
    suffix = data[len("check_join_"):]
    if suffix:
        args = [suffix]

    await _register_and_welcome(update, ctx, user, args)

# ─────────────────────────────────────────────
#  BUTTON CALLBACKS
# ─────────────────────────────────────────────
async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user_id = update.effective_user.id
    db_user = get_user(user_id)

    if not db_user:
        await query.edit_message_text("Please /start the bot first.")
        return

    # ── MENU ──
    if data == "menu":
        usdt_bal = inr_to_usdt(db_user["balance_inr"])
        text = (
            f"╔══════════════════════════════╗\n"
            f"║   💎  *REFERRAL REWARDS BOT*   ║\n"
            f"╚══════════════════════════════╝\n\n"
            f"Welcome, *{update.effective_user.first_name}*! 👋\n\n"
            f"┌─────────────────────────┐\n"
            f"│  💵 Balance: *₹{db_user['balance_inr']:.2f}*\n"
            f"│  🔶 USDT:    *${usdt_bal}*\n"
            f"│  👥 Referrals: *{db_user['total_refs']}*\n"
            f"└─────────────────────────┘\n\n"
            f"Choose an option below 👇"
        )
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_kb())

    # ── BALANCE ──
    elif data == "balance":
        inr = db_user["balance_inr"]
        usdt = inr_to_usdt(inr)
        text = (
            f"💰 *Your Balance*\n\n"
            f"┌──────────────────────────┐\n"
            f"│  🇮🇳 INR:  *₹{inr:.2f}*\n"
            f"│  🔶 USDT: *${usdt}*\n"
            f"│  👥 Refs:  *{db_user['total_refs']}*\n"
            f"└──────────────────────────┘\n\n"
            f"💡 Rate: ₹1 = ${1/USDT_TO_INR:.5f} USDT\n"
            f"📌 Min Withdrawal: *₹{MIN_WITHDRAW_INR:.0f}*\n"
            f"{'✅ Ready to withdraw!' if inr >= MIN_WITHDRAW_INR else f'⚠️ Need ₹{MIN_WITHDRAW_INR - inr:.2f} more to withdraw'}"
        )
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb())

    # ── REFERRALS ──
    elif data == "referrals":
        conn = get_db()
        refs = conn.execute(
            "SELECT u.full_name, r.reward_inr, r.earned_at FROM referrals r "
            "JOIN users u ON u.user_id=r.referee_id WHERE r.referrer_id=? ORDER BY r.earned_at DESC LIMIT 10",
            (user_id,)
        ).fetchall()
        conn.close()

        link = get_referral_link(user_id)
        ref_list = ""
        for r in refs:
            dt = r["earned_at"][:10]
            ref_list += f"  • {r['full_name']} — *+₹{r['reward_inr']:.2f}* ({dt})\n"

        text = (
            f"👥 *Your Referrals*\n\n"
            f"Total: *{db_user['total_refs']}* referrals\n"
            f"Earned: *₹{db_user['balance_inr']:.2f}*\n\n"
            f"🔗 Your link:\n`{link}`\n\n"
            + (f"📋 *Recent Referrals:*\n{ref_list}" if refs else "No referrals yet. Share your link!")
        )
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb())

    # ── REF LINK ──
    elif data == "reflink":
        link = get_referral_link(user_id)
        text = (
            f"🔗 *Your Referral Link*\n\n"
            f"`{link}`\n\n"
            f"📤 Share this link with friends!\n"
            f"💰 Earn *₹{REFERRAL_REWARD_INR:.0f}* for every friend who joins.\n\n"
            f"📊 You've referred *{db_user['total_refs']}* people so far!"
        )
        share_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 Share Link", url=f"https://t.me/share/url?url={link}&text=Join+and+earn+rewards!")],
            [InlineKeyboardButton("« Back to Menu", callback_data="menu")]
        ])
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=share_kb)

    # ── STATS ──
    elif data == "stats":
        conn = get_db()
        total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        total_refs   = conn.execute("SELECT COUNT(*) FROM referrals").fetchone()[0]
        total_paid   = conn.execute("SELECT COALESCE(SUM(amount_inr),0) FROM withdrawals WHERE status='approved'").fetchone()[0]
        conn.close()
        text = (
            f"📊 *Bot Statistics*\n\n"
            f"┌─────────────────────────┐\n"
            f"│  👤 Total Users:  *{total_users}*\n"
            f"│  🔗 Total Refs:   *{total_refs}*\n"
            f"│  💸 Total Paid:   *₹{total_paid:.2f}*\n"
            f"│  💱 Rate:         *₹{USDT_TO_INR}/USDT*\n"
            f"└─────────────────────────┘"
        )
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb())

    # ── HOW IT WORKS ──
    elif data == "howto":
        text = (
            f"ℹ️ *How It Works*\n\n"
            f"1️⃣ *Get Your Link* — Tap 🔗 My Ref Link\n"
            f"2️⃣ *Share It* — Send to friends, post on social media\n"
            f"3️⃣ *Earn* — Get *₹{REFERRAL_REWARD_INR:.0f}* every time someone joins using your link\n"
            f"4️⃣ *Withdraw* — Once you reach *₹{MIN_WITHDRAW_INR:.0f}*, withdraw via:\n"
            f"   • 🏦 UPI\n   • 🅿️ PayPal\n   • 💎 USDT BEP-20\n\n"
            f"💡 *Conversion:* ₹{USDT_TO_INR} = 1 USDT\n"
            f"⚡ Withdrawals processed within 24–48 hours."
        )
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb())

    # ── HISTORY ──
    elif data == "history":
        conn = get_db()
        rows = conn.execute(
            "SELECT method, amount_inr, amount_usdt, status, requested_at FROM withdrawals "
            "WHERE user_id=? ORDER BY requested_at DESC LIMIT 10",
            (user_id,)
        ).fetchall()
        conn.close()
        if not rows:
            text = "📋 *Withdrawal History*\n\nNo withdrawals yet."
        else:
            lines = ""
            for r in rows:
                emoji = {"pending": "⏳", "approved": "✅", "rejected": "❌"}.get(r["status"], "•")
                lines += f"{emoji} *{r['method'].upper()}* — ₹{r['amount_inr']:.2f} ({r['status']}) — {r['requested_at'][:10]}\n"
            text = f"📋 *Withdrawal History*\n\n{lines}"
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb())

    # ── SUPPORT ──
    elif data == "support":
        text = (
            f"🆘 *Support*\n\n"
            f"Need help? Contact our admin:\n"
            f"📩 @AdminUsername\n\n"
            f"Common issues:\n"
            f"• Withdrawal not received → wait 24–48h\n"
            f"• Referral not credited → ensure friend joined via your link\n"
            f"• Wrong payment address → contact admin immediately"
        )
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb())

    # ── WITHDRAW ──
    elif data == "withdraw":
        inr = db_user["balance_inr"]
        if inr < MIN_WITHDRAW_INR:
            text = (
                f"💸 *Withdraw*\n\n"
                f"❌ Insufficient balance!\n\n"
                f"Your balance: *₹{inr:.2f}*\n"
                f"Minimum required: *₹{MIN_WITHDRAW_INR:.0f}*\n"
                f"Need *₹{MIN_WITHDRAW_INR - inr:.2f}* more.\n\n"
                f"Keep referring to earn more! 🔗"
            )
            await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb())
        else:
            usdt = inr_to_usdt(inr)
            text = (
                f"💸 *Withdraw Funds*\n\n"
                f"Available: *₹{inr:.2f}* (${usdt} USDT)\n\n"
                f"Choose your withdrawal method:"
            )
            await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=withdraw_method_kb())

    # ── WITHDRAW METHOD CHOSEN ──
    elif data in ("w_upi", "w_paypal", "w_usdt"):
        method_map = {"w_upi": "UPI", "w_paypal": "PayPal", "w_usdt": "USDT BEP-20"}
        addr_map   = {"w_upi": "your UPI ID (e.g. name@upi)", "w_paypal": "your PayPal email", "w_usdt": "your BEP-20 wallet address"}
        method = method_map[data]
        ctx.user_data["withdraw_method"] = method
        text = (
            f"💸 *Withdraw via {method}*\n\n"
            f"Please send me {addr_map[data]}.\n\n"
            f"⚠️ Double-check your address before sending!"
        )
        cancel_kb = InlineKeyboardMarkup([[InlineKeyboardButton("« Cancel", callback_data="menu")]])
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=cancel_kb)
        ctx.user_data["awaiting_withdraw_addr"] = True

# ─────────────────────────────────────────────
#  WITHDRAW ADDRESS INPUT
# ─────────────────────────────────────────────
async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db_user = get_user(user_id)
    if not db_user:
        return

    if ctx.user_data.get("awaiting_withdraw_addr"):
        address = update.message.text.strip()
        method  = ctx.user_data.get("withdraw_method", "Unknown")
        inr     = db_user["balance_inr"]
        usdt    = inr_to_usdt(inr)

        # Save withdrawal request
        conn = get_db()
        conn.execute(
            "INSERT INTO withdrawals (user_id, amount_inr, amount_usdt, method, address) VALUES (?,?,?,?,?)",
            (user_id, inr, usdt, method, address)
        )
        # Deduct balance
        conn.execute("UPDATE users SET balance_inr=0 WHERE user_id=?", (user_id,))
        conn.commit()
        conn.close()
        ctx.user_data["awaiting_withdraw_addr"] = False

        text = (
            f"✅ *Withdrawal Request Submitted!*\n\n"
            f"┌──────────────────────────┐\n"
            f"│  Method: *{method}*\n"
            f"│  Amount: *₹{inr:.2f}* (${usdt} USDT)\n"
            f"│  Address: `{address}`\n"
            f"│  Status: *Pending* ⏳\n"
            f"└──────────────────────────┘\n\n"
            f"⏱ Processing time: 24–48 hours\n"
            f"📩 You'll be notified once processed."
        )
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_kb())

        # Notify admins
        for admin_id in ADMIN_IDS:
            try:
                await ctx.bot.send_message(
                    admin_id,
                    f"🔔 *New Withdrawal Request*\n\n"
                    f"User: [{update.effective_user.full_name}](tg://user?id={user_id}) (`{user_id}`)\n"
                    f"Method: *{method}*\n"
                    f"Amount: *₹{inr:.2f}* (${usdt} USDT)\n"
                    f"Address: `{address}`\n\n"
                    f"/approve_{user_id} | /reject_{user_id}",
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception:
                pass

# ─────────────────────────────────────────────
#  ADMIN COMMANDS
# ─────────────────────────────────────────────
async def admin_approve(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    try:
        uid = int(ctx.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /approve <user_id>")
        return
    conn = get_db()
    conn.execute(
        "UPDATE withdrawals SET status='approved', processed_at=datetime('now') "
        "WHERE user_id=? AND status='pending'", (uid,)
    )
    conn.commit()
    conn.close()
    await update.message.reply_text(f"✅ Withdrawal approved for user {uid}")
    try:
        await ctx.bot.send_message(uid, "✅ *Your withdrawal has been approved!*\nFunds will arrive shortly.", parse_mode=ParseMode.MARKDOWN)
    except Exception:
        pass

async def admin_reject(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    try:
        uid = int(ctx.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: /reject <user_id>")
        return
    conn = get_db()
    # Refund balance
    row = conn.execute("SELECT amount_inr FROM withdrawals WHERE user_id=? AND status='pending'", (uid,)).fetchone()
    if row:
        conn.execute("UPDATE users SET balance_inr = balance_inr + ? WHERE user_id=?", (row["amount_inr"], uid))
    conn.execute(
        "UPDATE withdrawals SET status='rejected', processed_at=datetime('now') "
        "WHERE user_id=? AND status='pending'", (uid,)
    )
    conn.commit()
    conn.close()
    await update.message.reply_text(f"❌ Withdrawal rejected for user {uid}, balance refunded.")
    try:
        await ctx.bot.send_message(uid, "❌ *Your withdrawal was rejected.*\nBalance has been refunded. Contact support.", parse_mode=ParseMode.MARKDOWN)
    except Exception:
        pass

async def admin_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    conn = get_db()
    total_users    = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total_refs     = conn.execute("SELECT COUNT(*) FROM referrals").fetchone()[0]
    pending_w      = conn.execute("SELECT COUNT(*), COALESCE(SUM(amount_inr),0) FROM withdrawals WHERE status='pending'").fetchone()
    approved_w     = conn.execute("SELECT COUNT(*), COALESCE(SUM(amount_inr),0) FROM withdrawals WHERE status='approved'").fetchone()
    conn.close()
    text = (
        f"🛡 *Admin Stats*\n\n"
        f"👤 Total Users: *{total_users}*\n"
        f"🔗 Total Referrals: *{total_refs}*\n"
        f"⏳ Pending Withdrawals: *{pending_w[0]}* (₹{pending_w[1]:.2f})\n"
        f"✅ Paid Out: *{approved_w[0]}* (₹{approved_w[1]:.2f})"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def admin_ban(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    try:
        uid = int(ctx.args[0])
        conn = get_db()
        conn.execute("UPDATE users SET is_banned=1 WHERE user_id=?", (uid,))
        conn.commit()
        conn.close()
        await update.message.reply_text(f"🚫 User {uid} banned.")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        return
    if not ctx.args:
        await update.message.reply_text("Usage: /broadcast <message>")
        return
    msg = " ".join(ctx.args)
    conn = get_db()
    users = conn.execute("SELECT user_id FROM users WHERE is_banned=0").fetchall()
    conn.close()
    sent = 0
    for u in users:
        try:
            await ctx.bot.send_message(u["user_id"], f"📢 *Announcement*\n\n{msg}", parse_mode=ParseMode.MARKDOWN)
            sent += 1
        except Exception:
            pass
    await update.message.reply_text(f"✅ Broadcast sent to {sent} users.")

# ─────────────────────────────────────────────
#  EXTRA COMMANDS
# ─────────────────────────────────────────────
async def leaderboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    conn = get_db()
    top = conn.execute(
        "SELECT full_name, total_refs, balance_inr FROM users ORDER BY total_refs DESC LIMIT 10"
    ).fetchall()
    conn.close()
    lines = ""
    medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
    for i, u in enumerate(top):
        lines += f"{medals[i]} *{u['full_name']}* — {u['total_refs']} refs — ₹{u['balance_inr']:.2f}\n"
    text = f"🏆 *Top Referrers*\n\n{lines or 'No data yet.'}"
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb())

async def profile(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db_user = get_user(user_id)
    if not db_user:
        await update.message.reply_text("Please /start first.")
        return
    link = get_referral_link(user_id)
    usdt = inr_to_usdt(db_user["balance_inr"])
    text = (
        f"👤 *Your Profile*\n\n"
        f"Name: *{db_user['full_name']}*\n"
        f"ID: `{user_id}`\n"
        f"Joined: {db_user['joined_at'][:10]}\n\n"
        f"💵 Balance INR: *₹{db_user['balance_inr']:.2f}*\n"
        f"🔶 Balance USDT: *${usdt}*\n"
        f"👥 Total Refs: *{db_user['total_refs']}*\n\n"
        f"🔗 Your Link:\n`{link}`"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_kb())

async def rate_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    usdt = inr_to_usdt(1)
    await update.message.reply_text(
        f"💱 *Current Exchange Rate*\n\n"
        f"₹1 = ${usdt} USDT\n"
        f"$1 USDT = ₹{USDT_TO_INR}",
        parse_mode=ParseMode.MARKDOWN
    )

# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────
def main():
    init_db()
    app = Application.builder().token(BOT_TOKEN).build()

    # Core
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("profile", profile))
    app.add_handler(CommandHandler("leaderboard", leaderboard))
    app.add_handler(CommandHandler("rate", rate_cmd))
    app.add_handler(CommandHandler("balance", lambda u, c: button_handler(u, c)))

    # Admin
    app.add_handler(CommandHandler("approve", admin_approve))
    app.add_handler(CommandHandler("reject",  admin_reject))
    app.add_handler(CommandHandler("astats",  admin_stats))
    app.add_handler(CommandHandler("ban",     admin_ban))
    app.add_handler(CommandHandler("broadcast", broadcast))

    # Callbacks
    app.add_handler(CallbackQueryHandler(check_join_callback, pattern="^check_join_"))
    app.add_handler(CallbackQueryHandler(button_handler))

    # Messages
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 Referral Bot is running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
