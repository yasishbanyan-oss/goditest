# GoodiBot - manager command restrictions
from core import *

FEATURE_LOCK_EMOJIS = {
    "header": "5818736497649524154",
    "ban": "5830144944399981619",
    "mute": "5873075766748520540",
    "warn": "5872883940624179027",
    "settings": "5818716826699307883",
    "cleanup": "5901989641204018165",
    "exempt": "5911198059676574025",
    "pin": "5904279000506704761",
    "link": "5397782960512444700",
    "fun": "5899859522108789256",
    "echo": "5339573565102515237",
    "special": "5341671394633607935",
    "back": BACK_CUSTOM_EMOJI_ID,
}

FEATURE_LOCK_LABELS = {
    "ban": "بن",
    "mute": "سکوت",
    "warn": "اخطار",
    "settings": "تنظیمات",
    "cleanup": "پاکسازی",
    "exempt": "معافیت",
    "pin": "سنجاق",
    "link": "لینک",
    "fun": "دستورات سرگرمی",
    "echo": "اکو",
    "special": "افزودن ویژه",
}

FEATURE_LOCK_KEYS = tuple(FEATURE_LOCK_LABELS)


def _feature_lock_store(g_data: dict) -> dict:
    store = g_data.setdefault("feature_locks", {})
    if not isinstance(store, dict):
        store = {}
        g_data["feature_locks"] = store
    for key in FEATURE_LOCK_KEYS:
        store.setdefault(key, False)
    return store


def feature_lock_enabled(g_data: dict, feature: str) -> bool:
    return bool(_feature_lock_store(g_data).get(feature, False))


async def _is_live_group_owner(context, chat_id: int, user_id: int) -> bool:
    try:
        member = await cached_chat_member(context, chat_id, int(user_id))
        return member.status == ChatMemberStatus.OWNER
    except Exception:
        return False


async def _is_live_group_admin(context, chat_id: int, user_id: int) -> bool:
    try:
        member = await cached_chat_member(context, chat_id, int(user_id))
        return member.status == ChatMemberStatus.ADMINISTRATOR
    except Exception:
        return False


async def is_manager_feature_locked(context, chat_id: int, user_id: int, feature: str) -> bool:
    """True only for an ordinary Goodi/Telegram admin when that feature is locked.

    Owners (including the real Telegram group owner), bot owner, special members,
    and exempt members are never blocked by the manager-limit system unless they
    are also explicitly an administrator in the group.
    """
    if feature not in FEATURE_LOCK_KEYS:
        return False
    db = load_db()
    g_data = get_group_data(db, chat_id)
    if not feature_lock_enabled(g_data, feature):
        return False

    uid = int(user_id)
    if uid == int(OWNER_ID):
        return False

    management = g_data.get("management", {}) or {}
    owners = {int(x) for x in management.get("owners", []) or [] if str(x).lstrip("-").isdigit()}
    if uid in owners or is_primary_group_owner_id(g_data, uid):
        return False
    if await _is_live_group_owner(context, chat_id, uid):
        return False

    # The restriction is specifically for managers/admins, not Goodi special/exempt users.
    admins = {int(x) for x in management.get("admins", []) or [] if str(x).lstrip("-").isdigit()}
    return uid in admins or await _is_live_group_admin(context, chat_id, uid)


def feature_lock_block_text(feature: str) -> str:
    label = html.escape(FEATURE_LOCK_LABELS.get(feature, feature))
    return (
        f'<b><tg-emoji emoji-id="5818716826699307883">❗️</tg-emoji> '
        f'دستور {label} از سوی مالک گروه برای تمامی مقامداران بسته شده است.</b>\n\n'
        '<b>- شما مجاز به انجام این دستور نخواهید بود.</b>'
    )


async def enforce_manager_feature(context, chat_id: int, user_id: int, feature: str, message=None) -> bool:
    if not await is_manager_feature_locked(context, chat_id, user_id, feature):
        return False
    if message is not None:
        await message.reply_text(feature_lock_block_text(feature), parse_mode=ParseMode.HTML)
    return True


def _feature_lock_text(g_data: dict) -> str:
    locks = _feature_lock_store(g_data)
    return (
        '<b><tg-emoji emoji-id="5818736497649524154">🔒</tg-emoji> جهت فعال کردن محدودیت برای مدیران گروه از طریق دکمه زیر اقدام کنید.</b>\n\n'
        '<b><tg-emoji emoji-id="5819051035284479206">🚨</tg-emoji> محدودیت ها برای مالکین اعمال نمی‌شوند.</b>'
    )


def _feature_lock_keyboard(chat_id: int, g_data: dict) -> InlineKeyboardMarkup:
    locks = _feature_lock_store(g_data)
    if not locks.get("manager_limit", False):
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(
                "محدودیت مدیران : ❌",
                callback_data=f"feature_lock_toggle:{int(chat_id)}:manager_limit",
                icon_custom_emoji_id=FEATURE_LOCK_EMOJIS["header"],
            )],
            [InlineKeyboardButton(
                "بازگشت",
                callback_data=f"feature_lock_back:{int(chat_id)}",
                style="danger",
                icon_custom_emoji_id=FEATURE_LOCK_EMOJIS["back"],
            )],
        ])

    rows = []
    for key, label in FEATURE_LOCK_LABELS.items():
        enabled = bool(locks.get(key, False))
        rows.append([InlineKeyboardButton(
            f"دسترسی به {label}: {'✅' if enabled else '❌'}",
            callback_data=f"feature_lock_toggle:{int(chat_id)}:{key}",
            style="success" if enabled else None,
            icon_custom_emoji_id=FEATURE_LOCK_EMOJIS.get(key),
        )])
    rows.insert(0, [InlineKeyboardButton(
        "محدودیت مدیران: ✅",
        callback_data=f"feature_lock_toggle:{int(chat_id)}:manager_limit",
        style="success",
        icon_custom_emoji_id=FEATURE_LOCK_EMOJIS["header"],
    )])
    rows.append([InlineKeyboardButton(
        "بازگشت",
        callback_data=f"feature_lock_back:{int(chat_id)}",
        style="danger",
        icon_custom_emoji_id=FEATURE_LOCK_EMOJIS["back"],
    )])
    return InlineKeyboardMarkup(rows)


async def render_feature_locks_panel(query, context, chat_id: int, db: dict):
    if not await is_configured_group_manager(context, chat_id, query.from_user.id):
        await query.answer("این پنل برای شما نیست.", show_alert=True)
        return
    g_data = get_group_data(db, chat_id)
    _feature_lock_store(g_data)
    await query.message.edit_text(
        _feature_lock_text(g_data),
        reply_markup=_feature_lock_keyboard(chat_id, g_data),
        parse_mode=ParseMode.HTML,
    )


async def handle_feature_lock_callback(query, context, db, data: str) -> bool:
    if not data.startswith(("advanced_feature_locks:", "feature_lock_toggle:", "feature_lock_back:")):
        return False

    user_id = int(query.from_user.id)
    try:
        cid = int(data.split(":")[1])
    except (IndexError, ValueError):
        await query.answer("دکمه نامعتبر است.", show_alert=True)
        return True

    if not await is_configured_group_manager(context, cid, user_id):
        await query.answer("این پنل برای شما نیست.", show_alert=True)
        return True

    if data.startswith("advanced_feature_locks:"):
        await render_feature_locks_panel(query, context, cid, db)
        await query.answer()
        return True

    if data.startswith("feature_lock_back:"):
        await query.message.edit_text(
            get_advanced_status_text(db, cid),
            reply_markup=build_advanced_panel_keyboard(cid),
            parse_mode=ParseMode.HTML,
        )
        await query.answer()
        return True

    parts = data.split(":", 2)
    key = parts[2] if len(parts) == 3 else ""
    g_data = get_group_data(db, cid)
    locks = _feature_lock_store(g_data)

    if key == "manager_limit":
        locks["manager_limit"] = not bool(locks.get("manager_limit", False))
        if not locks["manager_limit"]:
            # Keep per-command switches stored, but hide them while the master
            # switch is off. Re-enabling restores their previous state.
            mark_db_dirty(); save_db(force=True)
            await render_feature_locks_panel(query, context, cid, db)
            await query.answer("محدودیت مدیران خاموش شد.")
            return True
        mark_db_dirty(); save_db(force=True)
        await render_feature_locks_panel(query, context, cid, db)
        await query.answer("محدودیت مدیران فعال شد.")
        return True

    if key not in FEATURE_LOCK_KEYS:
        await query.answer("گزینه نامعتبر است.", show_alert=True)
        return True

    # Per-command switches only matter while the master switch is enabled.
    if not locks.get("manager_limit", False):
        await query.answer("ابتدا محدودیت مدیران را فعال کنید.", show_alert=True)
        return True

    locks[key] = not bool(locks.get(key, False))
    mark_db_dirty(); save_db(force=True)
    label = FEATURE_LOCK_LABELS[key]
    state = "بسته شد" if locks[key] else "باز شد"
    await render_feature_locks_panel(query, context, cid, db)
    await query.answer(f"دسترسی {label} برای مدیران {state}.")
    return True
