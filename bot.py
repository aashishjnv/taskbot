import os
import datetime
from pymongo import MongoClient
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
)
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes
)
from telegram.constants import ParseMode

# ─────────────────────────────────────────────
#  CONFIG — reads from Railway Environment Variables
# ─────────────────────────────────────────────
BOT_TOKEN    = os.environ.get("BOT_TOKEN")
MONGO_URI    = os.environ.get("MONGO_URI")
CHANNEL_ID   = os.environ.get("CHANNEL_ID", "@freelancebazar")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "gmail_creato_rbot")
ADMIN_IDS    = [int(x.strip()) for x in os.environ.get("ADMIN_IDS", "").split(",") if x.strip()]
MINI_APP_URL = os.environ.get("MINI_APP_URL", "")
GROUP_ID     = os.environ.get("GROUP_ID", "")   # optional: add group numeric ID in Railway

CHANNEL_LINK  = "https://t.me/freelancebazar"
GROUP_LINK    = "https://t.me/+fag7r8JXLwsyZTI9"
WEBSITE_LINK  = "https://t.me/gmail_creato_rbot"
ADMIN_CONTACT = "https://t.me/gmail_creato_rbot"

DB_NAME             = "referral_bot"
REFERRAL_REWARD_INR = 5.00
USDT_TO_INR         = 83.50
MIN_WITHDRAW_INR    = 200.00

# ─────────────────────────────────────────────
#  FREELANCE SERVICES CATALOG
# ─────────────────────────────────────────────
SERVICES = {
    "gmail": {
        "name": "Gmail Accounts", "emoji": "📧",
        "desc": "Fresh & aged Gmail accounts, bulk available",
        "items": [
            {"name": "1x Fresh Gmail",       "price": "₹15"},
            {"name": "5x Gmail Bundle",       "price": "₹60"},
            {"name": "10x Gmail Bundle",      "price": "₹100"},
            {"name": "Aged Gmail (1yr+)",     "price": "₹50"},
            {"name": "PVA Gmail (Verified)",  "price": "₹30"},
        ]
    },
    "chatgpt": {
        "name": "ChatGPT Plus", "emoji": "🤖",
        "desc": "ChatGPT Plus subscriptions at lowest price",
        "items": [
            {"name": "ChatGPT Plus 1 Month",  "price": "₹999"},
            {"name": "ChatGPT Plus 3 Months", "price": "₹2500"},
            {"name": "ChatGPT Plus 6 Months", "price": "₹4500"},
            {"name": "ChatGPT Team Account",  "price": "₹1500"},
        ]
    },
    "subscriptions": {
        "name": "Subscriptions", "emoji": "📺",
        "desc": "Netflix, Spotify, Prime & more",
        "items": [
            {"name": "Netflix 1 Month",         "price": "₹149"},
            {"name": "Spotify Premium 1 Month", "price": "₹79"},
            {"name": "Amazon Prime 1 Month",    "price": "₹99"},
            {"name": "YouTube Premium 1 Month", "price": "₹89"},
            {"name": "Canva Pro 1 Month",       "price": "₹99"},
        ]
    },
    "socialmedia": {
        "name": "Social Media", "emoji": "📱",
        "desc": "Instagram, Facebook, Twitter accounts & more",
        "items": [
            {"name": "Instagram Account", "price": "₹49"},
            {"name": "Facebook Account",  "price": "₹39"},
            {"name": "Twitter/X Account", "price": "₹59"},
            {"name": "TikTok Account",    "price": "₹69"},
            {"name": "LinkedIn Account",  "price": "₹99"},
        ]
    },
    "courses": {
        "name": "Courses", "emoji": "🎓",
        "desc": "Udemy, Coursera & premium courses",
        "items": [
            {"name": "Any Udemy Course",       "price": "₹49"},
            {"name": "Coursera Certificate",   "price": "₹199"},
            {"name": "Programming Bundle",     "price": "₹299"},
            {"name": "Design/Figma Course",    "price": "₹149"},
            {"name": "Digital Marketing Pack", "price": "₹199"},
        ]
    },
    "software": {
        "name": "Software", "emoji": "💻",
        "desc": "Windows, Office, Adobe & more",
        "items": [
            {"name": "Windows 11 Key",     "price": "₹199"},
            {"name": "MS Office 2021 Key", "price": "₹299"},
            {"name": "Adobe CC 1 Month",   "price": "₹499"},
            {"name": "Antivirus 1 Year",   "price": "₹149"},
            {"name": "VPN Premium 1 Month","price": "₹99"},
        ]
    },
    "custom": {
        "name": "Custom Work", "emoji": "⚙️",
        "desc": "Any custom requirement — just ask!",
        "items": [
            {"name": "Bot Development",    "price": "₹999+"},
            {"name": "Website Design",     "price": "₹1499+"},
            {"name": "Logo Design",        "price": "₹299+"},
            {"name": "Data Entry Work",    "price": "₹199+"},
            {"name": "Any Other Request",  "price": "Contact Admin"},
        ]
    },
}

# ─────────────────────────────────────────────
#  MONGODB SETUP
# ─────────────────────────────────────────────
client    = MongoClient(MONGO_URI)
db        = client[DB_NAME]
users_col = db["users"]
refs_col  = db["referrals"]
wdraw_col = db["withdrawals"]

users_col.create_index("user_id", unique=True)
refs_col.create_index("referrer_id")
wdraw_col.create_index("user_id")

# ─────────────────────────────────────────────
#  DATABASE HELPERS
# ─────────────────────────────────────────────
def get_user(user_id):
    return users_col.find_one({"user_id": user_id})

def create_user(user_id, username, full_name, referred_by=None):
    if not get_user(user_id):
        users_col.insert_one({
            "user_id": user_id, "username": username, "full_name": full_name,
            "referred_by": referred_by, "balance_inr": 0.0, "total_refs": 0,
            "joined_at": datetime.datetime.utcnow(), "is_banned": False
        })

def add_balance(user_id, amount_inr):
    users_col.update_one({"user_id": user_id}, {"$inc": {"balance_inr": amount_inr}})

def increment_refs(user_id):
    users_col.update_one({"user_id": user_id}, {"$inc": {"total_refs": 1}})

def inr_to_usdt(inr):
    return round(inr / USDT_TO_INR, 4)

def get_referral_link(user_id):
    return f"https://t.me/{BOT_USERNAME}?start=ref{user_id}"

def get_all_users():
    return list(users_col.find({"is_banned": False}, {"user_id": 1}))

# ─────────────────────────────────────────────
#  MEMBERSHIP CHECK
# ─────────────────────────────────────────────
async def is_channel_member(bot, user_id):
    try:
        m = await bot.get_chat_member(CHANNEL_ID, user_id)
        return m.status in ("member", "administrator", "creator")
    except Exception:
        return False

async def is_group_member(bot, user_id):
    if not GROUP_ID:
        return True
    try:
        m = await bot.get_chat_member(int(GROUP_ID), user_id)
        return m.status in ("member", "administrator", "creator")
    except Exception:
        return True

async def check_membership(bot, user_id):
    ch = await is_channel_member(bot, user_id)
    gr = await is_group_member(bot, user_id)
    return ch, gr

# ─────────────────────────────────────────────
#  KEYBOARDS
# ─────────────────────────────────────────────
def main_menu_kb():
    kb = [
        [InlineKeyboardButton("💰 My Balance",       callback_data="balance"),
         InlineKeyboardButton("👥 Referrals",        callback_data="referrals")],
        [InlineKeyboardButton("🛒 Freelance Market", callback_data="freelance"),
         InlineKeyboardButton("🔗 My Ref Link",      callback_data="reflink")],
        [InlineKeyboardButton("💸 Withdraw",         callback_data="withdraw"),
         InlineKeyboardButton("📊 Stats",            callback_data="stats")],
        [InlineKeyboardButton("📋 My History",       callback_data="history"),
         InlineKeyboardButton("ℹ️ How It Works",     callback_data="howto")],
        [InlineKeyboardButton("🌐 Visit Our Site",   url=WEBSITE_LINK),
         InlineKeyboardButton("🆘 Support",          callback_data="support")],
        [InlineKeyboardButton("❤️ Support Us / Donate", callback_data="donate")],
    ]
    if MINI_APP_URL:
        kb.insert(0, [InlineKeyboardButton("🎮 Tap Game & Wallet", web_app=WebAppInfo(url=MINI_APP_URL))])
    return InlineKeyboardMarkup(kb)

def back_kb():
    return InlineKeyboardMarkup([[InlineKeyboardButton("« Back to Menu", callback_data="menu")]])

def freelance_menu_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📧 Gmail Accounts",  callback_data="svc_gmail"),
         InlineKeyboardButton("🤖 ChatGPT Plus",    callback_data="svc_chatgpt")],
        [InlineKeyboardButton("📺 Subscriptions",   callback_data="svc_subscriptions"),
         InlineKeyboardButton("📱 Social Media",    callback_data="svc_socialmedia")],
        [InlineKeyboardButton("🎓 Courses",         callback_data="svc_courses"),
         InlineKeyboardButton("💻 Software",        callback_data="svc_software")],
        [InlineKeyboardButton("⚙️ Custom Work",     callback_data="svc_custom")],
        [InlineKeyboardButton("« Back to Menu",     callback_data="menu")],
    ])

def withdraw_method_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🏦 UPI",         callback_data="w_upi")],
        [InlineKeyboardButton("🅿️ PayPal",      callback_data="w_paypal")],
        [InlineKeyboardButton("💎 USDT BEP-20", callback_data="w_usdt")],
        [InlineKeyboardButton("« Cancel",       callback_data="menu")],
    ])

# ─────────────────────────────────────────────
#  START
# ─────────────────────────────────────────────
async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = ctx.args
    ch_ok, gr_ok = await check_membership(ctx.bot, user.id)

    if not ch_ok or not gr_ok:
        buttons = []
        if not ch_ok:
            buttons.append(InlineKeyboardButton("📢 Join Channel", url=CHANNEL_LINK))
        if not gr_ok:
            buttons.append(InlineKeyboardButton("👥 Join Group", url=GROUP_LINK))
        kb = InlineKeyboardMarkup([
            buttons,
            [InlineKeyboardButton("✅ I Joined Both", callback_data=f"check_join_{'_'.join(args) if args else ''}")]
        ])
        missing = []
        if not ch_ok: missing.append("📢 our Channel")
        if not gr_ok: missing.append("👥 our Group")
        await update.message.reply_text(
            "╔══════════════════════════════╗\n"
            "║  🔐  *Access Required*        ║\n"
            "╚══════════════════════════════╝\n\n"
            f"To use this bot, please join {' and '.join(missing)} first!\n\n"
            "👇 Tap below, join, then press *I Joined Both*.",
            parse_mode=ParseMode.MARKDOWN, reply_markup=kb
        )
        return
    await _register_and_welcome(update, ctx, user, args)

async def _register_and_welcome(update, ctx, user, args):
    existing = get_user(user.id)
    referred_by = None

    if not existing:
        if args and args[0].startswith("ref"):
            try:
                ref_id = int(args[0][3:])
                if ref_id != user.id and get_user(ref_id):
                    referred_by = ref_id
            except ValueError:
                pass
        create_user(user.id, user.username, user.full_name, referred_by)
        if referred_by:
            add_balance(referred_by, REFERRAL_REWARD_INR)
            increment_refs(referred_by)
            refs_col.insert_one({
                "referrer_id": referred_by, "referee_id": user.id,
                "reward_inr": REFERRAL_REWARD_INR, "earned_at": datetime.datetime.utcnow()
            })
            try:
                await ctx.bot.send_message(
                    referred_by,
                    f"🎉 *New Referral!*\n\n*{user.full_name}* joined using your link!\n"
                    f"💰 *+₹{REFERRAL_REWARD_INR:.2f}* added to your balance.",
                    parse_mode=ParseMode.MARKDOWN
                )
            except Exception:
                pass

    db_user  = get_user(user.id)
    usdt_bal = inr_to_usdt(db_user["balance_inr"])
    welcome  = (
        f"╔═══════════════════════════════╗\n"
        f"║  🛒  *FREELANCE BAZAR BOT*     ║\n"
        f"╚═══════════════════════════════╝\n\n"
        f"Welcome, *{user.first_name}*! 👋\n\n"
        f"┌──────────────────────────┐\n"
        f"│  💵 Balance: *₹{db_user['balance_inr']:.2f}*\n"
        f"│  🔶 USDT:    *${usdt_bal}*\n"
        f"│  👥 Referrals: *{db_user['total_refs']}*\n"
        f"└──────────────────────────┘\n\n"
        f"🛒 Buy Gmail, ChatGPT Plus, Subscriptions & more!\n"
        f"📌 Earn *₹{REFERRAL_REWARD_INR:.0f}* for every friend you refer!\n"
        f"💸 Min withdrawal: *₹{MIN_WITHDRAW_INR:.0f}*\n\n"
        f"Choose an option below 👇"
    )
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
    ch_ok, gr_ok = await check_membership(ctx.bot, user.id)
    if not ch_ok and not gr_ok:
        await query.answer("❌ Please join both the Channel and Group first!", show_alert=True)
        return
    if not ch_ok:
        await query.answer("❌ Please join the Channel first!", show_alert=True)
        return
    if not gr_ok:
        await query.answer("❌ Please join the Group first!", show_alert=True)
        return
    suffix = query.data[len("check_join_"):]
    args   = [suffix] if suffix else []
    await _register_and_welcome(update, ctx, user, args)

# ─────────────────────────────────────────────
#  BUTTON HANDLER
# ─────────────────────────────────────────────
async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query   = update.callback_query
    await query.answer()
    data    = query.data
    user_id = update.effective_user.id
    db_user = get_user(user_id)
    if not db_user:
        await query.edit_message_text("Please /start the bot first.")
        return

    if data == "menu":
        usdt_bal = inr_to_usdt(db_user["balance_inr"])
        await query.edit_message_text(
            f"╔═══════════════════════════════╗\n"
            f"║  🛒  *FREELANCE BAZAR BOT*     ║\n"
            f"╚═══════════════════════════════╝\n\n"
            f"Welcome, *{update.effective_user.first_name}*! 👋\n\n"
            f"┌──────────────────────────┐\n"
            f"│  💵 Balance: *₹{db_user['balance_inr']:.2f}*\n"
            f"│  🔶 USDT:    *${usdt_bal}*\n"
            f"│  👥 Referrals: *{db_user['total_refs']}*\n"
            f"└──────────────────────────┘\n\nChoose an option below 👇",
            parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_kb()
        )

    elif data == "balance":
        inr = db_user["balance_inr"]
        await query.edit_message_text(
            f"💰 *Your Balance*\n\n"
            f"┌──────────────────────────┐\n"
            f"│  🇮🇳 INR:  *₹{inr:.2f}*\n"
            f"│  🔶 USDT: *${inr_to_usdt(inr)}*\n"
            f"│  👥 Refs:  *{db_user['total_refs']}*\n"
            f"└──────────────────────────┘\n\n"
            f"💡 $1 USDT = ₹{USDT_TO_INR}\n"
            f"📌 Min Withdrawal: *₹{MIN_WITHDRAW_INR:.0f}*\n"
            f"{'✅ Ready to withdraw!' if inr >= MIN_WITHDRAW_INR else f'⚠️ Need ₹{MIN_WITHDRAW_INR - inr:.2f} more'}",
            parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb()
        )

    elif data == "referrals":
        refs = list(refs_col.find({"referrer_id": user_id}).sort("earned_at", -1).limit(10))
        link = get_referral_link(user_id)
        ref_list = ""
        for r in refs:
            u    = get_user(r["referee_id"])
            name = u["full_name"] if u else "Unknown"
            dt   = r["earned_at"].strftime("%Y-%m-%d") if isinstance(r["earned_at"], datetime.datetime) else str(r["earned_at"])[:10]
            ref_list += f"  • {name} — *+₹{r['reward_inr']:.2f}* ({dt})\n"
        share_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 Share Link", url=f"https://t.me/share/url?url={link}&text=Join+Freelance+Bazar+%26+earn+rewards!")],
            [InlineKeyboardButton("« Back to Menu", callback_data="menu")]
        ])
        await query.edit_message_text(
            f"👥 *Your Referrals*\n\nTotal: *{db_user['total_refs']}*\nEarned: *₹{db_user['balance_inr']:.2f}*\n\n"
            f"🔗 Your link:\n`{link}`\n\n"
            + (f"📋 *Recent:*\n{ref_list}" if refs else "No referrals yet. Share your link!"),
            parse_mode=ParseMode.MARKDOWN, reply_markup=share_kb
        )

    elif data == "reflink":
        link = get_referral_link(user_id)
        share_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 Share Link", url=f"https://t.me/share/url?url={link}&text=Join+Freelance+Bazar+%26+earn+₹5+per+friend!")],
            [InlineKeyboardButton("« Back to Menu", callback_data="menu")]
        ])
        await query.edit_message_text(
            f"🔗 *Your Referral Link*\n\n`{link}`\n\n"
            f"💰 Earn *₹{REFERRAL_REWARD_INR:.0f}* per friend!\n"
            f"📊 Referred: *{db_user['total_refs']}* people",
            parse_mode=ParseMode.MARKDOWN, reply_markup=share_kb
        )

    elif data == "freelance":
        await query.edit_message_text(
            f"🛒 *Freelance Bazar — Services*\n\n"
            f"Browse categories below. Click any to see items & prices.\n\n"
            f"💬 To order: pick a service → tap *Visit Site* or *Contact Admin*\n\n"
            f"🌐 [FreelanceBazar]({WEBSITE_LINK})",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=freelance_menu_kb(),
            disable_web_page_preview=True
        )

    elif data.startswith("svc_"):
        key = data[4:]
        svc = SERVICES.get(key)
        if not svc:
            await query.edit_message_text("Service not found.", reply_markup=back_kb())
            return
        lines = ""
        for i, item in enumerate(svc["items"], 1):
            lines += f"  {i}. *{item['name']}* — `{item['price']}`\n"
        order_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🌐 Visit Site to Order", url=WEBSITE_LINK)],
            [InlineKeyboardButton("💬 Contact Admin",       url=ADMIN_CONTACT)],
            [InlineKeyboardButton("« Back to Services",     callback_data="freelance")],
            [InlineKeyboardButton("« Main Menu",            callback_data="menu")],
        ])
        await query.edit_message_text(
            f"{svc['emoji']} *{svc['name']}*\n_{svc['desc']}_\n\n"
            f"*Available Items:*\n{lines}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"To order:\n1️⃣ Visit site or contact admin\n"
            f"2️⃣ Tell them what you need\n3️⃣ Pay & receive instantly! ⚡",
            parse_mode=ParseMode.MARKDOWN, reply_markup=order_kb
        )

    elif data == "stats":
        total_users = users_col.count_documents({})
        total_refs  = refs_col.count_documents({})
        paid_res    = list(wdraw_col.aggregate([{"$match": {"status": "approved"}}, {"$group": {"_id": None, "t": {"$sum": "$amount_inr"}}}]))
        total_paid  = paid_res[0]["t"] if paid_res else 0
        await query.edit_message_text(
            f"📊 *Bot Statistics*\n\n"
            f"┌─────────────────────────┐\n"
            f"│  👤 Users:    *{total_users}*\n"
            f"│  🔗 Refs:     *{total_refs}*\n"
            f"│  💸 Paid Out: *₹{total_paid:.2f}*\n"
            f"│  💱 Rate:     *₹{USDT_TO_INR}/USDT*\n"
            f"└─────────────────────────┘",
            parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb()
        )

    elif data == "howto":
        await query.edit_message_text(
            f"ℹ️ *How It Works*\n\n"
            f"💰 *Earn Money:*\n"
            f"1️⃣ Get your ref link — tap 🔗 My Ref Link\n"
            f"2️⃣ Share with friends\n"
            f"3️⃣ Earn *₹{REFERRAL_REWARD_INR:.0f}* per join\n\n"
            f"🛒 *Buy Services:*\n"
            f"1️⃣ Tap 🛒 Freelance Market\n"
            f"2️⃣ Choose category & item\n"
            f"3️⃣ Contact admin or visit site\n\n"
            f"💸 *Withdraw:*\n"
            f"• Min: *₹{MIN_WITHDRAW_INR:.0f}* | Methods: UPI, PayPal, USDT\n"
            f"• Processing: 24–48 hours",
            parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb()
        )

    elif data == "history":
        rows = list(wdraw_col.find({"user_id": user_id}).sort("requested_at", -1).limit(10))
        if not rows:
            text = "📋 *Withdrawal History*\n\nNo withdrawals yet."
        else:
            lines = ""
            for r in rows:
                emoji = {"pending": "⏳", "approved": "✅", "rejected": "❌"}.get(r["status"], "•")
                dt    = r["requested_at"].strftime("%Y-%m-%d") if isinstance(r["requested_at"], datetime.datetime) else str(r["requested_at"])[:10]
                lines += f"{emoji} *{r['method'].upper()}* — ₹{r['amount_inr']:.2f} ({r['status']}) — {dt}\n"
            text = f"📋 *Withdrawal History*\n\n{lines}"
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb())

    elif data == "support":
        await query.edit_message_text(
            f"🆘 *Support*\n\nNeed help? We're here!\n\n"
            f"• Withdrawal not received → wait 24–48h\n"
            f"• Referral not credited → check your link was used\n"
            f"• Service not delivered → contact admin immediately\n\n"
            f"👇 Reach us:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💬 Contact Admin", url=ADMIN_CONTACT)],
                [InlineKeyboardButton("🌐 Visit Site",    url=WEBSITE_LINK)],
                [InlineKeyboardButton("📢 Channel", url=CHANNEL_LINK),
                 InlineKeyboardButton("👥 Group",   url=GROUP_LINK)],
                [InlineKeyboardButton("« Back to Menu", callback_data="menu")],
            ])
        )

    elif data == "donate":
        _a = "9410988578"; _b = "@fam"
        upi_url = f"upi://pay?pa={_a+_b}&pn=FreelanceBazar&cu=INR"
        await query.edit_message_text(
            "❤️ *Support Us*\n\nThis bot is free and kept alive by your support.\n\n"
            "Every donation helps us maintain servers & add features! 🙏\n\n"
            "┌──────────────────────────┐\n│  💸 Any amount welcome   │\n│  🔒 100% secure via UPI  │\n└──────────────────────────┘\n\n"
            "👇 Tap to open your UPI app:",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💳 Pay via UPI App", url=upi_url)],
                [InlineKeyboardButton("« Back to Menu", callback_data="menu")]
            ])
        )

    elif data == "withdraw":
        inr = db_user["balance_inr"]
        if inr < MIN_WITHDRAW_INR:
            await query.edit_message_text(
                f"💸 *Withdraw*\n\n❌ Insufficient balance!\n\n"
                f"Your balance: *₹{inr:.2f}*\nMinimum: *₹{MIN_WITHDRAW_INR:.0f}*\n"
                f"Need *₹{MIN_WITHDRAW_INR - inr:.2f}* more. Keep referring! 🔗",
                parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb()
            )
        else:
            await query.edit_message_text(
                f"💸 *Withdraw Funds*\n\nAvailable: *₹{inr:.2f}* (${inr_to_usdt(inr)} USDT)\n\nChoose method:",
                parse_mode=ParseMode.MARKDOWN, reply_markup=withdraw_method_kb()
            )

    elif data in ("w_upi", "w_paypal", "w_usdt"):
        method_map = {"w_upi": "UPI", "w_paypal": "PayPal", "w_usdt": "USDT BEP-20"}
        addr_map   = {"w_upi": "your UPI ID (e.g. name@upi)", "w_paypal": "your PayPal email", "w_usdt": "your BEP-20 wallet address"}
        method = method_map[data]
        ctx.user_data["withdraw_method"] = method
        ctx.user_data["awaiting_withdraw_addr"] = True
        await query.edit_message_text(
            f"💸 *Withdraw via {method}*\n\nPlease send me {addr_map[data]}.\n\n⚠️ Double-check before sending!",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("« Cancel", callback_data="menu")]])
        )

# ─────────────────────────────────────────────
#  MESSAGE HANDLER
# ─────────────────────────────────────────────
async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db_user = get_user(user_id)
    if not db_user or not ctx.user_data.get("awaiting_withdraw_addr"):
        return
    address = update.message.text.strip()
    method  = ctx.user_data.get("withdraw_method", "Unknown")
    inr     = db_user["balance_inr"]
    usdt    = inr_to_usdt(inr)
    wdraw_col.insert_one({
        "user_id": user_id, "amount_inr": inr, "amount_usdt": usdt,
        "method": method, "address": address, "status": "pending",
        "requested_at": datetime.datetime.utcnow(), "processed_at": None
    })
    users_col.update_one({"user_id": user_id}, {"$set": {"balance_inr": 0.0}})
    ctx.user_data["awaiting_withdraw_addr"] = False
    await update.message.reply_text(
        f"✅ *Withdrawal Submitted!*\n\n"
        f"┌──────────────────────────┐\n"
        f"│  Method:  *{method}*\n"
        f"│  Amount:  *₹{inr:.2f}* (${usdt} USDT)\n"
        f"│  Address: `{address}`\n"
        f"│  Status:  *Pending* ⏳\n"
        f"└──────────────────────────┘\n\n"
        f"⏱ Processing: 24–48 hours",
        parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_kb()
    )
    for admin_id in ADMIN_IDS:
        try:
            await ctx.bot.send_message(
                admin_id,
                f"🔔 *New Withdrawal*\n\n"
                f"User: [{update.effective_user.full_name}](tg://user?id={user_id}) (`{user_id}`)\n"
                f"Method: *{method}*\nAmount: *₹{inr:.2f}* (${usdt})\nAddress: `{address}`\n\n"
                f"/approve {user_id} | /reject {user_id}",
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception:
            pass

# ─────────────────────────────────────────────
#  BROADCAST
# ─────────────────────────────────────────────
async def broadcast(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    if not ctx.args:
        await update.message.reply_text("Usage: `/broadcast <message>`", parse_mode=ParseMode.MARKDOWN)
        return
    msg = " ".join(ctx.args)
    all_users = get_all_users()
    p = await update.message.reply_text(f"📤 Sending to {len(all_users)} users...")
    sent = failed = 0
    for u in all_users:
        try:
            await ctx.bot.send_message(u["user_id"], f"📢 *Announcement*\n\n{msg}", parse_mode=ParseMode.MARKDOWN)
            sent += 1
        except Exception:
            failed += 1
    await p.edit_text(f"✅ Done! Sent: *{sent}* | Failed: *{failed}*", parse_mode=ParseMode.MARKDOWN)

async def broadcast_button(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    if not ctx.args:
        await update.message.reply_text("Usage: `/broadcast_button Btn|URL|Message`", parse_mode=ParseMode.MARKDOWN)
        return
    parts = [p.strip() for p in " ".join(ctx.args).split("|")]
    if len(parts) < 3:
        await update.message.reply_text("❌ Format: `/broadcast_button Btn|URL|Message`", parse_mode=ParseMode.MARKDOWN)
        return
    kb = InlineKeyboardMarkup([[InlineKeyboardButton(parts[0], url=parts[1])]])
    all_users = get_all_users()
    p = await update.message.reply_text(f"📤 Sending to {len(all_users)} users...")
    sent = failed = 0
    for u in all_users:
        try:
            await ctx.bot.send_message(u["user_id"], f"📢 *Announcement*\n\n{parts[2]}", parse_mode=ParseMode.MARKDOWN, reply_markup=kb)
            sent += 1
        except Exception:
            failed += 1
    await p.edit_text(f"✅ Done! Sent: *{sent}* | Failed: *{failed}*", parse_mode=ParseMode.MARKDOWN)

async def broadcast_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    if not update.message.reply_to_message or not update.message.reply_to_message.photo:
        await update.message.reply_text("🖼 Reply to a photo with `/broadcast_photo <caption>`", parse_mode=ParseMode.MARKDOWN)
        return
    photo_id  = update.message.reply_to_message.photo[-1].file_id
    caption   = " ".join(ctx.args) if ctx.args else "📢 New Announcement!"
    all_users = get_all_users()
    p = await update.message.reply_text(f"📤 Sending to {len(all_users)} users...")
    sent = failed = 0
    for u in all_users:
        try:
            await ctx.bot.send_photo(u["user_id"], photo=photo_id, caption=f"📢 *Announcement*\n\n{caption}", parse_mode=ParseMode.MARKDOWN)
            sent += 1
        except Exception:
            failed += 1
    await p.edit_text(f"✅ Done! Sent: *{sent}* | Failed: *{failed}*", parse_mode=ParseMode.MARKDOWN)

async def msg_user(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    if not ctx.args or len(ctx.args) < 2:
        await update.message.reply_text("Usage: `/msg <user_id> <message>`", parse_mode=ParseMode.MARKDOWN)
        return
    try:
        uid = int(ctx.args[0])
        msg = " ".join(ctx.args[1:])
        await ctx.bot.send_message(uid, f"💬 *Message from Admin*\n\n{msg}", parse_mode=ParseMode.MARKDOWN)
        await update.message.reply_text(f"✅ Sent to `{uid}`", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"❌ Failed: {e}")

# ─────────────────────────────────────────────
#  ADMIN COMMANDS
# ─────────────────────────────────────────────
async def admin_approve(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    try:
        uid = int(ctx.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: `/approve <user_id>`", parse_mode=ParseMode.MARKDOWN); return
    wdraw_col.update_one({"user_id": uid, "status": "pending"}, {"$set": {"status": "approved", "processed_at": datetime.datetime.utcnow()}})
    await update.message.reply_text(f"✅ Approved for `{uid}`", parse_mode=ParseMode.MARKDOWN)
    try: await ctx.bot.send_message(uid, "✅ *Your withdrawal has been approved!* Funds arriving shortly.", parse_mode=ParseMode.MARKDOWN)
    except Exception: pass

async def admin_reject(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    try:
        uid = int(ctx.args[0])
    except (IndexError, ValueError):
        await update.message.reply_text("Usage: `/reject <user_id>`", parse_mode=ParseMode.MARKDOWN); return
    row = wdraw_col.find_one({"user_id": uid, "status": "pending"})
    if row: users_col.update_one({"user_id": uid}, {"$inc": {"balance_inr": row["amount_inr"]}})
    wdraw_col.update_one({"user_id": uid, "status": "pending"}, {"$set": {"status": "rejected", "processed_at": datetime.datetime.utcnow()}})
    await update.message.reply_text(f"❌ Rejected & refunded `{uid}`", parse_mode=ParseMode.MARKDOWN)
    try: await ctx.bot.send_message(uid, "❌ *Withdrawal rejected.* Balance refunded. Contact support.", parse_mode=ParseMode.MARKDOWN)
    except Exception: pass

async def admin_ban(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    try:
        uid = int(ctx.args[0])
        users_col.update_one({"user_id": uid}, {"$set": {"is_banned": True}})
        await update.message.reply_text(f"🚫 User `{uid}` banned.", parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def admin_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    total_users = users_col.count_documents({})
    total_refs  = refs_col.count_documents({})
    p = list(wdraw_col.aggregate([{"$match": {"status": "pending"}},  {"$group": {"_id": None, "c": {"$sum": 1}, "t": {"$sum": "$amount_inr"}}}]))
    a = list(wdraw_col.aggregate([{"$match": {"status": "approved"}}, {"$group": {"_id": None, "c": {"$sum": 1}, "t": {"$sum": "$amount_inr"}}}]))
    pd = p[0] if p else {"c": 0, "t": 0}; ap = a[0] if a else {"c": 0, "t": 0}
    await update.message.reply_text(
        f"🛡 *Quick Stats*\n\n👤 Users: *{total_users}*\n🔗 Refs: *{total_refs}*\n"
        f"⏳ Pending W/D: *{pd['c']}* (₹{pd['t']:.2f})\n✅ Paid: *{ap['c']}* (₹{ap['t']:.2f})",
        parse_mode=ParseMode.MARKDOWN
    )

async def dashboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    total_users  = users_col.count_documents({})
    banned_users = users_col.count_documents({"is_banned": True})
    total_refs   = refs_col.count_documents({})
    p  = list(wdraw_col.aggregate([{"$match": {"status": "pending"}},  {"$group": {"_id": None, "c": {"$sum": 1}, "t": {"$sum": "$amount_inr"}}}]))
    a  = list(wdraw_col.aggregate([{"$match": {"status": "approved"}}, {"$group": {"_id": None, "c": {"$sum": 1}, "t": {"$sum": "$amount_inr"}}}]))
    rj = list(wdraw_col.aggregate([{"$match": {"status": "rejected"}}, {"$group": {"_id": None, "c": {"$sum": 1}}}]))
    tb = list(users_col.aggregate([{"$group": {"_id": None, "t": {"$sum": "$balance_inr"}}}]))
    pd = p[0]  if p  else {"c": 0, "t": 0}
    ap = a[0]  if a  else {"c": 0, "t": 0}
    rjd= rj[0] if rj else {"c": 0}
    tbd= tb[0] if tb else {"t": 0}
    top5 = list(users_col.find({}, {"full_name": 1, "total_refs": 1, "balance_inr": 1}).sort("total_refs", -1).limit(5))
    top5_text = ""
    for i, u in enumerate(top5, 1):
        top5_text += f"  {i}. *{u['full_name']}* — {u['total_refs']} refs — ₹{u['balance_inr']:.2f}\n"
    await update.message.reply_text(
        f"📊 *ADMIN DASHBOARD*\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 *Users*\n  Total: *{total_users}*  |  Banned: *{banned_users}*\n\n"
        f"🔗 *Referrals*\n  Total: *{total_refs}*\n\n"
        f"💰 *Wallets*\n  Total balance: *₹{tbd['t']:.2f}*\n\n"
        f"💸 *Withdrawals*\n  ⏳ Pending:  *{pd['c']}* (₹{pd['t']:.2f})\n"
        f"  ✅ Approved: *{ap['c']}* (₹{ap['t']:.2f})\n  ❌ Rejected: *{rjd['c']}*\n\n"
        f"🏆 *Top Referrers*\n{top5_text}\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"`/users` | `/pendings` | `/allbalances`",
        parse_mode=ParseMode.MARKDOWN
    )

async def list_users(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    page     = int(ctx.args[0]) - 1 if ctx.args else 0
    per_page = 20
    total    = users_col.count_documents({})
    all_u    = list(users_col.find({}, {"user_id": 1, "full_name": 1, "username": 1, "balance_inr": 1, "total_refs": 1, "is_banned": 1})
                    .sort("joined_at", -1).skip(page * per_page).limit(per_page))
    if not all_u:
        await update.message.reply_text("No users found."); return
    lines = ""
    for u in all_u:
        banned = " 🚫" if u.get("is_banned") else ""
        uname  = f"@{u['username']}" if u.get("username") else "no @"
        lines += f"`{u['user_id']}`{banned} — *{u['full_name']}* ({uname}) — ₹{u['balance_inr']:.0f} — {u['total_refs']} refs\n"
    total_pages = (total + per_page - 1) // per_page
    text = f"👥 *All Users* — Page {page+1}/{total_pages} (Total: {total})\n\n{lines}"
    if page + 1 < total_pages:
        text += f"\n➡️ Next: `/users {page+2}`"
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def user_info(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    if not ctx.args:
        await update.message.reply_text("Usage: `/userinfo <user_id>`", parse_mode=ParseMode.MARKDOWN); return
    try: uid = int(ctx.args[0])
    except ValueError:
        await update.message.reply_text("❌ Invalid user ID."); return
    u = get_user(uid)
    if not u:
        await update.message.reply_text("❌ User not found. Make sure the ID is correct."); return
    ref_count = refs_col.count_documents({"referrer_id": uid})
    w_pending = wdraw_col.count_documents({"user_id": uid, "status": "pending"})
    w_approved= wdraw_col.count_documents({"user_id": uid, "status": "approved"})
    w_total   = list(wdraw_col.aggregate([{"$match": {"user_id": uid, "status": "approved"}}, {"$group": {"_id": None, "s": {"$sum": "$amount_inr"}}}]))
    paid_out  = w_total[0]["s"] if w_total else 0.0
    joined    = u["joined_at"].strftime("%Y-%m-%d %H:%M") if isinstance(u["joined_at"], datetime.datetime) else str(u["joined_at"])[:16]
    ref_by    = "None"
    if u.get("referred_by"):
        ru = get_user(u["referred_by"])
        ref_by = ru["full_name"] if ru else str(u["referred_by"])
    await update.message.reply_text(
        f"👤 *User Details*\n\n"
        f"┌────────────────────────────┐\n"
        f"│ Name:    *{u['full_name']}*\n"
        f"│ ID:      `{uid}`\n"
        f"│ @:       @{u.get('username') or 'none'}\n"
        f"│ Joined:  {joined}\n"
        f"│ Banned:  {'🚫 Yes' if u.get('is_banned') else '✅ No'}\n"
        f"├────────────────────────────┤\n"
        f"│ 💵 INR:      ₹{u['balance_inr']:.2f}\n"
        f"│ 🔶 USDT:     ${inr_to_usdt(u['balance_inr'])}\n"
        f"│ 👥 Refs:     {ref_count}\n"
        f"├────────────────────────────┤\n"
        f"│ ⏳ Pending:  {w_pending}\n"
        f"│ ✅ Approved: {w_approved}\n"
        f"│ 💰 Paid:     ₹{paid_out:.2f}\n"
        f"│ 🔗 Ref by:   {ref_by}\n"
        f"└────────────────────────────┘\n\n"
        f"`/ban {uid}` | `/msg {uid} hi` | `/addbalance {uid} 10`",
        parse_mode=ParseMode.MARKDOWN
    )

async def all_balances(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    top = list(users_col.find({}, {"user_id": 1, "full_name": 1, "balance_inr": 1, "total_refs": 1}).sort("balance_inr", -1).limit(25))
    if not top:
        await update.message.reply_text("No users yet."); return
    lines = ""
    for i, u in enumerate(top, 1):
        lines += f"{i}. `{u['user_id']}` — *{u['full_name']}* — ₹{u['balance_inr']:.2f} ({u['total_refs']} refs)\n"
    await update.message.reply_text(f"💰 *All Balances* (Top 25)\n\n{lines}", parse_mode=ParseMode.MARKDOWN)

async def add_balance_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    if not ctx.args or len(ctx.args) < 2:
        await update.message.reply_text("Usage: `/addbalance <user_id> <amount>`", parse_mode=ParseMode.MARKDOWN); return
    try: uid = int(ctx.args[0]); amount = float(ctx.args[1])
    except ValueError:
        await update.message.reply_text("❌ Invalid ID or amount."); return
    u = get_user(uid)
    if not u:
        await update.message.reply_text("❌ User not found."); return
    add_balance(uid, amount)
    await update.message.reply_text(f"✅ Added *₹{amount:.2f}* to `{uid}` ({u['full_name']})", parse_mode=ParseMode.MARKDOWN)
    try: await ctx.bot.send_message(uid, f"🎁 *₹{amount:.2f}* bonus added to your balance by admin!", parse_mode=ParseMode.MARKDOWN)
    except Exception: pass

async def pending_withdrawals(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    rows = list(wdraw_col.find({"status": "pending"}).sort("requested_at", 1).limit(20))
    if not rows:
        await update.message.reply_text("✅ No pending withdrawals!"); return
    lines = ""
    for r in rows:
        u    = get_user(r["user_id"])
        name = u["full_name"] if u else "Unknown"
        dt   = r["requested_at"].strftime("%m/%d %H:%M") if isinstance(r["requested_at"], datetime.datetime) else str(r["requested_at"])[:13]
        lines += (f"👤 *{name}* (`{r['user_id']}`)\n   💸 ₹{r['amount_inr']:.2f} via *{r['method']}*\n"
                  f"   📬 `{r['address']}`\n   🕐 {dt}\n   `/approve {r['user_id']}` | `/reject {r['user_id']}`\n\n")
    await update.message.reply_text(f"⏳ *Pending Withdrawals* ({len(rows)})\n\n{lines}", parse_mode=ParseMode.MARKDOWN)

async def admin_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS: return
    await update.message.reply_text(
        "🛡 *Admin Commands*\n\n"
        "━━━━ 📊 Overview ━━━━\n"
        "`/dashboard` — Full admin overview\n"
        "`/astats` — Quick stats\n\n"
        "━━━━ 👥 Users ━━━━\n"
        "`/users` — List all users\n"
        "`/users 2` — Page 2\n"
        "`/userinfo <id>` — Full user details\n"
        "`/allbalances` — Users by balance\n"
        "`/addbalance <id> <₹>` — Add balance\n"
        "`/ban <id>` — Ban user\n\n"
        "━━━━ 💸 Withdrawals ━━━━\n"
        "`/pendings` — All pending\n"
        "`/approve <id>` — Approve\n"
        "`/reject <id>` — Reject & refund\n\n"
        "━━━━ 📢 Broadcast ━━━━\n"
        "`/broadcast <msg>`\n"
        "`/broadcast_button Btn|URL|msg`\n"
        "`/broadcast_photo <caption>` — reply to photo\n"
        "`/msg <id> <msg>` — one user\n",
        parse_mode=ParseMode.MARKDOWN
    )

# ─────────────────────────────────────────────
#  USER COMMANDS
# ─────────────────────────────────────────────
async def leaderboard(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    top    = list(users_col.find({}, {"full_name": 1, "total_refs": 1, "balance_inr": 1}).sort("total_refs", -1).limit(10))
    medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
    lines  = "".join(f"{medals[i]} *{u['full_name']}* — {u['total_refs']} refs — ₹{u['balance_inr']:.2f}\n" for i, u in enumerate(top))
    await update.message.reply_text(f"🏆 *Top Referrers*\n\n{lines or 'No data yet.'}", parse_mode=ParseMode.MARKDOWN, reply_markup=back_kb())

async def profile(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    db_user = get_user(user_id)
    if not db_user:
        await update.message.reply_text("Please /start first."); return
    joined = db_user["joined_at"].strftime("%Y-%m-%d") if isinstance(db_user["joined_at"], datetime.datetime) else str(db_user["joined_at"])[:10]
    await update.message.reply_text(
        f"👤 *Your Profile*\n\nName: *{db_user['full_name']}*\nID: `{user_id}`\nJoined: {joined}\n\n"
        f"💵 Balance: *₹{db_user['balance_inr']:.2f}*\n🔶 USDT: *${inr_to_usdt(db_user['balance_inr'])}*\n"
        f"👥 Referrals: *{db_user['total_refs']}*\n\n🔗 Your Link:\n`{get_referral_link(user_id)}`",
        parse_mode=ParseMode.MARKDOWN, reply_markup=main_menu_kb()
    )

async def rate_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"💱 *Exchange Rate*\n\n₹1 = ${inr_to_usdt(1)} USDT\n$1 USDT = ₹{USDT_TO_INR}",
        parse_mode=ParseMode.MARKDOWN
    )

# ─────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",            start))
    app.add_handler(CommandHandler("profile",          profile))
    app.add_handler(CommandHandler("leaderboard",      leaderboard))
    app.add_handler(CommandHandler("rate",             rate_cmd))
    app.add_handler(CommandHandler("dashboard",        dashboard))
    app.add_handler(CommandHandler("approve",          admin_approve))
    app.add_handler(CommandHandler("reject",           admin_reject))
    app.add_handler(CommandHandler("astats",           admin_stats))
    app.add_handler(CommandHandler("ban",              admin_ban))
    app.add_handler(CommandHandler("users",            list_users))
    app.add_handler(CommandHandler("userinfo",         user_info))
    app.add_handler(CommandHandler("allbalances",      all_balances))
    app.add_handler(CommandHandler("addbalance",       add_balance_cmd))
    app.add_handler(CommandHandler("pendings",         pending_withdrawals))
    app.add_handler(CommandHandler("admin_help",       admin_help))
    app.add_handler(CommandHandler("broadcast",        broadcast))
    app.add_handler(CommandHandler("broadcast_button", broadcast_button))
    app.add_handler(CommandHandler("broadcast_photo",  broadcast_photo))
    app.add_handler(CommandHandler("msg",              msg_user))

    app.add_handler(CallbackQueryHandler(check_join_callback, pattern="^check_join_"))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("🤖 FreelanceBazar Bot is running...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
