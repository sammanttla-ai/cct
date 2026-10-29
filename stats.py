import asyncio
import os
import collections
import logging

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# AIogram Imports
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
from aiogram import types, F, Router

# Router for this module
router = Router()

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# HELPERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_leaderboard_data():
    """
    Reads mshh.txt (and mst.txt) to count hits per user.
    Returns a sorted list of top users.
    """
    # Dictionary to store counts
    counts = collections.Counter()
    
    # Dictionary to store user details (username, first_name)
    user_details = {}

    # List of files to check
    files_to_check = ["mshh.txt", "mst.txt"]

    for filename in files_to_check:
        if not os.path.exists(filename):
            continue
            
        try:
            with open(filename, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Expected format: user_id|username|first_name
                    parts = line.split("|")
                    if len(parts) >= 3:
                        user_id = parts[0]
                        username = parts[1]
                        first_name = parts[2]

                        # Increment count
                        counts[user_id] += 1

                        # Store user details if not already stored
                        if user_id not in user_details:
                            # Handle "None" strings or empty values
                            safe_username = username if username and username != "None" else None
                            safe_fname = first_name if first_name and first_name != "Unknown" else "Unknown"
                            
                            user_details[user_id] = {
                                "username": safe_username,
                                "first_name": safe_fname
                            }
        except Exception as e:
            logging.error(f"Error reading {filename}: {e}")
            continue

    # Sort users by count (descending) and take top 10
    # items() returns (user_id, count), we sort by count (x[1])
    top_users = sorted(counts.items(), key=lambda x: x[1], reverse=True)[:10]
    
    return top_users, user_details

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# COMMAND: /stats
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@router.message(F.text.startswith("/stats"))
async def stats_command(message: types.Message):
    """
    Displays the top 10 users ranked by total Charged cards.
    Pulls data from mshh.txt and mst.txt files.
    """
    
    # Create a status message while fetching
    status_msg = await message.answer("⏳ <b>Fetching Leaderboard...</b>", parse_mode="HTML")

    try:
        # Run file reading in thread to prevent blocking
        top_users, user_details = await asyncio.to_thread(get_leaderboard_data)

        # 1. Format the Message
        if not top_users:
            text = (
                "<b>🏆 𝗟𝗲𝗮𝗱𝗲𝗿𝗯𝗼𝗮𝗿𝗱 (𝗖𝗵𝗮𝗿𝗴𝗲𝗱)</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                "No charged cards found yet.\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
                "🛠️ 𝗗𝗲𝘃 ➛ <a href='https://t.me/FailureFr_07'>kคli liຖนxx</a>"
            )
        else:
            header = (
                "<b>🏆 𝗟𝗲𝗮𝗱𝗲𝗿𝗯𝗼𝗮𝗿𝗱 (𝗖𝗵𝗮𝗿𝗴𝗲𝗱)</b>\n"
                "━━━━━━━━━━━━━━━━━━━━━\n"
            )
            
            list_text = ""
            for index, (user_id, count) in enumerate(top_users, 1):
                # Get details safely
                details = user_details.get(user_id, {})
                fname = details.get('first_name', 'Unknown')
                uname = details.get('username')

                # Create a clickable link to the user's profile
                if uname:
                    user_link = f'<a href="https://t.me/{uname}">{fname}</a>'
                else:
                    user_link = f'<a href="tg://user?id={user_id}">{fname}</a>'

                # Rank Medal
                medal = "🥇" if index == 1 else ("🥈" if index == 2 else ("🥉" if index == 3 else f"{index}."))

                list_text += f"{medal} {user_link} ➛ <b>{count} 💎</b>\n"

            footer = (
                "━━━━━━━━━━━━━━━━━━━━━\n"
                "🛠️ 𝗗𝗲𝘃 ➛ <a href='https://t.me/leiamarketcc'>メ𝗔𝗟𝗟𝗨𝗦</a>"
            )
            
            text = header + list_text + footer

        # 2. Edit the original message with the result
        await status_msg.edit_text(text, parse_mode="HTML", disable_web_page_preview=True)

    except Exception as e:
        logging.error(f"Error in /stats command: {e}")
        await status_msg.edit_text("❌ <b>Error fetching stats.</b>", parse_mode="HTML")
