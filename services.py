# GoodiBot modular feature module
from core import *

def fa_to_en_digits(text: str) -> str:
    if not text:
        return "0"
    return "".join(PERSIAN_PERMUTATIONS.get(ch, ch) for ch in text)

def normalize_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"[؟?\.,!؛\-_]", " ", text)
    text = text.replace("\u200c", " ")
    # Do not collapse repeated digits: moderation durations such as 9999
    # and 278181818 are meaningful numeric values. Repeated-letter cleanup
    # is intentionally limited to non-digit characters.
    text = re.sub(r"([^\d])\1{2,}", r"\1", text)
    text = re.sub(r"ه{2,}", "ه", text)
    text = re.sub(r"و{2,}", "و", text)
    text = re.sub(r"ی{2,}", "ی", text)
    words = text.strip().split()
    return " ".join(words)

def get_persian_date_info():
    weekdays = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه", "شنبه", "یکشنبه"]
    now = datetime.now(ZoneInfo("Asia/Tehran"))
    wd = weekdays[now.weekday()]
    time_str = now.strftime("%H:%M")
    return wd, time_str

def get_persian_date_str():
    wd, time_str = get_persian_date_info()
    return f"{wd} ، ساعت {time_str}"

def format_user_event_time(timestamp=None) -> str:
    """Format moderation/join timestamps in the same Persian style used by the bot."""
    dt = datetime.fromtimestamp(timestamp or datetime.now().timestamp(), ZoneInfo("Asia/Tehran"))
    weekdays = ["دوشنبه", "سه‌شنبه", "چهارشنبه", "پنج‌شنبه", "جمعه", "شنبه", "یکشنبه"]
    wd = weekdays[dt.weekday()]
    hour = dt.hour
    minute = dt.strftime("%M")
    period = "صبح" if hour < 12 else ("ظهر" if hour < 17 else "شب")
    hour12 = hour % 12 or 12
    return f"{wd} {hour12}:{minute} {period}"

def get_group_user_record(db: dict, chat_id: int, user_id: int) -> dict:
    """Return persistent per-group history for a user without disturbing old DB data."""
    g_data = get_group_data(db, chat_id)
    records = g_data.setdefault("user_records", {})
    uid = str(user_id)
    if uid not in records or not isinstance(records[uid], dict):
        records[uid] = {
            "first_joined_at": None,
            "ban_count": 0,
            "last_ban_at": None,
            "mute_count": 0,
            "last_mute_at": None,
        }
        mark_db_dirty()
    else:
        records[uid].setdefault("first_joined_at", None)
        records[uid].setdefault("ban_count", 0)
        records[uid].setdefault("last_ban_at", None)
        records[uid].setdefault("mute_count", 0)
        records[uid].setdefault("last_mute_at", None)
    return records[uid]

def _restricted_is_muted(chat_member) -> bool:
    if getattr(chat_member, "status", None) != ChatMemberStatus.RESTRICTED:
        return False
    permissions = getattr(chat_member, "permissions", None)
    if permissions is None:
        return True
    return not bool(getattr(permissions, "can_send_messages", False))

async def track_group_user_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Persist join/ban/mute history for the user-check panel."""
    result = update.chat_member
    if not result:
        return

    chat = result.chat
    if not chat or chat.type not in ["group", "supergroup"]:
        return

    user = result.new_chat_member.user
    if not user or user.is_bot:
        return

    old_member = result.old_chat_member
    new_member = result.new_chat_member
    old_status = old_member.status
    new_status = new_member.status
    now_ts = datetime.now().timestamp()
    record = get_group_user_record(load_db(), chat.id, user.id)

    was_real_member = old_status in [
        ChatMemberStatus.MEMBER,
        ChatMemberStatus.ADMINISTRATOR,
        ChatMemberStatus.OWNER,
    ]
    is_real_member = (
        new_status in [
            ChatMemberStatus.MEMBER,
            ChatMemberStatus.ADMINISTRATOR,
            ChatMemberStatus.OWNER,
        ]
        or (new_status == ChatMemberStatus.RESTRICTED and getattr(new_member, "is_member", True))
    )

    # First time we observe an actual join.
    if not record.get("first_joined_at") and not was_real_member and is_real_member:
        record["first_joined_at"] = now_ts
        mark_db_dirty()

    # A new ban event.
    if new_status == ChatMemberStatus.BANNED and old_status != ChatMemberStatus.BANNED:
        record["ban_count"] = int(record.get("ban_count", 0)) + 1
        record["last_ban_at"] = now_ts
        mark_db_dirty()

    # A new mute/restriction event. Only count it when sending messages is disabled.
    new_muted = _restricted_is_muted(new_member)
    old_muted = _restricted_is_muted(old_member)
    if new_muted and not old_muted:
        record["mute_count"] = int(record.get("mute_count", 0)) + 1
        record["last_mute_at"] = now_ts
        mark_db_dirty()

    save_db()

async def resolve_check_user(context: ContextTypes.DEFAULT_TYPE, db: dict, chat_id: int, target_text: str):
    """Resolve numeric ID or @username using Telegram and the bot's stored member cache."""
    clean = fa_to_en_digits(target_text.strip().lstrip("@"))
    if clean.isdigit():
        uid = int(clean)
        if uid <= 0:
            return None
        try:
            member = await cached_chat_member(context, chat_id, uid)
            return member.user
        except Exception:
            cached = db.get("members", {}).get(str(uid))
            if cached:
                # Lightweight User object is unnecessary; return cache tuple marker.
                return {"id": uid, "username": cached.get("username", ""), "full_name": cached.get("fullname", "کاربر")}
            return None

    if not re.fullmatch(r"[A-Za-z0-9_]{5,32}", clean):
        return None

    username = clean.lower()
    for uid_str, info in db.get("members", {}).items():
        if str(info.get("username", "")).lower() == username:
            try:
                member = await cached_chat_member(context, chat_id, int(uid_str))
                return member.user
            except Exception:
                return {
                    "id": int(uid_str),
                    "username": info.get("username", ""),
                    "full_name": info.get("fullname", "کاربر"),
                }

    return None

def extract_media_payload(msg) -> dict | None:
    if not msg:
        return None
    caption = msg.caption_html if msg.caption else ""
    if msg.text:
        return {"type": "text", "text": msg.text_html}
    if msg.photo:
        return {"type": "photo", "file_id": msg.photo[-1].file_id, "caption": caption}
    if msg.animation:
        return {"type": "animation", "file_id": msg.animation.file_id, "caption": caption}
    if msg.video:
        return {"type": "video", "file_id": msg.video.file_id, "caption": caption}
    if msg.voice:
        return {"type": "voice", "file_id": msg.voice.file_id, "caption": caption}
    if msg.audio:
        return {"type": "audio", "file_id": msg.audio.file_id, "caption": caption}
    if msg.document:
        return {"type": "document", "file_id": msg.document.file_id, "caption": caption}
    if msg.video_note:
        return {"type": "video_note", "file_id": msg.video_note.file_id}
    if msg.contact:
        return {"type": "contact", "phone_number": msg.contact.phone_number, "first_name": msg.contact.first_name,
                "last_name": msg.contact.last_name or "", "vcard": msg.contact.vcard or ""}
    if msg.location:
        return {"type": "location", "latitude": msg.location.latitude, "longitude": msg.location.longitude,
                "horizontal_accuracy": msg.location.horizontal_accuracy, "live_period": msg.location.live_period,
                "heading": msg.location.heading, "proximity_alert_radius": msg.location.proximity_alert_radius}
    if msg.venue:
        return {"type": "venue", "latitude": msg.venue.location.latitude, "longitude": msg.venue.location.longitude,
                "title": msg.venue.title, "address": msg.venue.address, "foursquare_id": msg.venue.foursquare_id or "",
                "foursquare_type": msg.venue.foursquare_type or "", "google_place_id": msg.venue.google_place_id or "",
                "google_place_type": msg.venue.google_place_type or ""}
    if msg.sticker:
        return {"type": "sticker", "file_id": msg.sticker.file_id}
    return None

async def send_media_payload(bot, chat_id: int, payload: dict, reply_to_message_id: int | None = None) -> bool:
    try:
        mtype = payload.get("type")
        fid = payload.get("file_id")
        cap = payload.get("caption", "")
        txt = payload.get("text", "")

        if mtype == "text":
            await bot.send_message(chat_id=chat_id, text=txt, parse_mode=ParseMode.HTML, reply_to_message_id=reply_to_message_id)
        elif mtype == "photo":
            await bot.send_photo(chat_id=chat_id, photo=fid, caption=cap, parse_mode=ParseMode.HTML, reply_to_message_id=reply_to_message_id)
        elif mtype == "animation":
            await bot.send_animation(chat_id=chat_id, animation=fid, caption=cap, parse_mode=ParseMode.HTML, reply_to_message_id=reply_to_message_id)
        elif mtype == "video":
            await bot.send_video(chat_id=chat_id, video=fid, caption=cap, parse_mode=ParseMode.HTML, reply_to_message_id=reply_to_message_id)
        elif mtype == "voice":
            await bot.send_voice(chat_id=chat_id, voice=fid, caption=cap, parse_mode=ParseMode.HTML, reply_to_message_id=reply_to_message_id)
        elif mtype == "audio":
            await bot.send_audio(chat_id=chat_id, audio=fid, caption=cap, parse_mode=ParseMode.HTML, reply_to_message_id=reply_to_message_id)
        elif mtype == "document":
            await bot.send_document(chat_id=chat_id, document=fid, caption=cap, parse_mode=ParseMode.HTML, reply_to_message_id=reply_to_message_id)
        elif mtype == "video_note":
            await bot.send_video_note(chat_id=chat_id, video_note=fid, reply_to_message_id=reply_to_message_id)
        elif mtype == "contact":
            await bot.send_contact(chat_id=chat_id, phone_number=payload.get("phone_number", ""),
                                   first_name=payload.get("first_name", ""), last_name=payload.get("last_name", ""),
                                   vcard=payload.get("vcard", "") or None, reply_to_message_id=reply_to_message_id)
        elif mtype == "location":
            kwargs = {}
            for k in ("horizontal_accuracy", "live_period", "heading", "proximity_alert_radius"):
                if payload.get(k) is not None: kwargs[k] = payload[k]
            await bot.send_location(chat_id=chat_id, latitude=payload["latitude"], longitude=payload["longitude"],
                                    reply_to_message_id=reply_to_message_id, **kwargs)
        elif mtype == "venue":
            kwargs = {}
            if payload.get("foursquare_id"): kwargs["foursquare_id"] = payload["foursquare_id"]
            if payload.get("foursquare_type"): kwargs["foursquare_type"] = payload["foursquare_type"]
            if payload.get("google_place_id"): kwargs["google_place_id"] = payload["google_place_id"]
            if payload.get("google_place_type"): kwargs["google_place_type"] = payload["google_place_type"]
            await bot.send_venue(chat_id=chat_id, latitude=payload["latitude"], longitude=payload["longitude"],
                                 title=payload["title"], address=payload["address"],
                                 reply_to_message_id=reply_to_message_id, **kwargs)
        elif mtype == "sticker":
            await bot.send_sticker(chat_id=chat_id, sticker=fid, reply_to_message_id=reply_to_message_id)
        return True
    except Exception as e:
        logger.error(f"Failed to dispatch media payload: {e}")
        return False

async def dispatch_shutdown_message(bot, target_chat_id: int, shutdown_data: dict, reply_to_msg_id: int | None = None):
    if not shutdown_data:
        try:
            await bot.send_message(
                chat_id=target_chat_id,
                text=f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> ربات در حال حاضر خاموش می‌باشد.</b>',
                reply_to_message_id=reply_to_msg_id,
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass
        return

    from_chat = shutdown_data.get("from_chat_id")
    msg_id = shutdown_data.get("message_id")
    if from_chat and msg_id:
        try:
            await bot.copy_message(chat_id=target_chat_id, from_chat_id=from_chat, message_id=msg_id, reply_to_message_id=reply_to_msg_id)
            return
        except Exception:
            pass

    payload = shutdown_data.get("payload")
    if payload:
        await send_media_payload(bot, target_chat_id, payload, reply_to_message_id=reply_to_msg_id)

def resolve_target_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> tuple[int | None, str, str, str]:
    user = None
    if update.message and update.message.reply_to_message and update.message.reply_to_message.from_user:
        user = update.message.reply_to_message.from_user
    elif update.effective_user:
        user = update.effective_user

    if not user:
        return None, "کاربر مجهول", "", "کاربر مجهول"

    uid = user.id
    fname = user.full_name or user.first_name or "کاربر"
    uname = user.username or ""
    mention = get_user_mention(uid, fname)
    return uid, fname, uname, mention

def log_admin_action(db: dict, admin_id: int, admin_name: str, chat_title: str, chat_id: int, action_type: str, details: str):
    admin_logs = db.setdefault("admin_logs", [])
    now_str = get_persian_date_str()
    log_entry = {
        "admin_id": admin_id,
        "admin_name": admin_name,
        "chat_title": chat_title or "پیوی/نامشخص",
        "chat_id": chat_id,
        "action_type": action_type,
        "details": details,
        "timestamp": now_str
    }
    admin_logs.append(log_entry)
    if len(admin_logs) > 1000:
        admin_logs.pop(0)
    mark_db_dirty()
    save_db()

def get_user_mention(user_id: int, fullname: str) -> str:
    clean_name = html.escape(fullname)
    return f'<a href="tg://user?id={user_id}">{clean_name}</a>'

def get_user_stat(db: dict, user_id: int, stat_key: str) -> int:
    uid = str(user_id)
    return db.get("user_stats", {}).get(uid, {}).get(stat_key, 0)

def increment_user_stat(db: dict, user_id: int, stat_key: str, amount: int = 1):
    uid = str(user_id)
    if "user_stats" not in db:
        db["user_stats"] = {}
    if uid not in db["user_stats"]:
        db["user_stats"][uid] = {}
    db["user_stats"][uid][stat_key] = db["user_stats"][uid].get(stat_key, 0) + amount
    mark_db_dirty()
    save_db()

async def is_user_in_chat(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int) -> bool:
    try:
        member = await cached_chat_member(context, chat_id, user_id)
        return member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except Exception:
        return False

async def register_member(update: Update, db: dict):
    user = update.effective_user
    chat = update.effective_chat
    if not user or user.is_bot:
        return
        
    user_id = str(user.id)
    fullname = user.full_name or "کاربر"
    username = user.username or ""
    
    if user_id not in db["members"] or db["members"][user_id].get("fullname") != fullname:
        db["members"][user_id] = {"username": username, "fullname": fullname}
        mark_db_dirty()
    
    if chat and chat.type in ["group", "supergroup"]:
        chat_str = str(chat.id)
        if chat.id not in db["active_chats"]:
            db["active_chats"].append(chat.id)
            mark_db_dirty()
            
        g_data = get_group_data(db, chat.id)
        g_data["title"] = chat.title or g_data.get("title", "")

        if update.message:
            last_msgs = g_data.setdefault("user_last_messages", {})
            last_msgs[user_id] = update.message.message_id
            if len(last_msgs) > 200:
                oldest_k = next(iter(last_msgs))
                del last_msgs[oldest_k]
            mark_db_dirty()

        if update.message and (
            update.message.text or update.message.caption or update.message.photo
            or update.message.animation or update.message.video or update.message.document
            or update.message.voice or update.message.audio or update.message.video_note
            or update.message.sticker
        ):
            m_logs = g_data.setdefault("message_logs", [])
            log_item = {
                "message_id": update.message.message_id,
                "user_id": user.id,
                "user_name": fullname,
                "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "text": update.message.text or update.message.caption or "",
                "media_type": "text"
            }
            if update.message.photo:
                log_item["media_type"] = "photo"
                log_item["file_id"] = update.message.photo[-1].file_id
            elif update.message.animation:
                log_item["media_type"] = "animation"
                log_item["file_id"] = update.message.animation.file_id
            elif update.message.video:
                log_item["media_type"] = "video"
                log_item["file_id"] = update.message.video.file_id
            elif update.message.document:
                log_item["media_type"] = "document"
                log_item["file_id"] = update.message.document.file_id
            elif update.message.voice:
                log_item["media_type"] = "voice"
                log_item["file_id"] = update.message.voice.file_id
            elif update.message.audio:
                log_item["media_type"] = "audio"
                log_item["file_id"] = update.message.audio.file_id
            elif update.message.video_note:
                log_item["media_type"] = "video_note"
                log_item["file_id"] = update.message.video_note.file_id
            elif update.message.sticker:
                log_item["media_type"] = "sticker"
                log_item["file_id"] = update.message.sticker.file_id

            m_logs.append(log_item)
            if len(m_logs) > 300:
                m_logs.pop(0)
            mark_db_dirty()

        if "hourly_messages" not in db: db["hourly_messages"] = {}
        if chat_str not in db["hourly_messages"]: db["hourly_messages"][chat_str] = {}
        db["hourly_messages"][chat_str][user_id] = db["hourly_messages"][chat_str].get(user_id, 0) + 1

        if "recent_active_users" not in db: db["recent_active_users"] = {}
        if chat_str not in db["recent_active_users"]: db["recent_active_users"][chat_str] = []
        recent_list = db["recent_active_users"][chat_str]
        
        recent_list = [u for u in recent_list if u[0] != user_id]
        recent_list.append((user_id, {"fullname": fullname, "username": username}))
        if len(recent_list) > 20:
            recent_list.pop(0)
        db["recent_active_users"][chat_str] = recent_list
        mark_db_dirty()
        
    save_db()

async def get_fast_random_member(context: ContextTypes.DEFAULT_TYPE, chat_id: int, db: dict) -> tuple | None:
    chat_str = str(chat_id)
    recent = db.get("recent_active_users", {}).get(chat_str, [])
    valid_recent = []
    for uid_str, info in recent:
        if await is_user_in_chat(context, chat_id, int(uid_str)):
            valid_recent.append((uid_str, info))
            
    if valid_recent:
        return random.choice(valid_recent)
    
    members = db.get("members", {})
    valid_members = []
    for uid_str, info in members.items():
        if await is_user_in_chat(context, chat_id, int(uid_str)):
            valid_members.append((uid_str, info))
    if valid_members:
        return random.choice(valid_members)
    return None

def get_cooldown_remaining(db: dict, chat_id: int, feature: str) -> tuple[bool, int, dict]:
    g_data = get_group_data(db, chat_id)
    cooldowns = g_data.get("cooldowns", {})
    if feature not in cooldowns:
        return False, 0, {}
    
    last_time = cooldowns[feature].get("timestamp", 0)
    cooldown_limit = db.get("cooldown_minutes", 10) * 60
    elapsed = datetime.now().timestamp() - last_time
    
    if elapsed < cooldown_limit:
        remaining_seconds = int(cooldown_limit - elapsed)
        return True, remaining_seconds, cooldowns[feature].get("data", {})
    return False, 0, {}

def set_cooldown_data(db: dict, chat_id: int, feature: str, data: dict):
    g_data = get_group_data(db, chat_id)
    cooldowns = g_data.setdefault("cooldowns", {})
    cooldowns[feature] = {
        "timestamp": datetime.now().timestamp(),
        "data": data
    }
    mark_db_dirty()
    save_db()
