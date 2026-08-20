# GoodiBot modular feature module
from core import *


def _looks_like_user_target(text: str) -> bool:
    """Return True only for an actual numeric ID or Telegram-style username."""
    value = (text or "").strip()
    if not value:
        return False
    parts = value.split()
    if len(parts) != 1:
        return False
    token = fa_to_en_digits(parts[0]).lstrip("@")
    return token.isdigit() or bool(re.fullmatch(r"[A-Za-z0-9_]{5,32}", token))


def _looks_like_duration(text: str) -> bool:
    value = fa_to_en_digits((text or "").strip().lower()).replace("‌", " ")
    value = re.sub(r"\s+", " ", value)
    if not value:
        return True
    if value in PERMANENT_DURATION_WORDS:
        return True
    return bool(re.fullmatch(r"\d+(?:\.\d+)?(?:\s*(?:ثانیه|دقیقه|ساعت|روز|هفته|ماه|seconds?|minutes?|hours?|days?|weeks?|months?|s|m|h|d|w|mo))?", value))

async def command_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    chat = update.effective_chat
    chat_type = chat.type if chat else ""
    user = update.effective_user

    # Deep-link entry for the per-group automatic-response manager.
    # This is intentionally kept before the normal PV /start response because
    # the deep-link has its own state-machine entry point.
    if chat_type == "private" and user and not user.is_bot:
        args = list(getattr(context, "args", []) or [])
        if args and args[0].startswith("autoresp_"):
            try:
                target_group_id = int(args[0].split("_", 1)[1])
            except (ValueError, IndexError):
                target_group_id = 0
            if target_group_id:
                await enter_auto_response_manager(update, context, target_group_id)
                return

    if chat_type == "private":
        # IMPORTANT: send the visible /start response BEFORE touching the DB.
        # A damaged/locked/very large database must never make /start appear
        # dead in PV. Database bookkeeping below is best-effort only.
        # Never make the visible /start reply depend on an extra Telegram API
        # request. The Application has already initialized the bot, so the
        # username is normally cached on context.bot. A slow/failing get_me()
        # here was able to make /start look completely dead in PV.
        bot_username = getattr(context.bot, "username", None) or ""
        if not bot_username:
            try:
                bot_info = await context.bot.get_me()
                bot_username = getattr(bot_info, "username", None) or ""
            except Exception:
                logger.exception("Failed to get bot username for /start; continuing without group URL")
                bot_username = ""

        start_pv_msg = (
            '<b>سلام عزیزم! به ربات جذاب من خوش اومدی! <tg-emoji emoji-id="5816739230482701944">⚡️</tg-emoji></b>\n'
            '<b>با استفاده از دکمه شیشه‌ای زیر منو به گروهت اضافه کن! <tg-emoji emoji-id="5818785846823755322">😻</tg-emoji></b>\n\n'
            '<b>بعد از اضافه کردن با ارسال دستور راهنما میتونی با من آشنا بشی! <tg-emoji emoji-id="5818984798298841943">⏳</tg-emoji></b>'
        )
        group_url = f"https://t.me/{bot_username}?startgroup=true" if bot_username else None
        button_kwargs = {
            "style": "success",
            "icon_custom_emoji_id": "4956745198521549627",
        }
        if group_url:
            button_kwargs["url"] = group_url
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("اضافه کردن گودی به گروه", **button_kwargs)]
        ])

        # This is the critical response. Do not put save_db() before it.
        await update.message.reply_text(start_pv_msg, reply_markup=kb, parse_mode=ParseMode.HTML)

        # PV bookkeeping is deliberately non-fatal. If persistence fails, the
        # user still receives /start and can continue using the bot.
        if user and not user.is_bot:
            try:
                db = load_db()
                cancel_auto_response_flow(db, user.id)
                uid_str = str(user.id)
                started_users = db.setdefault("started_users", {})
                now_ts = datetime.now().timestamp()
                if uid_str not in started_users:
                    started_users[uid_str] = {
                        "user_id": user.id,
                        "username": user.username or "",
                        "fullname": user.full_name or "کاربر",
                        "first_seen": now_ts,
                        "last_seen": now_ts
                    }
                else:
                    started_users[uid_str]["last_seen"] = now_ts
                    started_users[uid_str]["fullname"] = user.full_name or "کاربر"
                    started_users[uid_str]["username"] = user.username or ""
                mark_db_dirty()
                save_db(force=True)
            except Exception:
                logger.exception("PV /start database bookkeeping failed; /start response was already sent")
        return

    # Group /start keeps its existing group-only response.
    start_group_msg = '<b>بله عزیزم؟ من تو گروهم آماده و حاضر! <tg-emoji emoji-id="5283268017025736027">🤨</tg-emoji></b>'
    await update.message.reply_text(start_group_msg, parse_mode=ParseMode.HTML)

async def command_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    txt = (
        '<b>سلام عزیزم به ربات من خوش اومدی! <tg-emoji emoji-id="5352750090974929602">😍</tg-emoji></b>\n\n'
        '<b>از طریق دکمه‌های زیر میتونی کاملا با گودی آشنا بشی! <tg-emoji emoji-id="5884128023271182329">🐉</tg-emoji></b>'
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("راهنمای سرگرمی", callback_data=f"help_fun:{update.effective_user.id}", style="primary", icon_custom_emoji_id="5415940089375106928"),
         InlineKeyboardButton("راهنمای بی ادبی", callback_data=f"help_rude:{update.effective_user.id}", style="primary", icon_custom_emoji_id="5832633418386513259")],
        [InlineKeyboardButton("راهنمای کاربردی", callback_data=f"help_useful:{update.effective_user.id}", style="primary", icon_custom_emoji_id="5830338333892418460"),
         InlineKeyboardButton("راهنمای مدیریتی", callback_data=f"help_admin:{update.effective_user.id}", style="primary", icon_custom_emoji_id="5803348359972393936")]
    ])
    await update.message.reply_text(txt, reply_markup=kb, parse_mode=ParseMode.HTML)

async def command_owner_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    user_id = update.effective_user.id
    # /panel is a real bot command; never allow an unfinished auto-response
    # flow to consume or reinterpret it.
    cancel_auto_response_flow(load_db(), user_id)

    if int(user_id) != int(OWNER_ID):
        await update.message.reply_text(
            f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> این دستور فقط مخصوص مالک اصلی ربات می‌باشد!</b>',
            parse_mode=ParseMode.HTML
        )
        return
    try:
        await send_owner_panel_message(update, context)
    except Exception:
        logger.exception("OWNER PANEL ERROR:")

async def command_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    db = load_db()
    
    cleared = clear_user_all_states(db, user_id, chat_id)
    if cleared:
        await update.message.reply_text(
            f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> تمام عملیات‌های در حال اجرا برای شما به طور کامل لغو گردید.</b>',
            parse_mode=ParseMode.HTML
        )
    else:
        await update.message.reply_text("ℹ شما در هیچ حالت انتظاری قرار ندارید.")

async def command_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    user_id = str(update.effective_user.id)
    db = load_db()
    # /done is a real command too. End only the auto-response flow first,
    # then keep the existing /done behavior for every other feature.
    cancel_auto_response_flow(db, int(user_id))
    states = db.get("states", {})
    done_anything = False

    # /done also finishes the filter-word entry flow.
    if await filter_done(update, context):
        return

    if user_id in states.get("waiting_poem_names", {}):
        cid = states["waiting_poem_names"][user_id]
        del states["waiting_poem_names"][user_id]
        g_data = get_group_data(db, cid)
        count = len(g_data.get("custom_names", []))
        await update.message.reply_text(f" تنظیم اسامی به پایان رسید. تعداد کل: <b>{count}</b>", parse_mode=ParseMode.HTML)
        done_anything = True

    if user_id in states.get("waiting_fun_named_msg", {}):
        del states["waiting_fun_named_msg"][user_id]
        count = len(db.get("global_fun_named", []))
        await update.message.reply_text(f" ثبت پاسخ‌های فحش ناموسی سراسری پایان یافت. تعداد: <b>{count}</b>", parse_mode=ParseMode.HTML)
        done_anything = True

    if user_id in states.get("waiting_fun_normal_msg", {}):
        del states["waiting_fun_normal_msg"][user_id]
        count = len(db.get("global_fun_normal", []))
        await update.message.reply_text(f" ثبت پاسخ‌های فحش عادی سراسری پایان یافت. تعداد: <b>{count}</b>", parse_mode=ParseMode.HTML)
        done_anything = True

    if done_anything:
        mark_db_dirty()
        save_db(force=True)
    else:
        await update.message.reply_text("ℹ شما در هیچ وضعیت انتظاری نیستید.")

async def handle_pending_comment_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle a message that is explicitly expected as the saved comment.

    This handler runs before the generic message/filter handlers so another
    feature cannot consume the admin's message before the comment state is
    processed.
    """
    if not update.message or not update.effective_user:
        return
    db = load_db()
    state = db.setdefault("states", {}).setdefault("waiting_comment_msg", {}).get(str(update.effective_user.id))
    if state is None:
        return
    if isinstance(state, dict):
        target_cid = int(state.get("chat_id", 0) or 0)
    else:
        try:
            target_cid = int(state)
        except Exception:
            target_cid = 0
    if not target_cid:
        return
    if not await is_configured_group_manager(context, target_cid, update.effective_user.id):
        return
    handled = await save_comment_from_message(update, context, target_cid)
    if handled:
        raise ApplicationHandlerStop()

async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    try:
        db = load_db()

        # A comment message is a one-shot input for the comment setup panel.
        # Consume it before any other message logic so configured panel managers
        # are not blocked by unrelated handlers or Telegram-admin checks.
        user_id = update.effective_user.id if update.effective_user else None
        if user_id is not None:
            pending_comment = db.setdefault("states", {}).setdefault("waiting_comment_msg", {}).get(str(user_id))
            if pending_comment is not None:
                if isinstance(pending_comment, dict):
                    pending_chat_id = int(pending_comment.get("chat_id", 0) or 0)
                else:
                    try:
                        pending_chat_id = int(pending_comment)
                    except Exception:
                        pending_chat_id = 0
                if pending_chat_id and await save_comment_from_message(update, context, pending_chat_id):
                    return

            # Database restore is owner-only and private-only. It must run before
            # the generic private handlers so a backup file cannot be consumed by
            # another feature.
            if await handle_backup_restore_private_message(update, context):
                return

            # Automatic-response management is a private-only state machine.
            # It must run before the generic private handlers so management
            # keyboard inputs cannot accidentally become normal bot input.
            if await handle_auto_response_private_message(update, context):
                return

        await register_member(update, db)

        chat = update.effective_chat
        is_group = chat and chat.type in ["group", "supergroup"]

        if is_group:
            setup_chat_jobs(context.job_queue, [chat.id])

        user_id = update.effective_user.id
        u_str = str(user_id)
        chat_id = chat.id if chat else 0
        session_k = get_session_key(user_id, chat_id)
        raw_text = update.message.text or update.message.caption or ""
        clean_raw = raw_text.strip().lower()
        norm_text = normalize_text(raw_text)
        
        # --------------------------------------
        # USER CHECK COMMANDS (GLOBAL / NOT ADMIN-ONLY)
        # --------------------------------------
        check_user_commands = {"گودی بررسی", "گودی بررسی کن", "بررسی کاربر", "گودی بررسی کاربر", "گودی بررسی کاربر بیار"}
        if normalize_text(raw_text).lower() in check_user_commands and u_str not in db["states"].get("waiting_check_user", {}):
            await open_check_user_panel(update, context, return_to_advanced=False)
            return

        # --------------------------------------
        # LINK COMMAND HANDLER (GROUP ONLY)
        # --------------------------------------
        if is_group and LINK_COMMAND_PATTERN.match(raw_text):
            if not await is_admin_or_owner(context, chat_id, user_id):
                await update.message.reply_text(
                    f'<b>تو که ادمین نیستی! اجازه ندارم بهت لینک بدم.</b> <tg-emoji emoji-id="5276508228128103199">😐</tg-emoji>',
                    parse_mode=ParseMode.HTML
                )
                return

            if not await check_bot_admin_and_link_rights(context, chat_id):
                await update.message.reply_text(
                    f'<b>متاسفم! من ادمین گروه نیستم یا دسترسی به لینک ندارم.</b>\n'
                    f'<b>لطفا به یکی از ادمین‌ها بگو مشکل رو حل کنن!</b> <tg-emoji emoji-id="5274171963487576924">🌟</tg-emoji>',
                    parse_mode=ParseMode.HTML
                )
                return

            cmd_lower = raw_text.strip().lower()

            # In forum topics, and whenever the command is a reply to a user,
            # a plain link request must return the normal group invite directly
            # (not the link-selection panel). Existing link subcommands remain unchanged.
            plain_link_forms = {
                "لینک", "گودی لینک", "دریافت لینک", "لینک بده",
                "گودی لینک بده", "گودی لینک بگیر", "گودی لینک بفرست",
            }
            in_forum_topic = getattr(update.message, "message_thread_id", None) is not None
            if cmd_lower in plain_link_forms and (in_forum_topic or update.message.reply_to_message):
                try:
                    text_payload = await generate_group_link_text_payload(context, chat_id, is_once=False)
                    await update.message.reply_text(
                        text_payload,
                        parse_mode=ParseMode.HTML,
                        link_preview_options=LinkPreviewOptions(is_disabled=True)
                    )
                except Exception as e:
                    logger.exception("Topic/reply normal link command failed | chat_id=%s | user_id=%s", chat_id, user_id)
                    await update.message.reply_text(
                        f" ارسال لینک عادی ناموفق بود: {str(e)[:150]}",
                        parse_mode=ParseMode.HTML
                    )
                return

            normal_link_commands = {
                "گودی لینک عادی بده",
                "لینک عادی",
                "لینک عادی بگیر",
                "لینک عادی بده",
            }
            if cmd_lower in normal_link_commands:
                try:
                    text_payload = await generate_group_link_text_payload(context, chat_id, is_once=False)
                    await update.message.reply_text(
                        text_payload,
                        parse_mode=ParseMode.HTML,
                        link_preview_options=LinkPreviewOptions(is_disabled=True)
                    )
                except Exception as e:
                    logger.exception("Normal link command failed | chat_id=%s | user_id=%s", chat_id, user_id)
                    await update.message.reply_text(
                        f" ارسال لینک عادی ناموفق بود: {str(e)[:150]}",
                        parse_mode=ParseMode.HTML
                    )
                return

            if any(k in cmd_lower for k in ["عکس", "به صورت عکس", "رو عکس بفرست"]):
                try:
                    chat_obj = await context.bot.get_chat(chat_id)
                    caption_text = await generate_group_link_text_payload(context, chat_id, is_once=False)
                    photo_bytes = await get_group_photo_for_send(context, chat_obj)
                    if photo_bytes:
                        await context.bot.send_photo(chat_id=chat_id, photo=photo_bytes, caption=caption_text, parse_mode=ParseMode.HTML)
                    else:
                        await update.message.reply_text(caption_text, parse_mode=ParseMode.HTML, link_preview_options=LinkPreviewOptions(is_disabled=True))
                except Exception as e:
                    logger.exception("Link photo command failed | chat_id=%s | user_id=%s", chat_id, user_id)
                    await update.message.reply_text(f" دریافت لینک بصورت عکس ناموفق بود: {str(e)[:150]}", parse_mode=ParseMode.HTML)
                return

            elif "یک‌بار" in cmd_lower or "یکبار" in cmd_lower:
                try:
                    text_payload = await generate_group_link_text_payload(context, chat_id, is_once=True)
                    await update.message.reply_text(text_payload, reply_markup=build_link_sub_keyboard(chat_id, is_once=True, invite_link=load_db().get("groups", {}).get(str(chat_id), {}).get("invite_link")), parse_mode=ParseMode.HTML, link_preview_options=LinkPreviewOptions(is_disabled=True))
                except Exception as e:
                    logger.exception("One-time link command failed | chat_id=%s | user_id=%s", chat_id, user_id)
                    await update.message.reply_text(f" ساخت لینک یک‌بارمصرف ناموفق بود: {str(e)[:150]}", parse_mode=ParseMode.HTML)
                return

            elif "پیوی" in cmd_lower or "در پیوی" in cmd_lower:
                try:
                    text_payload = await generate_group_link_text_payload(context, chat_id, is_once=False)
                    await context.bot.send_message(chat_id=user_id, text=text_payload, parse_mode=ParseMode.HTML, link_preview_options=LinkPreviewOptions(is_disabled=True))
                    await update.message.reply_text(" لینک گروه با موفقیت در پیوی شما ارسال شد.", parse_mode=ParseMode.HTML)
                except Exception as e:
                    logger.exception("Link PV command failed | group=%s | user=%s", chat_id, user_id)
                    error_text = str(e).lower()
                    if any(x in error_text for x in ["chat not found", "user is deactivated", "forbidden"]):
                        msg = " ارسال به پیوی ممکن نشد. اگر ربات را بلاک کرده‌اید، آن را آزاد و دوباره Start کنید."
                    else:
                        msg = f" ارسال لینک به پیوی ناموفق بود: {str(e)[:150]}"
                    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
                return

            else:
                panel_text = f'<tg-emoji emoji-id="6044084382174552276">📊</tg-emoji> <b>نوع لینک را انتخاب کنید:</b>'
                await update.message.reply_text(panel_text, reply_markup=build_link_panel_keyboard(chat_id), parse_mode=ParseMode.HTML)
                return 

        # --------------------------------------
        # GROUP CONFIGURATION / MANAGEMENT / WARN / MUTE / BAN
        # --------------------------------------
        if is_group:
            cmd = normalize_text(raw_text).strip().lower()
            g_data = get_group_data(db, chat_id)

            # Commands that change roles or punish users must never be executed
            # when the command itself is sent as a reply to one of the bot's messages.
            # This applies equally inside forum topics.
            is_reply_to_bot = bool(
                update.message.reply_to_message
                and update.message.reply_to_message.from_user
                and update.message.reply_to_message.from_user.id == context.bot.id
            )
            reply_block_prefixes = (
                "تنظیم مدیر", "مدیر شو", "مدیر کن",
                "تنظیم مالک", "مالک شو", "مالک کن",
                "تنظیم ویژه", "ویژه شو", "ویژه کن", "عضو ویژه", "عضو ویژه شو",
                "ترفیع", "عزل",
                "معاف", "معاف شو", "معاف کردن",
                "از مدیر دربیا", "از مدیر دربیار", "از ادمین دربیا", "از ادمین دربیار",
                "از مالک دربیا", "از مالک دربیار", "از ویژه دربیا", "از ویژه دربیار",
                "حذف مدیر", "حذف ادمین", "حذف مالک", "حذف ویژه", "حذف عضو ویژه", "حذف معاف",
                "اخطار", "هشدار", "warn", "حذف اخطار", "حذف هشدار",
                "بن", "ban", "اخراج", "مسدود", "سیک",
                "سکوت", "میوت", "mute", "حذف بن", "آن بن", "unban",
                "رفع مسدود", "حذف اخراج", "رفع مسدودیت",
                "unmute", "remove mute", "حذف سکوت", "رفع سکوت",
                "لیست مالکین", "لیست ادمین", "لیست ادمین ها", "لیست مدیران",
                "پاکسازی مالکین", "پاکسازی لیست مالکین", "پاکسازی مدیران",
                "پاکسازی لیست مدیران", "پاکسازی اخطار", "پاکسازی لیست اخطار",
                "پاکسازی سکوت", "پاکسازی لیست سکوت", "پاکسازی بن", "پاکسازی لیست بن",
            )
            replied_bot_message_is_moderation_target = False
            if is_reply_to_bot and update.message.reply_to_message:
                moderation_map = g_data.get("moderation_message_targets", {}) or {}
                replied_bot_message_is_moderation_target = str(update.message.reply_to_message.message_id) in moderation_map

            if is_reply_to_bot and not replied_bot_message_is_moderation_target and any(
                cmd == prefix or cmd.startswith(prefix + " ")
                for prefix in reply_block_prefixes
            ):
                await update.message.reply_text(
                    '<b><tg-emoji emoji-id="6329823947877517249">🗿</tg-emoji> د آخه مشتی.</b>',
                    parse_mode=ParseMode.HTML
                )
                return

            config_cmds = {"گودی ثبت کن", "گودی ثبت سازی کن", "گودی پیکربندی", "پیکربندی", "پیکربندی کن", "گودی پیکربندی کن"}
            if cmd in config_cmds:
                if not await is_admin_or_owner(context, chat_id, user_id):
                    await update.message.reply_text(f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> فقط مدیران گروه می‌توانند پیکربندی را انجام دهند.</b>', parse_mode=ParseMode.HTML); return
                await configure_group_management(update, context, db, chat_id); return

            management = g_data.get("management", {}) or {}

            # Added promotion formats: «ترفیع»، «ترفیع @user»،
            # «ترفیع ادمین @user»، «ترفیع :ادمین شدن @user»، etc.
            # They are normalized into the existing admin-promotion engine below.
            promotion_text = re.sub(r"[：:]", " ", cmd)
            promotion_text = re.sub(r"\s+", " ", promotion_text).strip()
            promotion_match = re.match(
                r"^ترفیع(?:\s+(?:ادمین(?:\s+شدن)?|مدیر(?:\s+شدن)?))?(?:\s+(.*))?$",
                promotion_text,
                flags=re.IGNORECASE,
            )
            if promotion_match:
                promotion_target = (promotion_match.group(1) or "").strip()
                cmd = "مدیر شو" + (f" {promotion_target}" if promotion_target else "")

            # Management roles: owner / admin / special / exempt.
            role_specs = [
                ("admins", ["تنظیم مدیر", "مدیر شو", "مدیر کن"], "مدیر", False),
                ("owners", ["تنظیم مالک", "مالک شو", "مالک کن"], "مالک", False),
                ("special", ["تنظیم ویژه", "ویژه شو", "ویژه کن", "عضو ویژه", "عضو ویژه شو"], "عضو ویژه", False),
                ("exempt", ["معاف", "معاف شو", "معاف کردن"], "معاف", False),
            ]
            for role, prefixes, label, _ in role_specs:
                matched = next((x for x in prefixes if cmd == x or cmd.startswith(x + " ")), None)
                if matched:
                    rest = cmd[len(matched):].strip()
                    if rest and not _looks_like_user_target(rest):
                        return
                    # Role-management is a group-management operation. Any
                    # configured group manager (or a Telegram admin when the
                    # group has not been configured) may use it; it must not
                    # depend on the bot owner's identity.
                    allowed = await is_configured_group_manager(context, chat_id, user_id)
                    if not allowed:
                        await update.message.reply_text(f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> فقط مالکین گروه دسترسی اجرای این دستور را دارند.</b>', parse_mode=ParseMode.HTML); return
                    uid, name, uname = await resolve_group_target(update, context, db, chat_id, rest)
                    if not uid:
                        await update.message.reply_text('<b>برای اجرای این دستور روی کاربر ریپلای کنید یا آیدی/یوزرنیم او را وارد کنید.</b>', parse_mode=ParseMode.HTML); return
                    # Determine the target's CURRENT management rank first.
                    # IMPORTANT: never reject a promotion just because the user is
                    # already in a lower role. Lower -> higher is a valid promotion.
                    owner_ids = _role_ids(g_data, "owners")
                    admin_ids = _role_ids(g_data, "admins")
                    special_ids = _role_ids(g_data, "special")
                    exempt_ids = _role_ids(g_data, "exempt")
                    primary_owner = is_primary_group_owner_id(g_data, uid)
                    target_label = f"@{html.escape(uname.lstrip('@'))}" if uname else get_user_mention(uid, name)

                    # Telegram's live role is authoritative for real group owner/admin.
                    live_owner = False
                    live_admin = False
                    try:
                        live_member = await cached_chat_member(context, chat_id, uid)
                        live_owner = live_member.status == ChatMemberStatus.OWNER
                        live_admin = live_member.status == ChatMemberStatus.ADMINISTRATOR
                        if getattr(live_member, "user", None):
                            live_name = live_member.user.full_name or name
                            live_uname = live_member.user.username or uname
                            target_label = f"@{html.escape(live_uname.lstrip('@'))}" if live_uname else get_user_mention(uid, live_name)
                            name = live_name
                            uname = live_uname
                    except Exception:
                        pass

                    # Hierarchy: exempt < special < admin < owner.
                    # A user can ALWAYS be promoted upward. A user cannot be
                    # assigned a lower rank than the one they currently have.
                    role_rank = {"exempt": 0, "special": 1, "admins": 2, "owners": 3}
                    role_word = {"exempt": "معاف", "special": "عضو ویژه", "admins": "ادمین", "owners": "مالک"}
                    emoji_for_role = {
                        "exempt": (PREMIUM_ROLE_EMOJI, "🎖️"),
                        "special": (PREMIUM_ROLE_EMOJI, "🎖️"),
                        "admins": (PREMIUM_MANAGER_EMOJI, "⚡️"),
                        "owners": (PREMIUM_ROLE_EMOJI, "🎖️"),
                    }

                    if live_owner or primary_owner or int(uid) in owner_ids:
                        current_role = "owners"
                    elif live_admin or int(uid) in admin_ids:
                        current_role = "admins"
                    elif int(uid) in special_ids:
                        current_role = "special"
                    elif int(uid) in exempt_ids:
                        current_role = "exempt"
                    else:
                        current_role = None

                    current_rank = role_rank.get(current_role, -1)
                    target_rank = role_rank[role]

                    # The bot owner is protected ONLY when he is the actual owner
                    # of this same group. In every other group, normal hierarchy applies.
                    if int(uid) == int(OWNER_ID) and (live_owner or primary_owner):
                        await update.message.reply_text(
                            f'<b><tg-emoji emoji-id="{PREMIUM_ROLE_EMOJI}">🎖️</tg-emoji> کاربر {target_label} درحال حاضر مالک ربات است و انجام این عملیات غیرممکن میباشد.</b>',
                            parse_mode=ParseMode.HTML
                        ); return

                    # Same rank: do not change anything; report that the user already has it.
                    if current_rank == target_rank:
                        emoji_id, emoji = emoji_for_role[role]
                        await update.message.reply_text(
                            f'<b><tg-emoji emoji-id="{emoji_id}">{emoji}</tg-emoji> کاربر {target_label} از قبل {role_word[role]} می‌باشد.</b>',
                            parse_mode=ParseMode.HTML
                        ); return

                    # Lower rank requested for a higher-ranked user: refuse demotion.
                    if current_rank > target_rank:
                        emoji_id, emoji = emoji_for_role[current_role]
                        await update.message.reply_text(
                            f'<b><tg-emoji emoji-id="{emoji_id}">{emoji}</tg-emoji> کاربر {target_label} درحال حاضر {role_word[current_role]} می‌باشد و توانایی انجام چنین کاری وجود ندارد.</b>',
                            parse_mode=ParseMode.HTML
                        ); return

                    # Promotion: remove the previous lower role and assign the new one.
                    # This is the critical part: special -> admin, admin -> owner,
                    # exempt -> special/admin/owner, etc. must all be allowed.
                    if current_role and current_role != role:
                        old_ids = g_data["management"].setdefault(current_role, [])
                        g_data["management"][current_role] = [int(x) for x in old_ids if int(x) != int(uid)]

                    ids = g_data["management"].setdefault(role, [])
                    if uid not in [int(x) for x in ids]:
                        ids.append(uid)
                    db.setdefault("members", {})[str(uid)] = {"username": uname, "fullname": name}
                    mark_db_dirty(); save_db(force=True)

                    # A promoted user must not remain muted. If the target is currently
                    # in the bot's mute list, restore normal group permissions immediately
                    # after assigning the new management role. Keep the mute record if
                    # Telegram refuses the unmute, so we never pretend it was removed.
                    extra = ""
                    if str(uid) in (g_data.get("muted_users", {}) or {}):
                        if await bot_can_restrict_members(context, chat_id):
                            try:
                                await context.bot.restrict_chat_member(
                                    chat_id,
                                    uid,
                                    permissions=full_group_permissions()
                                )
                                g_data.setdefault("muted_users", {}).pop(str(uid), None)
                                mark_db_dirty(); save_db(force=True)
                            except Exception:
                                extra += f'\n- کاربر از نظر ربات {label} شد، اما رفع سکوت توسط تلگرام انجام نشد. <tg-emoji emoji-id="{PREMIUM_CANCEL_EMOJI}">❌</tg-emoji>'
                        else:
                            extra += f'\n- کاربر از نظر ربات {label} شد، اما ربات دسترسی رفع سکوت را ندارد. <tg-emoji emoji-id="{PREMIUM_CANCEL_EMOJI}">❌</tg-emoji>'

                    if role == "admins":
                        if await bot_can_promote_members(context, chat_id):
                            try:
                                await context.bot.promote_chat_member(
                                    chat_id, uid,
                                    can_manage_chat=True,
                                    can_delete_messages=True,
                                    can_restrict_members=True,
                                    can_change_info=True,
                                    can_invite_users=True,
                                    can_pin_messages=True,
                                    can_manage_topics=True,
                                    is_anonymous=False
                                )
                            except Exception:
                                extra += f'\n- اما ربات دسترسی به ادمین کردن گروه نداشت و شخص فقط در ربات ادمین شد! <tg-emoji emoji-id="{PREMIUM_CANCEL_EMOJI}">❌</tg-emoji>'
                        else:
                            extra += f'\n- اما ربات دسترسی به ادمین کردن گروه نداشت و شخص فقط در ربات ادمین شد! <tg-emoji emoji-id="{PREMIUM_CANCEL_EMOJI}">❌</tg-emoji>'

                    result_msg = await update.message.reply_text(
                        f'<b><tg-emoji emoji-id="{PREMIUM_MANAGER_EMOJI}">⚡️</tg-emoji> › {get_user_mention(uid, name)}\n\n'
                        f'›› <tg-emoji emoji-id="{PREMIUM_MANAGER_ADD_EMOJI}">💫</tg-emoji> به لیست {label} ربات افزوده شد.{extra}</b>',
                        parse_mode=ParseMode.HTML
                    )
                    g_data.setdefault("moderation_message_targets", {})[str(result_msg.message_id)] = int(uid)
                    mark_db_dirty(); save_db(force=True)
                    return

            # Added demotion formats: «عزل», «از مدیر دربیا/دربیـار», «از مالک دربیا/دربیـار», etc.
            demotion_text = re.sub(r"[：:]", " ", cmd)
            demotion_text = re.sub(r"\s+", " ", demotion_text).strip()
            demotion_aliases = [
                (r"^عزل(?:\s+(.*))?$", "حذف مدیر"),
                (r"^از مدیر دربیا(?:\s+(.*))?$", "حذف مدیر"),
                (r"^از مدیر دربیار(?:\s+(.*))?$", "حذف مدیر"),
                (r"^از ادمین دربیا(?:\s+(.*))?$", "حذف ادمین"),
                (r"^از ادمین دربیار(?:\s+(.*))?$", "حذف ادمین"),
                (r"^از مالک دربیا(?:\s+(.*))?$", "حذف مالک"),
                (r"^از مالک دربیار(?:\s+(.*))?$", "حذف مالک"),
                (r"^از ویژه دربیا(?:\s+(.*))?$", "حذف ویژه"),
                (r"^از ویژه دربیار(?:\s+(.*))?$", "حذف ویژه"),
                (r"^از عضو ویژه دربیا(?:\s+(.*))?$", "حذف عضو ویژه"),
                (r"^از عضو ویژه دربیار(?:\s+(.*))?$", "حذف عضو ویژه"),
            ]
            for alias_pattern, normalized_command in demotion_aliases:
                alias_match = re.match(alias_pattern, demotion_text, flags=re.IGNORECASE)
                if alias_match:
                    demotion_target = (alias_match.group(1) or "").strip()
                    cmd = normalized_command + (f" {demotion_target}" if demotion_target else "")
                    break

            remove_specs = [
                ("admins", ["حذف مدیر", "حذف ادمین"], "مدیر"),
                ("owners", ["حذف مالک"], "مالک"),
                ("special", ["حذف ویژه", "حذف عضو ویژه"], "عضو ویژه"),
                ("exempt", ["حذف معاف"], "معاف"),
            ]
            for role, prefixes, label in remove_specs:
                matched = next((x for x in prefixes if cmd == x or cmd.startswith(x + " ")), None)
                if matched:
                    rest = cmd[len(matched):].strip()
                    if rest and not _looks_like_user_target(rest):
                        return
                    if role == "owners":
                        # The bot's OWNER_ID gets this power only when that same
                        # Telegram account is the real owner of this exact group.
                        allowed = await is_primary_or_bot_owner_of_group(context, chat_id, g_data, user_id)
                    else:
                        allowed = await is_configured_group_owner(context, chat_id, user_id)
                    if not allowed:
                        await update.message.reply_text(f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> شما اجازه حذف {label} را ندارید.</b>', parse_mode=ParseMode.HTML); return
                    uid, name, uname = await resolve_group_target(update, context, db, chat_id, rest)
                    if not uid:
                        await update.message.reply_text('<b>برای اجرای این دستور روی کاربر ریپلای کنید یا آیدی/یوزرنیم او را وارد کنید.</b>', parse_mode=ParseMode.HTML); return
                    if role == "owners" and is_primary_group_owner_id(g_data, uid):
                        await update.message.reply_text('<b>مالک اصلی گروه را نمی‌توان حذف کرد.</b>', parse_mode=ParseMode.HTML); return
                    ids = g_data["management"].setdefault(role, [])
                    g_data["management"][role] = [int(x) for x in ids if int(x) != int(uid)]
                    if role == "admins" and await bot_can_promote_members(context, chat_id):
                        try:
                            await context.bot.promote_chat_member(chat_id, uid, can_manage_chat=False, can_delete_messages=False, can_restrict_members=False, can_change_info=False, can_invite_users=False, can_pin_messages=False, can_manage_topics=False, is_anonymous=False)
                        except Exception: pass
                    mark_db_dirty(); save_db(force=True)
                    result_msg = await update.message.reply_text(f'<b><tg-emoji emoji-id="{PREMIUM_MANAGER_EMOJI}">⚡️</tg-emoji> › {get_user_mention(uid, name)}\n\n›› <tg-emoji emoji-id="{PREMIUM_MANAGER_ADD_EMOJI}">💫</tg-emoji> {label} با موفقیت حذف شد.</b>', parse_mode=ParseMode.HTML)
                    g_data.setdefault("moderation_message_targets", {})[str(result_msg.message_id)] = int(uid)
                    mark_db_dirty(); save_db(force=True)
                    return

            list_commands = {
                "لیست اخطار": "warns", "اخطار گرفتگان": "warns", "گودی لیست اخطار": "warns", "گودی لیست اخطار بده": "warns", "گودی لیست اخطار بفرست": "warns",
                "لیست سکوت": "muted", "لیست میوت": "muted", "لیست سکوت شدگان": "muted", "لیست سکوت شده ها": "muted", "لیست میوت شده ها": "muted",
                "لیست بن": "banned", "لیست اخراج": "banned", "لیست مسدودیت": "banned", "لیست بن شده ها": "banned", "لیست مسدود شدگان": "banned",
                "لیست مالکین": "owners", "لیست ادمین ها": "admins", "لیست ادمین": "admins", "لیست مدیران": "admins",
                "لیست ویژه": "special", "لیست ویژه ها": "special", "لیست عضو های ویژه": "special", "لیست اعضای ویژه": "special", "لیست معاف": "exempt"
            }
            if cmd in list_commands:
                if not await is_configured_group_manager(context, chat_id, user_id):
                    await update.message.reply_text(f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> شما دسترسی مدیریت این گروه را ندارید.</b>', parse_mode=ParseMode.HTML); return
                text, kb = await build_group_list_detail_content(context, chat_id, list_commands[cmd], db, user_id)
                await update.message.reply_text(text, reply_markup=kb, parse_mode=ParseMode.HTML); return

            cleanup_cmds = {
                "پاکسازی اخطار": "warns", "پاکسازی لیست اخطار": "warns", "گودی لیست اخطار پاکسازی کن": "warns",
                "پاکسازی سکوت": "muted", "پاکسازی لیست سکوت": "muted",
                "پاکسازی بن": "banned", "پاکسازی لیست بن": "banned",
                "پاکسازی مالکین": "owners", "پاکسازی لیست مالکین": "owners",
                "پاکسازی مدیران": "admins", "پاکسازی لیست مدیران": "admins",
                "پاکسازی ویژه": "special", "پاکسازی لیست ویژه": "special",
                "پاکسازی معاف": "exempt", "پاکسازی لیست معاف": "exempt"
            }
            if cmd in cleanup_cmds:
                lt = cleanup_cmds[cmd]
                if lt == "owners" and not await is_primary_or_bot_owner_of_group(context, chat_id, g_data, user_id):
                    await update.message.reply_text(f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> این دستور فقط مختص مالک گروه میباشد.</b>', parse_mode=ParseMode.HTML); return
                if not await is_configured_group_manager(context, chat_id, user_id):
                    await update.message.reply_text(f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> شما دسترسی مدیریت این گروه را ندارید.</b>', parse_mode=ParseMode.HTML); return
                cleanup_name = {"owners": "مالکین", "admins": "مدیران", "special": "ویژه", "exempt": "معاف", "warns": "اخطار", "muted": "سکوت", "banned": "بن"}[lt]
                mgmt = g_data.get("management", {}) or {}
                list_values = {
                    "owners": mgmt.get("owners", []),
                    "admins": mgmt.get("admins", []),
                    "special": mgmt.get("special", []),
                    "exempt": mgmt.get("exempt", []),
                    "warns": g_data.get("warnings", {}),
                    "muted": g_data.get("muted_users", {}),
                    "banned": g_data.get("banned_users", {}),
                }.get(lt, [])
                if not list_values:
                    await update.message.reply_text(
                        f'<b><tg-emoji emoji-id="{CHECK_CUSTOM_EMOJI_ID}">✔️</tg-emoji> لیست {cleanup_name} از قبل خالی می‌باشد.</b>',
                        parse_mode=ParseMode.HTML
                    )
                    return
                kb = InlineKeyboardMarkup([[
                    InlineKeyboardButton("بله", callback_data=f"list_cleanup:{lt}:{chat_id}", style="success", icon_custom_emoji_id=CHECK_CUSTOM_EMOJI_ID),
                    InlineKeyboardButton("خیر", callback_data=f"list_cleanup_cancel:{lt}:{chat_id}", style="danger", icon_custom_emoji_id=CROSS_CUSTOM_EMOJI_ID)
                ]])
                await update.message.reply_text(f'<b><tg-emoji emoji-id="{CHECK_CUSTOM_EMOJI_ID}">✔️</tg-emoji> آیا از پاکسازی کامل لیست {cleanup_name} مطمئن هستید؟</b>', reply_markup=kb, parse_mode=ParseMode.HTML); return

            # Warning commands.
            warn_aliases = ["اخطار بده", "هشدار بده", "اخطار", "هشدار", "warn"]
            warn_match = next((x for x in sorted(warn_aliases, key=len, reverse=True) if cmd == x or cmd.startswith(x + " ")), None)
            if warn_match:
                if not await is_configured_group_manager(context, chat_id, user_id):
                    await update.message.reply_text(f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> شما مدیر گروه نیستید و دسترسی به سیستم اخطار ندارید.</b>', parse_mode=ParseMode.HTML); return
                s = g_data.get("warning_settings", {}) or {}
                if not s.get("punishment"):
                    await update.message.reply_text('<b> شما هنوز مجازاتی برای اخطار مشخص نکردید.</b>\n\n<b> با ارسال دستور پنل و رفتن به بخش تنظیمات پیشرفته مجازات کاربران را مشخص کنید.</b>', parse_mode=ParseMode.HTML); return
                rest = cmd[len(warn_match):].strip()
                if rest and not _looks_like_user_target(rest):
                    return
                uid, name, uname = await resolve_group_target(update, context, db, chat_id, rest)
                if not uid:
                    await update.message.reply_text('<b>برای اخطار دادن باید روی کاربر ریپلای کنید یا آیدی/یوزرنیم او را وارد کنید.</b>', parse_mode=ParseMode.HTML); return
                if int(uid) == int(OWNER_ID):
                    await update.message.reply_text(f'<b>›› <tg-emoji emoji-id="{PREMIUM_ROLE_EMOJI}">🎖️</tg-emoji> مالک ربات می‌باشد.</b>', parse_mode=ParseMode.HTML); return
                if uid in _role_ids(g_data, "special"):
                    await update.message.reply_text(f'<b>›› <tg-emoji emoji-id="{PREMIUM_ROLE_EMOJI}">🎖️</tg-emoji> کاربر عضو ویژه می‌باشد.</b>', parse_mode=ParseMode.HTML); return
                if is_group_manager_id(g_data, uid):
                    await update.message.reply_text(f'<b>›› <tg-emoji emoji-id="{PREMIUM_ROLE_EMOJI}">🎖️</tg-emoji> مدیر / مالک گروه می‌باشد.</b>', parse_mode=ParseMode.HTML); return
                db.setdefault("members", {})[str(uid)] = {"username": uname, "fullname": name}
                warnings = g_data.setdefault("warnings", {})
                item = warnings.setdefault(str(uid), {"count": 0, "username": uname, "fullname": name})
                try:
                    raw_limit = int(s.get("count", 3))
                except (TypeError, ValueError):
                    raw_limit = 3
                limit = max(1, min(20, raw_limit))
                try:
                    current_count = int(item.get("count", 0))
                except (TypeError, ValueError):
                    current_count = 0
                item["count"] = min(limit, max(0, current_count) + 1)
                item["username"], item["fullname"] = uname, name
                count = item["count"]
                punishment = s.get("punishment")
                mark_db_dirty(); save_db(force=True)
                mention = get_user_mention(uid, name)
                if count < limit:
                    result_msg = await update.message.reply_text(f'<b><tg-emoji emoji-id="{WARN_USER_EMOJI}">❗️</tg-emoji> › کاربر {mention}</b>\n\n<b>›› شما [ {count}/{limit} ] اخطار دریافت کردید.</b>', parse_mode=ParseMode.HTML)
                    g_data.setdefault("moderation_message_targets", {})[str(result_msg.message_id)] = int(uid)
                    mark_db_dirty(); save_db(force=True)
                    return
                # Execute configured punishment at the limit.
                try:
                    if punishment == "kick":
                        await context.bot.ban_chat_member(chat_id, uid)
                        g_data.setdefault("banned_users", {})[str(uid)] = {"username": uname, "fullname": name, "until": None, "created_at": datetime.now().timestamp()}
                        result = f'- به دلیل تکمیل اخطارها، از گروه اخراج می‌شوید. <tg-emoji emoji-id="{WARN_KICK_EMOJI}">❌</tg-emoji>' 
                    elif punishment == "mute":
                        await context.bot.restrict_chat_member(
                            chat_id, uid, permissions=full_mute_permissions()
                        )
                        g_data.setdefault("muted_users", {})[str(uid)] = {"username": uname, "fullname": name, "until": None, "created_at": datetime.now().timestamp()}
                        result = f'- به دلیل تکمیل اخطارها، به‌صورت دائم سکوت می‌شوید. <tg-emoji emoji-id="{WARN_MUTE_EMOJI}">🔇</tg-emoji>' 
                    else:
                        hours = max(1, int(s.get("temp_mute_hours", 1)))
                        until_ts = datetime.now().timestamp() + hours * 3600
                        until_dt = datetime.now() + timedelta(hours=hours)
                        try:
                            await context.bot.restrict_chat_member(
                                chat_id, uid,
                                permissions=full_mute_permissions(),
                                until_date=until_dt
                            )
                        except Exception as restrict_error:
                            logger.warning(
                                "Warning temp-mute retry without until_date | chat_id=%s user_id=%s topic=%s error=%s",
                                chat_id, uid, getattr(update.message, "message_thread_id", None), restrict_error
                            )
                            await context.bot.restrict_chat_member(
                                chat_id, uid,
                                permissions=full_mute_permissions()
                            )
                        g_data.setdefault("muted_users", {})[str(uid)] = {"username": uname, "fullname": name, "until": until_ts, "created_at": datetime.now().timestamp()}
                        result = f'- به دلیل تکمیل اخطارها، به مدت {hours} ساعت سکوت می‌شوید. <tg-emoji emoji-id="{WARN_TEMP_EMOJI}">🔇</tg-emoji>' 
                    # سقف اخطار رسید و مجازات با موفقیت اجرا شد؛ شمارنده اخطار این کاربر ریست می‌شود.
                    g_data.setdefault("warnings", {}).pop(str(uid), None)
                    mark_db_dirty(); save_db(force=True)
                    result_msg = await update.message.reply_text(f'<b><tg-emoji emoji-id="{WARN_DONE_EMOJI}">💥</tg-emoji> › کاربر {mention}</b>\n\n<b>›› <tg-emoji emoji-id="{PREMIUM_WARN_COUNT_EMOJI}">😾</tg-emoji> شما [ {count}/{limit} ] اخطار دریافت کردید.</b>\n<b>{result}</b>', parse_mode=ParseMode.HTML)
                    g_data.setdefault("moderation_message_targets", {})[str(result_msg.message_id)] = int(uid)
                    mark_db_dirty(); save_db(force=True)
                except Exception:
                    await update.message.reply_text(f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> ربات دسترسی اجرای مجازات انتخاب‌شده را ندارد.</b>', parse_mode=ParseMode.HTML)
                return

            # Delete / inspect warnings.
            del_match = next((x for x in ["حذف اخطار", "حذف هشدار"] if cmd == x or cmd.startswith(x + " ")), None)
            if del_match:
                if not await is_configured_group_manager(context, chat_id, user_id):
                    await update.message.reply_text(f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> شما مدیر گروه نیستید و دسترسی به سیستم اخطار ندارید.</b>', parse_mode=ParseMode.HTML); return
                rest = cmd[len(del_match):].strip()
                if rest and not _looks_like_user_target(rest):
                    return
                uid, name, uname = await resolve_group_target(update, context, db, chat_id, rest)
                if not uid: await update.message.reply_text('<b>روی کاربر ریپلای کنید یا آیدی/یوزرنیم او را وارد کنید.</b>', parse_mode=ParseMode.HTML); return
                item = g_data.setdefault("warnings", {}).get(str(uid))
                if not item or int(item.get("count", 0)) <= 0:
                    await update.message.reply_text(f'<b><tg-emoji emoji-id="{WARN_DONE_EMOJI}">💥</tg-emoji> › کاربر {get_user_mention(uid,name)}</b>\n\n<b>›› <tg-emoji emoji-id="{PREMIUM_WARN_COUNT_EMOJI}">😻</tg-emoji> هیچ اخطاری باقی نمانده است.</b>', parse_mode=ParseMode.HTML); return
                try:
                    current_count = int(item.get("count", 0))
                except (TypeError, ValueError):
                    current_count = 0
                item["count"] = max(0, current_count - 1)
                if item["count"] == 0: g_data["warnings"].pop(str(uid), None)
                mark_db_dirty(); save_db(force=True)
                remaining = item["count"]
                await update.message.reply_text(f'<b><tg-emoji emoji-id="{WARN_DONE_EMOJI}">💥</tg-emoji> › کاربر {get_user_mention(uid,name)}</b>\n\n<b>›› <tg-emoji emoji-id="{PREMIUM_WARN_COUNT_EMOJI}">😻</tg-emoji> یک اخطار شما حذف شد و {remaining} عدد باقی ماند.</b>', parse_mode=ParseMode.HTML); return

            check_match = next((x for x in ["بررسی اخطار", "تعداد اخطار", "مقدار اخطار", "بررسی هشدار"] if cmd == x or cmd.startswith(x + " ")), None)
            if check_match:
                if not await is_configured_group_manager(context, chat_id, user_id):
                    await update.message.reply_text(f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> شما مدیر گروه نیستید و دسترسی به سیستم اخطار ندارید.</b>', parse_mode=ParseMode.HTML); return
                rest = cmd[len(check_match):].strip()
                if rest and not _looks_like_user_target(rest):
                    return
                uid, name, uname = await resolve_group_target(update, context, db, chat_id, rest)
                if not uid: await update.message.reply_text('<b>روی کاربر ریپلای کنید یا آیدی/یوزرنیم او را وارد کنید.</b>', parse_mode=ParseMode.HTML); return
                try:
                    count = int(g_data.setdefault("warnings", {}).get(str(uid), {}).get("count", 0))
                except (TypeError, ValueError):
                    count = 0
                await update.message.reply_text(f'<b><tg-emoji emoji-id="{WARN_DONE_EMOJI}">💥</tg-emoji> › کاربر {get_user_mention(uid,name)}</b>\n\n<b>›› <tg-emoji emoji-id="{PREMIUM_WARN_COUNT_EMOJI}">😻</tg-emoji> تعداد اخطار های شما‌: {count}</b>', parse_mode=ParseMode.HTML); return

            # Ban / mute / unban / unmute commands.
            ban_cmds = ["بن", "ban", "اخراج", "مسدود", "سیک", "سیک کن", "بن کن", "اخراج کن", "مسدود کن"]
            mute_cmds = ["سکوت", "میوت", "mute", "سکوت کن", "میوت کن"]
            unban_cmds = ["حذف بن", "آن بن", "unban", "رفع مسدود", "حذف اخراج", "رفع مسدودیت"]
            unmute_cmds = ["unmute", "remove mute", "حذف سکوت", "رفع سکوت"]

            def match_prefix(options):
                # The command keyword must start at the beginning of the message.
                # This intentionally rejects sentences such as «الو سیک کن» / «بیا بن».
                return next((x for x in sorted(options, key=len, reverse=True) if cmd == x or cmd.startswith(x + " ")), None)

            action = None; matched = None
            if match_prefix(unban_cmds): action, matched = "unban", match_prefix(unban_cmds)
            elif match_prefix(unmute_cmds): action, matched = "unmute", match_prefix(unmute_cmds)
            elif match_prefix(ban_cmds): action, matched = "ban", match_prefix(ban_cmds)
            elif match_prefix(mute_cmds): action, matched = "mute", match_prefix(mute_cmds)

            # Natural reply syntax «9999 بن» / «9999 سکوت» is accepted only when
            # the message is actually a reply. Never scan arbitrary sentences for
            # a management keyword.
            if not action:
                parts = cmd.split()
                if update.message.reply_to_message and len(parts) >= 2 and parts[-1] in mute_cmds + ban_cmds:
                    # Only a numeric duration/target prefix is allowed here.
                    prefix_parts = parts[:-1]
                    if len(prefix_parts) == 1 and fa_to_en_digits(prefix_parts[0]).isdigit():
                        action = "mute" if parts[-1] in mute_cmds else "ban"
                        matched = parts[-1]
                        pre_duration = prefix_parts[0]
                        pre_target = ""
                if not action:
                    pre_duration = ""
                    pre_target = ""
            else:
                pre_duration = ""
                pre_target = ""

            if action:
                if not await is_configured_group_manager(context, chat_id, user_id):
                    await update.message.reply_text('<b><tg-emoji emoji-id="{0}">❌</tg-emoji> شما اجازه اجرای این دستور را ندارید.</b>'.format(CROSS_CUSTOM_EMOJI_ID), parse_mode=ParseMode.HTML); return
                rest = cmd[len(matched):].strip()
                reply_target = bool(update.message.reply_to_message)
                if rest:
                    if reply_target:
                        if not _looks_like_duration(rest):
                            return
                    elif not _looks_like_user_target(rest.split()[0]) or len(rest.split()) > 1:
                        return
                if pre_duration:
                    target_arg = ""
                    duration_arg = pre_duration
                elif pre_target:
                    target_arg = pre_target
                    duration_arg = pre_duration
                else:
                    target_arg = "" if reply_target else (rest.split()[0] if rest else "")
                    duration_arg = rest if reply_target else " ".join(rest.split()[1:])
                uid, name, uname = await resolve_group_target(update, context, db, chat_id, target_arg)
                if not uid:
                    await update.message.reply_text('<b>روی کاربر ریپلای کنید یا آیدی/یوزرنیم او را وارد کنید.</b>', parse_mode=ParseMode.HTML); return
                if int(uid) == int(OWNER_ID):
                    await update.message.reply_text(f'<b>›› <tg-emoji emoji-id="{PREMIUM_ROLE_EMOJI}">🎖️</tg-emoji> مالک ربات می‌باشد.</b>', parse_mode=ParseMode.HTML); return
                # Group hierarchy protection. Exempt users are intentionally
                # allowed through and may still be muted/banned/promoted.
                if is_primary_group_owner_id(g_data, uid):
                    await update.message.reply_text(f'<b><tg-emoji emoji-id="{PREMIUM_ROLE_EMOJI}">🎖️</tg-emoji> کاربر {html.escape("@" + uname.lstrip("@")) if uname else get_user_mention(uid, name)} مالک گروه می‌باشد و توانایی انجام چنین کاری وجود ندارد.</b>', parse_mode=ParseMode.HTML); return
                if uid in _role_ids(g_data, "admins"):
                    await update.message.reply_text(f'<b><tg-emoji emoji-id="{PREMIUM_MANAGER_EMOJI}">⚡️</tg-emoji> کاربر {html.escape("@" + uname.lstrip("@")) if uname else get_user_mention(uid, name)} ادمین گروه می‌باشد و توانایی انجام چنین کاری وجود ندارد.</b>', parse_mode=ParseMode.HTML); return
                if uid in _role_ids(g_data, "special"):
                    await update.message.reply_text(f'<b><tg-emoji emoji-id="{PREMIUM_ROLE_EMOJI}">🎖️</tg-emoji> کاربر {html.escape("@" + uname.lstrip("@")) if uname else get_user_mention(uid, name)} عضو ویژه می‌باشد و توانایی انجام چنین کاری وجود ندارد.</b>', parse_mode=ParseMode.HTML); return

                # Also inspect Telegram's live role. This prevents trying to mute/ban
                # a real group owner/admin when the bot's local management list is stale.
                try:
                    live_member = await cached_chat_member(context, chat_id, uid)
                    if live_member.status == ChatMemberStatus.OWNER:
                        live_label = f"@{html.escape(uname.lstrip('@'))}" if uname else get_user_mention(uid, name)
                        await update.message.reply_text(
                            f'<b><tg-emoji emoji-id="{PREMIUM_ROLE_EMOJI}">🎖️</tg-emoji> کاربر {live_label} مالک گروه می‌باشد و توانایی انجام چنین کاری وجود ندارد.</b>',
                            parse_mode=ParseMode.HTML
                        ); return
                    if live_member.status == ChatMemberStatus.ADMINISTRATOR:
                        live_label = f"@{html.escape(uname.lstrip('@'))}" if uname else get_user_mention(uid, name)
                        await update.message.reply_text(
                            f'<b><tg-emoji emoji-id="{PREMIUM_MANAGER_EMOJI}">⚡️</tg-emoji> کاربر {live_label} ادمین گروه می‌باشد و توانایی انجام چنین کاری وجود ندارد.</b>',
                            parse_mode=ParseMode.HTML
                        ); return
                except Exception:
                    pass

                if action in ("ban", "mute") and not await bot_can_restrict_members(context, chat_id):
                    await update.message.reply_text(f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> ربات دسترسی {"بن کردن" if action=="ban" else "سکوت کردن"} را ندارد.</b>', parse_mode=ParseMode.HTML); return
                db.setdefault("members", {})[str(uid)] = {"username": uname, "fullname": name}
                if action in ("unban", "unmute"):
                    try:
                        if action == "unban": await context.bot.unban_chat_member(chat_id, uid, only_if_banned=True)
                        else: await context.bot.restrict_chat_member(chat_id, uid, permissions=full_group_permissions())
                    except Exception:
                        await update.message.reply_text(f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> ربات دسترسی اجرای این عملیات را ندارد.</b>', parse_mode=ParseMode.HTML); return
                    g_data["banned_users"].pop(str(uid), None); g_data["muted_users"].pop(str(uid), None)
                    mark_db_dirty(); save_db(force=True)
                    result_msg = await update.message.reply_text(f'<b>› <tg-emoji emoji-id="{PREMIUM_USER_EMOJI}">👤</tg-emoji> کاربر {get_user_mention(uid,name)}</b>\n\n<b>›› <tg-emoji emoji-id="{PREMIUM_OK_EMOJI}">✔️</tg-emoji> از {"مسدودیت" if action=="unban" else "سکوت"} خارج شد!</b>', parse_mode=ParseMode.HTML)
                    g_data.setdefault("moderation_message_targets", {})[str(result_msg.message_id)] = int(uid)
                    mark_db_dirty(); save_db(force=True)
                    return
                # Empty duration (including reply with no duration) is always permanent.
                if not duration_arg.strip():
                    seconds, label = None, "دائم"
                else:
                    seconds, label = parse_duration_text(duration_arg, default_permanent=True)
                    if seconds is not None and seconds <= 0:
                        seconds, label = None, "دائم"
                try:
                    if action == "ban":
                        until_dt = moderation_until_datetime(seconds)
                        if until_dt: await context.bot.ban_chat_member(chat_id, uid, until_date=until_dt)
                        else: await context.bot.ban_chat_member(chat_id, uid)
                        g_data["banned_users"][str(uid)] = {"username": uname, "fullname": name, "until": None if seconds is None else datetime.now().timestamp()+seconds, "created_at": datetime.now().timestamp()}
                        phrase = "به‌صورت دائم بن شد." if seconds is None else f"به مدت {label} بن شد."
                    else:
                        until_dt = moderation_until_datetime(seconds)
                        try:
                            if until_dt:
                                await context.bot.restrict_chat_member(
                                    chat_id, uid,
                                    permissions=full_mute_permissions(),
                                    until_date=until_dt
                                )
                            else:
                                await context.bot.restrict_chat_member(
                                    chat_id, uid,
                                    permissions=full_mute_permissions()
                                )
                        except Exception as restrict_error:
                            # Forum topics do not require a thread-specific restriction;
                            # restriction is a chat-level Telegram operation. If the first
                            # request is rejected because of the optional until_date, retry
                            # the same mute without that optional field.
                            if until_dt:
                                logger.warning(
                                    "Timed mute retry without until_date | chat_id=%s user_id=%s topic=%s error=%s",
                                    chat_id, uid, getattr(update.message, "message_thread_id", None), restrict_error
                                )
                                await context.bot.restrict_chat_member(
                                    chat_id, uid,
                                    permissions=full_mute_permissions()
                                )
                            else:
                                raise
                        g_data["muted_users"][str(uid)] = {"username": uname, "fullname": name, "until": None if seconds is None else datetime.now().timestamp()+seconds, "created_at": datetime.now().timestamp()}
                        phrase = "به‌صورت دائم سکوت شد." if seconds is None else f"به مدت {label} سکوت شد."
                    mark_db_dirty(); save_db(force=True)
                    result_msg = await update.message.reply_text(
                        f'<b>› <tg-emoji emoji-id="{PREMIUM_USER_EMOJI}">👤</tg-emoji> {get_user_mention(uid,name)}</b>\n\n'
                        f'<b>›› <tg-emoji emoji-id="{PREMIUM_OK_EMOJI}">✔️</tg-emoji> {phrase}</b>',
                        parse_mode=ParseMode.HTML
                    )
                    g_data.setdefault("moderation_message_targets", {})[str(result_msg.message_id)] = int(uid)
                    mark_db_dirty(); save_db(force=True)
                except Exception:
                    await update.message.reply_text(f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> ربات دسترسی اجرای این عملیات را ندارد.</b>', parse_mode=ParseMode.HTML)
                return

        # --------------------------------------
        # 1. TEXT LOCK CONTROL COMMANDS (ADMIN ONLY - IN GROUP)
        # --------------------------------------
        if is_group and await is_configured_group_manager(context, chat_id, user_id):
            clean_cmd = re.sub(r"[!/؟?؛\-_]", "", clean_raw).strip()
            clean_cmd = re.sub(r"\s+", " ", clean_cmd)
            
            match_lock = LOCK_COMMAND_PATTERN.match(clean_cmd)
            if match_lock:
                verb1, target1, target2, _, verb2 = match_lock.groups()
                action_text = (verb1 or verb2 or "").strip()
                raw_target = (target1 or target2 or "").strip()

                if raw_target.startswith("قفل "):
                    raw_target = raw_target[4:].strip()

                lock_action = None
                if action_text in ["قفل", "ببند", "قفل کن"]:
                    lock_action = True
                elif action_text in ["باز کن", "بازکن", "حذف قفل", "بازکردن قفل"]:
                    lock_action = False

                if lock_action is not None and raw_target:
                    lock_key = LOCK_TEXT_ALIASES.get(raw_target)
                    if not lock_key:
                        for k, v in ALL_LOCKS.items():
                            if not v.get("is_category") and raw_target == v["name"]:
                                lock_key = k
                                break

                    if lock_key and lock_key in ALL_LOCKS and not ALL_LOCKS[lock_key].get("is_category"):
                        g_data = get_group_data(db, chat_id)
                        locks = g_data.setdefault("locks", get_default_locks_structure())
                        current_state = bool(locks.get(lock_key, False))
                        fa_name = ALL_LOCKS[lock_key]["name"]

                        if lock_action:
                            try:
                                bot_member = await cached_chat_member(context, chat_id, context.bot.id)
                                if bot_member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
                                    await update.message.reply_text(
                                        f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> ربات ادمین گروه نیست.</b>',
                                        parse_mode=ParseMode.HTML
                                    )
                                    return
                            except Exception:
                                await update.message.reply_text(
                                    f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> ربات ادمین گروه نیست.</b>',
                                    parse_mode=ParseMode.HTML
                                )
                                return

                        if current_state == lock_action:
                            if lock_action:
                                reply_text = f'قفل {fa_name} از قبل فعال بود. <tg-emoji emoji-id="{CHECK_CUSTOM_EMOJI_ID}">✅</tg-emoji>'
                            else:
                                reply_text = f'قفل {fa_name} از قبل غیرفعال بود. <tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji>'
                            await update.message.reply_text(reply_text, parse_mode=ParseMode.HTML)
                            return

                        locks[lock_key] = lock_action
                        mark_db_dirty()
                        save_db(force=True)

                        action_word = "فعال" if lock_action else "غیرفعال"
                        log_admin_action(db, user_id, update.effective_user.full_name, chat.title, chat_id, f"دستور متنی {fa_name}", f"وضعیت: {action_word}")

                        if lock_action:
                            reply_text = f'قفل {fa_name} با موفقیت فعال شد. <tg-emoji emoji-id="{CHECK_CUSTOM_EMOJI_ID}">✅</tg-emoji>'
                        else:
                            reply_text = f'قفل {fa_name} با موفقیت غیرفعال شد. <tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji>'

                        await update.message.reply_text(reply_text, parse_mode=ParseMode.HTML)
                        return

        # --------------------------------------
        # OWNER FLOWS IN PV / SPECIFIC SESSIONS
        # --------------------------------------
        if int(user_id) == int(OWNER_ID):
            ban_flows = db.setdefault("states", {}).setdefault("ban_flow", {})
            
            if session_k in ban_flows:
                flow = ban_flows[session_k]
                step = flow.get("step")

                if step == "ban_user_id":
                    target_uid_str = fa_to_en_digits(raw_text.strip())
                    if not target_uid_str.isdigit():
                        kb = InlineKeyboardMarkup([[InlineKeyboardButton(" لغو", callback_data="cancel_current_flow", style="danger")]])
                        await update.message.reply_text(
                            f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> لطفاً یک آیدی عددی معتبر ارسال کنید:</b>',
                            reply_markup=kb,
                            parse_mode=ParseMode.HTML
                        )
                        return

                    target_uid = int(target_uid_str)
                    if target_uid == int(OWNER_ID):
                        clear_user_all_states(db, user_id, chat_id)
                        await update.message.reply_text(
                            f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> شما نمی‌توانید مالک اصلی ربات را بن کنید!</b>',
                            parse_mode=ParseMode.HTML
                        )
                        return

                    flow["step"] = "ban_user_reason"
                    flow["target_uid"] = target_uid
                    mark_db_dirty()
                    save_db()

                    kb = InlineKeyboardMarkup([[InlineKeyboardButton(" لغو", callback_data="cancel_current_flow", style="danger")]])
                    await update.message.reply_text("دلیل بن را ارسال کنید:", reply_markup=kb)
                    return

                elif step == "ban_user_reason":
                    flow["reason"] = raw_text.strip()
                    flow["step"] = "ban_user_duration"
                    mark_db_dirty()
                    save_db()

                    kb = InlineKeyboardMarkup([[InlineKeyboardButton(" لغو", callback_data="cancel_current_flow", style="danger")]])
                    await update.message.reply_text(
                        "مدت زمان بن را بر حسب دقیقه وارد کنید.\n"
                        "برای بن دائم بنویسید:\n"
                        "دائم / دائمی / همیشه / همیشگی",
                        reply_markup=kb
                    )
                    return

                elif step == "ban_user_duration":
                    target_uid = flow["target_uid"]
                    reason = flow["reason"]
                    dur_clean = raw_text.strip().lower()
                    perm_triggers = ["دائم", "دائمی", "همیشه", "همیشگی", "permanent", "forever"]

                    now_dt = datetime.now()
                    now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")

                    # Empty/zero duration means permanent. Never fall back to 1 or 60 minutes.
                    if not dur_clean or dur_clean in perm_triggers:
                        b_type = "permanent"
                        b_until = None
                        dur_display = "دائم"
                    else:
                        min_str = fa_to_en_digits(dur_clean)
                        try:
                            minutes = int(min_str)
                        except ValueError:
                            minutes = 0
                        if minutes <= 0:
                            b_type = "permanent"
                            b_until = None
                            dur_display = "دائم"
                        else:
                            b_type = "temporary"
                            b_until = now_dt.timestamp() + (minutes * 60)
                            dur_display = f"{minutes} دقیقه"

                    db["global_bans"][str(target_uid)] = {
                        "type": b_type,
                        "banned_at": now_str,
                        "ban_until": b_until,
                        "reason": reason
                    }

                    clear_user_all_states(db, user_id, chat_id)
                    mark_db_dirty()
                    save_db(force=True)

                    pv_sent = await send_premium_ban_notification(
                        context.bot,
                        target_uid,
                        is_group=False,
                        duration_str=dur_display,
                        reason_str=reason
                    )

                    report_status = " پیام به PV کاربر ارسال شد." if pv_sent else " کاربر بن شد ولی ارسال پیام به PV ناموفق بود."
                    await update.message.reply_text(
                        f" <b>کاربر <code>{target_uid}</code> با موفقیت بن شد.</b>\n"
                        f"⏰ مدت: <b>{dur_display}</b>\n"
                        f" دلیل: <b>{html.escape(reason)}</b>\n\n{report_status}",
                        parse_mode=ParseMode.HTML
                    )
                    return

                elif step == "unban_user_id":
                    target_uid_str = fa_to_en_digits(raw_text.strip())
                    clear_user_all_states(db, user_id, chat_id)

                    if target_uid_str not in db.get("global_bans", {}):
                        await update.message.reply_text(
                            f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> این کاربر بن نیست.</b>',
                            parse_mode=ParseMode.HTML
                        )
                    else:
                        del db["global_bans"][target_uid_str]
                        mark_db_dirty()
                        save_db(force=True)

                        await send_premium_unban_notification(context.bot, int(target_uid_str), is_group=False)
                        await update.message.reply_text(f" بن کاربر <code>{target_uid_str}</code> با موفقیت برداشته شد.", parse_mode=ParseMode.HTML)
                    return

                elif step == "ban_group_reason":
                    flow["reason"] = raw_text.strip()
                    flow["step"] = "ban_group_duration"
                    mark_db_dirty()
                    save_db()

                    kb = InlineKeyboardMarkup([[InlineKeyboardButton(" لغو", callback_data="cancel_current_flow", style="danger")]])
                    await update.message.reply_text(
                        "مدت زمان بن گروه را بر حسب دقیقه وارد کنید.\n"
                        "برای بن دائم بنویسید:\n"
                        "دائم / دائمی / همیشه / همیشگی",
                        reply_markup=kb
                    )
                    return

                elif step == "ban_group_duration":
                    target_cid = flow["target_cid"]
                    reason = flow["reason"]
                    dur_clean = raw_text.strip().lower()
                    perm_triggers = ["دائم", "دائمی", "همیشه", "همیشگی", "permanent", "forever"]

                    now_dt = datetime.now()
                    now_str = now_dt.strftime("%Y-%m-%d %H:%M:%S")

                    # Empty/zero duration means permanent. Never fall back to 1 or 120 minutes.
                    if not dur_clean or dur_clean in perm_triggers:
                        b_type = "permanent"
                        b_until = None
                        dur_display = "دائم"
                    else:
                        min_str = fa_to_en_digits(dur_clean)
                        try:
                            minutes = int(min_str)
                        except ValueError:
                            minutes = 0
                        if minutes <= 0:
                            b_type = "permanent"
                            b_until = None
                            dur_display = "دائم"
                        else:
                            b_type = "temporary"
                            b_until = now_dt.timestamp() + (minutes * 60)
                            dur_display = f"{minutes} دقیقه"

                    db["global_group_bans"][str(target_cid)] = {
                        "type": b_type,
                        "banned_at": now_str,
                        "ban_until": b_until,
                        "reason": reason
                    }

                    clear_user_all_states(db, user_id, chat_id)
                    mark_db_dirty()
                    save_db(force=True)

                    await send_premium_ban_notification(context.bot, target_cid, is_group=True, duration_str=dur_display, reason_str=reason)
                    await update.message.reply_text(f" <b>گروه <code>{target_cid}</code> با موفقیت بن شد.</b>\nمدت: <b>{dur_display}</b>", parse_mode=ParseMode.HTML)
                    return

            if u_str in db["states"].get("waiting_lef_media", {}):
                del db["states"]["waiting_lef_media"][u_str]
                payload = extract_media_payload(update.message)
                if not payload:
                    await update.message.reply_text(
                        f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> این نوع پیام قابل ذخیره برای رسانه لف نیست.</b>',
                        parse_mode=ParseMode.HTML
                    )
                    return
                db["media_lef"] = payload
                mark_db_dirty()
                save_db(force=True)
                await update.message.reply_text(
                    '<b>رسانه لف با موفقیت ذخیره شد. از این به بعد پیام‌های لف با همین رسانه روی کاربر ریپلای می‌شوند. </b>',
                    parse_mode=ParseMode.HTML
                )
                return

            if u_str in db["states"].get("waiting_fun_named_msg", {}):
                payload = extract_media_payload(update.message)
                if payload:
                    db.setdefault("global_fun_named", []).append(payload)
                    mark_db_dirty()
                    save_db(force=True)
                    kb = InlineKeyboardMarkup([[InlineKeyboardButton(" دان", callback_data="own_fun_done:named", style="success")]])
                    await update.message.reply_text(f" پاسخ فحش ناموسی ذخیره شد (کل: {len(db['global_fun_named'])}).", reply_markup=kb, parse_mode=ParseMode.HTML)
                    return

            if u_str in db["states"].get("waiting_fun_normal_msg", {}):
                payload = extract_media_payload(update.message)
                if payload:
                    db.setdefault("global_fun_normal", []).append(payload)
                    mark_db_dirty()
                    save_db(force=True)
                    kb = InlineKeyboardMarkup([[InlineKeyboardButton(" دان", callback_data="own_fun_done:normal", style="success")]])
                    await update.message.reply_text(f" پاسخ فحش عادی ذخیره شد (کل: {len(db['global_fun_normal'])}).", reply_markup=kb, parse_mode=ParseMode.HTML)
                    return

            if u_str in db["states"].get("waiting_shutdown_msg", {}):
                del db["states"]["waiting_shutdown_msg"][u_str]
                db["bot_shutdown"] = True
                payload = extract_media_payload(update.message)
                db["shutdown_message"] = {
                    "from_chat_id": update.effective_chat.id,
                    "message_id": update.message.message_id,
                    "payload": payload
                }
                mark_db_dirty()
                save_db(force=True)
                await update.message.reply_text(" <b>ربات با موفقیت خاموش شد و پیام خاموشی ذخیره گردید.</b>", parse_mode=ParseMode.HTML)
                return

            if u_str in db["states"].get("waiting_cooldown", {}):
                del db["states"]["waiting_cooldown"][u_str]
                try:
                    mins = int(fa_to_en_digits(raw_text.strip()))
                    if mins < 0 or mins > 1440:
                        raise ValueError("cooldown out of range")
                    db["cooldown_minutes"] = mins
                    mark_db_dirty()
                    save_db(force=True)
                    await update.message.reply_text(f" زمان محدودیت (Cooldown) به {mins} دقیقه تغییر یافت.")
                except Exception:
                    await update.message.reply_text(
                        f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> مقدار وارد شده نامعتبر است.</b>',
                        parse_mode=ParseMode.HTML
                    )
                return
            
            if u_str in db["states"].get("waiting_owner_add_poem", {}):
                del db["states"]["waiting_owner_add_poem"][u_str]
                if raw_text and not raw_text.startswith("/"):
                    poem_item = raw_text.strip().replace("یوزرنیم", "{name}")
                    p_list = db.setdefault("global_poems", list(DEFAULT_POEMS))
                    p_list.append(poem_item)
                    mark_db_dirty()
                    save_db(force=True)
                    await update.message.reply_text(" شعر جدید سراسری با موفقیت اضافه شد.")
                    return

            if u_str in db["states"].get("waiting_owner_add_food", {}):
                del db["states"]["waiting_owner_add_food"][u_str]
                if raw_text and not raw_text.startswith("/"):
                    food_item = raw_text.strip()
                    foods = db.setdefault("global_foods", list(DEFAULT_FOODS))
                    if food_item.lower() not in [f.strip().lower() for f in foods]:
                        foods.append(food_item)
                        mark_db_dirty()
                        save_db(force=True)
                        await update.message.reply_text(f" «{food_item}» به منوی سراسری غذاها اضافه شد.")
                    else:
                        await update.message.reply_text(" این غذا از قبل در لیست وجود داشته است.")
                    return

            if u_str in db["states"].get("waiting_search_query", {}):
                target_cid = db["states"]["waiting_search_query"][u_str]
                del db["states"]["waiting_search_query"][u_str]
                mark_db_dirty()
                save_db()

                query_word = raw_text.strip().lower()
                g_data = get_group_data(db, target_cid)
                m_logs = g_data.get("message_logs", [])
                matches = [m for m in m_logs if query_word and query_word in str(m.get("text", "")).lower()][:2000]

                report_lines = [
                    "SEARCH REPORT",
                    "=============",
                    f"Group: {g_data.get('title', 'Unknown')}",
                    f"Chat ID: {target_cid}",
                    f"Query: {query_word}",
                    f"Total Matched: {len(matches)}",
                    "",
                    "RESULTS",
                    "======="
                ]

                for idx, m in enumerate(matches, 1):
                    report_lines.append(f"{idx}.")
                    report_lines.append(f"Message ID: {m['message_id']}")
                    report_lines.append(f"User: {m['user_name']}")
                    report_lines.append(f"User ID: {m['user_id']}")
                    report_lines.append(f"Date: {m['date']}")
                    report_lines.append(f"Text: {m['text']}")
                    if m.get("media_type") != "text":
                        report_lines.append(f"Media Type: {m['media_type']}")
                        report_lines.append(f"File ID: {m.get('file_id')}")
                    report_lines.append("")

                report_content = "\n".join(report_lines)
                # Keep report payload bounded even if the underlying log grows.
                report_content = report_content[:2_000_000]
                file_bytes = io.BytesIO(report_content.encode("utf-8"))
                file_bytes.name = f"search_{target_cid}.txt"
                await update.message.reply_document(document=file_bytes, caption=f" نتایج جستجوی <code>{query_word}</code>", parse_mode=ParseMode.HTML)
                return

            if u_str in db["states"].get("broadcast_builder", {}):
                builder = db["states"]["broadcast_builder"][u_str]
                mode = builder.get("mode")

                if mode == "media":
                    payload = extract_media_payload(update.message)
                    if payload:
                        builder["type"] = "media"
                        builder["payload"] = payload
                        kb = InlineKeyboardMarkup([
                            [InlineKeyboardButton(" تأیید و ارسال همگانی", callback_data="bcast_confirm_send", style="success")],
                            [InlineKeyboardButton(" لغو", callback_data="bcast_cancel", style="danger")]
                        ])
                        await update.message.reply_text(" <b>پیش‌نمایش مدیا دریافت شد. آیا برای ارسال تأیید می‌کنید؟</b>", reply_markup=kb, parse_mode=ParseMode.HTML)
                        return

                elif mode in ["poll", "quiz"]:
                    lines = [l.strip() for l in raw_text.strip().split("\n") if l.strip()]
                    if len(lines) < 3:
                        await update.message.reply_text(
                            f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> حداقل سؤال و ۲ گزینه الزامی است.</b>',
                            parse_mode=ParseMode.HTML
                        )
                        return

                    question = lines[0]
                    correct_id = 0
                    if mode == "quiz":
                        last_line = lines[-1]
                        if "صحیح:" in last_line:
                            try:
                                correct_id = int(fa_to_en_digits(last_line.replace("صحیح:", "").strip())) - 1
                                options = lines[1:-1]
                            except Exception:
                                options = lines[1:]
                        else:
                            options = lines[1:]
                    else:
                        options = lines[1:]

                    builder["type"] = "poll"
                    builder["poll_data"] = {
                        "question": question,
                        "options": options,
                        "is_anonymous": True,
                        "is_quiz": (mode == "quiz"),
                        "correct_option_id": correct_id if mode == "quiz" else None
                    }

                    kb = InlineKeyboardMarkup([
                        [InlineKeyboardButton(" تأیید و ارسال به همه", callback_data="bcast_confirm_send", style="success")],
                        [InlineKeyboardButton(" لغو", callback_data="bcast_cancel", style="danger")]
                    ])
                    await context.bot.send_poll(
                        chat_id=update.effective_chat.id,
                        question=question,
                        options=options,
                        type=PollType.QUIZ if mode == "quiz" else PollType.REGULAR,
                        correct_option_id=correct_id if mode == "quiz" else None
                    )
                    await update.message.reply_text(" <b>پیش‌نمایش نظرسنجی بالا را مشاهده می‌کنید. تأیید برای ارسال همگانی؟</b>", reply_markup=kb, parse_mode=ParseMode.HTML)
                    return

            if u_str in db["states"].get("waiting_user_broadcast_msg", {}):
                del db["states"]["waiting_user_broadcast_msg"][u_str]
                payload = extract_media_payload(update.message)
                if not payload:
                    await update.message.reply_text(
                        f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> پیامی دریافت نشد.</b>',
                        parse_mode=ParseMode.HTML
                    )
                    return

                started_users = db.get("started_users", {})
                succ, fail = 0, 0
                status_msg = await update.message.reply_text("⏳ در حال ارسال همگانی...")
                for uid_k in started_users.keys():
                    try:
                        await send_media_payload(context.bot, int(uid_k), payload)
                        succ += 1
                        await asyncio.sleep(0.04)
                    except Exception:
                        fail += 1

                await status_msg.edit_text(f" ارسال به اتمام رسید.\n\nموفق: {succ}\nناموفق: {fail}")
                return

        # --------------------------------------
        # HANDLER CLEANUP (GROUP ONLY)
        # --------------------------------------
        match_cleanup = CLEANUP_PATTERN.match(raw_text)
        if match_cleanup:
            if not is_group:
                return
            if not await is_admin_or_owner(context, chat_id, user_id):
                await update.message.reply_text(
                    f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> فقط مدیران گروه دسترسی اجرای این دستور را دارند.</b>',
                    parse_mode=ParseMode.HTML
                )
                return

            count_str = match_cleanup.group("count")
            if not count_str or not count_str.isdigit() or int(count_str) <= 0:
                await update.message.reply_text("<b>فرمت دستور پاکسازی اشتباه است!\nمثال: <code>حذف 20</code></b>", parse_mode=ParseMode.HTML)
                return

            req_count = int(count_str)
            target_msg_id = update.message.message_id
            deleted_count = 0
            try:
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=target_msg_id)
                except Exception:
                    pass

                for i in range(1, req_count + 1):
                    msg_id_to_del = target_msg_id - i
                    if msg_id_to_del <= 0:
                        break
                    try:
                        await context.bot.delete_message(chat_id=chat_id, message_id=msg_id_to_del)
                        deleted_count += 1
                        await asyncio.sleep(0.02)
                    except Exception as e:
                        err_s = str(e).lower()
                        if "message to delete not found" in err_s or "message can't be deleted" in err_s:
                            continue
                        elif "chat_admin_required" in err_s:
                            await update.message.reply_text(
                                f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> ربات دسترسی حذف پیام‌ها را ندارد.</b>',
                                parse_mode=ParseMode.HTML
                            )
                            return
                        break

                log_admin_action(db, user_id, update.effective_user.full_name, update.effective_chat.title, chat_id, "پاکسازی", f"پاکسازی {deleted_count} پیام اخیر")
                confirm_msg = await context.bot.send_message(
                    chat_id=chat_id,
                    text=f'<b>پاکسازی {deleted_count} پیام اخیر انجام شد! <tg-emoji emoji-id="{CLEANUP_CUSTOM_EMOJI_ID}">📝</tg-emoji></b>',
                    parse_mode=ParseMode.HTML
                )
                await asyncio.sleep(5)
                try:
                    await context.bot.delete_message(chat_id=chat_id, message_id=confirm_msg.message_id)
                except Exception:
                    pass
            except Exception as e:
                logger.error(f"Cleanup Error: {e}")
            return

        # --------------------------------------
        # HANDLER FUN COMMANDS: «ناموسی بده» & «فحش بده» (GROUP ONLY)
        # --------------------------------------
        match_fun_named = FUN_NAMED_PATTERN.match(raw_text)
        match_fun_normal = FUN_NORMAL_PATTERN.match(raw_text)

        if match_fun_named or match_fun_normal:
            if not is_group:
                return

            is_named = bool(match_fun_named)
            match_obj = match_fun_named if is_named else match_fun_normal
            cnt_str = match_obj.group("count")
            req_cnt = int(cnt_str) if cnt_str else 1
            req_cnt = min(req_cnt, MAX_FUN_MESSAGES)

            if update.message.reply_to_message and update.message.reply_to_message.from_user and update.message.reply_to_message.from_user.id == context.bot.id:
                await update.message.reply_text('<b>منظورت چیه؟ <tg-emoji emoji-id="5829923384217050622">❓</tg-emoji></b>', parse_mode=ParseMode.HTML)
                return

            g_data = get_group_data(db, chat_id)
            key_grp = "fun_named_responses" if is_named else "fun_normal_responses"
            key_glob = "global_fun_named" if is_named else "global_fun_normal"
            responses_list = g_data.get(key_grp, []) or db.get(key_glob, [])

            if not responses_list:
                title = "ناموسی" if is_named else "عادی"
                await update.message.reply_text(f"<b>هنوز هیچ پاسخ فحش {title} برای ربات ثبت نشده است!</b>", parse_mode=ParseMode.HTML)
                return

            target_msg_id = update.message.reply_to_message.message_id if update.message.reply_to_message else None
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=update.message.message_id)
            except Exception:
                pass

            for _ in range(req_cnt):
                resp_payload = random.choice(responses_list)
                await send_media_payload(context.bot, chat_id, resp_payload, reply_to_message_id=target_msg_id)
                await asyncio.sleep(0.3)
            return

        # --------------------------------------
        # HANDLER PIN / UNPIN COMMANDS (GROUP ONLY)
        # --------------------------------------
        if clean_raw in PIN_PATTERNS or clean_raw in UNPIN_PATTERNS:
            if not is_group:
                return
            if not await is_admin_or_owner(context, chat_id, user_id):
                await update.message.reply_text(
                    f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> فقط مدیران گروه دسترسی اجرای این دستور را دارند.</b>',
                    parse_mode=ParseMode.HTML
                )
                return

            if not update.message.reply_to_message:
                await update.message.reply_text("<b>برای استفاده از این دستور باید روی پیام مورد نظر ریپلای کنید!</b>", parse_mode=ParseMode.HTML)
                return

            target_msg_id = update.message.reply_to_message.message_id
            if clean_raw in PIN_PATTERNS:
                try:
                    await context.bot.pin_chat_message(chat_id=chat_id, message_id=target_msg_id)
                    log_admin_action(db, user_id, update.effective_user.full_name, update.effective_chat.title, chat_id, "پین پیام", f"Message ID: {target_msg_id}")
                    await update.message.reply_text('<b>پیامتو پین کردم عزیزم! <tg-emoji emoji-id="5870593825407243361">👋</tg-emoji></b>', parse_mode=ParseMode.HTML)
                except Exception:
                    await update.message.reply_text(
                        f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> ربات دسترسی سنجاق کردن پیام‌ها را ندارد.</b>',
                        parse_mode=ParseMode.HTML
                    )
                return
            elif clean_raw in UNPIN_PATTERNS:
                try:
                    await context.bot.unpin_chat_message(chat_id=chat_id, message_id=target_msg_id)
                    log_admin_action(db, user_id, update.effective_user.full_name, update.effective_chat.title, chat_id, "آن‌پین پیام", f"Message ID: {target_msg_id}")
                    await update.message.reply_text('<b>پیامو از پین دراوردم رفیق! <tg-emoji emoji-id="5870593825407243361">👋</tg-emoji></b>', parse_mode=ParseMode.HTML)
                except Exception:
                    await update.message.reply_text(
                        f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> ربات دسترسی تغییر پیام‌های سنجاق‌شده را ندارد.</b>',
                        parse_mode=ParseMode.HTML
                    )
                return

        # --------------------------------------
        # CHANNEL COMMENT COMMANDS (GROUP ONLY)
        # --------------------------------------
        if is_group and is_comment_list_command(clean_raw):
            if not await is_admin_or_owner(context, chat_id, user_id):
                await update.message.reply_text(
                    f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> فقط مدیران گروه دسترسی به این دستور را دارند.</b>',
                    parse_mode=ParseMode.HTML)
                return
            g = get_group_data(db, chat_id)
            # Command-created list view is owned by the sender.
            text = comment_list_text(g)
            sent = await update.message.reply_text(
                text,
                reply_markup=comment_close_keyboard(f"comment_cmd_close:{chat_id}:{user_id}"),
                parse_mode=ParseMode.HTML)
            set_comment_panel_session(db, user_id, chat_id, sent.message_id)
            save_db(force=True)
            return

        if is_group and is_comment_on_command(clean_raw):
            await activate_comments(update, context, chat_id, user_id)
            return

        if is_group and is_comment_off_command(clean_raw):
            await deactivate_comments(update, context, chat_id, user_id)
            return

        if is_group and is_comment_delete_command(clean_raw):
            if not await is_admin_or_owner(context, chat_id, user_id):
                await update.message.reply_text(
                    f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> فقط مدیران گروه دسترسی به این دستور را دارند.</b>',
                    parse_mode=ParseMode.HTML)
                return
            # Use a command-owned confirmation message, not the lists panel.
            sent = await update.message.reply_text(
                '<b>آیا از حذف کامل کامنت ذخیره‌شده مطمئن هستید؟</b>',
                reply_markup=InlineKeyboardMarkup([[
                    InlineKeyboardButton("بله", callback_data=f"comment_cmd_cleanup:yes:{chat_id}:{user_id}", style="success", icon_custom_emoji_id=CHECK_CUSTOM_EMOJI_ID),
                    InlineKeyboardButton("بستن", callback_data=f"comment_cmd_cleanup:no:{chat_id}:{user_id}", style="danger", icon_custom_emoji_id=CROSS_CUSTOM_EMOJI_ID)
                ]]), parse_mode=ParseMode.HTML)
            set_comment_panel_session(db, user_id, chat_id, sent.message_id)
            save_db(force=True)
            return

        if is_group and clean_raw in ["پنل", "admin", "/admin"]:
            if not await is_configured_group_manager(context, chat_id, user_id):
                await update.message.reply_text(
                    f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> شما دسترسی مدیریت این گروه را ندارید.</b>',
                    parse_mode=ParseMode.HTML
                )
                return
            await command_admin_panel(update, context)
            return

        if u_str in db["states"].get("waiting_check_user", {}):
            # One-shot: consume the pending check before validating the input.
            state = db["states"]["waiting_check_user"].pop(u_str)
            mark_db_dirty(); save_db(force=True)

            if isinstance(state, dict):
                target_cid = int(state.get("chat_id", chat_id))
                panel_message_id = state.get("panel_message_id")
                return_to_advanced = bool(state.get("return_to_advanced", False))
            else:
                target_cid = int(state)
                panel_message_id = None
                return_to_advanced = True

            if raw_text.strip().lower() in ["لغو", "cancel"]:
                cancel_text = f'<tg-emoji emoji-id="{CHECK_CUSTOM_EMOJI_ID}">✅</tg-emoji> <b>بررسی کاربر لغو شد.</b>'
                try:
                    if return_to_advanced and await is_admin_or_owner(context, target_cid, user_id):
                        cancel_text += "\n\n" + get_advanced_status_text(db, target_cid)
                        await context.bot.edit_message_text(chat_id=chat_id, message_id=panel_message_id, text=cancel_text, reply_markup=build_advanced_panel_keyboard(target_cid), parse_mode=ParseMode.HTML)
                    else:
                        await context.bot.edit_message_text(chat_id=chat_id, message_id=panel_message_id, text=cancel_text, reply_markup=None, parse_mode=ParseMode.HTML)
                except Exception:
                    await update.message.reply_text(cancel_text, parse_mode=ParseMode.HTML)
                return

            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=panel_message_id,
                    text=build_check_user_loading_text(),
                    reply_markup=None,
                    parse_mode=ParseMode.HTML
                )
            except Exception:
                pass

            target_user = await resolve_check_user(context, db, target_cid, raw_text)
            if not target_user:
                final_text = build_check_user_not_found_text()
                final_markup = build_check_user_keyboard()
                try:
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=panel_message_id,
                        text=final_text,
                        reply_markup=final_markup,
                        parse_mode=ParseMode.HTML
                    )
                except Exception:
                    await update.message.reply_text(final_text, reply_markup=final_markup, parse_mode=ParseMode.HTML)
                return

            uid = int(target_user.id)
            uid_str_target = str(uid)
            member_data = db.get("members", {}).get(uid_str_target, {})
            target_name = (getattr(target_user, "full_name", None) or (target_user.get("full_name") if isinstance(target_user, dict) else None) or member_data.get("fullname") or "کاربر")
            target_username = ((getattr(target_user, "username", None) if not isinstance(target_user, dict) else target_user.get("username")) or member_data.get("username") or "")
            db.setdefault("members", {})[uid_str_target] = {"username": target_username, "fullname": target_name}
            record = get_group_user_record(db, target_cid, uid) if target_cid else {"first_joined_at": None, "ban_count": 0, "last_ban_at": None, "mute_count": 0, "last_mute_at": None}
            try:
                member = await cached_chat_member(context, target_cid, uid)
                status = member.status
            except Exception:
                member = None; status = None
            if status == ChatMemberStatus.BANNED:
                current_status = "بن"
            elif status == ChatMemberStatus.RESTRICTED:
                current_status = "سکوت" if _restricted_is_muted(member) else "بدون مجازات"
            else:
                current_status = "بدون مجازات"
            if uid == int(OWNER_ID) or status == ChatMemberStatus.OWNER:
                rank_text = "مالک"
            elif status == ChatMemberStatus.ADMINISTRATOR:
                rank_text = "ادمین"
            else:
                rank_text = "عضو عادی"
            join_text = format_user_event_time(record["first_joined_at"]) if record.get("first_joined_at") else "ثبت نشده"
            last_ban_text = format_user_event_time(record["last_ban_at"]) if record.get("last_ban_at") else "ندارد"
            last_mute_text = format_user_event_time(record["last_mute_at"]) if record.get("last_mute_at") else "ندارد"
            username_display = f"@{html.escape(target_username)}" if target_username else "ندارد"
            name_display = html.escape(target_name)
            info_text = (
                f'<tg-emoji emoji-id="5884362854903064294">📚</tg-emoji> <b>بررسی کاربر</b>\n\n'
                f'<tg-emoji emoji-id="6008124493610885197">🔗</tg-emoji> <b>نام :</b> {name_display}\n'
                f'<tg-emoji emoji-id="6008341333624758856">💎</tg-emoji> <b>آیدی تلگرام :</b> {username_display}\n'
                f'<tg-emoji emoji-id="6008070651900861977">📤</tg-emoji> <b>آیدی عددی تلگرام :</b> <code>{uid}</code>\n'
                f'<tg-emoji emoji-id="6008261704931089837">📆</tg-emoji> <b>تاریخ عضویت در گروه :</b> {join_text}\n'
                f'<tg-emoji emoji-id="5873075766748520540">⛔️</tg-emoji> <b>تعداد بار‌های بن شدن :</b> {int(record.get("ban_count", 0))}\n'
                f'<tg-emoji emoji-id="6007982695265608502">⏰</tg-emoji> <b>آخرین بن از گروه :</b> {last_ban_text}\n'
                f'<tg-emoji emoji-id="5875037024909532569">😴</tg-emoji> <b>تعداد بارهای سکوت شدن :</b> {int(record.get("mute_count", 0))}\n'
                f'<tg-emoji emoji-id="6007923248623263109">📥</tg-emoji> <b>آخرین سکوت از گروه :</b> {last_mute_text}\n'
                f'<tg-emoji emoji-id="6059658968676961981">🆙</tg-emoji> <b>وضعیت کنونی :</b> {current_status}\n'
                f'<tg-emoji emoji-id="5846195056796509162">🏅</tg-emoji> <b>مقام در ربات و گروه :</b> {rank_text}'
            )
            mark_db_dirty(); save_db(force=True)
            final_text = info_text
            final_markup = InlineKeyboardMarkup([
                [InlineKeyboardButton("بستن", callback_data="check_user_close", style="danger", icon_custom_emoji_id=CLOSE_CUSTOM_EMOJI_ID)],
                [InlineKeyboardButton("بازگشت", callback_data="check_user_back_to_lists", style="danger", icon_custom_emoji_id=BACK_CUSTOM_EMOJI_ID)]
            ])
            try:
                await context.bot.edit_message_text(chat_id=chat_id, message_id=panel_message_id, text=final_text, reply_markup=final_markup, parse_mode=ParseMode.HTML)
            except Exception:
                await update.message.reply_text(final_text, reply_markup=final_markup, parse_mode=ParseMode.HTML)
            return
        if u_str in db["states"].get("waiting_welcome_msg", {}):
            target_cid = db["states"]["waiting_welcome_msg"][u_str]
            if await is_admin_or_owner(context, target_cid, user_id):
                del db["states"]["waiting_welcome_msg"][u_str]
                payload = extract_media_payload(update.message)
                if payload:
                    g_data = get_group_data(db, target_cid)
                    g_data["welcome"] = {"enabled": True, "custom": True, "payload": payload}
                    mark_db_dirty()
                    save_db(force=True)
                    await update.message.reply_text(" <b>پیام و مدیای خوش‌آمدگویی اختصاصی این گروه ذخیره شد!</b>", parse_mode=ParseMode.HTML)
                    return

        if u_str in db["states"].get("waiting_comment_msg", {}):
            comment_state = db["states"]["waiting_comment_msg"][u_str]
            if isinstance(comment_state, dict):
                target_cid = int(comment_state.get("chat_id", 0) or 0)
            else:
                try:
                    target_cid = int(comment_state)
                except Exception:
                    target_cid = 0
            if target_cid and await save_comment_from_message(update, context, target_cid):
                return

        if u_str in db["states"].get("waiting_add_food", {}):
            target_cid = db["states"]["waiting_add_food"][u_str]
            del db["states"]["waiting_add_food"][u_str]
            if raw_text:
                g_data = get_group_data(db, target_cid)
                foods = g_data.setdefault("foods", list(DEFAULT_FOODS))
                food_item = raw_text.strip()
                if food_item.lower() not in [f.strip().lower() for f in foods]:
                    foods.append(food_item)
                    await update.message.reply_text(f" «{food_item}» به منوی این گروه اضافه شد.")
                else:
                    await update.message.reply_text(
                        f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> این غذا قبلاً وجود داشته!</b>',
                        parse_mode=ParseMode.HTML
                    )
                mark_db_dirty()
                save_db(force=True)
                return

        if u_str in db["states"].get("waiting_del_food", {}):
            target_cid = db["states"]["waiting_del_food"][u_str]
            del db["states"]["waiting_del_food"][u_str]
            if raw_text:
                g_data = get_group_data(db, target_cid)
                foods = g_data.setdefault("foods", list(DEFAULT_FOODS))
                food_item = raw_text.strip()
                target_idx = next((i for i, f in enumerate(foods) if f.strip().lower() == food_item.lower()), None)
                if target_idx is not None:
                    rm = foods.pop(target_idx)
                    await update.message.reply_text(f" «{rm}» از لیست این گروه حذف شد.")
                else:
                    await update.message.reply_text(
                        f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> این غذا یافت نشد!</b>',
                        parse_mode=ParseMode.HTML
                    )
                mark_db_dirty()
                save_db(force=True)
                return

        if u_str in db["states"].get("waiting_poem_names", {}):
            target_cid = db["states"]["waiting_poem_names"][u_str]
            if raw_text and not raw_text.startswith("/"):
                g_data = get_group_data(db, target_cid)
                c_names = g_data.setdefault("custom_names", [])
                c_names.append(raw_text.strip())
                mark_db_dirty()
                save_db(force=True)
                await update.message.reply_text(f" اسم «{raw_text.strip()}» برای این گروه ثبت شد. بعدی را بفرستید یا « دان» را بزنید.")
                return

        if u_str in db["states"].get("waiting_add_poem", {}):
            target_cid = db["states"]["waiting_add_poem"][u_str]
            del db["states"]["waiting_add_poem"][u_str]
            if raw_text and not raw_text.startswith("/"):
                poem_item = raw_text.strip().replace("یوزرنیم", "{name}")
                g_data = get_group_data(db, target_cid)
                p_list = g_data.setdefault("poems", list(DEFAULT_POEMS))
                p_list.append(poem_item)
                mark_db_dirty()
                save_db(force=True)
                await update.message.reply_text(" شعر جدید برای این گروه اضافه شد.")
                return

        # --------------------------------------
        # GOODI SUPPORT / CREATOR QUICK REPLY
        # --------------------------------------
        if await handle_goodi_support_quick_reply(update, context):
            return

        features = db.get("features", {})

        # --------------------------------------
        # HELP / راهنما PANEL
        # --------------------------------------
        help_triggers = ["راهنما", "/help", "help", "هلپ", "گودی راهنما", "گودی معرفی کن", "گودی چیا بلدی؟", "چیا بلدی؟", "چیا بلدی", "گودی چیا بلدی"]
        if clean_raw in help_triggers:
            txt = (
                '<b>سلام عزیزم به ربات من خوش اومدی! <tg-emoji emoji-id="5352750090974929602">😍</tg-emoji></b>\n\n'
                '<b>از طریق دکمه‌های زیر میتونی کاملا با گودی که یه اژدها کوچولو هست آشنا بشی! <tg-emoji emoji-id="5884128023271182329">🐉</tg-emoji></b>'
            )
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("راهنمای سرگرمی", callback_data=f"help_fun:{update.effective_user.id}", style="primary", icon_custom_emoji_id="5415940089375106928"),
                 InlineKeyboardButton("راهنمای بی ادبی", callback_data=f"help_rude:{update.effective_user.id}", style="primary", icon_custom_emoji_id="5832633418386513259")],
                [InlineKeyboardButton("راهنمای کاربردی", callback_data=f"help_useful:{update.effective_user.id}", style="primary", icon_custom_emoji_id="5830338333892418460"),
                 InlineKeyboardButton("راهنمای مدیریتی", callback_data=f"help_admin:{update.effective_user.id}", style="primary", icon_custom_emoji_id="5803348359972393936")]
            ])
            await update.message.reply_text(txt, reply_markup=kb, parse_mode=ParseMode.HTML)
            return
        # --------------------------------------
        # REPORT SYSTEM (GROUP ONLY)
        # --------------------------------------
        if is_group and clean_raw in ["گزارش", "report"] and update.message.reply_to_message:
            target_msg = update.message.reply_to_message
            if target_msg.from_user and target_msg.from_user.id == context.bot.id:
                await update.message.reply_text('<b>منو گزارش میدی؟! <tg-emoji emoji-id="5818704981179505821">🕹</tg-emoji></b>', parse_mode=ParseMode.HTML)
                return

            rep_id = f"{chat_id}_{update.message.message_id}"
            reports = db.setdefault("reports", {})
            reports[rep_id] = {"reporter_id": user_id, "target_msg_id": target_msg.message_id}
            mark_db_dirty()
            save_db()

            txt = '<b><tg-emoji emoji-id="5819051035284479206">🚨</tg-emoji> گزارش شما برای مدیران گروه ارسال شد!</b>'
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("بررسی شد", callback_data=f"report_resolve:{rep_id}", style="success", icon_custom_emoji_id="5206607081334906820"),
                 InlineKeyboardButton("حذف", callback_data=f"report_cancel:{rep_id}", style="danger", icon_custom_emoji_id="5819154526816444042")]
            ])
            await update.message.reply_text(txt, reply_markup=kb, parse_mode=ParseMode.HTML)
            return

        # --------------------------------------
        # DODOL / FUN RESPONSE (GROUP ONLY)
        # --------------------------------------
        if is_group and DODOL_PATTERN.search(raw_text):
            ascii_penis = (
                "⣿⣿⣿⣿⣿⣿⣿⣿⣿⠟⠛⢉⢉⢉⢉⠻⣿⣿⣿⣿⣿⣿\n"
                "⣿⣿⣿⣿⣿⣿⣿⠟⠠⡰⣕⣗⣷⣧⣝⣅⠘⣿⣿⣿⣿⣿\n"
                "⣿⣿⣿⣿⣿⣿⠃⣠⣳⣟⣿⣿⣷⣿⡿⣜⠄⣿⣿⣿⣿⣿\n"
                "⣿⣿⣿⣿⠁⠄⣳⢷⣿⣿⣿⣿⡿⣿⣿⣿ ⣿⣿\n"
                "⣿⣿⣿⣿⠃⠄⢢⡹⣿⢷⣯⢿⢷⡫⣗⠍⢰⣿⣿⣿⣿⣿\n"
                "⣿⣿⣿⡏⢀⢄⠤⣁⠋⠿⣗⣟⡯⡏⢎⠁⢸⣿⣿⣿⣿⣿\n"
                "⣿⣿⣿⠄⢔⢕⣯⣿⣿⡲⡤⡄⡤⠄⡀⢠⣿⣿⣿⣿⣿⣿\n"
                "⣿⣿⠇⠠⡳⣯⣿⣿⣾⢵⣫⢎⢎⠆⢀⣿⣿⣿⣿⣿⣿⣿\n"
                "⣿⣿⠄⢨⣫⣿⣿⡿⣿⣻⢎⡗⡕⡅⢸⣿⣿⣿⣿⣿⣿⣿\n"
                "⣿⣿⠄ ⢾⣾⣿⣿⣟⣗⡪⡳⡀⢸⣿⣿⣿⣿⣿⣿⣿\n"
                "⣿⣿⠄⢸⢽⣿⣷⣿⣻⡮⡧⡳⡱⡁⢸⣿⣿⣿⣿⣿⣿⣿\n"
                "⣿⣿⡄⢨⣻⣽⣿⣟⣿⣞⣗⡽⡸⡐⢸⣿⣿⣿⣿⣿⣿⣿\n"
                "⣿⣿⡇⢀⢗⣿⣿⣿⣿⡿⣞⡵⡣⣊⢸⣿⣿⣿⣿⣿⣿⣿\n"
                "⣿⣿⣿⡀⡣⣗⣿⣿⣿⣿⣯⡯⡺⣼⠎⣿⣿⣿⣿⣿⣿⣿\n"
                "⣿⣿⣿⣧⠐⡵⣻⣟⣯⣿⣷⣟⣝⢞⡿⢹⣿⣿⣿⣿⣿⣿\n"
                "⣿⣿⣿⣿⡆⢘⡺⣽⢿⣻⣿⣗⡷⣹⢩⢃⢿⣿⣿⣿⣿⣿\n"
                "⣿⣿⣿⣿⣷⠄⠪⣯⣟⣿⢯⣿⣻⣜⢎⢆⠜⣿⣿⣿⣿⣿\n"
                "⣿⣿⣿⣿⡆⠄⢣⣻⣽⣿⣿⣟⣾⡮⡺⡸⠸⣿⣿⣿⣿⣿\n"
                "⣿⣿⠛⠉⠁⠄⢕⡳⣽⡾⣿⢽⣯⡿⣮⢚⣅⠹⣿⣿⣿\n"
                "⡿⠋⠄⠄⠄⠄⢀⠒⠝⣞⢿⡿⣿⣽⢿⡽⣧⣳⡅⠌⠻⣿\n"
                "⠁⠄⠄⠄⠄⠄⠐⡐⠱⡱⣻⡻⣝⣮⣟⣿⣿⣿⣿⣿⣿⣿"
            )
            clean_ascii = re.sub(r"[a-zA-Z]+", "", ascii_penis)
            msg1 = await update.message.reply_text(f"<code>{clean_ascii}</code>", parse_mode=ParseMode.HTML)
            await msg1.reply_text('<b>میخوریش برام؟؟ <tg-emoji emoji-id="5431423351987916271">👅</tg-emoji></b>', parse_mode=ParseMode.HTML)
            return

        # --------------------------------------
        # BOT NAME RESPONSES (GROUP ONLY)
        # --------------------------------------
        is_reply_to_bot = (
            update.message.reply_to_message and 
            update.message.reply_to_message.from_user and 
            update.message.reply_to_message.from_user.id == context.bot.id
        )

        if is_group and is_reply_to_bot and (clean_raw.startswith("درصد ") or clean_raw.startswith("این چقدر ") or clean_raw.startswith("این چقد ")):
            topic = clean_raw.replace("درصد ", "").replace("این چقدر ", "").replace("این چقد ", "").replace(" بودن", "").replace("ش", "").replace("ه", "").strip()
            await update.message.reply_text(f'<b>{html.escape(topic)} خودتی! <tg-emoji emoji-id="5886539179256450622">🤪</tg-emoji></b>', parse_mode=ParseMode.HTML)
            return

        if is_group and (is_reply_to_bot and clean_raw in ["تو کی هستی", "تو کی هستی؟"]):
            await update.message.reply_text('<b>من گودی هستم خوشگله! <tg-emoji emoji-id="5321415182109401472">😽</tg-emoji></b>', parse_mode=ParseMode.HTML)
            return

        elif is_group and (clean_raw == "گودی" or (is_reply_to_bot and clean_raw in ["گودی", "گودی؟"])):
            await update.message.reply_text('<b>بله خودم هستم چیکارم دارین؟ <tg-emoji emoji-id="5276088141671846201">🌟</tg-emoji></b>', parse_mode=ParseMode.HTML)
            return

        # --------------------------------------
        # ACTION REGISTRATION (GROUP ONLY)
        # --------------------------------------
        action_type = None
        if clean_raw in ["ثبت گوه خوری", "ثبت گوهخوری"]: action_type = "goh_khori"
        elif clean_raw in ["ثبت کصلیسی", "ثبت کص لیسی", "ثبت کسلیسی", "ثبت کس لیسی"]: action_type = "kos_lisi"
        elif clean_raw in ["ثبت خایمالی", "ثبت خایه مالی"]: action_type = "khaymali"
        elif clean_raw in ["ثبت کصخلی", "ثبت کص خلی"]: action_type = "kos_khali"
        elif clean_raw in ["ثبت جندگی", "ثبت جنده گی"]: action_type = "jendegi"

        if action_type:
            if not is_group:
                return
            if not update.message.reply_to_message:
                await update.message.reply_text(
                    f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> برای ثبت باید روی پیام یک نفر ریپلای کنی!</b>',
                    parse_mode=ParseMode.HTML
                )
                return

            target_uid, target_fname, target_uname, target_mention = resolve_target_user(update, context)
            if target_uid:
                if target_uid == context.bot.id:
                    await update.message.reply_text('<b><tg-emoji emoji-id="6041764253726150869">😐</tg-emoji> خیلی کارت زشت بود!</b>', parse_mode=ParseMode.HTML)
                    return
                if target_uid == user_id:
                    await update.message.reply_text('<b><tg-emoji emoji-id="6044308162855571406">😒</tg-emoji> داری سعی میکنی روی خودت انجام بدی؟ خود درگیری داری مگه داداش!</b>', parse_mode=ParseMode.HTML)
                    return

                action_configs = {
                    "goh_khori": {"title": "گوه‌خوری", "stat_key": "goh_khori", "icon_id": "5819051035284479206", "funny_text": "گوه‌خوری نوین مشاهده شد!"},
                    "kos_lisi": {"title": "کصلیسی", "stat_key": "kos_lisi", "icon_id": "5832692422647226240", "funny_text": "مدال شجاعت کصلیسی تعلق گرفت!"},
                    "khaymali": {"title": "خایمالی", "stat_key": "khaymali", "icon_id": "5920300405341820405", "funny_text": "خایمال‌نامه جدید صادر شد!"},
                    "kos_khali": {"title": "کصخلی", "stat_key": "kos_khali", "icon_id": "5443038326535759644", "funny_text": "پرونده پزشکی کصخلی تنظیم شد!"},
                    "jendegi": {"title": "جندگی", "stat_key": "jendegi", "icon_id": "4974615079971455718", "funny_text": "ثبت جندگی جدید در سیستم با موفقیت ثبت شد!"}
                }
                cfg = action_configs[action_type]
                rec_id = f"{chat_id}_{update.message.message_id}"
                
                increment_user_stat(db, target_uid, cfg["stat_key"])
                records = db.setdefault("action_records", {})
                records[rec_id] = {
                    "target_id": target_uid,
                    "target_name": target_fname,
                    "creator_id": user_id,
                    "creator_name": update.effective_user.full_name,
                    "action_title": cfg["title"],
                    "stat_key": cfg["stat_key"],
                    "funny_text": cfg["funny_text"],
                    "signers": []
                }
                mark_db_dirty()
                save_db()

                creator_mention = get_user_mention(user_id, update.effective_user.full_name)
                init_msg = (
                    f"<b>{cfg['title']} {target_mention} با موفقیت ثبت شد! <tg-emoji emoji-id=\"5206607081334906820\">✔️</tg-emoji></b>\n"
                    f"<b>ثبت کننده {cfg['title']}: {creator_mention} <tg-emoji emoji-id=\"4956745198521549627\">🌟</tg-emoji></b>\n"
                    f"<b><tg-emoji emoji-id=\"5803348359972393936\">⚙️</tg-emoji> در انتظار امضای شاهدان...</b>\n\n"
                    f"<b>{cfg['funny_text']} <tg-emoji emoji-id=\"{cfg['icon_id']}\">🔥</tg-emoji></b>"
                )
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("امضای شاهدان (۰)", callback_data=f"sign_action:{rec_id}", style="success", icon_custom_emoji_id="5859527571586161695")],
                    [InlineKeyboardButton(f"آمار کل {cfg['title']} این کاربر", callback_data=f"stat_action:{rec_id}", style="primary", icon_custom_emoji_id="5888937012253171131")]
                ])
                await update.message.reply_text(init_msg, reply_markup=kb, parse_mode=ParseMode.HTML)
                return

        # --------------------------------------
        # STATS & OVERALL USER STATUS (GROUP ONLY)
        # --------------------------------------
        is_asking_own_stats = clean_raw in ["آمارم", "آمار من", "وضعیت من"]
        is_asking_other_stats = clean_raw in ["اوضاع این", "اوضاعش", "آمار این", "وضعیت این", "وضعیت"] and update.message.reply_to_message

        if is_group and (is_asking_own_stats or is_asking_other_stats):
            if is_asking_own_stats:
                target_id = user_id
                header_str = '<b><tg-emoji emoji-id="5375056987174216702">😏</tg-emoji> آمار شما به شرح ذیل می‌باشد :</b>\n\n'
            else:
                target_uid, target_fname, target_uname, target_mention = resolve_target_user(update, context)
                target_id = target_uid
                header_str = f'<b><tg-emoji emoji-id="5375056987174216702">😏</tg-emoji> آمار {target_mention} به شرح ذیل می‌باشد :</b>\n\n'

            stats_msg = (
                f"{header_str}"
                f'<b><tg-emoji emoji-id="5433681959324754801">💩</tg-emoji> تعداد گوه‌خوری : {get_user_stat(db, target_id, "goh_khori")}</b>\n'
                f'<b><tg-emoji emoji-id="5863828384332647680">👅</tg-emoji> تعداد کصلیسی : {get_user_stat(db, target_id, "kos_lisi")}</b>\n'
                f'<b><tg-emoji emoji-id="5429327730070009271">🤲</tg-emoji> تعداد خایمالی : {get_user_stat(db, target_id, "khaymali")}</b>\n'
                f'<b><tg-emoji emoji-id="5983342699816685361">👑</tg-emoji> تعداد جندگی : {get_user_stat(db, target_id, "jendegi")}</b>\n'
                f'<b><tg-emoji emoji-id="5886539179256450622">🤪</tg-emoji> تعداد کصخلی : {get_user_stat(db, target_id, "kos_khali")}</b>\n'
                f'<b><tg-emoji emoji-id="5195297917048462460">🍌</tg-emoji> تعداد جقی بودن : {get_user_stat(db, target_id, "jaghi")}</b>\n'
                f'<b><tg-emoji emoji-id="5922483378304586599">🐙</tg-emoji> تعداد کونی بودن : {get_user_stat(db, target_id, "koni")}</b>\n'
                f'<b><tg-emoji emoji-id="5314297755579986373">😊</tg-emoji> تعداد سکسی شدن : {get_user_stat(db, target_id, "sexy")}</b>\n'
                f'<b><tg-emoji emoji-id="5771442740147523468">❤️</tg-emoji> تعداد جذاب شدن : {get_user_stat(db, target_id, "jazab")}</b>\n'
                f'<b><tg-emoji emoji-id="5283151000641757020">😎</tg-emoji> تعداد خوژتیپ شدن : {get_user_stat(db, target_id, "handsome")}</b>\n'
                f'<b><tg-emoji emoji-id="5406926593698312391">❤️</tg-emoji> تعداد کاپل شدن : {get_user_stat(db, target_id, "ship")}</b>\n'
                f'<b><tg-emoji emoji-id="5854843712181378616">🏆</tg-emoji> تعداد پر حرف بودن : {get_user_stat(db, target_id, "goh_khor_hour")}</b>'
            )
            await update.message.reply_text(stats_msg, parse_mode=ParseMode.HTML)
            return

        # --------------------------------------
        # GENERAL PERCENTAGE (GROUP ONLY)
        # --------------------------------------
        if is_group and (clean_raw.startswith("درصد ") or clean_raw.startswith("این چقدر ") or clean_raw.startswith("این چقد ")):
            target_uid, target_fname, target_uname, target_mention = resolve_target_user(update, context)
            topic = clean_raw.replace("درصد ", "").replace("این چقدر ", "").replace("این چقد ", "").replace(" بودن", "").strip()
            val = random.randint(0, 100)
            rand_emoji_id = random.choice(["5886539179256450622", "5922483378304586599", "5195297917048462460", "5983342699816685361"])
            await update.message.reply_text(f"{target_mention}\n\n<tg-emoji emoji-id=\"{rand_emoji_id}\">🎲</tg-emoji> <b>{val}٪ {html.escape(topic)}ه</b>", parse_mode=ParseMode.HTML)
            return

        # --------------------------------------
        # WORLD TIME (GROUP ONLY)
        # --------------------------------------
        if is_group and features.get("world_time", True):
            selected_country = None
            if norm_text.startswith("ساعت "):
                target_name = norm_text.replace("ساعت ", "").strip()
                for c_name, c_data in WORLD_COUNTRIES.items():
                    if target_name == c_name or target_name in c_data.get("aliases", []):
                        selected_country = (c_name, c_data)
                        break

            if selected_country:
                c_name, c_data = selected_country
                c_time = datetime.now(ZoneInfo(c_data["tz"])).strftime("%H:%M:%S")
                msg = f'<b>{c_data["emoji"]} ساعت {c_name}: {c_time}</b>'
                await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
                return

            elif norm_text in ["ساعت", "ساعت جهانی"]:
                lines = ['<b><tg-emoji emoji-id="5399898266265475100">🌍</tg-emoji> ساعت جهانی برخی از کشورها :</b>\n']
                for c_name, c_data in WORLD_COUNTRIES.items():
                    c_time = datetime.now(ZoneInfo(c_data["tz"])).strftime("%H:%M:%S")
                    lines.append(f'<b>{c_data["emoji"]} {c_name}: {c_time}</b>')
                
                await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
                return
# --------------------------------------
        # FUN FEATURES WITH PREMIUM EMOJIS & COOLDOWN
        # --------------------------------------
        # ۲. خوشتیپ / خوژتیپ
        if is_group and norm_text in ["خوشتیپ کیه", "خوشتیپ کی", "خوژتیپ کیه", "خوژتیپ کی", "خوشتیپ", "خوژتیپ"] and features.get("handsome", True):
            word_label = "خوژتیپ" if "خوژ" in norm_text else "خوشتیپ"
            is_cd, rem_sec, cd_data = get_cooldown_remaining(db, chat_id, "handsome")
            
            if is_cd:
                m_rem = rem_sec // 60
                target_mention = get_user_mention(cd_data["id"], cd_data["fullname"])
                msg = (
                    f'<b><tg-emoji emoji-id="5332699109168013117">🌟</tg-emoji> {word_label} گروه اینه :</b>\n\n'
                    f'<b><tg-emoji emoji-id="5321484996802797866">😎</tg-emoji> | {target_mention}</b>\n\n'
                    f'<b>- ولی خب {m_rem} دقیقه دیگه {word_label} بعدی معرفی میشه! <tg-emoji emoji-id="5323417298294298902">🙂</tg-emoji></b>'
                )
                await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
            else:
                m_tuple = await get_fast_random_member(context, chat_id, db)
                if m_tuple:
                    tid, info = m_tuple
                    target_mention = get_user_mention(int(tid), info["fullname"])
                    set_cooldown_data(db, chat_id, "handsome", {"id": int(tid), "fullname": info["fullname"]})
                    increment_user_stat(db, int(tid), "handsome")
                    
                    msg = (
                        f'<b><tg-emoji emoji-id="5332699109168013117">🌟</tg-emoji> {word_label} گروه اینه :</b>\n\n'
                        f'<b><tg-emoji emoji-id="5321484996802797866">😎</tg-emoji> | {target_mention}</b>'
                    )
                    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
                else:
                    await update.message.reply_text('<b> کاربری در حافظه گروه پیدا نشد!</b>', parse_mode=ParseMode.HTML)
            return

        # ۳. جنده
        elif is_group and norm_text in ["جنده کیه", "جنده کی", "جنده"] and features.get("jende", True):
            is_cd, rem_sec, cd_data = get_cooldown_remaining(db, chat_id, "jende")
            if is_cd:
                m_rem = rem_sec // 60
                target_mention = get_user_mention(cd_data["id"], cd_data["fullname"])
                msg = (
                    f'<b><tg-emoji emoji-id="4974615079971455718">🖤</tg-emoji> جنده گروه اینه :</b>\n\n'
                    f'<b><tg-emoji emoji-id="4974545355472372800">🖤</tg-emoji> | {target_mention}</b>\n\n'
                    f'<b>+ ولی خب هر جندگی دائمی نیست! {m_rem} دقیقه دیگه جنده بعدی معرفی میشه! <tg-emoji emoji-id="4974573543342736117">🖤</tg-emoji></b>'
                )
                await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
            else:
                m_tuple = await get_fast_random_member(context, chat_id, db)
                if m_tuple:
                    tid, info = m_tuple
                    target_mention = get_user_mention(int(tid), info["fullname"])
                    set_cooldown_data(db, chat_id, "jende", {"id": int(tid), "fullname": info["fullname"]})
                    increment_user_stat(db, int(tid), "jendegi")
                    
                    msg = (
                        f'<b><tg-emoji emoji-id="4974615079971455718">🖤</tg-emoji> جنده گروه اینه :</b>\n\n'
                        f'<b><tg-emoji emoji-id="4974545355472372800">🖤</tg-emoji> | {target_mention}</b>'
                    )
                    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
                else:
                    await update.message.reply_text('<b> کاربری در حافظه گروه پیدا نشد!</b>', parse_mode=ParseMode.HTML)
            return

        # ۴. کونی
        elif is_group and norm_text in ["کونی کیه", "کونی کی", "کونی"] and features.get("koni", True):
            is_cd, rem_sec, cd_data = get_cooldown_remaining(db, chat_id, "koni")
            if is_cd:
                m_rem = rem_sec // 60
                target_mention = get_user_mention(cd_data["id"], cd_data["fullname"])
                msg = (
                    f'<b><tg-emoji emoji-id="4976598744976851674">🍌</tg-emoji> کونی گروه اینه :</b>\n\n'
                    f'<b><tg-emoji emoji-id="4974439226830488153">🔞</tg-emoji> | {target_mention}</b>\n\n'
                    f'<b>+ ولی خب {m_rem} دقیقه دیگه کونی بعدی معرفی میشه! <tg-emoji emoji-id="4974672507979170737">🍌</tg-emoji></b>'
                )
                await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
            else:
                m_tuple = await get_fast_random_member(context, chat_id, db)
                if m_tuple:
                    tid, info = m_tuple
                    target_mention = get_user_mention(int(tid), info["fullname"])
                    set_cooldown_data(db, chat_id, "koni", {"id": int(tid), "fullname": info["fullname"]})
                    increment_user_stat(db, int(tid), "koni")
                    
                    msg = (
                        f'<b><tg-emoji emoji-id="4976598744976851674">🍌</tg-emoji> کونی گروه اینه :</b>\n\n'
                        f'<b><tg-emoji emoji-id="4974439226830488153">🔞</tg-emoji> | {target_mention}</b>'
                    )
                    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
                else:
                    await update.message.reply_text('<b> کاربری در حافظه گروه پیدا نشد!</b>', parse_mode=ParseMode.HTML)
            return

        # ۵. جقی
        elif is_group and norm_text in ["جقی", "جقی کیه", "جقی گروه"] and features.get("jaghi", True):
            is_cd, rem_sec, cd_data = get_cooldown_remaining(db, chat_id, "jaghi")
            if is_cd:
                m_rem = rem_sec // 60
                target_mention = get_user_mention(cd_data["id"], cd_data["fullname"])
                msg = (
                    f'<b><tg-emoji emoji-id="4974338329458770518">🍌</tg-emoji> جقی گروه اینه :</b>\n\n'
                    f'<b><tg-emoji emoji-id="4974362376980660892">🍌</tg-emoji> | {target_mention}</b>\n\n'
                    f'<b>+ بزن که خوب میزنی رفیق گلم! <tg-emoji emoji-id="6033112209612082866">😂</tg-emoji></b>\n'
                    f'<b>- ولی این جق ابدی نیست! {m_rem} دقیقه دیگه جقی بعدیو معرفی میکنم.</b>'
                )
                await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
            else:
                m_tuple = await get_fast_random_member(context, chat_id, db)
                if m_tuple:
                    tid, info = m_tuple
                    target_mention = get_user_mention(int(tid), info["fullname"])
                    set_cooldown_data(db, chat_id, "jaghi", {"id": int(tid), "fullname": info["fullname"]})
                    increment_user_stat(db, int(tid), "jaghi")
                    
                    msg = (
                        f'<b><tg-emoji emoji-id="4974338329458770518">🍌</tg-emoji> جقی گروه اینه :</b>\n\n'
                        f'<b><tg-emoji emoji-id="4974362376980660892">🍌</tg-emoji> | {target_mention}</b>\n\n'
                        f'<b>+ بزن که خوب میزنی رفیق گلم! <tg-emoji emoji-id="6033112209612082866">😂</tg-emoji></b>'
                    )
                    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
                else:
                    await update.message.reply_text('<b> کاربری در حافظه گروه پیدا نشد!</b>', parse_mode=ParseMode.HTML)
            return

        # ۶. کصخل / کسخل
        elif is_group and norm_text in ["کصخل", "کسخل", "کصخل گروه", "کسخل گروه"] and features.get("koskhal", True):
            is_cd, rem_sec, cd_data = get_cooldown_remaining(db, chat_id, "koskhal")
            if is_cd:
                m_rem = rem_sec // 60
                target_mention = get_user_mention(cd_data["id"], cd_data["fullname"])
                msg = (
                    f'<b><tg-emoji emoji-id="5886539179256450622">🤪</tg-emoji> کصخل گروه اینه :</b>\n\n'
                    f'<b><tg-emoji emoji-id="5861747442612964510">🤙</tg-emoji> | {target_mention}</b>\n\n'
                    f'<b>+ هر کصخلی درمانی دارد! {m_rem} دقیقه دیگه کصخل بعدیو معرفی میکنم.</b>'
                )
                await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
            else:
                m_tuple = await get_fast_random_member(context, chat_id, db)
                if m_tuple:
                    tid, info = m_tuple
                    target_mention = get_user_mention(int(tid), info["fullname"])
                    set_cooldown_data(db, chat_id, "koskhal", {"id": int(tid), "fullname": info["fullname"]})
                    increment_user_stat(db, int(tid), "kos_khali")
                    
                    msg = (
                        f'<b><tg-emoji emoji-id="5886539179256450622">🤪</tg-emoji> کصخل گروه اینه :</b>\n\n'
                        f'<b><tg-emoji emoji-id="5861747442612964510">🤙</tg-emoji> | {target_mention}</b>\n\n'
                        f'<b>+ هر کصخلی درمانی دارد!</b>'
                    )
                    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
                else:
                    await update.message.reply_text('<b> کاربری در حافظه گروه پیدا نشد!</b>', parse_mode=ParseMode.HTML)
            return

        # ۷. سکسی
        elif is_group and norm_text in ["سکسی", "سکسی گروه"] and features.get("sexy", True):
            is_cd, rem_sec, cd_data = get_cooldown_remaining(db, chat_id, "sexy")
            if is_cd:
                m_rem = rem_sec // 60
                target_mention = get_user_mention(cd_data["id"], cd_data["fullname"])
                msg = (
                    f'<b><tg-emoji emoji-id="5920075812911976155">😈</tg-emoji> سکسی گروه اینه :</b>\n\n'
                    f'<b><tg-emoji emoji-id="5247009821508537591">🚬</tg-emoji> | {target_mention}</b>\n\n'
                    f'<b>+ ولی خب {m_rem} دقیقه دیگه سکسی بعدیو معرفی میکنم.</b>'
                )
                await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
            else:
                m_tuple = await get_fast_random_member(context, chat_id, db)
                if m_tuple:
                    tid, info = m_tuple
                    target_mention = get_user_mention(int(tid), info["fullname"])
                    set_cooldown_data(db, chat_id, "sexy", {"id": int(tid), "fullname": info["fullname"]})
                    increment_user_stat(db, int(tid), "sexy")
                    
                    msg = (
                        f'<b><tg-emoji emoji-id="5920075812911976155">😈</tg-emoji> سکسی گروه اینه :</b>\n\n'
                        f'<b><tg-emoji emoji-id="5247009821508537591">🚬</tg-emoji> | {target_mention}</b>'
                    )
                    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
                else:
                    await update.message.reply_text('<b> کاربری در حافظه گروه پیدا نشد!</b>', parse_mode=ParseMode.HTML)
            return

        # ۸. جذاب
        elif is_group and norm_text in ["جذاب", "جذاب گروه"] and features.get("jazab", True):
            is_cd, rem_sec, cd_data = get_cooldown_remaining(db, chat_id, "jazab")
            if is_cd:
                m_rem = rem_sec // 60
                target_mention = get_user_mention(cd_data["id"], cd_data["fullname"])
                msg = (
                    f'<b><tg-emoji emoji-id="5771629206152679502">☕️</tg-emoji> جذاب گروه اینه :</b>\n\n'
                    f'<b><tg-emoji emoji-id="5774059410317905809">❤️</tg-emoji> | {target_mention}</b>\n\n'
                    f'<b>عشقمممم شماره میدی پاره کنیم؟؟؟ <tg-emoji emoji-id="5773636884320226590">💋</tg-emoji></b>\n'
                    f'<b>+ {m_rem} دقیقه دیگه جذاب بعدیو معرفی میکنم.</b>'
                )
                await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
            else:
                m_tuple = await get_fast_random_member(context, chat_id, db)
                if m_tuple:
                    tid, info = m_tuple
                    target_mention = get_user_mention(int(tid), info["fullname"])
                    set_cooldown_data(db, chat_id, "jazab", {"id": int(tid), "fullname": info["fullname"]})
                    increment_user_stat(db, int(tid), "jazab")
                    
                    msg = (
                        f'<b><tg-emoji emoji-id="5771629206152679502">☕️</tg-emoji> جذاب گروه اینه :</b>\n\n'
                        f'<b><tg-emoji emoji-id="5774059410317905809">❤️</tg-emoji> | {target_mention}</b>\n\n'
                        f'<b>عشقمممم شماره میدی پاره کنیم؟؟؟ <tg-emoji emoji-id="5773636884320226590">💋</tg-emoji></b>'
                    )
                    await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
                else:
                    await update.message.reply_text('<b> کاربری در حافظه گروه پیدا نشد!</b>', parse_mode=ParseMode.HTML)
            return

        # ۹. شیپ / کاپل
        elif is_group and norm_text in ["شیپ کن", "شیپ", "کاپل", "کاپل کن"] and features.get("ship", True):
            is_cd, rem_sec, cd_data = get_cooldown_remaining(db, chat_id, "ship")
            if is_cd:
                m_rem = rem_sec // 60
                name1 = get_user_mention(cd_data["u1"]["id"], cd_data["u1"]["name"])
                name2 = get_user_mention(cd_data["u2"]["id"], cd_data["u2"]["name"])
                
                last_msg_id = cd_data.get("last_msg_id")
                couple_data = db.get("couples", {}).get(str(last_msg_id), {}) if last_msg_id else {}
                agrees = couple_data.get("agrees", [])
                disagrees = couple_data.get("disagrees", [])

                agrees_text = ", ".join([get_user_mention(u["id"], u["name"]) for u in agrees]) if agrees else "هیچکس"
                disagrees_text = ", ".join([get_user_mention(u["id"], u["name"]) for u in disagrees]) if disagrees else "هیچکس"

                msg = (
                    f'<b><tg-emoji emoji-id="5830106027701314719">❤️</tg-emoji> دو عدد کفتر عاشقمون این رفقان:</b>\n\n'
                    f'<b><tg-emoji emoji-id="5834477789012564986">💕</tg-emoji> | {name1} <tg-emoji emoji-id="6048558196203720407">❤️</tg-emoji> {name2}</b>\n\n'
                    f'<b><tg-emoji emoji-id="5819032824623144971">➕</tg-emoji>موافقان ثبت شده: {agrees_text}</b>\n'
                    f'<b><tg-emoji emoji-id="5819154526816444042">❌</tg-emoji> مخالفان ثبت شده : {disagrees_text}</b>\n\n'
                    f'<b>+ {m_rem} دقیقه دیگه کاپل بعدیو میگم بچهااااا!<tg-emoji emoji-id="5816460319601467354">😺</tg-emoji></b>'
                )
                await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
            else:
                m1 = await get_fast_random_member(context, chat_id, db)
                m2 = await get_fast_random_member(context, chat_id, db)
                if m1 and m2 and m1[0] != m2[0]:
                    u1_dict = {"id": int(m1[0]), "name": m1[1]['fullname']}
                    u2_dict = {"id": int(m2[0]), "name": m2[1]['fullname']}
                    
                    increment_user_stat(db, u1_dict["id"], "ship")
                    increment_user_stat(db, u2_dict["id"], "ship")

                    name1 = get_user_mention(u1_dict["id"], u1_dict["name"])
                    name2 = get_user_mention(u2_dict["id"], u2_dict["name"])

                    kb = InlineKeyboardMarkup([
                        [
                            InlineKeyboardButton("موافقم", callback_data="couple_agree", style="success", icon_custom_emoji_id="5411228694935012881"),
                            InlineKeyboardButton("افتضاح", callback_data="couple_disagree", style="danger", icon_custom_emoji_id="5411484842489578182")
                        ]
                    ])

                    sent_msg = await update.message.reply_text(
                        f'<b><tg-emoji emoji-id="5830106027701314719">❤️</tg-emoji> دو عدد کفتر عاشقمون این رفقان:</b>\n\n'
                        f'<b><tg-emoji emoji-id="5834477789012564986">💕</tg-emoji> | {name1} <tg-emoji emoji-id="6048558196203720407">❤️</tg-emoji> {name2}</b>\n\n'
                        f'<b><tg-emoji emoji-id="5819032824623144971">➕</tg-emoji>موافقان: هیچکس</b>\n'
                        f'<b><tg-emoji emoji-id="5819154526816444042">❌</tg-emoji> مخالفان: هیچکس</b>',
                        reply_markup=kb,
                        parse_mode=ParseMode.HTML
                    )

                    if "couples" not in db:
                        db["couples"] = {}
                    db["couples"][str(sent_msg.message_id)] = {
                        "u1": u1_dict,
                        "u2": u2_dict,
                        "agrees": [],
                        "disagrees": [],
                        "created_at": datetime.now().timestamp()
                    }
                    set_cooldown_data(db, chat_id, "ship", {"u1": u1_dict, "u2": u2_dict, "last_msg_id": sent_msg.message_id})
                else:
                    await update.message.reply_text(
                        '<b> اعضای کافی موجود نیست! <tg-emoji emoji-id="5857415006022278161">❌</tg-emoji></b>',
                        parse_mode=ParseMode.HTML
                    )
            return

        # غذا
        elif is_group and any(w in norm_text.split() for w in ["غذا", "غدا", "نهار", "شام"]) and features.get("food", True):
            g_data = get_group_data(db, chat_id)
            fl = g_data.get("foods", DEFAULT_FOODS)
            if fl:
                selected_food = random.choice(fl)
                msg = (
                    f'<b><tg-emoji emoji-id="5418248505447698083">🧽</tg-emoji> دنبال غذایی؟ بنظرم بهترین ایده غذا برای تو اینه :</b>\n\n'
                    f'<b><tg-emoji emoji-id="5357066069250948384">🐱</tg-emoji> | {html.escape(selected_food)}</b>'
                )
                await update.message.reply_text(msg, parse_mode=ParseMode.HTML)
            return

        # شعر
        elif is_group and norm_text in ["شعر", "شعر بگو", "شاعر شو"] and features.get("poems", True):
            g_data = get_group_data(db, chat_id)
            custom_names = g_data.get("custom_names", [])
            if custom_names:
                target_name = random.choice(custom_names)
            else:
                m_tuple = await get_fast_random_member(context, chat_id, db)
                target_name = get_user_mention(int(m_tuple[0]), m_tuple[1]["fullname"]) if m_tuple else "رفیق"

            all_poems = g_data.get("poems", DEFAULT_POEMS)
            poem_template = random.choice(all_poems)
            final_poem = poem_template.format(name=target_name)
            await update.message.reply_text(f'<tg-emoji emoji-id="5859527571586161695">✍️</tg-emoji> <b>{final_poem}</b>', parse_mode=ParseMode.HTML)
            return

        # لف
        elif is_group and LEF_PATTERN.search(raw_text) and features.get("lef", True):
            g_data = get_group_data(db, chat_id)
            ml = g_data.get("media_lef") or db.get("media_lef")
            if ml:
                await send_media_payload(
                    context.bot,
                    chat_id,
                    ml,
                    reply_to_message_id=update.message.message_id
                )
            return

        # Automatic responses are evaluated only after the bot's existing
        # group commands have had a chance to handle the message. This keeps
        # the new feature from hijacking any pre-existing command.
        if is_group and await handle_auto_response_group_message(update, context):
            return

    except Exception:
        logger.exception("Error in handle_messages:")
