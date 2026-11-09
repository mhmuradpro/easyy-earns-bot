import os, json, hmac, hashlib, sqlite3, threading, time
from urllib.parse import parse_qsl
from flask import Flask, request, jsonify, send_from_directory
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

BOT_TOKEN = os.environ["BOT_TOKEN"]
BOT_USERNAME = os.environ.get("BOT_USERNAME", "Easyy_Earns_bot").lstrip("@")
WEBAPP_URL = os.environ["WEBAPP_URL"].rstrip("/")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
DB_PATH = os.environ.get("DB_PATH", "easyy_earns.db")

bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__, static_folder="static")

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with db() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
            balance REAL NOT NULL DEFAULT 0, referrer_id INTEGER,
            created_at INTEGER NOT NULL
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS withdrawals (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            amount REAL, method TEXT, account TEXT, status TEXT DEFAULT 'pending',
            created_at INTEGER
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER,
            amount REAL, kind TEXT, note TEXT, created_at INTEGER
        )""")

def upsert_user(u, referrer_id=None):
    with db() as c:
        existing = c.execute("SELECT user_id FROM users WHERE user_id=?", (u.id,)).fetchone()
        if not existing:
            valid_ref = None
            if referrer_id and int(referrer_id) != u.id:
                ref = c.execute("SELECT user_id FROM users WHERE user_id=?", (int(referrer_id),)).fetchone()
                if ref:
                    valid_ref = int(referrer_id)
            c.execute("""INSERT INTO users(user_id,username,first_name,referrer_id,created_at)
                         VALUES(?,?,?,?,?)""",
                      (u.id, u.username or "", u.first_name or "", valid_ref, int(time.time())))
        else:
            c.execute("UPDATE users SET username=?, first_name=? WHERE user_id=?",
                      (u.username or "", u.first_name or "", u.id))

@bot.message_handler(commands=["start"])
def start(message):
    parts = (message.text or "").split(maxsplit=1)
    ref = None
    if len(parts) > 1 and parts[1].startswith("ref_"):
        try: ref = int(parts[1][4:])
        except ValueError: pass
    upsert_user(message.from_user, ref)
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🚀 Open Easyy Earns", web_app=WebAppInfo(url=WEBAPP_URL)))
    markup.add(InlineKeyboardButton("👥 Invite Friends", url=f"https://t.me/share/url?url=https://t.me/{BOT_USERNAME}?start=ref_{message.from_user.id}"))
    bot.send_message(message.chat.id,
        f"Welcome to Easyy Earns, {message.from_user.first_name or 'friend'}!\\n\\nOpen the dashboard to view your balance, invite friends and request withdrawals.",
        reply_markup=markup)

@bot.message_handler(commands=["help"])
def help_cmd(message):
    bot.reply_to(message, "Use /start to open the Easyy Earns dashboard.")

@bot.message_handler(commands=["addbalance"])
def add_balance(message):
    if not ADMIN_ID or message.from_user.id != ADMIN_ID:
        return bot.reply_to(message, "Not authorized.")
    args = (message.text or "").split()
    if len(args) != 3:
        return bot.reply_to(message, "Usage: /addbalance USER_ID AMOUNT")
    try:
        uid, amount = int(args[1]), float(args[2])
        if amount <= 0: raise ValueError()
    except ValueError:
        return bot.reply_to(message, "Invalid user ID or amount.")
    with db() as c:
        row = c.execute("SELECT user_id FROM users WHERE user_id=?", (uid,)).fetchone()
        if not row: return bot.reply_to(message, "User not found. They must /start first.")
        c.execute("UPDATE users SET balance=balance+? WHERE user_id=?", (amount, uid))
        c.execute("INSERT INTO transactions(user_id,amount,kind,note,created_at) VALUES(?,?,?,?,?)",
                  (uid, amount, "admin_credit", "Admin credit", int(time.time())))
    bot.reply_to(message, f"Added ${amount:.2f} to {uid}.")

def verify_init_data(init_data):
    if not init_data: return None
    values = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = values.pop("hash", None)
    if not received_hash: return None
    data_check = "\\n".join(f"{k}={v}" for k, v in sorted(values.items()))
    secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    calculated = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calculated, received_hash): return None
    try:
        auth_date = int(values.get("auth_date", "0"))
        if time.time() - auth_date > 86400: return None
        user = json.loads(values["user"])
        return user
    except Exception:
        return None

@app.get("/")
def home():
    return send_from_directory("static", "index.html")

@app.get("/api/me")
def me():
    user = verify_init_data(request.headers.get("X-Telegram-Init-Data", ""))
    if not user: return jsonify(error="Open this app from your Telegram bot."), 401
    uid = int(user["id"])
    with db() as c:
        row = c.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
        if not row:
            c.execute("INSERT INTO users(user_id,username,first_name,created_at) VALUES(?,?,?,?)",
                      (uid, user.get("username",""), user.get("first_name",""), int(time.time())))
            row = c.execute("SELECT * FROM users WHERE user_id=?", (uid,)).fetchone()
        referrals = c.execute("SELECT COUNT(*) n FROM users WHERE referrer_id=?", (uid,)).fetchone()["n"]
        history = c.execute("SELECT amount,kind,note,created_at FROM transactions WHERE user_id=? ORDER BY id DESC LIMIT 8", (uid,)).fetchall()
    return jsonify(user={"id":uid,"name":row["first_name"],"balance":row["balance"],
                         "referrals":referrals,"ref_link":f"https://t.me/{BOT_USERNAME}?start=ref_{uid}"},
                   history=[dict(x) for x in history])

@app.post("/api/withdraw")
def withdraw():
    user = verify_init_data(request.headers.get("X-Telegram-Init-Data", ""))
    if not user: return jsonify(error="Unauthorized"), 401
    data = request.get_json(silent=True) or {}
    try: amount = round(float(data.get("amount", 0)), 2)
    except (TypeError, ValueError): amount = 0
    method, account = str(data.get("method",""))[:30], str(data.get("account",""))[:120]
    if amount <= 0 or not method or not account:
        return jsonify(error="Enter a valid amount, payment method and account."), 400
    with db() as c:
        row = c.execute("SELECT balance FROM users WHERE user_id=?", (int(user["id"]),)).fetchone()
        if not row or amount > row["balance"]:
            return jsonify(error="Insufficient balance."), 400
        c.execute("UPDATE users SET balance=balance-? WHERE user_id=?", (amount, int(user["id"])))
        c.execute("INSERT INTO withdrawals(user_id,amount,method,account,created_at) VALUES(?,?,?,?,?)",
                  (int(user["id"]), amount, method, account, int(time.time())))
        c.execute("INSERT INTO transactions(user_id,amount,kind,note,created_at) VALUES(?,?,?,?,?)",
                  (int(user["id"]), -amount, "withdrawal", "Withdrawal requested", int(time.time())))
    if ADMIN_ID:
        try: bot.send_message(ADMIN_ID, f"New withdrawal request\\nUser: {user['id']}\\nAmount: ${amount:.2f}\\nMethod: {method}\\nAccount: {account}")
        except Exception: pass
    return jsonify(ok=True, message="Withdrawal request submitted.")

if __name__ == "__main__":
    init_db()
    threading.Thread(target=bot.infinity_polling, kwargs={"skip_pending": True}, daemon=True).start()
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
