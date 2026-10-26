"""
ANTHE Aakash + Realoxy Firebase Auto Bulk Registration Bot
===========================================================
Features:
- Main Menu with Colorful Styled Inline Buttons & Animated Emojis (ZEROX_660_by_TgEmodziBot)
- 🚀 Auto Mode: Automatically extracts online devices & phone numbers from Firebase panels
- 📋 Firebase Panel Management: Add single/bulk URLs, upload .txt files, view and clear panels
- 💾 Persistent Storage: user_panels.json & bot_config.json
- ⭐ Global Phone Deduplication: SQLite Database tracks all processed numbers
- 📧 Configurable Email: Set once, used for all registrations without asking repeatedly
- ⚠️ Claim Limit Reached Auto-Detection: Stops & alerts admin to change email if limit hit
- ⏱ Minute-Rollover Sync: OTP submitted on the 1st second of the new minute
- 📱 Manual Mode: Single candidate registration with interactive terminal/chat input
"""

import sys
import os
import re
import json
import time
import base64
import sqlite3
import datetime
import asyncio
import logging
import requests
import warnings
import threading
from urllib.parse import urlparse, parse_qs
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.enums import ParseMode

warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Ensure UTF-8 console output on Windows
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ════════════════════════════════════════════════════════════════════
# Configuration & File Paths
# ════════════════════════════════════════════════════════════════════
BOT_TOKEN = "8796194701:AAH0Y-K14jdQJFA2zYc0TgWGozOU2n2rfQA"

TASKPAISA_URL = "https://gift.taskpaisa.com/api/public/campaigns/akash-register/leads"
TASKPAISA_REFERER = "https://gift.taskpaisa.com/camp/akash-register?rid=sharma"
ANTHE_BASE_URL = "https://antheaakash.com"

BASE_DIR = r"C:\Users\Dell\.gemini\antigravity-ide\scratch"
DB_PATH = os.path.join(BASE_DIR, "antheaakash.db")
CONFIG_FILE = os.path.join(BASE_DIR, "bot_config.json")
PANELS_FILE = os.path.join(BASE_DIR, "user_panels.json")

OTP_MAX_WAIT_SECONDS = 30
OTP_POLL_INTERVAL = 2
MAX_WORKERS = 30  # High-Speed Parallel Worker Threads (Upgraded from 20 to 30)
OTP_SENDER_PATTERNS = ["AAKASH", "AKASH", "ANTHE", "OTP", "VERIFY", ""]

# Custom Animated Emoji IDs from ZEROX_660_by_TgEmodziBot
EMOJI_CHECK = "6267008582294705964"      # ✅
EMOJI_CROSS = "6267000941547885720"      # 👎 / ❌
EMOJI_PARTY = "6267117038808870117"      # 🎉
EMOJI_FIRE = "6264785189394717307"       # 🔥
EMOJI_STAR = "6267118537752450044"       # 🌟
EMOJI_LIGHTNING = "6267107057304868214"  # ⚡️
EMOJI_HOURGLASS = "6267229004311303657"  # ⌛
EMOJI_ARROW = "6264699552041801361"      # ➡️
EMOJI_DIAMOND = "6264791387032523779"    # 💎
EMOJI_WARN = "6267039884016358504"       # ⚠️

def em(emoji_id: str, fallback: str = "•") -> str:
    """Format custom animated emoji tag for HTML parse mode."""
    return f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'


# ════════════════════════════════════════════════════════════════════
# Persistent Config (Per-User Storage)
# ════════════════════════════════════════════════════════════════════
def load_config() -> dict:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return {"users": {}}


def save_config(cfg: dict):
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        logging.error(f"Failed to save config: {e}")


def get_user_email(user_id: str) -> str:
    cfg = load_config()
    users = cfg.get("users", {})
    if isinstance(users, dict) and str(user_id) in users:
        u_info = users[str(user_id)]
        if isinstance(u_info, dict) and u_info.get("email"):
            return u_info["email"]
        elif isinstance(u_info, str):
            return u_info
    return cfg.get("active_email", "alexakijaiho5@gmail.com")


def set_user_email(user_id: str, email: str):
    cfg = load_config()
    if "users" not in cfg or not isinstance(cfg["users"], dict):
        cfg["users"] = {}
    cfg["users"][str(user_id)] = {
        "email": email,
        "updated_at": time.time()
    }
    save_config(cfg)


DEFAULT_BOOMLIFY_KEY = ""


def get_user_boomlify_key(user_id: str) -> str:
    cfg = load_config()
    users = cfg.get("users", {})
    if isinstance(users, dict) and str(user_id) in users:
        u_info = users[str(user_id)]
        if isinstance(u_info, dict) and u_info.get("boomlify_key"):
            return u_info["boomlify_key"]
    return cfg.get("boomlify_key", DEFAULT_BOOMLIFY_KEY)


def set_user_boomlify_key(user_id: str, key: str):
    cfg = load_config()
    if "users" not in cfg or not isinstance(cfg["users"], dict):
        cfg["users"] = {}
    if str(user_id) not in cfg["users"] or not isinstance(cfg["users"][str(user_id)], dict):
        cfg["users"][str(user_id)] = {}
    cfg["users"][str(user_id)]["boomlify_key"] = key.strip()
    save_config(cfg)


def is_user_boomlify_auto(user_id: str) -> bool:
    cfg = load_config()
    users = cfg.get("users", {})
    if isinstance(users, dict) and str(user_id) in users:
        u_info = users[str(user_id)]
        if isinstance(u_info, dict) and "boomlify_auto" in u_info:
            return bool(u_info["boomlify_auto"])
    return cfg.get("boomlify_auto", True)


def set_user_boomlify_auto(user_id: str, enabled: bool):
    cfg = load_config()
    if "users" not in cfg or not isinstance(cfg["users"], dict):
        cfg["users"] = {}
    if str(user_id) not in cfg["users"] or not isinstance(cfg["users"][str(user_id)], dict):
        cfg["users"][str(user_id)] = {}
    cfg["users"][str(user_id)]["boomlify_auto"] = bool(enabled)
    save_config(cfg)


def get_boomlify_credits(api_key: str):
    """Fetch live Boomlify credits/balance and account tier."""
    try:
        r = requests.get(
            "https://v1.boomlify.com/api/v1/account/credits",
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
            timeout=10
        )
        if r.status_code == 200:
            data = r.json()
            if data.get("success"):
                credits_info = data.get("credits", {})
                meta = data.get("meta", {})
                balance = credits_info.get("current_balance", 0)
                tier = meta.get("tier", "free").upper()
                return True, f"Tier: {tier} | Balance: {balance} credits"
        try:
            err = r.json()
            msg = err.get("message") or err.get("error") or r.text
        except Exception:
            msg = r.text
        return False, f"HTTP {r.status_code}: {msg}"
    except Exception as e:
        return False, f"Network Error: {e}"


def create_boomlify_email(api_key: str, time_tier: str = "10min"):
    """Create a temporary email using Boomlify API."""
    try:
        r = requests.post(
            "https://v1.boomlify.com/api/v1/emails/create",
            headers={"X-API-Key": api_key, "Content-Type": "application/json"},
            json={"time": time_tier},
            timeout=15
        )
        if r.status_code in (200, 201):
            data = r.json()
            if data.get("success") and "email" in data:
                email_obj = data["email"]
                return True, email_obj.get("address"), email_obj
        try:
            err = r.json()
            msg = err.get("message") or err.get("error") or r.text
        except Exception:
            msg = r.text
        return False, f"HTTP {r.status_code}: {msg}", None
    except Exception as e:
        return False, f"Network Error: {e}", None



# ════════════════════════════════════════════════════════════════════
# SQLite Database Setup & Deduplication
# ════════════════════════════════════════════════════════════════════
_db_lock = threading.Lock()

def init_db():
    with _db_lock:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT DEFAULT '',
                phone TEXT,
                email TEXT,
                status TEXT,
                details TEXT,
                panel_url TEXT,
                ts REAL
            )
        """)
        try:
            conn.execute("ALTER TABLE results ADD COLUMN user_id TEXT DEFAULT ''")
        except Exception:
            pass

        conn.execute("CREATE INDEX IF NOT EXISTS idx_phone ON results(phone)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_status ON results(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_user_id ON results(user_id)")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS vouchers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT DEFAULT '',
                phone TEXT,
                email TEXT,
                voucher_code TEXT,
                value TEXT,
                subject TEXT,
                raw_snippet TEXT,
                ts REAL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_vouchers_user_id ON vouchers(user_id)")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS boomlify_emails (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT DEFAULT '',
                email TEXT,
                boomlify_id TEXT,
                expires_at TEXT,
                ts REAL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_boomlify_user_id ON boomlify_emails(user_id)")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS registered_phones (
                phone TEXT PRIMARY KEY,
                status TEXT,
                reason TEXT,
                user_id TEXT DEFAULT '',
                ts REAL
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_reg_phones_phone ON registered_phones(phone)")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS processed_phones (
                phone TEXT PRIMARY KEY,
                first_seen REAL,
                last_seen REAL,
                status TEXT,
                count INTEGER DEFAULT 1
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_processed_phones_status ON processed_phones(status)")
        conn.commit()
        conn.close()


def log_result(phone, email, status, details="", panel_url="", user_id=""):
    with _db_lock:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.execute(
            "INSERT INTO results(user_id, phone, email, status, details, panel_url, ts) VALUES(?,?,?,?,?,?,?)",
            (str(user_id), phone, email, status, details, panel_url, time.time())
        )
        existing = conn.execute(
            "SELECT count, status FROM processed_phones WHERE phone=?", (phone,)
        ).fetchone()

        if existing:
            conn.execute(
                "UPDATE processed_phones SET last_seen=?, status=?, count=count+1 WHERE phone=?",
                (time.time(), status, phone)
            )
        else:
            conn.execute(
                "INSERT INTO processed_phones(phone, first_seen, last_seen, status, count) VALUES(?,?,?,?,1)",
                (phone, time.time(), time.time(), status)
            )
        conn.commit()
        conn.close()



def mark_phone_registered(phone: str, status: str = "success", reason: str = "", user_id: str = ""):
    """Permanently marks a phone number as registered/already exists in the dedicated database."""
    with _db_lock:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.execute(
            "INSERT OR REPLACE INTO registered_phones(phone, status, reason, user_id, ts) VALUES(?,?,?,?,?)",
            (str(phone).strip(), status, str(reason), str(user_id), time.time())
        )
        conn.commit()
        conn.close()


def is_phone_already_registered(phone: str) -> bool:
    """
    Checks if a phone number has ALREADY been registered, completed, or already exists on Aakash.
    Instantly skips the number to save time and prevent duplicate requests.
    """
    clean_ph = str(phone).strip()
    with _db_lock:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        # 1. Check dedicated registered_phones table
        row = conn.execute("SELECT 1 FROM registered_phones WHERE phone=?", (clean_ph,)).fetchone()
        if row:
            conn.close()
            return True

        # 2. Check results table for any success or already exists
        row2 = conn.execute(
            "SELECT 1 FROM results WHERE phone=? AND (status='success' OR details LIKE '%already%' OR details LIKE '%exists%')",
            (clean_ph,)
        ).fetchone()
        if row2:
            # Cache in registered_phones
            conn.execute(
                "INSERT OR REPLACE INTO registered_phones(phone, status, reason, ts) VALUES(?,?,?,?)",
                (clean_ph, "already_registered", "Cached from results", time.time())
            )
            conn.commit()
            conn.close()
            return True

        conn.close()
        return False


def is_phone_successful(phone):
    return is_phone_already_registered(phone)


def get_user_success_count(user_id: str) -> int:
    with _db_lock:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        count = conn.execute("SELECT COUNT(*) FROM results WHERE user_id=? AND status='success'", (str(user_id),)).fetchone()[0]
        conn.close()
        return count


def get_user_stats(user_id: str):
    with _db_lock:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        total = conn.execute("SELECT COUNT(*) FROM results WHERE user_id=?", (str(user_id),)).fetchone()[0]
        success = conn.execute("SELECT COUNT(*) FROM results WHERE user_id=? AND status='success'", (str(user_id),)).fetchone()[0]
        failed = conn.execute("SELECT COUNT(*) FROM results WHERE user_id=? AND status NOT IN ('success', 'already_used')", (str(user_id),)).fetchone()[0]
        already = conn.execute("SELECT COUNT(*) FROM results WHERE user_id=? AND status='already_used'", (str(user_id),)).fetchone()[0]
        conn.close()
        return total, success, failed, already


def get_success_count() -> int:
    with _db_lock:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        count = conn.execute("SELECT COUNT(*) FROM processed_phones WHERE status='success'").fetchone()[0]
        conn.close()
        return count




def is_boomlify_email_expired(user_id: str, email: str) -> bool:
    """Checks if a boomlify email is expired or has less than 90s remaining."""
    if not email:
        return True
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute(
            "SELECT expires_at, ts FROM boomlify_emails WHERE user_id = ? AND email = ? ORDER BY id DESC LIMIT 1",
            (user_id, email)
        )
        row = c.fetchone()
        conn.close()
        if not row:
            return True
        expires_at_str, created_ts = row
        now = time.time()
        if created_ts and (now - created_ts) > 480:  # > 8 minutes old
            return True
        if expires_at_str:
            try:
                exp_ts = datetime.datetime.fromisoformat(expires_at_str.replace("Z", "+00:00")).timestamp()
                if (exp_ts - now) < 90:
                    return True
            except Exception:
                pass
        return False
    except Exception:
        return True

def log_user_created_email(user_id: str, email: str, boomlify_id: str = "", expires_at: str = ""):
    with _db_lock:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        conn.execute(
            "INSERT INTO boomlify_emails(user_id, email, boomlify_id, expires_at, ts) VALUES(?,?,?,?,?)",
            (str(user_id), email, boomlify_id, str(expires_at), time.time())
        )
        conn.commit()
        conn.close()


def get_user_created_emails(user_id: str, limit: int = 15):
    with _db_lock:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        rows = conn.execute(
            "SELECT email, boomlify_id, expires_at, ts FROM boomlify_emails WHERE user_id=? ORDER BY id DESC LIMIT ?",
            (str(user_id), limit)
        ).fetchall()
        total = conn.execute(
            "SELECT COUNT(*) FROM boomlify_emails WHERE user_id=?", (str(user_id),)
        ).fetchone()[0]
        conn.close()
        return rows, total



def save_voucher(user_id: str, phone: str, email: str, voucher_code: str, value: str = "₹10.00", subject: str = "", raw_snippet: str = ""):
    with _db_lock:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        exists = conn.execute("SELECT 1 FROM vouchers WHERE voucher_code=?", (voucher_code,)).fetchone()
        if not exists:
            conn.execute(
                "INSERT INTO vouchers(user_id, phone, email, voucher_code, value, subject, raw_snippet, ts) VALUES(?,?,?,?,?,?,?,?)",
                (str(user_id), phone, email, voucher_code, value, subject, raw_snippet, time.time())
            )
            conn.commit()
        conn.close()


def get_user_vouchers(user_id: str, limit: int = 50):
    with _db_lock:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        rows = conn.execute(
            "SELECT phone, email, voucher_code, value, subject, ts FROM vouchers WHERE user_id=? ORDER BY id DESC LIMIT ?",
            (str(user_id), limit)
        ).fetchall()
        total_count = conn.execute(
            "SELECT COUNT(*) FROM vouchers WHERE user_id=?", (str(user_id),)
        ).fetchone()[0]
        conn.close()
        return rows, total_count


def get_user_latest_boomlify_id(user_id: str, email: str = "") -> str:
    with _db_lock:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        if email:
            row = conn.execute(
                "SELECT boomlify_id FROM boomlify_emails WHERE user_id=? AND email=? ORDER BY id DESC LIMIT 1",
                (str(user_id), email)
            ).fetchone()
        else:
            row = conn.execute(
                "SELECT boomlify_id FROM boomlify_emails WHERE user_id=? ORDER BY id DESC LIMIT 1",
                (str(user_id),)
            ).fetchone()
        conn.close()
        if row and row[0]:
            return row[0]
    return ""


def extract_voucher_details(text_content: str):
    """Extract Amazon Gift Card voucher code and amount from email text/html."""
    voucher_code = None
    value = "₹10.00"

    # Pattern 1: Exact format from TaskPaisa (e.g., BJDQ-N7RAQY-3XHD or WJJU-BRCFA7-UW8N)
    m = re.search(r'\b([A-Z0-9]{4}-[A-Z0-9]{4,8}-[A-Z0-9]{4})\b', text_content)
    if m:
        voucher_code = m.group(1).strip()
    else:
        # Pattern 2: Look after Voucher number header
        m2 = re.search(r'Voucher\s+number[\s\r\n:]+([A-Z0-9]{4,}[A-Z0-9\-]*)', text_content, re.IGNORECASE)
        if m2 and m2.group(1).lower() != 'is':
            voucher_code = m2.group(1).strip()

    # Amount / Value (handling both unicode ₹, Rs, and raw numbers)
    vm = re.search(r'Value[\s:]*(?:₹|\u20b9|Rs\.?)*[\s]*([0-9]+(?:\.[0-9]+)?)', text_content, re.IGNORECASE)
    if vm:
        value = f"₹{vm.group(1).strip()}"

    return voucher_code, value


def fetch_boomlify_messages(api_key: str, email_id: str):
    """Fetch messages for a Boomlify email ID."""
    try:
        url = f"https://v1.boomlify.com/api/v1/emails/{email_id}/messages"
        r = requests.get(url, headers={"X-API-Key": api_key, "Content-Type": "application/json"}, timeout=10)
        if r.status_code == 200:
            data = r.json()
            if data.get("success"):
                return True, data.get("messages", [])
        return False, []
    except Exception as e:
        return False, []


async def poll_voucher_for_success(bot: Bot, chat_id: int, user_id: str, phone: str, email: str, max_wait_sec: int = 15):
    """Poll Boomlify email inbox for up to max_wait_sec (default 10s) to extract Amazon voucher."""
    email_id = get_user_latest_boomlify_id(user_id, email)
    if not email_id:
        logging.info(f"No Boomlify email_id found for user {user_id} and email {email}")
        return None

    api_key = get_user_boomlify_key(user_id)
    # If email_id not in local DB, fetch from Boomlify API active emails list
    if not email_id:
        try:
            r_list = requests.get("https://v1.boomlify.com/api/v1/emails", headers={"X-API-Key": api_key}, timeout=8)
            if r_list.status_code == 200:
                for em_item in r_list.json().get("emails", []):
                    if em_item.get("address", "").lower() == email.lower():
                        email_id = em_item.get("id")
                        break
        except Exception:
            pass

    if not email_id:
        logging.info(f"No Boomlify email_id found for user {user_id} and email {email}")
        return None

    start_t = time.time()
    seen_msg_ids = set()

    logging.info(f"Polling Boomlify email {email} ({email_id}) for voucher up to {max_wait_sec}s...")
    while (time.time() - start_t) < max_wait_sec:
        ok, msgs = await asyncio.to_thread(fetch_boomlify_messages, api_key, email_id)
        if ok and msgs:
            for m in msgs:
                m_id = m.get("id") or m.get("subject")
                if m_id in seen_msg_ids:
                    continue
                seen_msg_ids.add(m_id)

                subject = m.get("subject", "")
                # Boomlify API returns body_text and body_html!
                text_content = m.get("body_text") or m.get("body_html") or m.get("text") or m.get("html") or m.get("snippet") or ""
                combined_text = f"{subject}\n{text_content}"

                v_code, v_val = extract_voucher_details(combined_text)
                if v_code:
                    save_voucher(user_id, phone, email, v_code, v_val, subject, text_content[:200])
                    await bot.send_message(
                        chat_id,
                        f"<blockquote>\n"
                        f"{em(EMOJI_PARTY, '🎉')} <b>AMAZON GIFT CARD RECEIVED!</b> {em(EMOJI_FIRE, '🔥')}\n\n"
                        f"📱 <b>Mobile:</b> <code>+91 {phone}</code>\n"
                        f"📧 <b>Email:</b> <code>{email}</code>\n"
                        f"💰 <b>Value:</b> <b>{v_val}</b>\n\n"
                        f"🎟 <b>Voucher Code:</b>\n"
                        f"<code>{v_code}</code>\n\n"
                        f"<i>Tap on code to copy! Saved to 'Your Vouchers' menu.</i>\n"
                        f"</blockquote>"
                    )
                    return v_code
                else:
                    await bot.send_message(
                        chat_id,
                        f"<blockquote>\n"
                        f"📩 <b>New Email Received on:</b> <code>{email}</code>\n"
                        f"<b>Subject:</b> {subject}\n\n"
                        f"<i>{text_content[:200]}</i>\n"
                        f"</blockquote>"
                    )
        await asyncio.sleep(2)

    return None


def get_phone_stats():
    with _db_lock:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        total_phones = conn.execute("SELECT COUNT(*) FROM processed_phones").fetchone()[0]
        success = conn.execute("SELECT COUNT(*) FROM processed_phones WHERE status='success'").fetchone()[0]
        failed = conn.execute("SELECT COUNT(*) FROM processed_phones WHERE status NOT IN ('success', 'already_used')").fetchone()[0]
        already = conn.execute("SELECT COUNT(*) FROM processed_phones WHERE status='already_used'").fetchone()[0]
        duplicates = conn.execute("SELECT COUNT(*) FROM processed_phones WHERE count > 1").fetchone()[0]
        conn.close()
        return total_phones, success, failed, already, duplicates


init_db()


# ════════════════════════════════════════════════════════════════════
# Persistent Firebase Panel Storage (user_panels.json)
# ════════════════════════════════════════════════════════════════════
_panels_lock = threading.Lock()

def load_panels() -> dict:
    with _panels_lock:
        if os.path.exists(PANELS_FILE):
            try:
                with open(PANELS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data.get("user_panels", {})
            except Exception as e:
                logging.error(f"Error loading panels: {e}")
        return {}


def save_panels(panels_data: dict) -> bool:
    with _panels_lock:
        try:
            with open(PANELS_FILE, "w", encoding="utf-8") as f:
                json.dump({"user_panels": panels_data, "updated_at": time.time()}, f, indent=2)
            return True
        except Exception as e:
            logging.error(f"Error saving panels: {e}")
            return False


def parse_firebase_link(link: str) -> str | None:
    link = link.strip()
    if link.startswith(("http://", "https://")) and (
        "firebaseio.com" in link or "firebasedatabase.app" in link
    ):
        return link.rstrip("/") + "/"
    parsed = urlparse(link)
    qs = parse_qs(parsed.query)
    encoded = qs.get("s", [None])[0]
    if not encoded:
        return None
    try:
        encoded += "=" * (-len(encoded) % 4)
        decoded = base64.b64decode(encoded).decode("utf-8").split("|")[0].strip()
        if "firebaseio.com" not in decoded and "firebasedatabase.app" not in decoded:
            return None
        return decoded.rstrip("/") + "/"
    except Exception:
        return None



def add_user_panels_bulk(user_id: str, parsed_urls: list[str]) -> tuple[int, int]:
    """Adds multiple URLs in a single file I/O operation. Returns (added_count, skipped_dup_count)."""
    panels_data = load_panels()
    user_id_str = str(user_id)
    if user_id_str not in panels_data:
        panels_data[user_id_str] = []

    existing_pending = {
        p["url"] for p in panels_data[user_id_str] if not p.get("processed", False)
    }

    added = 0
    skipped = 0
    base_ts = time.time()

    for idx, url in enumerate(parsed_urls):
        if url in existing_pending:
            skipped += 1
        else:
            panels_data[user_id_str].append({
                "url": url,
                "added_at": base_ts,
                "processed": False,
                "id": int(base_ts * 1000) + idx
            })
            existing_pending.add(url)
            added += 1

    if added > 0:
        save_panels(panels_data)

    return added, skipped

def add_user_panel_persistent(user_id: str, panel_url: str) -> bool:
    panels_data = load_panels()
    user_id_str = str(user_id)
    if user_id_str not in panels_data:
        panels_data[user_id_str] = []

    for panel in panels_data[user_id_str]:
        if panel["url"] == panel_url and not panel.get("processed", False):
            return False

    panels_data[user_id_str].append({
        "url": panel_url,
        "added_at": time.time(),
        "processed": False,
        "id": int(time.time() * 1000)
    })
    save_panels(panels_data)
    return True


def get_pending_panels_persistent(user_id: str) -> list[tuple[int, str]]:
    panels_data = load_panels()
    user_id_str = str(user_id)
    if user_id_str not in panels_data:
        return []
    pending = []
    for panel in panels_data[user_id_str]:
        if not panel.get("processed", False):
            pending.append((panel.get("id", 0), panel["url"]))
    return pending


def get_total_panels_persistent(user_id: str) -> tuple[int, int]:
    panels_data = load_panels()
    user_id_str = str(user_id)
    if user_id_str not in panels_data:
        return 0, 0
    total = len(panels_data[user_id_str])
    pending = sum(1 for p in panels_data[user_id_str] if not p.get("processed", False))
    return total, pending


def mark_panel_processed_persistent(user_id: str, panel_id: int):
    panels_data = load_panels()
    user_id_str = str(user_id)
    if user_id_str not in panels_data:
        return
    for panel in panels_data[user_id_str]:
        if panel.get("id") == panel_id:
            panel["processed"] = True
            panel["processed_at"] = time.time()
            save_panels(panels_data)
            return


def clear_panels_persistent(user_id: str) -> bool:
    panels_data = load_panels()
    user_id_str = str(user_id)
    if user_id_str not in panels_data:
        return False
    panels_data[user_id_str] = [p for p in panels_data[user_id_str] if p.get("processed", False)]
    save_panels(panels_data)
    return True


# ════════════════════════════════════════════════════════════════════
# Firebase Data Extraction Helpers
# ════════════════════════════════════════════════════════════════════
def is_online_device(data):
    if not isinstance(data, dict):
        return False
    for key in ("status", "state", "online", "isOnline", "connected", "isConnected"):
        val = data.get(key)
        if val is True or val == 1:
            return True
        if isinstance(val, str) and val.strip().lower() in {"true", "online", "connected", "active", "ready"}:
            return True
    return False


def extract_phone_from_messages(device_messages):
    patterns = [
        (re.compile(r'\b(?:\+91|91|0)?([6-9]\d{9})\b'), 10),
        (re.compile(r'\b(?:phone|mobile|number)[\s:]*([6-9]\d{9})\b', re.IGNORECASE), 15),
        (re.compile(r'[^0-9]([6-9]\d{9})[^0-9]'), 5),
    ]
    counts = Counter()
    for msg in device_messages.values():
        if not isinstance(msg, dict):
            continue
        text = str(msg.get("body") or msg.get("message") or msg.get("text") or "")
        for pattern, score in patterns:
            for num in pattern.findall(text):
                counts[num] += score
    if not counts:
        return None
    return counts.most_common(1)[0][0]


def fetch_devices_and_phones(firebase_url: str) -> list[dict]:
    try:
        c_req = requests.get(f"{firebase_url.rstrip('/')}/clients.json", timeout=5)
        c_req.raise_for_status()
        clients_data = c_req.json() or {}
    except Exception as e:
        logging.debug(f"Firebase clients unreachable for {firebase_url}: {e}")
        return []

    if not isinstance(clients_data, dict):
        return []

    online_devices = [c_id for c_id, c_data in clients_data.items() if is_online_device(c_data)]
    if not online_devices:
        return []

    try:
        m_req = requests.get(f"{firebase_url.rstrip('/')}/messages.json", timeout=6)
        m_req.raise_for_status()
        messages_data = m_req.json() or {}
    except Exception as e:
        logging.debug(f"Firebase messages unreachable for {firebase_url}: {e}")
        messages_data = {}

    result = []
    seen = set()

    for c_id in online_devices:
        device_messages = messages_data.get(str(c_id), {}) if isinstance(messages_data, dict) else {}
        phone = extract_phone_from_messages(device_messages)
        if phone and phone not in seen:
            seen.add(phone)
            result.append({"client_id": c_id, "phone": phone, "firebase_url": firebase_url})

    return result


def extract_otp_from_messages(device_messages, trigger_time_ms):
    """
    Searches for 4-digit OTP from recent messages in Firebase.
    Target format: 'Dear User, your One-Time Password (OTP) is 4701 Please enter it to proceed -Aakash Institute'
    """
    for msg_id in reversed(list(device_messages.keys())):
        msg_data = device_messages[msg_id]
        if not isinstance(msg_data, dict):
            continue
        try:
            msg_ts = int(msg_id)
            if msg_ts < (trigger_time_ms - 30000):
                continue
        except (ValueError, TypeError):
            pass

        body = str(msg_data.get("body") or msg_data.get("message") or msg_data.get("text") or "")

        # 1. Exact Aakash OTP pattern: "One-Time Password (OTP) is 4701"
        match = re.search(r'One-Time Password\s*(?:\(OTP\))?\s*is\s*(\d{4})', body, re.IGNORECASE)
        if match:
            return match.group(1)

        # 2. Aakash Institute OTP pattern: "your One-Time Password ... is 4701"
        match = re.search(r'(?:One-Time Password|OTP|code)\s*(?:is)?\s*[:\s]*(\d{4})\b', body, re.IGNORECASE)
        if match and any(k in body.lower() for k in ["aakash", "akash", "anthe", "institute"]):
            return match.group(1)

        # 3. If body mentions Aakash or ANTHE or Institute, find 4 digits
        if any(keyword in body.lower() for keyword in ["aakash", "akash", "anthe", "institute"]):
            match = re.search(r'(?<!\d)(\d{4})(?!\d)', body)
            if match:
                return match.group(0)

        # 4. General OTP pattern
        match = re.search(r'(?:OTP|code)\s*(?:is)?\s*[:\s]*(\d{4})\b', body, re.IGNORECASE)
        if match:
            return match.group(1)

    return None


def poll_for_otp_sync(firebase_url: str, client_id: str, trigger_time_ms: int, max_wait: int = OTP_MAX_WAIT_SECONDS) -> str | None:
    start_time = time.time()
    while (time.time() - start_time) < max_wait:
        time.sleep(OTP_POLL_INTERVAL)
        try:
            r = requests.get(f"{firebase_url.rstrip('/')}/messages/{client_id}.json", timeout=10)
            messages = r.json()
            if isinstance(messages, dict):
                otp = extract_otp_from_messages(messages, trigger_time_ms)
                if otp:
                    return otp
        except Exception:
            pass
    return None


# ════════════════════════════════════════════════════════════════════
# Core Registration Automation
# ════════════════════════════════════════════════════════════════════
def submit_lead(phone: str, email: str, rid: str = "sharma") -> dict:
    headers = {
        "content-type": "application/json",
        "origin": "https://gift.taskpaisa.com",
        "referer": f"https://gift.taskpaisa.com/camp/akash-register?rid={rid}",
        "user-agent": "Mozilla/5.0 (Linux; Android 16; V2338 Build/BP2A.250605.031.A3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.8059.46 Mobile Safari/537.36"
    }
    payload = {"email": email, "phone": phone, "rid": rid}
    try:
        r = requests.post(TASKPAISA_URL, json=payload, headers=headers, timeout=15)
        try:
            return r.json()
        except Exception:
            return {"status_code": r.status_code, "text": r.text}
    except Exception as e:
        return {"error": str(e)}


def start_session_and_send_otp(phone: str, redirect_url: str = None) -> tuple[bool, str, object]:
    target_url = ANTHE_BASE_URL
    if redirect_url:
        full_redir = f"https://gift.taskpaisa.com{redirect_url}" if redirect_url.startswith("/") else redirect_url
        try:
            # Pre-resolve redirect chain in Python (2-3s) to prevent Chrome from hanging on tracking network hops
            r = requests.get(full_redir, allow_redirects=True, timeout=8, headers={
                "User-Agent": "Mozilla/5.0 (Linux; Android 16; V2338 Build/BP2A.250605.031.A3) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/155.0.8059.46 Mobile Safari/537.36"
            })
            if r.url and "antheaakash" in r.url:
                target_url = r.url
            else:
                target_url = full_redir
        except Exception:
            target_url = full_redir

    options = uc.ChromeOptions()
    options.add_argument("--window-size=1280,800")
    options.add_argument("--log-level=3")
    options.add_argument("--disable-logging")
    options.page_load_strategy = "eager"  # Return immediately when DOM is interactive

    driver = None
    try:
        try:
            driver = uc.Chrome(options=options, version_main=155)
        except Exception:
            driver = uc.Chrome(options=options)

        driver.set_page_load_timeout(25)

        try:
            driver.get(target_url)
        except Exception:
            pass  # If page load timed out but DOM is interactive, continue

        time.sleep(1.5)

        # Wait up to 15s for phone input to be located
        inp = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.ID, "phoneInput"))
        )
        inp.clear()
        inp.send_keys(phone)
        time.sleep(0.5)

        btn = driver.find_element(By.ID, "sendOtpBtn")
        btn.click()

        for _ in range(25):
            time.sleep(1)
            try:
                otp_step = driver.find_element(By.ID, "reg-step-otp")
                if "is-active" in otp_step.get_attribute("class"):
                    return True, "OTP successfully sent.", driver

                err_el = driver.find_element(By.ID, "phoneError")
                if err_el.text:
                    err_msg = err_el.text
                    clean_driver(driver)
                    return False, err_msg, None
            except Exception:
                pass

        clean_driver(driver)
        return False, "OTP send request timed out.", None
    except Exception as e:
        clean_driver(driver)
        return False, str(e), None


def verify_otp_in_browser(driver, otp: str) -> tuple[bool, str]:
    try:
        otp_clean = str(otp).strip()[:4]
        # Use JavaScript injection to set all 4 OTP boxes atomically and trigger input/change events
        js_fill = """
            let otp = arguments[0];
            let boxes = document.querySelectorAll('#otpRow .otp-box');
            if (!boxes || boxes.length === 0) {
                boxes = document.querySelectorAll('input.otp-box, input[type="tel"], input[maxlength="1"]');
            }
            for (let i = 0; i < boxes.length && i < otp.length; i++) {
                boxes[i].focus();
                boxes[i].value = otp[i];
                boxes[i].dispatchEvent(new Event('input', { bubbles: true }));
                boxes[i].dispatchEvent(new Event('change', { bubbles: true }));
            }
            let verifyBtn = document.getElementById('verifyBtn');
            if (verifyBtn) {
                verifyBtn.disabled = false;
            }
            return Array.from(boxes).map(b => b.value).join('');
        """
        filled = driver.execute_script(js_fill, otp_clean)
        logging.info(f"Verified OTP boxes set via JS: '{filled}' vs expected: '{otp_clean}'")
        time.sleep(0.5)

        # Click verify button via JS and fallback to element click
        driver.execute_script("""
            let verifyBtn = document.getElementById('verifyBtn');
            if (verifyBtn) {
                verifyBtn.disabled = false;
                verifyBtn.click();
            }
        """)

        for _ in range(25):
            time.sleep(1)
            try:
                success_step = driver.find_element(By.ID, "reg-step-success")
                if "is-active" in success_step.get_attribute("class"):
                    return True, "Registration successful. Candidate profile link sent via SMS."

                err_el = driver.find_element(By.ID, "otpError")
                if err_el.text:
                    return False, err_el.text
            except Exception:
                pass

        return False, "OTP verification timed out."
    except Exception as e:
        return False, str(e)


def clean_driver(driver):
    if not driver:
        return
    try:
        pid = getattr(driver, "browser_pid", None)
        try:
            driver.quit()
        except Exception:
            pass
        if pid:
            os.system(f"taskkill /F /T /PID {pid} >nul 2>&1")
    except Exception:
        pass


# ════════════════════════════════════════════════════════════════════
# Auto Mode Worker Task
# ════════════════════════════════════════════════════════════════════
auto_mode_active = {}  # chat_id -> bool
active_drivers = {}    # user_id -> driver


async def run_auto_processing(chat_id: int, bot: Bot):
    """Processes pending Firebase panels in Auto Mode."""
    user_id = str(chat_id)
    auto_mode_active[chat_id] = True
    user_email = get_user_email(user_id)

    try:
        panels = get_pending_panels_persistent(user_id)
        if not panels:
            await bot.send_message(
                chat_id,
                f"<blockquote>\n"
                f"{em(EMOJI_WARN, '⚠️')} <b>Koi Pending Panel Nahi Hai!</b>\n\n"
                f"Kripya pehle <b>Manage Firebase Panels</b> button par click karke panel URLs add karein.\n"
                f"</blockquote>"
            )
            return

        total, pending = get_total_panels_persistent(user_id)
        await bot.send_message(
            chat_id,
            f"<blockquote>\n"
            f"{em(EMOJI_FIRE, '🚀')} <b>AUTO MODE STARTED!</b>\n\n"
            f"• <b>User ID:</b> <code>{user_id}</code>\n"
            f"• <b>Active Email:</b> <code>{user_email}</code>\n"
            f"• <b>Total Panels:</b> {total}\n"
            f"• <b>Pending Panels:</b> {pending}\n"
            f"• <b>Deduplication:</b> Enabled (Skips already registered numbers)\n"
            f"• <b>Minute-Rollover Sync:</b> Active\n\n"
            f"<i>Panels ek-ek karke process ho rahe hain...</i>\n"
            f"</blockquote>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🛑 Stop Auto Mode", callback_data="stop_auto_mode", style="danger", icon_custom_emoji_id=EMOJI_CROSS)
            ]])
        )

        dash_msg = None
        last_dash_edit = 0.0
        scanned_count = 0
        skipped_empty_count = 0
        initial_total = pending

        while auto_mode_active.get(chat_id, False):
            pending_list = get_pending_panels_persistent(user_id)
            if not pending_list:
                if dash_msg:
                    try:
                        await dash_msg.delete()
                    except Exception:
                        pass
                await bot.send_message(
                    chat_id,
                    f"<blockquote>\n"
                    f"{em(EMOJI_PARTY, '🎉')} <b>ALL PANELS COMPLETED!</b>\n\n"
                    f"Sabhi panels successfully check aur process ho chuke hain.\n"
                    f"🎯 Your Total Success: <b>{get_user_success_count(user_id)}</b>\n"
                    f"</blockquote>",
                    reply_markup=get_main_menu_kb()
                )
                break

            panel_id, panel_url = pending_list[0]
            clean_name = panel_url.split("//")[-1].split(".")[0][:30]
            scanned_count += 1

            # Update live scanning dashboard every 2.5s (Anti-spam rate limiting)
            now_t = time.time()
            if dash_msg is None or (now_t - last_dash_edit) >= 2.5:
                dash_text = (
                    f"<blockquote>\n"
                    f"{em(EMOJI_FIRE, '🚀')} <b>AUTO MODE RUNNING</b>\n\n"
                    f"📦 <b>Scanning Panels:</b> <b>{scanned_count}</b> / {initial_total}\n"
                    f"⏭️ <b>Offline/Empty Skipped:</b> {skipped_empty_count}\n"
                    f"🎯 <b>Total Successful:</b> <b>{get_user_success_count(user_id)}</b>\n"
                    f"🔍 <b>Current:</b> <code>{clean_name}</code>\n\n"
                    f"<i>Anti-spam active: Inactive panels ko silently skip kiya ja raha hai taaki bot spam ya freeze na ho.</i>\n"
                    f"</blockquote>"
                )
                try:
                    if dash_msg is None:
                        dash_msg = await bot.send_message(
                            chat_id,
                            dash_text,
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                InlineKeyboardButton(text="🛑 Stop Auto Mode", callback_data="stop_auto_mode", style="danger", icon_custom_emoji_id=EMOJI_CROSS)
                            ]])
                        )
                    else:
                        await dash_msg.edit_text(
                            dash_text,
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                InlineKeyboardButton(text="🛑 Stop Auto Mode", callback_data="stop_auto_mode", style="danger", icon_custom_emoji_id=EMOJI_CROSS)
                            ]])
                        )
                    last_dash_edit = now_t
                except Exception:
                    pass

            devices = await asyncio.to_thread(fetch_devices_and_phones, panel_url)

            if not devices:
                skipped_empty_count += 1
                mark_panel_processed_persistent(user_id, panel_id)
                await asyncio.sleep(0.05)
                continue

            # Deduplication
            new_devices = []
            skipped_count = 0
            for d in devices:
                ph = d["phone"]
                if is_phone_successful(ph):
                    skipped_count += 1
                else:
                    new_devices.append(d)

            if not new_devices:
                skipped_empty_count += 1
                mark_panel_processed_persistent(user_id, panel_id)
                await asyncio.sleep(0.05)
                continue

            # Active online device found! Alert user with full card
            dash_msg = None  # Reset dashboard so new status will generate after this panel
            await bot.send_message(
                chat_id,
                f"<blockquote>\n"
                f"{em(EMOJI_DIAMOND, '💎')} <b>Active Devices Found!</b>\n"
                f"Panel: <code>{clean_name}</code>\n\n"
                f"• Total Online Devices: <b>{len(devices)}</b>\n"
                f"• Skipped (Already Registered): <b>{skipped_count}</b>\n"
                f"• New Numbers to Register: <b>{len(new_devices)}</b>\n"
                f"</blockquote>"
            )

            for idx, d in enumerate(new_devices, 1):
                if not auto_mode_active.get(chat_id, False):
                    break

                phone = d["phone"]
                client_id = d["client_id"]

                # Ensure active email is NOT expired before lead submission
                if is_user_boomlify_auto(user_id):
                    if is_boomlify_email_expired(user_id, user_email):
                        bkey = get_user_boomlify_key(user_id)
                        logging.info(f"Email {user_email} expired/near expiry. Generating fresh Boomlify email before lead...")
                        b_ok, fresh_mail, mail_meta = await asyncio.to_thread(create_boomlify_email, bkey)
                        if b_ok and fresh_mail:
                            user_email = fresh_mail
                            set_user_email(user_id, fresh_mail)
                            b_id = mail_meta.get("id", "") if mail_meta else ""
                            b_exp = mail_meta.get("expires_at", "") if mail_meta else ""
                            log_user_created_email(user_id, fresh_mail, b_id, b_exp)
                            logging.info(f"Auto-refreshed email to {fresh_mail} (ID: {b_id})")

                # Live progress message updated at each step
                prog_msg = await bot.send_message(
                    chat_id,
                    f"<blockquote>\n"
                    f"📱 <b>[{idx}/{len(new_devices)}] Processing:</b> <code>+91 {phone}</code>\n\n"
                    f"⏳ <b>Step 1:</b> Submitting TaskPaisa Campaign Lead (<code>{user_email}</code>)...\n"
                    f"</blockquote>"
                )

                # 1. Submit lead with configured email
                lead_res = await asyncio.to_thread(submit_lead, phone, user_email)
                logging.info(f"Auto mode lead result for {phone}: {lead_res}")

                if lead_res.get("claimLimitReached") is True or lead_res.get("status") == "REDIRECTED":
                    if is_user_boomlify_auto(user_id):
                        bkey = get_user_boomlify_key(user_id)
                        await bot.send_message(
                            chat_id,
                            f"<blockquote>\n"
                            f"{em(EMOJI_WARN, '⚠️')} <b>Email Claim Limit Reached:</b> <code>{user_email}</code>\n"
                            f"{em(EMOJI_LIGHTNING, '⚡️')} <i>Boomlify Auto Enabled! Generating fresh disposable email...</i>\n"
                            f"</blockquote>"
                        )
                        b_ok, new_mail_or_err, mail_meta = await asyncio.to_thread(create_boomlify_email, bkey)
                        if b_ok:
                            new_email = new_mail_or_err
                            set_user_email(user_id, new_email)
                            b_id = mail_meta.get("id", "") if mail_meta else ""
                            b_exp = mail_meta.get("expires_at", "") if mail_meta else ""
                            log_user_created_email(user_id, new_email, b_id, b_exp)
                            user_email = new_email
                            await bot.send_message(
                                chat_id,
                                f"<blockquote>\n"
                                f"{em(EMOJI_CHECK, '✅')} <b>New Boomlify Email Created & Activated:</b>\n"
                                f"📧 <code>{new_email}</code>\n"
                                f"⏳ <i>Resubmitting TaskPaisa Campaign Lead immediately...</i>\n"
                                f"</blockquote>"
                            )
                            # Retry lead submission with the fresh email
                            lead_res = await asyncio.to_thread(submit_lead, phone, user_email)
                            logging.info(f"Auto mode lead retry result for {phone} with {new_email}: {lead_res}")
                            if lead_res.get("claimLimitReached") is True or lead_res.get("status") == "REDIRECTED":
                                await bot.send_message(
                                    chat_id,
                                    f"<blockquote>\n"
                                    f"{em(EMOJI_WARN, '⚠️')} <b>Limit still reached even with newly created email!</b>\n"
                                    f"Email: <code>{user_email}</code>\n"
                                    f"Pausing Auto Mode for manual inspection.\n"
                                    f"</blockquote>",
                                    reply_markup=get_main_menu_kb()
                                )
                                auto_mode_active[chat_id] = False
                                return
                        else:
                            await bot.send_message(
                                chat_id,
                                f"<blockquote>\n"
                                f"{em(EMOJI_CROSS, '✖')} <b>Boomlify API Error:</b>\n"
                                f"<code>{new_mail_or_err}</code>\n\n"
                                f"⚠️ <i>Could not auto-generate new email. Auto Mode is paused. Check credits / API Key.</i>\n"
                                f"</blockquote>",
                                reply_markup=get_main_menu_kb()
                            )
                            auto_mode_active[chat_id] = False
                            return
                    else:
                        await bot.send_message(
                            chat_id,
                            f"<blockquote>\n"
                            f"{em(EMOJI_WARN, '⚠️')} <b>AUTO MODE PAUSED: Claim Limit Reached!</b>\n\n"
                            f"Email: <code>{user_email}</code>\n"
                            f"<i>This email address has used all claims available for this campaign.</i>\n\n"
                            f"Kripya <b>Change Email</b> button par click karke naya email dalein ya Boomlify Auto enable karein.\n"
                            f"</blockquote>",
                            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                                InlineKeyboardButton(text="Change Email Now", callback_data="cmd_set_email", style="primary", icon_custom_emoji_id=EMOJI_STAR),
                                InlineKeyboardButton(text="Cancel", callback_data="cmd_cancel", style="danger", icon_custom_emoji_id=EMOJI_CROSS)
                            ]])
                        )
                        auto_mode_active[chat_id] = False
                        return

                redirect_url = lead_res.get("redirectUrl")

                try:
                    await prog_msg.edit_text(
                        f"<blockquote>\n"
                        f"📱 <b>[{idx}/{len(new_devices)}] Processing:</b> <code>+91 {phone}</code>\n\n"
                        f"{em(EMOJI_CHECK, '✔')} <b>Step 1:</b> Lead Captured ({lead_res.get('status', 'OK')})\n"
                        f"⏳ <b>Step 2:</b> Opening registration page & requesting OTP...\n"
                        f"</blockquote>"
                    )
                except Exception:
                    pass

                # 2. Start browser session and send OTP
                trigger_time = int(time.time() * 1000)
                success, msg, driver = await asyncio.to_thread(start_session_and_send_otp, phone, redirect_url)

                if not success or not driver:
                    is_already = ("already" in msg.lower() or "exists" in msg.lower())
                    status_tag = "already_registered" if is_already else "failed"
                    if is_already:
                        mark_phone_registered(phone, "already_exists", msg, user_id=user_id)

                    log_result(phone, user_email, status_tag, msg, panel_url, user_id=user_id)
                    try:
                        badge = "Already Registered (Saved to DB)" if is_already else f"Step 2 Failed: {msg}"
                        await prog_msg.edit_text(
                            f"<blockquote>\n"
                            f"📱 <b>[{idx}/{len(new_devices)}] Processing:</b> <code>+91 {phone}</code>\n\n"
                            f"{em(EMOJI_CHECK, '✔')} <b>Step 1:</b> Lead Captured\n"
                            f"{em(EMOJI_CROSS, '✖')} <b>{badge}</b>\n\n"
                            f"⏭️ <i>Skipping & proceeding to next number...</i>\n"
                            f"</blockquote>"
                        )
                    except Exception:
                        pass
                    continue

                try:
                    await prog_msg.edit_text(
                        f"<blockquote>\n"
                        f"📱 <b>[{idx}/{len(new_devices)}] Processing:</b> <code>+91 {phone}</code>\n\n"
                        f"{em(EMOJI_CHECK, '✔')} <b>Step 1:</b> Lead Captured\n"
                        f"{em(EMOJI_CHECK, '✔')} <b>Step 2:</b> OTP Sent to <code>+91 {phone}</code>\n"
                        f"⏳ <b>Step 3:</b> Polling Firebase for OTP (Max 30s wait)...\n"
                        f"</blockquote>"
                    )
                except Exception:
                    pass

                # 3. Auto-poll Firebase messages for 4-digit OTP (Strictly 30 seconds max)
                otp = await asyncio.to_thread(poll_for_otp_sync, panel_url, client_id, trigger_time, 30)

                if not otp:
                    clean_driver(driver)
                    log_result(phone, user_email, "otp_timeout", "No OTP received within 30s", panel_url, user_id=user_id)
                    try:
                        await prog_msg.edit_text(
                            f"<blockquote>\n"
                            f"📱 <b>[{idx}/{len(new_devices)}] Processing:</b> <code>+91 {phone}</code>\n\n"
                            f"{em(EMOJI_CHECK, '✔')} <b>Step 1:</b> Lead Captured\n"
                            f"{em(EMOJI_CHECK, '✔')} <b>Step 2:</b> OTP Sent\n"
                            f"{em(EMOJI_WARN, '⚠️')} <b>Step 3:</b> OTP Timeout (30s) — No SMS in Firebase.\n\n"
                            f"⏭️ <i>Skipping & proceeding to next number...</i>\n"
                            f"</blockquote>"
                        )
                    except Exception:
                        pass
                    continue

                # 4. Minute Rollover Sync
                now = datetime.datetime.now()
                secs_until_next_minute = (60.0 - now.second - (now.microsecond / 1_000_000.0)) + 0.5
                if secs_until_next_minute < 1.0:
                    secs_until_next_minute += 60.0
                # Cap rollover wait to max 20 seconds to prevent OTP expiring on Aakash server
                if secs_until_next_minute > 20.0:
                    secs_until_next_minute = 1.0

                try:
                    await prog_msg.edit_text(
                        f"<blockquote>\n"
                        f"📱 <b>[{idx}/{len(new_devices)}] Processing:</b> <code>+91 {phone}</code>\n\n"
                        f"{em(EMOJI_CHECK, '✔')} <b>Step 1:</b> Lead Captured\n"
                        f"{em(EMOJI_CHECK, '✔')} <b>Step 2:</b> OTP Sent\n"
                        f"{em(EMOJI_CHECK, '✔')} <b>Step 3:</b> OTP Fetched: <code>{otp}</code>\n"
                        f"⏱ <b>Step 4:</b> Minute Rollover Sync: Waiting {int(secs_until_next_minute)}s for new minute 1st second...\n"
                        f"</blockquote>"
                    )
                except Exception:
                    pass

                # Interruptible sleep so 'Stop Auto Mode' works instantly
                for _ in range(int(secs_until_next_minute)):
                    if not auto_mode_active.get(chat_id, False):
                        clean_driver(driver)
                        return
                    await asyncio.sleep(1)

                if not auto_mode_active.get(chat_id, False):
                    clean_driver(driver)
                    return

                # 5. Verify OTP
                submit_time = datetime.datetime.now().strftime("%I:%M:%S %p")
                ok, res_msg = await asyncio.to_thread(verify_otp_in_browser, driver, otp)
                clean_driver(driver)

                if ok:
                    mark_phone_registered(phone, "success", res_msg, user_id=user_id)
                    log_result(phone, user_email, "success", res_msg, panel_url, user_id=user_id)
                    user_success = get_user_success_count(user_id)
                    try:
                        await prog_msg.edit_text(
                            f"<blockquote>\n"
                            f"{em(EMOJI_PARTY, '🎉')} <b>REGISTRATION SUCCESSFUL!</b>\n\n"
                            f"📱 <b>Mobile:</b> <code>+91 {phone}</code>\n"
                            f"📧 <b>Email:</b> <code>{user_email}</code>\n"
                            f"🔑 <b>OTP:</b> <code>{otp}</code> (Verified at {submit_time} {em(EMOJI_CHECK, '✔')})\n"
                            f"🎯 <b>Your Total Successful:</b> <code>{user_success}</code>\n\n"
                            f"⏳ <i>Checking Boomlify mail for Amazon Voucher (max 15s)...</i>\n"
                            f"</blockquote>"
                        )
                    except Exception:
                        pass
                    # Check email inbox for Amazon Voucher up to 10s
                    await poll_voucher_for_success(bot, chat_id, user_id, phone, user_email, max_wait_sec=15)
                else:
                    log_result(phone, user_email, "verify_failed", res_msg, panel_url, user_id=user_id)
                    try:
                        await prog_msg.edit_text(
                            f"<blockquote>\n"
                            f"📱 <b>[{idx}/{len(new_devices)}]</b> <code>+91 {phone}</code>\n\n"
                            f"{em(EMOJI_CROSS, '✖')} <b>Verification Failed:</b> {res_msg}\n"
                            f"⏭️ <i>Moving to next number...</i>\n"
                            f"</blockquote>"
                        )
                    except Exception:
                        pass

            mark_panel_processed_persistent(user_id, panel_id)

    finally:
        auto_mode_active[chat_id] = False


# ════════════════════════════════════════════════════════════════════
# Inline Keyboards
# ════════════════════════════════════════════════════════════════════
def get_main_menu_kb() -> InlineKeyboardMarkup:
    btn_auto = InlineKeyboardButton(
        text="🚀 Auto Mode (Start Processing)",
        callback_data="cmd_start_auto",
        style="success",
        icon_custom_emoji_id=EMOJI_FIRE,
    )
    btn_boomlify = InlineKeyboardButton(
        text="⚡️ Boomlify Auto Mail",
        callback_data="cmd_boomlify_menu",
        style="primary",
        icon_custom_emoji_id=EMOJI_LIGHTNING,
    )
    btn_panels = InlineKeyboardButton(
        text="📋 Manage Firebase Panels",
        callback_data="cmd_panels_menu",
        style="primary",
        icon_custom_emoji_id=EMOJI_DIAMOND,
    )
    btn_manual = InlineKeyboardButton(
        text="📱 Manual Register Number",
        callback_data="cmd_register",
        style="primary",
        icon_custom_emoji_id=EMOJI_ARROW,
    )
    btn_set_email = InlineKeyboardButton(
        text="📧 Set / Change Email",
        callback_data="cmd_set_email",
        style="primary",
        icon_custom_emoji_id=EMOJI_STAR,
    )
    btn_stats = InlineKeyboardButton(
        text="📊 Statistics & Success Count",
        callback_data="cmd_stats",
        style="success",
        icon_custom_emoji_id=EMOJI_CHECK,
    )
    btn_vouchers = InlineKeyboardButton(
        text="🎁 Your Vouchers",
        callback_data="cmd_view_vouchers",
        style="success",
        icon_custom_emoji_id=EMOJI_PARTY,
    )
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn_auto],
        [btn_boomlify, btn_vouchers],
        [btn_panels],
        [btn_manual],
        [btn_set_email],
        [btn_stats]
    ])


def get_boomlify_menu_kb(is_auto: bool = True) -> InlineKeyboardMarkup:
    toggle_text = "🟢 Auto-Create on Limit: ON" if is_auto else "🔴 Auto-Create on Limit: OFF"
    btn_gen = InlineKeyboardButton(
        text="⚡️ Generate New Email Now",
        callback_data="cmd_boomlify_gen_now",
        style="success",
        icon_custom_emoji_id=EMOJI_FIRE,
    )
    btn_toggle = InlineKeyboardButton(
        text=toggle_text,
        callback_data="cmd_boomlify_toggle",
        style="primary",
        icon_custom_emoji_id=EMOJI_CHECK if is_auto else EMOJI_CROSS,
    )
    btn_set_key = InlineKeyboardButton(
        text="🔑 Update Boomlify API Key",
        callback_data="cmd_boomlify_set_key",
        style="primary",
        icon_custom_emoji_id=EMOJI_STAR,
    )
    btn_history = InlineKeyboardButton(
        text="📜 Created Emails History",
        callback_data="cmd_boomlify_history",
        style="primary",
        icon_custom_emoji_id=EMOJI_DIAMOND,
    )
    btn_back = InlineKeyboardButton(
        text="🔙 Back to Main Menu",
        callback_data="cmd_main_menu",
        style="success",
        icon_custom_emoji_id=EMOJI_ARROW,
    )
    return InlineKeyboardMarkup(inline_keyboard=[
        [btn_gen],
        [btn_toggle],
        [btn_set_key],
        [btn_history],
        [btn_back]
    ])


def get_panels_menu_kb() -> InlineKeyboardMarkup:
    btn_add = InlineKeyboardButton(
        text="➕ Add Panels (Paste URLs)",
        callback_data="cmd_add_panel_prompt",
        style="primary",
        icon_custom_emoji_id=EMOJI_ARROW,
    )
    btn_view = InlineKeyboardButton(
        text="📋 View Pending Panels",
        callback_data="cmd_view_panels",
        style="primary",
        icon_custom_emoji_id=EMOJI_DIAMOND,
    )
    btn_clear = InlineKeyboardButton(
        text="🗑 Clear Pending Panels",
        callback_data="cmd_clear_panels",
        style="danger",
        icon_custom_emoji_id=EMOJI_CROSS,
    )
    btn_back = InlineKeyboardButton(
        text="🔙 Back to Main Menu",
        callback_data="cmd_main_menu",
        style="success",
        icon_custom_emoji_id=EMOJI_STAR,
    )
    return InlineKeyboardMarkup(inline_keyboard=[[btn_add], [btn_view], [btn_clear], [btn_back]])


def get_cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Cancel", callback_data="cmd_cancel", style="danger", icon_custom_emoji_id=EMOJI_CROSS)
    ]])


def get_limit_reached_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Change Email Now", callback_data="cmd_set_email", style="primary", icon_custom_emoji_id=EMOJI_STAR)],
        [InlineKeyboardButton(text="Cancel", callback_data="cmd_cancel", style="danger", icon_custom_emoji_id=EMOJI_CROSS)]
    ])


def get_success_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Register Another Number", callback_data="cmd_register", style="primary", icon_custom_emoji_id=EMOJI_ARROW)
    ]])


# ════════════════════════════════════════════════════════════════════
# FSM State & Bot Initialization
# ════════════════════════════════════════════════════════════════════
class BotState(StatesGroup):
    waiting_for_phone = State()
    waiting_for_otp = State()
    waiting_for_admin_email = State()
    waiting_for_panel_urls = State()
    waiting_for_boomlify_key = State()


bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())


# ════════════════════════════════════════════════════════════════════
# Bot Commands & Handlers
# ════════════════════════════════════════════════════════════════════
@dp.message(CommandStart())
async def handle_start(message: Message, state: FSMContext):
    await state.clear()
    uid = str(message.from_user.id)
    total, pending = get_total_panels_persistent(uid)
    user_email = get_user_email(uid)
    email_display = user_email if user_email else "Not Set ⚠️"
    user_success = get_user_success_count(uid)

    text = (
        f"<blockquote>\n"
        f"{em(EMOJI_FIRE, '🔥')} <b>ANTHE Aakash + Realoxy Bulk Bot</b> {em(EMOJI_FIRE, '🔥')}\n\n"
        f"Automated Registration & Firebase OTP Processing System.\n\n"
        f"👤 <b>User ID:</b> <code>{uid}</code>\n"
        f"📧 <b>Your Email:</b> <code>{email_display}</code>\n"
        f"📋 <b>Your Panels:</b> <b>{total}</b> total (<b>{pending}</b> pending)\n"
        f"🎯 <b>Your Total Success:</b> <b>{user_success}</b>\n\n"
        f"{em(EMOJI_DIAMOND, '💎')} <b>Features:</b>\n"
        f"• Isolated panels & email per user\n"
        f"• Auto Mode with Firebase online device extraction\n"
        f"• Global phone deduplication (No repeat registrations)\n"
        f"• Minute-Rollover sync on OTP verification\n"
        f"</blockquote>\n\n"
        f"Niche diye gaye menu se action select karein:"
    )
    await message.answer(text, reply_markup=get_main_menu_kb())


@dp.callback_query(F.data == "cmd_main_menu")
async def handle_back_main(query: CallbackQuery, state: FSMContext):
    await query.answer()
    await state.clear()
    uid = str(query.from_user.id)
    total, pending = get_total_panels_persistent(uid)
    user_email = get_user_email(uid)
    email_display = user_email if user_email else "Not Set ⚠️"
    user_success = get_user_success_count(uid)

    text = (
        f"<blockquote>\n"
        f"{em(EMOJI_LIGHTNING, '⚡️')} <b>Main Menu</b>\n\n"
        f"👤 <b>User ID:</b> <code>{uid}</code>\n"
        f"📧 <b>Your Email:</b> <code>{email_display}</code>\n"
        f"📋 <b>Your Panels:</b> <b>{total}</b> total (<b>{pending}</b> pending)\n"
        f"🎯 <b>Your Total Success:</b> <b>{user_success}</b>\n"
        f"</blockquote>"
    )
    try:
        await query.message.edit_text(text, reply_markup=get_main_menu_kb())
    except Exception:
        await query.message.answer(text, reply_markup=get_main_menu_kb())


@dp.callback_query(F.data == "cmd_cancel")
async def handle_cancel(query: CallbackQuery, state: FSMContext):
    await query.answer()
    await state.clear()
    uid = query.from_user.id
    if uid in active_drivers:
        clean_driver(active_drivers.pop(uid))

    text = (
        f"<blockquote>\n"
        f"{em(EMOJI_CROSS, '✖')} <b>Process Cancelled.</b>\n"
        f"</blockquote>"
    )
    try:
        await query.message.edit_text(text, reply_markup=get_main_menu_kb())
    except Exception:
        await query.message.answer(text, reply_markup=get_main_menu_kb())


# ════════════════════════════════════════════════════════════════════
# Firebase Panel Management Handlers
# ════════════════════════════════════════════════════════════════════
@dp.callback_query(F.data == "cmd_panels_menu")
async def handle_panels_menu(query: CallbackQuery):
    await query.answer()
    uid = str(query.from_user.id)
    total, pending = get_total_panels_persistent(uid)

    text = (
        f"<blockquote>\n"
        f"{em(EMOJI_DIAMOND, '💎')} <b>Firebase Panels Management</b>\n\n"
        f"• Total Saved Panels: <b>{total}</b>\n"
        f"• Pending to Process: <b>{pending}</b>\n\n"
        f"Aap ek saath multiple Firebase URLs paste kar sakte hain ya <b>.txt file</b> chat mein send kar sakte hain!\n"
        f"</blockquote>"
    )
    try:
        await query.message.edit_text(text, reply_markup=get_panels_menu_kb())
    except Exception:
        await query.message.answer(text, reply_markup=get_panels_menu_kb())


@dp.callback_query(F.data == "cmd_add_panel_prompt")
async def handle_add_panel_prompt(query: CallbackQuery, state: FSMContext):
    await query.answer()
    await state.set_state(BotState.waiting_for_panel_urls)
    text = (
        f"<blockquote>\n"
        f"{em(EMOJI_ARROW, '➡️')} <b>Firebase Panel URL(s) Bhejein:</b>\n\n"
        f"Aap ek URL ya multiple URLs (ek line me ek) chat me paste karein ya <b>.txt file</b> upload karein:\n\n"
        f"<i>Example:</i>\n"
        f"<code>https://panel1.firebaseio.com/</code>\n"
        f"<code>https://panel2.firebaseio.com/</code>\n"
        f"</blockquote>"
    )
    try:
        await query.message.edit_text(text, reply_markup=get_cancel_kb())
    except Exception:
        await query.message.answer(text, reply_markup=get_cancel_kb())


@dp.message(Command("addpanel"))
async def handle_addpanel_cmd(message: Message):
    text_content = message.text or ""
    parts = re.split(r"[/]addpanel(?:@\w+)?\s*", text_content, maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer(
            f"<blockquote>\n"
            f"{em(EMOJI_WARN, '⚠️')} <b>Usage:</b>\n"
            f"/addpanel https://your-panel.firebaseio.com/\n\n"
            f"Or paste multiple URLs (one per line):\n"
            f"/addpanel https://panel1.firebaseio.com/\n"
            f"https://panel2.firebaseio.com/\n"
            f"</blockquote>"
        )
        return
    await process_bulk_urls(message, parts[1].strip())


@dp.message(BotState.waiting_for_panel_urls, F.text)
async def handle_panel_urls_text(message: Message, state: FSMContext):
    await state.clear()
    await process_bulk_urls(message, message.text.strip())


@dp.message(F.document)
async def handle_document_upload(message: Message, state: FSMContext):
    doc = message.document
    if not doc.file_name.lower().endswith(".txt"):
        await message.answer(f"<blockquote>{em(EMOJI_WARN, '⚠️')} Kripya valid .txt file upload karein.</blockquote>")
        return

    try:
        file = await bot.get_file(doc.file_id)
        file_bytes = await bot.download_file(file.file_path)
        content = file_bytes.read().decode("utf-8", errors="ignore")
        await state.clear()
        await process_bulk_urls(message, content)
    except Exception as e:
        await message.answer(f"<blockquote>{em(EMOJI_CROSS, '✖')} File reading error: {e}</blockquote>")


async def process_bulk_urls(message: Message, raw_text: str):
    user_id = str(message.from_user.id)
    # Split by newlines, spaces, commas, or tabs to handle any paste format
    raw_tokens = re.split(r'[\r\n\s,]+', raw_text.strip())
    tokens = [t.strip() for t in raw_tokens if t.strip()]

    added = 0
    skipped_dup = 0
    invalid_count = 0

    valid_urls = []
    for raw in tokens:
        parsed = parse_firebase_link(raw)
        if parsed:
            valid_urls.append(parsed)
        else:
            invalid_count += 1

    added, skipped_dup = add_user_panels_bulk(user_id, valid_urls)

    total, pending = get_total_panels_persistent(user_id)
    text = (
        f"<blockquote>\n"
        f"{em(EMOJI_CHECK, '✅')} <b>Panel Import Results:</b>\n\n"
        f"• Added New Panels: <b>{added}</b>\n"
        f"• Skipped (Duplicate): <b>{skipped_dup}</b>\n"
        f"• Invalid URLs: <b>{invalid_count}</b>\n\n"
        f"📋 Total Panels in Queue: <b>{total}</b> (Pending: <b>{pending}</b>)\n"
        f"</blockquote>"
    )
    await message.answer(text, reply_markup=get_panels_menu_kb())


@dp.callback_query(F.data == "cmd_view_panels")
async def handle_view_panels(query: CallbackQuery):
    await query.answer()
    uid = str(query.from_user.id)
    panels = get_pending_panels_persistent(uid)
    total, pending = get_total_panels_persistent(uid)

    if not panels:
        text = f"<blockquote>📋 Koi pending panel nahi hai.\nTotal Saved: <b>{total}</b></blockquote>"
    else:
        text = f"<blockquote>📋 <b>Pending Panels ({len(panels)} of {total}):</b>\n\n"
        for i, (pid, url) in enumerate(panels[:15], 1):
            text += f"{i}. <code>{url[:50]}...</code>\n"
        if len(panels) > 15:
            text += f"\n... aur {len(panels) - 15} more panels"
        text += "</blockquote>"

    try:
        await query.message.edit_text(text, reply_markup=get_panels_menu_kb())
    except Exception:
        await query.message.answer(text, reply_markup=get_panels_menu_kb())


@dp.callback_query(F.data == "cmd_clear_panels")
async def handle_clear_panels(query: CallbackQuery):
    await query.answer()
    uid = str(query.from_user.id)
    clear_panels_persistent(uid)
    text = f"<blockquote>{em(EMOJI_CHECK, '✅')} Sabhi pending panels clear kar diye gaye hain.</blockquote>"
    try:
        await query.message.edit_text(text, reply_markup=get_panels_menu_kb())
    except Exception:
        await query.message.answer(text, reply_markup=get_panels_menu_kb())


# ════════════════════════════════════════════════════════════════════
# Auto Mode Trigger
# ════════════════════════════════════════════════════════════════════
@dp.callback_query(F.data == "cmd_start_auto")
async def handle_start_auto(query: CallbackQuery):
    await query.answer()
    chat_id = query.message.chat.id
    uid = str(query.from_user.id)

    if auto_mode_active.get(chat_id, False):
        await query.message.answer(f"<blockquote>{em(EMOJI_WARN, '⚠️')} Aapka Auto Mode pehle se hi chal raha hai!</blockquote>")
        return

    user_email = get_user_email(uid)
    if not user_email:
        await query.message.answer(
            f"<blockquote>{em(EMOJI_WARN, '⚠️')} Kripya pehle <b>Set / Change Email</b> button se apna email set karein!</blockquote>",
            reply_markup=get_main_menu_kb()
        )
        return

    asyncio.create_task(run_auto_processing(chat_id, bot))


@dp.callback_query(F.data == "stop_auto_mode")
async def handle_stop_auto(query: CallbackQuery):
    await query.answer("🛑 Auto Mode Stopped!")
    chat_id = query.message.chat.id
    auto_mode_active[chat_id] = False
    try:
        await query.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await query.message.answer(
        f"<blockquote>\n"
        f"{em(EMOJI_CROSS, '🛑')} <b>Auto Mode Stopped Successfully.</b>\n"
        f"Sabhi active workers aur tasks turant stop kar diye gaye hain.\n"
        f"</blockquote>",
        reply_markup=get_main_menu_kb()
    )


# ════════════════════════════════════════════════════════════════════
# Set / Change Email Handlers (Per User)
# ════════════════════════════════════════════════════════════════════
@dp.callback_query(F.data == "cmd_set_email")
async def handle_set_email_start(query: CallbackQuery, state: FSMContext):
    await query.answer()
    await state.clear()
    await state.set_state(BotState.waiting_for_admin_email)
    uid = str(query.from_user.id)
    current_email = get_user_email(uid)

    text = (
        f"<blockquote>\n"
        f"{em(EMOJI_STAR, '🌟')} <b>Set / Change Your Campaign Email:</b>\n\n"
        f"👤 <b>User ID:</b> <code>{uid}</code>\n"
        f"Current Email: <code>{current_email}</code>\n\n"
        f"Kripya apna naya <b>Email ID</b> chat mein send karein:\n"
        f"<i>(Yeh email sirf aapke user account ke liye save hoga).</i>\n"
        f"</blockquote>"
    )
    try:
        await query.message.edit_text(text, reply_markup=get_cancel_kb())
    except Exception:
        await query.message.answer(text, reply_markup=get_cancel_kb())


@dp.message(BotState.waiting_for_admin_email)
async def handle_admin_email_save(message: Message, state: FSMContext):
    email = message.text.strip()
    uid = str(message.from_user.id)

    if "@" not in email or "." not in email:
        await message.answer(
            f"<blockquote>\n"
            f"{em(EMOJI_WARN, '⚠️')} <b>Invalid Email Format!</b>\n"
            f"Kripya valid email address send karein (jaise: name@gmail.com)\n"
            f"</blockquote>",
            reply_markup=get_cancel_kb()
        )
        return

    set_user_email(uid, email)
    await state.clear()

    text = (
        f"<blockquote>\n"
        f"{em(EMOJI_CHECK, '✅')} <b>Email Successfully Saved!</b>\n\n"
        f"👤 <b>User ID:</b> <code>{uid}</code>\n"
        f"Naya Active Email: <code>{email}</code>\n\n"
        f"Ab aapki sabhi registrations isi email ID se execute hongi.\n"
        f"</blockquote>"
    )
    await message.answer(text, reply_markup=get_main_menu_kb())


# ════════════════════════════════════════════════════════════════════
# Manual Registration Handler (Per User)
# ════════════════════════════════════════════════════════════════════
@dp.callback_query(F.data == "cmd_register")
async def handle_register_start(query: CallbackQuery, state: FSMContext):
    await query.answer()
    await state.clear()
    uid = str(query.from_user.id)
    if query.from_user.id in active_drivers:
        clean_driver(active_drivers.pop(query.from_user.id))

    user_email = get_user_email(uid)
    if not user_email:
        await state.set_state(BotState.waiting_for_admin_email)
        text = (
            f"<blockquote>\n"
            f"{em(EMOJI_WARN, '⚠️')} <b>Email Set Nahi Hai!</b>\n\n"
            f"Kripya pehle ek Email ID chat me send karein:\n"
            f"</blockquote>"
        )
        try:
            await query.message.edit_text(text, reply_markup=get_cancel_kb())
        except Exception:
            await query.message.answer(text, reply_markup=get_cancel_kb())
        return

    await state.set_state(BotState.waiting_for_phone)
    text = (
        f"<blockquote>\n"
        f"{em(EMOJI_FIRE, '🔥')} <b>Manual Candidate Registration</b>\n\n"
        f"👤 <b>User ID:</b> <code>{uid}</code>\n"
        f"📧 <b>Your Email:</b> <code>{user_email}</code>\n\n"
        f"Kripya candidate ka <b>10-digit Indian Mobile Number</b> chat me send karein:\n"
        f"<i>(Example: 9876543210)</i>\n"
        f"</blockquote>"
    )
    try:
        await query.message.edit_text(text, reply_markup=get_cancel_kb())
    except Exception:
        await query.message.answer(text, reply_markup=get_cancel_kb())


@dp.message(BotState.waiting_for_phone)
async def handle_phone_input(message: Message, state: FSMContext):
    raw_phone = message.text.strip().replace("+91", "").replace(" ", "").replace("-", "")
    uid = str(message.from_user.id)
    user_email = get_user_email(uid)

    if len(raw_phone) != 10 or not raw_phone.isdigit() or raw_phone[0] in "012345":
        await message.answer(
            f"<blockquote>\n"
            f"{em(EMOJI_WARN, '⚠️')} <b>Invalid Mobile Number!</b>\n"
            f"Kripya valid 10-digit Indian Mobile Number dalein jo 6, 7, 8, ya 9 se shuru hota ho.\n"
            f"</blockquote>",
            reply_markup=get_cancel_kb()
        )
        return

    await state.update_data(phone=raw_phone, email=user_email, user_id=uid)
    await process_manual_otp_sending(message, state, raw_phone, user_email, uid)


async def process_manual_otp_sending(msg: Message, state: FSMContext, phone: str, email: str, uid: str = ""):
    status_msg = await msg.answer(
        f"<blockquote>\n"
        f"{em(EMOJI_HOURGLASS, '⏳')} <b>Processing Registration...</b>\n\n"
        f"• <b>TaskPaisa Lead:</b> Submitting email (<code>{email}</code>)...\n"
        f"• <b>Referral Link:</b> Following tracking redirect chain...\n"
        f"• <b>Security:</b> Bypassing Cloudflare Turnstile...\n"
        f"• <b>SMS Gateway:</b> Requesting OTP on +91 {phone}...\n\n"
        f"<i>Kripya 5-10 seconds wait karein...</i>\n"
        f"</blockquote>"
    )

    lead_res = await asyncio.to_thread(submit_lead, phone, email)
    logging.info(f"TaskPaisa lead submission response: {lead_res}")

    if lead_res.get("claimLimitReached") is True or lead_res.get("status") == "REDIRECTED":
        if is_user_boomlify_auto(uid):
            bkey = get_user_boomlify_key(uid)
            try:
                await status_msg.edit_text(
                    f"<blockquote>\n"
                    f"{em(EMOJI_WARN, '⚠️')} <b>Claim Limit Reached on:</b> <code>{email}</code>\n"
                    f"{em(EMOJI_LIGHTNING, '⚡️')} <i>Boomlify Auto Enabled! Generating fresh disposable email...</i>\n"
                    f"</blockquote>"
                )
            except Exception:
                pass
            b_ok, new_mail_or_err, mail_meta = await asyncio.to_thread(create_boomlify_email, bkey)
            if b_ok:
                email = new_mail_or_err
                set_user_email(uid, email)
                b_id = mail_meta.get("id", "") if mail_meta else ""
                b_exp = mail_meta.get("expires_at", "") if mail_meta else ""
                log_user_created_email(uid, email, b_id, b_exp)
                try:
                    await status_msg.edit_text(
                        f"<blockquote>\n"
                        f"{em(EMOJI_CHECK, '✅')} <b>New Boomlify Email Activated:</b> <code>{email}</code>\n"
                        f"⏳ <i>Resubmitting TaskPaisa Campaign Lead...</i>\n"
                        f"</blockquote>"
                    )
                except Exception:
                    pass
                lead_res = await asyncio.to_thread(submit_lead, phone, email)
                logging.info(f"Manual lead retry result with {email}: {lead_res}")
                if lead_res.get("claimLimitReached") is True or lead_res.get("status") == "REDIRECTED":
                    await state.clear()
                    await status_msg.edit_text(
                        f"<blockquote>\n"
                        f"{em(EMOJI_WARN, '⚠️')} <b>Campaign Claim Limit reached even with new email!</b>\n"
                        f"Email: <code>{email}</code>\n"
                        f"</blockquote>",
                        reply_markup=get_limit_reached_kb()
                    )
                    return
            else:
                await state.clear()
                await status_msg.edit_text(
                    f"<blockquote>\n"
                    f"{em(EMOJI_CROSS, '✖')} <b>Boomlify Error:</b>\n"
                    f"<code>{new_mail_or_err}</code>\n"
                    f"</blockquote>",
                    reply_markup=get_limit_reached_kb()
                )
                return
        else:
            await state.clear()
            limit_text = (
                f"<blockquote>\n"
                f"{em(EMOJI_WARN, '⚠️')} <b>Claim Limit Reached for this Email!</b>\n\n"
                f"Email: <code>{email}</code>\n"
                f"<i>This email address has used all claims available for this campaign.</i>\n\n"
                f"Kripya <b>Change Email Now</b> par click karke naya Email set karein.\n"
                f"</blockquote>"
            )
            await status_msg.edit_text(limit_text, reply_markup=get_limit_reached_kb())
            return

    redirect_url = lead_res.get("redirectUrl")
    success, result_msg, driver = await asyncio.to_thread(start_session_and_send_otp, phone, redirect_url)

    if success and driver:
        chat_id = msg.chat.id
        active_drivers[chat_id] = driver
        await state.set_state(BotState.waiting_for_otp)

        success_text = (
            f"<blockquote>\n"
            f"{em(EMOJI_CHECK, '✅')} <b>OTP SENT SUCCESSFULLY!</b>\n\n"
            f"📱 <b>Mobile:</b> <code>+91 {phone}</code>\n"
            f"📧 <b>Email:</b> <code>{email}</code> (Campaign Lead Verified {em(EMOJI_CHECK, '✔')})\n"
            f"🔗 <b>TaskPaisa Status:</b> {lead_res.get('status', 'CAPTURED')} (Tracking Linked {em(EMOJI_CHECK, '✔')})\n\n"
            f"{em(EMOJI_LIGHTNING, '⚡️')} Mobile par <b>4-digit OTP</b> aa gaya hoga.\n"
            f"Kripya OTP code chat me type karke send karein:\n"
            f"<i>(Note: OTP aate hi minute rollover sync ke 1st sec par submit hoga).</i>\n"
            f"</blockquote>"
        )
        await status_msg.edit_text(success_text, reply_markup=get_cancel_kb())
    else:
        await state.clear()
        fail_text = (
            f"<blockquote>\n"
            f"{em(EMOJI_CROSS, '✖')} <b>OTP Send Failed!</b>\n\n"
            f"<b>Server Response:</b> {result_msg}\n\n"
            f"<i>Number pehle se registered ho sakta hai ya network issue ho sakta hai.</i>\n"
            f"</blockquote>"
        )
        await status_msg.edit_text(fail_text, reply_markup=get_main_menu_kb())


@dp.message(BotState.waiting_for_otp)
async def handle_manual_otp_verification(message: Message, state: FSMContext):
    otp = message.text.strip()

    if len(otp) != 4 or not otp.isdigit():
        await message.answer(
            f"<blockquote>{em(EMOJI_WARN, '⚠️')} Kripya 4-digit numeric OTP dalein jo mobile par aaya hai.</blockquote>",
            reply_markup=get_cancel_kb()
        )
        return

    uid = message.from_user.id
    driver = active_drivers.get(uid)

    if not driver:
        await state.clear()
        await message.answer(f"<blockquote>{em(EMOJI_WARN, '⚠️')} Session expire ho gaya. Kripya shuru se karein.</blockquote>", reply_markup=get_main_menu_kb())
        return

    data = await state.get_data()
    phone = data.get("phone")
    email = data.get("email")
    user_id = data.get("user_id", str(uid))

    now = datetime.datetime.now()
    secs_until_next_minute = (60.0 - now.second - (now.microsecond / 1_000_000.0)) + 0.5
    if secs_until_next_minute < 1.0:
        secs_until_next_minute += 60.0

    target_time = now + datetime.timedelta(seconds=secs_until_next_minute)

    waiting_msg = await message.answer(
        f"<blockquote>\n"
        f"{em(EMOJI_HOURGLASS, '⏳')} <b>OTP Received: <code>{otp}</code></b>\n\n"
        f"⏱ <b>Minute Rollover Sync Active:</b>\n"
        f"• Current Clock: <code>{now.strftime('%I:%M:%S %p')}</code>\n"
        f"• Submit Time: <code>{target_time.strftime('%I:%M:01 %p')}</code>\n"
        f"• Waiting: <b>{int(secs_until_next_minute)} seconds...</b>\n\n"
        f"<i>Jaise hi minute change hoga (1st second par), turant OTP server par submit ho jayega!</i>\n"
        f"</blockquote>"
    )

    await asyncio.sleep(secs_until_next_minute)
    submit_time = datetime.datetime.now().strftime("%I:%M:%S %p")

    ok, result_msg = await asyncio.to_thread(verify_otp_in_browser, driver, otp)
    clean_driver(driver)
    active_drivers.pop(uid, None)
    await state.clear()

    if ok:
        mark_phone_registered(phone, "success", result_msg, user_id=user_id)
        log_result(phone, email, "success", result_msg, "manual", user_id=user_id)
        u_success = get_user_success_count(user_id)
        success_text = (
            f"<blockquote>\n"
            f"{em(EMOJI_PARTY, '🎉')} <b>REGISTRATION SUCCESSFUL!</b> {em(EMOJI_PARTY, '🎉')}\n\n"
            f"📱 <b>Mobile:</b> <code>+91 {phone}</code>\n"
            f"📧 <b>Email:</b> <code>{email}</code> (Registered Lead {em(EMOJI_CHECK, '✔')})\n"
            f"🔑 <b>OTP:</b> <code>{otp}</code> (Verified at <code>{submit_time}</code> {em(EMOJI_CHECK, '✔')})\n"
            f"🎯 <b>Your Total Success:</b> <code>{u_success}</code>\n\n"
            f"{em(EMOJI_STAR, '🌟')} <b>Message:</b> Registration successful. Candidate profile link SMS ke zariye bhej diya gaya hai.\n\n"
            f"⏳ <i>Checking Boomlify mail for Amazon Voucher (max 15s)...</i>\n"
            f"</blockquote>"
        )
        await waiting_msg.edit_text(success_text, reply_markup=get_success_kb())
        await poll_voucher_for_success(message.bot, message.chat.id, user_id, phone, email, max_wait_sec=15)
    else:
        log_result(phone, email, "verify_failed", result_msg, "manual", user_id=user_id)
        fail_text = (
            f"<blockquote>\n"
            f"{em(EMOJI_CROSS, '✖')} <b>Verification Failed!</b>\n\n"
            f"<b>Server Error:</b> {result_msg}\n\n"
            f"Kripya OTP check karke dobara try karein.\n"
            f"</blockquote>"
        )
        await waiting_msg.edit_text(fail_text, reply_markup=get_main_menu_kb())


# ════════════════════════════════════════════════════════════════════
# Statistics Handler (Per User)
# ════════════════════════════════════════════════════════════════════
@dp.callback_query(F.data == "cmd_stats")
async def handle_stats(query: CallbackQuery):
    await query.answer()
    uid = str(query.from_user.id)
    u_total, u_success, u_failed, u_already = get_user_stats(uid)
    total_panels, pending_panels = get_total_panels_persistent(uid)
    user_email = get_user_email(uid)
    g_phones, g_success, g_failed, g_already, g_dups = get_phone_stats()

    text = (
        f"<blockquote>\n"
        f"{em(EMOJI_STAR, '📊')} <b>Your Account Statistics</b>\n\n"
        f"👤 <b>User ID:</b> <code>{uid}</code>\n"
        f"📧 <b>Your Email:</b> <code>{user_email}</code>\n\n"
        f"🎯 <b>Your Success:</b> <code>{u_success}</code>\n"
        f"📱 <b>Your Total Processed:</b> <code>{u_total}</code>\n"
        f"⏭️ <b>Already Registered (Skipped):</b> <code>{u_already}</code>\n"
        f"✖ <b>Failed:</b> <code>{u_failed}</code>\n"
        f"📋 <b>Your Panels:</b> <b>{total_panels}</b> total (<b>{pending_panels}</b> pending)\n\n"
        f"🌐 <b>Global Bot Totals:</b>\n"
        f"• Total Success: <code>{g_success}</code>\n"
        f"• Total Phones: <code>{g_phones}</code>\n"
        f"</blockquote>"
    )
    try:
        await query.message.edit_text(text, reply_markup=get_main_menu_kb())
    except Exception:
        await query.message.answer(text, reply_markup=get_main_menu_kb())


# ════════════════════════════════════════════════════════════════════
# Boomlify Temp Mail Handlers
# ════════════════════════════════════════════════════════════════════
@dp.callback_query(F.data == "cmd_boomlify_menu")
async def handle_boomlify_menu(query: CallbackQuery, state: FSMContext):
    await query.answer()
    await state.clear()
    uid = str(query.from_user.id)
    key = get_user_boomlify_key(uid)
    is_auto = is_user_boomlify_auto(uid)
    active_email = get_user_email(uid)
    _, total_created = get_user_created_emails(uid, limit=1)

    # Fetch live account credits asynchronously
    ok, cred_text = await asyncio.to_thread(get_boomlify_credits, key)
    masked_key = (key[:8] + "..." + key[-4:]) if len(key) > 15 else key
    auto_status_badge = "🟢 <b>ENABLED</b> (Auto creates new email when limit hits)" if is_auto else "🔴 <b>DISABLED</b> (Manual email entry only)"

    text = (
        f"<blockquote>\n"
        f"{em(EMOJI_LIGHTNING, '⚡️')} <b>Boomlify Auto Temp Mail Control Hub</b>\n\n"
        f"🔑 <b>API Key:</b> <code>{masked_key}</code>\n"
        f"💰 <b>Credits / Tier:</b> {cred_text}\n"
        f"📧 <b>Current Active Email:</b> <code>{active_email}</code>\n"
        f"🔄 <b>Auto-Create on Limit:</b> {auto_status_badge}\n"
        f"📜 <b>Total Emails Created:</b> <b>{total_created}</b>\n\n"
        f"💡 <i>Jab bhi registration me 'Claim Limit Reached' error aayega, ye bot automatically Boomlify se naya email generate karke lead register kar dega!</i>\n"
        f"</blockquote>"
    )
    try:
        await query.message.edit_text(text, reply_markup=get_boomlify_menu_kb(is_auto))
    except Exception:
        await query.message.answer(text, reply_markup=get_boomlify_menu_kb(is_auto))


@dp.callback_query(F.data == "cmd_boomlify_toggle")
async def handle_boomlify_toggle(query: CallbackQuery, state: FSMContext):
    uid = str(query.from_user.id)
    current = is_user_boomlify_auto(uid)
    new_state = not current
    set_user_boomlify_auto(uid, new_state)
    status_str = "Enabled (ON)" if new_state else "Disabled (OFF)"
    await query.answer(f"Boomlify Auto-Create on Limit {status_str}!", show_alert=False)
    await handle_boomlify_menu(query, state)


@dp.callback_query(F.data == "cmd_boomlify_gen_now")
async def handle_boomlify_gen_now(query: CallbackQuery, state: FSMContext):
    await query.answer("Creating new Boomlify email...", show_alert=False)
    uid = str(query.from_user.id)
    key = get_user_boomlify_key(uid)

    ok, res, email_obj = await asyncio.to_thread(create_boomlify_email, key)
    if ok:
        new_email = res
        set_user_email(uid, new_email)
        b_id = email_obj.get("id", "") if email_obj else ""
        b_exp = email_obj.get("expires_at", "") if email_obj else ""
        log_user_created_email(uid, new_email, b_id, b_exp)

        text = (
            f"<blockquote>\n"
            f"{em(EMOJI_CHECK, '✅')} <b>Boomlify Email Successfully Created!</b>\n\n"
            f"📧 <b>New Email:</b> <code>{new_email}</code>\n"
            f"🆔 <b>Email ID:</b> <code>{b_id}</code>\n"
            f"⏳ <b>Expires At:</b> <code>{b_exp}</code>\n\n"
            f"🎉 <i>Yeh email automatically aapka active campaign email set ho gaya hai!</i>\n"
            f"</blockquote>"
        )
    else:
        text = (
            f"<blockquote>\n"
            f"{em(EMOJI_CROSS, '✖')} <b>Boomlify Email Creation Failed!</b>\n\n"
            f"⚠️ <b>Error Details:</b>\n"
            f"<code>{res}</code>\n\n"
            f"💡 <i>Kripya check karein ki aapka API Key valid hai aur Boomlify credits bache hain.</i>\n"
            f"</blockquote>"
        )
    try:
        await query.message.edit_text(text, reply_markup=get_boomlify_menu_kb(is_user_boomlify_auto(uid)))
    except Exception:
        await query.message.answer(text, reply_markup=get_boomlify_menu_kb(is_user_boomlify_auto(uid)))


@dp.callback_query(F.data == "cmd_boomlify_set_key")
async def handle_boomlify_set_key_prompt(query: CallbackQuery, state: FSMContext):
    await query.answer()
    await state.clear()
    await state.set_state(BotState.waiting_for_boomlify_key)
    uid = str(query.from_user.id)
    curr_key = get_user_boomlify_key(uid)

    text = (
        f"<blockquote>\n"
        f"{em(EMOJI_STAR, '🌟')} <b>Update Boomlify API Key</b>\n\n"
        f"👤 <b>User ID:</b> <code>{uid}</code>\n"
        f"Current Key: <code>{curr_key}</code>\n\n"
        f"Kripya apna naya <b>Boomlify API Key</b> chat mein send karein:\n"
        f"<i>(Format: starts with <code>api_...</code>, from boomlify.com dashboard)</i>\n"
        f"</blockquote>"
    )
    try:
        await query.message.edit_text(text, reply_markup=get_cancel_kb())
    except Exception:
        await query.message.answer(text, reply_markup=get_cancel_kb())


@dp.message(BotState.waiting_for_boomlify_key, F.text)
async def handle_boomlify_save_key(message: Message, state: FSMContext):
    raw_key = message.text.strip()
    uid = str(message.from_user.id)

    if not raw_key.startswith("api_") or len(raw_key) < 20:
        await message.answer(
            f"<blockquote>\n"
            f"{em(EMOJI_WARN, '⚠️')} <b>Invalid API Key Format!</b>\n"
            f"Boomlify API key must start with <code>api_</code> and be at least 20 characters long.\n"
            f"Please enter a valid key from your Boomlify dashboard.\n"
            f"</blockquote>",
            reply_markup=get_cancel_kb()
        )
        return

    validating_msg = await message.answer("<i>Verifying API Key with Boomlify servers...</i>")
    ok, cred_res = await asyncio.to_thread(get_boomlify_credits, raw_key)
    try:
        await validating_msg.delete()
    except Exception:
        pass

    if not ok:
        await message.answer(
            f"<blockquote>\n"
            f"{em(EMOJI_CROSS, '✖')} <b>Boomlify API Key Verification Failed!</b>\n\n"
            f"<code>{cred_res}</code>\n\n"
            f"Kripya sahi API Key send karein ya Cancel karein.\n"
            f"</blockquote>",
            reply_markup=get_cancel_kb()
        )
        return

    set_user_boomlify_key(uid, raw_key)
    await state.clear()

    text = (
        f"<blockquote>\n"
        f"{em(EMOJI_CHECK, '✅')} <b>Boomlify API Key Successfully Saved!</b>\n\n"
        f"👤 <b>User ID:</b> <code>{uid}</code>\n"
        f"🔑 <b>Key:</b> <code>{raw_key[:8]}...{raw_key[-4:]}</code>\n"
        f"📊 <b>Account Status:</b> {cred_res}\n\n"
        f"Ab aapke accounts ke liye naye emails isi API key se automatically create honge.\n"
        f"</blockquote>"
    )
    await message.answer(text, reply_markup=get_boomlify_menu_kb(is_user_boomlify_auto(uid)))


@dp.callback_query(F.data == "cmd_boomlify_history")
async def handle_boomlify_history(query: CallbackQuery, state: FSMContext):
    await query.answer()
    uid = str(query.from_user.id)
    rows, total = get_user_created_emails(uid, limit=15)

    if not rows:
        history_text = (
            f"<blockquote>\n"
            f"{em(EMOJI_DIAMOND, '💎')} <b>Boomlify Email History:</b>\n\n"
            f"<i>Abhi tak koi email generate nahi hua hai.</i>\n\n"
            f"Niche diye gaye button par click karke abhi new email create kar sakte hain!\n"
            f"</blockquote>"
        )
    else:
        lines = []
        for i, (mail, b_id, b_exp, ts) in enumerate(rows, 1):
            t_str = datetime.datetime.fromtimestamp(ts).strftime("%d-%b %H:%M")
            lines.append(f"<b>{i}.</b> <code>{mail}</code> (<i>{t_str}</i>)")
        mails_list = "\n".join(lines)
        history_text = (
            f"<blockquote>\n"
            f"{em(EMOJI_DIAMOND, '💎')} <b>Boomlify Created Emails (Last {len(rows)} / Total {total}):</b>\n\n"
            f"{mails_list}\n"
            f"</blockquote>"
        )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⚡️ Generate New Email", callback_data="cmd_boomlify_gen_now", style="success", icon_custom_emoji_id=EMOJI_FIRE)],
        [InlineKeyboardButton(text="🔙 Back to Boomlify Menu", callback_data="cmd_boomlify_menu", style="primary", icon_custom_emoji_id=EMOJI_ARROW)]
    ])
    try:
        await query.message.edit_text(history_text, reply_markup=kb)
    except Exception:
        await query.message.answer(history_text, reply_markup=kb)


# ════════════════════════════════════════════════════════════════════
# Your Vouchers Menu Handler
# ════════════════════════════════════════════════════════════════════
@dp.callback_query(F.data == "cmd_view_vouchers")
async def handle_view_vouchers(query: CallbackQuery, state: FSMContext):
    await query.answer()
    uid = str(query.from_user.id)
    rows, total_count = get_user_vouchers(uid, limit=30)

    if not rows:
        text = (
            f"<blockquote>\n"
            f"{em(EMOJI_PARTY, '🎁')} <b>Your Amazon Gift Card Vouchers</b>\n\n"
            f"<i>Abhi tak koi voucher capture nahi hua hai.</i>\n\n"
            f"💡 <i>Auto Mode me jaise hi registration complete hoti hai, bot automatically 15 seconds ke andar Boomlify email se TaskPaisa voucher extract karke yaha add kar deta hai!</i>\n"
            f"</blockquote>"
        )
    else:
        lines = []
        total_val_num = 0.0
        for i, (phone, email, v_code, val, subj, ts) in enumerate(rows, 1):
            t_str = datetime.datetime.fromtimestamp(ts).strftime("%d-%b %H:%M")
            lines.append(
                f"<b>{i}.</b> 📱 <code>+91 {phone}</code>\n"
                f"   🎟 <code>{v_code}</code> | <b>{val}</b> (<i>{t_str}</i>)"
            )
            try:
                num = float(re.sub(r'[^0-9.]', '', val))
                total_val_num += num
            except Exception:
                total_val_num += 10.0

        v_list = "\n\n".join(lines)
        text = (
            f"<blockquote>\n"
            f"{em(EMOJI_PARTY, '🎁')} <b>Your Amazon Gift Vouchers (Total: {total_count})</b>\n\n"
            f"{v_list}\n\n"
            f"💰 <b>Estimated Total:</b> <b>₹{total_val_num:.2f}</b>\n"
            f"<i>Tap any code to copy!</i>\n"
            f"</blockquote>"
        )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Refresh Vouchers", callback_data="cmd_view_vouchers", style="primary", icon_custom_emoji_id=EMOJI_STAR)],
        [InlineKeyboardButton(text="🔙 Back to Main Menu", callback_data="cmd_main_menu", style="success", icon_custom_emoji_id=EMOJI_ARROW)]
    ])
    try:
        await query.message.edit_text(text, reply_markup=kb)
    except Exception:
        await query.message.answer(text, reply_markup=kb)


# ════════════════════════════════════════════════════════════════════
# Main Execution
# ════════════════════════════════════════════════════════════════════
async def main():
    print("="*60)
    print("   ANTHE AAKASH + REALOXY BULK REGISTRATION BOT STARTING...   ")
    print("="*60)
    # Configure high-speed 30-worker thread pool for asyncio to_thread executions
    loop = asyncio.get_running_loop()
    loop.set_default_executor(ThreadPoolExecutor(max_workers=MAX_WORKERS))
    print(f"[+] High-Speed Worker Pool Configured: {MAX_WORKERS} Concurrent Workers Active")
    me = await bot.get_me()
    print(f"[+] Bot Username: @{me.username} ({me.first_name})")
    print(f"[+] Database: {DB_PATH}")
    print(f"[+] Panels Storage: {PANELS_FILE}")
    print(f"[+] Multi-User Isolation: ENABLED")
    print("[+] Polling started. Ready to accept commands in Telegram!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("\nBot stopped.")
        for d in active_drivers.values():
            clean_driver(d)
