# GoodiBot comment-posting feature
from core import *

COMMENT_PANEL_EMOJI = "5908745251098473369"
COMMENT_CLOSE_EMOJI = CLOSE_CUSTOM_EMOJI_ID
COMMENT_OK_EMOJI = CHECK_CUSTOM_EMOJI_ID
COMMENT_CROSS_EMOJI = CROSS_CUSTOM_EMOJI_ID
COMMENT_INFO_EMOJI = "5899859522108789256"
COMMENT_ARROW_EMOJI = "6026095130698584657"
COMMENT_SUCCESS_EMOJI = "6026250741658685640"
COMMENT_ROCKET_EMOJI = "5899731270090363274"
COMMENT_WARN_EMOJI = "5902362294041448273"

COMMENT_LIST_COMMANDS = {
    "لیست کامنت", "کامنت چیه", "کامنت فعال نشون بده",
    "گودی لیست کامنت", "لیست کامنت‌ها", "لیست کامنت ها"
}
COMMENT_ON_COMMANDS = {
    "کامنت روشن", "کامنت فعال", "کامنت کانال روشن",
    "گودی کامنت فعال", "گودی کامنت وصل کن"
}
COMMENT_OFF_COMMANDS = {
    "گودی کامنت ببند", "گودی کامنت خاموش", "گودی کامنت حذف",
    "کامنت غیرفعال", "قفل کامنت", "بستن کامنت"
}
COMMENT_DELETE_COMMANDS = {"پاکسازی کامنت", "حذف کامنت", "گودی کامنت حذف کن"}

def is_comment_list_command(text): return (text or "").strip().lower() in COMMENT_LIST_COMMANDS
def is_comment_on_command(text): return (text or "").strip().lower() in COMMENT_ON_COMMANDS
def is_comment_off_command(text): return (text or "").strip().lower() in COMMENT_OFF_COMMANDS
def is_comment_delete_command(text): return (text or "").strip().lower() in COMMENT_DELETE_COMMANDS

def _comment_settings(g):
    c = g.setdefault("comment", {"enabled": False, "custom": False, "payload": None})
    c.setdefault("enabled", False)
    c.setdefault("custom", bool(c.get("payload")))
    c.setdefault("payload", None)
    return c

def _session(db, user_id):
    return db.setdefault("states", {}).setdefault("comment_panel", {}).get(str(user_id))

def set_comment_panel_session(db, user_id, chat_id, message_id):
    db.setdefault("states", {}).setdefault("comment_panel", {})[str(user_id)] = {
        "chat_id": int(chat_id), "message_id": int(message_id)
    }
    mark_db_dirty()

def clear_comment_panel_session(db, user_id):
    db.setdefault("states", {}).setdefault("comment_panel", {}).pop(str(user_id), None)
    mark_db_dirty()

async def comment_panel_owner(query, context, db, chat_id):
    uid = query.from_user.id
    if not await is_configured_group_manager(context, chat_id, uid):
        await query.answer("این پنل برای شما نیست.", show_alert=True)
        return False
    s = _session(db, uid)
    if not s or int(s.get("chat_id", 0)) != int(chat_id) or int(s.get("message_id", 0)) != int(query.message.message_id):
        await query.answer("این پنل برای شما نیست.", show_alert=True)
        return False
    return True

def comment_close_keyboard(callback_data):
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("بستن", callback_data=callback_data, style="danger", icon_custom_emoji_id=COMMENT_CLOSE_EMOJI)
    ]])

def comment_panel_keyboard(chat_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("تنظیم کامنت", callback_data=f"comment_set:{chat_id}", style="success", icon_custom_emoji_id=COMMENT_OK_EMOJI)],
        [InlineKeyboardButton("بازگشت", callback_data=f"panel_group_advanced:{chat_id}", style="danger", icon_custom_emoji_id=BACK_CUSTOM_EMOJI_ID)]
    ])

def comment_setup_prompt():
    return (
        f'<b><tg-emoji emoji-id="{COMMENT_INFO_EMOJI}">🩵</tg-emoji> کامنت خود را جهت ارسال زیر پست‌های کانال متصل به این گروه ارسال کنید.</b>\n\n'
        f'<b><tg-emoji emoji-id="{COMMENT_ARROW_EMOJI}">👆</tg-emoji> ربات کاملا از ایموجی های پریموم و مدیا پشتیبانی می‌کند و امکان ثبت هرگونه پیامی وجود دارد.</b>\n\n'
        f'<b><tg-emoji emoji-id="{COMMENT_SUCCESS_EMOJI}">⭐️</tg-emoji> کامنت خود را همین‌جا ارسال بفرمایید.</b>'
    )

def comment_list_text(g):
    c = _comment_settings(g)
    payload = c.get("payload")
    if payload:
        if payload.get("type") == "text":
            label = payload.get("text", "").replace("<", "").replace(">", "").strip()
        else:
            label = "پیام رسانه‌ای تنظیم‌شده"
    else:
        label = "تنظیم نشده"
    status = "فعال" if c.get("enabled") else "غیرفعال"
    return (
        f'<b><tg-emoji emoji-id="5899782925662032320">⭕️</tg-emoji> لیست کامنت‌ فعال گروه به شرح ذیل می‌باشد:</b>\n\n'
        f'<b>- {html.escape(label)}</b>\n\n'
        f'<b><tg-emoji emoji-id="5341671394633607935">🔵</tg-emoji> وضعیت ارسال کامنت زیر پست‌های کانال متصل به این گروه: {status}</b>'
    )

async def render_comment_list(query, context, chat_id, db):
    if not await is_configured_group_manager(context, chat_id, query.from_user.id):
        await query.answer("این پنل برای شما نیست.", show_alert=True)
        return
    g = get_group_data(db, chat_id)
    await query.message.edit_text(
        comment_list_text(g),
        reply_markup=comment_close_keyboard(f"comment_list_close:{chat_id}"),
        parse_mode=ParseMode.HTML
    )
    set_comment_panel_session(db, query.from_user.id, chat_id, query.message.message_id)
    save_db(force=True)

async def render_comment_panel(query, context, chat_id, db):
    if not await is_configured_group_manager(context, chat_id, query.from_user.id):
        await query.answer("این پنل برای شما نیست.", show_alert=True)
        return
    await query.message.edit_text(
        comment_setup_prompt(),
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("بازگشت", callback_data=f"comment_panel_back:{chat_id}", style="danger", icon_custom_emoji_id=BACK_CUSTOM_EMOJI_ID)
        ]]),
        parse_mode=ParseMode.HTML
    )
    set_comment_panel_session(db, query.from_user.id, chat_id, query.message.message_id)
    # The panel text itself tells the manager to send the comment immediately.
    # Put the user into the pending-comment state here so the next message is
    # captured by handle_pending_comment_message.
    db.setdefault("states", {}).setdefault("waiting_comment_msg", {})[str(query.from_user.id)] = {
        "chat_id": int(chat_id), "panel_message_id": int(query.message.message_id)
    }
    mark_db_dirty()
    save_db(force=True)


def _linked_channel_id(chat):
    return getattr(chat, "linked_chat_id", None)

async def get_linked_channel_id(context, chat_id):
    try:
        chat = await context.bot.get_chat(chat_id)
        return _linked_channel_id(chat)
    except Exception:
        return None

async def activate_comments(update, context, chat_id, user_id):
    db = load_db()
    if not await is_admin_or_owner(context, chat_id, user_id):
        await update.message.reply_text(
            f'<b><tg-emoji emoji-id="{COMMENT_CROSS_EMOJI}">❌</tg-emoji> فقط مدیران گروه دسترسی به این دستور را دارند.</b>',
            parse_mode=ParseMode.HTML)
        return
    g = get_group_data(db, chat_id)
    c = _comment_settings(g)
    if c.get("enabled"):
        await update.message.reply_text(
            f'<b><tg-emoji emoji-id="{COMMENT_OK_EMOJI}">✅</tg-emoji> سیستم کامنت‌گذاری از قبل فعال بود.</b>',
            parse_mode=ParseMode.HTML)
        return
    if not c.get("payload"):
        await update.message.reply_text(
            f'<b><tg-emoji emoji-id="{COMMENT_CROSS_EMOJI}">❌</tg-emoji> هنوز هیچ کامنتی برای این گروه تنظیم نشده است.</b>',
            parse_mode=ParseMode.HTML)
        return
    linked = await get_linked_channel_id(context, chat_id)
    if not linked:
        await update.message.reply_text(
            f'<b><tg-emoji emoji-id="{COMMENT_WARN_EMOJI}">⚠️</tg-emoji> هیچ کانالی به این گروه متصل نیست!!\nلطفا مجددا چک بفرمایید.</b>',
            parse_mode=ParseMode.HTML)
        return
    c["enabled"] = True
    mark_db_dirty(); save_db(force=True)
    label = c["payload"].get("text", "") if c["payload"].get("type") == "text" else "پیام رسانه‌ای تنظیم‌شده"
    await update.message.reply_text(
        f'<b><tg-emoji emoji-id="{COMMENT_OK_EMOJI}">✅</tg-emoji> کامنت گروه با موفقیت فعال شد.</b>\n'
        f'<b>- <tg-emoji emoji-id="5830381159011326872">⚡️</tg-emoji> از این لحظه به بعد هر پیامی داخل کانال متصل به گروه ارسال شود ربات پیام تنظیم شده را زیر آن کامنت خواهد کرد.</b>\n\n'
        f'<b><tg-emoji emoji-id="5830338333892418460">📦</tg-emoji> پیام تنظیم شده‌:</b>\n\n'
        f'<b>- {html.escape(label)}</b>',
        parse_mode=ParseMode.HTML)

async def deactivate_comments(update, context, chat_id, user_id):
    db = load_db()
    if not await is_admin_or_owner(context, chat_id, user_id):
        await update.message.reply_text(
            f'<b><tg-emoji emoji-id="{COMMENT_CROSS_EMOJI}">❌</tg-emoji> فقط مدیران گروه دسترسی به این دستور را دارند.</b>',
            parse_mode=ParseMode.HTML)
        return
    g = get_group_data(db, chat_id)
    c = _comment_settings(g)
    if not c.get("enabled"):
        await update.message.reply_text(
            f'<b><tg-emoji emoji-id="{COMMENT_CROSS_EMOJI}">❌</tg-emoji> سیستم کامنت‌گذاری از قبل غیرفعال بود.</b>',
            parse_mode=ParseMode.HTML)
        return
    c["enabled"] = False
    mark_db_dirty(); save_db(force=True)
    await update.message.reply_text(
        f'<b><tg-emoji emoji-id="5899731270090363274">👨‍🚀</tg-emoji> سیستم کامنت‌گذاری با موفقیت بسته شد.</b>',
        parse_mode=ParseMode.HTML)

async def handle_automatic_channel_comments(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not getattr(msg, "is_automatic_forward", False):
        return
    chat = update.effective_chat
    if not chat or chat.type not in ["group", "supergroup"]:
        return
    db = load_db()
    g_data = get_group_data(db, chat.id)
    c = _comment_settings(g_data)
    if not c.get("enabled") or not c.get("payload"):
        return
    # The automatic forward is the discussion-group representation of a
    # post from the linked channel. Replying to that message creates the
    # channel comment thread.
    linked = await get_linked_channel_id(context, chat.id)
    if not linked:
        return
    msg_key = f"{chat.id}_{msg.message_id}"
    commented_posts = db.setdefault("commented_channel_posts", [])
    if msg_key in commented_posts:
        return
    if await send_media_payload(context.bot, chat.id, c["payload"], reply_to_message_id=msg.message_id):
        commented_posts.append(msg_key)
        if len(commented_posts) > 1000:
            del commented_posts[:-1000]
        mark_db_dirty(); save_db()

async def save_comment_from_message(update, context, target_cid):
    db = load_db()
    user_id = update.effective_user.id
    state = db.setdefault("states", {}).setdefault("waiting_comment_msg", {}).get(str(user_id))
    if state is None:
        return False
    if isinstance(state, dict):
        target_cid = int(state.get("chat_id", target_cid))
        panel_message_id = state.get("panel_message_id")
    else:
        target_cid = int(state)
        panel_message_id = None
    if not await is_configured_group_manager(context, target_cid, user_id):
        db["states"]["waiting_comment_msg"].pop(str(user_id), None)
        mark_db_dirty(); save_db(force=True)
        return False
    payload = extract_media_payload(update.message)
    if not payload:
        logger.warning("Comment setup message received but no supported payload was extracted: user=%s chat=%s message=%s", user_id, target_cid, getattr(update.message, "message_id", None))
        return False
    db["states"]["waiting_comment_msg"].pop(str(user_id), None)
    g = get_group_data(db, target_cid)
    g["comment"] = {"enabled": False, "custom": True, "payload": payload}
    mark_db_dirty(); save_db(force=True)
    try:
        await update.message.delete()
    except Exception:
        pass
    success = (
        f'<b><tg-emoji emoji-id="{COMMENT_SUCCESS_EMOJI}">👨‍💻</tg-emoji> کامنت موردنظر با موفقیت ثبت و تنظیم شد.</b>\n\n'
        f'<b><tg-emoji emoji-id="{COMMENT_ARROW_EMOJI}">🤝</tg-emoji> با ارسال دستور <code>کامنت فعال</code> میتوانید دستور مربوطه را روشن بفرمایید.</b>'
    )
    if panel_message_id:
        try:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=int(panel_message_id),
                text=success,
                parse_mode=ParseMode.HTML
            )
            set_comment_panel_session(db, user_id, target_cid, int(panel_message_id))
            save_db(force=True)
            return True
        except Exception:
            pass
    await update.message.reply_text(success, parse_mode=ParseMode.HTML)
    return True

async def comment_cleanup_confirm(query, context, chat_id, db):
    if not await comment_panel_owner(query, context, db, chat_id):
        return
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("بله", callback_data=f"comment_cleanup:yes:{chat_id}", style="success", icon_custom_emoji_id=COMMENT_OK_EMOJI),
        InlineKeyboardButton("بستن", callback_data=f"comment_cleanup:no:{chat_id}", style="danger", icon_custom_emoji_id=COMMENT_CROSS_EMOJI)
    ]])
    await query.message.edit_text("<b>آیا از حذف کامل کامنت ذخیره‌شده مطمئن هستید؟</b>", reply_markup=kb, parse_mode=ParseMode.HTML)

async def comment_cleanup_execute(query, context, chat_id, db, yes):
    if not await comment_panel_owner(query, context, db, chat_id):
        return
    if yes:
        g = get_group_data(db, chat_id)
        g["comment"] = {"enabled": False, "custom": False, "payload": None}
        mark_db_dirty(); save_db(force=True)
        text = f'<b><tg-emoji emoji-id="{COMMENT_OK_EMOJI}">✅</tg-emoji> کامنت با موفقیت حذف شد.</b>'
    else:
        text = f'<b><tg-emoji emoji-id="{COMMENT_OK_EMOJI}">✅</tg-emoji> پنل پاکسازی کامنت با موفقیت بسته شد.</b>'
    await query.message.edit_text(text, reply_markup=None, parse_mode=ParseMode.HTML)
    clear_comment_panel_session(db, query.from_user.id)
    save_db(force=True)
