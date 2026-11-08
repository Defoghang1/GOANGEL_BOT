import logging
import os
from datetime import datetime, timedelta
from config import ADMIN_ID, BANNED_FILE, SECURITY_STRIKES_FILE, AUDIT_LOG
from telegram_api import load_json, save_json, send_message

def log_admin_action(action, details=""):
    with open(AUDIT_LOG, "a", encoding="utf-8") as f:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        f.write(f"[{timestamp}] ADMIN (ID:{ADMIN_ID}) - {action} : {details}\n")

def alert_unauthorized(update, command, sender_id, username):
    alert_msg = f"🚨 <b>ALERTE SÉCURITÉ</b> 🚨\nTentative non autorisée.\nCommande : <code>{command}</code>\nUtilisateur : @{username} (ID: <code>{sender_id}</code>)"
    send_message(ADMIN_ID, alert_msg)

def is_secure_admin(update, notif_channel):
    sender_id, chat_id = None, None
    if "message" in update:
        sender_id = update["message"].get("from", {}).get("id")
        chat_id = update["message"]["chat"]["id"]
    elif "callback_query" in update:
        sender_id = update["callback_query"]["from"]["id"]
        chat_id = update["callback_query"]["message"]["chat"]["id"]
    if sender_id is None: return False
    return (sender_id == ADMIN_ID) and (chat_id == ADMIN_ID or str(chat_id) == str(notif_channel))

def check_ban(chat_id):
    banned_users = load_json(BANNED_FILE)
    if str(chat_id) in banned_users:
        ban_until_str = banned_users[str(chat_id)]
        ban_until = datetime.strptime(ban_until_str, "%Y-%m-%d %H:%M:%S")
        if datetime.now() > ban_until:
            del banned_users[str(chat_id)]
            save_json(BANNED_FILE, banned_users)
            return False, 0
        else:
            delta = ban_until - datetime.now()
            return True, int(delta.total_seconds() // 3600) + 1
    return False, 0

def handle_admin_security(update, cmd, notif_channel):
    if not is_secure_admin(update, notif_channel):
        sender_id = update["message"]["from"]["id"]
        username = update["message"]["from"].get("username", "Sans pseudo")
        strikes = load_json(SECURITY_STRIKES_FILE)
        strikes[str(sender_id)] = strikes.get(str(sender_id), 0) + 1
        save_json(SECURITY_STRIKES_FILE, strikes)
        strike_count = strikes[str(sender_id)]
        if strike_count >= 3:
            banned = load_json(BANNED_FILE)
            banned[str(sender_id)] = (datetime.now() + timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
            save_json(BANNED_FILE, banned)
            send_message(update["message"]["chat"]["id"], "🚫 <b>BANNI 3 JOURS.</b>")
        else:
            send_message(update["message"]["chat"]["id"], f"⛔ <b>Accès refusé.</b> ({strike_count}/3)")
        alert_unauthorized(update, cmd, sender_id, username)
        return False
    return True
