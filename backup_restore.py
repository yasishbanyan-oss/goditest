# GoodiBot database backup / restore system.
# Keeps the full JSON database portable and sends an automatic backup to the
# bot owner every 15 minutes.
from core import *
from telegram import InputFile

import io
import zipfile
from datetime import datetime

BACKUP_STATE_KEY = "waiting_backup_restore"
BACKUP_INTERVAL_SECONDS = 15 * 60

BACKUP_EMOJI = {
    "backup": "5945116932536540095",
    "restore": "5836866392124563486",
    "close": "5819154526816444042",
    "back": BACK_CUSTOM_EMOJI_ID,
    "ok": CHECK_CUSTOM_EMOJI_ID,
    "error": CROSS_CUSTOM_EMOJI_ID,
}


def _be(name: str, fallback: str) -> str:
    return f'<tg-emoji emoji-id="{BACKUP_EMOJI.get(name, "")}">{fallback}</tg-emoji>'


def _backup_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "بکاپ گرفتن",
                callback_data="backup_now",
                style="success",
                icon_custom_emoji_id=BACKUP_EMOJI["backup"],
            ),
            InlineKeyboardButton(
                "ریستور دیتابیس",
                callback_data="backup_restore_start",
                style="primary",
                icon_custom_emoji_id=BACKUP_EMOJI["restore"],
            ),
        ],
        [
            InlineKeyboardButton(
                "بازگشت",
                callback_data="backup_restore_back",
                style="danger",
                icon_custom_emoji_id=BACKUP_EMOJI["back"],
            )
        ],
    ])


def backup_menu_text() -> str:
    return (
        f'<b>{_be("backup", "💾")} مدیریت بکاپ و ریستور دیتابیس</b>\n\n'
        '<b>از این بخش می‌توانید از کل دیتابیس ربات نسخه پشتیبان بگیرید یا یک نسخه پشتیبان معتبر را بازیابی کنید.</b>\n\n'
        f'<b>{_be("backup", "🔄")} ربات به‌صورت خودکار هر ۱۵ دقیقه یک نسخه پشتیبان کامل را برای مالک کل ارسال می‌کند.</b>'
    )


def _build_backup_bytes(db: dict) -> tuple[io.BytesIO, str]:
    # ZIP keeps the automatic backups compact as the database grows. The
    # restore system accepts both this ZIP format and plain JSON files.
    payload = json.dumps(db, ensure_ascii=False, indent=2).encode("utf-8")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"goodi_database_backup_{stamp}.zip"
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        zf.writestr("db.json", payload)
    stream.name = filename
    stream.seek(0)
    return stream, filename


def _extract_restore_data(raw: bytes, filename: str) -> dict:
    name = (filename or "").lower()
    if name.endswith(".zip") or raw[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(raw), "r") as zf:
            candidates = [n for n in zf.namelist() if n.lower().endswith(".json") and not n.endswith("/")]
            if not candidates:
                raise ValueError("در فایل ZIP هیچ فایل JSON معتبری پیدا نشد.")
            # Prefer db.json, then a file whose name contains database/backup.
            candidates.sort(key=lambda n: (0 if n.lower().endswith("db.json") else 1, 0 if "backup" in n.lower() or "database" in n.lower() else 1, len(n)))
            raw = zf.read(candidates[0])

    data = json.loads(raw.decode("utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("ساختار دیتابیس معتبر نیست.")
    if not isinstance(data.get("groups", {}), dict):
        raise ValueError("بخش گروه‌های دیتابیس معتبر نیست.")
    if not isinstance(data.get("members", {}), dict):
        raise ValueError("بخش کاربران دیتابیس معتبر نیست.")
    if "version" not in data:
        raise ValueError("نسخه دیتابیس در فایل پیدا نشد.")
    return migrate_db_if_needed(data)


async def send_database_backup(bot, chat_id: int, *, automatic: bool = False):
    db = load_db()
    stream, filename = _build_backup_bytes(db)
    size_kb = max(1, len(stream.getbuffer()) // 1024)
    caption = (
        f'<b>{_be("backup", "💾")} نسخه پشتیبان دیتابیس گودی</b>\n\n'
        f'<b>زمان: {datetime.now().strftime("%Y/%m/%d - %H:%M:%S")}</b>\n'
        f'<b>حجم: {size_kb} KB</b>\n'
        f'<b>وضعیت: {"بکاپ خودکار ۱۵ دقیقه‌ای" if automatic else "بکاپ دستی"}</b>'
    )
    await bot.send_document(
        chat_id=chat_id,
        document=InputFile(stream, filename=filename),
        caption=caption,
        parse_mode=ParseMode.HTML,
    )


async def open_backup_menu(query, context):
    if int(query.from_user.id) != int(OWNER_ID):
        await query.answer("این بخش فقط مخصوص مالک کل ربات است.", show_alert=True)
        return
    await query.message.edit_text(
        backup_menu_text(),
        reply_markup=_backup_menu_keyboard(),
        parse_mode=ParseMode.HTML,
    )
    await query.answer()


async def backup_now_callback(query, context):
    if int(query.from_user.id) != int(OWNER_ID):
        await query.answer("این بخش فقط مخصوص مالک کل ربات است.", show_alert=True)
        return
    try:
        await send_database_backup(context.bot, query.from_user.id, automatic=False)
        await query.answer("نسخه پشتیبان ارسال شد.")
    except Exception:
        logger.exception("Manual database backup failed")
        await query.answer("ارسال بکاپ با خطا مواجه شد.", show_alert=True)


async def backup_restore_start_callback(query, context):
    if int(query.from_user.id) != int(OWNER_ID):
        await query.answer("این بخش فقط مخصوص مالک کل ربات است.", show_alert=True)
        return
    db = load_db()
    db.setdefault("states", {}).setdefault(BACKUP_STATE_KEY, {})[str(query.from_user.id)] = {
        "step": "restore",
        "created_at": datetime.now().timestamp(),
    }
    mark_db_dirty()
    save_db(force=True)
    kb = InlineKeyboardMarkup([[
        InlineKeyboardButton(
            "لغو",
            callback_data="backup_restore_cancel",
            style="danger",
            icon_custom_emoji_id=BACKUP_EMOJI["close"],
        )
    ]])
    await query.message.edit_text(
        f'<b>{_be("restore", "♻️")} فایل بکاپ دیتابیس را ارسال کنید.</b>\n\n'
        '<b>فرمت‌های قابل قبول: JSON یا ZIP شامل فایل JSON دیتابیس.</b>\n'
        '<b>پس از بررسی صحت فایل، دیتابیس فعلی جایگزین نسخه ارسال‌شده می‌شود.</b>',
        reply_markup=kb,
        parse_mode=ParseMode.HTML,
    )
    await query.answer()


async def backup_restore_cancel_callback(query, context):
    if int(query.from_user.id) != int(OWNER_ID):
        await query.answer("این بخش فقط مخصوص مالک کل ربات است.", show_alert=True)
        return
    db = load_db()
    db.setdefault("states", {}).setdefault(BACKUP_STATE_KEY, {}).pop(str(query.from_user.id), None)
    mark_db_dirty()
    save_db(force=True)
    await query.message.edit_text(backup_menu_text(), reply_markup=_backup_menu_keyboard(), parse_mode=ParseMode.HTML)
    await query.answer()


async def backup_restore_back_callback(query, context):
    if int(query.from_user.id) != int(OWNER_ID):
        await query.answer("این بخش فقط مخصوص مالک کل ربات است.", show_alert=True)
        return
    await edit_owner_panel_message(query)
    await query.answer()


async def handle_backup_restore_private_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not update.message or not update.effective_chat or update.effective_chat.type != "private":
        return False
    user = update.effective_user
    if not user or int(user.id) != int(OWNER_ID):
        return False

    db = load_db()
    state = db.setdefault("states", {}).setdefault(BACKUP_STATE_KEY, {}).get(str(user.id))
    if not state:
        return False

    # A real bot command must always win over the restore flow.
    if update.message.text and update.message.text.startswith("/"):
        db["states"][BACKUP_STATE_KEY].pop(str(user.id), None)
        mark_db_dirty()
        save_db(force=True)
        return False

    document = update.message.document
    if not document:
        await update.message.reply_text(
            f'<b>{_be("error", "❌")} لطفاً فایل بکاپ JSON یا ZIP را ارسال کنید.</b>',
            parse_mode=ParseMode.HTML,
        )
        return True

    filename = document.file_name or "backup"
    if not filename.lower().endswith((".json", ".zip")):
        await update.message.reply_text(
            f'<b>{_be("error", "❌")} فقط فایل JSON یا ZIP قابل ریستور است.</b>',
            parse_mode=ParseMode.HTML,
        )
        return True

    try:
        tg_file = await document.get_file()
        buffer = io.BytesIO()
        await tg_file.download_to_memory(buffer)
        data = _extract_restore_data(buffer.getvalue(), filename)

        # Save the validated data atomically. The current DB remains untouched
        # until validation succeeds.
        global _DB_CACHE, _DB_DIRTY
        _DB_CACHE = data
        _DB_DIRTY = True
        save_db(force=True)

        db = load_db()
        try:
            from jobs import setup_chat_jobs
            setup_chat_jobs(context.application.job_queue, db.get("active_chats", []))
        except Exception:
            logger.exception("Failed to re-register group jobs after database restore")
        db.setdefault("states", {}).setdefault(BACKUP_STATE_KEY, {}).pop(str(user.id), None)
        mark_db_dirty()
        save_db(force=True)

        await update.message.reply_text(
            f'<b>{_be("ok", "✅")} ریستور با موفقیت انجام شد.</b>\n'
            '<b>دیتابیس جدید با موفقیت بارگذاری و ذخیره شد.</b>',
            parse_mode=ParseMode.HTML,
        )
        return True
    except Exception as exc:
        logger.exception("Database restore failed")
        await update.message.reply_text(
            f'<b>{_be("error", "❌")} ریستور انجام نشد.</b>\n'
            f'<b>فایل بکاپ معتبر نیست یا ساختار آن قابل شناسایی نیست.</b>',
            parse_mode=ParseMode.HTML,
        )
        return True


async def periodic_database_backup_job(context: ContextTypes.DEFAULT_TYPE):
    try:
        if not BOT_TOKEN or int(OWNER_ID) <= 0:
            return
        await send_database_backup(context.bot, int(OWNER_ID), automatic=True)
        logger.info("Automatic 15-minute database backup sent to owner.")
    except Exception:
        logger.exception("Automatic database backup failed")
