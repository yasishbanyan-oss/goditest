# GoodiBot modular feature module
from core import *


def _resolve_whisper_username_from_db(db: dict, username: str) -> tuple[int | None, str, str]:
    """Resolve a Telegram username to a numeric user ID from users the bot knows.

    Bot API get_chat(@username) is not a reliable user lookup (it is mainly for
    chats/channels). We therefore resolve against the bot's persistent member
    index and recent/group management indexes, then persist only the numeric ID.
    """
    uname = (username or "").lstrip("@").strip().lower()
    if not uname:
        return None, "", ""

    candidates = []
    for uid, info in (db.get("members", {}) or {}).items():
        candidates.append((uid, info or {}))
    for _, recent in (db.get("recent_active_users", {}) or {}).items():
        if isinstance(recent, dict):
            recent = list(recent.items())
        for uid, info in recent or []:
            candidates.append((uid, info or {}))
    for _, g_data in (db.get("groups", {}) or {}).items():
        g_data = g_data or {}
        for role in ("owners", "admins", "special", "exempt"):
            for uid in (g_data.get("management", {}) or {}).get(role, []) or []:
                info = (db.get("members", {}) or {}).get(str(uid), {}) or {}
                candidates.append((uid, info))
        for store_name in ("warnings", "muted_users", "banned_users"):
            for uid, info in (g_data.get(store_name, {}) or {}).items():
                candidates.append((uid, info or {}))

    seen = set()
    for uid, info in candidates:
        uid_key = str(uid)
        if uid_key in seen:
            continue
        seen.add(uid_key)
        stored_uname = str(info.get("username", "") or "").lstrip("@").lower()
        if stored_uname == uname:
            try:
                return int(uid), info.get("fullname", "کاربر") or "کاربر", info.get("username", "") or uname
            except (TypeError, ValueError):
                continue
    return None, "", ""

async def handle_inline_whisper(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query_obj = update.inline_query
    logger.info(f"Received Inline Query from {query_obj.from_user.id}: '{query_obj.query}'")
    
    query = query_obj.query.strip()
    user = query_obj.from_user
       
    if not query:
        help_text = (
            '<tg-emoji emoji-id="6084584811379299518">🔗</tg-emoji> <b>آموزش نجوا در ربات گودی!</b>\n\n'
            'پیام خود را جلوی یوزرنیم ربات نوشته و در انتهای پیام خود یوزرنیم یا آیدی عددی فرد دریافت کننده را وارد کنید.'
        )
        results = [
            InlineQueryResultArticle(
                id="whisper_help",
                title=" آموزش نجوا در ربات گودی!",
                description="- روی این دکمه کلیک کن و یاد بگیر چجوری نجوا بفرستی.",
                input_message_content=InputTextMessageContent(help_text, parse_mode=ParseMode.HTML)
            )
        ]
        await update.inline_query.answer(results, cache_time=0, is_personal=True)
        return

    parts = query.split()
    if len(parts) < 2:
        results = [
            InlineQueryResultArticle(
                id="whisper_error",
                title=" فرمت نامعتبر نجوا",
                description="متن پیام + یوزرنیم یا آیدی عددی گیرنده",
                input_message_content=InputTextMessageContent("<b> فرمت نجوا اشتباه است. لطفاً گیرنده را در انتهای پیام مشخص کنید.</b>", parse_mode=ParseMode.HTML)
            )
        ]
        await update.inline_query.answer(results, cache_time=0, is_personal=True)
        return

    target = parts[-1]
    message_text = " ".join(parts[:-1])

    if len(message_text) > 500:
        results = [
            InlineQueryResultArticle(
                id="whisper_too_long",
                title=" متن پیام خیلی طولانی است",
                description="حداکثر طول مجاز ۵۰۰ کاراکتر است.",
                input_message_content=InputTextMessageContent("<b> متن نجوا بیش از حد طولانی است.</b>", parse_mode=ParseMode.HTML)
            )
        ]
        await update.inline_query.answer(results, cache_time=0, is_personal=True)
        return

    target_uid = None
    target_uname = None

    clean_target = target.strip().lstrip("@").strip().rstrip(".,!?؛؟")
    clean_target = fa_to_en_digits(clean_target)
    if clean_target.isdigit():
        target_uid = int(clean_target)
        if target_uid <= 0:
            target_uid = None
    elif re.fullmatch(r"[A-Za-z0-9_]{5,32}", clean_target):
        target_uname = clean_target.lower()
        # Resolve the username to a numeric ID from the bot's persistent user
        # index. The username is only an input alias; the whisper itself is
        # always addressed/read by target_uid.
        db = load_db()
        target_uid, target_name, resolved_uname = _resolve_whisper_username_from_db(db, target_uname)
        if target_uid:
            target_uname = resolved_uname or target_uname
        else:
            results = [
                InlineQueryResultArticle(
                    id="whisper_bad_target",
                    title=" گیرنده یافت نشد!!",
                    description="یوزرنیم را دوباره بررسی کنید یا ابتدا کاربر در گروه با ربات تعامل داشته باشد.",
                    input_message_content=InputTextMessageContent(
                        '<tg-emoji emoji-id="5819154526816444042">❌</tg-emoji> <b>گیرنده یافت نشد!!</b>\n'
                        '<b>- این یوزرنیم هنوز در اطلاعات ربات ثبت نشده است.</b>',
                        parse_mode=ParseMode.HTML
                    )
                )
            ]
            await update.inline_query.answer(results, cache_time=0, is_personal=True)
            return
    else:
        results = [
            InlineQueryResultArticle(
                id="whisper_bad_target",
                title=" گیرنده یافت نشد!!",
                description="یوزرنیم یا آیدی عددی دریافت کننده را دوباره بررسی کنید.",
                input_message_content=InputTextMessageContent(
                    '<tg-emoji emoji-id="5819154526816444042">❌</tg-emoji> <b>گیرنده یافت نشد!!</b>\n'
                    '<b>- یوزرنیم یا آیدی عددی دریافت کننده را دوباره بررسی کنید.</b>',
                    parse_mode=ParseMode.HTML
                )
            )
        ]
        await update.inline_query.answer(results, cache_time=0, is_personal=True)
        return

    if target_uid and target_uid == user.id:
        results = [
            InlineQueryResultArticle(
                id="whisper_self",
                title=" ارسال نجوا به خودتان مجاز نیست",
                description="نمی‌توانید برای خودتان نجوا بفرستید.",
                input_message_content=InputTextMessageContent("<b> نمی‌توانید به خودتان نجوا بفرستید!</b>", parse_mode=ParseMode.HTML)
            )
        ]
        await update.inline_query.answer(results, cache_time=0, is_personal=True)
        return

    import uuid
    w_id = uuid.uuid4().hex[:12]

    db = load_db()
    whispers = db.setdefault("whispers", {})
    whispers[w_id] = {
        "whisper_id": w_id,
        "sender_id": user.id,
        "sender_username": user.username or "",
        "sender_name": user.full_name or "کاربر",
        "target_uid": target_uid,
        "target_username": target_uname,
        "text": message_text,
        "created_at": datetime.now().timestamp(),
        "read": False,
        "reader_id": None,
        "reader_username": None,
        "reader_name": None,
        "deleted": False
    }
    mark_db_dirty()
    save_db(force=True)

    display_target = f"@{target_uname}" if target_uname else str(target_uid)
    result_title = f" ارسال پیام نجوا به {display_target}"
    result_html = (
        f'<tg-emoji emoji-id="6057891250332241964">📱</tg-emoji> '
        f'<b>شما درحال ارسال پیام نجوا به کاربر {html.escape(display_target)} می‌باشید.</b>\n'
        f'<b>- جهت تایید روی این دکمه کلیک کنید! '
        f'<tg-emoji emoji-id="6084779072750097974">✅</tg-emoji></b>'
    )

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                " تایید ارسال",
                callback_data=f"wh_confirm:{w_id}",
                style="success",
                icon_custom_emoji_id="6084779072750097974"
            )
        ]
    ])

    results = [
        InlineQueryResultArticle(
            id=w_id,
            title=result_title,
            description=message_text[:50],
            input_message_content=InputTextMessageContent(result_html, parse_mode=ParseMode.HTML),
            reply_markup=keyboard
        )
    ]
    await update.inline_query.answer(results, cache_time=0, is_personal=True)
