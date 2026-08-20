# GoodiBot modular feature module
from core import *

async def resolve_group_target(update, context, db, chat_id: int, target_text: str = "") -> tuple[int | None, str, str]:
    msg = update.message
    g_data = get_group_data(db, chat_id)
    g_data.setdefault("moderation_message_targets", {})

    # Reply to a normal user's message.
    if msg and msg.reply_to_message:
        u = msg.reply_to_message.from_user
        if u and not u.is_bot:
            return u.id, u.full_name or "کاربر", u.username or ""

        # Reply to one of the bot's moderation result messages. We store the
        # target user on the result message so commands such as «حذف سکوت»
        # can operate directly by replying to «کاربر ... سکوت شد».
        if u and u.is_bot:
            moderation_map = g_data.get("moderation_message_targets", {}) or {}
            mapped = moderation_map.get(str(msg.reply_to_message.message_id))
            if mapped:
                info = db.get("members", {}).get(str(mapped), {}) or {}
                return int(mapped), info.get("fullname", "کاربر"), info.get("username", "")

        replied_text = (msg.reply_to_message.text or msg.reply_to_message.caption or "").strip()
        if replied_text and not target_text:
            target_text = replied_text

    target = (target_text or "").strip().split()[0] if target_text else ""
    target = fa_to_en_digits(target.lstrip("@"))
    if target.isdigit():
        uid = int(target)
        try:
            m = await cached_chat_member(context, chat_id, uid)
            return m.user.id, m.user.full_name or "کاربر", m.user.username or ""
        except Exception:
            info = db.get("members", {}).get(str(uid))
            if info: return uid, info.get("fullname", "کاربر"), info.get("username", "")
            return None, "", ""

    if re.fullmatch(r"[A-Za-z0-9_]{5,32}", target):
        uname = target.lower()
        candidates = []
        candidates.extend((db.get("members", {}) or {}).items())
        recent = db.get("recent_active_users", {}).get(str(chat_id), []) or []
        if isinstance(recent, dict):
            recent = list(recent.items())
        for uid, info in recent:
            if isinstance(info, dict): candidates.append((uid, info))
        mgmt = g_data.get("management", {}) or {}
        for role in ("owners", "admins", "special", "exempt"):
            for uid in mgmt.get(role, []) or []:
                info = db.get("members", {}).get(str(uid), {}) or {}
                candidates.append((str(uid), info))
        for store_name in ("warnings", "muted_users", "banned_users"):
            for uid, info in (g_data.get(store_name, {}) or {}).items():
                candidates.append((uid, info or {}))
        seen = set()
        for uid, info in candidates:
            if str(uid) in seen: continue
            seen.add(str(uid))
            if str(info.get("username", "")).lstrip("@").lower() == uname:
                try:
                    m = await cached_chat_member(context, chat_id, int(uid))
                    return m.user.id, m.user.full_name or info.get("fullname", "کاربر"), m.user.username or uname
                except Exception:
                    return int(uid), info.get("fullname", "کاربر"), info.get("username", uname)
    return None, "", ""

def role_label(role: str) -> str:
    return {"owners": "مالک", "admins": "مدیر", "special": "ویژه", "exempt": "معاف"}.get(role, role)

async def configure_group_management(update, context, db, chat_id: int):
    async def _reply(text, **kwargs):
        if getattr(update, "message", None):
            return await update.message.reply_text(text, **kwargs)
        return await context.bot.send_message(chat_id=chat_id, text=text, **kwargs)

    try:
        admins = await context.bot.get_chat_administrators(chat_id)
    except Exception:
        await _reply(f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> ربات نتوانست لیست مدیران گروه را دریافت کند.</b>', parse_mode=ParseMode.HTML)
        return
    owner = next((a.user for a in admins if a.status == ChatMemberStatus.OWNER), None)
    if not owner:
        await _reply(f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> مالک اصلی گروه پیدا نشد.</b>', parse_mode=ParseMode.HTML)
        return
    group_admins = [a.user for a in admins if a.status == ChatMemberStatus.ADMINISTRATOR and not a.user.is_bot]
    g = get_group_data(db, chat_id)
    g["management"] = {"configured": True, "primary_owner_id": owner.id, "owners": [owner.id], "admins": [u.id for u in group_admins], "special": g.get("management", {}).get("special", []), "exempt": g.get("management", {}).get("exempt", [])}
    g["title"] = (update.effective_chat.title if update.effective_chat else None) or g.get("title", "")
    mark_db_dirty(); save_db(force=True)

    owner_text = _user_label(owner)
    if group_admins:
        admin_lines = "\n".join(f'<b><tg-emoji emoji-id="{CONFIG_PLUS_EMOJI}">➕</tg-emoji> {_user_label(u)}</b>' for u in group_admins)
    else:
        admin_lines = f'<b><tg-emoji emoji-id="{CONFIG_NO_ADMIN_EMOJI}">⚠️</tg-emoji> ادمینی در گروه یافت نشد.</b>'
    text = (
        f'<b><tg-emoji emoji-id="{CONFIG_GEAR_EMOJI}">⚙️</tg-emoji> پیکربندی با موفقیت انجام شد.</b>\n\n'
        f'<b><tg-emoji emoji-id="{CONFIG_RED_EMOJI}">🔴</tg-emoji> مالک گروه:</b>\n'
        f'<b><tg-emoji emoji-id="{CONFIG_PLUS_EMOJI}">➕</tg-emoji> {owner_text}</b>\n\n'
        f'<b><tg-emoji emoji-id="{CONFIG_RED_EMOJI}">🔴</tg-emoji> ادمین‌های گروه:</b>\n'
        f'{admin_lines}\n\n'
        f'<b><tg-emoji emoji-id="5819051035284479206">🚨</tg-emoji> درصورت وقوع هرگونه مشکل به کانال پشتیبانی ربات مراجعه کنید:</b>\n'
        f'<b><tg-emoji emoji-id="6006061397480315684">💎</tg-emoji> @GoodiSupport</b>'
    )
    await _reply(text, parse_mode=ParseMode.HTML)

async def command_admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    if not update.effective_chat or update.effective_chat.type not in ["group", "supergroup"]:
        return

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if not await is_configured_group_manager(context, chat_id, user_id):
        await update.message.reply_text(
            f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> شما دسترسی مدیریت این گروه را ندارید.</b>',
            parse_mode=ParseMode.HTML
        )
        return

    db = load_db()
    g_data = get_group_data(db, chat_id)
    text, keyboard = build_group_admin_panel_content(chat_id, g_data.get("title") or "")
    sent = await update.message.reply_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    register_group_panel_session(db, chat_id, sent.message_id, user_id)
