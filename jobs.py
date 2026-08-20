# GoodiBot modular feature module
from core import *
from backup_restore import periodic_database_backup_job, BACKUP_INTERVAL_SECONDS

async def hourly_goh_khor_job(context: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    if not db["features"].get("goh_khor", True):
        return
        
    target_chat_id = context.job.chat_id
    if not target_chat_id:
        return
        
    chat_str = str(target_chat_id)
    messages_data = db.get("hourly_messages", {}).get(chat_str, {})
    if not messages_data:
        return
        
    top_user_id = max(messages_data, key=lambda k: messages_data[k])
    max_msgs = messages_data[top_user_id]
    
    if max_msgs > 0:
        member_info = db["members"].get(top_user_id, {})
        fullname = member_info.get("fullname", "کاربر")
        mention = get_user_mention(int(top_user_id), fullname)
        increment_user_stat(db, int(top_user_id), "goh_khor_hour")
        
        text = f'<tg-emoji emoji-id="5854843712181378616">🏆</tg-emoji> <b>گوه خور این ساعت</b>\n\n{mention}\n\nتو این یک ساعت خیلی حرف زدی <tg-emoji emoji-id="6033112209612082866">😂</tg-emoji>'
        try:
            await context.bot.send_message(chat_id=target_chat_id, text=text, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error(f"Job send error: {e}")

    db["hourly_messages"][chat_str] = {}
    mark_db_dirty()
    save_db(force=True)

async def periodic_group_reaction_job(context: ContextTypes.DEFAULT_TYPE):
    try:
        target_chat_id = context.job.chat_id
        if not target_chat_id:
            return

        db = load_db()
        if db.get("bot_shutdown", False):
            return
        g_banned, _ = is_group_globally_banned(db, target_chat_id)
        if g_banned:
            return

        g_data = get_group_data(db, target_chat_id)
        if not g_data.get("random_reaction", True):
            return

        user_last_msgs = g_data.get("user_last_messages", {})
        if not user_last_msgs:
            return

        candidate_users = list(user_last_msgs.keys())
        random.shuffle(candidate_users)

        for uid_str in candidate_users:
            uid = int(uid_str)
            u_banned, _ = is_user_globally_banned(db, uid)
            if u_banned:
                continue

            msg_id = user_last_msgs.get(uid_str)
            if not msg_id:
                continue

            try:
                await context.bot.set_message_reaction(
                    chat_id=target_chat_id,
                    message_id=msg_id,
                    reaction=[ReactionTypeCustomEmoji(FIXED_REACTION_CUSTOM_EMOJI_ID)]
                )
                break
            except Exception:
                continue
    except Exception as e:
        logger.error(f"Error in periodic_group_reaction_job: {e}")

async def cleanup_stale_xo_games_job(context: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    games = db.get("xo_games", {})
    if not isinstance(games, dict):
        return
    now = time.time()
    changed = False
    for game_id, game in list(games.items()):
        if not isinstance(game, dict):
            del games[game_id]
            changed = True
            continue
        created = float(game.get("created_at", now))
        if now - created > 2 * 60 * 60:
            del games[game_id]
            changed = True
    if changed:
        mark_db_dirty()
        save_db()

def setup_chat_jobs(job_queue, active_chats: list):
    if not job_queue:
        return
    for chat_id in active_chats:
        job_name_gk = f"goh_khor_{chat_id}"
        if not job_queue.get_jobs_by_name(job_name_gk):
            job_queue.run_repeating(hourly_goh_khor_job, interval=3600, first=3600, chat_id=chat_id, name=job_name_gk)

        job_name_rx = f"reaction_{chat_id}"
        if not job_queue.get_jobs_by_name(job_name_rx):
            job_queue.run_repeating(periodic_group_reaction_job, interval=300, first=300, chat_id=chat_id, name=job_name_rx)

async def post_init(application: Application):
    db = load_db()
    setup_chat_jobs(application.job_queue, db.get("active_chats", []))
    if not application.job_queue.get_jobs_by_name("cleanup_stale_xo_games"):
        application.job_queue.run_repeating(
            cleanup_stale_xo_games_job, interval=900, first=900, name="cleanup_stale_xo_games"
        )
    backup_job_name = "database_backup_15m"
    if not application.job_queue.get_jobs_by_name(backup_job_name):
        application.job_queue.run_repeating(
            periodic_database_backup_job,
            interval=BACKUP_INTERVAL_SECONDS,
            first=BACKUP_INTERVAL_SECONDS,
            name=backup_job_name,
        )
