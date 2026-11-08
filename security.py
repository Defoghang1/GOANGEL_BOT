import os
import json
import time
import logging
import hashlib
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import fcntl
    _FCNTL_AVAILABLE = True
except ImportError:
    _FCNTL_AVAILABLE = False

from config import (
    ADMIN_ID,
    BANNED_FILE,
    SECURITY_STRIKES_FILE,
    WARNINGS_FILE,
    AUDIT_LOG,
    CONFIG_FILE,
    DEFAULT_NOTIF_CHANNEL,
)
from telegram_api import load_json, save_json, send_message

logger = logging.getLogger(__name__)

_SECURITY_LOCK_FILE = ".security.lock"
_RATE_LIMIT_WINDOW_SECONDS = 60
_RATE_LIMIT_MAX_REQUESTS = 5
_RATE_LIMIT_STORE: Dict[str, List[float]] = {}

_ADMIN_COMMAND_NAMES: frozenset = frozenset({
    "setchannel", "setlien", "liens", "preuve", "delete_preuve",
    "confirm", "false", "block", "unlock", "orders",
})


def _acquire_lock(lock_file: str) -> Optional[int]:
    if not _FCNTL_AVAILABLE:
        return None
    try:
        fd = os.open(lock_file, os.O_CREAT | os.O_RDWR)
        fcntl.flock(fd, fcntl.LOCK_EX)
        return fd
    except OSError as exc:
        logger.error("Impossible d'acquérir le verrou fichier : %s", exc)
        return None


def _release_lock(fd: Optional[int]) -> None:
    if fd is not None and _FCNTL_AVAILABLE:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
        except OSError as exc:
            logger.error("Erreur libération verrou : %s", exc)


def save_json_locked(file_path: str, data: Any) -> bool:
    fd = _acquire_lock(_SECURITY_LOCK_FILE)
    try:
        return save_json(file_path, data)
    finally:
        _release_lock(fd)


def log_admin_action(action: str, details: str = "") -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] ADMIN (ID:{ADMIN_ID}) - {action} : {details}\n"
    try:
        with open(AUDIT_LOG, "a", encoding="utf-8") as fh:
            fh.write(log_line)
            fh.flush()
            os.fsync(fh.fileno())
    except OSError as exc:
        logger.error("Impossible d'écrire dans le journal d'audit : %s", exc)


def _hash_identifier(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _rate_limit_check(key: str) -> bool:
    now = time.time()
    window_start = now - _RATE_LIMIT_WINDOW_SECONDS
    timestamps = _RATE_LIMIT_STORE.get(key, [])
    timestamps = [ts for ts in timestamps if ts > window_start]
    if len(timestamps) >= _RATE_LIMIT_MAX_REQUESTS:
        _RATE_LIMIT_STORE[key] = timestamps
        return False
    timestamps.append(now)
    _RATE_LIMIT_STORE[key] = timestamps
    return True


def _extract_sender_info(update: Dict[str, Any]) -> Tuple[Optional[int], Optional[int], str]:
    sender_id: Optional[int] = None
    chat_id: Optional[int] = None
    username: str = "Sans pseudo"
    if "message" in update and isinstance(update["message"], dict):
        msg = update["message"]
        from_user = msg.get("from", {})
        if isinstance(from_user, dict):
            sender_id = from_user.get("id")
            username = from_user.get("username", "Sans pseudo")
        chat = msg.get("chat", {})
        if isinstance(chat, dict):
            chat_id = chat.get("id")
    elif "callback_query" in update and isinstance(update["callback_query"], dict):
        cb = update["callback_query"]
        from_user = cb.get("from", {})
        if isinstance(from_user, dict):
            sender_id = from_user.get("id")
            username = from_user.get("username", "Sans pseudo")
        msg = cb.get("message", {})
        if isinstance(msg, dict):
            chat = msg.get("chat", {})
            if isinstance(chat, dict):
                chat_id = chat.get("id")
    return sender_id, chat_id, username


def _validate_update_structure(update: Dict[str, Any]) -> bool:
    if not isinstance(update, dict):
        return False
    if "message" not in update and "callback_query" not in update:
        return False
    return True


def alert_unauthorized(
    update: Dict[str, Any],
    command: str,
    sender_id: int,
    username: str,
) -> None:
    if not _validate_update_structure(update):
        return
    alert_msg = (
        f"🚨 <b>ALERTE SÉCURITÉ</b> 🚨\n"
        f"Tentative non autorisée.\n"
        f"Commande : <code>{command}</code>\n"
        f"Utilisateur : @{username} (ID: <code>{sender_id}</code>)"
    )
    
    # On récupère le canal de notification configuré
    config = load_json(CONFIG_FILE)
    notif_channel = config.get("notification_channel", DEFAULT_NOTIF_CHANNEL)
    
    # Envoi au canal prioritaire
    sent_to_channel = send_message(notif_channel, alert_msg)
    
    # Si le canal échoue ou n'est pas l'admin, on sécurise en privé
    if not sent_to_channel and str(notif_channel) != str(ADMIN_ID):
        send_message(ADMIN_ID, alert_msg)
        
    logger.warning(
        "Tentative non autorisée : commande=%s sender_id=%s username=%s",
        command,
        sender_id,
        username,
    )


def is_secure_admin(update: Dict[str, Any], notif_channel: Union[int, str]) -> bool:
    if not _validate_update_structure(update):
        return False
    sender_id, chat_id, _ = _extract_sender_info(update)
    if sender_id is None or chat_id is None:
        return False
    if sender_id != ADMIN_ID:
        return False
    if chat_id == ADMIN_ID:
        return True
    if str(chat_id) == str(notif_channel):
        return True
    return False


def check_ban(chat_id: int) -> Tuple[bool, int]:
    banned_users = load_json(BANNED_FILE)
    if not isinstance(banned_users, dict):
        return False, 0
    key = str(chat_id)
    if key not in banned_users:
        return False, 0
    ban_until_str = banned_users[key]
    try:
        ban_until = datetime.strptime(ban_until_str, "%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError):
        del banned_users[key]
        save_json_locked(BANNED_FILE, banned_users)
        return False, 0
    now = datetime.now()
    if now >= ban_until:
        del banned_users[key]
        save_json_locked(BANNED_FILE, banned_users)
        return False, 0
    delta = ban_until - now
    hours_left = int(delta.total_seconds() // 3600) + 1
    return True, hours_left


def handle_admin_security(
    update: Dict[str, Any],
    cmd: str,
    notif_channel: Union[int, str],
) -> bool:
    if not _validate_update_structure(update):
        return False
    sender_id, chat_id, username = _extract_sender_info(update)
    if sender_id is None or chat_id is None:
        return False

    rate_key = f"admin:{sender_id}:{cmd}"
    if not _rate_limit_check(rate_key):
        logger.warning("Rate limit atteint pour %s sur %s", sender_id, cmd)
        send_message(chat_id, "⏳ Trop de tentatives. Veuillez patienter une minute.")
        return False

    if not is_secure_admin(update, notif_channel):
        strikes = load_json(SECURITY_STRIKES_FILE)
        if not isinstance(strikes, dict):
            strikes = {}
        key = str(sender_id)
        strikes[key] = strikes.get(key, 0) + 1
        strike_count = strikes[key]
        save_json_locked(SECURITY_STRIKES_FILE, strikes)

        if strike_count >= 3:
            banned = load_json(BANNED_FILE)
            if not isinstance(banned, dict):
                banned = {}
            ban_until = datetime.now() + timedelta(days=3)
            banned[key] = ban_until.strftime("%Y-%m-%d %H:%M:%S")
            save_json_locked(BANNED_FILE, banned)
            send_message(
                chat_id,
                "🚫 <b>BANNI 3 JOURS.</b>\n"
                "Tentative d'accès non autorisée répétée.",
            )
            logger.warning(
                "Utilisateur %s banni 3 jours après 3 tentatives sur %s.",
                sender_id,
                cmd,
            )
        else:
            send_message(
                chat_id,
                f"⛔ <b>Accès refusé.</b>\n"
                f"Avertissement {strike_count}/3. Toute tentative est signalée.",
            )
        alert_unauthorized(update, cmd, sender_id, username)
        return False

    log_admin_action("COMMAND_EXECUTED", f"{cmd} par {sender_id}")
    return True


def get_security_status(chat_id: int) -> Dict[str, Any]:
    is_banned, hours_left = check_ban(chat_id)
    strikes = load_json(SECURITY_STRIKES_FILE)
    if not isinstance(strikes, dict):
        strikes = {}
    strike_count = strikes.get(str(chat_id), 0)
    warnings = load_json(WARNINGS_FILE)
    if not isinstance(warnings, dict):
        warnings = {}
    warning_count = warnings.get(str(chat_id), 0)
    return {
        "is_banned": is_banned,
        "hours_left": hours_left,
        "strikes": strike_count,
        "warnings": warning_count,
    }
