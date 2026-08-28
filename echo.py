# GoodiBot - echo/repeat command
from core import *
import core as _core

ECHO_COMMANDS = (
    "گودی تکرار کن",
    "گودی بگو",
    "تکرار کن",
    "تکرار",
    "بگوو",
    "بگو",
    "اکو",
)


def _html_text_with_custom_emoji(message) -> str:
    """Return message text/caption as safe HTML while preserving custom emoji entities."""
    raw = message.text or message.caption or ""
    if not raw:
        return ""
    entities = getattr(message, "entities", None) if message.text is not None else getattr(message, "caption_entities", None)
    custom = [e for e in (entities or []) if getattr(e, "type", None) == MessageEntityType.CUSTOM_EMOJI]
    if not custom:
        return html.escape(raw)

    # PTB's Message.parse_entity handles Telegram's UTF-16 entity offsets.
    spans = []
    for entity in custom:
        try:
            start_text = message.parse_entity(entity)
            emoji_id = getattr(entity, "custom_emoji_id", None)
            if emoji_id:
                spans.append((entity, start_text, emoji_id))
        except Exception:
            continue

    if not spans:
        return html.escape(raw)

    # Convert UTF-16 offsets to Python indices safely.
    def py_index(utf16_offset: int) -> int:
        encoded = raw.encode("utf-16-le")
        prefix = encoded[: int(utf16_offset) * 2]
        return len(prefix.decode("utf-16-le", errors="ignore"))

    pieces = []
    cursor = 0
    for entity, entity_text, emoji_id in sorted(spans, key=lambda x: int(x[0].offset)):
        start = py_index(entity.offset)
        end = py_index(entity.offset + entity.length)
        if start < cursor:
            continue
        pieces.append(html.escape(raw[cursor:start]))
        pieces.append(f'<tg-emoji emoji-id="{html.escape(str(emoji_id))}">{html.escape(entity_text)}</tg-emoji>')
        cursor = end
    pieces.append(html.escape(raw[cursor:]))
    return "".join(pieces)


def _match_echo_command(raw: str):
    normalized = normalize_text(raw or "").strip()
    lowered = normalized.lower()
    for command in ECHO_COMMANDS:
        c = command.lower()
        if lowered == c:
            return command, ""
        if lowered.startswith(c + " "):
            # Use the normalized command length only for command matching; the
            # actual payload is sliced from normalized text so repeated spaces
            # and punctuation do not accidentally become part of the command.
            return command, normalized[len(command):].strip()
    return None, None


async def handle_echo_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    message = update.message
    chat = update.effective_chat
    user = update.effective_user
    if not message or not chat or chat.type not in ("group", "supergroup") or not user or user.is_bot:
        return False

    command, payload = _match_echo_command(message.text or "")
    if command is None:
        return False

    # All four Goodi roles are allowed: exempt, special, admin and owner.
    db = load_db()
    g_data = get_group_data(db, chat.id)
    management = g_data.get("management", {}) or {}
    uid = int(user.id)
    allowed = (
        uid == int(OWNER_ID)
        or uid in {int(x) for x in management.get("owners", []) or [] if str(x).lstrip("-").isdigit()}
        or uid in {int(x) for x in management.get("admins", []) or [] if str(x).lstrip("-").isdigit()}
        or uid in {int(x) for x in management.get("special", []) or [] if str(x).lstrip("-").isdigit()}
        or uid in {int(x) for x in management.get("exempt", []) or [] if str(x).lstrip("-").isdigit()}
    )
    if not allowed:
        # A live Telegram owner/admin may use the command even if Goodi's local
        # management snapshot is stale. Special/exempt are Goodi-only roles.
        try:
            member = await cached_chat_member(context, chat.id, uid)
            allowed = member.status in (ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR)
        except Exception:
            allowed = False

    if not allowed:
        return True

    if await enforce_manager_feature(context, chat.id, uid, "echo", message=message):
        return True

    if not payload:
        # A bare command is not an echo operation.
        return True

    rendered = _html_text_with_custom_emoji(message)
    # The normalized payload is only used to detect the command. For the actual
    # echo, preserve the user's original text/entities so normal emoji survive
    # the bot's global premium-emoji sanitizer as requested by this feature.
    raw_full = message.text or message.caption or ""
    command_end = None
    lowered_raw = raw_full.lower()
    for candidate in ECHO_COMMANDS:
        prefix = candidate.lower() + " "
        if lowered_raw.startswith(prefix):
            command_end = len(candidate)
            break
    if command_end is not None:
        # Rebuild from the original message, preserving custom emoji entities.
        # We still need to remove the command prefix itself.
        # Custom emoji offsets are based on the whole message, so use a helper
        # on the payload by creating a lightweight clone is not safe; instead
        # derive the original payload start and escape it while retaining custom
        # emoji via entity offsets.
        payload_start = command_end + 1
        # Most echo messages are plain text; for custom emojis after the command
        # we can parse entity positions directly and shift them into the payload.
        payload_raw = raw_full[payload_start:]
        entities = getattr(message, "entities", None) or []
        custom_after = [e for e in entities if getattr(e, "type", None) == MessageEntityType.CUSTOM_EMOJI and int(e.offset) >= len(raw_full[:payload_start].encode("utf-16-le")) // 2]
        if custom_after:
            pieces = []
            cursor = 0
            base_utf16 = len(raw_full[:payload_start].encode("utf-16-le")) // 2
            def local_py_index(off):
                enc = payload_raw.encode("utf-16-le")
                return len(enc[:int(off) * 2].decode("utf-16-le", errors="ignore"))
            for e in sorted(custom_after, key=lambda x: int(x.offset)):
                start = local_py_index(int(e.offset) - base_utf16)
                end = local_py_index(int(e.offset + e.length) - base_utf16)
                if start < cursor:
                    continue
                pieces.append(html.escape(payload_raw[cursor:start]))
                try:
                    ent_text = message.parse_entity(e)
                except Exception:
                    ent_text = ""
                pieces.append(f'<tg-emoji emoji-id="{html.escape(str(e.custom_emoji_id))}">{html.escape(ent_text)}</tg-emoji>')
                cursor = end
            pieces.append(html.escape(payload_raw[cursor:]))
            rendered = "".join(pieces)
        else:
            rendered = html.escape(payload_raw)

    try:
        await message.delete()
    except Exception:
        pass

    # Bypass the bot-wide emoji sanitizer only for echo. This command explicitly
    # promises to repeat both normal and premium/custom emoji exactly as sent.
    # Do not reply through the deleted Message object. Telegram may reject a
    # reply whose source message has already been deleted, which previously
    # caused the command message to disappear without the repeated text being
    # sent. Send the result directly to the same chat instead.
    await context.bot.send_message(
        chat_id=chat.id,
        text=rendered,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )
    return True
