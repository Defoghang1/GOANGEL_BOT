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
    ADMIN_COMMAND_NAMES,
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


_PURGE_SCOPES: List[Dict[str, Any]] = [
    {"type": "default"},
    {"type": "all_private_chats"},
    {"type": "all_group_chats"},
    {"type": "all_chat_administrators"},
]

# None = sans langue ; les menus définis avec un language_code (ex. via BotFather)
# prennent le pas sur le menu par défaut, il faut donc les purger aussi.
_PURGE_LANGUAGES: List[Optional[str]] = [
    None, "fr", "en", "es", "pt", "ar", "ru", "de", "it", "tr", "zh", "hi", "id", "sw",
]


def _scoped_payload(scope: Dict[str, Any], language_code: Optional[str] = None) -> Dict[str, Any]:
    payload: Dict[str, Any] = {"scope": scope}
    if language_code:
        payload["language_code"] = language_code
    return payload


def set_public_commands() -> bool:
    """Menu visible par TOUS les utilisateurs (scope par défaut) : commandes publiques uniquement."""
    commands = [c for c in PUBLIC_COMMANDS if c["command"] not in ADMIN_COMMAND_NAMES]
    payload: Dict[str, Any] = {"commands": commands, "scope": {"type": "default"}}
    result = _post("setMyCommands", payload)
    if result is None:
        logger.error("Impossible de configurer les commandes publiques.")
        return False
    logger.info("Commandes publiques configurées avec succès.")
    return True


def set_admin_commands() -> bool:
    """Menu complet visible UNIQUEMENT dans le chat privé de l'admin."""
    payload: Dict[str, Any] = {
        "commands": ADMIN_COMMANDS,
        "scope": {"type": "chat", "chat_id": ADMIN_ID},
    }
    result = _post("setMyCommands", payload)
    if result is None:
        logger.error(
            "Impossible de configurer les commandes admin (l'admin a-t-il déjà envoyé /start au bot ?)."
        )
        return False
    logger.info("Commandes admin configurées avec succès pour l'ID %s.", ADMIN_ID)
    return True


def delete_commands(scope: Optional[Dict[str, Any]] = None, language_code: Optional[str] = None) -> bool:
    payload: Dict[str, Any] = {}
    if scope is not None:
        payload["scope"] = scope
    if language_code:
        payload["language_code"] = language_code
    result = _post("deleteMyCommands", payload)
    return result is not None


def purge_all_commands() -> None:
    """Supprime tout menu résiduel (tous scopes publics x langues) avant reconstruction."""
    for scope in _PURGE_SCOPES:
        for lang in _PURGE_LANGUAGES:
            delete_commands(scope, lang)
    # Menu admin résiduel éventuel
    delete_commands({"type": "chat", "chat_id": ADMIN_ID})


def get_commands(scope: Dict[str, Any], language_code: Optional[str] = None) -> Optional[List[Dict[str, Any]]]:
    result = _post("getMyCommands", _scoped_payload(scope, language_code))
    if not isinstance(result, list):
        return None
    return result


def verify_menus() -> bool:
    """Retourne True si AUCUNE commande admin n'est visible hors du chat admin."""
    clean = True
    for scope in _PURGE_SCOPES:
        for lang in _PURGE_LANGUAGES:
            commands = get_commands(scope, lang)
            if not commands:
                continue
            leaked = sorted(
                c.get("command", "") for c in commands if c.get("command") in ADMIN_COMMAND_NAMES
            )
            if leaked:
                clean = False
                logger.critical(
                    "FUITE : commandes admin %s visibles (scope=%s, langue=%s).",
                    leaked, scope.get("type"), lang or "défaut",
                )
    return clean


def initialize_menus() -> bool:
    for attempt in (1, 2):
        purge_all_commands()
        set_public_commands()
        set_admin_commands()
        if verify_menus():
            logger.info("Vérification des menus OK : aucune commande admin visible aux non-admins.")
            return True
        logger.error("Menus non conformes (tentative %s/2), nouvelle purge.", attempt)
    logger.critical("Impossible de masquer les commandes admin aux utilisateurs.")
    return False


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
