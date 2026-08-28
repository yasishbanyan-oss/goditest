# GoodiBot modular feature module
from core import *

def check_and_set_welcome_duplicate(db: dict, chat_id: int, user_id: int) -> bool:
    g_data = get_group_data(db, chat_id)
    history = g_data.setdefault("recent_welcomed_users", {})
    now_ts = datetime.now().timestamp()
    uid_str = str(user_id)

    for k in list(history.keys()):
        if now_ts - history[k] > 120:
            del history[k]

    if uid_str in history and (now_ts - history[uid_str]) < 45:
        return True

    history[uid_str] = now_ts
    if len(history) > 20:
        oldest = min(history.keys(), key=lambda k: history[k])
        del history[oldest]

    mark_db_dirty()
    save_db()
    return False

async def send_welcome_to_member(
    context: ContextTypes.DEFAULT_TYPE,
    chat,
    user,
    reply_to_message_id: int | None = None,
    check_duplicate: bool = True,
):
    try:
        if not user or user.is_bot:
            return None

        db = load_db()
        g_data = get_group_data(db, chat.id)
        welcome_settings = g_data.get("welcome", {}) or {}

        if not welcome_settings.get("enabled", False):
            return None

        if check_duplicate and check_and_set_welcome_duplicate(db, chat.id, user.id):
            return None

        day_fa, time_str = get_persian_date_info()
        chat_title = html.escape(chat.title or "گروه")
        user_mention = get_user_mention(user.id, user.full_name or "کاربر")

        if not welcome_settings.get("custom", False):
            default_text = f"سلام {user_mention} ، به گروه {chat_title} خوش آمدید!\nساعت {time_str} روز {day_fa}!"
            sent = await context.bot.send_message(
                chat_id=chat.id,
                text=default_text,
                parse_mode=ParseMode.HTML,
                reply_to_message_id=reply_to_message_id,
            )
        else:
            payload = welcome_settings.get("payload")
            if not payload:
                return None
            raw_text = payload.get("text") or payload.get("caption") or ""
            formatted_text = (
                raw_text.replace("USERNAME", user_mention)
                .replace("{name}", user_mention)
                .replace("XXXX", chat_title)
                .replace("TIME", time_str)
                .replace("DAY", day_fa)
            )
            temp_payload = dict(payload)
            if "text" in temp_payload:
                temp_payload["text"] = formatted_text
            if "caption" in temp_payload:
                temp_payload["caption"] = formatted_text
            sent = await send_media_payload(
                context.bot,
                chat.id,
                temp_payload,
                reply_to_message_id=reply_to_message_id,
                return_message=True,
            )

        if sent and (welcome_settings.get("auto_delete") or {}).get("enabled") and context.job_queue:
            seconds = max(10, min(86400, int((welcome_settings.get("auto_delete") or {}).get("seconds", 90))))
            job_name = f"welcome_auto_delete:{int(chat.id)}:{int(sent.message_id)}"
            for job in context.job_queue.get_jobs_by_name(job_name):
                job.schedule_removal()
            context.job_queue.run_once(
                welcome_auto_delete_job,
                when=seconds,
                chat_id=int(chat.id),
                name=job_name,
                data={"chat_id": int(chat.id), "message_id": int(sent.message_id)},
            )
        return sent

    except Exception as e:
        logger.error(f"Error dispatching welcome in chat: {e}", exc_info=True)
        return None


async def welcome_auto_delete_job(context: ContextTypes.DEFAULT_TYPE):
    data = context.job.data or {}
    try:
        await context.bot.delete_message(chat_id=int(data["chat_id"]), message_id=int(data["message_id"]))
    except Exception:
        pass

async def handle_new_chat_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.new_chat_members:
        return
    chat = update.effective_chat
    db = load_db()
    w = (get_group_data(db, chat.id).get("welcome", {}) or {})
    if w.get("audience", "all") == "link":
        return
    reply_id = update.message.message_id
    for member in update.message.new_chat_members:
        if not member.is_bot:
            await send_welcome_to_member(context, chat, member, reply_to_message_id=reply_id)

async def handle_chat_member_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.chat_member
    if not result:
        return

    chat = result.chat
    if not chat or chat.type not in ["group", "supergroup"]:
        return

    user = result.new_chat_member.user
    if not user or user.is_bot:
        return

    # Keep a private per-group history for the "بررسی کاربر" panel.
    await track_group_user_status(update, context)

    old_status = result.old_chat_member.status
    new_status = result.new_chat_member.status

    was_member = old_status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    is_now_member = new_status in [ChatMemberStatus.MEMBER, ChatMemberStatus.RESTRICTED]

    if not was_member and is_now_member:
        if new_status == ChatMemberStatus.RESTRICTED:
            if not getattr(result.new_chat_member, "is_member", True):
                return
        db = load_db()
        w = (get_group_data(db, chat.id).get("welcome", {}) or {})
        audience = w.get("audience", "all")
        invite_link = getattr(result, "invite_link", None)
        via_chat_folder = bool(getattr(result, "via_chat_folder_invite_link", False))
        if audience == "link" and invite_link is None and not via_chat_folder:
            return
        await send_welcome_to_member(context, chat, user, reply_to_message_id=None)

async def handle_welcome_text_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    if not msg or not msg.text:
        return

    chat = update.effective_chat
    if not chat or chat.type not in ["group", "supergroup"]:
        return

    user = update.effective_user
    if not user:
        return

    raw_text = msg.text.strip()
    norm_cmd = raw_text.replace("\u200c", " ").strip().lower()
    norm_cmd = re.sub(r"\s+", " ", norm_cmd)

    match = WELCOME_CMD_PATTERN.match(norm_cmd)
    if not match:
        return

    chat_id = chat.id
    user_id = user.id

    if not await is_admin_or_owner(context, chat_id, user_id):
        return

    action_term = match.group(2).lower()
    turn_on = action_term in ["روشن", "on"]

    db = load_db()
    g_data = get_group_data(db, chat_id)
    w_set = g_data.setdefault("welcome", {"enabled": True, "custom": False})
    was_enabled = bool(w_set.get("enabled", True))

    # اگر وضعیت درخواستی از قبل همان بوده، فقط همان وضعیت را اعلام کن و دوباره ذخیره نکن.
    if was_enabled == turn_on:
        if turn_on:
            reply_html = f'<b>خوش‌آمدگویی از قبل فعال بود.</b> <tg-emoji emoji-id="{CHECK_CUSTOM_EMOJI_ID}">✅</tg-emoji>'
        else:
            reply_html = f'<b>خوش‌آمدگویی از قبل خاموش بود.</b> <tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji>'
        await msg.reply_text(reply_html, parse_mode=ParseMode.HTML)
        raise ApplicationHandlerStop()

    w_set["enabled"] = turn_on

    action_label = "فعال" if turn_on else "غیرفعال"
    log_admin_action(
        db,
        user_id,
        user.full_name or "ادمین",
        chat.title or "گروه",
        chat_id,
        "دستور متنی خوش‌آمدگویی",
        f"وضعیت جدید: {action_label}"
    )
    mark_db_dirty()
    save_db(force=True)

    if turn_on:
        reply_html = f'<b>خوش‌آمدگویی گروه با موفقیت فعال شد!</b> <tg-emoji emoji-id="{CHECK_CUSTOM_EMOJI_ID}">✅</tg-emoji>'
    else:
        reply_html = f'<b>خوش‌آمدگویی گروه با موفقیت غیرفعال شد!</b> <tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji>'

    try:
        await msg.reply_text(reply_html, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Failed to respond to welcome command: {e}")

    raise ApplicationHandlerStop()

async def track_chats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    result = update.my_chat_member
    if not result:
        return

    new_status = result.new_chat_member.status
    chat = result.chat
    db = load_db()
    if new_status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR]:
        g_data = get_group_data(db, chat.id)
        g_data["title"] = chat.title or ""
        if chat.id not in db["active_chats"]:
            db["active_chats"].append(chat.id)
            mark_db_dirty()
            save_db(force=True)

        # First time the bot becomes an administrator, initialize the group
        # management snapshot automatically. Later role changes remain manual.
        if new_status == ChatMemberStatus.ADMINISTRATOR and not (g_data.get("management", {}) or {}).get("configured"):
            try:
                await configure_group_management(update, context, db, chat.id)
            except Exception:
                logger.exception("Automatic first-time group configuration failed | chat_id=%s", chat.id)

        setup_chat_jobs(context.job_queue, [chat.id])

        welcome_msg = (
            "<b>سلام نینیا ، گودی اینجاست...! </b>"
            '<tg-emoji emoji-id="5276251363313996750">😊</tg-emoji>\n\n'
            "<b>شروع کنید به مسخره بازی که حال کنیم! </b>"
            '<tg-emoji emoji-id="5274211661870295868">😌</tg-emoji>'
        )
        try:
            await context.bot.send_message(chat_id=chat.id, text=welcome_msg, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error(f"Failed to send welcome message: {e}")
    elif (
        new_status in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED]
        or (
            getattr(result.old_chat_member, "status", None) == ChatMemberStatus.ADMINISTRATOR
            and new_status == ChatMemberStatus.MEMBER
        )
    ):
        reason = (
            "بن شد"
            if new_status == ChatMemberStatus.BANNED
            else "از گروه حذف/خارج شد"
            if new_status == ChatMemberStatus.LEFT
            else "از مدیریت گروه عزل شد"
        )
        try:
            await send_group_departure_backup(context.bot, db, chat.id, reason)
        except Exception:
            logger.exception("Group departure backup failed | chat_id=%s", chat.id)

        if new_status in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED] and chat.id in db["active_chats"]:
            db["active_chats"].remove(chat.id)
            mark_db_dirty()
            save_db(force=True)
        if new_status in [ChatMemberStatus.LEFT, ChatMemberStatus.BANNED] and context.job_queue:
            for jname in [f"goh_khor_{chat.id}", f"reaction_{chat.id}"]:
                jobs = context.job_queue.get_jobs_by_name(jname)
                for j in jobs:
                    j.schedule_removal()
