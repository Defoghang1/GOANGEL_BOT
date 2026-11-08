import os
import sys
import time
import signal
import logging
import traceback
from datetime import datetime
from typing import Any, Dict, List, Optional

from config import (
    TOKEN,
    ADMIN_ID,
    BASE_URL,
    MAX_RUNTIME,
    STATE_FILE,
    ORDERS_FILE,
    USERS_FILE,
    LINKS_FILE,
    CONFIG_FILE,
    WARNINGS_FILE,
    SECURITY_STRIKES_FILE,
    DEFAULT_NOTIF_CHANNEL,
    PROOFS_DIR,
    PACKS,
    PUBLIC_COMMANDS,
    ADMIN_COMMANDS,
    is_admin_command,
)
from telegram_api import (
    load_json,
    save_json,
    send_message,
    edit_message,
    delete_message,
    send_photo,
    get_updates,
    initialize_menus,
    answer_callback_query,
)
from handlers import process_update

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("goangel.bot")

_SHUTDOWN_REQUESTED: bool = False


def _handle_signal(signum: int, frame: Any) -> None:
    global _SHUTDOWN_REQUESTED
    _SHUTDOWN_REQUESTED = True
    logger.info("Signal %s reçu, arrêt demandé.", signum)


def _install_signal_handlers() -> None:
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(sig, _handle_signal)
        except (ValueError, OSError):
            pass


def _initialize_persistent_files() -> None:
    os.makedirs(PROOFS_DIR, exist_ok=True)
    defaults: Dict[str, Any] = {
        LINKS_FILE: {
            "starter": "https://drive.google.com/votre-lien-starter",
            "pro": "https://drive.google.com/votre-lien-pro",
            "elite": "https://drive.google.com/votre-lien-elite",
        },
        CONFIG_FILE: {"notification_channel": DEFAULT_NOTIF_CHANNEL},
        WARNINGS_FILE: {},
        SECURITY_STRIKES_FILE: {},
        STATE_FILE: {"offset": 0},
        ORDERS_FILE: {},
        USERS_FILE: [],
    }
    for file_path, default_value in defaults.items():
        if not os.path.exists(file_path):
            success = save_json(file_path, default_value)
            if success:
                logger.info("Fichier initialisé : %s", file_path)
            else:
                logger.error("Impossible d'initialiser le fichier : %s", file_path)


def _validate_startup_configuration() -> bool:
    if not TOKEN or not isinstance(TOKEN, str) or ":" not in TOKEN:
        logger.critical("Token Telegram invalide ou manquant.")
        return False
    if not isinstance(ADMIN_ID, int) or ADMIN_ID <= 0:
        logger.critical("ADMIN_ID invalide.")
        return False
    if not PACKS:
        logger.critical("Aucun pack configuré.")
        return False
    for key, pack in PACKS.items():
        if not isinstance(pack.get("name"), str):
            logger.critical("Pack %s : nom manquant.", key)
            return False
        if not isinstance(pack.get("price_num"), int) or pack["price_num"] <= 0:
            logger.critical("Pack %s : prix invalide.", key)
            return False
        if not isinstance(pack.get("features"), list):
            logger.critical("Pack %s : liste de fonctionnalités manquante.", key)
            return False
    return True


def _restore_menus() -> None:
    logger.info("Initialisation des menus Telegram...")
    try:
        initialize_menus()
    except Exception as exc:
        logger.error("Erreur lors de l'initialisation des menus : %s", exc)
        logger.debug(traceback.format_exc())


def _load_runtime_state() -> Dict[str, Any]:
    state = load_json(STATE_FILE)
    if not isinstance(state, dict):
        state = {"offset": 0}
    if "offset" not in state:
        state["offset"] = 0
    return state


def _load_runtime_orders() -> Dict[str, Any]:
    orders = load_json(ORDERS_FILE)
    if not isinstance(orders, dict):
        orders = {}
    return orders


def _load_runtime_users() -> List[int]:
    users = load_json(USERS_FILE)
    if not isinstance(users, list):
        users = []
    return users


def _persist_state(state: Dict[str, Any]) -> None:
    save_json(STATE_FILE, state)


def _persist_orders(orders: Dict[str, Any]) -> None:
    save_json(ORDERS_FILE, orders)


def _persist_users(users: List[int]) -> None:
    save_json(USERS_FILE, users)


def _process_single_update(
    update: Dict[str, Any],
    orders: Dict[str, Any],
    accepted_users: List[int],
) -> None:
    try:
        process_update(update, orders, accepted_users)
    except Exception as exc:
        logger.error("Erreur traitement update : %s", exc)
        logger.debug(traceback.format_exc())
        try:
            chat_id = None
            if "message" in update:
                chat_id = update["message"].get("chat", {}).get("id")
            elif "callback_query" in update:
                chat_id = update["callback_query"].get("message", {}).get("chat", {}).get("id")
            if chat_id is not None:
                send_message(chat_id, "⚠️ Une erreur interne est survenue. Veuillez réessayer.")
        except Exception:
            pass


def _run_polling_loop(
    state: Dict[str, Any],
    orders: Dict[str, Any],
    accepted_users: List[int],
    start_time: float,
) -> None:
    offset = int(state.get("offset", 0))
    while not _SHUTDOWN_REQUESTED and (time.time() - start_time) < MAX_RUNTIME:
        try:
            updates = get_updates(offset=offset, timeout=10)
            if updates is None:
                time.sleep(2)
                continue
            if not updates:
                continue
            for update in updates:
                try:
                    _process_single_update(update, orders, accepted_users)
                    offset = int(update.get("update_id", offset)) + 1
                    state["offset"] = offset
                    _persist_state(state)
                    _persist_orders(orders)
                    _persist_users(accepted_users)
                except Exception as exc:
                    logger.error("Erreur update individuelle : %s", exc)
                    logger.debug(traceback.format_exc())
        except KeyboardInterrupt:
            logger.info("Interruption clavier détectée.")
            break
        except Exception as exc:
            logger.error("Erreur boucle principale : %s", exc)
            logger.debug(traceback.format_exc())
            time.sleep(3)


def main() -> int:
    global _SHUTDOWN_REQUESTED
    _SHUTDOWN_REQUESTED = False
    _install_signal_handlers()

    if not _validate_startup_configuration():
        logger.critical("Configuration invalide, arrêt du bot.")
        return 1

    _initialize_persistent_files()
    _restore_menus()

    state = _load_runtime_state()
    orders = _load_runtime_orders()
    accepted_users = _load_runtime_users()

    start_time = time.time()
    logger.info("Bot démarré. Durée maximale : %s secondes.", MAX_RUNTIME)

    try:
        _run_polling_loop(state, orders, accepted_users, start_time)
    except Exception as exc:
        logger.critical("Erreur fatale : %s", exc)
        logger.debug(traceback.format_exc())
        return 1
    finally:
        _persist_state(state)
        _persist_orders(orders)
        _persist_users(accepted_users)
        logger.info("Bot arrêté proprement.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
