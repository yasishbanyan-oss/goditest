# GoodiBot modular feature module
from core import *

def check_xo_winner(board):
    lines = [
        [0, 1, 2], [3, 4, 5], [6, 7, 8],
        [0, 3, 6], [1, 4, 7], [2, 5, 8],
        [0, 4, 8], [2, 4, 6]
    ]
    for a, b, c in lines:
        if board[a] and board[a] == board[b] == board[c]:
            return board[a]
    if None not in board:
        return "draw"
    return None

def build_xo_keyboard(game_id: str, board: list, is_finished: bool = False) -> InlineKeyboardMarkup:
    buttons = []
    for i in range(0, 9, 3):
        row = []
        for j in range(i, i + 3):
            cell = board[j]
            if cell == "O":
                btn = InlineKeyboardButton("O", callback_data=f"xo_move:{game_id}:{j}", icon_custom_emoji_id="5857031396723269245")
            elif cell == "X":
                btn = InlineKeyboardButton("X", callback_data=f"xo_move:{game_id}:{j}", icon_custom_emoji_id="5857415006022278161")
            else:
                btn = InlineKeyboardButton(" ", callback_data=f"xo_move:{game_id}:{j}", icon_custom_emoji_id="5911319564301376749")
            row.append(btn)
        buttons.append(row)
    
    if not is_finished:
        buttons.append([InlineKeyboardButton("تسلیم", callback_data=f"xo_surrender:{game_id}", style="danger", icon_custom_emoji_id="5839270298205035832")])
    return InlineKeyboardMarkup(buttons)

async def start_dwoz_game(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat:
        return
    if update.effective_chat.type not in ["group", "supergroup"]:
        return
    try:
        db = load_db()
        chat_id = update.effective_chat.id
        user_id = update.effective_user.id

        game_id = f"{chat_id}_{update.message.message_id}"
        games = db.setdefault("xo_games", {})
        
        games[game_id] = {
            "host_id": user_id,
            "p1_id": None,
            "p1_name": None,
            "p2_id": None,
            "p2_name": None,
            "board": [None] * 9,
            "turn": None,
            "status": "waiting",
            "created_at": time.time()
        }
        mark_db_dirty()
        save_db()

        txt = (
            '<b><tg-emoji emoji-id="5816739230482701944">⚡️</tg-emoji> میبینم به یکم هیجان نیاز دارین! <tg-emoji emoji-id="5818785846823755322">😻</tg-emoji></b>\n\n'
            '<b>آماده بازی دوز هستین بچهااااا؟ <tg-emoji emoji-id="5818984798298841943">⏳</tg-emoji></b>\n\n'
            '<b>با استفاده از دکمه زیر به دوز بپیوندید :</b>'
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("شرکت", callback_data=f"xo_join:{game_id}", style="success", icon_custom_emoji_id="5889002570633977838")],
            [InlineKeyboardButton("بیخیال", callback_data=f"xo_cancel:{game_id}", style="danger", icon_custom_emoji_id="5848202125078699135")]
        ])
        await update.message.reply_text(txt, reply_markup=kb, parse_mode=ParseMode.HTML)
    except Exception:
        logger.exception("Error in start_dwoz_game:")

async def dwoz_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    if not update.effective_chat or update.effective_chat.type not in ["group", "supergroup"]:
        return

    raw_text = update.message.text.strip().lower()
    clean = raw_text.replace("\u200c", " ")
    clean = re.sub(r"[؟?\.,!؛\-_]", "", clean).strip()

    valid_triggers = ["دوز", "گودی دوز", "گودی دوز بزار", "گودی دوز بذار", "بازی دوز"]
    if clean in valid_triggers or raw_text in valid_triggers:
        await start_dwoz_game(update, context)
        raise ApplicationHandlerStop()
