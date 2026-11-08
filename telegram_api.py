import json
import os
import logging
import requests
from typing import Any, Dict, List, Optional, Union

from config import (
    BASE_URL,
    ADMIN_ID,
    PUBLIC_COMMANDS,
    ADMIN_COMMANDS,
    STATE_FILE,
    ORDERS_FILE,
    USERS_FILE,
    BANNED_FILE,
    WARNINGS_FILE,
    SECURITY_STRIKES_FILE,
    LINKS_FILE,
    CONFIG_FILE,
    AUDIT_LOG,
    PROOFS_DIR,
)

logger = logging.getLogger(__name__)


def load_json(file: str) -> Dict[str, Any]:
    if not os.path.exists(file):
        return {}
    try:
        with open(file, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            return data
        return {}
    except (OSError, json.JSONDecodeError) as exc:
        logger.error("Erreur lecture %s : %s", file, exc)
        return {}


def save_json(file: str, data: Any) -> bool:
    tmp_file = f"{file}.tmp"
    try:
        with open(tmp_file, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=4, ensure_ascii=False)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_file, file)
        return True
    except (OSError, TypeError, ValueError) as exc:
        logger.error("Erreur écriture %s : %s", file, exc)
        if os.path.exists(tmp_file):
            try:
                os.remove(tmp_file)
            except OSError:
                pass
        return False


def _post(method: str, payload: Dict[str, Any], timeout: int = 15) -> Optional[Dict[str, Any]]:
    url = f"{BASE_URL}/{method}"
    try:
        response = requests.post(url, json=payload, timeout=timeout)
    except requests.exceptions.Timeout:
        logger.warning("Timeout sur %s", method)
        return None
    except requests.exceptions.RequestException as exc:
        logger.error("Erreur réseau sur %s : %s", method, exc)
        return None

    if response.status_code != 200:
        logger.error("Réponse HTTP %s sur %s : %s", response.status_code, method, response.text[:500])
        return None

    try:
        data = response.json()
    except ValueError as exc:
        logger.error("Réponse non JSON sur %s : %s", method, exc)
        return None

    if not data.get("ok", False):
        logger.error("Telegram a renvoyé une erreur sur %s : %s", method, data.get("description", "inconnu"))
        return None

    return data.get("result")


def send_message(chat_id: Union[int, str], text: str, reply_markup: Optional[Dict[str, Any]] = None, parse_mode: str = "HTML") -> Optional[int]:
    if not text or not str(text).strip():
        logger.warning("Tentative d'envoi d'un message vide à %s", chat_id)
        return None
    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    result = _post("sendMessage", payload)
    if result is None:
        return None
    return result.get("message_id")


def edit_message(chat_id: Union[int, str], message_id: int, text: str, reply_markup: Optional[Dict[str, Any]] = None, parse_mode: str = "HTML") -> bool:
    if not isinstance(message_id, int) or message_id <= 0:
        logger.warning("message_id invalide pour edit_message : %s", message_id)
        return False
    if not text or not str(text).strip():
        logger.warning("Tentative d'édition avec un texte vide pour le message %s", message_id)
        return False
    payload: Dict[str, Any] = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    result = _post("editMessageText", payload)
    if result is None:
        return False
    return True


def delete_message(chat_id: Union[int, str], message_id: int) -> bool:
    if not isinstance(message_id, int) or message_id <= 0:
        logger.warning("message_id invalide pour delete_message : %s", message_id)
        return False
    payload: Dict[str, Any] = {"chat_id": chat_id, "message_id": message_id}
    result = _post("deleteMessage", payload)
    return result is not None


def send_photo(chat_id: Union[int, str], photo_path: str, caption: str = "", parse_mode: str = "HTML") -> Optional[int]:
    if not os.path.exists(photo_path):
        logger.warning("Fichier photo introuvable : %s", photo_path)
        return None
    try:
        with open(photo_path, "rb") as photo:
            files = {"photo": photo}
            payload = {
                "chat_id": chat_id,
                "caption": caption,
                "parse_mode": parse_mode,
            }
            response = requests.post(f"{BASE_URL}/sendPhoto", data=payload, files=files, timeout=30)
    except requests.exceptions.RequestException as exc:
        logger.error("Erreur envoi photo à %s : %s", chat_id, exc)
        return None

    if response.status_code != 200:
        logger.error("Réponse HTTP %s sur sendPhoto : %s", response.status_code, response.text[:500])
        return None

    try:
        data = response.json()
    except ValueError:
        return None

    if not data.get("ok", False):
        logger.error("Telegram a refusé la photo : %s", data.get("description", "inconnu"))
        return None

    result = data.get("result", {})
    return result.get("message_id")


def answer_callback_query(callback_query_id: str, text: Optional[str] = None, show_alert: bool = False) -> bool:
    if not callback_query_id:
        return False
    payload: Dict[str, Any] = {
        "callback_query_id": callback_query_id,
        "show_alert": bool(show_alert),
    }
    if text is not None:
        payload["text"] = text
    result = _post("answerCallbackQuery", payload)
    return result is not None


def set_public_commands() -> bool:
    payload: Dict[str, Any] = {"commands": PUBLIC_COMMANDS}
    result = _post("setMyCommands", payload)
    if result is None:
        logger.error("Impossible de configurer les commandes publiques.")
        return False
    logger.info("Commandes publiques configurées avec succès.")
    return True


def set_admin_commands() -> bool:
    payload: Dict[str, Any] = {
        "commands": ADMIN_COMMANDS,
        "scope": {"type": "chat", "chat_id": ADMIN_ID},
    }
    result = _post("setMyCommands", payload)
    if result is None:
        logger.error("Impossible de configurer les commandes admin.")
        return False
    logger.info("Commandes admin configurées avec succès pour l'ID %s.", ADMIN_ID)
    return True


def delete_commands(scope: Optional[Dict[str, Any]] = None) -> bool:
    payload: Dict[str, Any] = {}
    if scope is not None:
        payload["scope"] = scope
    result = _post("deleteMyCommands", payload)
    return result is not None


def get_updates(offset: int = 0, timeout: int = 10) -> Optional[List[Dict[str, Any]]]:
    payload: Dict[str, Any] = {
        "offset": offset,
        "timeout": timeout,
        "allowed_updates": ["message", "callback_query"],
    }
    try:
        response = requests.get(f"{BASE_URL}/getUpdates", params=payload, timeout=timeout + 10)
    except requests.exceptions.Timeout:
        return None
    except requests.exceptions.RequestException as exc:
        logger.error("Erreur réseau getUpdates : %s", exc)
        return None

    if response.status_code != 200:
        logger.error("Réponse HTTP %s sur getUpdates : %s", response.status_code, response.text[:500])
        return None

    try:
        data = response.json()
    except ValueError:
        return None

    if not data.get("ok", False):
        logger.error("Telegram a refusé getUpdates : %s", data.get("description", "inconnu"))
        return None

    result = data.get("result", [])
    if not isinstance(result, list):
        return None
    return result


def get_file(file_id: str) -> Optional[str]:
    if not file_id:
        return None
    result = _post("getFile", {"file_id": file_id})
    if result is None:
        return None
    file_path = result.get("file_path")
    if not isinstance(file_path, str) or not file_path:
        return None
    return file_path


def download_file(file_path: str, destination: str) -> bool:
    if not file_path or not destination:
        return False
    url = f"https://api.telegram.org/file/bot{BASE_URL.split('/bot')[-1]}/{file_path}"
    try:
        response = requests.get(url, timeout=30, stream=True)
    except requests.exceptions.RequestException as exc:
        logger.error("Erreur téléchargement fichier Telegram : %s", exc)
        return False

    if response.status_code != 200:
        logger.error("Réponse HTTP %s lors du téléchargement du fichier.", response.status_code)
        return False

    tmp_destination = f"{destination}.tmp"
    try:
        with open(tmp_destination, "wb") as fh:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    fh.write(chunk)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp_destination, destination)
        return True
    except OSError as exc:
        logger.error("Erreur écriture fichier téléchargé : %s", exc)
        if os.path.exists(tmp_destination):
            try:
                os.remove(tmp_destination)
            except OSError:
                pass
        return False


def delete_all_commands() -> None:
    delete_commands()
    delete_commands(scope={"type": "chat", "chat_id": ADMIN_ID})
    delete_commands(scope={"type": "all_private_chats"})


def initialize_menus() -> None:
    logger.info("Nettoyage des anciennes commandes...")
    delete_all_commands()
    
    logger.info("Configuration des commandes publiques...")
    set_public_commands()
    
    logger.info("Configuration des commandes administrateur...")
    set_admin_commands()
