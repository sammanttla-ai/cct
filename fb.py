import asyncio
import logging
import uuid
from typing import Any, Dict, List, Optional

from aiogram import types, Router, F, BaseMiddleware
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    InputMediaPhoto, InputMediaVideo, InputMediaAnimation, InputMediaDocument,
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONFIGURATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ADMIN_ID         = 6221445357
FEEDBACK_CHANNEL = -1002501525166   # channel where approved hits are posted

router = Router()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MEDIA GROUP COLLECTOR MIDDLEWARE
# Runs on every message — stores album messages before handlers fire
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# {media_group_id: [Message, ...]}
_MEDIA_GROUPS: Dict[str, List[types.Message]] = {}

class MediaGroupCollectorMiddleware(BaseMiddleware):
    async def __call__(self, handler, event: types.Message, data: Dict[str, Any]):
        gid = getattr(event, "media_group_id", None)
        if gid:
            bucket = _MEDIA_GROUPS.setdefault(gid, [])
            # Deduplicate by message_id
            existing_ids = {m.message_id for m in bucket}
            if event.message_id not in existing_ids:
                bucket.append(event)
        # Always let the handler chain continue
        return await handler(event, data)

router.message.middleware(MediaGroupCollectorMiddleware())

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# IN-MEMORY PENDING STORE
# key  : short UUID hex
# value: {
#   "messages":     [Message, ...]   — the replied-to messages (1 or full album)
#   "media_type":   "photo"|"video"|"animation"|"document"|"text"
#   "hit_text":     str
#   "user":         User
# }
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
_PENDING: dict = {}

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MEDIA DETECTION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _detect_media(msg: types.Message) -> str:
    """Returns media type string for a single message."""
    if msg.photo:       return "photo"
    if msg.video:       return "video"
    if msg.animation:   return "animation"
    if msg.document:    return "document"
    return "text"

def _get_file_id(msg: types.Message) -> Optional[str]:
    """Returns the primary file_id from a message, or None."""
    if msg.photo:       return msg.photo[-1].file_id
    if msg.video:       return msg.video.file_id
    if msg.animation:   return msg.animation.file_id
    if msg.document:    return msg.document.file_id
    return None

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def _admin_info_text(user: types.User, media_type: str, count: int) -> str:
    username_part = f"@{user.username}" if user.username else "N/A"
    user_link     = f'<a href="tg://user?id={user.id}">{user.first_name}</a>'
    media_label   = f"{count}× {media_type}" if count > 1 else media_type
    return (
        "━━━━━━━━━━━━━━━━\n"
        f"<b><i>User      ➛ {user_link}</i></b>\n"
        f"<b><i>UID       ➛ {user.id}</i></b>\n"
        f"<b><i>Username  ➛ {username_part}</i></b>\n"
        f"<b><i>Media     ➛ {media_label}</i></b>\n"
        "━━━━━━━━━━━━━━━━"
    )

def _approve_keyboard(pid: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="Approve", callback_data=f"fb_approve_{pid}"),
        InlineKeyboardButton(text="Reject", callback_data=f"fb_reject_{pid}"),
    ]])

def _channel_caption(user: types.User, hit_text: str) -> str:
    user_link = f'<a href="tg://user?id={user.id}">{user.first_name}</a>'
    note_part = hit_text if hit_text else "—"
    return (
        f"<b>𝗙𝗘𝗘𝗗𝗕𝗔𝗖𝗞</b> __PREMIUM_<tg-emoji emoji-id='5042050649248760772'>💎</tg-emoji>__\n"
        f"<b>𝗨𝗦𝗘𝗥 ➛</b> {user_link}\n"
        f"<b>𝗨𝗦𝗘𝗥 𝗜𝗗 ➛</b> {user.id}\n"
        f"━━━━━━\n"
        f" {note_part} "
    )

def _channel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="𝗕𝘂𝘆 𝗡𝗼𝘄", url="https://t.me/cc_checkershopibot?start=buy")
    ]])

def _build_input_media(msg: types.Message, caption: str = "", parse_mode: str = "HTML") -> Optional[Any]:
    """Build an InputMedia* object for send_media_group."""
    fid = _get_file_id(msg)
    if not fid:
        return None
    mtype = _detect_media(msg)
    if mtype == "photo":
        return InputMediaPhoto(media=fid, caption=caption or None, parse_mode=parse_mode if caption else None)
    if mtype == "video":
        return InputMediaVideo(media=fid, caption=caption or None, parse_mode=parse_mode if caption else None)
    if mtype == "animation":
        # send_media_group doesn't support animation; fall back to document
        return InputMediaDocument(media=fid, caption=caption or None, parse_mode=parse_mode if caption else None)
    if mtype == "document":
        return InputMediaDocument(media=fid, caption=caption or None, parse_mode=parse_mode if caption else None)
    return None

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# /fb COMMAND HANDLER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@router.message(Command("fb"))
async def feedback_cmd(message: types.Message):
    """Reply to any gate hit with /fb to submit it as feedback.
    Supports: single photo, video, GIF/animation, document, or a photo album (up to 7)."""

    if not message.reply_to_message:
        await message.reply(
            "<b><i>Usage ➛ Reply to your hit message with /fb</i></b>",
            parse_mode="HTML"
        )
        return

    replied = message.reply_to_message
    user    = message.from_user

    # ── Confirm to user INSTANTLY — no waiting ──────────────────────────────
    await message.reply(
          "━━━━━━━━━━━━━━━━\n"
          "<b><i>Feedback Submitted ✓</i></b>\n"
          "━━━━━━━━━━━━━━━━",
          parse_mode="HTML"
   )

    # ── Collect media group if applicable ───────────────────────────────────
    gid = getattr(replied, "media_group_id", None)
    if gid:
        # Wait briefly so all album messages can be collected by the middleware
        await asyncio.sleep(0.35)
        group_msgs = list(_MEDIA_GROUPS.get(gid, [replied]))
        # Sort by message_id to preserve original order
        group_msgs.sort(key=lambda m: m.message_id)
        # Cap at 10 (Telegram media group limit)
        group_msgs = group_msgs[:10]
        media_type = "photo_album"
        hit_text   = (replied.caption or replied.text or "").strip()
    else:
        group_msgs = [replied]
        media_type = _detect_media(replied)
        hit_text   = (replied.caption or replied.text or "").strip()

    # ── Store pending ────────────────────────────────────────────────────────
    pid = uuid.uuid4().hex[:10]
    _PENDING[pid] = {
        "messages":   group_msgs,
        "media_type": media_type,
        "hit_text":   hit_text,
        "user":       user,
    }

    admin_text = _admin_info_text(user, media_type, len(group_msgs))

    # ── Forward all hit messages to admin + send info block — concurrently ──
    async def _forward_all():
        for m in group_msgs:
            try:
                # Correct aiogram copy method
                await message.bot.copy_message(
                    chat_id=ADMIN_ID,
                    from_chat_id=m.chat.id,
                    message_id=m.message_id,
                    caption=m.caption if m.caption else None,
                    parse_mode="HTML" if m.caption else None
                )
                logging.info(f"[fb] Copied message {m.message_id} to admin")
            except Exception as e:
                logging.warning(f"[fb] Could not copy message {m.message_id}: {e}")
                try:
                    await message.bot.send_message(
                        ADMIN_ID,
                        f"⚠️ Feedback from user {user.id} — could not copy message"
                    )
                except Exception as e2:
                    logging.error(f"[fb] Admin notification failed: {e2}")

    async def _send_admin_info():
        try:
            await message.bot.send_message(
                chat_id=ADMIN_ID,
                text=admin_text,
                parse_mode="HTML",
                reply_markup=_approve_keyboard(pid),
                disable_web_page_preview=True
            )
            logging.info(f"[fb] Pending {pid} stored for user {user.id}")
        except Exception as e:
            logging.error(f"[fb] Admin notify error: {e}")

    # Run forward + admin notify concurrently — much faster
    await asyncio.gather(_forward_all(), _send_admin_info())

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# APPROVE CALLBACK
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@router.callback_query(F.data.startswith("fb_approve_"))
async def fb_approve(callback: types.CallbackQuery):
    # Answer + update admin message INSTANTLY before any network work
    await callback.answer()  # ✅ Call it directly
    
    await callback.message.edit_text(
        "<b><i>Approved ✓ — Posting to channel...</i></b>",
        parse_mode="HTML"
    )

    pid = callback.data.replace("fb_approve_", "")
    entry = _PENDING.pop(pid, None)

    if not entry:
        await callback.message.edit_text(
            "<b><i>Expired — feedback already handled or bot restarted.</i></b>",
            parse_mode="HTML"
        )
        return

    user = entry["user"]
    msgs = entry["messages"]
    media_type = entry["media_type"]
    hit_text = entry["hit_text"]
    caption = _channel_caption(user, hit_text)
    ch_kb = _channel_keyboard()

    try:
        if media_type == "photo_album" and len(msgs) > 1:
            media_items = []
            for i, m in enumerate(msgs):
                inp = _build_input_media(m, caption=caption if i == 0 else "")
                if inp:
                    media_items.append(inp)
            if media_items:
                await callback.bot.send_media_group(
                    chat_id=FEEDBACK_CHANNEL,
                    media=media_items
                )
                await callback.bot.send_message(
                    chat_id=FEEDBACK_CHANNEL,
                    text="⬆️",
                    reply_markup=ch_kb,
                    disable_web_page_preview=True
                )
            else:
                await callback.bot.forward_message(
                    chat_id=FEEDBACK_CHANNEL,
                    from_chat_id=msgs[0].chat.id,
                    message_id=msgs[0].message_id
                )

        elif media_type == "photo":
            await callback.bot.send_photo(
                chat_id=FEEDBACK_CHANNEL,
                photo=_get_file_id(msgs[0]),
                caption=caption,
                parse_mode="HTML",
                reply_markup=ch_kb
            )

        elif media_type == "video":
            await callback.bot.send_video(
                chat_id=FEEDBACK_CHANNEL,
                video=_get_file_id(msgs[0]),
                caption=caption,
                parse_mode="HTML",
                reply_markup=ch_kb
            )

        elif media_type == "animation":
            await callback.bot.send_animation(
                chat_id=FEEDBACK_CHANNEL,
                animation=_get_file_id(msgs[0]),
                caption=caption,
                parse_mode="HTML",
                reply_markup=ch_kb
            )

        elif media_type == "document":
            await callback.bot.send_document(
                chat_id=FEEDBACK_CHANNEL,
                document=_get_file_id(msgs[0]),
                caption=caption,
                parse_mode="HTML",
                reply_markup=ch_kb
            )

        else:
            await callback.bot.send_message(
                chat_id=FEEDBACK_CHANNEL,
                text=caption,
                parse_mode="HTML",
                disable_web_page_preview=True,
                reply_markup=ch_kb
            )

        await callback.message.edit_text(
            "<b><i>Approved ✓ — Posted to channel</i></b>",
            parse_mode="HTML"
        )
        logging.info(f"[fb] Approved and posted for user {user.id} ({media_type}, {len(msgs)} item(s))")

    except Exception as e:
        logging.error(f"[fb] Approve post error: {e}")
        try:
            await callback.message.edit_text(
                f"<b><i>Approve failed: {e}</i></b>",
                parse_mode="HTML"
            )
        except Exception:
            pass

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# REJECT CALLBACK
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
@router.callback_query(F.data.startswith("fb_reject_"))
async def fb_reject(callback: types.CallbackQuery):
    await callback.answer()
    pid = callback.data.replace("fb_reject_", "")
    _PENDING.pop(pid, None)
    await callback.message.edit_text(
        "<b><i>Rejected ✗</i></b>",
        parse_mode="HTML"
    )
    logging.info(f"[fb] Rejected feedback {pid}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# REGISTRATION (kept for backward compat — no-op if router already included)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def setup_feedback_handler(dispatcher):
    logging.info("[fb] setup_feedback_handler called (no-op — router pre-included).")
