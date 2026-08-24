# GoodiBot entry point
import core
import services, permissions, moderation, management, welcome, comments, jobs, links
import panels, games, whisper, callbacks, callbacks2, handlers, handler2, support, help, fun, filter_handler, auto_responses, backup_restore, start_handler, sensitive, smart_responses

registry = core.bind_all_modules([services, permissions, moderation, management, welcome, comments, jobs, links, panels, games, whisper, callbacks, callbacks2, handlers, handler2, support, help, fun, filter_handler, auto_responses, backup_restore, start_handler, sensitive, smart_responses])
globals().update(registry)
from core import *

async def global_error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Global Error: {context.error}", exc_info=context.error)

def main():
    if not BOT_TOKEN or BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.critical("FATAL: BOT_TOKEN is missing!")
        sys.exit(1)
    load_db()
    threading.Thread(target=run_health_check_server, daemon=True).start()
    app = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    app.add_handler(MessageHandler(filters.ALL, global_security_guard), group=-10)
    app.add_handler(CallbackQueryHandler(global_security_guard), group=-10)
    # Sensitive-content commands and enforcement run before normal group locks,
    # so protected content cannot be bypassed by another active lock.
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.TEXT & (~filters.COMMAND), _handle_sensitive_command), group=-9)
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.ALL, handle_sensitive_panel_message), group=-8)
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.TEXT & (~filters.COMMAND), handle_comment_post_lock_command), group=-6)
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.ALL, enforce_comment_post_lock), group=1)
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.ALL, enforce_sensitive_content), group=-7)
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.ALL, enforce_group_locks), group=-5)
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.UpdateType.EDITED_MESSAGE, enforce_group_locks), group=-5)
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.TEXT & (~filters.COMMAND), handle_welcome_text_command), group=-4)
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.IS_AUTOMATIC_FORWARD, handle_automatic_channel_comments), group=-3)
    # Pending comment messages must be consumed before filters/generic handlers.
    app.add_handler(MessageHandler(filters.ALL & (~filters.COMMAND), handle_pending_comment_message), group=-4)
    app.add_handler(ChatMemberHandler(handle_chat_member_welcome, ChatMemberHandler.CHAT_MEMBER), group=-2)
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_chat_members), group=-2)
    app.add_handler(ChatMemberHandler(track_chats, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(InlineQueryHandler(handle_inline_whisper))
    app.add_handler(CallbackQueryHandler(handle_tag_callback, pattern=r"^tag_panel:"))
    app.add_handler(CallbackQueryHandler(handle_callback_query))
    # Fast private /start handler: registered before the legacy handler so PV /start
    # never depends on the old get_me()-based path. Group /start remains unchanged.
    app.add_handler(CommandHandler("start", command_start_private, filters=filters.ChatType.PRIVATE))
    app.add_handler(CommandHandler("start", command_start))
    app.add_handler(CommandHandler("help", command_help))
    app.add_handler(CommandHandler("panel", command_owner_panel))
    app.add_handler(CommandHandler("cancel", command_cancel))
    app.add_handler(CommandHandler("done", command_done))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.ALL, handle_filter_messages), group=-3)
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.TEXT & (~filters.COMMAND), handle_tag_commands), group=-1)
    # Keep the game message handler in its own group. The tag handler below
    # intentionally uses a broad TEXT filter, and PTB only runs the first
    # matching handler in a handler group; sharing group -1 made «دوز» silently
    # stop before reaching dwoz_message_handler.
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), dwoz_message_handler), group=-2)
    app.add_handler(MessageHandler(filters.ChatType.GROUPS & filters.TEXT & (~filters.COMMAND), handle_smart_response), group=2)
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_goodi_support_message), group=-1)
    app.add_handler(MessageHandler(filters.ALL & (~filters.COMMAND), handle_messages))
    app.add_error_handler(global_error_handler)
    logger.info("Bot is running with full per-group lock & enhanced welcome system...")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
