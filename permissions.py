# GoodiBot modular feature module
from core import *

_MEMBER_CACHE = {}
_MEMBER_CACHE_TTL = 15

async def cached_chat_member(context, chat_id: int, user_id: int):
    key = (int(chat_id), int(user_id))
    now = time.time()
    item = _MEMBER_CACHE.get(key)
    if item and now - item[0] < _MEMBER_CACHE_TTL:
        return item[1]
    member = await context.bot.get_chat_member(chat_id, user_id)
    _MEMBER_CACHE[key] = (now, member)
    return member

def get_group_management(db: dict, chat_id: int) -> dict:
    g = get_group_data(db, chat_id)
    return g.setdefault("management", {"configured": False, "primary_owner_id": None, "owners": [], "admins": [], "special": [], "exempt": []})

def _role_ids(g_data: dict, role: str) -> set[int]:
    out = set()
    for uid in (g_data.get("management", {}) or {}).get(role, []) or []:
        try: out.add(int(uid))
        except Exception: pass
    return out

def is_group_owner_id(g_data: dict, user_id: int) -> bool:
    return int(user_id) in _role_ids(g_data, "owners")

def is_primary_group_owner_id(g_data: dict, user_id: int) -> bool:
    try: return int((g_data.get("management", {}) or {}).get("primary_owner_id")) == int(user_id)
    except Exception: return False

async def is_actual_group_owner(context, chat_id: int, user_id: int) -> bool:
    """True only when Telegram currently reports this user as the owner of this exact group."""
    try:
        member = await cached_chat_member(context, chat_id, int(user_id))
        return member.status == ChatMemberStatus.OWNER
    except Exception:
        return False

async def is_primary_or_bot_owner_of_group(context, chat_id: int, g_data: dict, user_id: int) -> bool:
    """Allow primary group owner, plus the bot owner only when he is the real owner of this group."""
    if is_primary_group_owner_id(g_data, user_id):
        return True
    return int(user_id) == int(OWNER_ID) and await is_actual_group_owner(context, chat_id, user_id)

def is_group_manager_id(g_data: dict, user_id: int) -> bool:
    return int(user_id) in (_role_ids(g_data, "owners") | _role_ids(g_data, "admins"))

async def is_configured_group_manager(context, chat_id: int, user_id: int) -> bool:
    if int(user_id) == int(OWNER_ID): return True
    g = get_group_data(load_db(), chat_id)
    if (g.get("management", {}) or {}).get("configured"):
        return is_group_manager_id(g, user_id)
    return await is_admin_or_owner(context, chat_id, user_id)

async def is_configured_group_owner(context, chat_id: int, user_id: int) -> bool:
    if int(user_id) == int(OWNER_ID): return True
    g = get_group_data(load_db(), chat_id)
    if (g.get("management", {}) or {}).get("configured"):
        return is_group_owner_id(g, user_id)
    try:
        return (await cached_chat_member(context, chat_id, user_id)).status == ChatMemberStatus.OWNER
    except Exception: return False

def _stored_user(db: dict, uid: int, name: str = "کاربر", username: str = "") -> dict:
    old = db.get("members", {}).get(str(uid), {}) or {}
    return {"id": int(uid), "fullname": old.get("fullname") or name, "username": old.get("username") or username}

async def is_admin_or_owner(context: ContextTypes.DEFAULT_TYPE, chat_id: int, user_id: int) -> bool:
    if int(user_id) == int(OWNER_ID):
        return True
    try:
        member = await cached_chat_member(context, chat_id, user_id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
    except Exception:
        return False
