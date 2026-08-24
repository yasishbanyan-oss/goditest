# GoodiBot sensitive-content protection and management panel.
from core import *

SENSITIVE_ADD_COMMANDS = {
    "حساس", "حساس شو", "گودی حساس شو", "حواست", "گودی حواست",
    "گودی حواست جمع کن", "حواست جمع کن",
}
SENSITIVE_REMOVE_COMMANDS = {"حذف حساس", "حساس نشو", "گودی حساس نشو", "حذف حساسیت"}
SENSITIVE_CLEANUP_COMMANDS = {"پاکسازی حساس", "پاکسازی حساسیت", "پاکسازی لیست حساسیت", "پاکسازی لیست حساس"}
SENSITIVE_OK_EMOJI = "5206607081334906820"
SENSITIVE_REMOVE_EMOJI = "4956395910306202687"
SENSITIVE_INFO_EMOJI = "6008257491568172845"
SENSITIVE_ADD_EMOJI = "5819032824623144971"
SENSITIVE_DELETE_EMOJI = "5819154526816444042"
SENSITIVE_BACK_EMOJI = "5823664135103061930"
SENSITIVE_CHAT_EMOJI = "6005644459235089937"
SENSITIVE_DONE_EMOJI = "5197702557568359549"
SENSITIVE_OPERATION_EMOJI = "6008257491568172845"
SENSITIVE_ACTIVE_EMOJI = "5197644042933917422"
SENSITIVE_PROMPT_EMOJI = "6008077523848537247"
SENSITIVE_THINK_EMOJI = "5422478210715634531"
SENSITIVE_REMOVE_DONE_EMOJI = "5965474544943638848"


def _sensitive_normalize_text(text: str) -> str:
    value = normalize_text(text or "").strip().lower()
    value = value.replace("ي", "ی").replace("ك", "ک")
    return re.sub(r"\s+", " ", value)


def _media_from_message(message):
    media_candidates = [
        ("عکس", getattr(message, "photo", None)), ("فیلم", getattr(message, "video", None)),
        ("گیف", getattr(message, "animation", None)), ("استیکر", getattr(message, "sticker", None)),
        ("ویس", getattr(message, "voice", None)), ("آهنگ", getattr(message, "audio", None)),
        ("فایل", getattr(message, "document", None)), ("ویدیو نوت", getattr(message, "video_note", None)),
    ]
    for kind, obj in media_candidates:
        if not obj:
            continue
        if isinstance(obj, (list, tuple)):
            obj = obj[-1] if obj else None
        if obj:
            return kind, obj
    return None, None


def _sensitive_message_signature(message) -> tuple[str, str] | None:
    if not message:
        return None
    kind, obj = _media_from_message(message)
    if obj:
        unique_id = getattr(obj, "file_unique_id", None) or getattr(obj, "file_id", None)
        if unique_id:
            return kind, f"media:{kind}:{unique_id}"
    text = getattr(message, "text", None)
    if text:
        normalized = _sensitive_normalize_text(text)
        if normalized:
            import hashlib
            digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
            return "پیام", f"text:{digest}"
    caption = getattr(message, "caption", None)
    if caption and not any(getattr(message, a, None) for a in ("photo", "video", "animation", "sticker", "voice", "audio", "document", "video_note")):
        normalized = _sensitive_normalize_text(caption)
        if normalized:
            import hashlib
            digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
            return "پیام", f"text:{digest}"
    return None


def _sensitive_display_from_message(message, signature=None) -> str:
    signature = signature or _sensitive_message_signature(message)
    if not signature:
        return "پیام"
    kind, _ = signature
    if kind == "پیام":
        text = getattr(message, "text", None) or getattr(message, "caption", None) or "پیام"
        return f"Massage | {html.escape(str(text).replace(chr(10), ' '))}"
    _, obj = _media_from_message(message)
    size = getattr(obj, "file_size", None) if obj else None
    media_labels = {"ویس": "Voice", "گیف": "Gif", "عکس": "Photo", "فیلم": "Video", "استیکر": "Sticker", "آهنگ": "Audio", "فایل": "File", "ویدیو نوت": "Video Note"}
    label = media_labels.get(kind, kind)
    if size:
        if size >= 1024 * 1024:
            size_text = f"{size / (1024 * 1024):.1f} MB".replace(".0 MB", " MB")
        else:
            size_text = f"{max(1, round(size / 1024))} KB"
        return f"{label} | {size_text}"
    return f"{label} | رسانه"


def _sensitive_panel_keyboard(chat_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ افزودن حساسیت", callback_data=f"sensitive_add:{chat_id}", style="success", icon_custom_emoji_id=SENSITIVE_ADD_EMOJI)],
        [InlineKeyboardButton("❌ حذف حساسیت", callback_data=f"sensitive_remove:{chat_id}", style="danger", icon_custom_emoji_id=SENSITIVE_DELETE_EMOJI)],
        [InlineKeyboardButton("⬅️ بازگشت", callback_data=f"sensitive_back:{chat_id}", style="primary", icon_custom_emoji_id=SENSITIVE_BACK_EMOJI)],
    ])


def _sensitive_back_keyboard(chat_id):
    return InlineKeyboardMarkup([[InlineKeyboardButton("⬅️ بازگشت", callback_data=f"sensitive_panel:{chat_id}", style="danger", icon_custom_emoji_id=BACK_CUSTOM_EMOJI_ID)]])


def _sensitive_panel_text(g_data):
    sensitive = g_data.get("sensitive_items", {}) or {}
    if not sensitive:
        return (
            f'<b><tg-emoji emoji-id="{SENSITIVE_INFO_EMOJI}">⛔️</tg-emoji> به بخش حساسیت‌ها خوش آمدید.</b>\n'
            f'<b>- با کمک این بخش می‌توانید برخی از پیام ها و مدیا هارا در لیست حساسیت قرار دهید تا در صورت ارسال پاک شوند و اگر مجازاتی ثبت شده است اجرا شود.</b>\n\n'
            f'<b><tg-emoji emoji-id="{SENSITIVE_THINK_EMOJI}">🤔</tg-emoji> عملیات خود را از طریق دکمه‌های زیر انجام دهید.</b>'
        )
    lines = [f'<b><tg-emoji emoji-id="{SENSITIVE_ACTIVE_EMOJI}">🔴</tg-emoji> حساسیت فعال است.</b>', ""]
    for item in sensitive.values():
        display = item.get("display") or item.get("kind", "پیام")
        lines.append(f"<b>{display}</b>")
    return "\n".join(lines)


async def render_sensitive_panel(query, context, chat_id, db):
    if not await is_configured_group_manager(context, chat_id, query.from_user.id):
        await query.answer("این پنل برای شما نیست.", show_alert=True); return
    g = get_group_data(db, chat_id)
    await query.message.edit_text(_sensitive_panel_text(g), reply_markup=_sensitive_panel_keyboard(chat_id), parse_mode=ParseMode.HTML)
    db.setdefault("states", {}).setdefault("sensitive_panel", {})[str(query.from_user.id)] = {"chat_id": int(chat_id), "message_id": int(query.message.message_id)}
    mark_db_dirty(); save_db(force=True)


async def _handle_sensitive_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    message = update.message; chat = update.effective_chat; user = update.effective_user
    if not message or not chat or chat.type not in ("group", "supergroup") or not user or user.is_bot:
        return False
    raw = (message.text or "").strip()
    normalized = normalize_text(raw).strip().lower()
    # During panel entry, ordinary text (even if it looks like a command) is content.
    pending = load_db().get("states", {}).get("waiting_sensitive_panel", {}).get(str(user.id))
    if pending and int(pending.get("chat_id", 0)) == int(chat.id) and normalized != "/done":
        return await handle_sensitive_panel_message(update, context)
    all_commands = SENSITIVE_ADD_COMMANDS | SENSITIVE_REMOVE_COMMANDS | SENSITIVE_CLEANUP_COMMANDS
    if normalized not in all_commands:
        return False
    if not await is_configured_group_manager(context, chat.id, user.id):
        await message.reply_text(f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> شما مدیر گروه نیستید و دسترسی به سیستم حساسیت ندارید.</b>', parse_mode=ParseMode.HTML)
        raise ApplicationHandlerStop()
    db = load_db(); g_data = get_group_data(db, chat.id); sensitive = g_data.setdefault("sensitive_items", {})
    if normalized in SENSITIVE_CLEANUP_COMMANDS:
        if not sensitive:
            await message.reply_text(f'<b><tg-emoji emoji-id="{PREMIUM_OK_EMOJI}">✔️</tg-emoji> لیست حساسیت از قبل خالی می‌باشد.</b>', parse_mode=ParseMode.HTML)
        else:
            count = len(sensitive); sensitive.clear(); mark_db_dirty(); save_db(force=True)
            await message.reply_text(f'<b><tg-emoji emoji-id="{SENSITIVE_DONE_EMOJI}">⛔️</tg-emoji> عملیات پاکسازی لیست حساسیت با موفقیت انجام شد.</b>\n\n<b>تعداد {count} محتوا از لیست حساسیت حذف گردید.</b>', parse_mode=ParseMode.HTML)
        raise ApplicationHandlerStop()
    replied = getattr(message, "reply_to_message", None)
    if replied is None:
        await message.reply_text(f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> برای این عملیات باید روی پیام موردنظر ریپلای کنید.</b>', parse_mode=ParseMode.HTML)
        raise ApplicationHandlerStop()
    signature = _sensitive_message_signature(replied)
    if signature is None:
        await message.reply_text(f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> این نوع پیام قابل ثبت در لیست حساسیت نیست.</b>', parse_mode=ParseMode.HTML)
        raise ApplicationHandlerStop()
    kind, key = signature
    if normalized in SENSITIVE_ADD_COMMANDS:
        if key in sensitive:
            await message.reply_text(f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> {html.escape(kind)} از قبل در لیست حساسیت می‌باشد.</b>', parse_mode=ParseMode.HTML)
            raise ApplicationHandlerStop()
        sensitive[key] = {"kind": kind, "message_id": replied.message_id, "created_by": user.id, "created_at": datetime.now().timestamp(), "display": _sensitive_display_from_message(replied, signature)}
        mark_db_dirty(); save_db(force=True)
        await message.reply_text(f'<b><tg-emoji emoji-id="{SENSITIVE_OK_EMOJI}">✔️</tg-emoji> {html.escape(kind)} با موفقیت به لیست حساسیت اضافه شد.</b>', parse_mode=ParseMode.HTML)
    else:
        if key not in sensitive:
            await message.reply_text(f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> {html.escape(kind)} از قبل در لیست حساسیت نبود.</b>', parse_mode=ParseMode.HTML)
            raise ApplicationHandlerStop()
        sensitive.pop(key, None); mark_db_dirty(); save_db(force=True)
        await message.reply_text(f'<b><tg-emoji emoji-id="{SENSITIVE_REMOVE_EMOJI}">🔴</tg-emoji> {html.escape(kind)} با موفقیت از لیست حساسیت حذف گردید.</b>', parse_mode=ParseMode.HTML)
    raise ApplicationHandlerStop()


async def start_sensitive_panel_flow(query, context, chat_id, mode):
    db = load_db(); uid = query.from_user.id
    if not await is_configured_group_manager(context, chat_id, uid):
        await query.answer("این پنل برای شما نیست.", show_alert=True); return
    state = {"chat_id": int(chat_id), "panel_message_id": int(query.message.message_id), "mode": mode, "content_ids": [], "bot_message_ids": [], "count": 0}
    db.setdefault("states", {}).setdefault("waiting_sensitive_panel", {})[str(uid)] = state
    db.setdefault("states", {}).setdefault("sensitive_panel", {})[str(uid)] = {"chat_id": int(chat_id), "message_id": int(query.message.message_id)}
    prompt = '<b><tg-emoji emoji-id="%s">💬</tg-emoji> لطفا محتوای خود را جهت افزودن به لیست حساسیت ارسال کنید.</b>' % SENSITIVE_CHAT_EMOJI if mode == "add" else '<b><tg-emoji emoji-id="%s">❗️</tg-emoji> محتوا را جهت حذف از لیست حساسیت ارسال کنید.</b>' % SENSITIVE_PROMPT_EMOJI
    await query.message.edit_text(prompt, reply_markup=_sensitive_back_keyboard(chat_id), parse_mode=ParseMode.HTML)
    mark_db_dirty(); save_db(force=True); await query.answer()


async def handle_sensitive_panel_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    message = update.message; user = update.effective_user; chat = update.effective_chat
    if not message or not user or not chat or chat.type not in ("group", "supergroup"):
        return False
    db = load_db(); state = db.get("states", {}).get("waiting_sensitive_panel", {}).get(str(user.id))
    if not state or int(state.get("chat_id", 0)) != int(chat.id):
        return False
    if not await is_configured_group_manager(context, chat.id, user.id):
        db["states"]["waiting_sensitive_panel"].pop(str(user.id), None); mark_db_dirty(); save_db(force=True); return False
    if (message.text or "").strip().lower() == "/done":
        return False
    signature = _sensitive_message_signature(message)
    if not signature:
        return False
    kind, key = signature; g = get_group_data(db, chat.id); sensitive = g.setdefault("sensitive_items", {})
    mode = state.get("mode")
    changed = False
    if mode == "add":
        if key in sensitive:
            reply = await message.reply_text(f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> {html.escape(kind)} از قبل در لیست حساسیت می‌باشد.</b>', parse_mode=ParseMode.HTML)
        else:
            sensitive[key] = {"kind": kind, "message_id": message.message_id, "created_by": user.id, "created_at": datetime.now().timestamp(), "display": _sensitive_display_from_message(message, signature)}
            changed = True
            mark_db_dirty(); save_db(force=True)
            reply = await message.reply_text(f'<b><tg-emoji emoji-id="{SENSITIVE_OK_EMOJI}">✔️</tg-emoji> محتوای شما به لیست حساسیت افزوده شد.</b>\n\n<b>محتوای بعدی را ارسال کنید یا با ارسال /done عملیات را به پایان برسانید.</b>', parse_mode=ParseMode.HTML)
    else:
        if key not in sensitive:
            reply = await message.reply_text(f'<b><tg-emoji emoji-id="{SENSITIVE_THINK_EMOJI}">🤔</tg-emoji> این محتوا اصلا در لیست حساسیت وجود ندارد.</b>', parse_mode=ParseMode.HTML)
        else:
            sensitive.pop(key, None); changed = True; mark_db_dirty(); save_db(force=True)
            reply = await message.reply_text(f'<b><tg-emoji emoji-id="{SENSITIVE_REMOVE_DONE_EMOJI}">🔼</tg-emoji> محتوا از حساسیت حذف شد.</b>\n\n<b>محتوای بعدی را ارسال کنید یا با دستور /Done عملیات را به پایان برسانید.</b>', parse_mode=ParseMode.HTML)
    state.setdefault("content_ids", []).append(message.message_id)
    state.setdefault("bot_message_ids", []).append(reply.message_id)
    state["count"] = int(state.get("count", 0)) + (1 if changed else 0)
    mark_db_dirty(); save_db(force=True)
    # Keep the live panel list synchronized while the multi-message flow remains active.
    try:
        await context.bot.edit_message_text(
            text=_sensitive_panel_text(g),
            chat_id=chat.id,
            message_id=int(state.get("panel_message_id", 0)),
            reply_markup=_sensitive_panel_keyboard(chat.id),
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        pass
    raise ApplicationHandlerStop()


async def cancel_sensitive_panel_flow(context, db, user_id: int):
    state = db.get("states", {}).get("waiting_sensitive_panel", {}).pop(str(user_id), None)
    db.get("states", {}).get("sensitive_panel", {}).pop(str(user_id), None)
    if state:
        cid = int(state.get("chat_id", 0))
        for mid in list(state.get("content_ids", [])) + list(state.get("bot_message_ids", [])):
            try: await context.bot.delete_message(cid, int(mid))
            except Exception: pass
    mark_db_dirty(); save_db(force=True)


async def sensitive_panel_done(update, context) -> bool:
    if not update.message: return False
    uid = str(update.effective_user.id); db = load_db(); state = db.get("states", {}).get("waiting_sensitive_panel", {}).get(uid)
    if not state: return False
    cid = int(state.get("chat_id", 0)); panel_id = int(state.get("panel_message_id", 0))
    if not await is_configured_group_manager(context, cid, int(uid)):
        return False
    for mid in list(state.get("content_ids", [])) + list(state.get("bot_message_ids", [])):
        try: await context.bot.delete_message(cid, int(mid))
        except Exception: pass
    g = get_group_data(db, cid); count = int(state.get("count", 0)); mode = state.get("mode", "add")
    db["states"]["waiting_sensitive_panel"].pop(uid, None)
    db.get("states", {}).get("sensitive_panel", {}).pop(uid, None)
    mark_db_dirty(); save_db(force=True)
    if mode == "add":
        text = f'<b><tg-emoji emoji-id="{SENSITIVE_DONE_EMOJI}">👌</tg-emoji> حساسیت انجام شد.</b>\n\n<b>تعداد محتوا های حساس شده : {count}</b>'
    else:
        text = f'<b><tg-emoji emoji-id="{SENSITIVE_OPERATION_EMOJI}">⛔️</tg-emoji> عملیات انجام شد.</b>\n\n<b>تعداد {count} محتوا با موفقیت از لیست حساسیت حذف گردید.</b>'
    try:
        await context.bot.edit_message_text(text=text, chat_id=cid, message_id=panel_id, reply_markup=_sensitive_back_keyboard(cid), parse_mode=ParseMode.HTML)
    except Exception:
        pass
    return True


async def enforce_sensitive_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message or update.edited_message; chat = update.effective_chat; user = update.effective_user
    if not message or not chat or chat.type not in ("group", "supergroup") or not user: return
    db = load_db(); g_data = get_group_data(db, chat.id); sensitive = g_data.get("sensitive_items", {}) or {}
    if not sensitive: return
    if user.is_bot or await is_configured_group_manager(context, chat.id, user.id): return
    signature = _sensitive_message_signature(message)
    if not signature: return
    if signature[1] not in sensitive: return
    try: await message.delete()
    except Exception: pass
    raise ApplicationHandlerStop()
