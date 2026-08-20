# GoodiBot modular feature module
from core import *

async def check_bot_admin_and_link_rights(context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> bool:
    try:
        bot_member = await cached_chat_member(context, chat_id, context.bot.id)
        if bot_member.status != ChatMemberStatus.ADMINISTRATOR:
            return False
        if not getattr(bot_member, "can_invite_users", True):
            return False
        return True
    except Exception:
        return False

async def get_or_create_group_invite_link(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    expire_date=None,
    member_limit: int = None,
) -> str | None:
    """Create a real invite link and never silently downgrade special links.

    For a normal link we can fall back to export_chat_invite_link().
    For a limited/expiring link we MUST NOT fall back, because the exported
    link would not have the requested restrictions.
    """
    try:
        kwargs = {"chat_id": chat_id}
        if expire_date is not None:
            kwargs["expire_date"] = expire_date
        if member_limit is not None:
            kwargs["member_limit"] = member_limit

        link_obj = await context.bot.create_chat_invite_link(**kwargs)
        link = getattr(link_obj, "invite_link", None)
        if not link:
            logger.error("Invite link API returned no invite_link for chat_id=%s", chat_id)
            return None
        try:
            db = load_db()
            get_group_data(db, chat_id)["invite_link"] = link
            mark_db_dirty()
            save_db()
        except Exception:
            logger.exception("Failed to persist generated invite link | chat_id=%s", chat_id)
        return link
    except Exception as e:
        logger.exception(
            "create_chat_invite_link failed | chat_id=%s | expire_date=%r | member_limit=%r",
            chat_id, expire_date, member_limit
        )

        # Never replace a one-time/limited link with an unrestricted link.
        if expire_date is not None or member_limit is not None:
            return None

        try:
            link = await context.bot.export_chat_invite_link(chat_id)
            if not link:
                logger.error("export_chat_invite_link returned no link for chat_id=%s", chat_id)
                return None
            try:
                db = load_db()
                get_group_data(db, chat_id)["invite_link"] = link
                mark_db_dirty()
                save_db()
            except Exception:
                logger.exception("Failed to persist exported invite link | chat_id=%s", chat_id)
            return link
        except Exception:
            logger.exception("export_chat_invite_link failed | chat_id=%s", chat_id)
            return None

def build_link_panel_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("دریافت لینک بصورت متن", callback_data=f"link_panel:text:{chat_id}", icon_custom_emoji_id="5942921379614565429")],
        [InlineKeyboardButton("دریافت لینک بصورت عکس", callback_data=f"link_panel:photo:{chat_id}", icon_custom_emoji_id="5942921379614565429")],
        [InlineKeyboardButton("دریافت لینک یک‌بار مصرف", callback_data=f"link_panel:once:{chat_id}", icon_custom_emoji_id="5942921379614565429")],
        [InlineKeyboardButton("دریافت لینک در پیوی", callback_data=f"link_panel:pv:{chat_id}", icon_custom_emoji_id="5942921379614565429")],
        [InlineKeyboardButton("بستن", callback_data=f"link_panel:close:{chat_id}", style="danger", icon_custom_emoji_id="5983093054842606366")]
    ])

def build_link_sub_keyboard(chat_id: int, is_once: bool = False, invite_link: str | None = None) -> InlineKeyboardMarkup:
    share_url = f"https://t.me/share/url?url={quote(invite_link, safe='')}" if invite_link else None
    share_button = (
        InlineKeyboardButton("اشتراک‌گذاری", url=share_url, style="primary", icon_custom_emoji_id="6030354793363413800")
        if share_url else
        InlineKeyboardButton("اشتراک‌گذاری", callback_data=f"link_sub:share:{chat_id}", style="primary", icon_custom_emoji_id="6030354793363413800")
    )
    if is_once:
        return InlineKeyboardMarkup([
            [share_button],
            [InlineKeyboardButton("بازگشت", callback_data=f"link_sub:back:{chat_id}", style="danger", icon_custom_emoji_id="5823664135103061930")]
        ])
    return InlineKeyboardMarkup([
        [share_button],
        [InlineKeyboardButton("حذف و ساخت لینک جدید", callback_data=f"link_sub:revoke:{chat_id}", style="success", icon_custom_emoji_id="6293870742282965014")],
        [InlineKeyboardButton("بازگشت", callback_data=f"link_sub:back:{chat_id}", style="danger", icon_custom_emoji_id="5823664135103061930")]
    ])

async def get_group_photo_for_send(context: ContextTypes.DEFAULT_TYPE, chat_obj):
    """Download the actual group photo bytes so Telegram never receives a ChatPhoto object as photo input."""
    photo = getattr(chat_obj, "photo", None)
    file_id = getattr(photo, "big_file_id", None) if photo else None
    if not file_id:
        return None
    tg_file = await context.bot.get_file(file_id)
    data = await tg_file.download_as_bytearray()
    return bytes(data)

async def generate_group_link_text_payload(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    is_once: bool = False,
) -> str:
    chat_obj = await context.bot.get_chat(chat_id)
    title = html.escape(chat_obj.title or "گروه")
    member_count = await context.bot.get_chat_member_count(chat_id)

    if is_once:
        from datetime import datetime, timedelta, timezone
        expire_at = datetime.now(timezone.utc) + timedelta(days=1)
        link = await get_or_create_group_invite_link(
            context, chat_id, expire_date=expire_at, member_limit=1
        )
        if not link:
            raise RuntimeError("ساخت لینک یک‌بارمصرف از Telegram API ناموفق بود.")
        return (
            f'<tg-emoji emoji-id="6008070651900861977">📤</tg-emoji> <b>لینک یک‌بار مصرف شما آماده است.</b>\n\n'
            f'<tg-emoji emoji-id="5803420768826038185">🔘</tg-emoji> <b>نام گروه :</b> {title}\n'
            f'<tg-emoji emoji-id="5802963792895678011">⚫️</tg-emoji> <b>تعداد عضو :</b> {member_count}\n'
            f'<tg-emoji emoji-id="5803057229909202251">♻️</tg-emoji> <b>تاریخ انقضا لینک :</b> 24 ساعت\n'
            f'<tg-emoji emoji-id="5803351177470940363">🗣</tg-emoji> <b>افراد مجاز :</b> 1\n\n'
            f'<tg-emoji emoji-id="6008124493610885197">🔗</tg-emoji><tg-emoji emoji-id="6008124493610885197">🔗</tg-emoji><tg-emoji emoji-id="6008124493610885197">🔗</tg-emoji><tg-emoji emoji-id="6008124493610885197">🔗</tg-emoji><tg-emoji emoji-id="6008124493610885197">🔗</tg-emoji><tg-emoji emoji-id="6008124493610885197">🔗</tg-emoji><tg-emoji emoji-id="6008124493610885197">🔗</tg-emoji>\n\n'
            f'<tg-emoji emoji-id="6032888897082497570">📤</tg-emoji> <b>لینک گروه :</b>\n\n- {link}'
        )

    link = await get_or_create_group_invite_link(context, chat_id)
    if not link:
        raise RuntimeError("ساخت لینک گروه از Telegram API ناموفق بود.")
    return (
        f'<tg-emoji emoji-id="5803420768826038185">🔘</tg-emoji> <b>نام گروه :</b> {title}\n'
        f'<tg-emoji emoji-id="5802963792895678011">⚫️</tg-emoji> <b>تعداد عضو :</b> {member_count}\n\n'
        f'<tg-emoji emoji-id="6008124493610885197">🔗</tg-emoji><tg-emoji emoji-id="6008124493610885197">🔗</tg-emoji><tg-emoji emoji-id="6008124493610885197">🔗</tg-emoji><tg-emoji emoji-id="6008124493610885197">🔗</tg-emoji><tg-emoji emoji-id="6008124493610885197">🔗</tg-emoji><tg-emoji emoji-id="6008124493610885197">🔗</tg-emoji><tg-emoji emoji-id="6008124493610885197">🔗</tg-emoji>\n\n'
        f'<tg-emoji emoji-id="6032888897082497570">📤</tg-emoji> <b>لینک گروه :</b>\n\n- {link}'
    )
