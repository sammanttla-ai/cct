import re
import logging
import aiohttp
import asyncio
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor
import io

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AIogram Imports
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
from aiogram import types, F, Router
from aiogram.types import BufferedInputFile

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# LOCAL IMPORTS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
from database import get_db_connection

# Router for this module
router = Router()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONFIGURATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MAX_CONCURRENT_CHECKS = 5  # Parallel requests limit
PROXY_TIMEOUT = 8  # Timeout per proxy check (seconds)
IPIFY_API_URL = "https://api.ipify.org?format=json"  # Ipify API endpoint

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PARSING HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def parse_proxy_input(proxy_input):
    """
    Parses proxy input from ANY common format.
    """
    s = proxy_input.strip()
    protocol = 'http' 
    
    protocol_match = re.match(r'^(?P<p>http|https|socks4|socks5)://', s, re.IGNORECASE)
    if protocol_match:
        protocol = protocol_match.group('p').lower()
        s = s[len(protocol_match.group('p'))+3:]

    def is_valid(ip, port):
        return port and port.isdigit()

    # Pattern A: user:pass@ip:port
    match = re.match(r'^([^:@]+):([^:@]+)@([^:@]+):(\d+)$', s)
    if match:
        user, password, ip, port = match.groups()
        if is_valid(ip, port): return build_dict(user, password, ip, port, protocol, proxy_input)

    # Pattern B: user:pass ip:port
    match = re.match(r'^([^:@]+):([^:@]+)\s+([^:@]+):(\d+)$', s)
    if match:
        user, password, ip, port = match.groups()
        if is_valid(ip, port): return build_dict(user, password, ip, port, protocol, proxy_input)

    # Pattern C: ip:port user pass
    match = re.match(r'^([^:@]+):(\d+)\s+([^:@]+)\s+([^:@]+)$', s)
    if match:
        ip, port, user, password = match.groups()
        if is_valid(ip, port): return build_dict(user, password, ip, port, protocol, proxy_input)

    # Pattern D: user pass ip:port
    match = re.match(r'^([^:@]+)\s+([^:@]+)\s+([^:@]+):(\d+)$', s)
    if match:
        user, password, ip, port = match.groups()
        if is_valid(ip, port): return build_dict(user, password, ip, port, protocol, proxy_input)

    # Pattern E: user pass ip port ✅ FIXED
    match = re.match(r'^([^:@]+)\s+([^:@]+)\s+([^:@]+)\s+(\d+)$', s)
    if match:
        user, password, ip, port = match.groups()
        if is_valid(ip, port): return build_dict(user, password, ip, port, protocol, proxy_input)

    # Pattern F: user:pass:ip:port
    match = re.match(r'^([^:@]+):([^:@]+):([^:@]+):(\d+)$', s)
    if match:
        user, password, ip, port = match.groups()
        if is_valid(ip, port): return build_dict(user, password, ip, port, protocol, proxy_input)

    # Pattern G: ip:port:user:pass
    match = re.match(r'^([^:@]+):(\d+):([^:@]+):([^:@]+)$', s)
    if match:
        ip, port, user, password = match.groups()
        if is_valid(ip, port): return build_dict(user, password, ip, port, protocol, proxy_input)

    return None

def build_dict(user, password, ip, port, protocol, original_input):
    encoded_user = quote(user, safe='')
    encoded_pass = quote(password, safe='')
    return {
        "user": user,
        "password": password,
        "ip": ip,
        "port": port,
        "original_format": original_input,
        "url_format": f"{protocol}://{encoded_user}:{encoded_pass}@{ip}:{port}",
        "db_format": f"{user} {password} {ip} {port}",
        "http_format": f"http://{user}:{password}@{ip}:{port}"
    }


async def check_proxy_live(proxy_url, session=None, timeout=PROXY_TIMEOUT):
    """
    Checks if proxy is live using IPIFY API.
    Returns: (is_alive: bool, info: dict)
    
    Args:
        proxy_url: Full proxy URL with auth
        session: Optional aiohttp session (for connection pooling)
        timeout: Request timeout in seconds
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'application/json'
    }
    
    client_timeout = aiohttp.ClientTimeout(total=timeout, connect=timeout/2)
    
    # Create session if not provided
    close_session = False
    if session is None:
        session = aiohttp.ClientSession(timeout=client_timeout, headers=headers)
        close_session = True
    
    try:
        async with session.get(IPIFY_API_URL, proxy=proxy_url, ssl=False) as resp:
            if resp.status == 200:
                try:
                    data = await resp.json()
                    ip = data.get('ip')
                    if ip:
                        return True, {"ip": ip}
                    return False, {"error": "No IP in response"}
                except Exception:
                    text_data = await resp.text()
                    if text_data.strip():
                        return True, {"ip": text_data.strip()}
                    return False, {"error": "Empty response"}
            elif resp.status == 429:
                return False, {"error": "Rate limited"}
            else:
                return False, {"error": f"HTTP {resp.status}"}
                
    except asyncio.TimeoutError:
        return False, {"error": "Timeout"}
    except aiohttp.ClientProxyConnectionError:
        return False, {"error": "Connection failed"}
    except aiohttp.ClientConnectorError as e:
        return False, {"error": f"DNS/Connection error"}
    except aiohttp.ClientError as e:
        return False, {"error": f"Client error: {str(e)[:50]}"}
    except Exception as e:
        return False, {"error": str(e)[:80]}
    finally:
        if close_session:
            await session.close()


async def check_proxies_parallel(proxies_list, max_concurrent=MAX_CONCURRENT_CHECKS):
    """
    Check multiple proxies in parallel with semaphore limiting.
    
    Args:
        proxies_list: List of proxy dicts with 'url_format' key
        max_concurrent: Max simultaneous checks (default: 5)
        
    Returns:
        List of tuples: [(proxy_data, is_live, info), ...]
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    results = []
    
    async def check_with_semaphore(proxy_data):
        async with semaphore:
            is_live, info = await check_proxy_live(proxy_data['url_format'])
            return (proxy_data, is_live, info)
    
    # Create tasks for all proxies
    tasks = [check_with_semaphore(p) for p in proxies_list]
    
    # Execute all tasks concurrently and gather results
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Process results - handle any exceptions
    processed_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            processed_results.append((proxies_list[i], False, {"error": str(result)}))
        else:
            processed_results.append(result)
    
    return processed_results


async def run_db_operation(func, *args):
    """Helper to run DB operations in thread pool"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, func, *args)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# BACKGROUND TASKS (PARALLEL PROCESSING)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def process_proxies_background(bot, message: types.Message, valid_proxies: list):
    """Process proxies in background - PARALLEL checking (5 at a time)"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    total_count = len(valid_proxies)
    
    # Send initial status message
    status_msg = await message.reply(
        f"⏳ <b>Processing...</b>\n\n"
        f"<code>{total_count}</code> proxies to check\n"
        f"<i>Checking</i>",
        parse_mode="HTML"
    )
    
    # ✅ PARALLEL CHECKING - Fast!
    results_list = await check_proxies_parallel(valid_proxies)
    
    # Count results
    live_count = sum(1 for _, is_live, _ in results_list if is_live)
    dead_count = total_count - live_count
    
    # Prepare proxies to save
    to_save = [proxy_data['db_format'] for proxy_data, is_live, _ in results_list if is_live]
    
    # Save to DB (skip clones)
    added_count = 0
    clone_count = 0
    if to_save:
        try:
            def save_to_db():
                conn = get_db_connection()
                cursor = conn.cursor()
                
                # Fetch existing proxies for this user to check clones
                cursor.execute("SELECT proxy FROM proxies WHERE user_id = %s", (user_id,))
                existing_proxies = {row[0] for row in cursor.fetchall()}
                
                added = 0
                clones = 0
                for p_str in to_save:
                    if p_str not in existing_proxies:
                        cursor.execute("INSERT INTO proxies (user_id, proxy) VALUES (%s, %s)", (user_id, p_str))
                        existing_proxies.add(p_str)
                        added += 1
                    else:
                        clones += 1
                
                conn.commit()
                conn.close()
                return added, clones
            
            added_count, clone_count = await run_db_operation(save_to_db)
        except Exception as e:
            logging.error(f"DB Error: {e}")

    # Build final response
    is_bulk = total_count > 1
    
    if is_bulk:
        caption = (
            f"<b>✅ Complete!</b>\n\n"
            f"<b>Total ➛</b> <code>{total_count}</code>\n"
            f"<b>Live ➛</b> <b>{live_count}</b> ✅\n"
            f"<b>Added ➛</b> <b>{added_count}</b> 💾\n"
            f"<b>Clones ➛</b> <b>{clone_count}</b> 🔁\n"
            f"<b>Dead ➛</b> <b>{dead_count}</b> ❌"
        )
    else:
        # Single proxy result
        if results_list:
            proxy_data, is_live, info = results_list[0]
        else:
            proxy_data, is_live, info = valid_proxies[0], False, {}
        
        if is_live:
            ip = info.get("ip") or proxy_data['ip']
            if added_count > 0:
                caption = (
                    f"<b>✅ Success!</b>\n\n"
                    f"<b>Status ➛ Live ✅</b>\n"
                    f"<b>IP ➛</b> <code>{ip}</code>\n\n"
                    f"<b>💾 Saved to database</b>"
                )
            else:
                caption = (
                    f"<b>⚠️ Warning!</b>\n\n"
                    f"<b>Status ➛ Live ✅</b>\n"
                    f"<b>IP ➛</b> <code>{ip}</code>\n\n"
                    f"<b>🔁 Already exists in DB</b>"
                )
        else:
            error_msg = info.get("error", "Unknown")
            caption = (
                f"<b>❌ Failed!</b>\n\n"
                f"<b>Status ➛ Dead ❌</b>\n"
                f"<b>Reason ➛</b> <code>{error_msg}</code>\n\n"
                f"<b>🚫 Not added.</b>"
            )
    
    # Edit status message with final result (reply to original)
    try:
        await bot.edit_message_text(
            chat_id=status_msg.chat.id,
            message_id=status_msg.message_id,
            text=caption,
            parse_mode="HTML"
        )
    except Exception:
        # If edit fails, send new message replying to original
        await message.reply(caption, parse_mode="HTML")


async def check_db_proxies_background(bot, message: types.Message):
    """Check saved proxies in background - PARALLEL, single reply to command"""
    user_id = message.from_user.id
    chat_id = message.chat.id
    
    # Fetch proxies from DB
    def fetch_proxies():
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, proxy FROM proxies WHERE user_id = %s", (user_id,))
        rows = cursor.fetchall()
        conn.close()
        return rows
    
    try:
        rows = await run_db_operation(fetch_proxies)
    except Exception as e:
        logging.error(f"DB Error: {e}")
        await message.reply("<b>❌ DB Error.</b>", parse_mode="HTML")
        return

    if not rows:
        await message.reply("<b>📭 No proxies saved.</b>", parse_mode="HTML")
        return

    total_count = len(rows)
    
    # Send initial status message
    status_msg = await message.reply(
        f"⏳ <b>Checking...</b>\n\n"
        f"<code>{total_count}</code> saved proxies\n"
        f"<i>Testing {min(MAX_CONCURRENT_CHECKS, total_count)} at a time...</i>",
        parse_mode="HTML"
    )
    
    # Prepare proxy list for parallel checking
    proxies_to_check = []
    proxy_id_map = {}  # Map index to DB ID
    
    for idx, (proxy_id, proxy_str) in enumerate(rows):
        parsed = parse_proxy_input(proxy_str)
        if parsed:
            proxies_to_check.append(parsed)
            proxy_id_map[idx] = proxy_id
        else:
            # Invalid format, mark as dead immediately
            pass  # Will handle below
    
    # ✅ PARALLEL CHECKING - Much faster!
    results_list = await check_proxies_parallel(proxies_to_check)
    
    dead_ids = []
    live_proxies = []
    
    # Process results
    for idx, (proxy_data, is_live, info) in enumerate(results_list):
        db_id = proxy_id_map.get(idx)
        if is_live:
            live_proxies.append(proxy_data['db_format'])  # Use db_format
        else:
            if db_id:
                dead_ids.append(db_id)
    
    # Delete dead proxies from DB
    if dead_ids:
        def delete_dead():
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("DELETE FROM proxies WHERE id = ANY(%s)", (dead_ids,))
            conn.commit()
            conn.close()
        
        try:
            await run_db_operation(delete_dead)
        except Exception as e:
            logging.error(f"DB Delete Error: {e}")

    # Build caption
    caption = (
        f"<b>✅ Check Complete!</b>\n\n"
        f"<b>Total ➛</b> <code>{total_count}</code>\n"
        f"<b>Live ➛</b> <b>{len(live_proxies)}</b> ✅\n"
        f"<b>Removed ➛</b> <b>{len(dead_ids)}</b> 🗑️"
    )

    if not live_proxies:
        caption += "\n\n<b>⚠️ No live proxies remaining.</b>"
        
        # Update status message
        try:
            await bot.edit_message_text(
                chat_id=status_msg.chat.id,
                message_id=status_msg.message_id,
                text=caption,
                parse_mode="HTML"
            )
        except Exception:
            await message.reply(caption, parse_mode="HTML")
        return

    # Build .txt file content with http format
    file_content = ""
    for p_str in live_proxies:
        parsed = parse_proxy_input(p_str)
        if parsed:
            file_content += parsed['http_format'] + "\n"
        else:
            file_content += p_str + "\n"

    # Create file
    txt_file = BufferedInputFile(
        file=file_content.encode('utf-8'),
        filename=f"live_proxies_{len(live_proxies)}.txt"
    )

    # Delete status message and send file
    try:
        await bot.delete_message(
            chat_id=status_msg.chat.id, 
            message_id=status_msg.message_id
        )
    except Exception:
        pass

    # Send document replying directly to original command
    try:
        await message.reply_document(
            document=txt_file,
            caption=caption,
            parse_mode="HTML",
            reply_to_message_id=message.message_id
        )
    except Exception as e:
        logging.error(f"File send error: {e}")
        await message.reply(caption, parse_mode="HTML")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COMMAND 1: /proxy (Add Single or Bulk)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.message(F.text.startswith("/proxy"))
async def proxy_command(message: types.Message):
    # 1. Gather Text Input
    raw_text = ""
    parts = message.text.split(maxsplit=1)
    if len(parts) > 1: raw_text += parts[1].strip() + "\n"
    if message.reply_to_message and message.reply_to_message.text: raw_text += message.reply_to_message.text + "\n"
    if message.reply_to_message and message.reply_to_message.caption: raw_text += message.reply_to_message.caption + "\n"

    document = message.document
    if document:
        if document.file_size > 2 * 1024 * 1024:
            await message.reply("<b>❌ File too large. Max 2MB.</b>", parse_mode="HTML")
            return
        try:
            file = await message.bot.get_file(document.file_id)
            byte_content = await file.download_as_bytearray()
            raw_text += byte_content.decode('utf-8', errors='ignore')
        except Exception as e:
            await message.reply(f"<b>❌ Error reading file: {e}</b>", parse_mode="HTML")
            return

    if not raw_text.strip():
        await message.reply("<b>⚠️ Invalid Usage!</b>", parse_mode="HTML")
        return

    # 2. Parse
    lines = raw_text.strip().split('\n')
    valid_proxies = []
    for line in lines:
        proxy_data = parse_proxy_input(line)
        if proxy_data: valid_proxies.append(proxy_data)
            
    if not valid_proxies:
        await message.reply("<b>❌ No valid proxies found.</b>", parse_mode="HTML")
        return

    # 3. Start background task
    asyncio.create_task(process_proxies_background(message.bot, message, valid_proxies))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COMMAND 2: /checkproxy
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.message(F.text.startswith("/checkproxy"))
async def checkproxy_command(message: types.Message):
    # Start background task - will reply when done with .txt file
    asyncio.create_task(check_db_proxies_background(message.bot, message))


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COMMAND 3: /clearproxy
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.message(F.text.startswith("/clearproxy"))
async def clearproxy_command(message: types.Message):
    user_id = message.from_user.id
    
    def clear_proxies():
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM proxies WHERE user_id = %s", (user_id,))
        count = cursor.fetchone()[0]
        
        if count > 0:
            cursor.execute("DELETE FROM proxies WHERE user_id = %s", (user_id,))
            conn.commit()
            conn.close()
            return count
        else:
            conn.close()
            return 0
    
    try:
        count = await run_db_operation(clear_proxies)
        if count > 0:
            msg = f"<b>✅ Success!</b>\n\n<b>Deleted {count} proxies.</b>"
        else:
            msg = "<b>📭 Database is already empty.</b>"
        await message.reply(msg, parse_mode="HTML")
    except Exception as e:
        logging.error(f"DB Error: {e}")
        await message.reply("<b>❌ Error.</b>", parse_mode="HTML")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# BONUS: /myproxies command
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.message(F.text.startswith("/myproxies"))
async def myproxies_command(message: types.Message):
    """Quick check how many proxies are saved"""
    user_id = message.from_user.id
    
    def count_proxies():
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM proxies WHERE user_id = %s", (user_id,))
        count = cursor.fetchone()[0]
        conn.close()
        return count
    
    try:
        count = await run_db_operation(count_proxies)
        if count > 0:
            msg = (
                f"<b>📊 Your Proxies</b>\n\n"
                f"<b>Total Saved:</b> <b>{count}</b> proxies\n\n"
                f"Use <code>/checkproxy</code> to test them\n"
                f"Use <code>/clearproxy</code> to remove all"
            )
        else:
            msg = (
                f"<b>📭 No Proxies</b>\n\n"
                f"You haven't saved any proxies yet.\n\n"
                f"Use <code>/proxy</code> to add some!"
            )
        await message.reply(msg, parse_mode="HTML")
    except Exception as e:
        logging.error(f"DB Error: {e}")
        await message.reply("<b>❌ Error.</b>", parse_mode="HTML")
