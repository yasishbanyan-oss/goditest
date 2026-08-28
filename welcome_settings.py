# GoodiBot - advanced welcome-management panel
from core import *

WELCOME_PANEL_EMOJIS = {
    "header": "5397782960512444700",
    "enable": "5819032824623144971",
    "status": "5830144944399981619",
    "set": "5819032824623144971",
    "audience": "5819051035284479206",
    "preview": "5830381159011326872",
    "auto": "6008125631777218410",
    "back": "5823664135103061930",
    "check": "5830144944399981619",
    "up": "5368509223632118184",
    "down": "5368445885749404444",
    "setup": "6294135870614147548",
    "formats": "6294322839130477429",
}


def _welcome_settings(g_data: dict) -> dict:
    w = g_data.setdefault("welcome", {})
    w.setdefault("enabled", False)
    w.setdefault("custom", bool(w.get("payload")))
    w.setdefault("payload", None)
    w.setdefault("audience", "all")
    auto = w.setdefault("auto_delete", {})
    auto.setdefault("enabled", False)
    auto.setdefault("seconds", 90)
    try:
        auto["seconds"] = max(10, min(86400, int(auto.get("seconds", 90))))
    except Exception:
        auto["seconds"] = 90
    return w


def _fa_digits(value: int) -> str:
    return str(int(value)).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))


def _duration_text(seconds: int) -> str:
    seconds = max(0, int(seconds))
    minutes, sec = divmod(seconds, 60)
    if minutes and sec:
        return f"{_fa_digits(minutes)} دقیقه و {_fa_digits(sec)} ثانیه"
    if minutes:
        return f"{_fa_digits(minutes)} دقیقه"
    return f"{_fa_digits(sec)} ثانیه"


def _media_label(payload: dict | None) -> str | None:
    if not payload:
        return None
    labels = {
        "animation": "گیف",
        "sticker": "استیکر",
        "photo": "عکس",
        "video": "ویدیو",
        "video_note": "ویدیو سلفی",
        "audio": "آهنگ",
        "voice": "ویس",
        "document": "فایل",
        "contact": "مخاطب",
        "location": "موقعیت مکانی",
        "venue": "مکان",
    }
    return labels.get(payload.get("type"), "رسانه")


def _payload_display_text(payload: dict | None) -> str:
    if not payload:
        return "پیام پیش‌فرض سیستم"
    raw = payload.get("text") or payload.get("caption") or ""
    if raw:
        return raw
    return "پیام بدون متن"


def _welcome_current_text(w: dict) -> str:
    payload = w.get("payload") if w.get("custom") else None
    message_text = _payload_display_text(payload)
    media = _media_label(payload)
    if media:
        tail = f"پیام بالا همراه {media} ارسال خواهد شد."
    else:
        tail = "تنها پیام بالا ارسال خواهد شد."
    return (
        '<b><tg-emoji emoji-id="5830245188936670873">🌟</tg-emoji> خوش‌آمدگویی فعلی :</b>\n\n'
        f'<b>{message_text}</b>\n\n'
        f'<b>{tail}</b>'
    )


def _welcome_panel_keyboard(chat_id: int, w: dict) -> InlineKeyboardMarkup:
    audience = "همه اعضا" if w.get("audience", "all") == "all" else "عضویت با لینک"
    auto = bool((w.get("auto_delete") or {}).get("enabled", False))
    auto_text = "حذف خودکار پیام خوش‌آمدگویی: فعال" if auto else "حذف خودکار پیام خوش‌آمدگویی: خاموش"
    auto_style = "success" if auto else None
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("خوش‌آمدگویی", callback_data=f"welcome_toggle:{chat_id}", style="success" if w.get("enabled") else None, icon_custom_emoji_id=WELCOME_PANEL_EMOJIS["status"])],
        [InlineKeyboardButton("تنظیم پیام خوش‌آمدگویی", callback_data=f"welcome_set:{chat_id}", icon_custom_emoji_id=WELCOME_PANEL_EMOJIS["set"])],
        [InlineKeyboardButton(f"خوش‌آمدگویی به : {audience}", callback_data=f"welcome_audience:{chat_id}", icon_custom_emoji_id=WELCOME_PANEL_EMOJIS["audience"])],
        [InlineKeyboardButton("مشاهده پیام خوش‌آمدگویی", callback_data=f"welcome_preview:{chat_id}", icon_custom_emoji_id=WELCOME_PANEL_EMOJIS["preview"])],
        [InlineKeyboardButton(auto_text, callback_data=f"welcome_auto:{chat_id}", style=auto_style, icon_custom_emoji_id=WELCOME_PANEL_EMOJIS["auto"])],
        [InlineKeyboardButton("بازگشت", callback_data=f"panel_group_advanced:{chat_id}", style="danger", icon_custom_emoji_id=WELCOME_PANEL_EMOJIS["back"])],
    ])


def _welcome_auto_keyboard(chat_id: int, w: dict) -> InlineKeyboardMarkup:
    seconds = int((w.get("auto_delete") or {}).get("seconds", 90))
    # Keep the four time controls as four distinct premium-emoji buttons.
    # The outer pair changes the timeout by one minute; the inner pair changes
    # it by ten seconds.  Two rows also make the four controls unambiguous on
    # narrow Telegram clients.
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("حذف خودکار پیام خوش‌آمدگویی : فعال", callback_data=f"welcome_auto:{chat_id}", style="success", icon_custom_emoji_id=WELCOME_PANEL_EMOJIS["auto"])],
        [InlineKeyboardButton(_duration_text(seconds), callback_data=f"welcome_auto_noop:{chat_id}", icon_custom_emoji_id=WELCOME_PANEL_EMOJIS["auto"])],
        [
            InlineKeyboardButton("⏪⏪", callback_data=f"welcome_time:{chat_id}:-60", icon_custom_emoji_id=WELCOME_PANEL_EMOJIS["down"]),
            InlineKeyboardButton("⏩⏩", callback_data=f"welcome_time:{chat_id}:60", icon_custom_emoji_id=WELCOME_PANEL_EMOJIS["up"]),
        ],
        [
            InlineKeyboardButton("⏪", callback_data=f"welcome_time:{chat_id}:-10", icon_custom_emoji_id=WELCOME_PANEL_EMOJIS["down"]),
            InlineKeyboardButton("⏩", callback_data=f"welcome_time:{chat_id}:10", icon_custom_emoji_id=WELCOME_PANEL_EMOJIS["up"]),
        ],
        [InlineKeyboardButton("بازگشت", callback_data=f"welcome_auto_back:{chat_id}", style="danger", icon_custom_emoji_id=WELCOME_PANEL_EMOJIS["back"])],
    ])


def _welcome_setup_prompt() -> str:
    return (
        '<b><tg-emoji emoji-id="6294135870614147548">📱</tg-emoji> پیام خود را جهت تنظیم خوش‌آمد‌گویی ارسال بفرمایید.</b>\n\n'
        '<b><tg-emoji emoji-id="6294322839130477429">👍</tg-emoji>برخی فرمت‌ها:</b>\n\n'
        '<b>- TIME -> زمان\n- USERNAME -> نام شخص\n- XXXX -> نام گروه\n- DAY -> روز</b>'
    )


def _welcome_disabled_text() -> str:
    return (
        '<b><tg-emoji emoji-id="5397782960512444700">📌</tg-emoji> به بخش خوش‌آمدگویی خوش آمدید.</b>\n\n'
        '<b>ابتدا خوش‌آمدگویی را فعال کنید.</b>'
    )


def _welcome_disabled_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("روشن کردن خوش‌آمدگویی", callback_data=f"welcome_toggle:{chat_id}", style="success", icon_custom_emoji_id=WELCOME_PANEL_EMOJIS["enable"])],
        [InlineKeyboardButton("بازگشت", callback_data=f"panel_group_advanced:{chat_id}", style="danger", icon_custom_emoji_id=WELCOME_PANEL_EMOJIS["back"])],
    ])


async def render_welcome_panel_message(query, chat_id: int, db: dict):
    g_data = get_group_data(db, chat_id)
    w = _welcome_settings(g_data)
    if not w.get("enabled", False):
        await query.message.edit_text(_welcome_disabled_text(), reply_markup=_welcome_disabled_keyboard(chat_id), parse_mode=ParseMode.HTML)
    else:
        await query.message.edit_text(_welcome_current_text(w), reply_markup=_welcome_panel_keyboard(chat_id, w), parse_mode=ParseMode.HTML)


async def _schedule_welcome_auto_delete(context, chat_id: int, message_id: int, seconds: int):
    queue = context.job_queue
    if not queue:
        return
    name = f"welcome_auto_delete:{int(chat_id)}:{int(message_id)}"
    for job in queue.get_jobs_by_name(name):
        job.schedule_removal()
    queue.run_once(
        welcome_auto_delete_job,
        when=max(1, int(seconds)),
        chat_id=int(chat_id),
        name=name,
        data={"chat_id": int(chat_id), "message_id": int(message_id)},
    )


async def welcome_auto_delete_job(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data or {}
    try:
        await context.bot.delete_message(chat_id=int(data["chat_id"]), message_id=int(data["message_id"]))
    except Exception:
        pass


async def handle_welcome_settings_callback(query, context, db, data: str) -> bool:
    user_id = query.from_user.id

    if data.startswith("advanced_welcome:"):
        cid = int(data.split(":", 1)[1])
        if not await is_configured_group_manager(context, cid, user_id):
            await query.answer("این پنل برای شما نیست.", show_alert=True)
            return True
        await render_welcome_panel_message(query, cid, db)
        return True

    if data.startswith("welcome_toggle:"):
        cid = int(data.split(":", 1)[1])
        if not await is_configured_group_manager(context, cid, user_id):
            await query.answer("این پنل برای شما نیست.", show_alert=True)
            return True
        g = get_group_data(db, cid)
        w = _welcome_settings(g)
        w["enabled"] = not bool(w.get("enabled", False))
        mark_db_dirty(); save_db(force=True)
        await render_welcome_panel_message(query, cid, db)
        await query.answer()
        return True

    if data.startswith("welcome_set:"):
        cid = int(data.split(":", 1)[1])
        if not await is_configured_group_manager(context, cid, user_id):
            await query.answer("این پنل برای شما نیست.", show_alert=True)
            return True
        db.setdefault("states", {}).setdefault("waiting_welcome_msg", {})[str(user_id)] = {
            "chat_id": int(cid),
            "panel_message_id": int(query.message.message_id),
        }
        touch_state(db, "waiting_welcome_msg", str(user_id))
        mark_db_dirty(); save_db(force=True)
        await query.message.edit_text(
            _welcome_setup_prompt(),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("بازگشت", callback_data=f"welcome_setup_back:{cid}", style="danger", icon_custom_emoji_id=WELCOME_PANEL_EMOJIS["back"])]]),
            parse_mode=ParseMode.HTML,
        )
        await query.answer()
        return True

    if data.startswith("welcome_setup_back:"):
        cid = int(data.split(":", 1)[1])
        if not await is_configured_group_manager(context, cid, user_id):
            await query.answer("این پنل برای شما نیست.", show_alert=True)
            return True
        db.setdefault("states", {}).setdefault("waiting_welcome_msg", {}).pop(str(user_id), None)
        mark_db_dirty(); save_db(force=True)
        await render_welcome_panel_message(query, cid, db)
        await query.answer()
        return True

    if data.startswith("welcome_audience:"):
        cid = int(data.split(":", 1)[1])
        if not await is_configured_group_manager(context, cid, user_id):
            await query.answer("این پنل برای شما نیست.", show_alert=True)
            return True
        g = get_group_data(db, cid)
        w = _welcome_settings(g)
        w["audience"] = "link" if w.get("audience", "all") == "all" else "all"
        mark_db_dirty(); save_db(force=True)
        await render_welcome_panel_message(query, cid, db)
        await query.answer()
        return True

    if data.startswith("welcome_preview:"):
        cid = int(data.split(":", 1)[1])
        if not await is_configured_group_manager(context, cid, user_id):
            await query.answer("این پنل برای شما نیست.", show_alert=True)
            return True
        g = get_group_data(db, cid)
        w = _welcome_settings(g)
        try:
            await query.message.edit_text(
                '<b><tg-emoji emoji-id="5830144944399981619">✅</tg-emoji> انجام شد.</b>',
                reply_markup=None,
                parse_mode=ParseMode.HTML,
            )
            await send_welcome_to_member(context, query.message.chat, query.from_user, reply_to_message_id=None, check_duplicate=False)
        except Exception:
            logger.exception("Welcome preview failed | chat_id=%s", cid)
            await query.answer("نمایش پیام خوش‌آمد ناموفق بود.", show_alert=True)
            return True
        await query.answer()
        return True

    if data.startswith("welcome_auto:"):
        cid = int(data.split(":", 1)[1])
        if not await is_configured_group_manager(context, cid, user_id):
            await query.answer("این پنل برای شما نیست.", show_alert=True)
            return True
        g = get_group_data(db, cid)
        w = _welcome_settings(g)
        auto = w["auto_delete"]
        auto["enabled"] = not bool(auto.get("enabled", False))
        mark_db_dirty(); save_db(force=True)
        if auto["enabled"]:
            await query.message.edit_text(
                '<b><tg-emoji emoji-id="6008125631777218410">⚠️</tg-emoji> حذف خودکار پیام خوش‌آمد : فعال</b>\n'
                f'<b>{_duration_text(auto["seconds"])}</b>',
                reply_markup=_welcome_auto_keyboard(cid, w),
                parse_mode=ParseMode.HTML,
            )
        else:
            await render_welcome_panel_message(query, cid, db)
        await query.answer()
        return True

    if data.startswith("welcome_auto_noop:"):
        await query.answer()
        return True

    if data.startswith("welcome_auto_back:"):
        cid = int(data.split(":", 1)[1])
        if not await is_configured_group_manager(context, cid, user_id):
            await query.answer("این پنل برای شما نیست.", show_alert=True)
            return True
        await render_welcome_panel_message(query, cid, db)
        await query.answer()
        return True

    if data.startswith("welcome_time:"):
        _, cid_s, delta_s = data.split(":", 2)
        cid, delta = int(cid_s), int(delta_s)
        if not await is_configured_group_manager(context, cid, user_id):
            await query.answer("این پنل برای شما نیست.", show_alert=True)
            return True
        g = get_group_data(db, cid)
        w = _welcome_settings(g)
        auto = w["auto_delete"]
        auto["seconds"] = max(10, min(86400, int(auto.get("seconds", 90)) + delta))
        mark_db_dirty(); save_db(force=True)
        await query.message.edit_text(
            '<b><tg-emoji emoji-id="6008125631777218410">⚠️</tg-emoji> حذف خودکار پیام خوش‌آمد : فعال</b>\n'
            f'<b>{_duration_text(auto["seconds"])}</b>',
            reply_markup=_welcome_auto_keyboard(cid, w),
            parse_mode=ParseMode.HTML,
        )
        await query.answer()
        return True

    return False
