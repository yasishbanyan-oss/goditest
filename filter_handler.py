# GoodiBot filter-words feature module
from core import *

FILTER_ADD_EMOJI = "5819032824623144971"
FILTER_BACK_EMOJI = BACK_CUSTOM_EMOJI_ID
FILTER_BUCKET_EMOJI = "5312123724739129803"
FILTER_WARN_EMOJI = "5818716826699307883"
FILTER_KICK_EMOJI = "5872823922751185495"
FILTER_MUTE_EMOJI = "5872883940624179027"
FILTER_TEMP_EMOJI = "5872792857252733333"
FILTER_ALERT_EMOJI = "5819051035284479206"
FILTER_DIAMOND_EMOJI = "5929272673627546181"

FILTER_ACTIONS = {
    "delete": "حذف پیام کاربر",
    "warn": "حذف پیام و اخطار به کاربر",
    "kick": "حذف پیام و اخراج کاربر",
    "mute": "حذف پیام و سکوت کاربر",
    "temp_mute": "حذف پیام و سکوت موقت کاربر",
}

FILTER_ACTION_TEXT = {
    "delete": "حذف پیام",
    "warn": "اخطار به کاربر",
    "kick": "اخراج کاربر",
    "mute": "سکوت کاربر",
    "temp_mute": "سکوت موقت کاربر",
}

def _filter_words(g):
    words = g.setdefault("filter_words", [])
    if not isinstance(words, list):
        g["filter_words"] = []
        words = g["filter_words"]
    return words

def _norm_filter_word(value):
    value = normalize_text(str(value or "")).strip().lower()
    value = re.sub(r"\s+", " ", value)
    return value

def _fa_num(n):
    return str(n).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))

def _duration_label(minutes):
    minutes = int(minutes)
    if minutes % 60 == 0:
        h = minutes // 60
        if h == 1:
            return "۱ ساعت"
        return f"{_fa_num(h)} ساعت"
    return f"{_fa_num(minutes)} دقیقه"

def _action_label(item):
    action = item.get("punishment", "delete")
    if action == "temp_mute":
        return f"سکوت {_duration_label(item.get('duration_minutes', 30))}"
    return FILTER_ACTION_TEXT.get(action, "حذف پیام")

def _filter_item(word, punishment="delete", duration_minutes=30):
    return {
        "word": str(word),
        "normalized": _norm_filter_word(word),
        "punishment": punishment,
        "duration_minutes": int(duration_minutes),
    }

def _find_filter(g, word):
    target = _norm_filter_word(word)
    if not target:
        return None
    for item in _filter_words(g):
        if _norm_filter_word(item.get("normalized") or item.get("word")) == target:
            return item
    return None

async def _filter_panel_allowed(context, chat_id, user_id):
    return await is_configured_group_manager(context, chat_id, user_id)

def _session_key(user_id):
    return str(user_id)

def _get_filter_panel_session(db, user_id):
    return (db.setdefault("states", {}).setdefault("filter_panel", {}) or {}).get(_session_key(user_id))

def _set_filter_panel_session(db, user_id, chat_id, message_id):
    db.setdefault("states", {}).setdefault("filter_panel", {})[_session_key(user_id)] = {
        "chat_id": int(chat_id),
        "message_id": int(message_id),
    }
    mark_db_dirty()

def _clear_filter_panel_session(db, user_id):
    db.setdefault("states", {}).setdefault("filter_panel", {}).pop(_session_key(user_id), None)
    mark_db_dirty()

async def _owns_filter_panel(query, context, db, chat_id):
    user_id = query.from_user.id
    if not await _filter_panel_allowed(context, chat_id, user_id):
        await query.answer("این پنل برای شما نیست.", show_alert=True)
        return False
    session = _get_filter_panel_session(db, user_id)
    if not session or int(session.get("chat_id", 0)) != int(chat_id) or int(session.get("message_id", 0)) != int(query.message.message_id):
        await query.answer("این پنل برای شما نیست.", show_alert=True)
        return False
    return True

def _filter_panel_buttons_empty(chat_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "➕ افزودن کلمه به لیست فیلتر",
            callback_data=f"filter_add_menu:{chat_id}",
            style="primary",
            icon_custom_emoji_id=FILTER_ADD_EMOJI
        )],
        [InlineKeyboardButton(
            "⬅️ بازگشت",
            callback_data=f"filter_back_lists:{chat_id}",
            style="danger",
            icon_custom_emoji_id=FILTER_BACK_EMOJI
        )]
    ])

def _filter_panel_buttons_full(chat_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(
            "🎉 پاکسازی لیست فیلتر",
            callback_data=f"filter_cleanup_confirm:{chat_id}",
            style="primary",
            icon_custom_emoji_id=CLEANUP_CUSTOM_EMOJI_ID
        )],
        [InlineKeyboardButton(
            "❌ حذف کلمه از لیست",
            callback_data=f"filter_delete_prompt:{chat_id}",
            style="danger",
            icon_custom_emoji_id=FILTER_KICK_EMOJI
        )],
        [InlineKeyboardButton(
            "➕ افزودن به لیست فیلتر",
            callback_data=f"filter_add_menu:{chat_id}",
            style="primary",
            icon_custom_emoji_id=FILTER_ADD_EMOJI
        )],
        [InlineKeyboardButton(
            "⬅️ بازگشت",
            callback_data=f"filter_back_lists:{chat_id}",
            style="danger",
            icon_custom_emoji_id=FILTER_BACK_EMOJI
        )]
    ])

def build_filter_panel_content(g):
    words = _filter_words(g)
    if not words:
        return (
            f'<b><tg-emoji emoji-id="{FILTER_ALERT_EMOJI}">⚠️</tg-emoji> لیست عبارات فیلتر شده خالی است.</b>',
            None
        )

    lines = [
        f'<b><tg-emoji emoji-id="{FILTER_ALERT_EMOJI}">🚨</tg-emoji> لیست کلمات فیلتر به شرح ذیل می‌باشد:</b>',
        ""
    ]
    for idx, item in enumerate(words):
        word = html.escape(str(item.get("word", "")))
        action = html.escape(_action_label(item))
        arrow = "⬅️" if idx % 2 == 0 else "➡️"
        lines.append(f'<b><tg-spoiler>{word}</tg-spoiler> {arrow} {action}</b>')
    lines.extend(["", "<b>نوع عملیات را انتخاب کنید.</b>"])
    return "\n".join(lines), None

async def render_filter_panel(query, context, chat_id, db, set_owner=True):
    g = get_group_data(db, chat_id)
    text, _ = build_filter_panel_content(g)
    kb = _filter_panel_buttons_full(chat_id) if _filter_words(g) else _filter_panel_buttons_empty(chat_id)
    await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    if set_owner:
        _set_filter_panel_session(db, query.from_user.id, chat_id, query.message.message_id)
        save_db(force=True)

async def _render_filter_lists(query, context, chat_id, db):
    if not await _filter_panel_allowed(context, chat_id, query.from_user.id):
        await query.answer("دسترسی غیرمجاز!", show_alert=True)
        return
    g = get_group_data(db, chat_id)
    text = await build_group_lists_status(context, chat_id, db, g)
    buttons = [
        [
            InlineKeyboardButton("مالکین", callback_data=f"list_owners:{chat_id}", style="primary", icon_custom_emoji_id="6060078591276749279"),
            InlineKeyboardButton("مدیران", callback_data=f"list_admins:{chat_id}", style="primary", icon_custom_emoji_id="6057831537401925660")
        ],
        [
            InlineKeyboardButton("اعضای ویژه", callback_data=f"list_special:{chat_id}", style="primary", icon_custom_emoji_id="6294080753298837622"),
            InlineKeyboardButton("کلمات فیلتر", callback_data=f"list_filters:{chat_id}", style="primary", icon_custom_emoji_id="6086622219310470226")
        ],
        [
            InlineKeyboardButton("سکوت‌ شده‌ها", callback_data=f"list_muted:{chat_id}", style="primary", icon_custom_emoji_id="5886328760218688328"),
            InlineKeyboardButton("بن‌شده‌ها", callback_data=f"list_banned:{chat_id}", style="primary", icon_custom_emoji_id="5872823922751185495")
        ],
        [
            InlineKeyboardButton("لیست معاف", callback_data=f"list_exempt:{chat_id}", style="primary", icon_custom_emoji_id="5884078304729767721"),
            InlineKeyboardButton("لیست اخطار", callback_data=f"list_warns:{chat_id}", style="primary", icon_custom_emoji_id="5911318301580991657")
        ],
        [
            InlineKeyboardButton("پاسخ‌دهی خودکار", callback_data=f"list_auto_resp:{chat_id}", style="primary", icon_custom_emoji_id="5859316800361077930"),
            InlineKeyboardButton("کامنت‌گذاری", callback_data=f"list_comments:{chat_id}", style="primary", icon_custom_emoji_id="5908745251098473369")
        ],
        [InlineKeyboardButton("بررسی کاربر", callback_data=f"list_check_user:{chat_id}", style="primary", icon_custom_emoji_id="5884362854903064294")],
        [InlineKeyboardButton("بازگشت", callback_data=f"panel_group_main:{chat_id}", style="danger", icon_custom_emoji_id=CLOSE_CUSTOM_EMOJI_ID)]
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
    _clear_filter_panel_session(db, query.from_user.id)
    save_db(force=True)

def _filter_add_keyboard(chat_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🪣 حذف پیام کاربر", callback_data=f"filter_choose:delete:{chat_id}", style=None, icon_custom_emoji_id=FILTER_BUCKET_EMOJI)],
        [InlineKeyboardButton("❗️ حذف پیام و اخطار به کاربر", callback_data=f"filter_choose:warn:{chat_id}", style=None, icon_custom_emoji_id=FILTER_WARN_EMOJI)],
        [InlineKeyboardButton("❌ حذف پیام و اخراج کاربر", callback_data=f"filter_choose:kick:{chat_id}", style=None, icon_custom_emoji_id=FILTER_KICK_EMOJI)],
        [InlineKeyboardButton("🔇 حذف پیام و سکوت کاربر", callback_data=f"filter_choose:mute:{chat_id}", style=None, icon_custom_emoji_id=FILTER_MUTE_EMOJI)],
        [InlineKeyboardButton("🛡 حذف پیام و سکوت موقت کاربر", callback_data=f"filter_choose:temp_mute:{chat_id}", style=None, icon_custom_emoji_id=FILTER_TEMP_EMOJI)],
        [InlineKeyboardButton("⬅️ بازگشت", callback_data=f"filter_add_back:{chat_id}", style="danger", icon_custom_emoji_id=FILTER_BACK_EMOJI)]
    ])

async def _show_filter_add_menu(query, context, chat_id, db):
    await query.message.edit_text(
        "<b>لطفا نوع مجازات کلمه فیلتر را انتخاب کنید.</b>",
        reply_markup=_filter_add_keyboard(chat_id),
        parse_mode=ParseMode.HTML
    )

def _filter_duration_keyboard(chat_id, minutes):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("−", callback_data=f"filter_temp_dec:{chat_id}", style="danger", icon_custom_emoji_id=FILTER_WARN_EMOJI),
            InlineKeyboardButton(_duration_label(minutes), callback_data=f"filter_temp_noop:{chat_id}", style="primary"),
            InlineKeyboardButton("+", callback_data=f"filter_temp_inc:{chat_id}", style="success", icon_custom_emoji_id=FILTER_ADD_EMOJI)
        ],
        [InlineKeyboardButton("ثبت و ادامه", callback_data=f"filter_temp_confirm:{chat_id}", style="success", icon_custom_emoji_id=CHECK_CUSTOM_EMOJI_ID)],
        [InlineKeyboardButton("⬅️ بازگشت", callback_data=f"filter_add_back:{chat_id}", style="danger", icon_custom_emoji_id=FILTER_BACK_EMOJI)]
    ])

def _filter_prompt_text(action, minutes=30):
    action_phrase = FILTER_ACTIONS[action]
    if action == "temp_mute":
        action_phrase = f"حذف پیام و سکوت موقت کاربر به مدت {_duration_label(minutes)}"
    return (
        f'<b><tg-emoji emoji-id="{FILTER_ALERT_EMOJI}">🚨</tg-emoji> جهت فیلتر کردن کلمات با مجازات {html.escape(action_phrase)} '
        f'لطفا کلمات را یکی یکی و پشت هم ارسال کنید.</b>\n\n'
        f'<b><tg-emoji emoji-id="{FILTER_DIAMOND_EMOJI}">⚡️</tg-emoji> در نهایت با دستور /done عملیات را به پایان برسانید.</b>'
    )

def _filter_result_text(word, action):
    if action == "delete":
        phrase = "پیام کاربر متخلف حذف می‌شود!"
    elif action == "warn":
        phrase = "کاربر متخلف اخطار می‌گیرد."
    elif action == "kick":
        phrase = "کاربر متخلف بن می‌شود."
    elif action == "mute":
        phrase = "کاربر متخلف سکوت می‌شود."
    else:
        phrase = "کاربر متخلف سکوت موقت می‌شود."
    return (
        f'<b><tg-emoji emoji-id="{FILTER_WARN_EMOJI}">❗️</tg-emoji> کلمه [ <tg-spoiler>{html.escape(word)}</tg-spoiler> ] فیلتر شد.</b>\n\n'
        f'<b><tg-emoji emoji-id="{FILTER_ALERT_EMOJI}">🚨</tg-emoji> {phrase}</b>\n\n'
        f'<b><tg-emoji emoji-id="{FILTER_DIAMOND_EMOJI}">✨</tg-emoji> در صورت ادامه کلمه بعدی را ارسال کنید در غیر اینصورت با دستور /done عملیات را به پایان برسانید.</b>'
    )

def _filter_error_for_action(action):
    if action in ("kick",):
        label = "اخراج"
    elif action in ("mute", "temp_mute"):
        label = "سکوت"
    else:
        label = "حذف پیام"
    return (
        f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> ربات به {label} دسترسی ندارد.</b>\n'
        f'<b>لطفا دسترسی هارا به ربات بدهید.</b>'
    )

async def _bot_can_do_filter_action(context, chat_id, action):
    try:
        member = await cached_chat_member(context, chat_id, context.bot.id)
        if member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
            return False
        if action in ("delete", "warn", "kick", "mute", "temp_mute"):
            if not bool(getattr(member, "can_delete_messages", False)) and member.status != ChatMemberStatus.OWNER:
                return False
        if action in ("kick", "mute", "temp_mute"):
            if member.status != ChatMemberStatus.OWNER and not bool(getattr(member, "can_restrict_members", False)):
                return False
        return True
    except Exception:
        return False

async def _bot_can_delete(context, chat_id):
    try:
        member = await cached_chat_member(context, chat_id, context.bot.id)
        return member.status == ChatMemberStatus.OWNER or (
            member.status == ChatMemberStatus.ADMINISTRATOR and bool(getattr(member, "can_delete_messages", False))
        )
    except Exception:
        return False

async def _execute_filter_action(update, context, db, g, item, user):
    chat_id = update.effective_chat.id
    uid = user.id
    name = user.full_name or "کاربر"
    action = item.get("punishment", "delete")
    duration_minutes = int(item.get("duration_minutes", 30) or 30)

    if not await _bot_can_delete(context, chat_id):
        await update.message.reply_text(
            f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> ربات به حذف پیام دسترسی ندارد.</b>\n<b>لطفا دسترسی هارا به ربات بدهید.</b>',
            parse_mode=ParseMode.HTML
        )
        return

    try:
        await update.message.delete()
    except Exception:
        await update.message.reply_text(
            f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> ربات به حذف پیام دسترسی ندارد.</b>\n<b>لطفا دسترسی هارا به ربات بدهید.</b>',
            parse_mode=ParseMode.HTML
        )
        return

    mention_name = html.escape(name)
    base = (
        f'<b><tg-emoji emoji-id="{FILTER_ALERT_EMOJI}">⚠️</tg-emoji> کاربر {mention_name} عزیز!</b>\n\n'
        f'<b>پیام ارسالی شما در لیست فیلتر ربات قرار داشت و حذف گردید.</b>'
    )

    if action == "delete":
        await context.bot.send_message(chat_id=chat_id, text=base, parse_mode=ParseMode.HTML)
        return

    if action == "warn":
        settings = g.setdefault("warning_settings", {"count": 3, "punishment": None, "temp_mute_hours": 1})
        warning_punishment = settings.get("punishment")
        if not warning_punishment:
            await context.bot.send_message(
                chat_id=chat_id,
                text=base + "\n<b>- به دلیل مشخص نبودن مجازات و اخطار از سوی مالک گروه ، اخطاری داده نشد.</b>",
                parse_mode=ParseMode.HTML
            )
            return

        warnings = g.setdefault("warnings", {})
        item_warn = warnings.setdefault(str(uid), {"count": 0, "username": user.username or "", "fullname": name})
        limit = max(1, min(20, int(settings.get("count", 3))))
        item_warn["count"] = min(limit, int(item_warn.get("count", 0)) + 1)
        item_warn["username"] = user.username or ""
        item_warn["fullname"] = name
        count = int(item_warn["count"])

        if count < limit:
            mark_db_dirty()
            save_db(force=True)
            await context.bot.send_message(
                chat_id=chat_id,
                text=base + f"\n<b>- کاربر {mention_name} [ {count}/{limit} ] اخطار دریافت کرد.</b>",
                parse_mode=ParseMode.HTML
            )
            return

        # Reached the warning limit: execute the warning system's configured punishment.
        if warning_punishment in ("kick", "mute", "temp_mute") and not await _bot_can_do_filter_action(context, chat_id, warning_punishment):
            mark_db_dirty()
            save_db(force=True)
            await context.bot.send_message(
                chat_id=chat_id,
                text=base + f"\n<b>- اخطار [ {count}/{limit} ] ثبت شد اما ربات دسترسی اجرای مجازات نهایی را ندارد.</b>\n"
                            f"<b>لطفا دسترسی هارا به ربات بدهید.</b>",
                parse_mode=ParseMode.HTML
            )
            return

        try:
            if warning_punishment == "kick":
                await context.bot.ban_chat_member(chat_id, uid)
                g.setdefault("banned_users", {})[str(uid)] = {
                    "username": user.username or "", "fullname": name, "until": None, "created_at": datetime.now().timestamp()
                }
                final_phrase = "بخاطر تکمیل اخطارها از گروه اخراج میشوید."
            elif warning_punishment == "mute":
                await context.bot.restrict_chat_member(chat_id, uid, permissions=full_mute_permissions())
                g.setdefault("muted_users", {})[str(uid)] = {
                    "username": user.username or "", "fullname": name, "until": None, "created_at": datetime.now().timestamp()
                }
                final_phrase = "بخاطر تکمیل اخطارها سکوت میشوید."
            else:
                hours = max(1, int(settings.get("temp_mute_hours", 1)))
                until_dt = datetime.now() + timedelta(hours=hours)
                until_ts = datetime.now().timestamp() + hours * 3600
                await context.bot.restrict_chat_member(
                    chat_id, uid, permissions=full_mute_permissions(), until_date=until_dt
                )
                g.setdefault("muted_users", {})[str(uid)] = {
                    "username": user.username or "", "fullname": name, "until": until_ts, "created_at": datetime.now().timestamp()
                }
                final_phrase = f"بخاطر تکمیل اخطارها به مدت {hours} ساعت سکوت میشوید."
            warnings.pop(str(uid), None)
            mark_db_dirty()
            save_db(force=True)
            await context.bot.send_message(chat_id=chat_id, text=base + f"\n<b>- {final_phrase}</b>", parse_mode=ParseMode.HTML)
        except Exception:
            await context.bot.send_message(
                chat_id=chat_id,
                text=base + "\n<b>- ربات نتوانست مجازات نهایی اخطار را اجرا کند.</b>",
                parse_mode=ParseMode.HTML
            )
        return

    if action == "kick":
        if not await _bot_can_do_filter_action(context, chat_id, "kick"):
            await context.bot.send_message(chat_id=chat_id, text=_filter_error_for_action("kick"), parse_mode=ParseMode.HTML)
            return
        try:
            await context.bot.ban_chat_member(chat_id, uid)
            g.setdefault("banned_users", {})[str(uid)] = {
                "username": user.username or "", "fullname": name, "until": None, "created_at": datetime.now().timestamp()
            }
            mark_db_dirty()
            save_db(force=True)
            await context.bot.send_message(
                chat_id=chat_id,
                text=base + "\n<b>و بخاطر ارسال کلمه ممنوعه از گروه اخراج میشوید.</b>",
                parse_mode=ParseMode.HTML
            )
        except Exception:
            await context.bot.send_message(chat_id=chat_id, text=_filter_error_for_action("kick"), parse_mode=ParseMode.HTML)
        return

    if action in ("mute", "temp_mute"):
        if not await _bot_can_do_filter_action(context, chat_id, action):
            await context.bot.send_message(chat_id=chat_id, text=_filter_error_for_action(action), parse_mode=ParseMode.HTML)
            return
        try:
            if action == "mute":
                await context.bot.restrict_chat_member(chat_id, uid, permissions=full_mute_permissions())
                g.setdefault("muted_users", {})[str(uid)] = {
                    "username": user.username or "", "fullname": name, "until": None, "created_at": datetime.now().timestamp()
                }
                phrase = "و بخاطر ارسال کلمه ممنوعه سکوت میشوید."
            else:
                seconds = max(30, duration_minutes * 60)
                until_dt = moderation_until_datetime(seconds)
                if until_dt:
                    await context.bot.restrict_chat_member(chat_id, uid, permissions=full_mute_permissions(), until_date=until_dt)
                else:
                    await context.bot.restrict_chat_member(chat_id, uid, permissions=full_mute_permissions())
                g.setdefault("muted_users", {})[str(uid)] = {
                    "username": user.username or "", "fullname": name,
                    "until": datetime.now().timestamp() + seconds, "created_at": datetime.now().timestamp()
                }
                phrase = f"و بخاطر ارسال کلمه ممنوعه {_duration_label(duration_minutes)} سکوت میشوید."
            mark_db_dirty()
            save_db(force=True)
            await context.bot.send_message(chat_id=chat_id, text=base + f"\n<b>{phrase}</b>", parse_mode=ParseMode.HTML)
        except Exception:
            await context.bot.send_message(chat_id=chat_id, text=_filter_error_for_action(action), parse_mode=ParseMode.HTML)

async def handle_filter_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat:
        return
    if update.effective_chat.type not in ("group", "supergroup"):
        return
    if not update.effective_user or update.effective_user.is_bot:
        return

    db = load_db()
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    states = db.setdefault("states", {})

    # A pending delete flow belongs only to its creator.
    if await handle_filter_pending_text(update, context):
        raise ApplicationHandlerStop()

    # A filter-entry flow belongs only to its creator. Other users' messages are never consumed.
    flow = states.setdefault("filter_add", {}).get(str(user_id))
    if flow and int(flow.get("chat_id", 0)) == int(chat_id):
        raw = (update.message.text or "").strip()
        if not raw or raw.startswith("/"):
            return
        word = raw.strip()
        action = flow.get("punishment", "delete")
        duration = int(flow.get("duration_minutes", 30) or 30)
        g = get_group_data(db, chat_id)
        if _find_filter(g, word):
            msg = await update.message.reply_text(
                f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> کلمه موردنظر از قبل در لیست فیلتر بود.</b>',
                parse_mode=ParseMode.HTML
            )
            flow.setdefault("message_ids", []).extend([update.message.message_id, msg.message_id])
            mark_db_dirty()
            save_db(force=True)
            return

        g.setdefault("filter_words", []).append(_filter_item(word, action, duration))
        flow["words_added"] = int(flow.get("words_added", 0)) + 1
        mark_db_dirty()
        save_db(force=True)

        confirm = await update.message.reply_text(_filter_result_text(word, action), parse_mode=ParseMode.HTML)
        flow.setdefault("message_ids", []).extend([update.message.message_id, confirm.message_id])
        mark_db_dirty()
        save_db(force=True)
        return

    # Text commands are handled before the actual filter so management commands
    # are never mistaken for filtered content.
    await handle_filter_text_commands(update, context)

    # The filter itself is group-only and ignores privileged members.
    g = get_group_data(db, chat_id)
    words = _filter_words(g)
    if not words:
        return

    user = update.effective_user
    management = g.get("management", {}) or {}
    privileged = (
        user.id == int(OWNER_ID)
        or user.id in _role_ids(g, "owners")
        or user.id in _role_ids(g, "admins")
        or user.id in _role_ids(g, "special")
        or user.id in _role_ids(g, "exempt")
    )
    if privileged:
        return

    try:
        live = await cached_chat_member(context, chat_id, user.id)
        if live.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR):
            return
    except Exception:
        pass

    text = update.message.text or update.message.caption or ""
    normalized = _norm_filter_word(text)
    if not normalized:
        return

    matched = None
    for item in words:
        needle = _norm_filter_word(item.get("normalized") or item.get("word"))
        if needle and needle in normalized:
            matched = item
            break
    if not matched:
        return

    await _execute_filter_action(update, context, db, g, matched, user)
    raise ApplicationHandlerStop()

async def filter_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return False
    user_id = str(update.effective_user.id)
    db = load_db()
    flow = db.setdefault("states", {}).setdefault("filter_add", {}).get(user_id)
    if not flow:
        return False

    chat_id = int(flow.get("chat_id", update.effective_chat.id))
    panel_message_id = int(flow.get("panel_message_id", 0) or 0)
    message_ids = list(dict.fromkeys(int(x) for x in flow.get("message_ids", []) if str(x).isdigit()))
    words_added = int(flow.get("words_added", 0))

    for mid in message_ids:
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=mid)
        except Exception:
            pass

    db["states"]["filter_add"].pop(user_id, None)
    g = get_group_data(db, chat_id)
    text = (
        f'<b><tg-emoji emoji-id="{FILTER_DIAMOND_EMOJI}">💎</tg-emoji> پروسه فیلتر کردن با موفقیت به اتمام رسید.</b>\n\n'
        f'<b>تعداد {words_added} کلمه فیلتر شدند.</b>'
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("بازگشت", callback_data=f"filter_back_lists:{chat_id}", style="danger", icon_custom_emoji_id=FILTER_BACK_EMOJI)]
    ])
    try:
        if panel_message_id:
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=panel_message_id,
                text=text,
                reply_markup=kb,
                parse_mode=ParseMode.HTML
            )
        else:
            await update.message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
    except Exception:
        await update.message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)

    _set_filter_panel_session(db, update.effective_user.id, chat_id, panel_message_id or update.message.message_id)
    mark_db_dirty()
    save_db(force=True)
    return True

async def _filter_add_direct(update, context, db, chat_id, user_id, word):
    g = get_group_data(db, chat_id)
    if _find_filter(g, word):
        await update.message.reply_text(
            f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> کلمه موردنظر از قبل در لیست فیلتر بود.</b>',
            parse_mode=ParseMode.HTML
        )
        return
    if not await _bot_can_do_filter_action(context, chat_id, "delete"):
        await update.message.reply_text(_filter_error_for_action("delete"), parse_mode=ParseMode.HTML)
        return
    g.setdefault("filter_words", []).append(_filter_item(word, "delete", 30))
    mark_db_dirty()
    save_db(force=True)
    await update.message.reply_text(
        f'<b><tg-emoji emoji-id="{CHECK_CUSTOM_EMOJI_ID}">✅</tg-emoji> کلمه موردنظر با موفقیت به لیست فیلتر اضافه شد.</b>',
        parse_mode=ParseMode.HTML
    )

async def handle_filter_text_commands(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat or update.effective_chat.type not in ("group", "supergroup"):
        return
    if not update.effective_user or update.effective_user.is_bot:
        return

    text = (update.message.text or "").strip()
    if not text:
        return
    cmd = normalize_text(text).lower()
    db = load_db()
    cid = update.effective_chat.id
    uid = update.effective_user.id

    # Do not consume /done; the existing CommandHandler handles it.
    if cmd.startswith("/"):
        return

    list_cmds = {"لیست فیلتر", "لیست کلمات فیلتر", "کلمات فیلتر", "گودی فیلتر"}
    cleanup_cmds = {"پاکسازی لیست فیلتر", "گودی لیست فیلتر خالی کن", "حذف لیست فیلتر"}

    if cmd in list_cmds or cmd in cleanup_cmds or cmd.startswith("حذف فیلتر ") or any(
        cmd.startswith(prefix + " ") for prefix in ("فیلتر", "فیلتر کردن", "ثبت فیلتر", "تنظیم فیلتر")
    ):
        if not await _filter_panel_allowed(context, cid, uid):
            await update.message.reply_text(
                f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> فقط مدیران گروه دسترسی به پنل فیلتر را دارند.</b>',
                parse_mode=ParseMode.HTML
            )
            raise ApplicationHandlerStop()

    if cmd in list_cmds:
        # Reuse the same panel renderer by sending a lightweight temporary message.
        g = get_group_data(db, cid)
        text_panel, _ = build_filter_panel_content(g)
        kb = _filter_panel_buttons_full(cid) if _filter_words(g) else _filter_panel_buttons_empty(cid)
        sent = await update.message.reply_text(text_panel, reply_markup=kb, parse_mode=ParseMode.HTML)
        _set_filter_panel_session(db, uid, cid, sent.message_id)
        save_db(force=True)
        raise ApplicationHandlerStop()

    if cmd in cleanup_cmds:
        g = get_group_data(db, cid)
        if not _filter_words(g):
            await update.message.reply_text(
                f'<b><tg-emoji emoji-id="{CHECK_CUSTOM_EMOJI_ID}">✔️</tg-emoji> لیست فیلتر از قبل خالی می‌باشد.</b>',
                parse_mode=ParseMode.HTML
            )
            raise ApplicationHandlerStop()
        states = db.setdefault("states", {})
        states.setdefault("filter_cleanup", {})[str(uid)] = {"chat_id": cid, "message_id": None}
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("بله", callback_data=f"filter_cleanup_cmd_do:{cid}", style="success", icon_custom_emoji_id=CHECK_CUSTOM_EMOJI_ID),
            InlineKeyboardButton("خیر", callback_data=f"filter_cleanup_cmd_close:{cid}", style="danger", icon_custom_emoji_id=CROSS_CUSTOM_EMOJI_ID)
        ]])
        sent = await update.message.reply_text(
            f'<b><tg-emoji emoji-id="{CHECK_CUSTOM_EMOJI_ID}">✔️</tg-emoji> آیا از پاکسازی کامل لیست فیلتر مطمئن هستید؟</b>',
            reply_markup=kb,
            parse_mode=ParseMode.HTML
        )
        states["filter_cleanup"][str(uid)]["message_id"] = sent.message_id
        mark_db_dirty()
        save_db(force=True)
        raise ApplicationHandlerStop()

    if cmd.startswith("حذف فیلتر "):
        word = cmd[len("حذف فیلتر "):].strip()
        g = get_group_data(db, cid)
        target = _find_filter(g, word)
        if not target:
            await update.message.reply_text(
                f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> کلمه موردنظر در لیست نبود.</b>',
                parse_mode=ParseMode.HTML
            )
            raise ApplicationHandlerStop()
        g["filter_words"] = [
            x for x in _filter_words(g)
            if _norm_filter_word(x.get("normalized") or x.get("word")) != _norm_filter_word(word)
        ]
        mark_db_dirty()
        save_db(force=True)
        await update.message.reply_text(
            f'<b><tg-emoji emoji-id="{CHECK_CUSTOM_EMOJI_ID}">✅</tg-emoji> کلمه موردنظر با موفقیت از لیست حذف شد.</b>',
            parse_mode=ParseMode.HTML
        )
        raise ApplicationHandlerStop()

    prefixes = ("فیلتر کردن", "ثبت فیلتر", "تنظیم فیلتر", "فیلتر")
    prefix = next((p for p in prefixes if cmd.startswith(p + " ")), None)
    if prefix:
        word = text[len(prefix):].strip()
        if not word:
            await update.message.reply_text(
                f'<b><tg-emoji emoji-id="{FILTER_ALERT_EMOJI}">❗️</tg-emoji> لطفا کلمه موردنظر را بعد از دستور وارد کنید.</b>',
                parse_mode=ParseMode.HTML
            )
            raise ApplicationHandlerStop()
        await _filter_add_direct(update, context, db, cid, uid, word)
        raise ApplicationHandlerStop()

async def handle_filter_callback(query, context, db):
    data = query.data or ""
    user_id = query.from_user.id

    if data.startswith("list_filters:"):
        cid = int(data.split(":", 1)[1])
        if not await _filter_panel_allowed(context, cid, user_id):
            await query.answer("این پنل برای شما نیست.", show_alert=True)
            return True
        g = get_group_data(db, cid)
        text, _ = build_filter_panel_content(g)
        kb = _filter_panel_buttons_full(cid) if _filter_words(g) else _filter_panel_buttons_empty(cid)
        await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)
        _set_filter_panel_session(db, user_id, cid, query.message.message_id)
        save_db(force=True)
        await query.answer()
        return True

    if not data.startswith("filter_"):
        return False

    parts = data.split(":")
    if len(parts) < 2:
        return True

    if parts[0] in ("filter_cleanup_cmd_do", "filter_cleanup_cmd_close"):
        cid = int(parts[1])
        state = db.setdefault("states", {}).setdefault("filter_cleanup", {}).get(str(user_id))
        if not state or int(state.get("chat_id", 0)) != cid or not await _filter_panel_allowed(context, cid, user_id):
            await query.answer("این پنل برای شما نیست.", show_alert=True)
            return True
        if parts[0] == "filter_cleanup_cmd_close":
            db["states"]["filter_cleanup"].pop(str(user_id), None)
            mark_db_dirty()
            save_db(force=True)
            await query.message.edit_text(
                f'<b><tg-emoji emoji-id="{CHECK_CUSTOM_EMOJI_ID}">✔️</tg-emoji> پنل پاکسازی با موفقیت بسته شد.</b>',
                reply_markup=None,
                parse_mode=ParseMode.HTML
            )
            await query.answer()
            return True
        g = get_group_data(db, cid)
        if not _filter_words(g):
            db["states"]["filter_cleanup"].pop(str(user_id), None)
            mark_db_dirty()
            save_db(force=True)
            await query.message.edit_text(
                f'<b><tg-emoji emoji-id="{CHECK_CUSTOM_EMOJI_ID}">✔️</tg-emoji> لیست فیلتر از قبل خالی می‌باشد.</b>',
                reply_markup=None,
                parse_mode=ParseMode.HTML
            )
            await query.answer()
            return True
        g["filter_words"] = []
        db["states"]["filter_cleanup"].pop(str(user_id), None)
        mark_db_dirty()
        save_db(force=True)
        await query.message.edit_text(
            f'<b><tg-emoji emoji-id="{CHECK_CUSTOM_EMOJI_ID}">✔️</tg-emoji> پاکسازی لیست فیلتر با موفقیت انجام شد.</b>',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("بستن", callback_data=f"filter_cleanup_cmd_close:{cid}", style="danger", icon_custom_emoji_id=CROSS_CUSTOM_EMOJI_ID)]
            ]),
            parse_mode=ParseMode.HTML
        )
        await query.answer()
        return True

    cid = int(parts[-1]) if parts[-1].lstrip("-").isdigit() else None
    if cid is None:
        await query.answer("دکمه نامعتبر است.", show_alert=True)
        return True

    if not await _filter_panel_allowed(context, cid, user_id):
        await query.answer("این پنل برای شما نیست.", show_alert=True)
        return True

    if parts[0] == "filter_back_lists":
        session = _get_filter_panel_session(db, user_id)
        if not session or int(session.get("chat_id", 0)) != cid or int(session.get("message_id", 0)) != int(query.message.message_id):
            await query.answer("این پنل برای شما نیست.", show_alert=True)
            return True
        await _render_filter_lists(query, context, cid, db)
        await query.answer()
        return True

    if parts[0] in ("filter_add_menu", "filter_add_back"):
        if parts[0] == "filter_add_back":
            if not await _owns_filter_panel(query, context, db, cid):
                return True
            await render_filter_panel(query, context, cid, db)
            await query.answer()
            return True
        # From the main filter panel, establish ownership and show punishment choices.
        session = _get_filter_panel_session(db, user_id)
        if not session or int(session.get("chat_id", 0)) != cid or int(session.get("message_id", 0)) != int(query.message.message_id):
            await query.answer("این پنل برای شما نیست.", show_alert=True)
            return True
        await _show_filter_add_menu(query, context, cid, db)
        await query.answer()
        return True

    if parts[0] == "filter_choose":
        if not await _owns_filter_panel(query, context, db, cid):
            return True
        action = parts[1]
        if action not in FILTER_ACTIONS:
            await query.answer("نوع مجازات نامعتبر است.", show_alert=True)
            return True
        if not await _bot_can_do_filter_action(context, cid, action):
            await query.answer()
            await query.message.edit_text(
                _filter_error_for_action(action),
                reply_markup=_filter_add_keyboard(cid),
                parse_mode=ParseMode.HTML
            )
            return True
        states = db.setdefault("states", {})
        states.setdefault("filter_add", {})[str(user_id)] = {
            "chat_id": cid,
            "panel_message_id": query.message.message_id,
            "punishment": action,
            "duration_minutes": 30,
            "message_ids": [],
            "words_added": 0
        }
        if action == "temp_mute":
            await query.message.edit_text(
                "<b>مدت سکوت موقت را مشخص کنید:</b>",
                reply_markup=_filter_duration_keyboard(cid, 30),
                parse_mode=ParseMode.HTML
            )
        else:
            await query.message.edit_text(
                _filter_prompt_text(action),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ بازگشت", callback_data=f"filter_add_back:{cid}", style="danger", icon_custom_emoji_id=FILTER_BACK_EMOJI)]
                ]),
                parse_mode=ParseMode.HTML
            )
        mark_db_dirty()
        save_db(force=True)
        await query.answer()
        return True

    if parts[0].startswith("filter_temp_"):
        if not await _owns_filter_panel(query, context, db, cid):
            return True
        flow = db.setdefault("states", {}).setdefault("filter_add", {}).get(str(user_id))
        if not flow or flow.get("punishment") != "temp_mute":
            await query.answer("این پنل برای شما نیست.", show_alert=True)
            return True
        minutes = max(30, min(1440, int(flow.get("duration_minutes", 30))))
        if parts[0] == "filter_temp_inc":
            minutes = min(1440, minutes + 30)
        elif parts[0] == "filter_temp_dec":
            minutes = max(30, minutes - 30)
        elif parts[0] == "filter_temp_confirm":
            flow["duration_minutes"] = minutes
            await query.message.edit_text(
                _filter_prompt_text("temp_mute", minutes),
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⬅️ بازگشت", callback_data=f"filter_add_back:{cid}", style="danger", icon_custom_emoji_id=FILTER_BACK_EMOJI)]
                ]),
                parse_mode=ParseMode.HTML
            )
            mark_db_dirty()
            save_db(force=True)
            await query.answer()
            return True
        flow["duration_minutes"] = minutes
        await query.message.edit_reply_markup(_filter_duration_keyboard(cid, minutes))
        mark_db_dirty()
        save_db(force=True)
        await query.answer()
        return True

    if parts[0] == "filter_delete_prompt":
        if not await _owns_filter_panel(query, context, db, cid):
            return True
        states = db.setdefault("states", {})
        states.setdefault("filter_delete", {})[str(user_id)] = {
            "chat_id": cid,
            "panel_message_id": query.message.message_id
        }
        await query.message.edit_text(
            f'<b><tg-emoji emoji-id="{FILTER_WARN_EMOJI}">❗️</tg-emoji> لطفا کلمه‌ای را که میخواهید از لیست فیلتر حذف شود ارسال کنید.</b>',
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⬅️ بازگشت", callback_data=f"filter_delete_back:{cid}", style="danger", icon_custom_emoji_id=FILTER_BACK_EMOJI)]
            ]),
            parse_mode=ParseMode.HTML
        )
        mark_db_dirty()
        save_db(force=True)
        await query.answer()
        return True

    if parts[0] == "filter_delete_back":
        if not await _owns_filter_panel(query, context, db, cid):
            return True
        db.setdefault("states", {}).setdefault("filter_delete", {}).pop(str(user_id), None)
        await render_filter_panel(query, context, cid, db)
        await query.answer()
        return True

    if parts[0] == "filter_cleanup_confirm":
        if not await _owns_filter_panel(query, context, db, cid):
            return True
        await query.message.edit_text(
            "<b>آیا از پاکسازی کامل لیست فیلتر مطمئن هستید؟</b>",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("بله", callback_data=f"filter_cleanup_do:{cid}", style="success", icon_custom_emoji_id=CHECK_CUSTOM_EMOJI_ID),
                InlineKeyboardButton("بستن", callback_data=f"filter_cleanup_cancel:{cid}", style="danger", icon_custom_emoji_id=CROSS_CUSTOM_EMOJI_ID)
            ]]),
            parse_mode=ParseMode.HTML
        )
        await query.answer()
        return True

    if parts[0] == "filter_cleanup_cancel":
        if not await _owns_filter_panel(query, context, db, cid):
            return True
        await render_filter_panel(query, context, cid, db)
        await query.answer()
        return True

    if parts[0] == "filter_cleanup_do":
        if not await _owns_filter_panel(query, context, db, cid):
            return True
        g = get_group_data(db, cid)
        g["filter_words"] = []
        mark_db_dirty()
        save_db(force=True)
        await render_filter_panel(query, context, cid, db)
        await query.answer()
        return True

    return True

async def handle_filter_pending_text(update, context):
    if not update.message or not update.effective_chat or update.effective_chat.type not in ("group", "supergroup"):
        return False
    db = load_db()
    uid = str(update.effective_user.id)
    cid = update.effective_chat.id
    states = db.setdefault("states", {})

    delete_state = states.setdefault("filter_delete", {}).get(uid)
    if delete_state and int(delete_state.get("chat_id", 0)) == cid:
        text = (update.message.text or "").strip()
        if not text or text.startswith("/"):
            return False
        g = get_group_data(db, cid)
        target = _find_filter(g, text)
        states["filter_delete"].pop(uid, None)
        if target:
            g["filter_words"] = [
                x for x in _filter_words(g)
                if _norm_filter_word(x.get("normalized") or x.get("word")) != _norm_filter_word(text)
            ]
            msg_text = f'<b><tg-emoji emoji-id="{CHECK_CUSTOM_EMOJI_ID}">✅</tg-emoji> کلمه موردنظر با موفقیت از لیست حذف شد.</b>'
        else:
            msg_text = f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> کلمه موردنظر در لیست نبود.</b>'
        mark_db_dirty()
        save_db(force=True)
        panel_id = delete_state.get("panel_message_id")
        try:
            if panel_id:
                fake_query = None
                await context.bot.edit_message_text(chat_id=cid, message_id=int(panel_id), text=msg_text, reply_markup=None, parse_mode=ParseMode.HTML)
                # Re-open the filter panel in the same message.
                g = get_group_data(db, cid)
                ptxt, _ = build_filter_panel_content(g)
                kb = _filter_panel_buttons_full(cid) if _filter_words(g) else _filter_panel_buttons_empty(cid)
                await context.bot.edit_message_text(chat_id=cid, message_id=int(panel_id), text=ptxt, reply_markup=kb, parse_mode=ParseMode.HTML)
                _set_filter_panel_session(db, update.effective_user.id, cid, int(panel_id))
                save_db(force=True)
            else:
                await update.message.reply_text(msg_text, parse_mode=ParseMode.HTML)
        except Exception:
            await update.message.reply_text(msg_text, parse_mode=ParseMode.HTML)
        return True

    return False
