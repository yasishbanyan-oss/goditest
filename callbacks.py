# GoodiBot modular feature module
from core import *

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    user_id = query.from_user.id
    current_chat_id = query.message.chat.id if query.message else 0
    db = load_db()
    session_k = get_session_key(user_id, current_chat_id)

    # Every group-management panel is owned by the user who opened it.
    # This guard runs before any nested panel callback, so another manager
    # cannot press buttons on someone else's panel and change group settings.
    if query.message and query.message.chat and query.message.chat.type in ("group", "supergroup"):
        panel_session = get_group_panel_session(db, current_chat_id, query.message.message_id)
        if panel_session and int(panel_session.get("owner_id", 0)) != int(user_id):
            await query.answer("این پنل برای شما نیست.", show_alert=True)
            return

    # Filter-word panel callbacks are isolated in filter_handler.py.
    if await handle_filter_callback(query, context, db):
        return

    # اول از همه بررسی دکمه‌های لینک تا سریعاً واکنش نشان دهند
    if data.startswith("link_panel:"):
        parts = data.split(":", 2)
        if len(parts) != 3 or not parts[2].lstrip("-").isdigit():
            await query.answer(" اطلاعات دکمه نامعتبر است.", show_alert=True)
            return

        action = parts[1]
        cid = int(parts[2])

        if not await is_configured_group_manager(context, cid, user_id):
            await query.answer(" دسترسی غیرمجاز!", show_alert=True)
            return

        if action == "close":
            try:
                if query.message:
                    await query.message.edit_text(
                        f'<b><tg-emoji emoji-id="{CHECK_CUSTOM_EMOJI_ID}">✅</tg-emoji> پنل دریافت لینک با موفقیت بسته شد.</b>' ,
                        reply_markup=None,
                        parse_mode=ParseMode.HTML,
                    )
                await query.answer()
            except Exception:
                logger.exception("Failed to close link panel | chat_id=%s | user_id=%s", cid, user_id)
                await query.answer(" بستن پنل ناموفق بود.", show_alert=True)
            return

        if action == "text":
            try:
                text_payload = await generate_group_link_text_payload(context, cid, is_once=False)
                await query.message.edit_text(
                    text_payload,
                    reply_markup=build_link_sub_keyboard(cid, is_once=False, invite_link=load_db().get("groups", {}).get(str(cid), {}).get("invite_link")),
                    parse_mode=ParseMode.HTML,
                    link_preview_options=LinkPreviewOptions(is_disabled=True),
                )
                await query.answer(" لینک آماده شد.")
            except Exception as e:
                logger.exception("Link text callback failed | chat_id=%s | user_id=%s", cid, user_id)
                await query.answer(f" ساخت لینک ناموفق بود: {str(e)[:150]}", show_alert=True)
            return

        if action == "photo":
            try:
                chat_obj = await context.bot.get_chat(cid)
                caption_text = await generate_group_link_text_payload(context, cid, is_once=False)

                photo_bytes = await get_group_photo_for_send(context, chat_obj)
                if photo_bytes:
                    await context.bot.send_photo(
                        chat_id=cid,
                        photo=photo_bytes,
                        caption=caption_text,
                        parse_mode=ParseMode.HTML,
                        reply_to_message_id=query.message.message_id if query.message else None,
                    )
                else:
                    await context.bot.send_message(
                        chat_id=cid,
                        text=caption_text,
                        parse_mode=ParseMode.HTML,
                        link_preview_options=LinkPreviewOptions(is_disabled=True),
                        reply_to_message_id=query.message.message_id if query.message else None,
                    )

                await query.answer(" لینک به‌صورت عکس ارسال شد.")
            except Exception as e:
                logger.exception("Link photo callback failed | chat_id=%s | user_id=%s", cid, user_id)
                await query.answer(f" ارسال لینک به‌صورت عکس ناموفق بود: {str(e)[:120]}", show_alert=True)
            return

        if action == "once":
            try:
                text_payload = await generate_group_link_text_payload(context, cid, is_once=True)
                await query.message.edit_text(
                    text_payload,
                    reply_markup=build_link_sub_keyboard(cid, is_once=True, invite_link=load_db().get("groups", {}).get(str(cid), {}).get("invite_link")),
                    parse_mode=ParseMode.HTML,
                    link_preview_options=LinkPreviewOptions(is_disabled=True),
                )
                await query.answer(" لینک یک‌بارمصرف آماده شد.")
            except Exception as e:
                logger.exception("One-time link callback failed | chat_id=%s | user_id=%s", cid, user_id)
                await query.answer(f" ساخت لینک یک‌بارمصرف ناموفق بود: {str(e)[:150]}", show_alert=True)
            return

        if action == "pv":
            try:
                # First generate the link separately so a Telegram link-generation
                # failure is not incorrectly reported as a PV/start error.
                text_payload = await generate_group_link_text_payload(context, cid, is_once=False)
                await context.bot.send_message(
                    chat_id=user_id,
                    text=text_payload,
                    parse_mode=ParseMode.HTML,
                    link_preview_options=LinkPreviewOptions(is_disabled=True),
                )
                await query.answer(" لینک گروه در پیوی شما ارسال شد.", show_alert=True)
            except Exception as e:
                logger.exception("Link PV callback failed | group=%s | user=%s", cid, user_id)
                error_text = str(e).lower()
                if any(x in error_text for x in ["chat not found", "user is deactivated", "forbidden"]):
                    msg = " ارسال به پیوی ممکن نشد. اگر ربات را قبلاً بلاک کرده‌اید، آن را آزاد و دوباره Start کنید."
                else:
                    msg = f" ارسال لینک به پیوی ناموفق بود: {str(e)[:150]}"
                await query.answer(msg, show_alert=True)
            return

        await query.answer(" گزینه لینک ناشناخته است.", show_alert=True)
        return

    elif data.startswith("link_sub:"):
        parts = data.split(":", 2)
        if len(parts) != 3 or not parts[2].lstrip("-").isdigit():
            await query.answer(" اطلاعات دکمه نامعتبر است.", show_alert=True)
            return

        sub_action = parts[1]
        cid = int(parts[2])
        if not await is_configured_group_manager(context, cid, user_id):
            await query.answer(" دسترسی غیرمجاز!", show_alert=True)
            return

        if sub_action == "share":
            await query.answer("لینک گروه آماده اشتراک‌گذاری است.", show_alert=False)
            return
        elif sub_action == "back":
            panel_text = f'<tg-emoji emoji-id="6044084382174552276">📊</tg-emoji> <b>نوع لینک را انتخاب کنید:</b>'
            try:
                await query.message.edit_text(panel_text, reply_markup=build_link_panel_keyboard(cid), parse_mode=ParseMode.HTML)
                await query.answer()
            except Exception:
                logger.exception("Failed to return to link panel | chat_id=%s", cid)
                await query.answer(" بازگشت ناموفق بود.", show_alert=True)
            return
        elif sub_action == "revoke":
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("بله", callback_data=f"link_revoke:yes:{cid}", style="success", icon_custom_emoji_id="5830144944399981619"),
                 InlineKeyboardButton("خیر", callback_data=f"link_revoke:no:{cid}", style="danger", icon_custom_emoji_id="5819154526816444042")]
            ])
            try:
                await query.message.edit_text("<b>از حذف لینک نهایت اطمینان را دارید؟</b>", reply_markup=kb, parse_mode=ParseMode.HTML)
                await query.answer()
            except Exception:
                logger.exception("Failed to open link revoke confirmation | chat_id=%s", cid)
                await query.answer(" عملیات ناموفق بود.", show_alert=True)
            return

        await query.answer(" گزینه ناشناخته است.", show_alert=True)
        return

    elif data.startswith("link_revoke:"):
        parts = data.split(":", 2)
        if len(parts) != 3 or not parts[2].lstrip("-").isdigit():
            await query.answer(" اطلاعات دکمه نامعتبر است.", show_alert=True)
            return

        decision = parts[1]
        cid = int(parts[2])
        if not await is_configured_group_manager(context, cid, user_id):
            await query.answer(" دسترسی غیرمجاز!", show_alert=True)
            return

        if decision == "no":
            try:
                text_payload = await generate_group_link_text_payload(context, cid, is_once=False)
                await query.message.edit_text(text_payload, reply_markup=build_link_sub_keyboard(cid, is_once=False, invite_link=load_db().get("groups", {}).get(str(cid), {}).get("invite_link")), parse_mode=ParseMode.HTML, link_preview_options=LinkPreviewOptions(is_disabled=True))
                await query.answer()
            except Exception as e:
                logger.exception("Failed to cancel link revoke | chat_id=%s", cid)
                await query.answer(f" خطا: {str(e)[:150]}", show_alert=True)
            return

        if decision == "yes":
            try:
                db = load_db()
                g_data = get_group_data(db, cid)
                current_link = g_data.get("invite_link")

                # The Bot API has no get_chat_export_invite_links() method.
                # Revoke the exact invite link that this bot last generated/stored.
                if not current_link:
                    raise RuntimeError("لینک ذخیره‌شده‌ای برای حذف پیدا نشد.")

                await context.bot.revoke_chat_invite_link(cid, current_link)
                g_data["invite_link"] = None
                mark_db_dirty()
                save_db()

                success_text = (
                    '<tg-emoji emoji-id="5830144944399981619">✅</tg-emoji> '
                    '<b>لینک قبلی با موفقیت حذف شد. برای ساخت لینک جدید از دکمه زیر استفاده کنید.</b>'
                )
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("ساخت لینک جدید", callback_data=f"link_panel:text:{cid}", icon_custom_emoji_id="5983093054842606366")]
                ])
                await query.message.edit_text(success_text, reply_markup=kb, parse_mode=ParseMode.HTML, link_preview_options=LinkPreviewOptions(is_disabled=True))
                await query.answer(" لینک حذف شد.")
            except Exception as e:
                logger.exception("Failed to revoke group invite link | chat_id=%s", cid)
                await query.answer(f" حذف لینک ناموفق بود: {str(e)[:150]}", show_alert=True)
            return

        await query.answer(" گزینه نامعتبر است.", show_alert=True)
        return

    if data.startswith("help_"):
        parts = data.split(":", 1)
        help_key = parts[0]
        try:
            help_owner = int(parts[1]) if len(parts) == 2 else 0
        except (TypeError, ValueError):
            help_owner = 0
        if help_owner and int(user_id) != help_owner:
            await query.answer("این پنل برای شما نیست.", show_alert=True)
            return
        help_texts = {
            "help_fun": "<b>راهنمای سرگرمی</b>\nدستورات سرگرمی ربات در این بخش معرفی می‌شوند.",
            "help_rude": "<b>راهنمای بی ادبی</b>\nدستورات این بخش برای سرگرمی و شوخی هستند.",
            "help_useful": "<b>راهنمای کاربردی</b>\nدستورات کاربردی ربات را از این بخش مشاهده کنید.",
            "help_admin": "<b>راهنمای مدیریتی</b>\nدستورات مدیریتی گروه در این بخش قرار دارند.",
        }
        if help_key not in help_texts:
            await query.answer("گزینه راهنما نامعتبر است.", show_alert=True)
            return
        owner_suffix = f":{help_owner}" if help_owner else ""
        help_kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("راهنمای سرگرمی", callback_data=f"help_fun{owner_suffix}", style="primary", icon_custom_emoji_id="5415940089375106928"),
             InlineKeyboardButton("راهنمای بی ادبی", callback_data=f"help_rude{owner_suffix}", style="primary", icon_custom_emoji_id="5832633418386513259")],
            [InlineKeyboardButton("راهنمای کاربردی", callback_data=f"help_useful{owner_suffix}", style="primary", icon_custom_emoji_id="5830338333892418460"),
             InlineKeyboardButton("راهنمای مدیریتی", callback_data=f"help_admin{owner_suffix}", style="primary", icon_custom_emoji_id="5803348359972393936")]
        ])
        await query.message.edit_text(help_texts[help_key], reply_markup=help_kb, parse_mode=ParseMode.HTML)
        await query.answer()
        return

    # LOCKS PANEL NAVIGATION & TOGGLE
    elif data.startswith("panel_group_locks:"):
        parts = data.split(":")
        cid = int(parts[1])
        page = int(parts[2]) if len(parts) > 2 else 1
        if not await is_configured_group_manager(context, cid, user_id):
            await query.answer(" دسترسی غیرمجاز!", show_alert=True)
            return
        await render_group_locks_panel(query, cid, page)
        return

    elif data.startswith("panel_service_locks:"):
        cid = int(data.split(":")[1])
        if not await is_configured_group_manager(context, cid, user_id):
            await query.answer(" دسترسی غیرمجاز!", show_alert=True)
            return
        await render_telegram_service_locks_panel(query, cid)
        return

     # WHISPER (NAJVA) CALLBACKS
    elif data.startswith("wh_confirm:"):
        w_id = data.replace("wh_confirm:", "")
        whispers = db.get("whispers", {})

        if w_id not in whispers:
            await query.answer(" این نجوا منقضی یا حذف شده است!", show_alert=True)
            return

        w_data = whispers[w_id]

        if query.from_user.id != w_data.get("sender_id"):
            await query.answer(" فقط فرستنده نجوا می‌تواند ارسال را تایید کند.", show_alert=True)
            return

        display_target = (
            f"@{w_data.get('target_username')}"
            if w_data.get("target_username")
            else str(w_data.get("target_uid"))
        )

        sent_text = (
            f'<tg-emoji emoji-id="6059631768649077274">📣</tg-emoji> '
            f'<b>یک نجوا برای کاربر {html.escape(display_target)} ارسال شد.</b>'
        )

        sent_kb = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "مشاهده نجوا",
                    callback_data=f"wh_read:{w_id}",
                    style="success",
                    icon_custom_emoji_id="6084779072750097974"
                ),
                InlineKeyboardButton(
                    "حذف نجوا",
                    callback_data=f"wh_del:{w_id}",
                    style="danger",
                    icon_custom_emoji_id="5819154526816444042"
                )
            ]
        ])

        try:
            await query.edit_message_text(
                sent_text,
                reply_markup=sent_kb,
                parse_mode=ParseMode.HTML
            )
            await query.answer()
        except Exception:
            await query.answer(" ارسال نجوا ناموفق بود.", show_alert=True)
        return

    elif data.startswith("wh_read:"):
        w_id = data.replace("wh_read:", "")
        whispers = db.get("whispers", {})
        
        if w_id not in whispers:
            await query.answer(" این نجوا منقضی یا حذف شده است!", show_alert=True)
            return

        w_data = whispers[w_id]
        created_at = w_data.get("created_at", 0)
        if created_at and (datetime.now().timestamp() - created_at) > 86400:
            whispers.pop(w_id, None)
            mark_db_dirty()
            save_db(force=True)
            await query.answer(" این نجوا منقضی شده است!", show_alert=True)
            return
        sender_id = w_data["sender_id"]
        target_uid = w_data.get("target_uid")
        u_id = query.from_user.id

        # Whisper ownership is strictly numeric-ID based. Username is only used
        # when initially resolving the recipient and for display.
        is_sender = (u_id == sender_id)
        is_target = bool(target_uid and u_id == int(target_uid))

        if not is_sender and not is_target:
            await query.answer(" فضولی نکن! این نجوا برای شما نیست.", show_alert=True)
            return

        await query.answer(w_data["text"], show_alert=True)

        if is_target and not w_data.get("read", False):
            w_data["read"] = True
            w_data["reader_id"] = u_id
            w_data["reader_username"] = query.from_user.username or ""
            w_data["reader_name"] = query.from_user.full_name
            db["whispers"][w_id] = w_data
            mark_db_dirty()
            save_db(force=True)

            reader_username = query.from_user.username
            reader_display = f"@{reader_username}" if reader_username else str(u_id)
            edited_text = (
                f'<tg-emoji emoji-id="6084779072750097974">✅</tg-emoji> '
                f'<b>نجوای ارسالی توسط کاربر {html.escape(reader_display)} خوانده شد.</b>'
            )

            # After the whisper is read, both sender and recipient see the same
            # three glass buttons. No private message is sent to either user.
            new_kb = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        "خواندن مجدد",
                        callback_data=f"wh_read:{w_id}",
                        style="primary",
                        icon_custom_emoji_id="5843493805835165294"  # 👀
                    )
                ],
                [
                    InlineKeyboardButton(
                        "پاسخ به نجوا",
                        # Reply by numeric ID so a later username change cannot
                        # break the reply flow.
                        switch_inline_query_current_chat=f"{w_data['sender_id']} ",
                        style="success",
                        icon_custom_emoji_id="6084779072750097974"  # ✅
                    ),
                    InlineKeyboardButton(
                        "کانال پشتیبانی",
                        url="https://t.me/GoodiSupport",
                        style="success",
                        icon_custom_emoji_id="5911319564301376749"  # 🤖
                    )
                ]
            ])

            try:
                await query.edit_message_text(edited_text, reply_markup=new_kb, parse_mode=ParseMode.HTML)
            except Exception:
                pass
        return

    elif data.startswith("wh_del:"):
        w_id = data.replace("wh_del:", "")
        whispers = db.get("whispers", {})

        if w_id not in whispers:
            await query.answer(" این نجوا قبلاً حذف شده است!", show_alert=True)
            return

        w_data = whispers[w_id]
        if query.from_user.id != w_data["sender_id"]:
            await query.answer("شما نمی‌توانید نجوای دیگران را حذف کنید.", show_alert=True)
            return

        del whispers[w_id]
        mark_db_dirty()
        save_db(force=True)

        await query.answer(" نجوای شما با موفقیت حذف شد.", show_alert=True)

        try:
            del_text = '<b><tg-emoji emoji-id="5818716826699307883">❗️</tg-emoji> این نجوا توسط فرستنده حذف گردید.</b>'
            await query.edit_message_text(del_text, reply_markup=None, parse_mode=ParseMode.HTML)
        except Exception:
            pass
        return  

    elif data.startswith("tgl_srv_lock:"):
        parts = data.split(":")
        cid = int(parts[1])
        lock_key = parts[2]

        if not await is_configured_group_manager(context, cid, user_id):
            await query.answer(" دسترسی غیرمجاز!", show_alert=True)
            return

        g_data = get_group_data(db, cid)
        locks = g_data.setdefault("locks", get_default_locks_structure())
        if not locks.get(lock_key, False):
            try:
                bot_member = await cached_chat_member(context, cid, context.bot.id)
                if bot_member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
                    await query.answer(" ربات ادمین گروه نیست.", show_alert=True)
                    return
            except Exception:
                await query.answer(" ربات ادمین گروه نیست.", show_alert=True)
                return
        locks[lock_key] = not locks.get(lock_key, False)
        
        status_word = "فعال" if locks[lock_key] else "غیرفعال"
        lock_fa_name = ALL_LOCKS.get(lock_key, {}).get("name", lock_key)

        log_admin_action(db, user_id, query.from_user.full_name, g_data.get("title", ""), cid, f"تغییر {lock_fa_name}", f"وضعیت جدید: {status_word}")
        mark_db_dirty()
        save_db(force=True)

        alert_msg = f"{lock_fa_name} با موفقیت {status_word} شد!"
        await query.answer(alert_msg, show_alert=False)
        await render_telegram_service_locks_panel(query, cid)
        return

    elif data.startswith("tgl_lock:"):
        parts = data.split(":")
        cid = int(parts[1])
        lock_key = parts[2]
        page = int(parts[3]) if len(parts) > 3 else 1

        if not await is_configured_group_manager(context, cid, user_id):
            await query.answer(" دسترسی غیرمجاز!", show_alert=True)
            return

        g_data = get_group_data(db, cid)
        locks = g_data.setdefault("locks", get_default_locks_structure())
        if not locks.get(lock_key, False):
            try:
                bot_member = await cached_chat_member(context, cid, context.bot.id)
                if bot_member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
                    await query.answer(" ربات ادمین گروه نیست.", show_alert=True)
                    return
            except Exception:
                await query.answer(" ربات ادمین گروه نیست.", show_alert=True)
                return
        locks[lock_key] = not locks.get(lock_key, False)
        
        status_word = "فعال" if locks[lock_key] else "غیرفعال"
        lock_fa_name = ALL_LOCKS.get(lock_key, {}).get("name", lock_key)

        log_admin_action(db, user_id, query.from_user.full_name, g_data.get("title", ""), cid, f"تغییر قفل {lock_fa_name}", f"وضعیت جدید: {status_word}")
        mark_db_dirty()
        save_db(force=True)

        alert_msg = (
            f"قفل {lock_fa_name} با موفقیت فعال شد."
            if locks[lock_key]
            else f"قفل {lock_fa_name} با موفقیت غیرفعال شد."
        )
        await query.answer(alert_msg, show_alert=False)
        await render_group_locks_panel(query, cid, page)
        return

    # SHUTDOWN MENU
    elif data == "panel_shutdown_menu":
        if int(user_id) != int(OWNER_ID):
            await query.answer(" دسترسی غیرمجاز! فقط مالک کل.", show_alert=True)
            return
        await render_shutdown_panel(query, db)
        return

    elif data == "bot_do_turn_on":
        if int(user_id) != int(OWNER_ID):
            await query.answer(" دسترسی غیرمجاز! فقط مالک کل.", show_alert=True)
            return
        db["bot_shutdown"] = False
        mark_db_dirty()
        save_db(force=True)
        await query.answer("ربات با موفقیت روشن شد! ", show_alert=True)
        await render_shutdown_panel(query, db)
        return

    elif data == "bot_do_shutdown":
        if int(user_id) != int(OWNER_ID):
            await query.answer(" دسترسی غیرمجاز! فقط مالک کل.", show_alert=True)
            return
        db["states"]["waiting_shutdown_msg"] = {str(user_id): current_chat_id}
        mark_db_dirty()
        save_db()
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(" لغو", callback_data="cancel_current_flow", style="danger")]])
        await query.message.edit_text("<b>پیام خاموشی را ارسال کنید:</b>\n\n(متن، عکس، گیف، ویدیو، استیکر و... ذخیره می‌شود)", reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    # USER BAN & UNBAN
    elif data == "ban_user_start":
        if int(user_id) != int(OWNER_ID):
            await query.answer(" فقط مالک کل.", show_alert=True)
            return
        clear_user_all_states(db, user_id, current_chat_id)
        db["states"].setdefault("ban_flow", {})[session_k] = {"step": "ban_user_id"}
        mark_db_dirty()
        save_db()
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(" لغو", callback_data="cancel_current_flow", style="danger")]])
        await query.message.edit_text("لطفاً آیدی عددی کاربر را ارسال کنید:", reply_markup=kb)
        return

    elif data == "unban_user_start":
        if int(user_id) != int(OWNER_ID):
            await query.answer(" فقط مالک کل.", show_alert=True)
            return
        clear_user_all_states(db, user_id, current_chat_id)
        db["states"].setdefault("ban_flow", {})[session_k] = {"step": "unban_user_id"}
        mark_db_dirty()
        save_db()
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(" لغو", callback_data="cancel_current_flow", style="danger")]])
        await query.message.edit_text("لطفاً آیدی عددی کاربری که می‌خواهید انبن شود را ارسال کنید:", reply_markup=kb)
        return

    elif data.startswith("ban_group_list_"):
        if int(user_id) != int(OWNER_ID):
            await query.answer(" فقط مالک کل.", show_alert=True)
            return
        page = int(data.replace("ban_group_list_", ""))
        await render_ban_group_picker(query, page, db)
        return

    elif data.startswith("unban_group_list_"):
        if int(user_id) != int(OWNER_ID):
            await query.answer(" فقط مالک کل.", show_alert=True)
            return
        page = int(data.replace("unban_group_list_", ""))
        await render_unban_group_picker(query, page, db)
        return

    elif data.startswith("select_bangrp:"):
        if int(user_id) != int(OWNER_ID):
            await query.answer(" دسترسی غیرمجاز!", show_alert=True)
            return
        target_cid = int(data.replace("select_bangrp:", ""))
        clear_user_all_states(db, user_id, current_chat_id)
        db["states"].setdefault("ban_flow", {})[session_k] = {
            "step": "ban_group_reason",
            "target_cid": target_cid
        }
        mark_db_dirty()
        save_db()
        g_data = get_group_data(db, target_cid)
        title = g_data.get("title") or str(target_cid)
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(" لغو", callback_data="cancel_current_flow", style="danger")]])
        await query.message.edit_text(f"گروه <b>{html.escape(title)}</b> انتخاب شد.\n\nدلیل بن گروه را وارد کنید:", reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    elif data.startswith("select_unbangrp:"):
        if int(user_id) != int(OWNER_ID):
            await query.answer(" دسترسی غیرمجاز!", show_alert=True)
            return
        target_cid_str = data.replace("select_unbangrp:", "")
        if target_cid_str in db.get("global_group_bans", {}):
            del db["global_group_bans"][target_cid_str]
            mark_db_dirty()
            save_db(force=True)
            await send_premium_unban_notification(context.bot, int(target_cid_str), is_group=True)
            await query.answer("بن گروه برداشته شد! ", show_alert=True)
        else:
            await query.answer("این گروه بن نیست.", show_alert=True)
        await render_unban_group_picker(query, 1, db)
        return

    elif data == "owner_fun_named":
        if int(user_id) != int(OWNER_ID):
            await query.answer(" دسترسی غیرمجاز!", show_alert=True)
            return
        await render_owner_fun_panel(query, "named", db)
        return

    elif data == "owner_fun_normal":
        if int(user_id) != int(OWNER_ID):
            await query.answer(" دسترسی غیرمجاز!", show_alert=True)
            return
        await render_owner_fun_panel(query, "normal", db)
        return

    elif data.startswith("own_fun_add:"):
        if int(user_id) != int(OWNER_ID):
            await query.answer(" دسترسی غیرمجاز!", show_alert=True)
            return
        fun_type = data.split(":")[1]
        state_key = "waiting_fun_named_msg" if fun_type == "named" else "waiting_fun_normal_msg"
        db["states"][state_key] = {str(user_id): "global"}
        mark_db_dirty()
        save_db()
        title = "ناموسی" if fun_type == "named" else "عادی"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(" دان", callback_data=f"own_fun_done:{fun_type}", style="success")]])
        await query.message.edit_text(f" لطفاً پاسخ‌های فحش {title} سراسری را بفرستید:\n\nدر پایان « دان» را بزنید.", reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    elif data.startswith("own_fun_done:"):
        fun_type = data.split(":")[1]
        state_key = "waiting_fun_named_msg" if fun_type == "named" else "waiting_fun_normal_msg"
        if str(user_id) in db["states"].get(state_key, {}):
            del db["states"][state_key][str(user_id)]
            mark_db_dirty()
            save_db(force=True)
        await query.answer("تنظیم پاسخ‌ها ذخیره شد.", show_alert=True)
        await render_owner_fun_panel(query, fun_type, db)
        return

    elif data.startswith("own_fun_del_all:"):
        if int(user_id) != int(OWNER_ID):
            await query.answer(" دسترسی غیرمجاز!", show_alert=True)
            return
        fun_type = data.split(":")[1]
        key = "global_fun_named" if fun_type == "named" else "global_fun_normal"
        db[key] = []
        mark_db_dirty()
        save_db(force=True)
        await query.answer("تمام پاسخ‌های این بخش حذف شدند.", show_alert=True)
        await render_owner_fun_panel(query, fun_type, db)
        return

    elif data == "cancel_current_flow":
        clear_user_all_states(db, user_id, current_chat_id)
        await query.answer("عملیات به طور کامل لغو شد. ", show_alert=True)
        await edit_owner_panel_message(query)
        return

    elif data.startswith("panel_owner_groups_"):
        if int(user_id) != int(OWNER_ID):
            await query.answer(" دسترسی غیرمجاز! فقط مالک کل.", show_alert=True)
            return
        page = int(data.split("_")[-1])
        await render_owner_groups_page(query, page, db, context)
        return

    elif data.startswith("ogrp_view:"):
        if int(user_id) != int(OWNER_ID):
            await query.answer(" دسترسی غیرمجاز!", show_alert=True)
            return
        target_cid = int(data.replace("ogrp_view:", ""))
        await render_owner_single_group_panel(query, target_cid, db, context)
        return

    elif data.startswith("ogrp_link:"):
        if int(user_id) != int(OWNER_ID):
            await query.answer(" دسترسی غیرمجاز!", show_alert=True)
            return
        target_cid = int(data.replace("ogrp_link:", ""))
        invite_link = None
        try:
            bot_member = await cached_chat_member(context, target_cid, context.bot.id)
            if bot_member.status == ChatMemberStatus.ADMINISTRATOR:
                invite_link = await context.bot.export_chat_invite_link(target_cid)
        except Exception:
            pass

        if not invite_link:
            g_data = get_group_data(db, target_cid)
            invite_link = g_data.get("invite_link")

        if invite_link:
            await query.message.reply_text(f" <b>لینک گروه:</b>\n{invite_link}", parse_mode=ParseMode.HTML)
        else:
            await query.message.reply_text(
                f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> ربات دسترسی ساخت لینک در گروه را ندارد یا ذخیره نشده است.</b>',
                parse_mode=ParseMode.HTML
            )
        await query.answer()
        return

    elif data.startswith("ogrp_admins:"):
        if int(user_id) != int(OWNER_ID):
            await query.answer(" دسترسی غیرمجاز!", show_alert=True)
            return
        target_cid = int(data.replace("ogrp_admins:", ""))
        g_data = get_group_data(db, target_cid)
        title = g_data.get("title", "گروه")

        report_lines = [
            "GROUP ADMINS",
            "============",
            f"Group: {title}",
            f"Chat ID: {target_cid}",
            ""
        ]

        try:
            admins = await context.bot.get_chat_administrators(target_cid)
            for idx, a in enumerate(admins, 1):
                report_lines.append(f"{idx}.")
                report_lines.append(f"Name: {a.user.full_name}")
                report_lines.append(f"Username: @{a.user.username}" if a.user.username else "Username: None")
                report_lines.append(f"ID: {a.user.id}")
                report_lines.append(f"Status: {a.status}")
                report_lines.append(f"Custom Title: {a.custom_title or 'None'}")
                report_lines.append("")
        except Exception as e:
            report_lines.append(f"Error fetching administrators: {e}")

        report_content = "\n".join(report_lines)
        file_bytes = io.BytesIO(report_content.encode("utf-8"))
        file_bytes.name = f"admins_{target_cid}.txt"
        await query.message.reply_document(document=file_bytes, caption=f" گزارش لیست ادمین‌های گروه <code>{target_cid}</code>", parse_mode=ParseMode.HTML)
        await query.answer()
        return

    elif data.startswith("ogrp_members:"):
        if int(user_id) != int(OWNER_ID):
            await query.answer(" دسترسی غیرمجاز!", show_alert=True)
            return
        target_cid = int(data.replace("ogrp_members:", ""))
        g_data = get_group_data(db, target_cid)
        title = g_data.get("title", "گروه")

        member_count = "نامشخص"
        try:
            member_count = await context.bot.get_chat_member_count(target_cid)
        except Exception:
            pass

        report_lines = [
            "GROUP INFO",
            "==========",
            f"Title: {title}",
            f"Chat ID: {target_cid}",
            f"Member Count: {member_count}",
            "",
            "MEMBERS (Discovered in Database Cache)",
            "=====================================",
            ""
        ]

        active_users = db.get("recent_active_users", {}).get(str(target_cid), [])
        for idx, (uid_str, info) in enumerate(active_users, 1):
            report_lines.append(f"{idx}.")
            report_lines.append(f"Name: {info.get('fullname')}")
            report_lines.append(f"Username: @{info.get('username')}" if info.get("username") else "Username: None")
            report_lines.append(f"ID: {uid_str}")
            report_lines.append("Status: Active/Member")
            report_lines.append("")

        report_content = "\n".join(report_lines)
        file_bytes = io.BytesIO(report_content.encode("utf-8"))
        file_bytes.name = f"members_{target_cid}.txt"
        await query.message.reply_document(document=file_bytes, caption=f" گزارش اعضای در دسترس گروه <code>{target_cid}</code>", parse_mode=ParseMode.HTML)
        await query.answer()
        return

    elif data.startswith("ogrp_search:"):
        if int(user_id) != int(OWNER_ID):
            await query.answer(" دسترسی غیرمجاز!", show_alert=True)
            return
        target_cid = int(data.replace("ogrp_search:", ""))
        db["states"]["waiting_search_query"][str(user_id)] = target_cid
        mark_db_dirty()
        save_db()
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(" لغو", callback_data="cancel_current_flow", style="danger")]])
        await query.message.edit_text(" <b>کلمه یا عبارت موردنظر برای جستجو در لاگ‌های این گروه را ارسال کنید:</b>", reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    elif data == "panel_bcast_type_select":
        if int(user_id) != int(OWNER_ID):
            await query.answer("این بخش مخصوص مالک اصلی است.", show_alert=True)
            return
        buttons = [
            [InlineKeyboardButton(" پیام متنی یا رسانه", callback_data="bcast_mode:media", style="primary")],
            [InlineKeyboardButton(" نظرسنجی معمولی (Poll)", callback_data="bcast_mode:poll", style="primary")],
            [InlineKeyboardButton(" کوئیز (Quiz Poll)", callback_data="bcast_mode:quiz", style="primary")],
            [InlineKeyboardButton(" بازگشت", callback_data="panel_owner_main", style="primary")]
        ]
        await query.message.edit_text(" <b>نوع پیام همگانی (Broadcast) را انتخاب کنید:</b>", reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
        return

    elif data.startswith("bcast_mode:"):
        if int(user_id) != int(OWNER_ID):
            await query.answer("این بخش مخصوص مالک اصلی است.", show_alert=True)
            return
        mode = data.replace("bcast_mode:", "")
        db["states"]["broadcast_builder"][str(user_id)] = {"mode": mode, "step": "dest"}
        mark_db_dirty()
        save_db()

        buttons = [
            [InlineKeyboardButton(" تمام گروه‌ها", callback_data="bcast_dest:groups", style="primary")],
            [InlineKeyboardButton(" گروه خاص", callback_data="bcast_dest:group_select", style="primary")],
            [InlineKeyboardButton(" تمام کاربران خصوصی", callback_data="bcast_dest:users", style="primary")],
            [InlineKeyboardButton(" همه (گروه‌ها + کاربران)", callback_data="bcast_dest:all", style="success")],
            [InlineKeyboardButton(" بازگشت", callback_data="panel_bcast_type_select", style="danger")]
        ]
        await query.message.edit_text(" <b>مقصد ارسال پیام همگانی را انتخاب کنید:</b>", reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
        return

    elif data == "bcast_dest:group_select":
        if int(user_id) != int(OWNER_ID):
            await query.answer("این بخش مخصوص مالک اصلی است.", show_alert=True)
            return
        builder = db["states"]["broadcast_builder"].setdefault(str(user_id), {})
        builder["step"] = "group_select"
        buttons = []
        active_chats = db.get("active_chats", []) or []
        banned_groups = {str(x) for x in (db.get("global_group_bans", {}) or {}).keys()}
        for cid in active_chats:
            if str(cid) in banned_groups:
                continue
            g = get_group_data(db, int(cid))
            title = html.escape(g.get("title") or f"گروه {cid}")
            buttons.append([InlineKeyboardButton(title, callback_data=f"bcast_group:{int(cid)}", style="primary")])
        if not buttons:
            await query.answer("هیچ گروه فعالی برای ارسال پیدا نشد.", show_alert=True)
            return
        buttons.append([InlineKeyboardButton("بازگشت", callback_data="bcast_mode_back_dest", style="danger")])
        await query.message.edit_text(" <b>گروه موردنظر برای ارسال پیام همگانی را انتخاب کنید:</b>", reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
        return

    elif data == "bcast_mode_back_dest":
        if int(user_id) != int(OWNER_ID):
            await query.answer("این بخش مخصوص مالک اصلی است.", show_alert=True)
            return
        builder = db["states"]["broadcast_builder"].setdefault(str(user_id), {})
        buttons = [
            [InlineKeyboardButton(" تمام گروه‌ها", callback_data="bcast_dest:groups", style="primary")],
            [InlineKeyboardButton(" گروه خاص", callback_data="bcast_dest:group_select", style="primary")],
            [InlineKeyboardButton(" تمام کاربران خصوصی", callback_data="bcast_dest:users", style="primary")],
            [InlineKeyboardButton(" همه (گروه‌ها + کاربران)", callback_data="bcast_dest:all", style="success")],
            [InlineKeyboardButton(" بازگشت", callback_data="panel_bcast_type_select", style="danger")]
        ]
        await query.message.edit_text(" <b>مقصد ارسال پیام همگانی را انتخاب کنید:</b>", reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
        return

    elif data.startswith("bcast_group:"):
        if int(user_id) != int(OWNER_ID):
            await query.answer("این بخش مخصوص مالک اصلی است.", show_alert=True)
            return
        try:
            cid = int(data.split(":", 1)[1])
        except (TypeError, ValueError):
            await query.answer("گروه انتخاب‌شده نامعتبر است.", show_alert=True)
            return
        if cid not in [int(x) for x in (db.get("active_chats", []) or [])]:
            await query.answer("این گروه دیگر در فهرست گروه‌های فعال نیست.", show_alert=True)
            return
        builder = db["states"]["broadcast_builder"].setdefault(str(user_id), {})
        builder["dest"] = "specific_group"
        builder["group_id"] = cid
        builder["step"] = "content"
        mark_db_dirty(); save_db()
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("لغو", callback_data="bcast_cancel", style="danger")]])
        mode = builder.get("mode", "media")
        g = get_group_data(db, cid)
        title = html.escape(g.get("title") or str(cid))
        if mode == "media":
            prompt = f" <b>مقصد: {title}</b>\n\n<b>لطفاً متن، عکس، GIF، ویدیو، استیکر یا فایل موردنظر را بفرستید:</b>"
        elif mode == "poll":
            prompt = f" <b>مقصد: {title}</b>\n\n<b>لطفاً نظرسنجی موردنظر را ارسال کنید:</b>\n\n<code>سؤال\nگزینه 1\nگزینه 2</code>"
        else:
            prompt = f" <b>مقصد: {title}</b>\n\n<b>لطفاً کوئیز را به صورت زیر ارسال کنید:</b>\n\n<code>سؤال\nگزینه 1\nگزینه 2\nصحیح: 1</code>"
        await query.message.edit_text(prompt, reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    elif data.startswith("bcast_dest:"):
        if int(user_id) != int(OWNER_ID):
            await query.answer("این بخش مخصوص مالک اصلی است.", show_alert=True)
            return
        dest = data.replace("bcast_dest:", "")
        builder = db["states"]["broadcast_builder"].setdefault(str(user_id), {})
        builder["dest"] = dest
        builder.pop("group_id", None)
        builder["step"] = "content"
        mark_db_dirty()
        save_db()

        kb = InlineKeyboardMarkup([[InlineKeyboardButton(" لغو", callback_data="cancel_current_flow", style="danger")]])
        mode = builder.get("mode", "media")
        if mode == "media":
            await query.message.edit_text(" <b>لطفاً متن، عکس، GIF، ویدیو، استیکر یا فایل موردنظر را بفرستید:</b>", reply_markup=kb, parse_mode=ParseMode.HTML)
        elif mode == "poll":
            await query.message.edit_text(" <b>لطفاً نظرسنجی موردنظر را ارسال کنید:</b>\n\n<code>سؤال\nگزینه 1\nگزینه 2</code>", reply_markup=kb, parse_mode=ParseMode.HTML)
        elif mode == "quiz":
            await query.message.edit_text(" <b>لطفاً کوئیز را به صورت زیر ارسال کنید:</b>\n\n<code>سؤال\nگزینه 1\nگزینه 2\nصحیح: 1</code>", reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    elif data == "bcast_confirm_send":
        if int(user_id) != int(OWNER_ID):
            await query.answer("این بخش مخصوص مالک اصلی است.", show_alert=True)
            return
        builder = db["states"]["broadcast_builder"].get(str(user_id))
        if not builder:
            await query.answer("اطلاعات ارسال یافت نشد.", show_alert=True)
            return

        del db["states"]["broadcast_builder"][str(user_id)]
        mark_db_dirty()
        save_db()

        status_msg = await query.message.reply_text("⏳ <b>شروع عملیات ارسال همگانی...</b>", parse_mode=ParseMode.HTML)
        dest = builder.get("dest", "groups")
        targets = []
        if dest in ["groups", "all"]:
            targets.extend(db.get("active_chats", []))
        elif dest == "specific_group":
            specific_group_id = builder.get("group_id")
            if specific_group_id is not None:
                targets.append(int(specific_group_id))
        if dest in ["users", "all"]:
            targets.extend([int(u) for u in db.get("started_users", {}).keys()])

        succ, fail = 0, 0
        b_type = builder.get("type")

        for tid in targets:
            try:
                if b_type == "poll":
                    p_data = builder["poll_data"]
                    await context.bot.send_poll(
                        chat_id=tid,
                        question=p_data["question"],
                        options=p_data["options"],
                        is_anonymous=p_data.get("is_anonymous", True),
                        type=PollType.QUIZ if p_data.get("is_quiz") else PollType.REGULAR,
                        correct_option_id=p_data.get("correct_option_id")
                    )
                elif b_type == "media":
                    await send_media_payload(context.bot, tid, builder["payload"])
                succ += 1
                await asyncio.sleep(0.04)
            except Exception:
                fail += 1

        await status_msg.edit_text(f" <b>عملیات ارسال همگانی به پایان رسید.</b>\n\n ارسال موفق: <code>{succ}</code>\n ناموفق: <code>{fail}</code>", parse_mode=ParseMode.HTML)
        await query.answer()
        return

    elif data == "bcast_cancel":
        if int(user_id) != int(OWNER_ID):
            await query.answer("این بخش مخصوص مالک اصلی است.", show_alert=True)
            return
        clear_user_all_states(db, user_id, current_chat_id)
        await query.message.edit_text(
            f'<b><tg-emoji emoji-id="{CROSS_CUSTOM_EMOJI_ID}">❌</tg-emoji> عملیات ارسال همگانی لغو شد.</b>',
            parse_mode=ParseMode.HTML
        )
        return

    # GROUP ADMIN ADVANCED
    elif data.startswith("panel_group_main:"):
        cid = int(data.replace("panel_group_main:", ""))
        if not await is_configured_group_manager(context, cid, user_id):
            await query.answer(" دسترسی غیرمجاز!", show_alert=True)
            return
        if not get_group_panel_session(db, cid, query.message.message_id):
            register_group_panel_session(db, cid, query.message.message_id, user_id)
        await render_group_admin_panel_message(query, cid)
        return

    elif data.startswith("panel_group_advanced:"):
        cid = int(data.replace("panel_group_advanced:", ""))
        if not await is_configured_group_manager(context, cid, user_id):
            await query.answer(" دسترسی غیرمجاز!", show_alert=True)
            return
        
        text = get_advanced_status_text(db, cid)
        buttons = build_advanced_panel_keyboard(cid)
        await query.message.edit_text(text, reply_markup=buttons, parse_mode=ParseMode.HTML)
        return

    elif data.startswith("advanced_warnings:"):
        cid = int(data.split(":")[1])
        if not await is_configured_group_manager(context, cid, user_id):
            await query.answer(" دسترسی غیرمجاز!", show_alert=True); return
        await render_warning_panel(query, cid, db)
        return

    elif data.startswith("warning_noop:") or data.startswith("warning_temp_noop:"):
        await query.answer(); return

    elif data.startswith("warning_inc:") or data.startswith("warning_dec:"):
        cid = int(data.split(":")[1])
        if not await is_configured_group_manager(context, cid, user_id):
            await query.answer(" دسترسی غیرمجاز!", show_alert=True); return
        g = get_group_data(db, cid); s = g.setdefault("warning_settings", {"count": 3, "punishment": None, "temp_mute_hours": 1})
        delta = 1 if data.startswith("warning_inc:") else -1
        s["count"] = max(1, min(20, int(s.get("count", 3)) + delta))
        mark_db_dirty(); save_db(force=True)
        await render_warning_panel(query, cid, db); await query.answer(); return

    elif data.startswith("warning_mode:"):
        _, mode, cid_s = data.split(":", 2); cid = int(cid_s)
        if not await is_configured_group_manager(context, cid, user_id):
            await query.answer(" دسترسی غیرمجاز!", show_alert=True); return
        g = get_group_data(db, cid); s = g.setdefault("warning_settings", {"count": 3, "punishment": None, "temp_mute_hours": 1})
        if s.get("punishment") == mode:
            label = {"temp_mute": "سکوت موقت", "mute": "سکوت", "kick": "اخراج"}[mode]
            await query.answer(f"حالت {label} از قبل فعال است.", show_alert=True); return
        if mode in ("temp_mute", "mute", "kick") and not await bot_can_restrict_members(context, cid):
            await query.answer(" ربات دسترسی سکوت و بن کردن را ندارد.", show_alert=True); return
        s["punishment"] = mode
        if mode != "temp_mute": s["temp_mute_hours"] = max(1, int(s.get("temp_mute_hours", 1)))
        mark_db_dirty(); save_db(force=True)
        await render_warning_panel(query, cid, db); await query.answer(); return

    elif data.startswith("warning_temp_inc:") or data.startswith("warning_temp_dec:"):
        cid = int(data.split(":")[1])
        if not await is_configured_group_manager(context, cid, user_id):
            await query.answer(" دسترسی غیرمجاز!", show_alert=True); return
        g = get_group_data(db, cid); s = g.setdefault("warning_settings", {"count": 3, "punishment": "temp_mute", "temp_mute_hours": 1})
        delta = 1 if data.startswith("warning_temp_inc:") else -1
        s["temp_mute_hours"] = max(1, min(720, int(s.get("temp_mute_hours", 1)) + delta))
        mark_db_dirty(); save_db(force=True)
        await render_warning_panel(query, cid, db); await query.answer(); return

    elif data.startswith("warning_back:"):
        cid = int(data.split(":")[1])
        if not await is_configured_group_manager(context, cid, user_id):
            await query.answer(" دسترسی غیرمجاز!", show_alert=True); return
        text = get_advanced_status_text(db, cid)
        await query.message.edit_text(text, reply_markup=build_advanced_panel_keyboard(cid), parse_mode=ParseMode.HTML)
        return
    elif data.startswith("advanced_"):
        await query.answer("COMING SOON...!", show_alert=True)
        return

    elif data.startswith("panel_group_lists:"):
        cid = int(data.replace("panel_group_lists:", ""))
        if not await is_configured_group_manager(context, cid, user_id):
            await query.answer(" دسترسی غیرمجاز!", show_alert=True)
            return
        
        g_data = get_group_data(db, cid)
        text = await build_group_lists_status(context, cid, db, g_data)
        
        buttons = [
            [
                InlineKeyboardButton("مالکین", callback_data=f"list_owners:{cid}", style="primary", icon_custom_emoji_id="6060078591276749279"),
                InlineKeyboardButton("مدیران", callback_data=f"list_admins:{cid}", style="primary", icon_custom_emoji_id="6057831537401925660")
            ],
            [
                InlineKeyboardButton("اعضای ویژه", callback_data=f"list_special:{cid}", style="primary", icon_custom_emoji_id="6294080753298837622"),
                InlineKeyboardButton("کلمات فیلتر", callback_data=f"list_filters:{cid}", style="primary", icon_custom_emoji_id="6086622219310470226")
            ],
            [
                InlineKeyboardButton("سکوت‌ شده‌ها", callback_data=f"list_muted:{cid}", style="primary", icon_custom_emoji_id="5886328760218688328"),
                InlineKeyboardButton("بن‌شده‌ها", callback_data=f"list_banned:{cid}", style="primary", icon_custom_emoji_id="5872823922751185495")
            ],
            [
                InlineKeyboardButton("لیست معاف", callback_data=f"list_exempt:{cid}", style="primary", icon_custom_emoji_id="5884078304729767721"),
                InlineKeyboardButton("لیست اخطار", callback_data=f"list_warns:{cid}", style="primary", icon_custom_emoji_id="5911318301580991657")
            ],
            [
                InlineKeyboardButton("پاسخ‌دهی خودکار", callback_data=f"list_auto_resp:{cid}", style="primary", icon_custom_emoji_id="5859316800361077930"),
                InlineKeyboardButton("کامنت‌گذاری", callback_data=f"list_comments:{cid}", style="primary", icon_custom_emoji_id="5908745251098473369")
            ],
            [
                InlineKeyboardButton("بررسی کاربر", callback_data=f"list_check_user:{cid}", style="primary", icon_custom_emoji_id="5884362854903064294")
            ],
            [
                InlineKeyboardButton("بازگشت", callback_data=f"panel_group_main:{cid}", style="danger", icon_custom_emoji_id="5983093054842606366")
            ]
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
        return

    elif data == "check_user_close":
        clear_user_all_states(db, user_id, current_chat_id)
        await query.message.edit_text(
            build_check_user_close_text(),
            reply_markup=None,
            parse_mode=ParseMode.HTML
        )
        await query.answer()
        return

    elif data == "check_user_back_to_lists":
        clear_user_all_states(db, user_id, current_chat_id)
        cid = current_chat_id
        if not await is_configured_group_manager(context, cid, user_id):
            await query.answer(" دسترسی غیرمجاز!", show_alert=True)
            return
        g_data = get_group_data(db, cid)
        text = await build_group_lists_status(context, cid, db, g_data)
        buttons = [
            [
                InlineKeyboardButton("مالکین", callback_data=f"list_owners:{cid}", style="primary", icon_custom_emoji_id="6060078591276749279"),
                InlineKeyboardButton("مدیران", callback_data=f"list_admins:{cid}", style="primary", icon_custom_emoji_id="6057831537401925660")
            ],
            [
                InlineKeyboardButton("اعضای ویژه", callback_data=f"list_special:{cid}", style="primary", icon_custom_emoji_id="6294080753298837622"),
                InlineKeyboardButton("کلمات فیلتر", callback_data=f"list_filters:{cid}", style="primary", icon_custom_emoji_id="6086622219310470226")
            ],
            [
                InlineKeyboardButton("سکوت‌ شده‌ها", callback_data=f"list_muted:{cid}", style="primary", icon_custom_emoji_id="5886328760218688328"),
                InlineKeyboardButton("بن‌شده‌ها", callback_data=f"list_banned:{cid}", style="primary", icon_custom_emoji_id="5872823922751185495")
            ],
            [
                InlineKeyboardButton("لیست معاف", callback_data=f"list_exempt:{cid}", style="primary", icon_custom_emoji_id="5884078304729767721"),
                InlineKeyboardButton("لیست اخطار", callback_data=f"list_warns:{cid}", style="primary", icon_custom_emoji_id="5911318301580991657")
            ],
            [
                InlineKeyboardButton("پاسخ‌دهی خودکار", callback_data=f"list_auto_resp:{cid}", style="primary", icon_custom_emoji_id="5859316800361077930"),
                InlineKeyboardButton("کامنت‌گذاری", callback_data=f"list_comments:{cid}", style="primary", icon_custom_emoji_id="5908745251098473369")
            ],
            [
                InlineKeyboardButton("بررسی کاربر", callback_data=f"list_check_user:{cid}", style="primary", icon_custom_emoji_id="5884362854903064294")
            ],
            [
                InlineKeyboardButton("بازگشت", callback_data=f"panel_group_main:{cid}", style="danger", icon_custom_emoji_id=CLOSE_CUSTOM_EMOJI_ID)
            ]
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
        await query.answer()
        return

    elif data.startswith("list_check_user:"):
        cid = int(data.replace("list_check_user:", ""))
        if not await is_configured_group_manager(context, cid, user_id):
            await query.answer(" دسترسی غیرمجاز!", show_alert=True)
            return
        db.setdefault("states", {}).setdefault("waiting_check_user", {})[str(user_id)] = {
            "chat_id": cid, "panel_message_id": query.message.message_id,
            "return_to_advanced": False, "return_to_lists": True
        }
        mark_db_dirty(); save_db(force=True)
        await query.answer("آیدی عددی یا یوزرنیم را ارسال کن.")
        await query.message.edit_text(
            build_check_user_prompt_text(),
            reply_markup=build_check_user_keyboard(),
            parse_mode=ParseMode.HTML
        )
        return

    elif data == "check_user_direct":
        await query.answer("آیدی عددی یا یوزرنیم را ارسال کن.")
        await open_check_user_panel(update, context, return_to_advanced=False, edit_message=query.message)
        return

    elif data.startswith("list_detail:"):
        _, list_type, cid_s = data.split(":", 2)
        cid = int(cid_s)
        if not await is_configured_group_manager(context, cid, user_id):
            await query.answer(" دسترسی غیرمجاز!", show_alert=True); return
        await render_group_list_detail(query, context, cid, list_type, db); return

    elif data.startswith(("list_owners:", "list_admins:", "list_special:", "list_muted:", "list_banned:", "list_exempt:", "list_warns:")):
        prefix = data.split(":", 1)[0]; cid = int(data.split(":", 1)[1])
        if not await is_configured_group_manager(context, cid, user_id):
            await query.answer(" دسترسی غیرمجاز!", show_alert=True); return
        list_type = {"list_owners":"owners", "list_admins":"admins", "list_special":"special", "list_muted":"muted", "list_banned":"banned", "list_exempt":"exempt", "list_warns":"warns"}[prefix]
        await render_group_list_detail(query, context, cid, list_type, db); return

    elif data.startswith("list_cleanup_confirm:"):
        _, list_type, cid_s = data.split(":", 2); cid = int(cid_s)
        g = get_group_data(db, cid)
        allowed = await is_configured_group_manager(context, cid, user_id)
        if list_type == "owners": allowed = await is_primary_or_bot_owner_of_group(context, cid, g, user_id)
        if not allowed:
            if list_type == "owners":
                await query.answer("این دستور فقط مختص مالک گروه میباشد.", show_alert=True)
            else:
                await query.answer(" دسترسی غیرمجاز!", show_alert=True)
            return
        await render_cleanup_confirm(query, list_type, cid); return

    elif data.startswith("list_cleanup_cancel:"):
        _, list_type, cid_s = data.split(":", 2); cid = int(cid_s)
        g = get_group_data(db, cid)
        allowed = await is_configured_group_manager(context, cid, user_id)
        if list_type == "owners": allowed = await is_primary_or_bot_owner_of_group(context, cid, g, user_id)
        if not allowed:
            if list_type == "owners":
                await query.answer("این دستور فقط مختص مالک گروه میباشد.", show_alert=True)
            else:
                await query.answer(" دسترسی غیرمجاز!", show_alert=True)
            return
        names = {"owners": "مالکین", "admins": "مدیران", "special": "ویژه", "exempt": "معاف", "warns": "اخطارها", "muted": "سکوت ها", "banned": "بن ها"}
        name = names.get(list_type, "لیست")
        await query.message.edit_text(f'<b><tg-emoji emoji-id="{PREMIUM_OK_EMOJI}">✔️</tg-emoji> پاکسازی لیست {name} با موفقیت لغو شد.</b>', reply_markup=None, parse_mode=ParseMode.HTML)
        await query.answer(); return

    elif data.startswith("list_cleanup:"):
        _, list_type, cid_s = data.split(":", 2); cid = int(cid_s)
        g = get_group_data(db, cid); allowed = await is_configured_group_manager(context, cid, user_id)
        if list_type == "owners": allowed = await is_primary_or_bot_owner_of_group(context, cid, g, user_id)
        if not allowed:
            if list_type == "owners":
                await query.answer("این دستور فقط مختص مالک گروه میباشد.", show_alert=True)
            else:
                await query.answer(" دسترسی غیرمجاز!", show_alert=True)
            return
        # A list may become empty between the command and confirmation.
        mgmt = g.get("management", {}) or {}
        current_values = {
            "owners": mgmt.get("owners", []),
            "admins": mgmt.get("admins", []),
            "special": mgmt.get("special", []),
            "exempt": mgmt.get("exempt", []),
            "warns": g.get("warnings", {}),
            "muted": g.get("muted_users", {}),
            "banned": g.get("banned_users", {}),
        }.get(list_type, [])
        if not current_values:
            names = {"owners": "مالکین", "admins": "مدیران", "special": "ویژه", "exempt": "معاف", "warns": "اخطارها", "muted": "سکوت ها", "banned": "بن ها"}
            name = names.get(list_type, "لیست")
            await query.message.edit_text(f'<b><tg-emoji emoji-id="{PREMIUM_OK_EMOJI}">✔️</tg-emoji> لیست {name} از قبل خالی می‌باشد.</b>', reply_markup=None, parse_mode=ParseMode.HTML)
            await query.answer()
            return
        if list_type in ("owners", "admins", "special", "exempt"):
            if list_type == "owners":
                primary = (g.get("management", {}) or {}).get("primary_owner_id")
                g["management"]["owners"] = [int(primary)] if primary else []
            else:
                g["management"][list_type] = []
        elif list_type == "warns": g["warnings"] = {}
        elif list_type == "muted":
            for uid in list(g.get("muted_users", {})):
                try: await context.bot.restrict_chat_member(cid, int(uid), permissions=full_group_permissions())
                except Exception: pass
            g["muted_users"] = {}
        elif list_type == "banned":
            for uid in list(g.get("banned_users", {})):
                try: await context.bot.unban_chat_member(cid, int(uid), only_if_banned=True)
                except Exception: pass
            g["banned_users"] = {}
        mark_db_dirty(); save_db(force=True)
        names = {"owners": "مالکین", "admins": "مدیران", "special": "ویژه", "exempt": "معاف", "warns": "اخطارها", "muted": "سکوت ها", "banned": "بن ها"}
        name = names.get(list_type, "لیست")
        await query.message.edit_text(f'<b><tg-emoji emoji-id="{PREMIUM_OK_EMOJI}">✔️</tg-emoji> پاکسازی لیست {name} با موفقیت انجام شد.</b>', reply_markup=None, parse_mode=ParseMode.HTML)
        await query.answer(); return

    elif data.startswith("panel_list_poems:"):
        cid = int(data.replace("panel_list_poems:", ""))
        if not await is_configured_group_manager(context, cid, user_id):
            await query.answer(" دسترسی غیرمجاز!", show_alert=True)
            return
        g_data = get_group_data(db, cid)
        poems_list = g_data.get("poems", [])
        if not poems_list:
            text = " <b>هنوز شعری برای این گروه ثبت نشده است.</b>"
        else:
            text = " <b>لیست شعارهای فعال این گروه:</b>\n\n"
            for idx, p in enumerate(poems_list, 1):
                clean_p = html.escape(p).replace("{name}", "نام‌کاربر")
                text += f"{idx}. {clean_p}\n"

        buttons = [[InlineKeyboardButton(" بازگشت", callback_data=f"panel_group_lists:{cid}", style="primary")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
        return

    elif data.startswith("panel_list_foods:"):
        cid = int(data.replace("panel_list_foods:", ""))
        if not await is_configured_group_manager(context, cid, user_id):
            await query.answer(" دسترسی غیرمجاز!", show_alert=True)
            return
        g_data = get_group_data(db, cid)
        foods = g_data.get("foods", [])
        text = " <b>لیست غذاهای ذخیره‌شده گروه:</b>\n\n" + ", ".join(foods)
        buttons = [[InlineKeyboardButton(" بازگشت", callback_data=f"panel_group_lists:{cid}", style="primary")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
        return

    elif data == "owner_list_poems":
        if int(user_id) != int(OWNER_ID):
            await query.answer(" دسترسی غیرمجاز!", show_alert=True)
            return
        poems_list = db.get("global_poems", DEFAULT_POEMS)
        if not poems_list:
            text = " <b>هنوز شعری ثبت نشده است.</b>"
        else:
            text = " <b>لیست شعارهای سراسری ربات:</b>\n\n"
            for idx, p in enumerate(poems_list, 1):
                clean_p = html.escape(p).replace("{name}", "نام‌کاربر")
                text += f"{idx}. {clean_p}\n"
        buttons = [[InlineKeyboardButton(" بازگشت", callback_data="panel_owner_main", style="primary")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
        return    

    elif data == "owner_list_foods":
        if int(user_id) != int(OWNER_ID):
            await query.answer(" دسترسی غیرمجاز!", show_alert=True)
            return
        foods = db.get("global_foods", DEFAULT_FOODS)
        text = " <b>لیست غذاهای سراسری ربات:</b>\n\n" + ", ".join(foods)
        buttons = [[InlineKeyboardButton(" بازگشت", callback_data="panel_owner_main", style="primary")]]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
        return

    elif data == "owner_add_poem":
        if int(user_id) != int(OWNER_ID):
            await query.answer(" دسترسی غیرمجاز!", show_alert=True)
            return
        db["states"]["waiting_owner_add_poem"] = {str(user_id): current_chat_id}
        mark_db_dirty()
        save_db()
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(" لغو", callback_data="cancel_current_flow", style="danger")]])
        await query.message.edit_text(" شعر جدید سراسری را با استفاده از <code>{name}</code> یا <code>یوزرنیم</code> بفرستید:", reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    elif data == "owner_add_food":
        if int(user_id) != int(OWNER_ID):
            await query.answer(" دسترسی غیرمجاز!", show_alert=True, style="danger")
            return
        db["states"]["waiting_owner_add_food"] = {str(user_id): current_chat_id}
        mark_db_dirty()
        save_db()
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(" لغو", callback_data="cancel_current_flow", style="danger")]])
        await query.message.edit_text(" نام غذای جدید سراسری که می‌خواهید اضافه شود را بنویسید:", reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    elif data == "panel_group_close":
        try:
            close_text = f'• پنل با موفقیت بسته شد! <tg-emoji emoji-id="{PARTY_CUSTOM_EMOJI_ID}">🎉</tg-emoji>'
            clear_group_panel_session(db, current_chat_id, query.message.message_id)
            await query.message.edit_text(close_text, reply_markup=None, parse_mode=ParseMode.HTML)
        except Exception:
            try:
                await query.message.delete()
            except Exception:
                pass
        await query.answer()
        return

    elif data == "panel_user_broadcast":
        if int(user_id) != int(OWNER_ID):
            await query.answer("این بخش مخصوص مالک اصلی است.", show_alert=True)
            return
        started_users = db.get("started_users", {})
        user_count = len(started_users)
        text = f" <b>پیام همگانی به تمام کاربران خصوصی ربات</b>\n\n <b>تعداد کاربران دریافت‌کننده:</b> <code>{user_count}</code> نفر"
        buttons = [
            [InlineKeyboardButton(" ارسال پیام همگانی", callback_data="user_broadcast_send", style="success")],
            [InlineKeyboardButton(" بازگشت", callback_data="panel_owner_main", style="primary")]
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
        return

    elif data == "user_broadcast_send":
        if int(user_id) != int(OWNER_ID):
            await query.answer("این بخش مخصوص مالک اصلی است.", show_alert=True)
            return
        db["states"]["waiting_user_broadcast_msg"] = {str(user_id): current_chat_id}
        mark_db_dirty()
        save_db()
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(" لغو", callback_data="cancel_current_flow", style="danger")]])
        await query.message.edit_text("<b> پیام مورد نظر برای ارسال به تمام کاربران خصوصی ربات را بفرستید:</b>", reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    elif data.startswith("list_comments:"):
        cid = int(data.replace("list_comments:", ""))
        await render_comment_panel(query, context, cid, db)
        return

    elif data.startswith("panel_comment:"):
        cid = int(data.replace("panel_comment:", ""))
        await render_comment_panel(query, context, cid, db)
        return

    elif data.startswith("comment_main_back:"):
        cid = int(data.replace("comment_main_back:", ""))
        if not await comment_panel_owner(query, context, db, cid):
            return
        clear_comment_panel_session(db, user_id)
        g_data = get_group_data(db, cid)
        text = await build_group_lists_status(context, cid, db, g_data)
        buttons = [
            [
                InlineKeyboardButton("مالکین", callback_data=f"list_owners:{cid}", style="primary", icon_custom_emoji_id="6060078591276749279"),
                InlineKeyboardButton("مدیران", callback_data=f"list_admins:{cid}", style="primary", icon_custom_emoji_id="6057831537401925660")
            ],
            [
                InlineKeyboardButton("اعضای ویژه", callback_data=f"list_special:{cid}", style="primary", icon_custom_emoji_id="6294080753298837622"),
                InlineKeyboardButton("کلمات فیلتر", callback_data=f"list_filters:{cid}", style="primary", icon_custom_emoji_id="6086622219310470226")
            ],
            [
                InlineKeyboardButton("سکوت‌ شده‌ها", callback_data=f"list_muted:{cid}", style="primary", icon_custom_emoji_id="5886328760218688328"),
                InlineKeyboardButton("بن‌شده‌ها", callback_data=f"list_banned:{cid}", style="primary", icon_custom_emoji_id="5872823922751185495")
            ],
            [
                InlineKeyboardButton("لیست معاف", callback_data=f"list_exempt:{cid}", style="primary", icon_custom_emoji_id="5884078304729767721"),
                InlineKeyboardButton("لیست اخطار", callback_data=f"list_warns:{cid}", style="primary", icon_custom_emoji_id="5911318301580991657")
            ],
            [
                InlineKeyboardButton("پاسخ‌دهی خودکار", callback_data=f"list_auto_resp:{cid}", style="primary", icon_custom_emoji_id="5859316800361077930"),
                InlineKeyboardButton("کامنت‌گذاری", callback_data=f"list_comments:{cid}", style="primary", icon_custom_emoji_id="5908745251098473369")
            ],
            [InlineKeyboardButton("بررسی کاربر", callback_data=f"list_check_user:{cid}", style="primary", icon_custom_emoji_id="5884362854903064294")],
            [InlineKeyboardButton("بازگشت", callback_data=f"panel_group_main:{cid}", style="danger", icon_custom_emoji_id=BACK_CUSTOM_EMOJI_ID)]
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
        return

    elif data.startswith("list_auto_resp:"):
        cid = int(data.replace("list_auto_resp:", ""))
        await open_auto_response_panel(query, context, cid, db)
        return

    elif data.startswith("auto_access:"):
        _, cid_s, access = data.split(":", 2)
        await auto_response_access_callback(query, context, int(cid_s), access)
        return

    elif data.startswith("auto_cleanup:"):
        _, cid_s, decision = data.split(":", 2)
        await auto_response_cleanup_callback(query, context, int(cid_s), decision == "yes")
        return

    elif data.startswith("comment_set:"):
        cid = int(data.replace("comment_set:", ""))
        if not await comment_panel_owner(query, context, db, cid):
            return
        db.setdefault("states", {}).setdefault("waiting_comment_msg", {})[str(user_id)] = {
            "chat_id": int(cid), "panel_message_id": int(query.message.message_id)
        }
        mark_db_dirty(); save_db(force=True)
        await query.message.edit_text(
            comment_setup_prompt(),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("بازگشت", callback_data=f"comment_main_back:{cid}", style="danger", icon_custom_emoji_id=BACK_CUSTOM_EMOJI_ID)
            ]]),
            parse_mode=ParseMode.HTML
        )
        return

    elif data.startswith("comment_panel_back:"):
        # The back button from the comment setup screen must return to the
        # group's LISTS panel, not reopen the same comment screen.
        cid = int(data.replace("comment_panel_back:", ""))
        if not await comment_panel_owner(query, context, db, cid):
            return
        db.setdefault("states", {}).setdefault("waiting_comment_msg", {}).pop(str(user_id), None)
        clear_comment_panel_session(db, user_id)
        g_data = get_group_data(db, cid)
        text = await build_group_lists_status(context, cid, db, g_data)
        buttons = [
            [
                InlineKeyboardButton("مالکین", callback_data=f"list_owners:{cid}", style="primary", icon_custom_emoji_id="6060078591276749279"),
                InlineKeyboardButton("مدیران", callback_data=f"list_admins:{cid}", style="primary", icon_custom_emoji_id="6057831537401925660")
            ],
            [
                InlineKeyboardButton("اعضای ویژه", callback_data=f"list_special:{cid}", style="primary", icon_custom_emoji_id="6294080753298837622"),
                InlineKeyboardButton("کلمات فیلتر", callback_data=f"list_filters:{cid}", style="primary", icon_custom_emoji_id="6086622219310470226")
            ],
            [
                InlineKeyboardButton("سکوت‌ شده‌ها", callback_data=f"list_muted:{cid}", style="primary", icon_custom_emoji_id="5886328760218688328"),
                InlineKeyboardButton("بن‌شده‌ها", callback_data=f"list_banned:{cid}", style="primary", icon_custom_emoji_id="5872823922751185495")
            ],
            [
                InlineKeyboardButton("لیست معاف", callback_data=f"list_exempt:{cid}", style="primary", icon_custom_emoji_id="5884078304729767721"),
                InlineKeyboardButton("لیست اخطار", callback_data=f"list_warns:{cid}", style="primary", icon_custom_emoji_id="5911318301580991657")
            ],
            [
                InlineKeyboardButton("پاسخ‌دهی خودکار", callback_data=f"list_auto_resp:{cid}", style="primary", icon_custom_emoji_id="5859316800361077930"),
                InlineKeyboardButton("کامنت‌گذاری", callback_data=f"list_comments:{cid}", style="primary", icon_custom_emoji_id="5908745251098473369")
            ],
            [InlineKeyboardButton("بررسی کاربر", callback_data=f"list_check_user:{cid}", style="primary", icon_custom_emoji_id="5884362854903064294")],
            [InlineKeyboardButton("بازگشت", callback_data=f"panel_group_main:{cid}", style="danger", icon_custom_emoji_id=BACK_CUSTOM_EMOJI_ID)]
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
        await query.answer()
        return

    elif data.startswith("comment_set_cancel:"):
        cid = int(data.replace("comment_set_cancel:", ""))
        if not await comment_panel_owner(query, context, db, cid):
            return
        db.setdefault("states", {}).setdefault("waiting_comment_msg", {}).pop(str(user_id), None)
        clear_comment_panel_session(db, user_id)
        g_data = get_group_data(db, cid)
        text = await build_group_lists_status(context, cid, db, g_data)
        buttons = [
            [InlineKeyboardButton("مالکین", callback_data=f"list_owners:{cid}", style="primary", icon_custom_emoji_id="6060078591276749279"), InlineKeyboardButton("مدیران", callback_data=f"list_admins:{cid}", style="primary", icon_custom_emoji_id="6057831537401925660")],
            [InlineKeyboardButton("اعضای ویژه", callback_data=f"list_special:{cid}", style="primary", icon_custom_emoji_id="6294080753298837622"), InlineKeyboardButton("کلمات فیلتر", callback_data=f"list_filters:{cid}", style="primary", icon_custom_emoji_id="6086622219310470226")],
            [InlineKeyboardButton("سکوت‌ شده‌ها", callback_data=f"list_muted:{cid}", style="primary", icon_custom_emoji_id="5886328760218688328"), InlineKeyboardButton("بن‌شده‌ها", callback_data=f"list_banned:{cid}", style="primary", icon_custom_emoji_id="5872823922751185495")],
            [InlineKeyboardButton("لیست معاف", callback_data=f"list_exempt:{cid}", style="primary", icon_custom_emoji_id="5884078304729767721"), InlineKeyboardButton("لیست اخطار", callback_data=f"list_warns:{cid}", style="primary", icon_custom_emoji_id="5911318301580991657")],
            [InlineKeyboardButton("پاسخ‌دهی خودکار", callback_data=f"list_auto_resp:{cid}", style="primary", icon_custom_emoji_id="5859316800361077930"), InlineKeyboardButton("کامنت‌گذاری", callback_data=f"list_comments:{cid}", style="primary", icon_custom_emoji_id="5908745251098473369")],
            [InlineKeyboardButton("بررسی کاربر", callback_data=f"list_check_user:{cid}", style="primary", icon_custom_emoji_id="5884362854903064294")],
            [InlineKeyboardButton("بازگشت", callback_data=f"panel_group_main:{cid}", style="danger", icon_custom_emoji_id=BACK_CUSTOM_EMOJI_ID)]
        ]
        await query.message.edit_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode=ParseMode.HTML)
        await query.answer()
        return

    elif data.startswith("comment_list_close:"):
        cid = int(data.replace("comment_list_close:", ""))
        if not await comment_panel_owner(query, context, db, cid):
            return
        await query.message.edit_text(
            f'<b><tg-emoji emoji-id="{CHECK_CUSTOM_EMOJI_ID}">💠</tg-emoji> لیست کامنت با موفقیت بسته شد.</b>',
            parse_mode=ParseMode.HTML
        )
        clear_comment_panel_session(db, user_id); save_db(force=True)
        return

    elif data.startswith("comment_cleanup_confirm:"):
        cid = int(data.replace("comment_cleanup_confirm:", ""))
        await comment_cleanup_confirm(query, context, cid, db)
        return

    elif data.startswith("comment_cleanup:"):
        _, decision, cid_s = data.split(":", 2)
        cid = int(cid_s)
        await comment_cleanup_execute(query, context, cid, db, decision == "yes")
        return

    elif data.startswith("comment_toggle:"):
        # Kept for backwards compatibility with old keyboards.
        cid = int(data.replace("comment_toggle:", ""))
        if not await comment_panel_owner(query, context, db, cid):
            return
        g = get_group_data(db, cid)
        c = _comment_settings(g)
        c["enabled"] = not c.get("enabled", False)
        mark_db_dirty(); save_db(force=True)
        await render_comment_panel(query, context, cid, db)
        return

    elif data.startswith("comment_delete:"):
        cid = int(data.replace("comment_delete:", ""))
        await comment_cleanup_confirm(query, context, cid, db)
        return

    elif data.startswith("comment_cmd_close:"):
        _, cid_s, owner_s = data.split(":", 2)
        cid, owner = int(cid_s), int(owner_s)
        if int(user_id) != owner or not await is_configured_group_manager(context, cid, user_id):
            await query.answer("این پنل برای شما نیست.", show_alert=True)
            return
        await query.message.edit_text(
            f'<b><tg-emoji emoji-id="{CHECK_CUSTOM_EMOJI_ID}">💠</tg-emoji> لیست کامنت با موفقیت بسته شد.</b>',
            parse_mode=ParseMode.HTML)
        clear_comment_panel_session(db, user_id); save_db(force=True)
        return

    elif data.startswith("comment_cmd_cleanup:"):
        _, decision, cid_s, owner_s = data.split(":", 3)
        cid, owner = int(cid_s), int(owner_s)
        if int(user_id) != owner or not await is_admin_or_owner(context, cid, user_id):
            await query.answer("این پنل برای شما نیست.", show_alert=True)
            return
        if decision == "yes":
            g = get_group_data(db, cid)
            g["comment"] = {"enabled": False, "custom": False, "payload": None}
            text = f'<b><tg-emoji emoji-id="{CHECK_CUSTOM_EMOJI_ID}">✅</tg-emoji> کامنت با موفقیت حذف شد.</b>'
        else:
            text = f'<b><tg-emoji emoji-id="{CHECK_CUSTOM_EMOJI_ID}">✅</tg-emoji> پنل پاکسازی کامنت با موفقیت بسته شد.</b>'
        await query.message.edit_text(text, parse_mode=ParseMode.HTML)
        clear_comment_panel_session(db, user_id); mark_db_dirty(); save_db(force=True)
        return

    elif data.startswith("panel_welcome:"):
        cid = int(data.replace("panel_welcome:", ""))
        if not await is_configured_group_manager(context, cid, user_id):
            await query.answer(" دسترسی غیرمجاز!", show_alert=True)
            return
        await render_welcome_panel_message(query, cid, db)
        return

    elif data.startswith("welcome_toggle:"):
        cid = int(data.replace("welcome_toggle:", ""))
        if not await is_configured_group_manager(context, cid, user_id):
            await query.answer(" دسترسی غیرمجاز!", show_alert=True)
            return
        g_data = get_group_data(db, cid)
        w_set = g_data.setdefault("welcome", {"enabled": True, "custom": False})
        w_set["enabled"] = not w_set.get("enabled", True)
        log_admin_action(db, user_id, query.from_user.full_name, g_data.get("title", ""), cid, "تغییر Welcome", f"وضعیت: {w_set['enabled']}")
        mark_db_dirty()
        save_db()
        await render_welcome_panel_message(query, cid, db)
        return

    elif data.startswith("welcome_set:"):
        cid = int(data.replace("welcome_set:", ""))
        if not await is_configured_group_manager(context, cid, user_id):
            await query.answer(" دسترسی غیرمجاز!", show_alert=True)
            return
        db["states"]["waiting_welcome_msg"][str(user_id)] = cid
        mark_db_dirty()
        save_db()
        prompt_text = (
            "<b> تنظیم پیام خوش‌آمدگویی اختصاصی گروه:</b>\n\n"
            "لطفاً پیام یا مدیای خوش‌آمدگویی جدید را ارسال کنید.\n"
            "متغیرها: <code>USERNAME</code> | <code>XXXX</code> | <code>TIME</code> | <code>DAY</code>"
        )
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(" لغو", callback_data="cancel_current_flow", style="danger")]])
        await query.message.edit_text(prompt_text, reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    elif data.startswith("welcome_delete_confirm:"):
        cid = int(data.replace("welcome_delete_confirm:", ""))
        if not await is_configured_group_manager(context, cid, user_id):
            await query.answer(" دسترسی غیرمجاز!", show_alert=True)
            return
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(" بله، حذف شود", callback_data=f"welcome_delete_do:{cid}", style="danger"),
             InlineKeyboardButton(" لغو", callback_data=f"panel_welcome:{cid}", style="primary")]
        ])
        await query.message.edit_text("<b>آیا از حذف خوش‌آمد اختصاصی اطمینان دارید؟</b>", reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    elif data.startswith("welcome_delete_do:"):
        cid = int(data.replace("welcome_delete_do:", ""))
        if not await is_configured_group_manager(context, cid, user_id):
            await query.answer(" دسترسی غیرمجاز!", show_alert=True)
            return
        g_data = get_group_data(db, cid)
        g_data["welcome"] = {"enabled": True, "custom": False}
        mark_db_dirty()
        save_db()
        await query.answer("پیام اختصاصی حذف شد.", show_alert=True)
        await render_welcome_panel_message(query, cid, db)
        return

    elif data.startswith("panel_foods:"):
        cid = int(data.replace("panel_foods:", ""))
        if not await is_configured_group_manager(context, cid, user_id):
            await query.answer(" دسترسی غیرمجاز!", show_alert=True)
            return
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton(" افزودن غذا", callback_data=f"food_add:{cid}", style="success")],
            [InlineKeyboardButton(" حذف غذا", callback_data=f"food_del:{cid}", style="danger")],
            [InlineKeyboardButton(" لیست غذاها", callback_data=f"panel_list_foods:{cid}", style="primary")],
            [InlineKeyboardButton(" بازگشت", callback_data=f"panel_group_advanced:{cid}", style="primary")]
        ])
        await query.message.edit_text(" <b>مدیریت غذاهای اختصاصی این گروه</b>", reply_markup=keyboard, parse_mode=ParseMode.HTML)
        return

    elif data.startswith("food_add:"):
        cid = int(data.replace("food_add:", ""))
        if not await is_configured_group_manager(context, cid, user_id):
            await query.answer(" دسترسی غیرمجاز!", show_alert=True)
            return
        db["states"]["waiting_add_food"][str(user_id)] = cid
        mark_db_dirty()
        save_db()
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(" لغو", callback_data="cancel_current_flow", style="danger")]])
        await query.message.edit_text(" نام غذایی که می‌خواهید اضافه شود را بنویسید:", reply_markup=kb)
        return

    elif data.startswith("food_del:"):
        cid = int(data.replace("food_del:", ""))
        if not await is_configured_group_manager(context, cid, user_id):
            await query.answer(" دسترسی غیرمجاز!", show_alert=True)
            return
        db["states"]["waiting_del_food"][str(user_id)] = cid
        mark_db_dirty()
        save_db()
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(" لغو", callback_data="cancel_current_flow", style="danger")]])
        await query.message.edit_text(" نام دقیق غذایی که می‌خواهید حذف شود را بنویسید:", reply_markup=kb)
        return

    elif data.startswith("panel_poem_names:"):
        cid = int(data.replace("panel_poem_names:", ""))
        if not await is_configured_group_manager(context, cid, user_id):
            await query.answer(" دسترسی غیرمجاز!", show_alert=True)
            return
        db["states"]["waiting_poem_names"][str(user_id)] = cid
        mark_db_dirty()
        save_db()
        g_data = get_group_data(db, cid)
        current_names = ", ".join(g_data.get("custom_names", [])) or "هیچ اسمی ثبت نشده"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(" دان", callback_data=f"poem_names_done:{cid}", style="success")]])
        await query.message.edit_text(f" <b>اسامی فعلی شعرها در این گروه:</b>\n{current_names}\n\nاسامی جدید را یکی‌یکی بفرستید و در پایان « دان» را بزنید.", reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    elif data.startswith("poem_names_done:"):
        cid = int(data.replace("poem_names_done:", ""))
        if str(user_id) in db["states"].get("waiting_poem_names", {}):
            del db["states"]["waiting_poem_names"][str(user_id)]
            mark_db_dirty()
            save_db(force=True)
        await query.answer("اسامی با موفقیت ذخیره شد.", show_alert=True)
        await render_group_admin_panel_message(query, cid)
        return

    elif data.startswith("panel_add_poem:"):
        cid = int(data.replace("panel_add_poem:", ""))
        if not await is_configured_group_manager(context, cid, user_id):
            await query.answer(" دسترسی غیرمجاز!", show_alert=True)
            return
        db["states"]["waiting_add_poem"][str(user_id)] = cid
        mark_db_dirty()
        save_db()
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(" لغو", callback_data="cancel_current_flow", style="danger")]])
        await query.message.edit_text(" شعر جدید را با <code>{name}</code> یا <code>یوزرنیم</code> بفرستید:", reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    # TIC TAC TOE
    elif data.startswith("xo_"):
        parts = data.split(":")
        act = parts[0]
        game_id = parts[1]
        
        games = db.setdefault("xo_games", {})
        if game_id not in games:
            await query.answer("این بازی به اتمام رسیده است.", show_alert=True)
            return
        
        game = games[game_id]

        if act == "xo_cancel":
            if user_id != game["host_id"]:
                await query.answer("فقط ایجادکننده بازی می‌تواند بازی را لغو کند!", show_alert=True)
                return
            del games[game_id]
            mark_db_dirty()
            save_db()
            await query.message.edit_text('<b>حله! هروقت خواستید من اینجام تا راوی رقابت شما باشم! <tg-emoji emoji-id="5816531766382436821">🛠</tg-emoji></b>', parse_mode=ParseMode.HTML)
            return

        elif act == "xo_leave":
            if user_id == game.get("p1_id"):
                game["p1_id"] = game.get("p2_id")
                game["p1_name"] = game.get("p2_name")
                game["p2_id"] = None
                game["p2_name"] = None
            elif user_id == game.get("p2_id"):
                game["p2_id"] = None
                game["p2_name"] = None
            else:
                await query.answer("شما عضو این میز نیستید!", show_alert=True)
                return

            db["xo_games"][game_id] = game
            mark_db_dirty()
            save_db()

            m1_txt = get_user_mention(game["p1_id"], game["p1_name"]) if game.get("p1_id") else ""
            txt = (
                '<b><tg-emoji emoji-id="5816739230482701944">⚡️</tg-emoji> میبینم به یکم هیجان نیاز دارین! <tg-emoji emoji-id="5818785846823755322">😻</tg-emoji></b>\n\n'
                '<b>آماده بازی دوز هستین بچهااااا؟ <tg-emoji emoji-id="5818984798298841943">⏳</tg-emoji></b>\n\n'
            )
            if m1_txt:
                txt += f'<b>شرکت کنندگان :</b>\n<b>{m1_txt}</b>\n\n<b>- یک نفر دیگه تموممممه! کسی نبودد؟ <tg-emoji emoji-id="5431776939465516694">🔥</tg-emoji></b>\n'
            txt += '<b>با استفاده از دکمه زیر به دوز بپیوندید :</b>'
            
            kb_list = [
                [InlineKeyboardButton("شرکت", callback_data=f"xo_join:{game_id}", style="success", icon_custom_emoji_id="5889002570633977838")]
            ]
            if m1_txt:
                kb_list[0].append(InlineKeyboardButton("انصراف", callback_data=f"xo_leave:{game_id}", style="danger", icon_custom_emoji_id="5888594273862950655"))
            kb_list.append([InlineKeyboardButton("بیخیال", callback_data=f"xo_cancel:{game_id}", style="danger", icon_custom_emoji_id="5848202125078699135")])

            await query.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(kb_list), parse_mode=ParseMode.HTML)
            await query.answer("شما از بازی انصراف دادید.")
            return

        elif act == "xo_join":
            if user_id in [game.get("p1_id"), game.get("p2_id")]:
                await query.answer("شما از قبل در بازی حضور دارید.", show_alert=True)
                return

            if not game.get("p1_id"):
                game["p1_id"] = user_id
                game["p1_name"] = query.from_user.full_name
            elif not game.get("p2_id"):
                game["p2_id"] = user_id
                game["p2_name"] = query.from_user.full_name

            db["xo_games"][game_id] = game
            mark_db_dirty()
            save_db()

            m1 = get_user_mention(game["p1_id"], game["p1_name"]) if game.get("p1_id") else ""
            m2 = get_user_mention(game["p2_id"], game["p2_name"]) if game.get("p2_id") else ""

            if game.get("p1_id") and game.get("p2_id"):
                txt = (
                    '<b><tg-emoji emoji-id="5816739230482701944">⚡️</tg-emoji> میبینم به یکم هیجان نیاز دارین! <tg-emoji emoji-id="5818785846823755322">😻</tg-emoji></b>\n\n'
                    '<b>آماده بازی دوز هستین بچهااااا؟ <tg-emoji emoji-id="5818984798298841943">⏳</tg-emoji></b>\n\n'
                    f'<b>شرکت کنندگان :</b>\n<b>{m1}</b>\n<b>{m2}</b>\n\n'
                    '<b><tg-emoji emoji-id="5474531397571986677">🚬</tg-emoji> اگر آماده‌اید روی دکمه شروع بازی کلیک کنید تا حال کنیممم!</b>'
                )
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("شروع بازی", callback_data=f"xo_start:{game_id}", style="success", icon_custom_emoji_id="5832397371278892338")],
                    [InlineKeyboardButton("انصراف", callback_data=f"xo_leave:{game_id}", style="danger", icon_custom_emoji_id="5888594273862950655")]
                ])
            else:
                txt = (
                    '<b><tg-emoji emoji-id="5816739230482701944">⚡️</tg-emoji> میبینم به یکم هیجان نیاز دارین! <tg-emoji emoji-id="5818785846823755322">😻</tg-emoji></b>\n\n'
                    '<b>آماده بازی دوز هستین بچهااااا؟ <tg-emoji emoji-id="5818984798298841943">⏳</tg-emoji></b>\n\n'
                    f'<b>شرکت کنندگان :</b>\n<b>{m1}</b>\n\n'
                    '<b>- یک نفر دیگه تموممممه! کسی نبودد؟ <tg-emoji emoji-id="5431776939465516694">🔥</tg-emoji></b>\n'
                    '<b>با استفاده از دکمه زیر به دوز بپیوندید :</b>'
                )
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("شرکت", callback_data=f"xo_join:{game_id}", style="success", icon_custom_emoji_id="5889002570633977838"), InlineKeyboardButton("انصراف", callback_data=f"xo_leave:{game_id}", style="danger", icon_custom_emoji_id="5888594273862950655")],
                    [InlineKeyboardButton("بیخیال", callback_data=f"xo_cancel:{game_id}", style="danger", icon_custom_emoji_id="5848202125078699135")]
                ])

            await query.message.edit_text(txt, reply_markup=kb, parse_mode=ParseMode.HTML)
            return

        elif act == "xo_start":
            if user_id != game.get("p1_id"):
                await query.answer("شما توانایی شروع بازی را ندارید.", show_alert=True)
                return

            game["status"] = "playing"
            game["turn"] = game["p1_id"]
            db["xo_games"][game_id] = game
            mark_db_dirty()
            save_db()

            turn_mention = get_user_mention(game['p1_id'], game['p1_name'])
            o_emoji = '<tg-emoji emoji-id="5857031396723269245">⭕️</tg-emoji>'
            txt = (
                '<b>بازی شروع شد! ببینیم برنده میدان کیه! <tg-emoji emoji-id="5818704981179505821">🕹</tg-emoji></b>\n\n'
                f'<b><tg-emoji emoji-id="5816739230482701944">⚡️</tg-emoji> نوبت بازی: {turn_mention} ({o_emoji})</b>'
            )
            kb = build_xo_keyboard(game_id, game["board"])
            await query.message.edit_text(txt, reply_markup=kb, parse_mode=ParseMode.HTML)
            return

        elif act == "xo_surrender":
            if user_id not in [game.get("p1_id"), game.get("p2_id")]:
                await query.answer("شما جزو بازیکنان این بازی نیستید!", show_alert=True)
                return

            surrender_user = query.from_user.full_name
            winner_id = game["p2_id"] if user_id == game["p1_id"] else game["p1_id"]
            winner_name = game["p2_name"] if user_id == game["p1_id"] else game["p1_name"]
            
            del games[game_id]
            mark_db_dirty()
            save_db()

            s_mention = get_user_mention(user_id, surrender_user)
            w_mention = get_user_mention(winner_id, winner_name)

            txt = (
                f'<b>اوووه! بازیکن {s_mention} تسلیم شد! <tg-emoji emoji-id="5816531766382436821">🛠</tg-emoji></b>\n'
                f'<b>- بازی با برتری بازیکن {w_mention} به اتمام رسید. <tg-emoji emoji-id="5866225658983617570">😈</tg-emoji></b>'
            )
            await query.message.edit_text(txt, parse_mode=ParseMode.HTML)
            return

        elif act == "xo_move":
            if game.get("status") != "playing":
                await query.answer("این بازی به اتمام رسیده است.", show_alert=True)
                return

            if user_id not in [game["p1_id"], game["p2_id"]]:
                await query.answer("شما جزو بازیکنان این بازی نیستید!", show_alert=True)
                return

            if user_id != game.get("turn"):
                await query.answer("نوبت شما نیست!", show_alert=True)
                return

            try:
                idx = int(parts[2])
            except (ValueError, TypeError):
                await query.answer("حرکت نامعتبر است.", show_alert=True)
                return
            board = game.get("board", [])
            if idx < 0 or idx >= len(board):
                await query.answer("خانه نامعتبر است.", show_alert=True)
                return
            if board[idx] is not None:
                await query.answer("این خانه قبلاً انتخاب شده است!", show_alert=True)
                return

            symbol = "O" if user_id == game["p1_id"] else "X"
            game["board"][idx] = symbol
            winner_symbol = check_xo_winner(game["board"])

            if winner_symbol:
                # Finished games do not need to remain in the persistent DB.
                del db["xo_games"][game_id]
                mark_db_dirty()
                save_db()

                kb = build_xo_keyboard(game_id, game["board"], is_finished=True)

                if winner_symbol == "draw":
                    res_txt = (
                        '<b>اوووه! میبینم که بازی تموم شده!</b>\n'
                        '<b>- ای بابا حیف شد ، دو طرف خیلی قوی بودن و بازی مساوی شد. <tg-emoji emoji-id="5870693988339553767">🦸‍♀️</tg-emoji></b>'
                    )
                else:
                    winner_id = game["p1_id"] if winner_symbol == "O" else game["p2_id"]
                    winner_name = game["p1_name"] if winner_symbol == "O" else game["p2_name"]
                    w_mention = get_user_mention(winner_id, winner_name)
                    res_txt = (
                        '<b>اوووه! میبینم که بازی تموم شده!</b>\n'
                        f'<b>- بازی با برتری بازیکن {w_mention} به اتمام رسید. <tg-emoji emoji-id="5866225658983617570">😈</tg-emoji></b>'
                    )

                try:
                    await query.message.edit_text(res_txt, reply_markup=kb, parse_mode=ParseMode.HTML)
                except Exception:
                    pass
                return

            else:
                next_turn_id = game["p2_id"] if user_id == game["p1_id"] else game["p1_id"]
                next_turn_name = game["p2_name"] if user_id == game["p1_id"] else game["p1_name"]
                next_symbol = "X" if symbol == "O" else "O"
                
                game["turn"] = next_turn_id
                db["xo_games"][game_id] = game
                mark_db_dirty()
                save_db()

                turn_mention = get_user_mention(next_turn_id, next_turn_name)
                symbol_emoji = '<tg-emoji emoji-id="5857415006022278161">❌</tg-emoji>' if next_symbol == "X" else '<tg-emoji emoji-id="5857031396723269245">⭕️</tg-emoji>'
                
                txt = (
                    '<b>بازی در جریان است... <tg-emoji emoji-id="5818704981179505821">🕹</tg-emoji></b>\n\n'
                    f'<b><tg-emoji emoji-id="5816739230482701944">⚡️</tg-emoji> نوبت بازی: {turn_mention} ({symbol_emoji})</b>'
                )

                kb = build_xo_keyboard(game_id, game["board"])
                try:
                    await query.message.edit_text(txt, reply_markup=kb, parse_mode=ParseMode.HTML)
                except Exception:
                    pass
                return

    # REPORTS
    elif data.startswith("report_"):
        rep_id = data.replace("report_resolve:", "").replace("report_cancel:", "")
        reports = db.get("reports", {})
        
        if rep_id not in reports:
            await query.answer("اطلاعات این گزارش یافت نشد!", show_alert=True)
            return

        rep = reports[rep_id]

        if data.startswith("report_cancel:"):
            if user_id != rep["reporter_id"]:
                await query.answer("فقط فرد گزارش‌دهنده می‌تواند این گزارش را لغو کند!", show_alert=True)
                return
            del reports[rep_id]
            mark_db_dirty()
            save_db()
            txt = '<b><tg-emoji emoji-id="5829923384217050622">❓</tg-emoji> گزارش شما لغو گردید.</b>'
            await query.message.edit_text(txt, parse_mode=ParseMode.HTML)
            return

        elif data.startswith("report_resolve:"):
            if not await is_admin_or_owner(context, query.message.chat.id, user_id):
                await query.answer("فقط مدیران گروه می‌توانند گزارش را بررسی کنند!", show_alert=True)
                return
            del reports[rep_id]
            mark_db_dirty()
            save_db()
            txt = f'<b><tg-emoji emoji-id="{CHECK_CUSTOM_EMOJI_ID}">✅</tg-emoji> گزارش شما توسط مدیران بررسی شد.</b>'
            await query.message.edit_text(txt, parse_mode=ParseMode.HTML)
            return

    # SIGN ACTIONS
    elif data.startswith("sign_action:"):
        rec_id = data.replace("sign_action:", "")
        records = db.get("action_records", {})
        
        if rec_id not in records:
            await query.answer(" اطلاعات این ثبت منقضی شده است!", show_alert=True)
            return

        rec = records[rec_id]
        if user_id == rec["target_id"]:
            await query.answer("داش کصخلی؟ میخوای به اتهام خودت رای بدی؟ ", show_alert=True)
            return

        if user_id == rec["creator_id"]:
            await query.answer(f"جقی تو نمیتونی {rec['action_title']} ای که خودت ثبت کردی رو امضاء کنی بقیه باید امضا کنن ", show_alert=True)
            return

        if any(u["id"] == user_id for u in rec["signers"]):
            await query.answer("شما قبلاً این ثبت را امضا کرده‌اید!", show_alert=True)
            return

        signer_info = {"id": user_id, "name": query.from_user.full_name}
        rec["signers"].append(signer_info)
        db["action_records"][rec_id] = rec
        mark_db_dirty()
        save_db()

        await query.answer("امضای شما با موفقیت ثبت شد! ")

        target_mention = get_user_mention(rec["target_id"], rec["target_name"])
        creator_mention = get_user_mention(rec["creator_id"], rec["creator_name"])
        signers_list = ", ".join([get_user_mention(u["id"], u["name"]) for u in rec["signers"]])

        new_text = (
            f"<b>{html.escape(rec['action_title'])} {target_mention} با موفقیت ثبت شد! <tg-emoji emoji-id=\"5206607081334906820\">✔️</tg-emoji></b>\n"
            f"<b>ثبت کننده {html.escape(rec['action_title'])}: {creator_mention} <tg-emoji emoji-id=\"4956745198521549627\">🌟</tg-emoji></b>\n"
            f"<b><tg-emoji emoji-id=\"5803348359972393936\">⚙️</tg-emoji> در انتظار امضای شاهدان...</b>\n\n"
            f"<b>{rec['funny_text']}</b>\n"
            f"<b>شاهدان {html.escape(rec['action_title'])}: <tg-emoji emoji-id=\"5458382591121964689\">✍️</tg-emoji></b>\n"
            f"{signers_list}"
        )

        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton(f"امضای شاهدان ({len(rec['signers'])})", callback_data=f"sign_action:{rec_id}", style="success", icon_custom_emoji_id="5859527571586161695")],
            [InlineKeyboardButton(f"آمار کل {rec['action_title']} این کاربر", callback_data=f"stat_action:{rec_id}", style="primary", icon_custom_emoji_id="5888937012253171131")]
        ])

        try:
            await query.message.edit_text(new_text, reply_markup=kb, parse_mode=ParseMode.HTML)
        except Exception:
            pass
        return

    elif data.startswith("stat_action:"):
        rec_id = data.replace("stat_action:", "")
        records = db.get("action_records", {})
        if rec_id in records:
            rec = records[rec_id]
            current_count = get_user_stat(db, rec["target_id"], rec["stat_key"])
            alert_msg = f" آمار ثبت‌شده {rec['action_title']} برای {rec['target_name']}: {current_count} بار"
            await query.answer(alert_msg, show_alert=True)
        else:
            await query.answer("اطلاعات یافت نشد!", show_alert=True)
        return

    # COUPLES / SHIPS (VOTING SYSTEM WITH 30 SECONDS TIMEOUT)
    elif data in ["couple_agree", "couple_disagree"]:
        msg_id = str(query.message.message_id)
        couples = db.get("couples", {})
        
        if msg_id not in couples:
            await query.answer(" اطلاعات این شیپ منقضی شده است!", show_alert=True)
            return

        couple_data = couples[msg_id]
        created_at = couple_data.get("created_at", 0)
        
        if datetime.now().timestamp() - created_at > 30:
            await query.answer("⏳ مهلت ۳۰ ثانیه‌ای رای‌گیری به پایان رسیده است!", show_alert=True)
            try:
                await query.message.edit_reply_markup(reply_markup=None)
            except Exception:
                pass
            return

        agrees = couple_data["agrees"]
        disagrees = couple_data["disagrees"]
        user_info = {"id": user_id, "name": query.from_user.full_name}

        if data == "couple_agree":
            disagrees = [u for u in disagrees if u["id"] != user_id]
            if not any(u["id"] == user_id for u in agrees):
                agrees.append(user_info)
                await query.answer("موافقت شما ثبت شد! ")
            else:
                await query.answer("شما قبلاً موافقت کرده‌اید!")
        else:
            agrees = [u for u in agrees if u["id"] != user_id]
            if not any(u["id"] == user_id for u in disagrees):
                disagrees.append(user_info)
                await query.answer("مخالفت شما ثبت شد! ")
            else:
                await query.answer("شما قبلاً مخالفت کرده‌اید!")

        couple_data["agrees"] = agrees
        couple_data["disagrees"] = disagrees
        db["couples"][msg_id] = couple_data
        mark_db_dirty()
        save_db()

        u1, u2 = couple_data["u1"], couple_data["u2"]
        name1 = get_user_mention(u1["id"], u1["name"])
        name2 = get_user_mention(u2["id"], u2["name"])

        agrees_text = ", ".join([get_user_mention(u["id"], u["name"]) for u in agrees]) if agrees else "هیچکس"
        disagrees_text = ", ".join([get_user_mention(u["id"], u["name"]) for u in disagrees]) if disagrees else "هیچکس"

        new_text = (
            f'<b><tg-emoji emoji-id="5830106027701314719">❤️</tg-emoji> دو عدد کفتر عاشقمون این رفقان:</b>\n\n'
            f'<b><tg-emoji emoji-id="5834477789012564986">💕</tg-emoji> | {name1} <tg-emoji emoji-id="6048558196203720407">❤️</tg-emoji> {name2}</b>\n\n'
            f'<b><tg-emoji emoji-id="5819032824623144971">➕</tg-emoji>موافقان: {agrees_text}</b>\n'
            f'<b><tg-emoji emoji-id="5819154526816444042">❌</tg-emoji> مخالفان: {disagrees_text}</b>'
        )

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("موافقم", callback_data="couple_agree", style="success", icon_custom_emoji_id="5411228694935012881"),
                InlineKeyboardButton("افتضاح", callback_data="couple_disagree", style="danger", icon_custom_emoji_id="5411484842489578182")
            ]
        ])

        try:
            await query.message.edit_text(new_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
        except Exception:
            pass
        return

    # OWNER LEF MEDIA SETUP
    elif data == "owner_lef_media":
        if int(user_id) != int(OWNER_ID):
            await query.answer(" دسترسی غیرمجاز! فقط مالک کل.", show_alert=True)
            return
        db["states"]["waiting_lef_media"][str(user_id)] = current_chat_id
        mark_db_dirty()
        save_db()
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(" لغو", callback_data="cancel_current_flow", style="danger")]])
        await query.message.edit_text(
            "<b>تنظیم رسانه لف</b>\n\nهر رسانه‌ای که می‌خواهید پاسخ لف باشد ارسال کنید؛ استیکر، گیف، ویدیو، عکس، صدا، فایل یا متن.\n"
            "رسانه قبلی با مورد جدید جایگزین می‌شود.",
            reply_markup=kb,
            parse_mode=ParseMode.HTML
        )
        return

    # DATABASE BACKUP / RESTORE
    elif data == "panel_backup_restore":
        await open_backup_menu(query, context)
        return

    elif data == "backup_now":
        await backup_now_callback(query, context)
        return

    elif data == "backup_restore_start":
        await backup_restore_start_callback(query, context)
        return

    elif data == "backup_restore_cancel":
        await backup_restore_cancel_callback(query, context)
        return

    elif data == "backup_restore_back":
        await backup_restore_back_callback(query, context)
        return

    # OWNER MAIN PANEL ACTIONS
    elif data == "panel_owner_main":
        if int(user_id) != int(OWNER_ID):
            await query.answer("این بخش مخصوص مالک اصلی است.", show_alert=True)
            return
        await edit_owner_panel_message(query)
        return

    elif data == "panel_admin_logs":
        if int(user_id) != int(OWNER_ID):
            await query.answer("این بخش مخصوص مالک اصلی است.", show_alert=True)
            return
        await render_admin_logs_panel(query, db)
        return

    elif data == "panel_cooldown":
        if int(user_id) != int(OWNER_ID):
            await query.answer("این بخش مخصوص مالک اصلی است.", show_alert=True)
            return
        db["states"]["waiting_cooldown"][str(user_id)] = current_chat_id
        mark_db_dirty()
        save_db()
        kb = InlineKeyboardMarkup([[InlineKeyboardButton(" لغو", callback_data="cancel_current_flow", style="danger")]])
        await query.message.edit_text(f"⏱ زمان فعلی محدودیت: <b>{db.get('cooldown_minutes', 10)} دقیقه</b>\n\nزمان جدید را به دقیقه ارسال کنید:", reply_markup=kb, parse_mode=ParseMode.HTML)
        return

    elif data == "panel_features":
        if int(user_id) != int(OWNER_ID):
            await query.answer("این بخش مخصوص مالک اصلی است.", show_alert=True)
            return
        await render_features_panel_message(query, db)
        return

    elif data.startswith("toggle_"):
        if int(user_id) != int(OWNER_ID):
            await query.answer("این بخش مخصوص مالک اصلی است.", show_alert=True)
            return
        fk = data.replace("toggle_", "")
        if fk in db["features"]:
            db["features"][fk] = not db["features"][fk]
            mark_db_dirty()
            save_db()
        await render_features_panel_message(query, db)
        return

    await query.answer()
