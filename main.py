import logging
import asyncio
import time
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from typing import Callable, Dict, Any, Awaitable

from aiogram import Bot, Dispatcher, types, F, Router, BaseMiddleware
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from database import get_user, create_user, get_user_credits, update_credits, DB_CONFIG
from gate import on_command, off_command
from fb import setup_feedback_handler, feedback_cmd, router as fb_router
from stats import stats_command
from tools.binn import binn_command
from cmds import cmds_command, router as cmds_router
from broad import broad_command, router as broad_router
from ban import ban_command, unban_command, BanMiddleware, router as ban_router
from status import vps_command, router as status_router

from sub import (
    sub_command, rc_command, suball_command, g_code_command,
    claim_command, info_command, rsub_command, buy_command, adcr_command
)
from proxy import proxy_command, checkproxy_command, clearproxy_command

from gates.hc import hc_command

from mass_gates.msh import (
    router as msh_router,
    MshStopCallback,
    MshResultCallback,
    handle_stop_callback as msh_stop_handler,
    handle_result_callback as msh_result_handler,
)

from mass_gates.sitechk import (
    sitechk_command, addsite_command, siteall_command,
    removeall_command, dedupe_command, proxyinfo_command, resetproxy_command
)

import payments as pay_sys

BOT_TOKEN = "7688322079:AAEfUKmBVPP03Zp1LqUevySCJJFk_7744gA"
WEBHOOK_URL = "https://cleaners-beam-ethical-drew.trycloudflare.com/8979001589:AAFiBvepjdZbHPNYI-yXSXVdwZ9EAfd6bDQ"
WEBHOST = "0.0.0.0"
WEBPORT = 8080

START_IMAGE_URL = "https://i.pinimg.com/1200x/35/e4/76/35e476aedea94952ec9c7cc22dc10c61.jpg"
LOG_CHANNEL_ID = -1002501525166
BOT_LINK = "https://t.me/pokchod"

REQUIRED_CHANNEL_ID = -1003902779119
REQUIRED_GROUP_ID = -5471534941
CHANNEL_LINK = "https://t.me/pokchod"
GROUP_LINK = "https://t.me/jigu5656"

JOIN_TEXT = (
    "⚠️ <b>𝗔𝗰𝗰𝗲𝘀𝘀 𝗥𝗲𝘀𝘁𝗿𝗶𝗰𝘁𝗲𝗱!</b>\n\n"
    "𝗧𝗼 𝘂𝘀𝗲 𝘁𝗵𝗶𝘀 𝗯𝗼𝘁 𝘆𝗼𝘂 𝗺𝘂𝘀𝘁 𝗷𝗼𝗶𝗻 𝗼𝘂𝗿 𝗰𝗵𝗮𝗻𝗻𝗲𝗹 𝗮𝗻𝗱 𝗴𝗿𝗼𝘂𝗽 𝗳𝗶𝗿𝘀𝘁.\n\n"
    "𝗖𝗹𝗶𝗰𝗸 𝗩𝗲𝗿𝗶𝗳𝘆 𝗮𝗳𝘁𝗲𝗿 𝗷𝗼𝗶𝗻𝗶𝗻𝗴 𝗯𝗼𝘁𝗵."
)

PRICING_TEXT = (
    f'<b>𝗔𝗰𝗰𝗲𝘀𝘀 ➛ 𝗖𝗢𝗥𝗘</b> <tg-emoji emoji-id="5379869575338812919">💎</tg-emoji>\n'
    f'<b>𝗦𝗽𝗮𝗻 ➛</b> [𝟳 𝗗𝗔𝗬𝗦]\n'
    f'<b>𝗖𝗿𝗲𝗱𝗶𝘁𝘀 ➛</b> 𝟭𝟯,𝟬𝟬𝟬\n'
    f'<b>𝗣𝗿𝗶𝗰𝗲 ➛</b> 𝟭𝟬$\n'
    f'━━━━━━━━━━━━━━━━\n'
    f'<b>𝗔𝗰𝗰𝗲𝘀𝘀 ➛ 𝗘𝗟𝗜𝗧𝗘</b> <tg-emoji emoji-id="5836898273666798437">💎</tg-emoji>\n'
    f'<b>𝗦𝗽𝗮𝗻 ➛</b> [𝟭𝟱 𝗗𝗔𝗬𝗦]\n'
    f'<b>𝗖𝗿𝗲𝗱𝗶𝘁𝘀 ➛</b> 𝟮𝟯,𝟬𝟬𝟬\n'
    f'<b>𝗣𝗿𝗶𝗰𝗲 ➛</b> 𝟭𝟱$\n'
    f'━━━━━━━━━━━━━━━━\n'
    f'<b>𝗔𝗰𝗰𝗲𝘀𝘀 ➛ 𝗥𝗢𝗢𝗧</b> <tg-emoji emoji-id="4956420911310832630">💎</tg-emoji>\n'
    f'<b>𝗦𝗽𝗮𝗻 ➛</b> [𝟯𝟬 𝗗𝗔𝗬𝗦]\n'
    f'<b>𝗖𝗿𝗲𝗱𝗶𝘁𝘀 ➛</b> 𝟱𝟯,𝟬𝟬𝟬\n'
    f'<b>𝗣𝗿𝗶𝗰𝗲 ➛</b> 𝟯𝟬$'
)

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

dp.include_router(msh_router)
dp.include_router(cmds_router)
dp.include_router(fb_router)
dp.include_router(ban_router)
dp.include_router(broad_router)
dp.include_router(status_router)

router = Router()
dp.include_router(router)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MEMBERSHIP CACHE — avoids Telegram API calls on every message
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Cache structure: {user_id: (is_member: bool, expires_at: float)}
_MEMBERSHIP_CACHE: Dict[int, tuple] = {}
_MEMBERSHIP_CACHE_TTL = 60  # seconds — positive results cached 60s, negatives 15s
_MEMBERSHIP_LOCK: Dict[int, asyncio.Lock] = {}
_MEMBERSHIP_LOCK_MAP_LOCK = asyncio.Lock()

_VALID_STATUSES = {"member", "administrator", "creator"}


async def _get_user_lock(user_id: int) -> asyncio.Lock:
    async with _MEMBERSHIP_LOCK_MAP_LOCK:
        if user_id not in _MEMBERSHIP_LOCK:
            _MEMBERSHIP_LOCK[user_id] = asyncio.Lock()
        return _MEMBERSHIP_LOCK[user_id]


async def check_membership(user_id: int, bot_instance: Bot) -> bool:
    now = time.monotonic()

    # Fast path: serve from cache if still valid
    cached = _MEMBERSHIP_CACHE.get(user_id)
    if cached is not None:
        is_member, expires_at = cached
        if now < expires_at:
            return is_member

    # Deduplicate concurrent checks for the same user via per-user lock
    lock = await _get_user_lock(user_id)
    async with lock:
        # Re-check cache inside the lock — another coroutine may have filled it
        cached = _MEMBERSHIP_CACHE.get(user_id)
        if cached is not None:
            is_member, expires_at = cached
            if now < expires_at:
                return is_member

        try:
            ch, gr = await asyncio.gather(
                bot_instance.get_chat_member(REQUIRED_CHANNEL_ID, user_id),
                bot_instance.get_chat_member(REQUIRED_GROUP_ID, user_id),
            )
            is_member = ch.status in _VALID_STATUSES and gr.status in _VALID_STATUSES
        except Exception as e:
            logging.warning(f"Membership check failed for {user_id}: {e}")
            # On error, assume member to avoid blocking legitimate users temporarily
            is_member = True

        # Cache positives for 60s, negatives for 15s (so denied users don't wait long)
        ttl = _MEMBERSHIP_CACHE_TTL if is_member else 15
        _MEMBERSHIP_CACHE[user_id] = (is_member, now + ttl)
        return is_member


def invalidate_membership_cache(user_id: int):
    """Call this after a user verifies membership so the cache is cleared immediately."""
    _MEMBERSHIP_CACHE.pop(user_id, None)


_JOIN_KB = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="𝗝𝗼𝗶𝗻 𝗖𝗵𝗮𝗻𝗻𝗲𝗹", url="https://t.me/pokchod")],
    [InlineKeyboardButton(text="𝗝𝗼𝗶𝗻 𝗚𝗿𝗼𝘂𝗽", url="https://t.me/jigu5656")],
    [InlineKeyboardButton(text="𝗩𝗲𝗿𝗶𝗳𝘆", callback_data="verify_membership")]
])

ADMIN_IDS = {6221445357}


class MembershipMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: types.Message, data: Dict[str, Any]):
        user = event.from_user
        if not user:
            return await handler(event, data)
        if user.id in ADMIN_IDS:
            return await handler(event, data)
        if not await check_membership(user.id, data["bot"]):
            await event.reply(text=JOIN_TEXT, parse_mode="HTML", reply_markup=_JOIN_KB, disable_web_page_preview=True)
            return
        return await handler(event, data)


dp.message.middleware(MembershipMiddleware())
dp.message.middleware(BanMiddleware())


@router.callback_query(F.data == "verify_membership")
async def verify_membership_callback(callback: types.CallbackQuery):
    # Invalidate cache so the live check runs fresh
    invalidate_membership_cache(callback.from_user.id)
    joined = await check_membership(callback.from_user.id, callback.bot)
    if joined:
        await asyncio.gather(
            callback.answer("✅ 𝗩𝗲𝗿𝗶𝗳𝗶𝗲𝗱! 𝗬𝗼𝘂 𝗻𝗼𝘄 𝗵𝗮𝘃𝗲 𝗳𝘂𝗹𝗹 𝗮𝗰𝗰𝗲𝘀𝘀.", show_alert=True),
            callback.message.delete(),
        )
    else:
        await callback.answer(
            "❌ 𝗬𝗼𝘂 𝗵𝗮𝘃𝗲𝗻'𝘁 𝗷𝗼𝗶𝗻𝗲𝗱 𝘆𝗲𝘁!\n\n𝗣𝗹𝗲𝗮𝘀𝗲 𝗷𝗼𝗶𝗻 𝗯𝗼𝘁𝗵 𝘁𝗵𝗲 𝗰𝗵𝗮𝗻𝗻𝗲𝗹 𝗮𝗻𝗱 𝗴𝗿𝗼𝘂𝗽 𝗳𝗶𝗿𝘀𝘁, 𝘁𝗵𝗲𝗻 𝗰𝗹𝗶𝗰𝗸 𝗩𝗲𝗿𝗶𝗳𝘆.",
            show_alert=True
        )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DB HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _db_conn():
    return psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)

def _ensure_user_sync(user_id, username):
    try:
        if not get_user(user_id):
            create_user(user_id, username or "unknown")
        cr = get_user_credits(user_id)
        if not cr:
            update_credits(user_id, 150)
    except Exception as e:
        logging.error(f"ensure_user {user_id}: {e}")

async def ensure_user_and_credits(user_id, username="unknown"):
    await asyncio.to_thread(_ensure_user_sync, user_id, username)

def _status_sync(user_id):
    conn = _db_conn()
    cur = conn.cursor()
    plan, credits_str, joined_str = "Trial", "0", "N/A"
    try:
        cur.execute("SELECT is_premium, premium_expiry, joined_at FROM users WHERE user_id = %s", (user_id,))
        row = cur.fetchone()
        if row:
            if row['joined_at']:
                joined_str = row['joined_at'].strftime('%Y-%m-%d')
            if row['is_premium'] == 1 and row['premium_expiry'] and datetime.now() < row['premium_expiry']:
                cur.execute("SELECT plan FROM receipts WHERE user_id = %s ORDER BY purchased_on DESC LIMIT 1", (user_id,))
                r = cur.fetchone()
                plan = r['plan'] if r else "Premium"
        cr = get_user_credits(user_id)
        credits_str = str(cr if cr is not None else 0)
    except Exception as e:
        logging.error(f"status {user_id}: {e}")
        cr = get_user_credits(user_id)
        credits_str = str(cr if cr is not None else 0)
    finally:
        conn.close()
    return credits_str, plan, joined_str

async def _get_caption(user) -> str:
    credits_str, access_str, joined_str = await asyncio.to_thread(_status_sync, user.id)
    ul = f'<a href="tg://user?id={user.id}">{user.first_name}</a>'
    dl = '<a href="https://t.me/leiamarketcc">メ𝗔𝗟𝗟𝗨𝗦</a>'
    return (
        f"𝗨𝘀𝗲𝗿 ➛ {ul}\n"
        f"𝗨𝘀𝗲𝗿 𝗜𝗗 ➛ <code>{user.id}</code>\n"
        f"𝗔𝗰𝗰𝗲𝘀𝘀 ➛ <b>{access_str}</b>\n"
        f"𝗖𝗿𝗲𝗱𝗶𝘁𝘀 ➛ <b>{credits_str}</b>\n"
        f"𝗝𝗼𝗶𝗻𝗲𝗱 ➛ <b>{joined_str}</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"𝗗𝗲𝘃 ➛ {dl}"
    )

def _loading_caption(user) -> str:
    ul = f'<a href="tg://user?id={user.id}">{user.first_name}</a>'
    dl = '<a href="https://t.me/leiamarketcc">メ𝗔𝗟𝗟𝗨𝗦</a>'
    return (
        f"𝗨𝘀𝗲𝗿 ➛ {ul}\n"
        f"𝗨𝘀𝗲𝗿 𝗜𝗗 ➛ <code>{user.id}</code>\n"
        f"𝗔𝗰𝗰𝗲𝘀𝘀 ➛ <b>Loading…</b>\n"
        f"𝗖𝗿𝗲𝗱𝗶𝘁𝘀 ➛ <b>Loading…</b>\n"
        f"𝗝𝗼𝗶𝗻𝗲𝗱 ➛ <b>Loading…</b>\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"𝗗𝗲𝘃 ➛ {dl}"
    )

def mask_receipt_id(receipt_id):
    parts = receipt_id.split('-')
    if len(parts) == 3:
        m = parts[1]
        if len(m) >= 2:
            return f"{parts[0]}-{m[:2]}XX{m[4:]}-{parts[2]}"
    return receipt_id

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# KEYBOARDS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

_MAIN_KB = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="𝗖𝗵𝗲𝗰𝗸𝗲𝗿", callback_data="menu_gates"),
     InlineKeyboardButton(text="𝗕𝘂𝘆 𝗡𝗼𝘄", callback_data="menu_pricing")],
    [InlineKeyboardButton(text="𝗨𝗽𝗱𝗮𝘁𝗲𝘀", url="https://t.me/+CtZrEQiodwkxM2Zl"),
     InlineKeyboardButton(text="𝗚𝗿𝗼𝘂𝗽", url="https://t.me/allus_xd_hit")],
    [InlineKeyboardButton(text="𝗦𝘂𝗽𝗽𝗼𝗿𝘁", url="https://t.me/leiamarketcc")]
])

def _back(target):
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="« 𝗕𝗮𝗰𝗸", callback_data=target)]])

_KB_BACK_MAIN   = _back("back_main")
_KB_BACK_GATES  = _back("menu_gates")
_KB_BACK_MASS   = _back("menu_mass_in_gates")
_KB_BACK_CHARGE = _back("menu_charge")

_KB_PRICING = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="💎 𝗣𝗮𝘆 𝗩𝗶𝗮", callback_data="menu_payment_methods")],
    [InlineKeyboardButton(text="« 𝗕𝗮𝗰𝗸", callback_data="back_main")]
])

_KB_GATES = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="𝗖𝗵𝗮𝗿𝗴𝗲", callback_data="menu_charge")],
    [InlineKeyboardButton(text="𝗠𝗮𝘀𝘀", callback_data="menu_mass_in_gates")],
    [InlineKeyboardButton(text="« 𝗕𝗮𝗰𝗸", callback_data="back_main")]
])

_KB_MASS = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="𝗦𝗵𝗼𝗽𝗶𝗳𝘆 𝟬-𝟮𝟬$", callback_data="info_msh_gate")],
    [InlineKeyboardButton(text="« 𝗕𝗮𝗰𝗸", callback_data="menu_gates")]
])

# ✅ ADD THIS - KB_CHARGE was missing
_KB_CHARGE = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="𝗦𝗵𝗼𝗽𝗶𝗳𝘆", callback_data="info_charge_shopify")],
    [InlineKeyboardButton(text="« 𝗕𝗮𝗰𝗸", callback_data="menu_gates")]
])

_SEP = "━━━━━━━━━━━━━━━━"
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# STATIC MENU LOOKUP — O(1) dict, text+keyboard pre-built
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_PAYMENT_SELECT_TEXT = "<b>✨ 𝗦𝗲𝗹𝗲𝗰𝘁 𝗬𝗼𝘂𝗿 𝗣𝗹𝗮𝗻 ✨\n\nChoose a plan to proceed with\nsecure crypto payment</b>"

STATIC_MENU_MAP: dict = {
    "menu_pricing": (PRICING_TEXT, _KB_PRICING),
    "menu_gates": (
        "<b>𝗚𝗮𝘁𝗲𝘀 𝗦𝘁𝗮𝘁𝘂𝘀:</b>\n"
        "𝗠𝗮𝘀𝘀 𝗚𝗮𝘁𝗲𝘀 ➛ <b>1</b>\n"
        "𝗖𝗵𝗮𝗿𝗴𝗲 𝗚𝗮𝘁𝗲𝘀 ➛ <b>1</b>\n"
        f"{_SEP}\n<b><i>Select a Gate Category</i></b>",
        _KB_GATES
    ),
    "menu_mass_in_gates": ("<b><i>Select a Mass Gate</i></b>", _KB_MASS),
    "menu_charge": ("<b><i>Select Charge Method</i></b>", _KB_CHARGE),
    "menu_payment_methods": (_PAYMENT_SELECT_TEXT, None),
    "info_msh_gate": (
        f"{_SEP}\n<b><i>Gate ➛ Shopify 0-20$</i></b>\n<b><i>Command ➛ /msh</i></b>\n"
        f"<b><i>Limit ➛ 5000</i></b>\n<b><i>Type ➛ Mass Checker</i></b>\n<b><i>Stop ➛ 🛑 Button</i></b>\n"
        f"{_SEP}",
        _KB_BACK_MASS   # ✅ Add this line
    ),  # ✅ Closing parenthesis
    "info_charge_shopify": (
        f"{_SEP}\n<b><i>Gate ➛ Shopify 5$</i></b>\n<b><i>Command ➛ /hc</i></b>\n"
        f"<b><i>Gate Health ➛ 100%</i></b>\n{_SEP}\n<b><i>Gate ➛ Shopify 1$</i></b>\n"
        f"{_SEP}",
        _KB_BACK_CHARGE   # ✅ Add this line
    ),  # ✅ Closing parenthesis
}
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# FAST INLINE EDIT HELPER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
async def _edit(msg: types.Message, text: str, kb: InlineKeyboardMarkup):
    try:
        if msg.caption is not None:
            await msg.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
        else:
            await msg.edit_text(text=text, reply_markup=kb, parse_mode="HTML")
    except TypeError:
        pass
    except Exception as e:
        if "Message is not modified" not in str(e):
            logging.warning(f"_edit: {e}")

async def _safe_answer(cb: types.CallbackQuery, text: str = "", **kw):
    try:
        await cb.answer(text, **kw)
    except Exception:
        pass

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# /start
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@router.message(Command("start"))
async def start(message: types.Message):
    user = message.from_user
    asyncio.create_task(ensure_user_and_credits(user.id, user.username))

    if message.text and len(message.text.split()) > 1 and message.text.split()[1] == "buy":
        await buy_command(message)
        return

    quick = _loading_caption(user)
    caption_task = asyncio.create_task(_get_caption(user))

    sent = await message.reply_photo(photo=START_IMAGE_URL, caption=quick, reply_markup=_MAIN_KB)

    try:
        full = await caption_task
        await sent.edit_caption(caption=full, reply_markup=_MAIN_KB)
    except Exception:
        pass

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# DOT COMMANDS (.chk, .st, etc.)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DOT_COMMAND_MAP = {
    "hc": hc_command, "sub": sub_command, "rc": rc_command,
    "suball": suball_command,"g_code": g_code_command, 
    "claim": claim_command, "info": info_command,
    "rsub": rsub_command, "buy": buy_command, "adcr": adcr_command,
    "on": on_command, "off": off_command, "stats": stats_command,
    "proxy": proxy_command, "checkproxy": checkproxy_command,
    "clearproxy": clearproxy_command, "sitechk": sitechk_command,
    "addsite": addsite_command, "siteall": siteall_command,
    "removeall": removeall_command, "dedupe": dedupe_command,
    "proxyinfo": proxyinfo_command, "resetproxy": resetproxy_command,
    "cmds": cmds_command, "fb": feedback_cmd, "broad": broad_command,
    "ban": ban_command, "unban": unban_command, "vps": vps_command,
}

@router.message(F.text.regexp(r'^\.\w+'))
async def dot_command_handler(message: types.Message):
    cmd = message.text.strip().split()[0][1:].lower()
    h = DOT_COMMAND_MAP.get(cmd)
    if h:
        await h(message)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CALLBACK HANDLER — MAXIMUM SPEED
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_MASS_PREFIXES = ("mshs_", "mshr_", "msts_", "mstr_", "stco_", "fb_", "cmds_")

@router.callback_query()
async def button_handler(callback: types.CallbackQuery):
    data = callback.data or ""

    # These are owned by other routers — drop immediately, no answer needed
    if data.startswith(_MASS_PREFIXES):
        return

    # Guard: if the message is inaccessible (too old / deleted), bail out gracefully
    msg = callback.message
    if not isinstance(msg, types.Message):
        await _safe_answer(callback, "❌ Message expired. Please use /start again.", show_alert=True)
        return

    user_id = callback.from_user.id

    # ── STATIC MENU (most common path) ─────────────────────────────────────
    static = STATIC_MENU_MAP.get(data)
    if static is not None:
        text, kb = static
        if kb is None:  # menu_payment_methods — kb computed at runtime
            kb = pay_sys.get_plan_selection_keyboard()
        asyncio.create_task(_safe_answer(callback))   # answer instantly — no waiting
        asyncio.create_task(_edit(msg, text, kb))     # edit in background
        return

    # ── BACK TO MAIN ───────────────────────────────────────────────────────
    if data == "back_main":
        user = callback.from_user
        quick = _loading_caption(user)
        caption_task = asyncio.create_task(_get_caption(user))
        asyncio.create_task(_safe_answer(callback))   # answer instantly — no waiting
        try:
            if msg.caption is not None:
                await msg.edit_caption(caption=quick, reply_markup=_MAIN_KB, parse_mode="HTML")
            else:
                await msg.answer_photo(photo=START_IMAGE_URL, caption=quick, reply_markup=_MAIN_KB, parse_mode="HTML")
        except TypeError:
            pass
        except Exception as e:
            if "Message is not modified" not in str(e):
                logging.warning(f"back_main load: {e}")
        try:
            full = await caption_task
            await msg.edit_caption(caption=full, reply_markup=_MAIN_KB, parse_mode="HTML")
        except TypeError:
            pass
        except Exception:
            pass
        return

    # ── BUY PLANS (inline group context) ───────────────────────────────────
    if data == "show_buy_plans":
        buy_url_kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="💎 𝗧𝗮𝗽 𝗛𝗲𝗿𝗲 𝘁𝗼 𝗕𝘂𝘆", url=f"{BOT_LINK}?start=buy")
        ]])
        asyncio.create_task(_safe_answer(callback))
        asyncio.create_task(msg.edit_reply_markup(reply_markup=buy_url_kb))
        return

    # ── PAYMENT PLAN SELECTION ──────────────────────────────────────────────
    if data.startswith("pay_plan_"):
        plan = data[9:]
        if plan not in pay_sys.PLANS:
            asyncio.create_task(_safe_answer(callback))
            asyncio.create_task(msg.answer("Invalid plan!"))
            return
        pi = pay_sys.PLANS[plan]
        pay_sys.set_user_session(user_id, plan)
        text = (
            f"<b>{pi['display']} 𝗣𝗹𝗮𝗻</b>\n"
            f"<b>𝗣𝗿𝗶𝗰𝗲 ➛</b> ${pi['price']}\n"
            f"<b>𝗗𝘂𝗿𝗮𝘁𝗶𝗼𝗻 ➛</b> {pi['days']} Days\n"
            f"<b>𝗖𝗿𝗲𝗱𝗶𝘁𝘀 ➛</b> {pi['credits']:,}\n"
            f"<b>𝗦𝗲𝗹𝗲𝗰𝘁 𝗣𝗮𝘆𝗺𝗲𝗻𝘁 𝗠𝗲𝘁𝗵𝗼𝗱:</b>"
        )
        asyncio.create_task(_safe_answer(callback))
        asyncio.create_task(_edit(msg, text, pay_sys.get_network_selection_keyboard(user_id)))
        return

    # ── BACK TO PLAN LIST ───────────────────────────────────────────────────
    if data.startswith("pay_back_plans_"):
        try:
            owner_id = int(data[15:])
        except ValueError:
            await _safe_answer(callback, "❌ Error", show_alert=True)
            return
        if user_id != owner_id:
            await _safe_answer(callback, "❌ No permission", show_alert=True)
            return
        asyncio.create_task(_safe_answer(callback))
        asyncio.create_task(_edit(msg, _PAYMENT_SELECT_TEXT, pay_sys.get_plan_selection_keyboard()))
        return

    # ── DIRECT PAYMENT INITIATION ───────────────────────────────────────────
    if data.startswith("pay_direct_"):
        net_key = data[11:]
        session = pay_sys.get_user_session(user_id)
        if not session or not session.get("plan"):
            asyncio.create_task(_safe_answer(callback))
            asyncio.create_task(msg.answer("Session expired!"))
            return
        plan = session["plan"]
        net_info = pay_sys.DIRECT_NETWORKS.get(net_key)
        if not net_info:
            asyncio.create_task(_safe_answer(callback))
            asyncio.create_task(msg.answer("Invalid network!"))
            return
        pay_sys.cancel_user_active_payment(user_id)
        payment_data = await asyncio.to_thread(
            pay_sys.create_payment, user_id, plan, net_info["currency"], net_info["network"]
        )
        if not payment_data:
            await asyncio.gather(
                _safe_answer(callback),
                _edit(msg, "❌ <b>Payment Failed</b>\n\nPlease try again later.",
                      _back("menu_pricing")),
            )
            return
        track_id = payment_data["track_id"]
        pay_sys.register_payment(track_id, user_id, plan)
        caption = pay_sys.format_payment_caption(payment_data, plan)
        kb = pay_sys.get_paid_button_keyboard(track_id, user_id)
        await _safe_answer(callback)
        try:
            sent_msg = await msg.answer(text=caption, reply_markup=kb, disable_web_page_preview=True)
        except Exception as e:
            logging.error(f"pay_direct send: {e}")
            return
        try:
            await msg.delete()
        except Exception:
            pass
        if sent_msg:
            pay_sys.active_payments[track_id].update({
                "chat_id": sent_msg.chat.id,
                "message_id": sent_msg.message_id,
                "original_text": caption,
            })
        return

    # ── PAYMENT CHECK (I Paid button) ───────────────────────────────────────
    if data.startswith("pay_check_"):
        track_id = data[10:]
        payment = pay_sys.active_payments.get(track_id)
        if not payment or payment.get("user_id") != user_id:
            await _safe_answer(callback, "❌ No permission", show_alert=True)
            return
        bot_i = pay_sys.get_bot()
        if not bot_i:
            await _safe_answer(callback, "❌ Bot error", show_alert=True)
            return
        try:
            status = await asyncio.to_thread(pay_sys.check_payment_status, track_id)
            logging.info(f"pay_check {track_id}: {status}")
            if status and status.lower() == "paid":
                await asyncio.to_thread(pay_sys.activate_plan, user_id, payment["plan"])
                receipt = pay_sys.get_receipt_for_user(user_id, payment["plan"])
                pi = pay_sys.PLANS.get(payment["plan"], {})
                dn = callback.from_user.first_name or callback.from_user.username or "User"
                ul = f'<a href="tg://user?id={user_id}">{dn}</a>'
                mid = mask_receipt_id(receipt['receipt_id']) if receipt else "N/A"
                log_kb = InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="𝗕𝘂𝘆 𝗡𝗼𝘄", url=f"{BOT_LINK}?start=buy")
                ]])
                try:
                    await bot_i.send_message(
                        chat_id=LOG_CHANNEL_ID, parse_mode="HTML", reply_markup=log_kb,
                        text=(f"<b>NEW PLAN PURCHASED 🛒</b>\n<b>User ➛</b> {ul}\n"
                              f"<b>Access ➛</b> <b>{pi.get('display','')}</b>\n"
                              f"<b>Amount ➛</b> <b>{pi.get('price',0)} USD</b>\n"
                              f"<b>Receipt ID ➛</b> <code>{mid}</code>")
                    )
                except Exception as le:
                    logging.error(f"log channel: {le}")
                success = (
                    f"✅ <b>𝗧𝗿𝗮𝗻𝘀𝗮𝗰𝘁𝗶𝗼𝗻 𝗦𝘂𝗰𝗰𝗲𝘀𝘀!</b>\n\n"
                    f" <b>𝗣𝗹𝗮𝗻 ➛</b> {pi.get('display','')}\n"
                    f" <b>𝗗𝘂𝗿𝗮𝘁𝗶𝗼𝗻 ➛</b> {pi.get('days',0)} Days\n"
                    f" <b>𝗖𝗿𝗲𝗱𝗶𝘁𝘀 𝗔𝗱𝗱𝗲𝗱 ➛</b> +{pi.get('credits',0):,}\n\n"
                    f" <b>𝗬𝗼𝘂𝗿 𝗣𝗹𝗮𝗻 𝗵𝗮𝘀 𝗯𝗲𝗲𝗻 𝗮𝗰𝘁𝗶𝘃𝗮𝘁𝗲𝗱!</b>"
                )
                dm_kb = InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="𝗦𝘂𝗽𝗽𝗼𝗿𝘁", url="https://t.me/leiamarketcc")
                ]])
                if receipt:
                    dm = (f"𝐂𝐨𝐧𝐠𝐫𝐚𝐭𝐮𝐥𝐚𝐭𝐢𝐨𝐧𝐬! 🎉 𝐘𝐨𝐮𝐫 𝐚𝐜𝐜𝐞𝐬𝐬 𝐡𝐚𝐬 𝐛𝐞𝐞𝐧 𝐚𝐜𝐭𝐢𝐯𝐚𝐭𝐞𝐝.\n"
                          f"𝗨𝘀𝗲𝗿 ➛ {ul}\n𝗔𝗰𝗰𝗲𝘀𝘀 ➛ <b>{receipt['plan_name']}</b>\n"
                          f"𝗗𝘂𝗿𝗮𝘁𝗶𝗼𝗻 ➛ {receipt['days']} Days\n"
                          f"𝗖𝗿𝗲𝗱𝗶𝘁𝘀 𝗔𝗱𝗱𝗲𝗱 ➛ +{receipt['credits']:,}\n"
                          f"𝗥𝗲𝗰𝗲𝗶𝗽𝘁 𝗜𝗗 ➛ <code>{receipt['receipt_id']}</code>\n"
                          f"𝗣𝗹𝗲𝗮𝘀𝗲 𝘀𝗮𝘃𝗲 𝘁𝗵𝗶𝘀 𝗿𝗲𝗰𝗲𝗶𝗽𝘁 𝗜𝗗.")
                else:
                    dm = (f"𝐂𝐨𝐧𝐠𝐫𝐚𝐭𝐮𝐥𝐚𝐭𝐢𝐨𝐧𝐬! 🎉 𝐘𝐨𝐮𝐫 𝐚𝐜𝐜𝐞𝐬𝐬 𝐡𝐚𝐬 𝐛𝐞𝐞𝐧 𝐚𝐜𝐭𝐢𝐯𝐚𝐭𝐞𝐝.\n"
                          f"𝗔𝗰𝗰𝗲𝘀𝘀 ➛ <b>{pi.get('display','')}</b>\n"
                          f"𝗗𝘂𝗿𝗮𝘁𝗶𝗼𝗻 ➛ {pi.get('days',0)} Days\n"
                          f"𝗖𝗿𝗲𝗱𝗶𝘁𝘀 𝗔𝗱𝗱𝗲𝗱 ➛ +{pi.get('credits',0):,}\n"
                          f"𝗬𝗼𝘂𝗿 𝗽𝗹𝗮𝗻 𝗵𝗮𝘀 𝗯𝗲𝗲𝗻 𝗮𝗰𝘁𝗶𝘃𝗮𝘁𝗲𝗱!")
                await asyncio.gather(
                    _safe_answer(callback, "✅ Payment Confirmed! Plan activated.", show_alert=True),
                    bot_i.edit_message_text(chat_id=payment["chat_id"],
                                            message_id=payment["message_id"], text=success),
                    bot_i.send_message(chat_id=user_id, text=dm, parse_mode="HTML", reply_markup=dm_kb),
                )
                pay_sys._cleanup_payment(track_id, user_id)

            elif status and status.lower() == "expired":
                await asyncio.gather(
                    _safe_answer(callback, "⏰ Payment Expired!", show_alert=True),
                    bot_i.edit_message_text(
                        chat_id=payment["chat_id"], message_id=payment["message_id"],
                        text="<b>Payment Expired</b>\n\nThe payment window has closed.\nPlease start a new payment."
                    ),
                )
                pay_sys._cleanup_payment(track_id, user_id)

            else:
                await _safe_answer(callback, "⏳ Payment not detected yet.\nEnsure exact amount is sent.", show_alert=True)
                cur_text = payment.get("original_text", "")
                if "Payment not detected yet" not in cur_text:
                    pending = (f"{cur_text}\n\n⏳ <b>Payment not detected yet.</b>\n"
                               f"<i>Ensure exact amount is sent. Click 'Paid' again to recheck.</i>")
                    try:
                        await bot_i.edit_message_text(
                            chat_id=payment["chat_id"], message_id=payment["message_id"],
                            text=pending, reply_markup=pay_sys.get_paid_button_keyboard(track_id, user_id)
                        )
                        payment["original_text"] = pending
                    except Exception as e:
                        if "not modified" not in str(e):
                            logging.error(f"pending edit: {e}")
        except Exception as e:
            logging.error(f"pay_check error: {e}")
            await _safe_answer(callback, "⚠️ Network error. Try again.", show_alert=True)
        return

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# EXPLICIT CALLBACK REGISTRATIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
dp.callback_query.register(msh_stop_handler, MshStopCallback.filter())
dp.callback_query.register(msh_result_handler, MshResultCallback.filter())

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COMMAND REGISTRATIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
for _cmd, _fn in [
    ("hc", hc_command), ("sub", sub_command), ("rc", rc_command),
    ("suball", suball_command), ("g_code", g_code_command), ("claim", claim_command),
    ("info", info_command), ("rsub", rsub_command), ("buy", buy_command),
    ("adcr", adcr_command), ("on", on_command), ("off", off_command),
    ("sitechk", sitechk_command), ("addsite", addsite_command),
    ("siteall", siteall_command), ("removeall", removeall_command), ("dedupe", dedupe_command),
    ("proxyinfo", proxyinfo_command), ("resetproxy", resetproxy_command),
    ("stats", stats_command), ("proxy", proxy_command), ("checkproxy", checkproxy_command),
    ("clearproxy", clearproxy_command), ("bin", binn_command), ("binn", binn_command),
]:
    dp.message.register(_fn, Command(_cmd))

setup_feedback_handler(dp)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# WEBHOOK SERVER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
from aiohttp import web

async def on_startup(bot: Bot):
    await bot.set_webhook(WEBHOOK_URL)
    pay_sys.set_bot(bot)
    logging.info(f"Webhook set: {WEBHOOK_URL}")

async def on_shutdown(bot: Bot):
    await bot.delete_webhook()
    logging.info("Webhook deleted")

async def webhook_handler(request):
    try:
        data = await request.json()
        update = types.Update.model_validate(data)
    except Exception as e:
        logging.error(f"webhook parse: {e}")
        return web.Response(status=200)
    try:
        await dp.feed_update(bot, update)
    except TypeError:
        pass
    except Exception as e:
        logging.error(f"webhook: {e}")
    return web.Response(status=200)

def main():
    app = web.Application()
    app.on_startup.append(lambda _: on_startup(bot))
    app.on_shutdown.append(lambda _: on_shutdown(bot))
    app.router.add_post(f"/{BOT_TOKEN}", webhook_handler)
    logging.info("Bot starting via Webhook…")
    web.run_app(app, host=WEBHOST, port=WEBPORT)

if __name__ == "__main__":
    import asyncio
    asyncio.run(dp.start_polling(bot))
