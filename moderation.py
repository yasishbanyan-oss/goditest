# GoodiBot modular feature module
from core import *

def moderation_until_datetime(seconds: float | None):
    """Return a Telegram-safe timed restriction date.

    Telegram treats restriction dates farther than roughly 366 days as
    permanent. For very large user-entered durations we therefore omit
    until_date instead of letting the Bot API reject the request. The bot
    still keeps the requested duration/label in its own moderation record.
    """
    if seconds is None:
        return None
    if seconds > TELEGRAM_MAX_TIMED_RESTRICTION_SECONDS:
        return None
    return datetime.now() + timedelta(seconds=seconds)

def parse_duration_text(text: str, default_permanent: bool = True) -> tuple[float | None, str]:
    value = fa_to_en_digits((text or "").strip().lower()).replace("‌", " ")
    value = re.sub(r"\s+", " ", value)
    if not value: return (None, "دائم") if default_permanent else (None, "")
    if value in PERMANENT_DURATION_WORDS: return None, "دائم"
    # A bare number is ALWAYS interpreted as minutes. Zero means permanent.
    # Keep the exact number entered; never silently replace it with 1 minute.
    bare_number = re.fullmatch(r"\d+(?:\.\d+)?", value)
    if bare_number:
        n = float(value)
        if n <= 0:
            return None, "دائم"
        label = f"{int(n) if n.is_integer() else n} دقیقه"
        return n * 60, label
    words = value.split()
    if len(words) == 2 and words[0] in PERSIAN_NUMBER_WORDS:
        n, unit = PERSIAN_NUMBER_WORDS[words[0]], words[1]
    else:
        m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*([a-zA-Z]+|ثانیه|دقیقه|ساعت|روز|هفته|ماه)", value)
        if m: n, unit = float(m.group(1)), m.group(2)
        elif re.fullmatch(r"\d+(?:\.\d+)?", value): n, unit = float(value), "دقیقه"
        else: return (None, "دائم") if default_permanent else (None, "")
    n = float(n)
    u = str(unit).lower()
    if n <= 0:
        return None, "دائم"
    if u.startswith(("ثانیه", "second", "sec", "s")): sec, label = n, f"{int(n) if n.is_integer() else n} ثانیه"
    elif u.startswith(("دقیقه", "minute", "min", "m")): sec, label = n*60, f"{int(n) if n.is_integer() else n} دقیقه"
    elif u.startswith(("ساعت", "hour", "hr", "h")): sec, label = n*3600, f"{int(n) if n.is_integer() else n} ساعت"
    elif u.startswith(("روز", "day", "d")): sec, label = n*86400, f"{int(n) if n.is_integer() else n} روز"
    elif u.startswith(("هفته", "week", "w")): sec, label = n*604800, f"{int(n) if n.is_integer() else n} هفته"
    elif u.startswith(("ماه", "month", "mo")): sec, label = n*2592000, f"{int(n) if n.is_integer() else n} ماه"
    else: sec, label = n*60, f"{int(n) if n.is_integer() else n} دقیقه"
    return max(1, sec), label

def full_mute_permissions():
    return ChatPermissions(can_send_messages=False, can_send_audios=False, can_send_documents=False, can_send_photos=False, can_send_videos=False, can_send_video_notes=False, can_send_voice_notes=False, can_send_polls=False, can_send_other_messages=False, can_add_web_page_previews=False, can_change_info=False, can_invite_users=False, can_pin_messages=False, can_manage_topics=False)

def full_group_permissions():
    return ChatPermissions(can_send_messages=True, can_send_audios=True, can_send_documents=True, can_send_photos=True, can_send_videos=True, can_send_video_notes=True, can_send_voice_notes=True, can_send_polls=True, can_send_other_messages=True, can_add_web_page_previews=True, can_change_info=False, can_invite_users=False, can_pin_messages=False, can_manage_topics=False)

async def bot_can_restrict_members(context, chat_id: int) -> bool:
    try:
        m = await cached_chat_member(context, chat_id, context.bot.id)
        return m.status == ChatMemberStatus.OWNER or (m.status == ChatMemberStatus.ADMINISTRATOR and bool(getattr(m, "can_restrict_members", False)))
    except Exception: return False

async def bot_can_promote_members(context, chat_id: int) -> bool:
    try:
        m = await cached_chat_member(context, chat_id, context.bot.id)
        return m.status == ChatMemberStatus.OWNER or (m.status == ChatMemberStatus.ADMINISTRATOR and bool(getattr(m, "can_promote_members", False)))
    except Exception: return False

def prune_group_action_lists(g_data: dict):
    changed = False
    now = datetime.now().timestamp()
    for key in ("muted_users", "banned_users"):
        store = g_data.setdefault(key, {})
        for uid in list(store):
            until = store[uid].get("until")
            if until and float(until) <= now:
                store.pop(uid, None); changed = True
    if changed: mark_db_dirty()

def is_user_globally_banned(db: dict, user_id: int) -> tuple[bool, dict | None]:
    uid_str = str(user_id)
    bans = db.get("global_bans", {})
    if uid_str not in bans:
        return False, None

    ban_info = bans[uid_str]
    b_type = ban_info.get("type", "permanent")
    if b_type == "temporary":
        ban_until = ban_info.get("ban_until")
        now_ts = datetime.now().timestamp()
        if ban_until and now_ts > ban_until:
            del bans[uid_str]
            mark_db_dirty()
            save_db()
            return False, None
    return True, ban_info

def is_group_globally_banned(db: dict, chat_id: int) -> tuple[bool, dict | None]:
    cid_str = str(chat_id)
    bans = db.get("global_group_bans", {})
    if cid_str not in bans:
        return False, None

    ban_info = bans[cid_str]
    b_type = ban_info.get("type", "permanent")
    if b_type == "temporary":
        ban_until = ban_info.get("ban_until")
        now_ts = datetime.now().timestamp()
        if ban_until and now_ts > ban_until:
            del bans[cid_str]
            mark_db_dirty()
            save_db()
            return False, None
    return True, ban_info

async def send_premium_ban_notification(bot, chat_id: int, is_group: bool, duration_str: str, reason_str: str) -> bool:
    title = "گروه شما از ربات گودی بن شد!" if is_group else "شما از ربات گودی بن شدید!"
    esc_title = html.escape(title)
    esc_dur = html.escape(duration_str)
    esc_reason = html.escape(reason_str)

    html_text = (
        f'<tg-emoji emoji-id="5819051035284479206">🚨</tg-emoji> <b>{esc_title}</b>\n\n'
        f'<tg-emoji emoji-id="5906896396526560494">⏰</tg-emoji> <b>مدت زمان :</b> {esc_dur}\n'
        f'<tg-emoji emoji-id="5901989641204018165">⚙️</tg-emoji> <b>دلیل :</b> {esc_reason}'
    )

    try:
        await bot.send_message(chat_id=chat_id, text=html_text, parse_mode=ParseMode.HTML)
        return True
    except Exception as e:
        logger.warning(f"Could not deliver Ban notification to chat {chat_id}: {e}")
        return False

async def send_premium_unban_notification(bot, chat_id: int, is_group: bool = False) -> bool:
    sub = "گروه شما از محدودیت ربات خارج شد." if is_group else "شما از محدودیت ربات خارج شدید."
    html_text = (
        f'<b>تبریک! </b><tg-emoji emoji-id="{PARTY_CUSTOM_EMOJI_ID}">🎉</tg-emoji>\n\n'
        f'<b>{sub}</b> <tg-emoji emoji-id="5816739230482701944">✨</tg-emoji>'
    )
    try:
        await bot.send_message(chat_id=chat_id, text=html_text, parse_mode=ParseMode.HTML)
        return True
    except Exception as e:
        logger.warning(f"Could not deliver Unban notification to {chat_id}: {e}")
        return False

COMMAND_SPAM_WINDOW = 5
COMMAND_SPAM_THRESHOLD = 4
COMMAND_SPAM_COMMAND_WORDS = {
    "قفل", "ببند", "باز", "حذف", "پاکسازی", "لیست", "سکوت", "میوت", "mute", "ban", "بن",
    "اخطار", "هشدار", "warn", "ترفیع", "عزل", "مدیر", "مالک", "ویژه", "معاف", "پیکربندی",
    "تنظیم", "پنل", "راهنما", "help", "هلپ", "گزارش", "لینک", "فیلتر", "کلمه", "حذف",
    "سنجاق", "پین", "فحش", "ناموسی", "غذا", "شعر", "پاکسازی", "آمار"
}

def _is_command_like_message(msg) -> bool:
    if not msg or not msg.text:
        return False
    text = msg.text.strip().lower()
    if text.startswith(("/", "!", ".")):
        return True
    first = normalize_text(text).split(" ", 1)[0]
    return first in COMMAND_SPAM_COMMAND_WORDS or text.startswith("گودی ")

async def _command_antispam(update: Update, context: ContextTypes.DEFAULT_TYPE, db: dict) -> bool:
    chat = update.effective_chat
    user = update.effective_user
    msg = update.message
    if not chat or chat.type not in ["group", "supergroup"] or not user or user.is_bot or not _is_command_like_message(msg):
        return False
    now = time.time()
    state = db.setdefault("_command_antispam", {}).setdefault(str(chat.id), {}).setdefault(str(user.id), {"times": [], "warned_until": 0})
    times = [t for t in state.get("times", []) if now - float(t) <= COMMAND_SPAM_WINDOW]
    times.append(now)
    state["times"] = times[-10:]
    if len(times) <= COMMAND_SPAM_THRESHOLD:
        return False
    if now >= float(state.get("warned_until", 0)):
        state["warned_until"] = now + COMMAND_SPAM_WINDOW
        mark_db_dirty()
        try:
            await msg.reply_text(
                f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> لطفاً دستورات را پشت سر هم ارسال نکنید؛ پیام‌های تکراری حذف می‌شوند.</b>',
                parse_mode=ParseMode.HTML
            )
        except Exception:
            pass
    else:
        try:
            await msg.delete()
        except Exception:
            pass
    mark_db_dirty()
    return True

async def global_security_guard(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user = update.effective_user
        chat = update.effective_chat
        db = load_db()

        if chat and chat.type in ["group", "supergroup"]:
            g_banned, _ = is_group_globally_banned(db, chat.id)
            if g_banned:
                raise ApplicationHandlerStop()

        if user and int(user.id) == int(OWNER_ID):
            return

        if user:
            if await _command_antispam(update, context, db):
                raise ApplicationHandlerStop()
            is_banned, _ = is_user_globally_banned(db, user.id)
            if is_banned:
                raise ApplicationHandlerStop()

        if db.get("bot_shutdown", False):
            is_command = update.message and update.message.text and update.message.text.startswith("/")
            is_private = chat and chat.type == "private"
            
            if is_command or is_private:
                s_data = db.get("shutdown_message")
                target_chat_id = chat.id if chat else (user.id if user else None)
                reply_id = update.message.message_id if update.message else None
                if target_chat_id:
                    await dispatch_shutdown_message(context.bot, target_chat_id, s_data, reply_id)
                raise ApplicationHandlerStop()
            else:
                raise ApplicationHandlerStop()

    except ApplicationHandlerStop:
        raise
    except Exception as e:
        logger.error(f"Error in global_security_guard: {e}")

async def enforce_group_locks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    msg = update.message or update.edited_message

    if not chat or chat.type not in ["group", "supergroup"] or not msg:
        return

    db = load_db()
    g_data = get_group_data(db, chat.id)
    locks = g_data.get("locks", {})

    if not any(locks.values()):
        return

    should_delete = False

    if msg.new_chat_members:
        is_join_by_link = False
        is_added_by_other = False

        if len(msg.new_chat_members) == 1 and user and msg.new_chat_members[0].id == user.id:
            is_join_by_link = True
        elif user and any(m.id != user.id for m in msg.new_chat_members):
            is_added_by_other = True
        else:
            is_join_by_link = True

        if is_join_by_link and locks.get("service_join_link", False):
            should_delete = True
        elif is_added_by_other and locks.get("service_add_member", False):
            should_delete = True

    if not should_delete and locks.get("service_pinned", False) and bool(getattr(msg, "pinned_message", None)):
        should_delete = True

    if not should_delete and locks.get("service_video_chat", False):
        has_vc_event = bool(
            getattr(msg, "video_chat_started", None) or
            getattr(msg, "video_chat_ended", None) or
            getattr(msg, "video_chat_participants_invited", None) or
            getattr(msg, "video_chat_scheduled", None) or
            getattr(msg, "voice_chat_started", None) or
            getattr(msg, "voice_chat_ended", None) or
            getattr(msg, "voice_chat_participants_invited", None)
        )
        if has_vc_event:
            should_delete = True

    if not should_delete:
        special_ids = _role_ids(g_data, "special")
        if user and (user.is_bot or user.id in special_ids or await is_configured_group_manager(context, chat.id, user.id)):
            return

        is_edited = update.edited_message is not None

        if is_edited:
            has_media = bool(msg.photo or msg.video or msg.animation or msg.audio or msg.voice or msg.document or msg.sticker)
            if has_media and locks.get("edit_media", False):
                should_delete = True
            elif not has_media and locks.get("edit_msg", False):
                should_delete = True

        if not should_delete:
            if locks.get("photo", False) and bool(msg.photo): should_delete = True
            elif locks.get("video", False) and bool(msg.video): should_delete = True
            elif locks.get("gif", False) and bool(msg.animation): should_delete = True
            elif locks.get("audio", False) and bool(msg.audio): should_delete = True
            elif locks.get("voice", False) and bool(msg.voice): should_delete = True
            elif locks.get("document", False) and bool(msg.document): should_delete = True
            elif locks.get("sticker", False) and bool(msg.sticker): should_delete = True
            elif locks.get("location", False) and bool(msg.location or msg.venue): should_delete = True
            elif locks.get("contact", False) and bool(msg.contact): should_delete = True
            elif locks.get("poll", False) and bool(msg.poll): should_delete = True

        if not should_delete and locks.get("forward", False):
            if bool(msg.forward_origin or msg.forward_date or msg.forward_from or msg.forward_from_chat):
                should_delete = True

        if not should_delete:
            text_content = msg.text or msg.caption or ""
            entities = list(msg.entities or []) + list(msg.caption_entities or [])

            if locks.get("link", False):
                if any(e.type in [MessageEntityType.URL, MessageEntityType.TEXT_LINK] for e in entities) or URL_REGEX.search(normalize_link_text(text_content)):
                    should_delete = True

            if not should_delete and locks.get("mention", False):
                if any(e.type in [MessageEntityType.MENTION, MessageEntityType.TEXT_MENTION] for e in entities):
                    should_delete = True

            if not should_delete and locks.get("tag", False):
                if "@" in text_content or any(e.type == MessageEntityType.MENTION for e in entities):
                    should_delete = True

            if not should_delete and locks.get("username", False):
                if any(e.type == MessageEntityType.MENTION for e in entities) or ("@" in text_content and not text_content.startswith("/")):
                    should_delete = True

            if not should_delete and locks.get("hashtag", False):
                if any(e.type == MessageEntityType.HASHTAG for e in entities) or "#" in text_content:
                    should_delete = True

            if not should_delete and locks.get("spoiler", False):
                if any(e.type == MessageEntityType.SPOILER for e in entities):
                    should_delete = True

            if not should_delete and locks.get("emoji", False):
                if any(e.type == MessageEntityType.CUSTOM_EMOJI for e in entities) or EMOJI_REGEX.search(text_content):
                    should_delete = True

            if not should_delete and locks.get("english", False):
                if ENGLISH_CHAR_REGEX.search(text_content):
                    should_delete = True

            if not should_delete and locks.get("persian", False):
                if PERSIAN_CHAR_REGEX.search(text_content):
                    should_delete = True

    if should_delete:
        try:
            await msg.delete()
        except Exception:
            pass
        if not bool(msg.new_chat_members):
            raise ApplicationHandlerStop()
