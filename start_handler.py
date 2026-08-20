# GoodiBot private /start fast-path
# This handler intentionally does not call Telegram getMe() while processing /start.
# The visible PV response must never wait for an extra network request.

from core import *
from auto_responses import enter_auto_response_manager


async def command_start_private(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start in private chats without any blocking pre-response API call."""
    if not update.message:
        return

    chat = update.effective_chat
    if not chat or chat.type != "private":
        return

    user = update.effective_user
    if user and user.is_bot:
        return

    # Preserve the existing automatic-response deep-link flow.
    args = list(getattr(context, "args", []) or [])
    if user and args and args[0].startswith("autoresp_"):
        try:
            target_group_id = int(args[0].split("_", 1)[1])
        except (ValueError, IndexError):
            target_group_id = 0
        if target_group_id:
            await enter_auto_response_manager(update, context, target_group_id)
            return

    # IMPORTANT: do not call context.bot.get_me() here.
    # Application startup already initializes the bot. If username is available,
    # use the cached value; otherwise send the message without a URL rather than
    # making /start wait on another Telegram API request.
    bot_username = getattr(context.bot, "username", None) or os.getenv("BOT_USERNAME", "")
    bot_username = str(bot_username).lstrip("@").strip()

    start_pv_msg = (
        '<b>سلام عزیزم! به ربات جذاب من خوش اومدی! <tg-emoji emoji-id="5816739230482701944">⚡️</tg-emoji></b>\n'
        '<b>با استفاده از دکمه شیشه‌ای زیر منو به گروهت اضافه کن! <tg-emoji emoji-id="5818785846823755322">😻</tg-emoji></b>\n\n'
        '<b>بعد از اضافه کردن با ارسال دستور راهنما میتونی با من آشنا بشی! <tg-emoji emoji-id="5818984798298841943">⏳</tg-emoji></b>'
    )

    button_kwargs = {
        "style": "success",
        "icon_custom_emoji_id": "4956745198521549627",
    }
    if bot_username:
        button_kwargs["url"] = f"https://t.me/{bot_username}?startgroup=true"

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("اضافه کردن گودی به گروه", **button_kwargs)]
    ])

    # This is intentionally the first Telegram API call in the normal /start path.
    await update.message.reply_text(
        start_pv_msg,
        reply_markup=kb,
        parse_mode=ParseMode.HTML,
    )

    # Existing started-user persistence is kept, but it can never prevent the
    # visible /start response from being delivered.
    if user:
        try:
            db = load_db()
            cancel_auto_response_flow(db, user.id)
            uid_str = str(user.id)
            started_users = db.setdefault("started_users", {})
            now_ts = datetime.now().timestamp()
            if uid_str not in started_users:
                started_users[uid_str] = {
                    "user_id": user.id,
                    "username": user.username or "",
                    "fullname": user.full_name or "کاربر",
                    "first_seen": now_ts,
                    "last_seen": now_ts,
                }
            else:
                started_users[uid_str]["last_seen"] = now_ts
                started_users[uid_str]["fullname"] = user.full_name or "کاربر"
                started_users[uid_str]["username"] = user.username or ""
            mark_db_dirty()
            save_db(force=True)
        except Exception:
            logger.exception("PV /start database bookkeeping failed; response was already sent")
