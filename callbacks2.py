# GoodiBot - Tagging callbacks (new module; existing callbacks.py is untouched)
from core import *
from handler2 import _collect_manager_tag_users, _collect_recent_tag_users, _send_tagged_users


def _tag_close_text():
    return '<b><tg-emoji emoji-id="5830144944399981619">✅</tg-emoji> پنل تگ کردن اعضا با موفقیت بسته شد.</b>'


async def handle_tag_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query or not query.data or not query.message:
        return False
    data = query.data
    if not data.startswith("tag_panel:"):
        return False

    parts = data.split(":")
    if len(parts) != 3:
        await query.answer("اطلاعات دکمه نامعتبر است.", show_alert=True)
        return True

    action = parts[1]
    try:
        owner_id = int(parts[2])
    except ValueError:
        await query.answer("اطلاعات دکمه نامعتبر است.", show_alert=True)
        return True

    user_id = query.from_user.id
    chat_id = query.message.chat.id
    if user_id != owner_id:
        await query.answer("این پنل برای شما نیست.", show_alert=True)
        return True

    if not await is_configured_group_manager(context, chat_id, user_id):
        await query.answer("این دکمه مختص مقامداران ربات می‌باشد.", show_alert=True)
        return True

    db = load_db()

    try:
        if action == "close":
            await query.message.edit_text(_tag_close_text(), reply_markup=None, parse_mode=ParseMode.HTML)
            await query.answer()
            return True

        if action == "managers":
            users = await _collect_manager_tag_users(context, chat_id, db)
        elif action == "recent50":
            users = await _collect_recent_tag_users(context, chat_id, db, 50)
        elif action == "recent300":
            users = await _collect_recent_tag_users(context, chat_id, db, 300)
        else:
            await query.answer("گزینه نامعتبر است.", show_alert=True)
            return True

        # Close the selection panel immediately after a valid choice so the
        # same panel cannot be used repeatedly or remain visually active.
        try:
            await query.message.edit_reply_markup(reply_markup=None)
        except Exception:
            logger.exception("Could not close tag panel | chat_id=%s", chat_id)

        await _send_tagged_users(query.message, users)
        await query.answer()
    except Exception:
        logger.exception("Tag callback failed | chat_id=%s | user_id=%s | action=%s", chat_id, user_id, action)
        await query.answer("اجرای تگ ناموفق بود.", show_alert=True)
    return True
