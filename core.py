# GoodiBot modular core
# Shared imports, configuration, Premium emoji sanitation, constants and database layer.

import html

import io

import json

import logging

import os

import random

import re

import shutil

import sys

import asyncio

import threading
import time
import unicodedata

from http.server import HTTPServer, BaseHTTPRequestHandler

from datetime import datetime, timedelta

from urllib.parse import quote

from zoneinfo import ZoneInfo

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InlineQueryResultArticle,
    InputTextMessageContent,
    ReactionTypeEmoji,
    ReactionTypeCustomEmoji,
    LinkPreviewOptions,
    ChatPermissions,
)

from telegram.constants import ParseMode, ChatMemberStatus, PollType, MessageEntityType

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ChatMemberHandler,
    InlineQueryHandler,
    ContextTypes,
    ApplicationHandlerStop,
    filters,
)

from telegram import Message, Bot

_original_message_reply_text = Message.reply_text

async def _premium_reply_text(self, text=None, *args, **kwargs):
    if isinstance(text, str):
        text = premium_only_text(text)
    return await _original_message_reply_text(self, text, *args, **kwargs)

Message.reply_text = _premium_reply_text

_original_message_edit_text = Message.edit_text

async def _premium_edit_text(self, text=None, *args, **kwargs):
    if isinstance(text, str):
        text = premium_only_text(text)
    return await _original_message_edit_text(self, text, *args, **kwargs)

Message.edit_text = _premium_edit_text

_original_bot_send_message = Bot.send_message

async def _premium_send_message(self, *args, **kwargs):
    if isinstance(kwargs.get("text"), str):
        kwargs["text"] = premium_only_text(kwargs["text"])
    elif args and isinstance(args[1] if len(args) > 1 else None, str):
        args = list(args); args[1] = premium_only_text(args[1]); args = tuple(args)
    if isinstance(kwargs.get("caption"), str):
        kwargs["caption"] = premium_only_text(kwargs["caption"])
    return await _original_bot_send_message(self, *args, **kwargs)

Bot.send_message = _premium_send_message

BOT_TOKEN = os.getenv("BOT_TOKEN", "8618205537:AAHZTpyWz5Sz7CU4aUejFRCa_KX_iZG4QFM")

OWNER_ID = int(os.getenv("OWNER_ID", "6749949992"))

DB_FILE = "db.json"

TEMP_DB_FILE = "db.json.tmp"

MAX_FUN_MESSAGES = 20

CHECK_CUSTOM_EMOJI_ID = "5830144944399981619"

FIXED_REACTION_CUSTOM_EMOJI_ID = CHECK_CUSTOM_EMOJI_ID

CROSS_CUSTOM_EMOJI_ID = "5819154526816444042"

CLEANUP_CUSTOM_EMOJI_ID = "5859215993183674044"

CANDY_CUSTOM_EMOJI_ID = "6046300980436278776"

CHECK_USER_CANDLE_CUSTOM_EMOJI_ID = "6030507681314250465"

PARTY_CUSTOM_EMOJI_ID = "5818785846823755322"

CLOSE_CUSTOM_EMOJI_ID = "5983093054842606366"

NEXT_CUSTOM_EMOJI_ID = "5843732253829503840"

PREV_CUSTOM_EMOJI_ID = "5845874566336880660"

BACK_CUSTOM_EMOJI_ID = "5823664135103061930"

GEAR_CUSTOM_EMOJI_ID = "5901989641204018165"

PANEL_SCALE_EMOJI_ID = "5825563515670242868"

PANEL_CASTLE_EMOJI_ID = "5832397371278892338"

PANEL_HASH_EMOJI_ID = "5902054589699465736"

LOCK_CUSTOM_EMOJI_ID = "5818736497649524154"

ADVANCED_CUSTOM_EMOJI_ID = "5819151717907832367"

LISTS_CUSTOM_EMOJI_ID = "5888937012253171131"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)

_PLAIN_EMOJI_RE = re.compile(
    r"[\U0001F1E6-\U0001F1FF\U0001F300-\U0001FAFF\U00002600-\U000027BF\U00002B00-\U00002BFF\U00002300-\U000023FF]"
    r"|[\u200d\ufe0f]"
)

def premium_only_text(value):
    if not isinstance(value, str):
        return value
    protected = []
    def _protect(m):
        protected.append(m.group(0))
        return f"__TG_PREMIUM_{len(protected)-1}__"
    value = re.sub(r"<tg-emoji\b[^>]*>.*?</tg-emoji>", _protect, value, flags=re.DOTALL | re.IGNORECASE)
    value = _PLAIN_EMOJI_RE.sub("", value)
    for i, tag in enumerate(protected):
        value = value.replace(f"__TG_PREMIUM_{i}__", tag)
    return value

try:
    from telegram import CallbackQuery
    _original_callback_answer = CallbackQuery.answer
    async def _premium_callback_answer(self, text=None, *args, **kwargs):
        if isinstance(text, str):
            text = premium_only_text(text)
        return await _original_callback_answer(self, text=text, *args, **kwargs)
    CallbackQuery.answer = _premium_callback_answer
except Exception:
    pass

_original_keyboard_button_init = InlineKeyboardButton.__init__

def _premium_keyboard_button_init(self, text, *args, **kwargs):
    if isinstance(text, str):
        text = premium_only_text(text)
    return _original_keyboard_button_init(self, text, *args, **kwargs)

InlineKeyboardButton.__init__ = _premium_keyboard_button_init

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

    def log_message(self, format, *args):
        return

def run_health_check_server():
    port = int(os.environ.get("PORT", 8080))
    try:
        server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
        logger.info(f"Dummy HTTP server running on port {port}")
        server.serve_forever()
    except Exception as e:
        logger.error(f"Health check server error: {e}")

# «لف» is intentionally substring-based: «لف»، «لفاف»، «کونلف»، «لفت»
# and similar forms all count as a LEF trigger. It is used only by the
# dedicated LEF feature, so it does not turn management commands into triggers.
LEF_PATTERN = re.compile(r"(?<!\w)\S*لف\S*(?!\w)", re.IGNORECASE)

DODOL_PATTERN = re.compile(
    r"(دولتو|دودولتو|شومبولتو|کیرتو|دولتو|دودولت|دول|شومبول|کیر)\s*(ببینم|نشون بده|نشون بپوش|بده|ببینیم)",
    re.IGNORECASE
)

PIN_PATTERNS = ["سنجاق", "پین", "pin"]

UNPIN_PATTERNS = ["حذف پین", "حذف سنجاق", "آن پین", "ان‌پین", "حذف‌سنجاق", "حذف‌پین", "آن‌پین", "unpin", "un pin"]

CLEANUP_PATTERN = re.compile(r"^\s*حذف\s+(?P<count>-?\d+|[a-zA-Z]+)?\s*$", re.IGNORECASE)

FUN_NAMED_PATTERN = re.compile(r"^\s*ناموسی\s+بده(?:\s+(?P<count>\d+))?\s*$", re.IGNORECASE)

FUN_NORMAL_PATTERN = re.compile(r"^\s*فحش\s+بده(?:\s+(?P<count>\d+))?\s*$", re.IGNORECASE)

LOCK_COMMAND_PATTERN = re.compile(
    r"^(?:گودی\s+)?(?:(?:(قفل|ببند|باز\s*کن|حذف\s*قفل|بازکردن\s*قفل)\s+(.+))|(?:(.+?)\s+(رو|را)?\s*(قفل\s*کن|ببند|باز\s*کن)))$",
    re.IGNORECASE
)

WELCOME_CMD_PATTERN = re.compile(
    r"^(?:[/!])?(?:گودی\s+)?(خوش\s*آمد|خوشآمد|خوش\s*امد|خوشآمدگویی|خوش\s*آمدگویی|welcome)\s*(روشن|خاموش|on|off)$",
    re.IGNORECASE
)

URL_REGEX = re.compile(r"(https?://\S+|t\.me/\S+|telegram\.me/\S+|www\.\S+)", re.IGNORECASE)

def normalize_link_text(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = text.replace("\u200b", "").replace("\u200c", "").replace("\u200d", "").replace("\ufeff", "")
    # Normalize Unicode dot-like separators and whitespace used to evade URL locks.
    for ch in "\u2024\u2025\u2026\u3002\uff0e\u0589\u06d4":
        text = text.replace(ch, ".")
    text = re.sub(r"\s+", "", text)
    return text

ENGLISH_CHAR_REGEX = re.compile(r"[a-zA-Z]")

PERSIAN_CHAR_REGEX = re.compile(r"[\u0600-\u06FF\uFB8A\u067E\u0686\u06AF\u200C\u200D]")

EMOJI_REGEX = re.compile(
    r"[\U00010000-\U0010ffff\u2600-\u27bf\u1f300-\u1f64f\u1f680-\u1f6ff\u1f900-\u1f9ff\u1fa70-\u1faff]",
    flags=re.UNICODE
)

PERSIAN_PERMUTATIONS = {
    '0': '0', '1': '1', '2': '2', '3': '3', '4': '4', '5': '5', '6': '6', '7': '7', '8': '8', '9': '9',
    '۰': '0', '۱': '1', '۲': '2', '۳': '3', '۴': '4', '۵': '5', '۶': '6', '۷': '7', '٨': '8', '۹': '9',
    '٠': '0', '١': '1', '٢': '2', '٣': '3', '٤': '4', '٥': '5', '٦': '6', '٧': '7', '٨': '8', '٩': '9'
}

WORLD_COUNTRIES = {
    "ایران": {
        "tz": "Asia/Tehran",
        "emoji": '<tg-emoji emoji-id="5271878966347601947">🇮🇷</tg-emoji>'
    },
    "آمریکا": {
        "tz": "America/New_York",
        "emoji": '<tg-emoji emoji-id="5927292517610426176">🇺🇸</tg-emoji>',
        "aliases": ["امریکا"]
    },
    "آلمان": {
        "tz": "Europe/Berlin",
        "emoji": '<tg-emoji emoji-id="5409360418520967565">🇩🇪</tg-emoji>',
        "aliases": ["المان"]
    },
    "انگلیس": {
        "tz": "Europe/London",
        "emoji": '<tg-emoji emoji-id="5229192892710402006">🏴󠁧󠁢󠁥󠁮󠁧󠁿</tg-emoji>',
        "aliases": ["انگلستان"]
    },
    "ترکیه": {
        "tz": "Europe/Istanbul",
        "emoji": '<tg-emoji emoji-id="5226948110873278599">🇹🇷</tg-emoji>',
        "aliases": []
    },
    "هند": {
        "tz": "Asia/Kolkata",
        "emoji": '<tg-emoji emoji-id="6136551252781172945">🇮🇳</tg-emoji>',
        "aliases": ["هندوستان"]
    },
    "عربستان": {
        "tz": "Asia/Riyadh",
        "emoji": '<tg-emoji emoji-id="5202079966761590204">🇸🇦</tg-emoji>',
        "aliases": []
    },
    "فرانسه": {
        "tz": "Europe/Paris",
        "emoji": '<tg-emoji emoji-id="5931269906434624310">🇫🇷</tg-emoji>',
        "aliases": []
    },
    "چین": {
        "tz": "Asia/Shanghai",
        "emoji": '<tg-emoji emoji-id="5431782733376399004">🇨🇳</tg-emoji>',
        "aliases": []
    },
    "ژاپن": {
        "tz": "Asia/Tokyo",
        "emoji": '<tg-emoji emoji-id="5456261908069885892">🇯🇵</tg-emoji>',
        "aliases": []
    }
}

ALL_LOCKS = {
    "mention": {"name": "منشن", "page": 1},
    "tag": {"name": "تگ", "page": 1},
    "spoiler": {"name": "اسپویلر", "page": 1},
    "video": {"name": "فیلم", "page": 1},
    "photo": {"name": "عکس", "page": 1},
    "document": {"name": "فایل", "page": 1},
    "audio": {"name": "آهنگ", "page": 1},
    "sticker": {"name": "استیکر", "page": 1},
    "gif": {"name": "گیف", "page": 1},
    "poll": {"name": "نظرسنجی", "page": 1},
    "voice": {"name": "ویس", "page": 1},
    "location": {"name": "مکان", "page": 1},
    "contact": {"name": "مخاطب", "page": 1},
    "edit_msg": {"name": "ویرایش پیام", "page": 1},
    "edit_media": {"name": "ویرایش رسانه", "page": 1},
    "forward": {"name": "فوروارد", "page": 2},
    "emoji": {"name": "ایموجی", "page": 2},
    "link": {"name": "لینک", "page": 2},
    "english": {"name": "انگلیسی", "page": 2},
    "persian": {"name": "فارسی", "page": 2},
    "hashtag": {"name": "هشتگ", "page": 2},
    "username": {"name": "یوزرنیم", "page": 2},
    "telegram_services": {"name": "سرویس تلگرام", "page": 2, "is_category": True},
    "service_join_link": {"name": "حذف پیام ورود با لینک", "page": 0, "is_service": True},
    "service_add_member": {"name": "حذف پیام افزودن عضو", "page": 0, "is_service": True},
    "service_pinned": {"name": "حذف پیام سنجاق شدن", "page": 0, "is_service": True},
    "service_video_chat": {"name": "حذف پیام‌های ویدیو چت", "page": 0, "is_service": True},
}

TELEGRAM_SERVICE_LOCK_KEYS = [
    "service_join_link",
    "service_add_member",
    "service_pinned",
    "service_video_chat"
]

LOCK_TEXT_ALIASES = {
    "منشن": "mention", "منشنها": "mention",
    "تگ": "tag", "تگها": "tag",
    "اسپویلر": "spoiler", "اسپویل": "spoiler",
    "فیلم": "video", "ویدیو": "video", "ویدئو": "video",
    "عکس": "photo", "تصویر": "photo",
    "فایل": "document", "داکیومنت": "document", "سند": "document",
    "آهنگ": "audio", "اهنگ": "audio", "موزیک": "audio", "صدا": "audio",
    "استیکر": "sticker", "استیکرها": "sticker",
    "گیف": "gif", "انیمیشن": "gif",
    "نظرسنجی": "poll", "پل": "poll",
    "ویس": "voice", "صدا ضبط شده": "voice", "ویسها": "voice",
    "مکان": "location", "لوکیشن": "location", "موقعیت": "location",
    "مخاطب": "contact", "مخاطبین": "contact", "شماره": "contact",
    "ویرایش پیام": "edit_msg", "ادیت پیام": "edit_msg", "ویرایش": "edit_msg",
    "ویرایش رسانه": "edit_media", "ادیت رسانه": "edit_media", "ویرایش مدیا": "edit_media",
    "فوروارد": "forward", "فروارد": "forward", "بازارسال": "forward",
    "ایموجی": "emoji", "اموجی": "emoji", "شکلک": "emoji",
    "لینک": "link", "لینکها": "link", "پیوند": "link",
    "انگلیسی": "english", "لاتین": "english",
    "فارسی": "persian", "پارسی": "persian",
    "هشتگ": "hashtag", "تگ هشتگ": "hashtag",
    "یوزرنیم": "username", "ایدی": "username", "آیدی": "username",
    "پیام ورود با لینک": "service_join_link", "ورود با لینک": "service_join_link",
    "پیام افزودن عضو": "service_add_member", "افزودن عضو": "service_add_member",
    "پیام سنجاق شدن": "service_pinned", "پیام پین": "service_pinned",
    "پیام‌های ویدیو چت": "service_video_chat", "ویدیو چت": "service_video_chat"
}

_DB_CACHE = None

_DB_DIRTY = False
_DB_LOCK = threading.RLock()

DEFAULT_FOODS = [
    "قرمه سبزی", "قیمه سیب‌زمینی", "قیمه نثار", "فسنجان", "دیزی / آبگوشت",
    "کباب کوبیده", "جوجه کباب", "شیشلیک", "کباب برگ", "کباب سلطانی",
    "کباب بختیاری", "کباب تابه ای", "ماهی کباب", "چلو گوشت", "زرشک پلو با مرغ",
    "باقالی پلو با گوشت", "باقالی پلو با مرغ", "آلبالو پلو", "شیرین پلو", "کلم پلو شیرازی",
    "عدس پلو با گوشت", "لوبیا پلو", "رشته پلو", "استامبولی", "دمپختک",
    "ته‌چین مرغ", "ته‌چین گوشت", "ته‌چین بادمجان", "کوفته تبریزی", "کوفته ریزه",
    "دلمه برگ مو", "دلمه بادمجان", "دلمه فلفل دلمه‌ای", "دلمه کدو", "میرزا قاسمی",
    "کشک بادمجان", "حلیم بادمجون", "خورشت بادمجان", "خورشت کدو", "خورشت کرفس",
    "پیتزا مخلوط", "پیتزا پپرونی", "برگر مخصوص", "چیزبرگر", "پاستا آلفردو", "لازانیا", "سوخاری"
]

DEFAULT_POEMS = [
    "{name} خواست منو خراب کنه، بردن تو خرابه کردنش!",
    "در ناامیدی بسی امید است، زیر لباس {name} کصی سفید است!",
    "از دیشب تا حالا شبیه‌خون زدن، {name} رو بردن و جف‌کون زدن!",
    "ای که از کوچه معشوقه ما می‌گذری، بی‌خبر از دل ما {name} رو یواشکی می‌بری!",
    "نه جانی ماند و نه دلداری ماند، {name} ماند و یک کونِ بادکرده!"
]

def get_default_locks_structure() -> dict:
    return {k: False for k in ALL_LOCKS.keys() if not ALL_LOCKS[k].get("is_category")}

def get_default_group_structure() -> dict:
    return {
        "title": "",
        "fun_named_responses": [],
        "fun_normal_responses": [],
        "foods": list(DEFAULT_FOODS),
        "custom_names": [],
        "poems": list(DEFAULT_POEMS),
        "media_lef": None,
        "cooldowns": {},
        "welcome": {"enabled": True, "custom": False},
        "comment": {"enabled": False, "custom": False},
        "random_reaction": True,
        "invite_link": None,
        "message_logs": [],
        "user_last_messages": {},
        "locks": get_default_locks_structure(),
        "management": {"configured": False, "primary_owner_id": None, "owners": [], "admins": [], "special": [], "exempt": []},
        "warning_settings": {"count": 3, "punishment": None, "temp_mute_hours": 1},
        "warnings": {},
        "muted_users": {},
        "banned_users": {},
        "filter_words": []
    }

def get_default_db_structure() -> dict:
    return {
        "version": 5,
        "members": {},
        "groups": {},
        "hourly_messages": {},
        "recent_active_users": {},
        "last_job_reset": 0,
        "active_chats": [],
        "cooldown_minutes": 10,
        "couples": {},
        "reports": {},
        "xo_games": {},
        "user_stats": {},
        "action_records": {},
        "commented_channel_posts": [],
        "started_users": {},
        "admin_logs": [],
        "whispers": {},
        "bot_shutdown": False,
        "shutdown_message": None,
        "global_bans": {},
        "global_group_bans": {},
        "global_fun_named": [],
        "global_fun_normal": [],
        "features": {
            "world_time": True,
            "handsome": True,
            "jende": True,
            "koni": True,
            "jaghi": True,
            "ship": True,
            "food": True,
            "lef": True,
            "goh_khor": True,
            "koni_percent": True,
            "poems": True,
            "koskhal": True,
            "sexy": True,
            "jazab": True
        },
        "states": {
            "waiting_lef_media": {},
            "waiting_add_food": {},
            "waiting_del_food": {},
            "waiting_cooldown": {},
            "waiting_poem_names": {},
            "waiting_add_poem": {},
            "waiting_broadcast_group": {},
            "waiting_broadcast_msg": {},
            "waiting_welcome_msg": {},
            "waiting_comment_msg": {},
            "waiting_user_broadcast_msg": {},
            "waiting_fun_named_msg": {},
            "waiting_fun_normal_msg": {},
            "waiting_search_query": {},
            "broadcast_builder": {},
            "waiting_shutdown_msg": {},
            "waiting_check_user": {},
            "ban_flow": {},
            "filter_panel": {},
            "filter_add": {},
            "filter_delete": {},
            "filter_cleanup": {}
        }
    }

def migrate_db_if_needed(data: dict) -> dict:
    if data.get("version") == 5:
        return data

    logger.info("Migrating database to v5...")
    new_db = get_default_db_structure()
    for k in new_db.keys():
        if k in data and k != "states":
            new_db[k] = data[k]

    groups = new_db.setdefault("groups", {})
    for _, g_val in groups.items():
        if "locks" not in g_val or not isinstance(g_val["locks"], dict):
            g_val["locks"] = get_default_locks_structure()
        else:
            for lk in ALL_LOCKS.keys():
                if not ALL_LOCKS[lk].get("is_category") and lk not in g_val["locks"]:
                    g_val["locks"][lk] = False

    new_db["version"] = 5
    return new_db

def load_db() -> dict:
    global _DB_CACHE
    if _DB_CACHE is not None:
        cleanup_expired_states(_DB_CACHE)
        return _DB_CACHE

    default_struct = get_default_db_structure()
    if not os.path.exists(DB_FILE):
        _DB_CACHE = default_struct
        save_db(force=True)
        return _DB_CACHE

    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            data = migrate_db_if_needed(data)
            for key, val in default_struct.items():
                if key not in data:
                    data[key] = val
            _DB_CACHE = data
            cleanup_expired_states(_DB_CACHE)
            return _DB_CACHE
    except Exception as e:
        logger.error(f"Database load error! Initializing default. Details: {e}")
        _DB_CACHE = default_struct
        save_db(force=True)
        return _DB_CACHE

def mark_db_dirty():
    global _DB_DIRTY
    _DB_DIRTY = True

def save_db(force: bool = False):
    global _DB_DIRTY, _DB_CACHE
    if _DB_CACHE is None:
        return
    with _DB_LOCK:
        if not force and not _DB_DIRTY:
            return
        try:
            with open(TEMP_DB_FILE, "w", encoding="utf-8") as f:
                json.dump(_DB_CACHE, f, ensure_ascii=False, indent=4)
                f.flush()
                os.fsync(f.fileno())
            os.replace(TEMP_DB_FILE, DB_FILE)
            _DB_DIRTY = False
        except Exception as e:
            logger.error(f"Error saving DB: {e}")

STATE_TIMEOUT_SECONDS = 15 * 60

def cleanup_expired_states(db: dict, now_ts: float | None = None) -> bool:
    """Remove stale interactive states without changing the stored state format."""
    now_ts = now_ts or time.time()
    states = db.setdefault("states", {})
    timestamps = db.setdefault("_state_timestamps", {})
    changed = False
    # Start the timer for legacy states that were created before timestamping
    # was introduced. This preserves their original state payloads.
    for state_name, entries in list(states.items()):
        if isinstance(entries, dict):
            stamp_map = timestamps.setdefault(state_name, {})
            for key in entries.keys():
                stamp_map.setdefault(str(key), now_ts)

    for state_name, entries in list(timestamps.items()):
        if not isinstance(entries, dict):
            continue
        target_states = states.get(state_name, {})
        if not isinstance(target_states, dict):
            continue
        for key, created in list(entries.items()):
            try:
                expired = now_ts - float(created) > STATE_TIMEOUT_SECONDS
            except Exception:
                expired = True
            if expired:
                target_states.pop(key, None)
                entries.pop(key, None)
                changed = True
        if not entries:
            timestamps.pop(state_name, None)
    if changed:
        mark_db_dirty()
    return changed

def touch_state(db: dict, state_name: str, key: str):
    db.setdefault("_state_timestamps", {}).setdefault(state_name, {})[str(key)] = time.time()

def get_session_key(user_id: int, chat_id: int) -> str:
    return f"{user_id}_{chat_id}"

def clear_user_all_states(db: dict, user_id: int, chat_id: int | None = None) -> bool:
    u_str = str(user_id)
    cleared = False
    states = db.setdefault("states", {})

    ban_flow = states.setdefault("ban_flow", {})
    keys_to_del = [k for k in ban_flow.keys() if k.startswith(f"{user_id}_")]
    if keys_to_del:
        for k in keys_to_del:
            del ban_flow[k]
        cleared = True

    for state_name in list(states.keys()):
        if state_name == "ban_flow":
            continue
        st_dict = states.get(state_name, {})
        if isinstance(st_dict, dict) and u_str in st_dict:
            del st_dict[u_str]
            cleared = True

    if cleared:
        mark_db_dirty()
        save_db(force=True)
    return cleared

def get_group_data(db: dict, chat_id: int | str) -> dict:
    cid_str = str(chat_id)
    groups = db.setdefault("groups", {})
    if cid_str not in groups:
        groups[cid_str] = get_default_group_structure()
        mark_db_dirty()
    else:
        if "user_last_messages" not in groups[cid_str]:
            groups[cid_str]["user_last_messages"] = {}
        if "filter_words" not in groups[cid_str] or not isinstance(groups[cid_str]["filter_words"], list):
            groups[cid_str]["filter_words"] = []
            mark_db_dirty()
        if "locks" not in groups[cid_str] or not isinstance(groups[cid_str]["locks"], dict):
            groups[cid_str]["locks"] = get_default_locks_structure()
            mark_db_dirty()
        else:
            for lk in ALL_LOCKS.keys():
                if not ALL_LOCKS[lk].get("is_category") and lk not in groups[cid_str]["locks"]:
                    groups[cid_str]["locks"][lk] = False
                    mark_db_dirty()
    return groups[cid_str]

PERSIAN_NUMBER_WORDS = {"یک": 1, "يك": 1, "دو": 2, "سه": 3, "چهار": 4, "پنج": 5, "شش": 6, "هفت": 7, "هشت": 8, "نه": 9, "ده": 10}

PERMANENT_DURATION_WORDS = {"دائم", "دائمی", "همیشه", "همیشگی", "ابدی", "forever", "permanent"}

TELEGRAM_MAX_TIMED_RESTRICTION_SECONDS = 366 * 24 * 60 * 60

LINK_COMMAND_PATTERN = re.compile(
    r"^(?:گودی\s+)?("
    r"لینک|دریافت\s+لینک|لینک\s+بده|گودی\s+لینک|گودی\s+لینک\s+بده|گودی\s+لینک\s+بگیر|گودی\s+لینک\s+بفرست|"
    r"گودی\s+لینک\s+عادی\s+بده|لینک\s+عادی|لینک\s+عادی\s+بگیر|لینک\s+عادی\s+بده|"
    r"لینک\s+یک‌بار\s+مصرف|لینک\s+یکبار\s+مصرف|لینک\s+یک‌بار\s+مصرف\s+بده|لینک\s+یکبار\s+مصرف\s+بده|گودی\s+لینک\s+یک‌بار\s+مصرف\s+بده|"
    r"لینک\s+پیوی|لینک\s+پیوی\s+بده|لینک\s+رو\s+پیوی\s+بفرست|لینک\s+در\s+پیوی|"
    r"لینک\s+عکس|لینک\s+به\s+صورت\s+عکس|لینک\s+عکس\s+بده|لینک\s+رو\s+عکس\s+بفرست"
    r")$",
    re.IGNORECASE
)

CONFIG_GEAR_EMOJI = "5803348359972393936"

CONFIG_RED_EMOJI = "4956395910306202687"

CONFIG_PLUS_EMOJI = "4956507094124594921"

CONFIG_NO_ADMIN_EMOJI = "5767342218905919987"

WARN_HEADER_EMOJI = "5825563515670242868"

WARN_INFO_EMOJI = "5830245188936670873"

WARN_COUNT_EMOJI = "5767342218905919987"

WARN_MINUS_EMOJI = "5888644331706785495"

WARN_PLUS_EMOJI = "5888598714859133997"

WARN_TEMP_EMOJI = "5886328760218688328"

WARN_MUTE_EMOJI = "5872883940624179027"

WARN_KICK_EMOJI = "5872823922751185495"

WARN_USER_EMOJI = "5818716826699307883"

WARN_DONE_EMOJI = "5884330316230827477"

PREMIUM_USER_EMOJI = "5843973755545590553"

PREMIUM_ROLE_EMOJI = "5836866392124563486"

PREMIUM_MANAGER_EMOJI = "5816739230482701944"

PREMIUM_MANAGER_ADD_EMOJI = "5830137127559504626"

PREMIUM_CANCEL_EMOJI = "5819154526816444042"

PREMIUM_OK_EMOJI = "5830144944399981619"

PREMIUM_WARN_EMOJI = "5818716826699307883"

PREMIUM_WARN_COUNT_EMOJI = "5825809784800025821"

GOODI_SUPPORT_TRIGGERS = {
    "گودی سازندت کیه", "سازنده گودی", "گودی سازنده", "سازندت کیه",
    "پشتیبانی", "گودی پشتیبانی", "پشتیبانی گودی",
    "گودی کمک", "کمک", "گودی هلپ",
}

GOODI_SUPPORT_REPLY = (
    '<b><tg-emoji emoji-id="5819051035284479206">🚨</tg-emoji> درصورت هرگونه مشکل کانال پشتیبانی ربات را چک بفرمایید:</b>\n\n'
    '- https://t.me/GoodiSupport'
)

# ---------------------------------------------------------------------------
# Modular function registry
# ---------------------------------------------------------------------------
def bind_all_modules(modules):
    """Expose every split function to every feature module.

    The source bot was a single Python module and many functions call other
    functions by bare name. This registry preserves that call graph after the
    physical split and avoids circular imports.
    """
    import inspect
    registry = {}
    all_modules = [__import__(__name__)] + list(modules)
    for mod in all_modules:
        for name, obj in vars(mod).items():
            if inspect.isfunction(obj) and getattr(obj, '__module__', None) == mod.__name__:
                registry[name] = obj
    for mod in modules:
        mod.__dict__.update(registry)
    return registry

