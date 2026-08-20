# GoodiBot automatic response feature
from core import *
from telegram import ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton


AUTO_STATE_KEY = "auto_response_flow"
AUTO_PANEL_KEY = "auto_response_panel_context"
AUTO_GROUP_KEY = "auto_responses"

# Premium custom emoji IDs used in the automatic-response UI.
AUTO_EMOJI = {
    "welcome": "6024048153580277867",
    "info": "6026095130698584657",
    "next": "5899859522108789256",
    "manage": "5902255053003034414",
    "back": "5823664135103061930",
    "menu": "6294098882355794530",
    "add": "5819032824623144971",
    "delete": "5819154526816444042",
    "finish": "5836866392124563486",
    "list": "5859215993183674044",
    "stage1": "5899731270090363274",
    "num1": "5899760673436471128",
    "num2": "5900246704820588032",
    "num3": "5899833069405212539",
    "all": "6057495125498532044",
    "managers": "6059760849596191487",
    "owner": "6294100961119966181",
    "cancel": "6292024898483130897",
    "stage2": "6003651701783929327",
    "stage3": "5082613952479757015",
    "success": "6026147640968744910",
    "list_clock": "5945116932536540095",
    "list_count": "5972009728526523236",
    "left": "5767083949637507970",
    "right": "5767058308682751651",
    "plane": "5339236405874814208",
    "warning": "5420323339723881652",
    "removed": "5803378592247190638",
    "bullet": "5884330316230827477",
    "done": "5902204801885671680",
}


def _ae(name: str, fallback: str) -> str:
    return f'<tg-emoji emoji-id="{AUTO_EMOJI.get(name, "")}">{fallback}</tg-emoji>'


def _state_store(db: dict) -> dict:
    return db.setdefault("states", {}).setdefault(AUTO_STATE_KEY, {})


def _panel_store(db: dict) -> dict:
    return db.setdefault("states", {}).setdefault(AUTO_PANEL_KEY, {})


def _group_responses(g_data: dict) -> list:
    items = g_data.setdefault(AUTO_GROUP_KEY, [])
    if not isinstance(items, list):
        items = []
        g_data[AUTO_GROUP_KEY] = items
    return items


def _norm_auto_text(text: str) -> str:
    value = normalize_text(text or "")
    value = (
        value.replace("ي", "ی")
             .replace("ى", "ی")
             .replace("ك", "ک")
             .replace("ۀ", "ه")
             .replace("ة", "ه")
    )
    return re.sub(r"\s+", " ", value).strip().casefold()


def _flow(db: dict, user_id: int):
    return _state_store(db).get(str(user_id))


def _set_flow(db: dict, user_id: int, flow: dict):
    _state_store(db)[str(user_id)] = flow
    mark_db_dirty()
    save_db(force=True)


def _clear_flow(db: dict, user_id: int):
    states = db.setdefault("states", {})
    flows = states.setdefault(AUTO_STATE_KEY, {})
    if str(user_id) in flows:
        del flows[str(user_id)]
        mark_db_dirty()
        save_db(force=True)

def cancel_auto_response_flow(db: dict, user_id: int):
    """Cancel only the private automatic-response flow for a user.

    This public wrapper is used by real command handlers (/start, /panel,
    /done) so those commands can always cancel an unfinished auto-response
    flow without depending on a private helper name.
    """
    _clear_flow(db, int(user_id))


def _flow_group(flow: dict | None) -> int:
    try:
        return int((flow or {}).get("chat_id") or 0)
    except Exception:
        return 0


def _role_allowed(g_data: dict, user_id: int, access: str) -> bool:
    if access == "all":
        return True

    mgmt = g_data.get("management", {}) or {}

    def ids(name):
        out = set()
        for uid in mgmt.get(name, []) or []:
            try:
                out.add(int(uid))
            except Exception:
                pass
        return out

    uid = int(user_id)
    owner_ids = ids("owners")
    primary = mgmt.get("primary_owner_id")
    try:
        if primary is not None:
            owner_ids.add(int(primary))
    except Exception:
        pass

    if access == "owner":
        return uid in owner_ids

    # "مقام دار" = مدیر + ویژه + معاف. مالک هم در این سطح بالاتر قرار می‌گیرد.
    manager_ids = ids("admins") | ids("special") | ids("exempt") | owner_ids
    return uid in manager_ids


def _access_label(access: str) -> str:
    return {
        "all": "همه کاربران",
        "manager": "کاربران مقام دار",
        "owner": "مقام مالک",
    }.get(access, "همه کاربران")


def _auto_main_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [
                KeyboardButton("افزودن پاسخ", style="success", icon_custom_emoji_id=AUTO_EMOJI["add"]),
                KeyboardButton("حذف پاسخ", style="danger", icon_custom_emoji_id=AUTO_EMOJI["delete"]),
            ],
            [
                KeyboardButton("پایان دادن", style="danger", icon_custom_emoji_id=AUTO_EMOJI["finish"]),
                KeyboardButton("مشاهده لیست پاسخ", style="primary", icon_custom_emoji_id=AUTO_EMOJI["list"]),
            ],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="یکی از گزینه‌ها را انتخاب کنید",
    )


def _auto_stage1_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "همه کاربران", callback_data=f"auto_access:{int(chat_id)}:all",
                style="success", icon_custom_emoji_id=AUTO_EMOJI["all"],
            ),
            InlineKeyboardButton(
                "کاربران مقام دار", callback_data=f"auto_access:{int(chat_id)}:manager",
                style="primary", icon_custom_emoji_id=AUTO_EMOJI["managers"],
            ),
        ],
        [
            InlineKeyboardButton(
                "مقام مالک", callback_data=f"auto_access:{int(chat_id)}:owner",
                style="primary", icon_custom_emoji_id=AUTO_EMOJI["owner"],
            ),
            InlineKeyboardButton(
                "لغو", callback_data=f"auto_access:{int(chat_id)}:cancel",
                style="danger", icon_custom_emoji_id=AUTO_EMOJI["cancel"],
            ),
        ],
    ])


def _auto_delete_keyboard(g_data: dict) -> ReplyKeyboardMarkup:
    rows = [[KeyboardButton("لغو", style="danger", icon_custom_emoji_id=AUTO_EMOJI["delete"])]]
    buttons = [
        KeyboardButton(
            str(item.get("trigger", "")),
            style="primary",
            icon_custom_emoji_id=AUTO_EMOJI["bullet"],
        )
        for item in _group_responses(g_data) if item.get("trigger")
    ]
    for i in range(0, len(buttons), 2):
        rows.append(buttons[i:i + 2])
    return ReplyKeyboardMarkup(
        rows,
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="کلمه‌ای را برای حذف انتخاب کنید",
    )


def _auto_group_panel_keyboard(bot_username: str, chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "👾 مدیریت پاسخ سریع",
                url=f"https://t.me/{bot_username}?start=autoresp_{chat_id}",
                style="primary",
                icon_custom_emoji_id=AUTO_EMOJI["manage"],
            )
        ],
        [
            InlineKeyboardButton(
                "⬅️ بازگشت",
                callback_data=f"panel_group_lists:{chat_id}",
                style="danger",
                icon_custom_emoji_id=AUTO_EMOJI["back"],
            )
        ],
    ])


async def _sync_group_auto_panel(context, flow: dict | None, g_data: dict):
    flow = flow or {}
    chat_id = _flow_group(flow)
    message_id = flow.get("panel_message_id")
    if not chat_id or not message_id:
        return
    try:
        me = await context.bot.get_me()
        text = _auto_group_panel_list_text(g_data) if _group_responses(g_data) else _auto_group_panel_text()
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=int(message_id),
            text=text,
            reply_markup=_auto_group_panel_keyboard(me.username, chat_id),
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        logger.exception("Failed to sync automatic-response group panel | chat_id=%s | message_id=%s", chat_id, message_id)


def _auto_group_panel_text() -> str:
    return (
        f'<b>{_ae("welcome", "🔄")} به بخش پاسخ‌دهی خودکار خوش آمدید.</b>\n\n'
        f'<b>{_ae("info", "👆")} این بخش چه می‌کند؟ شما می‌توانید کلماتی را در این قسمت ثبت کنید تا در صورت مشاهده توسط سیستم هوشمند ربات گودی پیام پاسخ تنظیم شده، روی کاربر ریپلی شود.</b>\n\n'
        f'<b>{_ae("next", "🩵")} عملیات بعدی را از طریق دکمه‌های زیر انجام دهید.</b>'
    )


async def open_auto_response_panel(query, context, chat_id: int, db: dict):
    user_id = query.from_user.id
    if not await is_configured_group_manager(context, chat_id, user_id):
        await query.answer(" دسترسی غیرمجاز!", show_alert=True)
        return
    me = await context.bot.get_me()
    _panel_store(db)[str(user_id)] = {
        "chat_id": int(chat_id),
        "panel_message_id": int(query.message.message_id),
    }
    mark_db_dirty()
    save_db(force=True)
    g_data = get_group_data(db, chat_id)
    panel_text = _auto_group_panel_list_text(g_data) if _group_responses(g_data) else _auto_group_panel_text()
    await query.message.edit_text(
        panel_text,
        reply_markup=_auto_group_panel_keyboard(me.username, chat_id),
        parse_mode=ParseMode.HTML,
    )
    await query.answer()


async def enter_auto_response_manager(update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int) -> bool:
    if not update.message or update.effective_chat.type != "private":
        return False

    user_id = update.effective_user.id
    db = load_db()
    if not await is_configured_group_manager(context, int(chat_id), user_id):
        await update.message.reply_text(
            f'<b>{_ae("cancel", "❌")} این بخش فقط برای مدیران همان گروه فعال است.</b>',
            parse_mode=ParseMode.HTML,
        )
        return True

    pending_panel = _panel_store(db).get(str(user_id), {}) or {}
    panel_message_id = pending_panel.get("panel_message_id") if int(pending_panel.get("chat_id", 0) or 0) == int(chat_id) else None
    if panel_message_id:
        _panel_store(db).pop(str(user_id), None)
        mark_db_dirty()
        save_db(force=True)
    flow_data = {"chat_id": int(chat_id), "step": "menu"}
    if panel_message_id:
        flow_data["panel_message_id"] = int(panel_message_id)
    _set_flow(db, user_id, flow_data)
    await update.message.reply_text(
        f'<b>{_ae("menu", "☠️")} گزینه‌ی موردنظر را جهت مدیریت سیستم پاسخ‌دهی مشخص کنید.</b>',
        reply_markup=_auto_main_keyboard(),
        parse_mode=ParseMode.HTML,
    )
    return True


async def handle_auto_response_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Handle only the private automatic-response management flow.

    Returns True when this message belongs to the auto-response UI and must not
    fall through into the bot's other generic private-message logic.
    """
    if not update.message or not update.effective_chat or update.effective_chat.type != "private":
        return False

    user = update.effective_user
    if not user or user.is_bot:
        return False

    db = load_db()
    flow = _flow(db, user.id)
    if not flow:
        return False

    group_id = _flow_group(flow)
    if not group_id or not await is_configured_group_manager(context, group_id, user.id):
        _clear_flow(db, user.id)
        await update.message.reply_text(
            f'<b>{_ae("cancel", "❌")} دسترسی این بخش برای شما فعال نیست.</b>',
            reply_markup=ReplyKeyboardRemove(),
            parse_mode=ParseMode.HTML,
        )
        return True

    raw = update.message.text or update.message.caption or ""
    clean = _norm_auto_text(raw)
    g_data = get_group_data(db, group_id)

    # Management keyboard actions.
    if clean in {_norm_auto_text("❌ لغو"), _norm_auto_text("لغو")}:
        _clear_flow(db, user.id)
        await update.message.reply_text(
            f'<b>{_ae("done", "👑")} سیستم افزودن پاسخ‌ها لغو گردید و به منوی قبل بازگشتید.</b>',
            reply_markup=_auto_main_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        # A fresh menu state is intentional: the user remains inside management.
        _set_flow(db, user.id, {"chat_id": group_id, "step": "menu", **({"panel_message_id": int(flow.get("panel_message_id"))} if flow.get("panel_message_id") else {})})
        return True

    if clean in {_norm_auto_text("⛔ لغو"), _norm_auto_text("لغو")}:
        _clear_flow(db, user.id)
        await update.message.reply_text(
            f'<b>{_ae("done", "👑")} سیستم افزودن پاسخ‌ها لغو گردید و به منوی قبل بازگشتید.</b>',
            reply_markup=_auto_main_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        _set_flow(db, user.id, {"chat_id": group_id, "step": "menu", **({"panel_message_id": int(flow.get("panel_message_id"))} if flow.get("panel_message_id") else {})})
        return True

    if clean in {_norm_auto_text("🎖️ پایان دادن"), _norm_auto_text("پایان دادن")}:
        _clear_flow(db, user.id)
        await update.message.reply_text(
            f'<b>{_ae("done", "🐱")} تمام!</b>\n'
            f'<b>- مدیریت سیستم پاسخ‌گویی به اتمام رسید.\nتمامی تنظیمات ثبت و اجرا خواهد شد.</b>',
            reply_markup=ReplyKeyboardRemove(),
            parse_mode=ParseMode.HTML,
        )
        return True

    if clean in {_norm_auto_text("📝 مشاهده لیست پاسخ"), _norm_auto_text("مشاهده لیست پاسخ")}:
        await update.message.reply_text(
            _auto_list_text(g_data),
            reply_markup=_auto_main_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        return True

    if clean in {_norm_auto_text("❌ حذف پاسخ"), _norm_auto_text("حذف پاسخ")}:
        if not _group_responses(g_data):
            await update.message.reply_text(
                f'<b>{_ae("warning", "⚠️")} هنوز هیچ پاسخ خودکاری برای این گروه ثبت نشده است.</b>',
                reply_markup=_auto_main_keyboard(),
                parse_mode=ParseMode.HTML,
            )
            return True
        _set_flow(db, user.id, {"chat_id": group_id, "step": "delete", **({"panel_message_id": int(flow.get("panel_message_id"))} if flow.get("panel_message_id") else {})})
        await update.message.reply_text(
            f'<b>{_ae("plane", "✈️")} برای حذف یکی از پاسخ‌ها، آن را از لیست ارسال کنید.</b>',
            reply_markup=_auto_delete_keyboard(g_data),
            parse_mode=ParseMode.HTML,
        )
        return True

    if clean in {_norm_auto_text("➕ افزودن پاسخ"), _norm_auto_text("افزودن پاسخ")}:
        _set_flow(db, user.id, {"chat_id": group_id, "step": "access", **({"panel_message_id": int(flow.get("panel_message_id"))} if flow.get("panel_message_id") else {})})
        await update.message.reply_text(
            f'<b>{_ae("stage1", "👨‍🚀")} ابتدا مرحله اول را مشخص کنید:</b>\n\n'
            f'<b>{_ae("num1", "1⃣")} - ربات به همه کاربران پاسخ دهد.</b>\n'
            f'<b>{_ae("num2", "2⃣")}- ربات فقط به مقام داران پاسخ دهد.</b>\n'
            f'<b>{_ae("num3", "3⃣")}- ربات فقط به مالکان پاسخ دهد.</b>',
            reply_markup=_auto_stage1_keyboard(group_id),
            parse_mode=ParseMode.HTML,
        )
        return True

    step = flow.get("step")

    if step == "access":
        access_map = {
            _norm_auto_text("🟢 همه کاربران"): "all",
            _norm_auto_text("همه کاربران"): "all",
            _norm_auto_text("🔴 کاربران مقام دار"): "manager",
            _norm_auto_text("کاربران مقام دار"): "manager",
            _norm_auto_text("👑 مقام مالک"): "owner",
            _norm_auto_text("مقام مالک"): "owner",
        }
        access = access_map.get(clean)
        if not access:
            # Do not treat the management controls or bot commands as keywords.
            if clean in {"راهنما", "help", "/help", "هلپ", "گودی راهنما"}:
                _clear_flow(db, user.id)
                return False
            await update.message.reply_text(
                f'<b>{_ae("stage1", "👨‍🚀")} ابتدا یکی از سه سطح دسترسی را انتخاب کنید.</b>',
                reply_markup=_auto_stage1_keyboard(group_id),
                parse_mode=ParseMode.HTML,
            )
            return True

        _set_flow(db, user.id, {"chat_id": group_id, "step": "trigger", "access": access, **({"panel_message_id": int(flow.get("panel_message_id"))} if flow.get("panel_message_id") else {})})
        await update.message.reply_text(
            f'<b>{_ae("stage2", "☕️")} مرحله دوم!</b>\n'
            '<b>کلمه یا جمله‌ای که میخواهید گودی به آن پاسخ دهد را ارسال کنید.</b>',
            reply_markup=ReplyKeyboardRemove(),
            parse_mode=ParseMode.HTML,
        )
        return True

    if step == "trigger":
        # A plain management/help command must cancel the flow and be processed
        # by the normal bot command system instead of becoming a trigger.
        if clean in {"راهنما", "help", "/help", "هلپ", "گودی راهنما", "گودی معرفی کن", "چیا بلدی؟", "چیا بلدی"}:
            _clear_flow(db, user.id)
            return False
        if not clean:
            await update.message.reply_text(
                f'<b>{_ae("stage2", "☕️")} لطفاً کلمه یا جمله را ارسال کنید.</b>',
                parse_mode=ParseMode.HTML,
            )
            return True

        trigger = raw.strip()
        if trigger.startswith("/"):
            _clear_flow(db, user.id)
            return False

        # A trigger may not be one of the automatic UI labels.
        if clean in {
            _norm_auto_text("➕ افزودن پاسخ"),
            _norm_auto_text("❌ حذف پاسخ"),
            _norm_auto_text("🎖️ پایان دادن"),
            _norm_auto_text("📝 مشاهده لیست پاسخ"),
        }:
            await update.message.reply_text(
                f'<b>{_ae("stage2", "☕️")} این گزینه برای مدیریت سیستم است؛ کلمه یا جمله‌ی موردنظر را ارسال کنید.</b>',
                parse_mode=ParseMode.HTML,
            )
            return True

        flow["step"] = "response"
        flow["trigger"] = trigger
        _set_flow(db, user.id, flow)
        await update.message.reply_text(
            f'<b>{_ae("stage3", "📝")} مرحله سوم:\nپاسخی را بفرستید که میخواهید وقتی گودی کلمه {html.escape(trigger)} را دید ارسال کند.</b>',
            parse_mode=ParseMode.HTML,
        )
        return True

    if step == "response":
        if clean in {"راهنما", "help", "/help", "هلپ", "گودی راهنما", "گودی معرفی کن", "چیا بلدی؟", "چیا بلدی"}:
            _clear_flow(db, user.id)
            return False
        payload = extract_media_payload(update.message)
        if not payload:
            await update.message.reply_text(
                f'<b>{_ae("stage3", "📝")} لطفاً پاسخ را به صورت متن یا رسانه ارسال کنید.</b>',
                parse_mode=ParseMode.HTML,
            )
            return True

        trigger = flow.get("trigger", "").strip()
        access = flow.get("access", "all")
        if not trigger:
            _clear_flow(db, user.id)
            return False

        items = _group_responses(g_data)
        norm_trigger = _norm_auto_text(trigger)
        # One trigger is one rule. Re-adding it updates the response and access.
        existing = next((x for x in items if _norm_auto_text(x.get("trigger", "")) == norm_trigger), None)
        rule = {
            "trigger": trigger,
            "trigger_norm": norm_trigger,
            "response": payload,
            "access": access,
            "created_by": int(user.id),
            "updated_at": datetime.now().timestamp(),
        }
        if existing is not None:
            existing.clear()
            existing.update(rule)
        else:
            items.append(rule)

        mark_db_dirty()
        save_db(force=True)
        panel_flow = dict(flow)
        _clear_flow(db, user.id)
        await _sync_group_auto_panel(context, panel_flow, g_data)

        await update.message.reply_text(
            f'<b>{_ae("success", "✅")} پاسخ‌دهی خودکار کلمه‌ی {html.escape(trigger)} شما فعال شد.</b>\n'
            f'<b>هر زمان ربات کلمه‌ی {html.escape(trigger)} را ببیند پاسخ تنظیم‌شده را ارسال می‌کند.</b>',
            parse_mode=ParseMode.HTML,
        )
        _set_flow(db, user.id, {"chat_id": group_id, "step": "menu", **({"panel_message_id": int(flow.get("panel_message_id"))} if flow.get("panel_message_id") else {})})
        await update.message.reply_text(
            f'<b>{_ae("info", "👆")} دستورات بعدی خود را انجام دهید یا از طریق دکمه پایان دادن سیستم را ببندید.</b>',
            reply_markup=_auto_main_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        return True

    if step == "delete":
        if clean in {_norm_auto_text("❌ لغو"), _norm_auto_text("لغو")}:
            _set_flow(db, user.id, {"chat_id": group_id, "step": "menu", **({"panel_message_id": int(flow.get("panel_message_id"))} if flow.get("panel_message_id") else {})})
            await update.message.reply_text(
                f'<b>{_ae("back", "⬅️")} به منوی مدیریت پاسخ‌ها بازگشتید.</b>',
                reply_markup=_auto_main_keyboard(),
                parse_mode=ParseMode.HTML,
            )
            return True

        selected = raw.strip()
        if selected.startswith("❗️"):
            selected = selected.removeprefix("❗️").strip()
        norm_selected = _norm_auto_text(selected)
        items = _group_responses(g_data)
        found = next((x for x in items if _norm_auto_text(x.get("trigger", "")) == norm_selected), None)
        if found is None:
            await update.message.reply_text(
                f'<b>{_ae("warning", "⚠️")} کلمه‌ی بعدی را حذف کنید یا با دکمه‌ی لغو به منوی قبلی برگردید.</b>',
                reply_markup=_auto_delete_keyboard(g_data),
                parse_mode=ParseMode.HTML,
            )
            return True

        removed_trigger = found.get("trigger", selected)
        panel_flow = dict(flow)
        items.remove(found)
        mark_db_dirty()
        save_db(force=True)
        await _sync_group_auto_panel(context, panel_flow, g_data)

        if items:
            await update.message.reply_text(
                f'<b>{_ae("removed", "⚡️")} کلمه‌ی {html.escape(removed_trigger)} با موفقیت از لیست پاسخ‌دهی حذف گردید.</b>',
                parse_mode=ParseMode.HTML,
            )
            await update.message.reply_text(
                f'<b>{_ae("warning", "⚠️")} کلمه‌ی بعدی را حذف کنید یا با دکمه‌ی لغو به منوی قبلی برگردید.</b>',
                reply_markup=_auto_delete_keyboard(g_data),
                parse_mode=ParseMode.HTML,
            )
        else:
            _set_flow(db, user.id, {"chat_id": group_id, "step": "menu", **({"panel_message_id": int(flow.get("panel_message_id"))} if flow.get("panel_message_id") else {})})
            await update.message.reply_text(
                f'<b>{_ae("removed", "⚡️")} کلمه‌ی {html.escape(removed_trigger)} با موفقیت از لیست پاسخ‌دهی حذف گردید.</b>',
                reply_markup=_auto_main_keyboard(),
                parse_mode=ParseMode.HTML,
            )
        return True

    return True


def _auto_list_text(g_data: dict) -> str:
    items = _group_responses(g_data)
    lines = [
        f'<b>{_ae("list_clock", "⏰")} لیست پاسخ خودکار :</b>',
        "",
        f'<b>{_ae("list_count", "😀")} تعداد کل پاسخ‌ها: {len(items)}</b>',
        "",
    ]
    for item in items:
        trigger = html.escape(str(item.get("trigger", "")))
        preview = _payload_preview(item.get("response", {}) or {})
        lines.append(f'<b>{_ae("bullet", "💥")} {trigger} —&gt; {preview}</b>')
    if not items:
        lines.append('<b>هنوز پاسخی برای این گروه ثبت نشده است.</b>')
    return "\n".join(lines)


def _auto_group_panel_list_text(g_data: dict) -> str:
    items = _group_responses(g_data)
    lines = [
        f'<b>{_ae("success", "✅")} لیست پاسخ‌های خودکار:</b>',
        f'<b>- {_ae("list_count", "🔴")} تعداد کل پاسخ‌های ذخیره شده: {len(items)}</b>',
        "",
    ]
    for item in items:
        trigger = html.escape(str(item.get("trigger", "")))
        preview = _payload_preview(item.get("response", {}) or {})
        lines.append(f'<b>{_ae("bullet", "💥")} {trigger} —&gt; {preview}</b>')
    return "\n".join(lines)


def _payload_preview(payload: dict) -> str:
    kind = payload.get("type")
    if kind == "text":
        text = re.sub(r"\s+", " ", str(payload.get("text", ""))).strip()
        text = re.sub(r"<[^>]+>", "", text)
        return html.escape(text[:120] or "رسانه")
    labels = {
        "photo": "عکس",
        "animation": "گیف",
        "video": "ویدیو",
        "voice": "ویس",
        "audio": "صدا",
        "document": "فایل",
        "video_note": "ویدیو نوت",
        "sticker": "استیکر",
        "contact": "مخاطب",
        "location": "موقعیت",
        "venue": "مکان",
    }
    return html.escape(labels.get(kind, "رسانه"))


async def handle_auto_response_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """Run group-only auto-response commands and trigger matching.

    True means this feature handled the update and the generic message handler
    must stop. False means the rest of the bot should process it normally.
    """
    if not update.message or not update.effective_chat:
        return False
    if update.effective_chat.type not in ("group", "supergroup"):
        return False
    if not update.effective_user or update.effective_user.is_bot:
        return False

    db = load_db()
    chat_id = int(update.effective_chat.id)
    user_id = int(update.effective_user.id)
    raw = update.message.text or update.message.caption or ""
    clean = _norm_auto_text(raw)

    # Explicit group commands belong to this feature and must never be treated
    # as triggers.
    list_commands = {"لیست پاسخ", "لیست پاسخ‌ها", "گودی پاسخ ها"}
    cleanup_commands = {"پاکسازی لیست پاسخ", "گودی حذف لیست پاسخ", "لیست پاسخ حذف"}

    if clean in {_norm_auto_text(x) for x in list_commands}:
        if not await is_configured_group_manager(context, chat_id, user_id):
            await update.message.reply_text(
                f'<b>{_ae("cancel", "❌")} فقط مدیران گروه می‌توانند لیست پاسخ‌ها را مشاهده کنند.</b>',
                parse_mode=ParseMode.HTML,
            )
            return True
        await update.message.reply_text(_auto_list_text(get_group_data(db, chat_id)), parse_mode=ParseMode.HTML)
        return True

    if clean in {_norm_auto_text(x) for x in cleanup_commands}:
        if not await is_configured_group_manager(context, chat_id, user_id):
            await update.message.reply_text(
                f'<b>{_ae("cancel", "❌")} فقط مدیران گروه می‌توانند این عملیات را انجام دهند.</b>',
                parse_mode=ParseMode.HTML,
            )
            return True
        if not _group_responses(get_group_data(db, chat_id)):
            await update.message.reply_text(
                f'<b>{_ae("warning", "⚠️")} لیست پاسخ‌های خودکار این گروه از قبل خالی است.</b>',
                parse_mode=ParseMode.HTML,
            )
            return True

        buttons = [[
            InlineKeyboardButton("بله", callback_data=f"auto_cleanup:{chat_id}:yes", style="success", icon_custom_emoji_id=AUTO_EMOJI["success"]),
            InlineKeyboardButton("خیر", callback_data=f"auto_cleanup:{chat_id}:no", style="danger", icon_custom_emoji_id=AUTO_EMOJI["cancel"]),
        ]]
        await update.message.reply_text(
            f'<b>{_ae("success", "✔️")} آیا از حذف کامل لیست پاسخ‌های خودکار این گروه مطمئن هستید؟</b>',
            reply_markup=InlineKeyboardMarkup(buttons),
            parse_mode=ParseMode.HTML,
        )
        return True

    # Trigger matching is group-specific and runs only after explicit commands.
    g_data = get_group_data(db, chat_id)
    items = _group_responses(g_data)
    if not items:
        return False

    message_norm = _norm_auto_text(raw)
    if not message_norm:
        return False

    matched = []
    for item in items:
        trigger_norm = item.get("trigger_norm") or _norm_auto_text(item.get("trigger", ""))
        if not trigger_norm:
            continue
        if trigger_norm in message_norm and _role_allowed(g_data, user_id, item.get("access", "all")):
            matched.append(item)

    if not matched:
        return False

    # Reply once for every matching rule, preserving the order in which rules
    # were configured. A single rule is never sent twice for one message.
    for item in matched:
        payload = item.get("response")
        if payload:
            await send_media_payload(
                context.bot,
                chat_id,
                payload,
                reply_to_message_id=update.message.message_id,
            )
    return True


async def auto_response_access_callback(query, context, chat_id: int, access: str):
    db = load_db()
    user_id = query.from_user.id
    if not await is_configured_group_manager(context, chat_id, user_id):
        await query.answer(" دسترسی غیرمجاز!", show_alert=True)
        return

    flow = _flow(db, user_id) or {}
    if _flow_group(flow) != int(chat_id) or flow.get("step") != "access":
        await query.answer(" این مرحله منقضی شده است.", show_alert=True)
        return

    if access == "cancel":
        panel_flow = dict(flow)
        _set_flow(db, user_id, {
            "chat_id": int(chat_id),
            "step": "menu",
            **({"panel_message_id": int(panel_flow["panel_message_id"])} if panel_flow.get("panel_message_id") else {}),
        })
        await query.message.edit_text(
            f'<b>{_ae("done", "👑")} سیستم افزودن پاسخ‌ها لغو گردید و به منوی قبل بازگشتید.</b>',
            reply_markup=None,
            parse_mode=ParseMode.HTML,
        )
        await query.message.reply_text(
            f'<b>{_ae("menu", "☠️")} گزینه‌ی موردنظر را جهت مدیریت سیستم پاسخ‌دهی مشخص کنید.</b>',
            reply_markup=_auto_main_keyboard(),
            parse_mode=ParseMode.HTML,
        )
        await query.answer()
        return

    if access not in {"all", "manager", "owner"}:
        await query.answer(" گزینه نامعتبر است.", show_alert=True)
        return

    flow["access"] = access
    flow["step"] = "trigger"
    _set_flow(db, user_id, flow)
    await query.message.edit_text(
        f'<b>{_ae("stage2", "☕️")} مرحله دوم!</b>\n'
        '<b>کلمه یا جمله‌ای که میخواهید گودی به آن پاسخ دهد را ارسال کنید.</b>',
        reply_markup=None,
        parse_mode=ParseMode.HTML,
    )
    await query.answer()


async def auto_response_cleanup_callback(query, context, chat_id: int, confirm: bool):
    db = load_db()
    user_id = query.from_user.id
    if not await is_configured_group_manager(context, chat_id, user_id):
        await query.answer(" دسترسی غیرمجاز!", show_alert=True)
        return

    if confirm:
        g_data = get_group_data(db, chat_id)
        g_data[AUTO_GROUP_KEY] = []
        mark_db_dirty()
        save_db(force=True)
        active_flow = _flow(db, user_id) or {}
        if _flow_group(active_flow) == int(chat_id):
            await _sync_group_auto_panel(context, active_flow, g_data)
        text = f'<b>{_ae("success", "✅")} لیست پاسخ‌های خودکار با موفقیت پاکسازی شد.</b>'
    else:
        text = f'<b>{_ae("back", "⬅️")} عملیات پاکسازی لیست پاسخ‌ها لغو شد.</b>'

    await query.message.edit_text(text, reply_markup=None, parse_mode=ParseMode.HTML)
    await query.answer()
