# GoodiBot - group default permissions panel
from core import *
import inspect

GROUP_PERMISSION_EMOJIS = {
    "send_messages": "5830106027701314719",
    "send_photos": "5854818638162304218",
    "send_videos": "5911092197322661106",
    "send_video_notes": "5875065225664798722",
    "send_audios": "5082523762461508199",
    "send_voice_notes": "5080499179302683244",
    "send_documents": "5253742260054409879",
    "send_other_messages": "5197270281994921791",
    "send_polls": "5350310124349053625",
    "link_previews": "5197166786167986122",
    "react": "5195131457000989269",
    "edit_tag": "5197499598888785929",
    "change_info": "5197418402532054381",
    "invite_users": "5424756785355445731",
    "pin_messages": "5397782960512444700",
    "back": "5823664135103061930",
}

GROUP_PERMISSION_ITEMS = [
    ("send_messages", "ارسال پیام", "can_send_messages"),
    ("send_photos", "ارسال عکس", "can_send_photos"),
    ("send_videos", "ارسال ویدیو", "can_send_videos"),
    ("send_video_notes", "ارسال ویدیو سلفی", "can_send_video_notes"),
    ("send_audios", "ارسال آهنگ", "can_send_audios"),
    ("send_voice_notes", "ارسال ویس", "can_send_voice_notes"),
    ("send_documents", "ارسال فایل", "can_send_documents"),
    ("send_other_messages", "ارسال استیکر و گیف", "can_send_other_messages"),
    ("send_polls", "ارسال نظرسنجی", "can_send_polls"),
    ("link_previews", "پیش‌نمایش لینک", "can_add_web_page_previews"),
    ("react", "ری‌اکشن‌ها", "can_react_to_messages"),
    ("edit_tag", "ویرایش تگ شخصی", "can_edit_tag"),
    ("change_info", "تغییر اطلاعات گروه", "can_change_info"),
    ("invite_users", "دعوت کاربران", "can_invite_users"),
    ("pin_messages", "سنجاق کردن", "can_pin_messages"),
]


def _permissions_bot_can_change(member) -> bool:
    return (
        getattr(member, "status", None) == ChatMemberStatus.OWNER
        or (
            getattr(member, "status", None) == ChatMemberStatus.ADMINISTRATOR
            and bool(getattr(member, "can_restrict_members", False))
        )
    )


async def bot_can_change_group_permissions(context, chat_id: int) -> bool:
    try:
        me = await context.bot.get_me()
        member = await context.bot.get_chat_member(chat_id, me.id)
        return _permissions_bot_can_change(member)
    except Exception:
        logger.exception("Failed to check group permission rights | chat_id=%s", chat_id)
        return False


def _chat_permission_value(permissions, attr: str, default: bool = True) -> bool:
    value = getattr(permissions, attr, None) if permissions is not None else None
    return default if value is None else bool(value)


async def get_group_default_permissions(context, chat_id: int) -> dict:
    """Return the current Telegram default permissions as a simple boolean map."""
    chat = await context.bot.get_chat(chat_id)
    permissions = getattr(chat, "permissions", None)
    result = {}
    for key, _label, attr in GROUP_PERMISSION_ITEMS:
        result[key] = _chat_permission_value(permissions, attr, True)
    return result


def _permission_markup(chat_id: int, states: dict) -> InlineKeyboardMarkup:
    rows = []
    for key, label, _attr in GROUP_PERMISSION_ITEMS:
        blocked = not bool(states.get(key, True))
        rows.append([
            InlineKeyboardButton(
                label,
                callback_data=f"group_perm_toggle:{int(chat_id)}:{key}",
                style="success" if blocked else None,
                icon_custom_emoji_id=GROUP_PERMISSION_EMOJIS.get(key),
            )
        ])
    rows.append([
        InlineKeyboardButton(
            "بازگشت",
            callback_data=f"group_perm_back:{int(chat_id)}",
            style="danger",
            icon_custom_emoji_id=GROUP_PERMISSION_EMOJIS["back"],
        )
    ])
    return InlineKeyboardMarkup(rows)


def group_permissions_text(chat_title: str) -> str:
    title = html.escape(chat_title or "گروه")
    return (
        '<b><tg-emoji emoji-id="6008257491568172845">⛔️</tg-emoji> به بخش اختیارات گروه خوش آمدید.</b>\n'
        f'<b>- نام گروه : {title}</b>\n\n'
        '<b><tg-emoji emoji-id="5965474544943638848">🔼</tg-emoji> لطفا مشخص کنید چه ویژگی‌ای خاموش یا روشن شود:</b>'
    )


async def render_group_permissions_panel(query, context, chat_id: int):
    if not await is_configured_group_manager(context, chat_id, query.from_user.id):
        await query.answer("این پنل برای شما نیست.", show_alert=True)
        return
    if not await bot_can_change_group_permissions(context, chat_id):
        await query.answer("ربات دسترسی کافی برای تغییر دسترسی‌های گروه را ندارد.", show_alert=True)
        return
    try:
        chat = await context.bot.get_chat(chat_id)
        states = await get_group_default_permissions(context, chat_id)
        await query.message.edit_text(
            group_permissions_text(getattr(chat, "title", "گروه")),
            reply_markup=_permission_markup(chat_id, states),
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        logger.exception("Failed to render group permissions panel | chat_id=%s", chat_id)
        await query.answer("نمایش اختیارات گروه ناموفق بود.", show_alert=True)


async def _set_permission(context, chat_id: int, key: str, allowed: bool):
    chat = await context.bot.get_chat(chat_id)
    current = getattr(chat, "permissions", None)
    values = {}
    for item_key, _label, attr in GROUP_PERMISSION_ITEMS:
        values[attr] = _chat_permission_value(current, attr, True)
    target_attr = next((attr for item_key, _label, attr in GROUP_PERMISSION_ITEMS if item_key == key), None)
    if not target_attr:
        raise ValueError("unknown group permission")
    values[target_attr] = bool(allowed)

    # Keep every permission Telegram currently exposes, including fields not
    # represented by this panel (e.g. topic creation), instead of accidentally
    # resetting unrelated group settings.
    for attr in ("can_manage_topics", "can_create_topics"):
        if hasattr(current, attr):
            values[attr] = _chat_permission_value(current, attr, True)

    supported = set(inspect.signature(ChatPermissions).parameters)
    kwargs = {k: v for k, v in values.items() if k in supported}
    await context.bot.set_chat_permissions(
        chat_id=chat_id,
        permissions=ChatPermissions(**kwargs),
        use_independent_chat_permissions=True,
    )


async def handle_group_permissions_callback(query, context, db, data: str) -> bool:
    if data == "advanced_group_permissions:" or data.startswith("advanced_group_permissions:"):
        cid = int(data.split(":", 1)[1])
        if not await is_configured_group_manager(context, cid, query.from_user.id):
            await query.answer("این پنل برای شما نیست.", show_alert=True)
            return True
        if not await bot_can_change_group_permissions(context, cid):
            await query.answer("ربات دسترسی کافی برای تغییر دسترسی‌های گروه را ندارد.", show_alert=True)
            return True
        await render_group_permissions_panel(query, context, cid)
        return True

    if data.startswith("group_perm_toggle:"):
        parts = data.split(":", 2)
        if len(parts) != 3:
            await query.answer("دکمه نامعتبر است.", show_alert=True)
            return True
        cid, key = int(parts[1]), parts[2]
        if not await is_configured_group_manager(context, cid, query.from_user.id):
            await query.answer("این پنل برای شما نیست.", show_alert=True)
            return True
        if not await bot_can_change_group_permissions(context, cid):
            await query.answer("ربات دسترسی کافی برای تغییر دسترسی‌های گروه را ندارد.", show_alert=True)
            return True
        states = await get_group_default_permissions(context, cid)
        if key not in states:
            await query.answer("گزینه نامعتبر است.", show_alert=True)
            return True
        try:
            await _set_permission(context, cid, key, not states[key])
            await render_group_permissions_panel(query, context, cid)
            await query.answer()
        except Exception as e:
            logger.exception("Group permission toggle failed | chat_id=%s | key=%s", cid, key)
            await query.answer("تغییر دسترسی انجام نشد.", show_alert=True)
        return True

    if data.startswith("group_perm_back:"):
        cid = int(data.split(":", 1)[1])
        if not await is_configured_group_manager(context, cid, query.from_user.id):
            await query.answer("این پنل برای شما نیست.", show_alert=True)
            return True
        text = get_advanced_status_text(db, cid)
        await query.message.edit_text(text, reply_markup=build_advanced_panel_keyboard(cid), parse_mode=ParseMode.HTML)
        await query.answer()
        return True

    return False
