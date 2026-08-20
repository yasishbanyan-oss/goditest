# GoodiBot modular feature module
from core import *

def get_owner_panel_content(db: dict) -> tuple[str, InlineKeyboardMarkup]:
    # Keep the owner panel resilient even if an older/restored database has
    # one of these collections missing or stored as None.
    def _safe_len(value, default=0):
        try:
            return len(value) if value is not None else default
        except (TypeError, AttributeError):
            return default

    user_count = _safe_len(db.get("started_users", {}))
    group_count = _safe_len(db.get("active_chats", []))
    banned_users_count = _safe_len(db.get("global_bans", {}))
    banned_groups_count = _safe_len(db.get("global_group_bans", {}))

    text = "<b>مالک محترم ربات \n\nبه پنل اصلی مدیریت ربات خوش آمدید. گزینه مورد نظر را انتخاب کنید:</b>"
    buttons = [
        [InlineKeyboardButton(" خاموشی ربات", callback_data="panel_shutdown_menu", style="danger")],
        [
            InlineKeyboardButton(f" بن کاربر ({banned_users_count})", callback_data="ban_user_start", style="danger"),
            InlineKeyboardButton(" انبن کاربر", callback_data="unban_user_start", style="success")
        ],
        [
            InlineKeyboardButton(f" بن گروه ({banned_groups_count})", callback_data="ban_group_list_1", style="danger"),
            InlineKeyboardButton(" انبن گروه", callback_data="unban_group_list_1", style="success")
        ],
        [
            InlineKeyboardButton(" تنظیم فحش ناموسی", callback_data="owner_fun_named", style="danger"),
            InlineKeyboardButton(" تنظیم فحش عادی", callback_data="owner_fun_normal", style="primary")
        ],
        [
            InlineKeyboardButton(" شعارهای سراسری", callback_data="owner_list_poems", style="primary"),
            InlineKeyboardButton(" غذاهای سراسری", callback_data="owner_list_foods", style="primary")
        ],
        [InlineKeyboardButton(" تنظیم رسانه لف", callback_data="owner_lef_media", style="primary")],
        [
            InlineKeyboardButton(" افزودن شعر جدید", callback_data="owner_add_poem", style="success"),
            InlineKeyboardButton(" افزودن غذا", callback_data="owner_add_food", style="success")
        ],
        [InlineKeyboardButton(f" مشخصات گروه‌ها ({group_count})", callback_data="panel_owner_groups_1", style="primary")],
        [InlineKeyboardButton("⏱ زمان محدودیت (Cooldown)", callback_data="panel_cooldown", style="primary")],
        [InlineKeyboardButton(" مدیریت قابلیت ها", callback_data="panel_features", style="primary")],
        [InlineKeyboardButton(" پیام همگانی پیشرفته (Broadcast)", callback_data="panel_bcast_type_select", style="primary")],
        [InlineKeyboardButton(f" پیام همگانی کاربران ({user_count})", callback_data="panel_user_broadcast", style="success")],
        [InlineKeyboardButton(" ادمین لاگ", callback_data="panel_admin_logs", style="primary")],
        [InlineKeyboardButton(" بکاپ و ریستور دیتابیس", callback_data="panel_backup_restore", style="primary")]
    ]
    return text, InlineKeyboardMarkup(buttons)

async def send_owner_panel_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    clear_user_all_states(db, update.effective_user.id, update.effective_chat.id)
    text, keyboard = get_owner_panel_content(db)
    await update.message.reply_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)

async def edit_owner_panel_message(query):
    db = load_db()
    clear_user_all_states(db, query.from_user.id, query.message.chat.id)
    text, keyboard = get_owner_panel_content(db)
    await query.message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)



def register_group_panel_session(db: dict, chat_id: int, message_id: int, owner_id: int):
    sessions = db.setdefault("_group_panel_sessions", {})
    key = f"{int(chat_id)}:{int(message_id)}"
    sessions[key] = {
        "chat_id": int(chat_id),
        "message_id": int(message_id),
        "owner_id": int(owner_id),
        "updated_at": time.time(),
    }
    # Keep the lightweight session store bounded.
    if len(sessions) > 500:
        old_keys = sorted(sessions, key=lambda k: float((sessions.get(k) or {}).get("updated_at", 0)))
        for old_key in old_keys[: max(0, len(sessions) - 500)]:
            sessions.pop(old_key, None)
    mark_db_dirty()
    save_db(force=True)


def get_group_panel_session(db: dict, chat_id: int, message_id: int):
    return (db.get("_group_panel_sessions", {}) or {}).get(f"{int(chat_id)}:{int(message_id)}")


def clear_group_panel_session(db: dict, chat_id: int, message_id: int):
    sessions = db.get("_group_panel_sessions", {}) or {}
    sessions.pop(f"{int(chat_id)}:{int(message_id)}", None)
    mark_db_dirty()
    save_db(force=True)

def build_group_admin_panel_content(chat_id: int, title: str) -> tuple[str, InlineKeyboardMarkup]:
    esc_title = html.escape(title or "این گروه")
    text = (
        f'<b>به بخش مدیریت گروه خود خوش‌آمدید! <tg-emoji emoji-id="{PANEL_SCALE_EMOJI_ID}">⚖️</tg-emoji></b>\n'
        f'<b><tg-emoji emoji-id="{PANEL_CASTLE_EMOJI_ID}">🏰</tg-emoji> نام گروه: {esc_title}</b>\n\n'
        f'<b>- لطفا از طریق دکمه های زیر عملیات مدیریتی خود را انجام دهید! <tg-emoji emoji-id="{PANEL_HASH_EMOJI_ID}">#️⃣</tg-emoji></b>'
    )
    buttons = [
        [
            InlineKeyboardButton("قفل‌ها", callback_data=f"panel_group_locks:{chat_id}:1", style="primary", icon_custom_emoji_id=LOCK_CUSTOM_EMOJI_ID),
            InlineKeyboardButton("لیست‌ها", callback_data=f"panel_group_lists:{chat_id}", style="primary", icon_custom_emoji_id=LISTS_CUSTOM_EMOJI_ID)
        ],
        [
            InlineKeyboardButton("تنظیمات پیشرفته", callback_data=f"panel_group_advanced:{chat_id}", style="primary", icon_custom_emoji_id=ADVANCED_CUSTOM_EMOJI_ID)
        ],
        [
            InlineKeyboardButton("بستن", callback_data="panel_group_close", style="danger", icon_custom_emoji_id=CLOSE_CUSTOM_EMOJI_ID)
        ]
    ]
    return text, InlineKeyboardMarkup(buttons)

async def render_group_admin_panel_message(query, chat_id: int):
    db = load_db()
    if query.message and not get_group_panel_session(db, chat_id, query.message.message_id):
        register_group_panel_session(db, chat_id, query.message.message_id, query.from_user.id)
    g_data = get_group_data(db, chat_id)
    text, keyboard = build_group_admin_panel_content(chat_id, g_data.get("title") or "")
    await query.message.edit_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)

async def render_group_locks_panel(query, chat_id: int, page: int = 1):
    db = load_db()
    g_data = get_group_data(db, chat_id)
    locks = g_data.get("locks", {})

    text = (
        f'<b>به بخش قفل گروه خود خوش آمدید! <tg-emoji emoji-id="{CANDY_CUSTOM_EMOJI_ID}">🍭</tg-emoji></b>\n'
        '<b>چه عملیاتی انجام می‌دهید؟</b>'
    )

    page_locks = [k for k, v in ALL_LOCKS.items() if v["page"] == page]
    buttons = []
    
    for i in range(0, len(page_locks), 2):
        row = []
        k1 = page_locks[i]
        meta1 = ALL_LOCKS[k1]
        name1 = meta1['name']

        if meta1.get("is_category"):
            btn1 = InlineKeyboardButton(name1, callback_data=f"panel_service_locks:{chat_id}", style=None)
        else:
            is_on1 = locks.get(k1, False)
            btn1 = InlineKeyboardButton(
                name1,
                callback_data=f"tgl_lock:{chat_id}:{k1}:{page}",
                style="success" if is_on1 else None,
                icon_custom_emoji_id=CHECK_CUSTOM_EMOJI_ID if is_on1 else None
            )
        row.append(btn1)

        if i + 1 < len(page_locks):
            k2 = page_locks[i + 1]
            meta2 = ALL_LOCKS[k2]
            name2 = meta2['name']
            if meta2.get("is_category"):
                btn2 = InlineKeyboardButton(name2, callback_data=f"panel_service_locks:{chat_id}", style=None)
            else:
                is_on2 = locks.get(k2, False)
                btn2 = InlineKeyboardButton(
                    name2,
                    callback_data=f"tgl_lock:{chat_id}:{k2}:{page}",
                    style="success" if is_on2 else None,
                    icon_custom_emoji_id=CHECK_CUSTOM_EMOJI_ID if is_on2 else None
                )
            row.append(btn2)
        buttons.append(row)

    if page == 1:
        nav_row = [
            InlineKeyboardButton("بازگشت", callback_data=f"panel_group_main:{chat_id}", style="danger", icon_custom_emoji_id=BACK_CUSTOM_EMOJI_ID),
            InlineKeyboardButton("صفحه بعد", callback_data=f"panel_group_locks:{chat_id}:2", style="danger", icon_custom_emoji_id=NEXT_CUSTOM_EMOJI_ID)
        ]
    else:
        nav_row = [
            InlineKeyboardButton("صفحه قبل", callback_data=f"panel_group_locks:{chat_id}:1", style="danger", icon_custom_emoji_id=PREV_CUSTOM_EMOJI_ID),
            InlineKeyboardButton("بازگشت", callback_data=f"panel_group_main:{chat_id}", style="danger", icon_custom_emoji_id=BACK_CUSTOM_EMOJI_ID)
        ]
    buttons.append(nav_row)

    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

async def render_telegram_service_locks_panel(query, chat_id: int):
    db = load_db()
    g_data = get_group_data(db, chat_id)
    locks = g_data.get("locks", {})

    text = (
        f'<b><tg-emoji emoji-id="{GEAR_CUSTOM_EMOJI_ID}">⚙️</tg-emoji> مدیریت قفل سرویس‌های تلگرام <tg-emoji emoji-id="{CANDY_CUSTOM_EMOJI_ID}">🍭</tg-emoji></b>\n\n'
        '<b>از گزینه‌های زیر برای روشن یا خاموش کردن حذف پیام‌های سرویس استفاده کنید:</b>'
    )

    buttons = []
    for k in TELEGRAM_SERVICE_LOCK_KEYS:
        is_on = locks.get(k, False)
        name = ALL_LOCKS[k]['name']
        btn = InlineKeyboardButton(
            name,
            callback_data=f"tgl_srv_lock:{chat_id}:{k}",
            style="success" if is_on else None,
            icon_custom_emoji_id=CHECK_CUSTOM_EMOJI_ID if is_on else None
        )
        buttons.append([btn])

    buttons.append([InlineKeyboardButton("بازگشت به قفل‌ها", callback_data=f"panel_group_locks:{chat_id}:2", style="danger", icon_custom_emoji_id=BACK_CUSTOM_EMOJI_ID)])

    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

async def render_ban_group_picker(query, page: int, db: dict):
    active_chats = db.get("active_chats", [])
    banned_chats = db.get("global_group_bans", {})
    available_chats = [cid for cid in active_chats if str(cid) not in banned_chats]

    page_size = 5
    total_pages = max(1, (len(available_chats) + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))

    start_idx = (page - 1) * page_size
    current_chats = available_chats[start_idx:start_idx + page_size]

    text = f" <b>انتخاب گروه برای بن (صفحه {page} از {total_pages})</b>\n\nروی گروه مورد نظر کلیک کنید:"
    buttons = []

    for cid in current_chats:
        g_data = get_group_data(db, cid)
        title = g_data.get("title") or f"گروه {cid}"
        buttons.append([InlineKeyboardButton(f" {title}", callback_data=f"select_bangrp:{cid}", style="danger")])

    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("⬅ قبلی", callback_data=f"ban_group_list_{page-1}", style="primary"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton("بعدی ", callback_data=f"ban_group_list_{page+1}", style="primary"))

    if nav_row:
        buttons.append(nav_row)
    buttons.append([InlineKeyboardButton(" بازگشت به پنل اصلی", callback_data="panel_owner_main", style="primary")])

    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

async def render_unban_group_picker(query, page: int, db: dict):
    banned_chats = list(db.get("global_group_bans", {}).keys())

    if not banned_chats:
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(" بازگشت", callback_data="panel_owner_main", style="primary")]])
        await query.message.edit_text(
            f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> هیچ گروهی در لیست بن قرار ندارد.</b>',
            reply_markup=kb,
            parse_mode=ParseMode.HTML
        )
        return

    page_size = 5
    total_pages = max(1, (len(banned_chats) + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))

    start_idx = (page - 1) * page_size
    current_chats = banned_chats[start_idx:start_idx + page_size]

    text = f" <b>انتخاب گروه برای انبن (صفحه {page} از {total_pages})</b>\n\nروی گروه مورد نظر کلیک کنید:"
    buttons = []

    for cid_str in current_chats:
        g_data = get_group_data(db, cid_str)
        title = g_data.get("title") or f"گروه {cid_str}"
        buttons.append([InlineKeyboardButton(f" انبن: {title}", callback_data=f"select_unbangrp:{cid_str}", style="success")])

    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("⬅ قبلی", callback_data=f"unban_group_list_{page-1}", style="primary"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton("بعدی ", callback_data=f"unban_group_list_{page+1}", style="primary"))

    if nav_row:
        buttons.append(nav_row)
    buttons.append([InlineKeyboardButton(" بازگشت به پنل اصلی", callback_data="panel_owner_main", style="primary")])

    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

async def render_shutdown_panel(query, db: dict):
    is_down = db.get("bot_shutdown", False)
    status_str = " وضعیت ربات: خاموش" if is_down else " وضعیت ربات: روشن"

    buttons = [
        [InlineKeyboardButton(" خاموش کردن ربات", callback_data="bot_do_shutdown", style="danger")],
        [InlineKeyboardButton(" روشن کردن ربات", callback_data="bot_do_turn_on", style="success")],
        [InlineKeyboardButton(" بازگشت", callback_data="panel_owner_main", style="primary")]
    ]
    await query.message.edit_text(f"<b>مدیریت خاموشی ربات</b>\n\n{status_str}", reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

async def render_owner_fun_panel(query, fun_type: str, db: dict):
    title = " مدیریت فحش ناموسی ربات" if fun_type == "named" else " مدیریت فحش عادی ربات"
    key = "global_fun_named" if fun_type == "named" else "global_fun_normal"
    items = db.get(key, [])
    
    text = (
        f"<b>{title}</b>\n\n"
        f"<b>تعداد پاسخ‌های ثبت‌شده:</b> <code>{len(items)}</code> عدد"
    )

    buttons = [
        [InlineKeyboardButton(" افزودن پاسخ", callback_data=f"own_fun_add:{fun_type}", style="success")],
        [InlineKeyboardButton(" حذف همه پاسخ‌ها", callback_data=f"own_fun_del_all:{fun_type}", style="danger")],
        [InlineKeyboardButton(" بازگشت به پنل اصلی", callback_data="panel_owner_main", style="primary")]
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

async def render_welcome_panel_message(query, chat_id: int, db: dict):
    g_data = get_group_data(db, chat_id)
    w_set = g_data.get("welcome", {})
    is_enabled = w_set.get("enabled", True)
    has_custom = w_set.get("custom", False)

    status_str = " فعال" if is_enabled else " غیرفعال"
    custom_str = "اختصاصی تنظیم شده" if has_custom else "پیش‌فرض سیستم"

    text = (
        f" <b>مدیریت خوش‌آمدگویی گروه</b>\n\n"
        f"<b>وضعیت فعلی:</b> {status_str}\n"
        f"<b>نوع پیام:</b> {custom_str}"
    )

    toggle_btn_text = " غیرفعال کردن" if is_enabled else " فعال کردن"
    buttons = [
        [InlineKeyboardButton(toggle_btn_text, callback_data=f"welcome_toggle:{chat_id}", style="primary")],
        [InlineKeyboardButton(" تنظیم پیام خوش‌آمد", callback_data=f"welcome_set:{chat_id}", style="success")],
        [InlineKeyboardButton(" حذف پیام اختصاصی", callback_data=f"welcome_delete_confirm:{chat_id}", style="danger")],
        [InlineKeyboardButton(" بازگشت", callback_data=f"panel_group_advanced:{chat_id}", style="primary")]
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

async def render_comment_panel_message(query, chat_id: int, db: dict):
    g_data = get_group_data(db, chat_id)
    c_set = g_data.get("comment", {})
    is_enabled = c_set.get("enabled", False)
    has_custom = c_set.get("custom", False)

    status_str = " فعال" if is_enabled else " خاموش"
    custom_str = "ذخیره شده" if has_custom else "تنظیم نشده"

    text = (
        f" <b>سیستم مدیریت کامنت اتوماتیک کانال</b>\n\n"
        f"<b>وضعیت سیستم:</b> {status_str}\n"
        f"<b>پیام کامنت:</b> {custom_str}"
    )

    toggle_btn_text = " خاموش کردن" if is_enabled else " فعال کردن"
    buttons = [
        [InlineKeyboardButton(" تنظیم کامنت", callback_data=f"comment_set:{chat_id}", style="success")],
        [InlineKeyboardButton(toggle_btn_text, callback_data=f"comment_toggle:{chat_id}", style="primary")],
        [InlineKeyboardButton(" حذف کامنت ذخیره‌شده", callback_data=f"comment_delete:{chat_id}", style="danger")],
        [InlineKeyboardButton(" بازگشت", callback_data=f"panel_group_advanced:{chat_id}", style="primary")]
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

async def render_owner_groups_page(query, page: int, db: dict, context: ContextTypes.DEFAULT_TYPE):
    active_chats = db.get("active_chats", [])
    page_size = 5
    total_pages = max(1, (len(active_chats) + page_size - 1) // page_size)
    page = max(1, min(page, total_pages))

    start_idx = (page - 1) * page_size
    current_chats = active_chats[start_idx:start_idx + page_size]

    text = f" <b>مشخصات گروه‌ها (صفحه {page} از {total_pages})</b>\n\nلطفاً گروه موردنظر را انتخاب کنید:"
    buttons = []

    for cid in current_chats:
        g_data = get_group_data(db, cid)
        title = g_data.get("title") or str(cid)
        buttons.append([InlineKeyboardButton(f" {title}", callback_data=f"ogrp_view:{cid}", style="primary")])

    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton("⬅ قبلی", callback_data=f"panel_owner_groups_{page-1}", style="primary"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton("بعدی ", callback_data=f"panel_owner_groups_{page+1}", style="primary"))

    if nav_row:
        buttons.append(nav_row)
    buttons.append([InlineKeyboardButton(" بازگشت به پنل اصلی", callback_data="panel_owner_main", style="primary")])

    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

async def render_owner_single_group_panel(query, target_cid: int, db: dict, context: ContextTypes.DEFAULT_TYPE):
    g_data = get_group_data(db, target_cid)
    title = html.escape(g_data.get("title") or "بدون عنوان")
    
    text = (
        f" <b>مشخصات گروه: {title}</b>\n"
        f"🆔 <b>Chat ID:</b> <code>{target_cid}</code>\n\n"
        "یکی از گزینه‌های زیر را انتخاب نمایید:"
    )

    buttons = [
        [InlineKeyboardButton(" لینک گروه", callback_data=f"ogrp_link:{target_cid}", style="primary")],
        [InlineKeyboardButton(" اعضای گروه (TXT)", callback_data=f"ogrp_members:{target_cid}", style="primary")],
        [InlineKeyboardButton(" سرچ پیام (TXT)", callback_data=f"ogrp_search:{target_cid}", style="primary")],
        [InlineKeyboardButton(" ادمین‌ها (TXT)", callback_data=f"ogrp_admins:{target_cid}", style="primary")],
        [InlineKeyboardButton(" بازگشت به لیست گروه‌ها", callback_data="panel_owner_groups_1", style="primary")]
    ]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

async def render_admin_logs_panel(query, db: dict):
    logs = db.get("admin_logs", [])
    recent_logs = logs[-20:][::-1]

    if not recent_logs:
        text = " <b>هیچ لاگ مدیریتی ثبت نشده است.</b>"
    else:
        text = " <b>۲۰ عملیات اخیر ادمین‌ها:</b>\n\n"
        for idx, l in enumerate(recent_logs, 1):
            admin_mention = get_user_mention(l["admin_id"], l["admin_name"])
            text += (
                f"<b>{idx}. {html.escape(l['action_type'])}</b>\n"
                f" <b>ادمین:</b> {admin_mention}\n"
                f"🆔 <b>User ID:</b> <code>{l['admin_id']}</code>\n"
                f" <b>گروه:</b> {html.escape(l['chat_title'])}\n"
                f"🆔 <b>Chat ID:</b> <code>{l['chat_id']}</code>\n"
                f" <b>جزئیات:</b> {html.escape(l['details'])}\n"
                f" <b>زمان:</b> {l['timestamp']}\n"
                f"----------------------------\n"
            )

    buttons = [[InlineKeyboardButton(" بازگشت", callback_data="panel_owner_main", style="primary")]]
    await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)

async def render_features_panel_message(query, db: dict):
    feats = db.get("features", {})
    def status(key):
        return "" if feats.get(key, True) else ""

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton(f"{status('world_time')}  ساعت جهانی", callback_data="toggle_world_time", style="primary")],
        [InlineKeyboardButton(f"{status('handsome')}  خوشتیپ", callback_data="toggle_handsome", style="primary")],
        [InlineKeyboardButton(f"{status('jende')}  جنده", callback_data="toggle_jende", style="primary")],
        [InlineKeyboardButton(f"{status('koni')}  کونی", callback_data="toggle_koni", style="primary")],
        [InlineKeyboardButton(f"{status('jaghi')}  جقی", callback_data="toggle_jaghi", style="primary")],
        [InlineKeyboardButton(f"{status('koskhal')}  کصخل", callback_data="toggle_koskhal", style="primary")],
        [InlineKeyboardButton(f"{status('sexy')}  سکسی", callback_data="toggle_sexy", style="primary")],
        [InlineKeyboardButton(f"{status('jazab')}  جذاب", callback_data="toggle_jazab", style="primary")],
        [InlineKeyboardButton(f"{status('ship')}  شیپ", callback_data="toggle_ship", style="primary")],
        [InlineKeyboardButton(f"{status('food')}  غذا", callback_data="toggle_food", style="primary")],
        [InlineKeyboardButton(f"{status('lef')}  لف", callback_data="toggle_lef", style="primary")],
        [InlineKeyboardButton(f"{status('goh_khor')}  گوه خور", callback_data="toggle_goh_khor", style="primary")],
        [InlineKeyboardButton(f"{status('koni_percent')}  درصد", callback_data="toggle_koni_percent", style="primary")],
        [InlineKeyboardButton(" بازگشت", callback_data="panel_owner_main", style="primary")]
    ])
    await query.message.edit_text(" <b>مدیریت قابلیت‌ها</b>\n\nبا کلیک روی هر دکمه، وضعیت آن را روشن یا خاموش کنید:", reply_markup=keyboard, parse_mode=ParseMode.HTML)

def get_advanced_status_text(db: dict, chat_id: int) -> str:
    base_text = '<tg-emoji emoji-id="5765170391383286478">🗂</tg-emoji> <b>تنظیمات پیشرفته :</b>\n\n- عملیات مدیریتی خود را از طریق دکمه‌های زیر انجام دهید.'
    return base_text

def build_advanced_panel_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    cid = int(chat_id)
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("تایید هویت", callback_data=f"advanced_identity:{cid}", style="primary", icon_custom_emoji_id="5231012545799666522"), InlineKeyboardButton("ضد خیانت", callback_data=f"advanced_anti_betrayal:{cid}", style="primary", icon_custom_emoji_id="5872792857252733333")],
        [InlineKeyboardButton("عضویت اجباری", callback_data=f"advanced_forced_membership:{cid}", style="primary", icon_custom_emoji_id="6084584811379299518"), InlineKeyboardButton("خوش آمد", callback_data=f"advanced_welcome:{cid}", style="primary", icon_custom_emoji_id="5443038326535759644")],
        [InlineKeyboardButton("تنظیم اخطار", callback_data=f"advanced_warnings:{cid}", style="primary", icon_custom_emoji_id="5420323339723881652"), InlineKeyboardButton("سخت‌گیرانه", callback_data=f"advanced_strict:{cid}", style="primary", icon_custom_emoji_id="5825563515670242868")],
        [InlineKeyboardButton("ضد تبچی", callback_data=f"advanced_anti_cheat:{cid}", style="primary", icon_custom_emoji_id="5856986522904959860"), InlineKeyboardButton("پیام‌ رگباری", callback_data=f"advanced_burst_messages:{cid}", style="primary", icon_custom_emoji_id="5859215993183674044")],
        [InlineKeyboardButton("قفل خودکار", callback_data=f"advanced_auto_lock:{cid}", style="primary", icon_custom_emoji_id="5886328760218688328"), InlineKeyboardButton("اختیارات گروه", callback_data=f"advanced_group_permissions:{cid}", style="primary", icon_custom_emoji_id="5901989641204018165")],
        [InlineKeyboardButton("پاکسازی گروه", callback_data=f"advanced_cleanup:{cid}", style="primary", icon_custom_emoji_id="5458382591121964689"), InlineKeyboardButton("قفل امکانات", callback_data=f"advanced_feature_locks:{cid}", style="primary", icon_custom_emoji_id="5296369303661067030")],
        [InlineKeyboardButton("خداحافظی", callback_data=f"advanced_goodbye:{cid}", style="primary", icon_custom_emoji_id="5904279000506704761")],
        [InlineKeyboardButton("بازگشت", callback_data=f"panel_group_main:{cid}", style="danger", icon_custom_emoji_id="5983093054842606366")]
    ])

def build_check_user_prompt_text() -> str:
    return (
        '<tg-emoji emoji-id="5947405845162629459">🥷</tg-emoji> <b>به بخش بررسی کاربر خوش آمدید.</b>\n\n'
        '<tg-emoji emoji-id="5803385846446954748">🤖</tg-emoji> <b>برای دریافت مشخصات کاربر موردنظر ، آیدی عددی یا آیدی تلگرام آن را همینجا ارسال کنید و منتظر پاسخ ربات باشید.</b>'
    )

def build_check_user_keyboard(return_to_lists: bool = True) -> InlineKeyboardMarkup:
    if return_to_lists:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("بازگشت", callback_data="check_user_back_to_lists", style="danger", icon_custom_emoji_id=BACK_CUSTOM_EMOJI_ID)]
        ])
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("بازگشت", callback_data="check_user_back_to_lists", style="danger", icon_custom_emoji_id=BACK_CUSTOM_EMOJI_ID)]
    ])

def build_check_user_close_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("بستن", callback_data="check_user_close", style="danger", icon_custom_emoji_id=CLOSE_CUSTOM_EMOJI_ID)]
    ])

def build_check_user_loading_text() -> str:
    return (
        '<tg-emoji emoji-id="5803057229909202251">♻️</tg-emoji> <b>درحال بررسی مشخصات کاربر موردنظر...! </b>'
        '<tg-emoji emoji-id="5765170391383286478">🗂</tg-emoji>\n'
        '<b>- شکیبا باشید.</b>'
    )

def build_check_user_not_found_text() -> str:
    return (
        '<tg-emoji emoji-id="5829923384217050622">❓</tg-emoji> <b>کاربر موردنظر یافت نشد.</b>\n'
        '<b>- احتمالا در گروه عضو نیست یا در دیتابیس ربات ثبت نشده است.</b>'
    )

def build_check_user_close_text() -> str:
    return '<tg-emoji emoji-id="5947405845162629459">🥷</tg-emoji> <b>پنل بررسی کاربران با موفقیت بسته شد.</b>'

def build_direct_check_user_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton("بررسی کاربر", callback_data="check_user_direct", style="primary", icon_custom_emoji_id=CHECK_USER_CANDLE_CUSTOM_EMOJI_ID)]])

async def open_check_user_panel(update: Update, context: ContextTypes.DEFAULT_TYPE, return_to_advanced: bool = False, edit_message=None):
    if not update.effective_chat or not update.effective_user:
        return
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    db = load_db()
    if edit_message is not None:
        panel_message = edit_message
        await panel_message.edit_text(
            build_check_user_prompt_text(),
            reply_markup=build_check_user_keyboard(),
            parse_mode=ParseMode.HTML
        )
    else:
        panel_message = await update.message.reply_text(
            build_check_user_prompt_text(),
            reply_markup=build_check_user_keyboard(),
            parse_mode=ParseMode.HTML
        )
    db.setdefault("states", {}).setdefault("waiting_check_user", {})[str(user_id)] = {
        "chat_id": chat_id, "panel_message_id": panel_message.message_id,
        "return_to_advanced": False,
        "return_to_lists": True
    }
    mark_db_dirty(); save_db(force=True)

def build_check_user_error_text() -> str:
    return build_check_user_not_found_text()

async def build_group_lists_status(context: ContextTypes.DEFAULT_TYPE, chat_id: int, db: dict, g_data: dict) -> str:
    management = g_data.get("management", {}) or {}
    if management.get("configured"):
        owners_count = len(management.get("owners", []) or [])
        admins_count = len(management.get("admins", []) or [])
    else:
        owners_count = 1
        admins_count = 0
        try:
            admins = await context.bot.get_chat_administrators(chat_id)
            admins_count = len([a for a in admins if a.status == ChatMemberStatus.ADMINISTRATOR and not a.user.is_bot])
        except Exception:
            admins_count = 0

    # اعضای ویژه
    special_members_count = len(g_data.get("special_members", []))

    # سکوت‌شده‌ها (Mute)
    muted_count = len(g_data.get("muted_users", []))

    # بن‌شده‌ها
    prune_group_action_lists(g_data)
    banned_count = len(g_data.get("banned_users", {}) or {})

    # اخطار گرفتگان
    warned_count = len(g_data.get("warned_users", []))

    # معاف شدگان (Exempt)
    exempt_count = len(g_data.get("exempt_users", []))

    # کلمات فیلتر
    filter_words_count = len(g_data.get("filter_words", []))

    # کامنت‌گذاری
    comment_enabled = g_data.get("comment", {}).get("enabled", False)
    comment_status_str = "فعال" if comment_enabled else "غیرفعال"

    # لیست پاسخ (پاسخ‌دهی خودکار)
    auto_responses_count = len(g_data.get("auto_responses", []))

    text = (
        '<tg-emoji emoji-id="5803057229909202251">♻️</tg-emoji> <b>بخش لیست ها :</b>\n\n'
        f'   ├<tg-emoji emoji-id="5803378592247190638">⚡️</tg-emoji> <b>مالکین : {owners_count}</b>\n'
        f'   ├<tg-emoji emoji-id="5983208078361761545">⚡️</tg-emoji> <b>مدیران : {admins_count}</b>\n'
        f'   ├<tg-emoji emoji-id="5803224441575970112">💼</tg-emoji> <b>ویژه ها : {special_members_count}</b>\n'
        f'   ├<tg-emoji emoji-id="5983227268275638287">💠</tg-emoji> <b>سکوت شدگان : {muted_count}</b>\n'
        f'   ├<tg-emoji emoji-id="5802963792895678011">⚫️</tg-emoji> <b>بن شدگان : {banned_count}</b>\n'
        f'   ├<tg-emoji emoji-id="5803420768826038185">🔘</tg-emoji> <b>اخطار گرفتگان : {warned_count}</b>\n'
        f'   ├<tg-emoji emoji-id="5803257186406634805">🖤</tg-emoji> <b>معاف شدگان : {exempt_count}</b>\n'
        f'   ├<tg-emoji emoji-id="5866017773976555711">⚫️</tg-emoji> <b>کلمات فیلتر : {filter_words_count}</b>\n'
        f'   ├<tg-emoji emoji-id="5981132367912243320">🟢</tg-emoji> <b>کامنت‌گذاری : {comment_status_str}</b>\n'
        f'   ├<tg-emoji emoji-id="5980891235563343409">🤖</tg-emoji> <b>لیست پاسخ : {auto_responses_count}</b>\n'
        '~ ~ ~ ~ ~ ~ ~ ~ ~ ~'
    )
    return text   

def _user_label(user) -> str:
    if getattr(user, "username", None): return f"@{html.escape(user.username)}"
    return get_user_mention(user.id, user.full_name or "کاربر")

def build_warning_panel(g_data: dict, chat_id: int) -> tuple[str, InlineKeyboardMarkup]:
    s = g_data.setdefault("warning_settings", {"count": 3, "punishment": None, "temp_mute_hours": 1})
    count = max(1, min(20, int(s.get("count", 3))))
    punishment = s.get("punishment")
    temp_hours = max(1, int(s.get("temp_mute_hours", 1)))
    temp_active = punishment == "temp_mute"
    mute_active = punishment == "mute"
    kick_active = punishment == "kick"
    text = f'<b><tg-emoji emoji-id="{WARN_HEADER_EMOJI}">⚖️</tg-emoji> به بخش تنظیم اخطار خوش آمدید.</b>\n\n<b><tg-emoji emoji-id="{WARN_INFO_EMOJI}">🌟</tg-emoji> از طریق دکمه‌های زیر تعداد اخطار موردنظر و مجازات دریافتی را مشخص کنید.</b>'
    rows = [
        [InlineKeyboardButton(f"تعداد اخطار: {count}", callback_data=f"warning_noop:{chat_id}", style="primary", icon_custom_emoji_id=WARN_COUNT_EMOJI)],
        [InlineKeyboardButton("−", callback_data=f"warning_dec:{chat_id}", style="danger", icon_custom_emoji_id=WARN_MINUS_EMOJI), InlineKeyboardButton("+", callback_data=f"warning_inc:{chat_id}", style="success", icon_custom_emoji_id=WARN_PLUS_EMOJI)],
        [InlineKeyboardButton(f"حالت سکوت موقت: {'فعال' if temp_active else 'غیرفعال'}", callback_data=f"warning_mode:temp_mute:{chat_id}", style="success" if temp_active else None, icon_custom_emoji_id=WARN_TEMP_EMOJI)],
    ]
    if temp_active:
        rows.append([InlineKeyboardButton("۱ ساعت", callback_data=f"warning_temp_dec:{chat_id}", style="danger", icon_custom_emoji_id=WARN_MINUS_EMOJI), InlineKeyboardButton(f"{temp_hours} ساعت", callback_data=f"warning_temp_noop:{chat_id}", style="primary"), InlineKeyboardButton("۱ ساعت", callback_data=f"warning_temp_inc:{chat_id}", style="success", icon_custom_emoji_id=WARN_PLUS_EMOJI)])
    rows.extend([
        [InlineKeyboardButton(f"حالت سکوت: {'فعال' if mute_active else 'غیرفعال'}", callback_data=f"warning_mode:mute:{chat_id}", style="success" if mute_active else None, icon_custom_emoji_id=WARN_MUTE_EMOJI)],
        [InlineKeyboardButton(f"حالت اخراج: {'فعال' if kick_active else 'غیرفعال'}", callback_data=f"warning_mode:kick:{chat_id}", style="success" if kick_active else None, icon_custom_emoji_id=WARN_KICK_EMOJI)],
        [InlineKeyboardButton("بازگشت", callback_data=f"warning_back:{chat_id}", style="danger", icon_custom_emoji_id=BACK_CUSTOM_EMOJI_ID)]
    ])
    return text, InlineKeyboardMarkup(rows)

async def render_warning_panel(query, chat_id: int, db: dict):
    g = get_group_data(db, chat_id)
    text, kb = build_warning_panel(g, chat_id)
    await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)

async def build_group_list_detail_content(context, chat_id: int, list_type: str, db: dict, viewer_id: int) -> tuple[str, InlineKeyboardMarkup]:
    g = get_group_data(db, chat_id)
    prune_group_action_lists(g)
    m = g.get("management", {}) or {}
    title_map = {"owners": "لیست مالکین", "admins": "لیست مدیران", "special": "لیست اعضای ویژه", "exempt": "لیست معاف شدگان", "warns": "لیست کاربران اخطار گرفته", "muted": "لیست سکوت شدگان", "banned": "لیست بن شدگان"}
    title = title_map.get(list_type, "لیست")
    lines = [f'<b><tg-emoji emoji-id="{LISTS_CUSTOM_EMOJI_ID}">📋</tg-emoji> {title}</b>\n']
    if list_type in ("owners", "admins", "special", "exempt"):
        ids = m.get(list_type, []) or []
        for uid in ids:
            info = _stored_user(db, int(uid))
            display = f'@{html.escape(info["username"])}' if info.get("username") else get_user_mention(int(uid), info.get("fullname", "کاربر"))
            lines.append(f'<b><tg-emoji emoji-id="{PREMIUM_USER_EMOJI}">👤</tg-emoji> {display} | {role_label(list_type)}</b>')
        if not ids: lines.append(f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> لیستی برای نمایش وجود ندارد.</b>')
    else:
        store = g.get("warnings", {}) if list_type == "warns" else g.get("muted_users", {}) if list_type == "muted" else g.get("banned_users", {})
        if list_type == "warns":
            for uid, item in store.items():
                info = _stored_user(db, int(uid), item.get("fullname", "کاربر"), item.get("username", ""))
                display = f'@{html.escape(info["username"])}' if info.get("username") else get_user_mention(int(uid), info.get("fullname", "کاربر"))
                lines.append(f'<b><tg-emoji emoji-id="{PREMIUM_WARN_COUNT_EMOJI}">😾</tg-emoji> | {display} | {int(item.get("count", 0))} اخطار</b>')
        else:
            for uid, item in store.items():
                info = _stored_user(db, int(uid), item.get("fullname", "کاربر"), item.get("username", ""))
                display = f'@{html.escape(info["username"])}' if info.get("username") else get_user_mention(int(uid), info.get("fullname", "کاربر"))
                created = item.get("created_at")
                until = item.get("until")
                when = format_user_event_time(created) if created else "ثبت نشده"
                expiry = "دائم" if not until else format_user_event_time(until)
                lines.append(f'<b><tg-emoji emoji-id="{PREMIUM_USER_EMOJI}">👤</tg-emoji> {display} | آیدی: <code>{uid}</code> | زمان: {when} | تا: {expiry}</b>')
        if not store: lines.append(f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> لیستی برای نمایش وجود ندارد.</b>')
    can_cleanup = await is_configured_group_manager(context, chat_id, viewer_id)
    # Keep the owners-list cleanup button visible to managers so an unauthorized
    # manager gets the exact owner-only explanation instead of a silent omission.
    buttons = []
    if can_cleanup:
        buttons.append([InlineKeyboardButton("پاکسازی", callback_data=f"list_cleanup_confirm:{list_type}:{chat_id}", style="success", icon_custom_emoji_id=CLEANUP_CUSTOM_EMOJI_ID)])
    buttons.append([InlineKeyboardButton("⬅ بازگشت", callback_data=f"panel_group_lists:{chat_id}", style="danger", icon_custom_emoji_id=BACK_CUSTOM_EMOJI_ID)])
    return "\n".join(lines), InlineKeyboardMarkup(buttons)

async def render_group_list_detail(query, context, chat_id: int, list_type: str, db: dict):
    text, kb = await build_group_list_detail_content(context, chat_id, list_type, db, query.from_user.id)
    await query.message.edit_text(text, reply_markup=kb, parse_mode=ParseMode.HTML)

async def render_cleanup_confirm(query, list_type: str, chat_id: int):
    names = {"owners": "مالکین", "admins": "مدیران", "special": "ویژه", "exempt": "معاف", "warns": "اخطارها", "muted": "سکوت ها", "banned": "بن ها"}
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton("بله", callback_data=f"list_cleanup:{list_type}:{chat_id}", style="success", icon_custom_emoji_id=CHECK_CUSTOM_EMOJI_ID),
        InlineKeyboardButton("خیر", callback_data=f"list_cleanup_cancel:{list_type}:{chat_id}", style="danger", icon_custom_emoji_id=CROSS_CUSTOM_EMOJI_ID)
    ]])
    await query.message.edit_text(f'<b><tg-emoji emoji-id="{CHECK_CUSTOM_EMOJI_ID}">✔️</tg-emoji> آیا از پاکسازی کامل لیست {names.get(list_type, "موردنظر")} مطمئن هستید؟</b>', reply_markup=kb, parse_mode=ParseMode.HTML)
