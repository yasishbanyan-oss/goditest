# GoodiBot - Tagging feature (new module; existing handlers.py is intentionally untouched)
from core import *
from telegram import ReplyParameters

TAG_OPEN_COMMANDS = {
    "گودی همه رو خبر کن",
    "گودی اطلاع بده",
    "تگ",
    "اطلاع",
    "گودی تگ",
    "گودی تگ کن",
}

TAG_MANAGER_COMMANDS = {
    "گودی مقام دار ها خبر کن",
    "گودی مقام دارها خبر کن",
    "تگ مقامدار",
    "تگ مقام دار",
    "تگ مقامدارها",
    "تگ ادمینا",
    "تگ ادمین",
}

TAG_50_COMMANDS = {"تگ همه", "تگ 50 نفر", "تگ ۵۰ نفر"}
TAG_300_COMMANDS = {"تگ همگانی", "تگ 300 نفر", "تگ ۳۰۰ نفر"}

TAG_MANAGER_EMOJI_ID = "6008077523848537247"
TAG_RECENT_EMOJI_ID = "5965216078106729238"
TAG_CLOSE_EMOJI_ID = "5983093054842606366"


def _tag_panel_keyboard(user_id: int):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "تگ کاربران مقام‌دار",
            callback_data=f"tag_panel:managers:{int(user_id)}",
            icon_custom_emoji_id=TAG_MANAGER_EMOJI_ID,
        )],
        [InlineKeyboardButton(
            "تگ 50 کاربر اخیر",
            callback_data=f"tag_panel:recent50:{int(user_id)}",
            icon_custom_emoji_id=TAG_RECENT_EMOJI_ID,
        )],
        [InlineKeyboardButton(
            "تگ 300 کاربر اخیر",
            callback_data=f"tag_panel:recent300:{int(user_id)}",
            icon_custom_emoji_id=TAG_RECENT_EMOJI_ID,
        )],
        [InlineKeyboardButton(
            "بستن",
            callback_data=f"tag_panel:close:{int(user_id)}",
            style="danger",
            icon_custom_emoji_id=TAG_CLOSE_EMOJI_ID,
        )],
    ])


def _tag_display(user_id: int, username: str, fullname: str) -> str:
    label = f"@{username}" if username else (fullname or "کاربر")
    return f'<a href="tg://user?id={int(user_id)}">{html.escape(label)}</a>'


async def _collect_recent_tag_users(context, chat_id: int, db: dict, limit: int):
    """Collect up to ``limit`` unique recent group users, newest first.

    Telegram has no Bot API method for listing every group member.  For the
    "recent" modes we therefore use users Goodi has actually observed in this
    group (recent activity + message history) first.  A live get_chat_member
    check is used when available, but a temporary API/cache failure must not
    make a user who just sent a message disappear from the tag list.
    """
    g_data = get_group_data(db, chat_id)
    member_count = None
    try:
        member_count = int(await context.bot.get_chat_member_count(chat_id))
    except Exception:
        logger.exception("Could not get member count for tag | chat_id=%s", chat_id)

    target_limit = limit
    if member_count is not None and member_count < target_limit:
        target_limit = member_count

    candidates = []
    seen_candidates = set()
    activity_ids = set()

    def add_candidate(uid, info=None, activity=False):
        try:
            uid_int = int(uid)
        except (TypeError, ValueError):
            return
        if uid_int <= 0 or uid_int in seen_candidates:
            return
        seen_candidates.add(uid_int)
        if activity:
            activity_ids.add(uid_int)
        info = info if isinstance(info, dict) else {}
        candidates.append((
            uid_int,
            info.get("username", ""),
            info.get("fullname", info.get("user_name", "کاربر")),
        ))

    # Newest unique activity first.
    recent = db.get("recent_active_users", {}).get(str(chat_id), []) or []
    if isinstance(recent, dict):
        recent = list(recent.items())
    for entry in reversed(recent):
        try:
            uid, info = entry
        except (TypeError, ValueError):
            continue
        add_candidate(uid, info, activity=True)

    # Message history is also a reliable record that the user has actually
    # spoken in this group.  Use it as a fallback/extra source for older users.
    logs = g_data.get("message_logs", []) or []
    for item in reversed(logs):
        if not isinstance(item, dict):
            continue
        add_candidate(item.get("user_id"), {
            "username": item.get("username", ""),
            "fullname": item.get("user_name", "کاربر"),
        }, activity=True)

    # Per-group records and the global cache are fallback sources only.
    for uid, info in reversed(list((g_data.get("user_records", {}) or {}).items())):
        cached = db.get("members", {}).get(str(uid), {}) or {}
        add_candidate(uid, cached if cached else info, activity=False)

    if member_count is not None and member_count <= limit:
        for uid, info in (db.get("members", {}) or {}).items():
            add_candidate(uid, info, activity=False)

    result = []
    for uid, username, fullname in candidates:
        # A user observed sending a message in this exact group is already
        # proven to be a group participant.  Do not discard that user merely
        # because get_chat_member is temporarily unavailable or its cache is
        # stale.  For cache-only users we still require a live membership check.
        if uid in activity_ids:
            try:
                member = await cached_chat_member(context, chat_id, uid)
                user_obj = getattr(member, "user", None)
                if getattr(member, "status", None) in (
                    ChatMemberStatus.MEMBER,
                    ChatMemberStatus.ADMINISTRATOR,
                    ChatMemberStatus.OWNER,
                ):
                    username = getattr(user_obj, "username", None) or username
                    fullname = getattr(user_obj, "full_name", None) or fullname or "کاربر"
            except Exception:
                # Keep the observed user with the stored username/name.
                pass
            result.append((uid, username, fullname or "کاربر"))
        else:
            try:
                member = await cached_chat_member(context, chat_id, uid)
                if member.status not in (
                    ChatMemberStatus.MEMBER,
                    ChatMemberStatus.ADMINISTRATOR,
                    ChatMemberStatus.OWNER,
                ):
                    continue
                user_obj = getattr(member, "user", None)
                username = getattr(user_obj, "username", None) or username
                fullname = getattr(user_obj, "full_name", None) or fullname or "کاربر"
                result.append((uid, username, fullname))
            except Exception:
                continue

        if len(result) >= target_limit:
            break

    return result


async def _collect_manager_tag_users(context, chat_id: int, db: dict):
    """Collect Telegram owners/admins plus Goodi-registered owners/admins."""
    users = {}

    try:
        administrators = await context.bot.get_chat_administrators(chat_id)
    except Exception:
        administrators = []

    for admin in administrators:
        user_obj = getattr(admin, "user", None)
        if not user_obj or user_obj.is_bot:
            continue
        users[int(user_obj.id)] = (
            int(user_obj.id),
            getattr(user_obj, "username", None) or "",
            getattr(user_obj, "full_name", None) or "کاربر",
        )

    g_data = get_group_data(db, chat_id)
    management = g_data.get("management", {}) or {}
    configured_ids = set()
    for role in ("owners", "admins"):
        for raw_uid in management.get(role, []) or []:
            try:
                configured_ids.add(int(raw_uid))
            except (TypeError, ValueError):
                pass

    if management.get("primary_owner_id") is not None:
        try:
            configured_ids.add(int(management["primary_owner_id"]))
        except (TypeError, ValueError):
            pass

    members = db.get("members", {}) or {}
    for uid in configured_ids:
        if uid in users:
            continue
        info = members.get(str(uid), {}) or {}
        try:
            member = await cached_chat_member(context, chat_id, uid)
            if member.status not in (
                ChatMemberStatus.MEMBER,
                ChatMemberStatus.ADMINISTRATOR,
                ChatMemberStatus.OWNER,
            ):
                continue
            user_obj = getattr(member, "user", None)
            username = getattr(user_obj, "username", None) or info.get("username", "")
            fullname = getattr(user_obj, "full_name", None) or info.get("fullname", "کاربر")
        except Exception:
            # A registered manager must still be a current member of this group
            # to be tagged. If Telegram cannot confirm membership, skip them.
            continue
        users[uid] = (uid, username, fullname)

    return list(users.values())


async def _send_tagged_users(update_or_message, users, prefix="", reply_to_message_id=None):
    if not users:
        await update_or_message.reply_text("کاربری برای تگ کردن پیدا نشد.")
        return

    # Telegram message text is limited to 4096 characters. Split while keeping
    # every selected user mentioned exactly once.
    chunks = []
    current = prefix
    for uid, username, fullname in users:
        token = _tag_display(uid, username, fullname)
        candidate = f"{current} - {token}" if current else token
        if current and len(candidate) > 3800:
            chunks.append(current)
            current = token
        else:
            current = candidate
    if current:
        chunks.append(current)

    for chunk in chunks:
        reply_kwargs = {}
        if reply_to_message_id is not None:
            reply_kwargs["reply_parameters"] = ReplyParameters(message_id=int(reply_to_message_id))
        await update_or_message.reply_text(
            chunk,
            parse_mode=ParseMode.HTML,
            disable_web_page_preview=True,
            **reply_kwargs,
        )


async def _open_tag_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not update.effective_user or not update.effective_chat:
        return
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    if not await is_configured_group_manager(context, chat_id, user_id):
        await message.reply_text(
            '<b>شما دسترسی تگ کردن اعضای این گروه را ندارید.</b> <tg-emoji emoji-id="5819154526816444042">❌</tg-emoji>',
            parse_mode=ParseMode.HTML,
        )
        return

    panel_text = "<b>حالت تگ کردن را انتخاب کنید:</b>"
    panel_kwargs = {}
    # If the tag command itself was sent as a reply, keep that original
    # message as the target of the eventual tag result. The panel is also
    # anchored to that same message so the callback can recover the target
    # without changing callback-data format or storing extra state.
    replied = getattr(message, "reply_to_message", None)
    if replied is not None:
        panel_kwargs["reply_parameters"] = ReplyParameters(message_id=int(replied.message_id))
    await message.reply_text(
        panel_text,
        reply_markup=_tag_panel_keyboard(user_id),
        parse_mode=ParseMode.HTML,
        **panel_kwargs,
    )


async def handle_tag_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat or update.effective_chat.type not in ("group", "supergroup"):
        return
    if not update.effective_user or update.effective_user.is_bot:
        return

    raw = update.message.text or update.message.caption or ""
    normalized = normalize_text(raw).strip().lower()

    if normalized in TAG_OPEN_COMMANDS:
        await _open_tag_panel(update, context)
        return

    if normalized not in TAG_MANAGER_COMMANDS and normalized not in TAG_50_COMMANDS and normalized not in TAG_300_COMMANDS:
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    if not await is_configured_group_manager(context, chat_id, user_id):
        await update.message.reply_text(
            '<b>شما دسترسی تگ کردن اعضای این گروه را ندارید.</b> <tg-emoji emoji-id="5819154526816444042">❌</tg-emoji>',
            parse_mode=ParseMode.HTML,
        )
        return

    db = load_db()
    if normalized in TAG_MANAGER_COMMANDS:
        users = await _collect_manager_tag_users(context, chat_id, db)
    elif normalized in TAG_50_COMMANDS:
        users = await _collect_recent_tag_users(context, chat_id, db, 50)
    else:
        users = await _collect_recent_tag_users(context, chat_id, db, 300)

    replied = getattr(update.message, "reply_to_message", None)
    reply_to_message_id = getattr(replied, "message_id", None) if replied is not None else None
    await _send_tagged_users(update.message, users, reply_to_message_id=reply_to_message_id)
