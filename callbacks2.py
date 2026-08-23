# GoodiBot - Tagging callbacks (new module; existing callbacks.py is untouched)
from core import *
from telegram import ReplyParameters
from handler2 import _collect_manager_tag_users, _collect_recent_tag_users, _send_tagged_users, _tag_display


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

        # Delete the whole selection panel immediately after a valid choice.
        # Removing only the keyboard leaves the panel message visible in the
        # chat, which is not the intended UX. Send the result as a fresh message.
        try:
            await query.message.delete()
        except Exception:
            logger.exception("Could not delete tag panel | chat_id=%s", chat_id)

        # The panel itself is anchored to the original replied message when
        # the user opened the tag panel as a reply. Reuse that message as the
        # reply target for every tag result. With no original reply, results
        # are sent normally (no reply).
        replied = getattr(query.message, "reply_to_message", None)
        reply_to_message_id = getattr(replied, "message_id", None) if replied is not None else None
        reply_kwargs = {}
        if reply_to_message_id is not None:
            reply_kwargs["reply_parameters"] = ReplyParameters(message_id=int(reply_to_message_id))

        if not users:
            await context.bot.send_message(
                chat_id=chat_id,
                text="کاربری برای تگ کردن پیدا نشد.",
                **reply_kwargs,
            )
        else:
            # Always send six tagged users per message, then continue with the
            # next six. The final message may contain fewer than six.
            chunks = []
            batch = []
            for uid, username, fullname in users:
                batch.append(_tag_display(uid, username, fullname))
                if len(batch) == 6:
                    chunks.append(" - ".join(batch))
                    batch = []
            if batch:
                chunks.append(" - ".join(batch))

            for chunk in chunks:
                await context.bot.send_message(
                    chat_id=chat_id,
                    text=chunk,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True,
                    **reply_kwargs,
                )

        await query.answer()
    except Exception:
        logger.exception("Tag callback failed | chat_id=%s | user_id=%s | action=%s", chat_id, user_id, action)
        await query.answer("اجرای تگ ناموفق بود.", show_alert=True)
    return True
