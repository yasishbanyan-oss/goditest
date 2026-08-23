# GoodiBot sensitive-content protection.
# Managers can mark a replied message/media as sensitive. Matching content from
# non-managers is then deleted automatically.

from core import *


SENSITIVE_ADD_COMMANDS = {
    "حساس",
    "حساس شو",
    "گودی حساس شو",
    "حواست",
    "گودی حواست",
    "گودی حواست جمع کن",
    "حواست جمع کن",
}

SENSITIVE_REMOVE_COMMANDS = {
    "حذف حساس",
    "حساس نشو",
    "گودی حساس نشو",
    "حذف حساسیت",
}

SENSITIVE_OK_EMOJI = "5206607081334906820"
SENSITIVE_REMOVE_EMOJI = "4956395910306202687"


def _sensitive_normalize_text(text: str) -> str:
    value = normalize_text(text or "").strip().lower()
    value = value.replace("ي", "ی").replace("ك", "ک")
    return re.sub(r"\s+", " ", value)


def _sensitive_message_signature(message) -> tuple[str, str] | None:
    if not message:
        return None

    media_candidates = [
        ("عکس", getattr(message, "photo", None)),
        ("فیلم", getattr(message, "video", None)),
        ("گیف", getattr(message, "animation", None)),
        ("استیکر", getattr(message, "sticker", None)),
        ("ویس", getattr(message, "voice", None)),
        ("آهنگ", getattr(message, "audio", None)),
        ("فایل", getattr(message, "document", None)),
        ("ویدیو نوت", getattr(message, "video_note", None)),
    ]

    for kind, obj in media_candidates:
        if not obj:
            continue
        if isinstance(obj, (list, tuple)):
            obj = obj[-1] if obj else None
        if not obj:
            continue
        unique_id = getattr(obj, "file_unique_id", None) or getattr(obj, "file_id", None)
        if unique_id:
            return kind, f"media:{kind}:{unique_id}"

    # Text messages are matched by normalized exact content. Captions on media
    # are intentionally not used as the primary signature; the media itself is
    # the protected content.
    text = getattr(message, "text", None)
    if text:
        normalized = _sensitive_normalize_text(text)
        if normalized:
            import hashlib
            digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
            return "پیام", f"text:{digest}"

    caption = getattr(message, "caption", None)
    if caption and not any(getattr(message, attr, None) for _, attr in [
        ("عکس", "photo"), ("فیلم", "video"), ("گیف", "animation"),
        ("استیکر", "sticker"), ("ویس", "voice"), ("آهنگ", "audio"),
        ("فایل", "document"), ("ویدیو نوت", "video_note")
    ]):
        normalized = _sensitive_normalize_text(caption)
        if normalized:
            import hashlib
            digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
            return "پیام", f"text:{digest}"

    return None


def _sensitive_display_type(message) -> str:
    sig = _sensitive_message_signature(message)
    return sig[0] if sig else "پیام"


async def _handle_sensitive_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    message = update.message
    chat = update.effective_chat
    user = update.effective_user

    if not message or not chat or chat.type not in ("group", "supergroup") or not user or user.is_bot:
        return False

    raw = (message.text or "").strip()
    if not raw:
        return False
    normalized = normalize_text(raw).strip().lower()

    if normalized not in SENSITIVE_ADD_COMMANDS and normalized not in SENSITIVE_REMOVE_COMMANDS:
        return False

    if not await is_configured_group_manager(context, chat.id, user.id):
        await message.reply_text(
            f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> شما مدیر گروه نیستید و دسترسی به سیستم حساسیت ندارید.</b>',
            parse_mode=ParseMode.HTML,
        )
        raise ApplicationHandlerStop()

    replied = getattr(message, "reply_to_message", None)
    if replied is None:
        await message.reply_text(
            f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> برای این عملیات باید روی پیام موردنظر ریپلای کنید.</b>',
            parse_mode=ParseMode.HTML,
        )
        raise ApplicationHandlerStop()

    signature = _sensitive_message_signature(replied)
    if signature is None:
        await message.reply_text(
            f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> این نوع پیام قابل ثبت در لیست حساسیت نیست.</b>',
            parse_mode=ParseMode.HTML,
        )
        raise ApplicationHandlerStop()

    g_data = get_group_data(load_db(), chat.id)
    sensitive = g_data.setdefault("sensitive_items", {})

    kind, key = signature
    if normalized in SENSITIVE_ADD_COMMANDS:
        if key in sensitive:
            await message.reply_text(
                f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> {html.escape(kind)} از قبل در لیست حساسیت می‌باشد.</b>',
                parse_mode=ParseMode.HTML,
            )
            raise ApplicationHandlerStop()

        sensitive[key] = {
            "kind": kind,
            "message_id": replied.message_id,
            "created_by": user.id,
            "created_at": datetime.now().timestamp(),
        }
        mark_db_dirty()
        save_db(force=True)

        await message.reply_text(
            f'<b><tg-emoji emoji-id="{SENSITIVE_OK_EMOJI}">✔️</tg-emoji> {html.escape(kind)} با موفقیت به لیست حساسیت اضافه شد.</b>',
            parse_mode=ParseMode.HTML,
        )
    else:
        if key not in sensitive:
            await message.reply_text(
                f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> {html.escape(kind)} از قبل در لیست حساسیت نبود.</b>',
                parse_mode=ParseMode.HTML,
            )
            raise ApplicationHandlerStop()

        sensitive.pop(key, None)
        mark_db_dirty()
        save_db(force=True)
        await message.reply_text(
            f'<b><tg-emoji emoji-id="{SENSITIVE_REMOVE_EMOJI}">🔴</tg-emoji> {html.escape(kind)} با موفقیت از لیست حساسیت حذف گردید.</b>',
            parse_mode=ParseMode.HTML,
        )

    raise ApplicationHandlerStop()


async def enforce_sensitive_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message or update.edited_message
    chat = update.effective_chat
    user = update.effective_user

    if not message or not chat or chat.type not in ("group", "supergroup") or not user:
        return

    db = load_db()
    g_data = get_group_data(db, chat.id)
    sensitive = g_data.get("sensitive_items", {}) or {}
    if not sensitive:
        return

    # Group managers, including Goodi-registered managers/owners and the
    # configured bot owner, are allowed to send protected content.
    if user.is_bot or await is_configured_group_manager(context, chat.id, user.id):
        return

    signature = _sensitive_message_signature(message)
    if not signature:
        return

    _, key = signature
    if key not in sensitive:
        return

    try:
        await message.delete()
    except Exception:
        pass
    raise ApplicationHandlerStop()
