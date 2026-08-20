# GoodiBot modular feature module
from core import *

async def handle_goodi_support_quick_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not update.message:
        return False
    candidate = (update.message.text or update.message.caption or "").strip().lower()
    candidate = re.sub(r"^[!/]\s*", "", candidate)
    if candidate not in {x.lstrip("/").lower() for x in GOODI_SUPPORT_TRIGGERS}:
        return False
    await update.message.reply_text(
        GOODI_SUPPORT_REPLY,
        parse_mode=ParseMode.HTML,
        link_preview_options=LinkPreviewOptions(is_disabled=True),
    )
    return True

async def handle_goodi_support_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await handle_goodi_support_quick_reply(update, context):
        raise ApplicationHandlerStop
