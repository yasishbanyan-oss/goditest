# GoodiBot - Tagging feature (new module; existing handlers.py is intentionally untouched)
from core import *

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
    """Collect unique users from the newest stored group messages.

    The bot cannot enumerate every member of a Telegram group. The existing
    message log is therefore the source for the requested recent-user tags.
    Users are deduplicated newest-first and verified as current chat members.
    """
    g_data = get_group_data(db, chat_id)
    logs = g_data.get("message_logs", []) or []
    result = []
    seen = set()

    for item in reversed(logs):
        try:
            uid = int(item.get("user_id"))
        except (TypeError, ValueError):
            continue
        if uid in seen:
            continue
        seen.add(uid)
        try:
            member = await cached_chat_member(context, chat_id, uid)
            if member.status not in (
                ChatMemberStatus.MEMBER,
                ChatMemberStatus.ADMINISTRATOR,
                ChatMemberStatus.OWNER,
            ):
                continue
            user_obj = getattr(member, "user", None)
            username = getattr(user_obj, "username", None) or item.get("username", "")
            fullname = getattr(user_obj, "full_name", None) or item.get("user_name", "کاربر")
            result.append((uid, username, fullname))
        except Exception:
            # A deleted/left user is simply skipped; tagging should continue.
            continue
        if len(result) >= limit:
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


async def _send_tagged_users(update_or_message, users, prefix=""):
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
        await update_or_message.reply_text(chunk, parse_mode=ParseMode.HTML, disable_web_page_preview=True)


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
    await message.reply_text(
        panel_text,
        reply_markup=_tag_panel_keyboard(user_id),
        parse_mode=ParseMode.HTML,
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

    await _send_tagged_users(update.message, users)
