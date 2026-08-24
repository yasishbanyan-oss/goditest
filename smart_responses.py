from core import *

SMART_RESPONSES = {
    "night": {
        "triggers": {"شب بخیر", "شب خوش", "شو خوش", "شو بخیر", "گود نایت", "good night", "goodnight", "good-night", "شببخیر", "شببخیرر", "شب بخیرر"},
        "emoji": "6028621125519416848",
        "texts": ["شب بخیر ناناص", "شب بخیر کوچولو", "خوب بخوابی", "شب بخیررر", "خواب خوبی داشته باشی جیگر", "خوب لالا کنی", "مسواک یادت نره"],
    },
    "morning": {
        "triggers": {"صبح بخیر", "صبح خوش", "صبحت بخیر", "صبحتون بخیر", "صبح بخیرر", "صبح بخیررر", "گود مورنینگ", "good morning", "goodmorning", "good-morning"},
        "emoji": "6026240790219460632",
        "texts": ["صبح توام بخیر", "خوب خوابیدی؟", "روز خوبی داشته باشی", "صبح بخیررر"],
    },
    "day": {
        "triggers": {"روز بخیر", "روز خوش", "روزت بخیر", "روز شما بخیر", "روزتون بخیر", "روز بخیرر"},
        "emoji": "5260373844178262063",
        "texts": ["روز توام بخیر", "خسته نباشی"],
    },
    "bye": {
        "triggers": {"خدافظ", "خدافظی", "خداحافظ", "خدانگهدار", "خدا نگهدار", "خدانگهدار", "بای", "بای بای", "bye", "goodbye", "good bye"},
        "emoji": "5197573115843981021",
        "texts": ["خدانگهداررر", "باااای کوچولو", "خداحافظ جیگر"],
    },
    "hello": {
        "triggers": {"سلام", "سلامم", "دلام", "دلامم", "دلاام", "سلام سلام", "درود", "درود بر شما", "هلو", "hello", "hi", "hey", "های"},
        "emoji": "5282759776365730523",
        "texts": ["سلاااامم", "دلامم", "سلامم چخبرااا", "سلااامم کجا بودیی دلتنگت بودم"],
    },
}

async def handle_smart_response(update, context):
    msg = update.message
    chat = update.effective_chat
    if not msg or not chat or chat.type not in ("group", "supergroup"):
        return
    if not msg.text or getattr(msg.from_user, "is_bot", False):
        return
    normalized = normalize_text(msg.text.strip()).lower()
    # Exact/single-message matching only: "سلام خوبی" must never trigger "سلام".
    if not normalized:
        return
    for data in SMART_RESPONSES.values():
        if normalized in data["triggers"]:
            response = random.choice(data["texts"])
            emoji_id = data["emoji"]
            await msg.reply_text(f'<b><tg-emoji emoji-id="{emoji_id}">❤️</tg-emoji> {html.escape(response)}</b>', parse_mode=ParseMode.HTML)
            raise ApplicationHandlerStop()
