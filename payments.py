# ═══════════════════════════════════════════════════════════════════════════════
# payments.py - OxaPay Crypto Payment Gateway (Fully Automated Premium Edition)
# ═══════════════════════════════════════════════════════════════════════════════

import requests
import json
import asyncio
import logging
import random
import string
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

# ═══════════════════════════════════════════════════════════════════════════════
# OXAPAY CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

API_KEY = "NLQIPG-8SOFHX-VPRQZ5-MQA7H9"
CALLBACK_URL = "https://cxchk.site/payment_callback"
API_BASE = "https://api.oxapay.com/v1"

# ═══════════════════════════════════════════════════════════════════════════════
# DIRECT NETWORK MAPPING (The only 7 allowed options)
# ═══════════════════════════════════════════════════════════════════════════════

DIRECT_NETWORKS: Dict[str, Dict[str, str]] = {
    "BEP20": {"currency": "USDT", "network": "BSC"},
    "TRC20": {"currency": "USDT", "network": "TRC20"},
    "LTC": {"currency": "LTC", "network": "Litecoin"},
    "BTC": {"currency": "BTC", "network": "Bitcoin"},
    "SOL": {"currency": "SOL", "network": "Solana"},
    "POL": {"currency": "POL", "network": "Polygon"},
    "TON": {"currency": "TON", "network": "TON"}
}

# ═══════════════════════════════════════════════════════════════════════════════
# PLAN CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

PLANS: Dict[str, Dict[str, Any]] = {
    "CORE":   {"price": 10, "days": 7,  "credits": 12000,  "display": "CORE"},
    "ELITE":  {"price": 15, "days": 15, "credits": 23000, "display": "ELITE"},
    "ROOT":   {"price": 30, "days": 30, "credits": 53000, "display": "ROOT"}
}

# ═══════════════════════════════════════════════════════════════════════════════
# UNICODE BOLD MATH SANS MAPPER (Fixed Lengths)
# ═══════════════════════════════════════════════════════════════════════════════

def to_premium_bold(text: str) -> str:
    """Converts standard text to 𝗨𝗻𝗶𝗰𝗼𝗱𝗲 𝗕𝗼𝗹𝗱 Math Sans-Serif"""
    normal = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789$"
    bold   = "𝗔𝗕𝗖𝗗𝗘𝗙𝗚𝗛𝗜𝗝𝗞𝗟𝗠𝗡𝗢𝗣𝗤𝗥𝗦𝗧𝗨𝗩𝗪𝗫𝗬𝗭𝗮𝗯𝗰𝗱𝗲𝗳𝗴𝗵𝗶𝗷𝗸𝗹𝗺𝗻𝗼𝗽𝗾𝗿𝘀𝘁𝘂𝘃𝘄𝘅𝘆𝘇𝟬𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵$"
    return text.translate(str.maketrans(normal, bold))

# ═══════════════════════════════════════════════════════════════════════════════
# PAYMENT TRACKING (In-Memory)
# ═══════════════════════════════════════════════════════════════════════════════

active_payments: Dict[str, Dict[str, Any]] = {}
user_sessions: Dict[int, Dict[str, str]] = {}

_bot = None

def set_bot(bot):
    global _bot
    _bot = bot

def get_bot():
    return _bot

# ═══════════════════════════════════════════════════════════════════════════════
# PAYMENT CREATION & STATUS
# ═══════════════════════════════════════════════════════════════════════════════

def create_payment(user_id: int, plan: str, currency: str, network: str) -> Optional[Dict]:
    if plan not in PLANS: return None
    
    plan_info = PLANS[plan]
    url = f"{API_BASE}/payment/white-label"
    headers = {
        "merchant_api_key": API_KEY,
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0"
    }
    order_id = f"{user_id}_{plan}_{int(datetime.now().timestamp())}"
    payload = {
        "amount": plan_info["price"], "currency": "USD", "pay_currency": currency,
        "network": network, "lifetime": 30, "fee_paid_by_payer": 0,
        "under_paid_coverage": 2, "to_currency": "USDT", "order_id": order_id,
        "description": f"{plan} Plan Activation - User {user_id}", "callback_url": CALLBACK_URL
    }
    
    try:
        r = requests.post(url, data=json.dumps(payload), headers=headers, timeout=30)
        res = r.json()
        if res.get("status") == 200:
            payment_data = res["data"]
            return {
                "track_id": payment_data["track_id"], "address": payment_data["address"],
                "amount": payment_data["pay_amount"], "currency": payment_data["pay_currency"],
                "network": payment_data["network"], "qr": payment_data["qr_code"],
                "expires": payment_data["expired_at"], "order_id": order_id
            }
        else:
            logging.error(f"OxaPay API Error: {res}")
            return None
    except Exception as e:
        logging.error(f"Payment creation error: {e}")
        return None

def check_payment_status(track_id: str) -> Optional[str]:
    url = f"{API_BASE}/payment/{track_id}"
    headers = {"merchant_api_key": API_KEY, "Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=15)
        res = r.json()
        status = res.get("data", {}).get("status")
        if track_id in active_payments:
            active_payments[track_id]["status"] = status
        return status
    except Exception as e:
        logging.error(f"Status check error for {track_id}: {e}")
        return None

# ═══════════════════════════════════════════════════════════════════════════════
# PLAN ACTIVATION
# ═══════════════════════════════════════════════════════════════════════════════
def generate_receipt_id():
    """Generates a Receipt ID like STRIPEX-054879-CHK"""
    random_str = ''.join(random.choices(string.digits, k=6))
    return f"STRIPEX-{random_str}-CHK"

def activate_plan(user_id: int, plan: str) -> bool:
    if plan not in PLANS: return False
    plan_info = PLANS[plan]
    try:
        from database import DB_CONFIG
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        conn = psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)
        cursor = conn.cursor()
        expiry = datetime.now() + timedelta(days=plan_info["days"])
        
        # 1. ENSURE USER EXISTS
        cursor.execute("""
            INSERT INTO users (user_id, username, first_name, credits, joined_at)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (user_id) DO NOTHING
        """, (user_id, "Unknown", "User", 0, datetime.now()))

        # 2. Calculate correct expiry date (stacking if already premium)
        cursor.execute("SELECT premium_expiry FROM users WHERE user_id = %s", (user_id,))
        row = cursor.fetchone()
        if row and row.get('premium_expiry'):
            current_expiry = row['premium_expiry']
            if current_expiry and datetime.now() < current_expiry:
                expiry = current_expiry + timedelta(days=plan_info["days"])
        
        # 3. Update Premium Time
        cursor.execute(
            "UPDATE users SET is_premium = 1, premium_expiry = %s WHERE user_id = %s",
            (expiry, user_id)
        )

        # 4. Add Plan Credits
        cursor.execute(
            "UPDATE users SET credits = credits + %s WHERE user_id = %s",
            (plan_info["credits"], user_id)
        )

        # 5. Generate and Store Receipt (FIXED: Added receipt_id and purchased_on)
        receipt_id = generate_receipt_id()
        purchased_on = datetime.now()
        
        cursor.execute(
            "INSERT INTO receipts (receipt_id, user_id, plan, amount_paid, purchased_on, expires_on) VALUES (%s, %s, %s, %s, %s, %s)",
            (receipt_id, user_id, plan, plan_info["price"], purchased_on, expiry)
        )
        
        affected = cursor.rowcount
        conn.commit()
        conn.close()
        
        if affected > 0:
            logging.info(f"✅ Activated {plan} for user {user_id} (+{plan_info['credits']} credits)")
            return True
        return False
    except Exception as e:
        logging.error(f"Plan activation error for {user_id}: {e}")
        return False

# ═══════════════════════════════════════════════════════════════════════════════
# GET RECEIPT INFO FOR CONGRATULATIONS MESSAGE
# ═══════════════════════════════════════════════════════════════════════════════

def get_receipt_for_user(user_id: int, plan: str) -> Optional[Dict[str, Any]]:
    """Fetches receipt details for the congratulations message."""
    try:
        from database import DB_CONFIG
        import psycopg2
        from psycopg2.extras import RealDictCursor
        
        conn = psycopg2.connect(**DB_CONFIG, cursor_factory=RealDictCursor)
        cursor = conn.cursor()
        
        # Get user info
        cursor.execute("SELECT first_name FROM users WHERE user_id = %s", (user_id,))
        user_row = cursor.fetchone()
        first_name = user_row['first_name'] if user_row and user_row['first_name'] else "User"
        if first_name in ["Unknown", "User"]:
            first_name = "User"
        
        user_link = f'<a href="tg://user?id={user_id}">{first_name}</a>'
        
        # Get latest receipt for this plan
        cursor.execute(
            "SELECT receipt_id FROM receipts WHERE user_id = %s AND plan = %s ORDER BY purchased_on DESC LIMIT 1",
            (user_id, plan)
        )
        receipt_row = cursor.fetchone()
        
        conn.close()
        
        if receipt_row:
            plan_info = PLANS.get(plan, {})
            plan_display = plan_info.get('display', plan)
            return {
                "user_link": user_link,
                "plan_name": plan_display,
                "days": plan_info.get('days', 0),
                "credits": plan_info.get('credits', 0),
                "receipt_id": receipt_row['receipt_id']
            }
        return None
    except Exception as e:
        logging.error(f"Error getting receipt for user {user_id}: {e}")
        return None

# ═══════════════════════════════════════════════════════════════════════════════
# PREMIUM TEXT FORMATTERS (Exact UI Match)
# ═══════════════════════════════════════════════════════════════════════════════

def format_payment_caption(payment_data: Dict, plan: str) -> str:
    plan_info = PLANS.get(plan, {})
    
    try:
        expires_dt = datetime.fromisoformat(payment_data["expires"].replace("Z", "+00:00"))
        diff = expires_dt - datetime.now(expires_dt.tzinfo)
        minutes = int(diff.total_seconds() / 60)
    except:
        minutes = 30

    plan_txt = to_premium_bold(f"Plan ➛ {plan_info.get('display', plan)}")
    price_txt = to_premium_bold(f"Price ➛ ${plan_info.get('price', 0):.2f} USD")
    pay_txt = to_premium_bold(f"Pay ➛ {payment_data['amount']} {payment_data['currency']}")
    net_txt = to_premium_bold(f"Network ➛ {payment_data['network']}")
    dep_txt = to_premium_bold("Deposit Address ➛")
    exp_txt = to_premium_bold(f"Expires in ➛ {minutes} minutes")
    confirm_txt = to_premium_bold("Deposits take 3 mins to confirm after completed")
    
    return (
        f"{plan_txt}\n"
        f"{price_txt}\n"
        f"{pay_txt}\n"
        f"{net_txt}\n\n"
        f"{dep_txt}\n"
        f"<code>{payment_data['address']}</code>\n\n"
        f"{exp_txt}\n"
        f"{confirm_txt}"
    )

# ═══════════════════════════════════════════════════════════════════════════════
# AUTOMATIC MONITORING LOGIC (Runs silently)
# ═══════════════════════════════════════════════════════════════════════════════

async def start_payment_monitor(track_id: str, chat_id: int, message_id: int, is_photo: bool, original_text: str):
    if track_id in active_payments:
        existing = active_payments[track_id].get("task")
        if existing and not existing.done(): existing.cancel()
    
    active_payments[track_id].update({"chat_id": chat_id, "message_id": message_id, "is_photo": is_photo, "original_text": original_text})
    task = asyncio.create_task(_monitor_payment_loop(track_id))
    active_payments[track_id]["task"] = task

async def _monitor_payment_loop(track_id: str):
    max_checks = 360
    check_count = 0
    while check_count < max_checks:
        try:
            status = await asyncio.to_thread(check_payment_status, track_id)
            if status == "Paid":
                logging.info(f"💰 Payment confirmed: {track_id}")
                await _handle_payment_success(track_id)
                return
            elif status == "Expired":
                logging.info(f"⏰ Payment expired: {track_id}")
                await _handle_payment_expired(track_id)
                return
            await asyncio.sleep(5)
            check_count += 10
        except asyncio.CancelledError:
            return
        except Exception as e:
            logging.error(f"Monitor error for {track_id}: {e}")
            await asyncio.sleep(5)

async def _handle_payment_success(track_id: str):
    bot = get_bot()
    if not bot: return
    
    payment = active_payments.get(track_id, {})
    user_id = payment.get("user_id")
    plan = payment.get("plan")
    chat_id = payment.get("chat_id")
    message_id = payment.get("message_id")
    
    if not all([user_id, plan, chat_id, message_id]): return
    
    success = await asyncio.to_thread(activate_plan, user_id, plan)
    plan_info = PLANS.get(plan, {})
    
    # Get receipt info for congratulations message
    receipt_info = get_receipt_for_user(user_id, plan)
    
    if receipt_info:
        dm_text = (
            f"𝐂𝐨𝐧𝐠𝐫𝐚𝐭𝐮𝐥𝐚𝐭𝐢𝐨𝐧𝐬!🎉 𝐲𝐨𝐮𝐫 𝐚𝐜𝐜𝐞𝐬𝐬 𝐡𝐚𝐬 𝐛𝐞𝐞𝐧 𝐚𝐜𝐭𝐢𝐯𝐚𝐭𝐞𝐝.\n"
            f"𝗨𝘀𝗲𝗿 ➛ {receipt_info['user_link']}\n"
            f"𝗔𝗰𝗰𝗲𝘀𝘀 ➛ <b>{receipt_info['plan_name']}</b>\n"
            f"𝗗𝘂𝗿𝗮𝘁𝗶𝗼𝗻 ➛ {receipt_info['days']} Days\n"
            f"𝗖𝗿𝗲𝗱𝗶𝘁𝘀 𝗔𝗱𝗱𝗲𝗱 ➛ +{receipt_info['credits']:,}\n"
            f"𝗥𝗲𝗰𝗲𝗶𝗽𝘁 𝗜𝗗 ➛ <code>{receipt_info['receipt_id']}</code>\n"
            f"𝗽𝗹𝗲𝗮𝘀𝗲 𝘀𝗮𝘃𝗲 𝘁𝗵𝗶𝘀 𝗿𝗲𝗰𝗲𝗶𝗽𝘁 𝗜𝗗."
        )
    else:
        dm_text = (
            f"𝐂𝐨𝐧𝐠𝐫𝐚𝐭𝐮𝐥𝐚𝐭𝐢𝐨𝐧𝐬!🎉 𝐲𝐨𝐮𝐫 𝐚𝐜𝐜𝐞𝐬𝐬 𝐡𝐚𝐬 𝐛𝐞𝐞𝐧 𝐚𝐜𝐭𝐢𝐯𝐚𝐭𝐞𝐝.\n"
            f"𝗔𝗰𝗰𝗲𝘀𝘀 ➛ <b>{plan_info.get('display', plan)}</b>\n"
            f"𝗗𝘂𝗿𝗮𝘁𝗶𝗼𝗻 ➛ {plan_info.get('days', 0)} Days\n"
            f"𝗖𝗿𝗲𝗱𝗶𝘁𝘀 𝗔𝗱𝗱𝗲𝗱 ➛ +{plan_info.get('credits', 0):,}\n"
            f"𝗬𝗼𝘂𝗿 𝗽𝗹𝗮𝗻 𝗵𝗮𝘀 𝗯𝗲𝗲𝗻 𝗮𝗰𝘁𝗶𝘃𝐚𝐭𝐞𝐝!"
        )
    
    # SUCCESS EDIT TEXT (for the payment chat)
    success_text = (
        f"✅ <b>𝗧𝗿𝗮𝗻𝘀𝗮𝗰𝘁𝗶𝗼𝗻 𝗦𝘂𝗰𝗰𝗲𝗲𝗱𝗲𝗱!</b>\n\n"
        f" <b>𝗣𝗹𝗮𝗻 ➛</b> {plan_info.get('display', plan)}\n"
        f" <b>𝗗𝘂𝗿𝗮𝘁𝗶𝗼𝗻 ➛</b> {plan_info.get('days', 0)} Days\n"
        f" <b>𝗖𝗿𝗲𝗱𝗶𝘁𝘀 𝗔𝗱𝗱𝗲𝗱 ➛</b> +{plan_info.get('credits', 0):,}\n\n"
        f" <b>𝗬𝗼𝘂𝗿 𝗽𝗹𝗮𝗻 𝗵𝗮𝘀 𝗯𝗲𝗲𝗻 𝗮𝗰𝘁𝗶𝘃𝗮𝘁𝗲𝗱!</b>"
    )
    
    try:
        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=success_text)
    except Exception as e:
        logging.error(f"Error editing success message: {e}")
        try:
            await bot.send_message(chat_id=chat_id, text=success_text)
        except: pass
    
    # SEND DM TO USER (congratulations message)
    try:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="𝗦𝘂𝗽𝗽𝗼𝗿𝘁", url="https://t.me/leiamarketcc")]
        ])
        await bot.send_message(
            chat_id=user_id,
            text=dm_text,
            parse_mode="HTML",
            reply_markup=keyboard
        )
        logging.info(f"📧 Sent congratulations DM to user {user_id}")
    except Exception as e:
        logging.error(f"Could not send DM to user {user_id}: {e}")
    
    _cleanup_payment(track_id, user_id)

async def _handle_payment_expired(track_id: str):
    bot = get_bot()
    if not bot: return
    payment = active_payments.get(track_id, {})
    chat_id = payment.get("chat_id")
    message_id = payment.get("message_id")
    user_id = payment.get("user_id")
    
    expired_text = "<b>Payment Expired</b>\n\nThe payment window has closed.\nPlease start a new payment."
    try:
        await bot.edit_message_text(chat_id=chat_id, message_id=message_id, text=expired_text)
    except: pass
    
    _cleanup_payment(track_id, user_id)

async def manual_check_payment(track_id: str) -> str:
    """Returns status string silently without touching the chat message."""
    status = await asyncio.to_thread(check_payment_status, track_id)
    if status == "Paid":
        await _handle_payment_success(track_id)
    elif status == "Expired":
        await _handle_payment_expired(track_id)
    return status if status else "Pending"

# ═══════════════════════════════════════════════════════════════════════════════
# SESSION & CLEANUP MANAGEMENT
# ═══════════════════════════════════════════════════════════════════════════════

def set_user_session(user_id: int, plan: str, currency: str = None):
    user_sessions[user_id] = {"plan": plan, "currency": currency}

def get_user_session(user_id: int) -> Optional[Dict]:
    return user_sessions.get(user_id)

def clear_user_session(user_id: int):
    if user_id in user_sessions: del user_sessions[user_id]

def _cleanup_payment(track_id: str, user_id: int = None):
    if track_id in active_payments:
        task = active_payments[track_id].get("task")
        if task and not task.done(): task.cancel()
        del active_payments[track_id]
    if user_id and user_id in user_sessions: del user_sessions[user_id]

def cancel_user_active_payment(user_id: int):
    for track_id, payment in list(active_payments.items()):
        if payment.get("user_id") == user_id:
            task = payment.get("task")
            if task and not task.done(): task.cancel()
            del active_payments[track_id]
    clear_user_session(user_id)

def register_payment(track_id: str, user_id: int, plan: str):
    active_payments[track_id] = {"user_id": user_id, "plan": plan, "created_at": datetime.now(), "status": "Pending"}

# ═══════════════════════════════════════════════════════════════════════════════
# KEYBOARD BUILDERS (No emojis, no bold tags inside buttons)
# ═══════════════════════════════════════════════════════════════════════════════

def get_plan_selection_keyboard():
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='𝗖𝗢𝗥𝗘 — $10', callback_data="pay_plan_CORE")],
        [InlineKeyboardButton(text='𝗘𝗟𝗜𝗧𝗘 — $15', callback_data="pay_plan_ELITE")],
        [InlineKeyboardButton(text='𝗥𝗢𝗢𝗧 — $30', callback_data="pay_plan_ROOT")],
        [InlineKeyboardButton(text="« 𝗕𝗮𝗰𝗸", callback_data="menu_pricing")]
    ])

def get_network_selection_keyboard(user_id: int):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="𝗨𝗦𝗗𝗧 (𝗕𝗘𝗣𝟮𝟬)", callback_data="pay_direct_BEP20"), InlineKeyboardButton(text="𝗨𝗦𝗗𝗧 (𝗧𝗥𝗖𝟮𝟬)", callback_data="pay_direct_TRC20")],
        [InlineKeyboardButton(text="𝗟𝗜𝗧𝗘𝗖𝗢𝗜𝗡", callback_data="pay_direct_LTC"), InlineKeyboardButton(text="𝗕𝗜𝗧𝗖𝗢𝗜𝗡", callback_data="pay_direct_BTC")],
        [InlineKeyboardButton(text="𝗦𝗢𝗟𝗔𝗡𝗔", callback_data="pay_direct_SOL"), InlineKeyboardButton(text="𝗣𝗢𝗟𝗬𝗚𝗢𝗡", callback_data="pay_direct_POL")],
        [InlineKeyboardButton(text="𝗧𝗢𝗡", callback_data="pay_direct_TON")],
        [InlineKeyboardButton(text="« 𝗕𝗮𝗰𝗸", callback_data=f"pay_back_plans_{user_id}")]
    ])

def get_paid_button_keyboard(track_id: str, user_id: int):
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='Paid ✅', callback_data=f"pay_check_{track_id}")],
        [InlineKeyboardButton(text="𝗦𝘂𝗽𝗽𝗼𝗿𝘁", url="https://t.me/STRIPEX_SUPPORT_BOT")],
        [InlineKeyboardButton(text="« 𝗕𝗮𝗰𝗸", callback_data=f"pay_back_plans_{user_id}")]
    ])
