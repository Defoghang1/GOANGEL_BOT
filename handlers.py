import os
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from config import (
    PACKS,
    ORANGE_MONEY,
    MTN_MONEY,
    TELEGRAM_CONTACT,
    LINKS_FILE,
    WARNINGS_FILE,
    BANNED_FILE,
    CONFIG_FILE,
    PROOFS_DIR,
    ORDERS_FILE,
    USERS_FILE,
    DEFAULT_NOTIF_CHANNEL,
    ADMIN_ID,
    TOKEN,
    BASE_URL,
    is_admin_command,
)
from telegram_api import (
    load_json,
    save_json,
    send_message,
    edit_message,
    delete_message,
    send_photo,
    get_file,
    download_file,
)
from security import handle_admin_security, check_ban, log_admin_action
from texts import (
    get_main_menu_text,
    get_main_menu_keyboard,
    get_consent_text,
    get_consent_keyboard,
    get_prices_text,
    get_prices_keyboard,
    get_payment_method_text,
    get_payment_method_keyboard,
    get_recap_text,
    get_recap_keyboard,
    get_ussd_text,
    get_ussd_keyboard,
    get_waiting_text,
    get_waiting_keyboard,
    get_success_text,
    get_success_keyboard,
    get_rejected_text,
    get_links_report_text,
    get_security_text,
)

logger = logging.getLogger(__name__)

user_states: Dict[int, str] = {}


def _safe_get(dictionary: Dict[str, Any], key: str, default: Any = None) -> Any:
    if not isinstance(dictionary, dict):
        return default
    return dictionary.get(key, default)


def _parse_command(text: str) -> Tuple[str, List[str]]:
    if not isinstance(text, str):
        return "", []
    parts = text.strip().split()
    if not parts:
        return "", []
    command = parts[0].lower().split("@", 1)[0]
    args = parts[1:]
    return command, args


def _format_phone_number(number: str) -> str:
    digits = "".join(filter(str.isdigit, str(number)))
    if digits.startswith("237"):
        digits = digits[3:]
    return digits[-9:] if len(digits) >= 9 else digits


def _generate_ussd_code(provider: str, amount: int) -> str:
    if provider == "mtn":
        number = _format_phone_number(MTN_MONEY)
        return f"*126*1*1*{number}*{amount}#"
    number = _format_phone_number(ORANGE_MONEY)
    return f"#150*1*1*{number}*1*{amount}*2#"


def _get_current_notification_channel() -> Any:
    config = load_json(CONFIG_FILE)
    return _safe_get(config, "notification_channel", DEFAULT_NOTIF_CHANNEL)


def _handle_admin_command(
    command: str,
    args: List[str],
    update: Dict[str, Any],
    orders: Dict[str, Any],
    notif_channel: Any,
) -> bool:
    if not handle_admin_security(update, command, notif_channel):
        return False

    message = update.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    if chat_id is None:
        return False

    try:
        if command == "/setchannel":
            if not args:
                send_message(chat_id, "Format : <code>/setchannel &lt;id_du_canal&gt;</code>")
                return True
            new_channel = args[0]
            config = load_json(CONFIG_FILE)
            config["notification_channel"] = new_channel
            save_json(CONFIG_FILE, config)
            send_message(chat_id, f"✅ Canal configuré : <code>{new_channel}</code>")
            log_admin_action("SET_CHANNEL", new_channel)
            return True

        if command == "/confirm":
            if not args:
                send_message(chat_id, "Format : <code>/confirm &lt;ORD-xxxx&gt;</code>")
                return True
            order_id = args[0]
            if order_id not in orders:
                send_message(chat_id, f"❌ Commande <code>{order_id}</code> introuvable.")
                return True
            order = orders[order_id]
            if order.get("status") == "PAID":
                send_message(chat_id, f"⚠️ La commande <code>{order_id}</code> est déjà payée.")
                return True
            order["status"] = "PAID"
            order["paid_at"] = str(datetime.now())
            save_json(ORDERS_FILE, orders)
            buyer_id = order["user_id"]
            pack_key = order["pack"]
            pack_name = PACKS.get(pack_key, {}).get("name", pack_key)
            success_text = get_success_text(pack_name)
            success_kb = get_success_keyboard(order_id)
            status_msg_id = order.get("status_msg_id")
            if status_msg_id:
                edit_message(buyer_id, status_msg_id, success_text, success_kb)
            else:
                send_message(buyer_id, success_text, success_kb)
            send_message(chat_id, f"✅ Commande <code>{order_id}</code> validée.")
            log_admin_action("VALIDATE_ORDER", order_id)
            return True

        if command == "/false":
            if not args:
                send_message(chat_id, "Format : <code>/false &lt;ORD-xxxx&gt;</code>")
                return True
            order_id = args[0]
            if order_id not in orders:
                send_message(chat_id, f"❌ Commande <code>{order_id}</code> introuvable.")
                return True
            order = orders[order_id]
            if order.get("status") == "PAID":
                send_message(chat_id, f"⚠️ La commande <code>{order_id}</code> est déjà payée.")
                return True
            order["status"] = "REJECTED"
            save_json(ORDERS_FILE, orders)
            buyer_id = order["user_id"]
            warnings = load_json(WARNINGS_FILE)
            warnings[str(buyer_id)] = warnings.get(str(buyer_id), 0) + 1
            save_json(WARNINGS_FILE, warnings)
            warning_count = warnings[str(buyer_id)]
            if warning_count >= 3:
                banned = load_json(BANNED_FILE)
                ban_until = datetime.now() + timedelta(days=3)
                banned[str(buyer_id)] = ban_until.strftime("%Y-%m-%d %H:%M:%S")
                save_json(BANNED_FILE, banned)
                send_message(buyer_id, "🚫 <b>BANNI 3 JOURS.</b>\nFaux paiement répété.")
                send_message(chat_id, f"🚫 Client {buyer_id} banni 3 jours (3 faux paiements).")
                log_admin_action("BAN_USER", f"{buyer_id} via /false")
            else:
                send_message(buyer_id, get_rejected_text())
                send_message(chat_id, f"⚠️ Avertissement {warning_count}/3 envoyé au client {buyer_id}.")
            log_admin_action("REJECT_ORDER", order_id)
            return True

        if command == "/block":
            if not args:
                send_message(chat_id, "Format : <code>/block &lt;ID&gt;</code>")
                return True
            target_id = args[0]
            banned = load_json(BANNED_FILE)
            ban_until = datetime.now() + timedelta(days=3)
            banned[str(target_id)] = ban_until.strftime("%Y-%m-%d %H:%M:%S")
            save_json(BANNED_FILE, banned)
            send_message(chat_id, f"🚫 Utilisateur <code>{target_id}</code> bloqué 3 jours.")
            send_message(int(target_id), "🚫 Vous avez été bloqué par l'administrateur.")
            log_admin_action("BLOCK_USER", target_id)
            return True

        if command == "/unlock":
            if not args:
                send_message(chat_id, "Format : <code>/unlock &lt;ID&gt;</code>")
                return True
            target_id = args[0]
            banned = load_json(BANNED_FILE)
            if target_id in banned:
                del banned[target_id]
                save_json(BANNED_FILE, banned)
                send_message(chat_id, f"✅ Utilisateur <code>{target_id}</code> débloqué.")
                send_message(int(target_id), "✅ Votre accès a été rétabli.")
                log_admin_action("UNLOCK_USER", target_id)
            else:
                send_message(chat_id, "⚠️ Cet utilisateur n'est pas banni.")
            return True

        if command == "/preuve":
            user_states[chat_id] = "waiting_proof"
            send_message(chat_id, "📸 Envoyez l'image de preuve.")
            return True

        if command == "/delete_preuve":
            proof_path = os.path.join(PROOFS_DIR, "proof_1.jpg")
            if os.path.exists(proof_path):
                os.remove(proof_path)
                send_message(chat_id, "🗑️ Preuve supprimée.")
                log_admin_action("DELETE_PROOF")
            else:
                send_message(chat_id, "⚠️ Aucune preuve à supprimer.")
            return True

        if command == "/orders":
            pending = [
                f"{oid} ({order.get('pack', 'inconnu')})"
                for oid, order in orders.items()
                if order.get("status") == "PENDING"
            ]
            if pending:
                send_message(chat_id, "📋 <b>Commandes en attente :</b>\n" + "\n".join(pending))
            else:
                send_message(chat_id, "✅ Aucune commande en attente.")
            return True

        if command == "/setlien":
            if len(args) < 2:
                send_message(chat_id, "Format : <code>/setlien &lt;pack&gt; &lt;lien&gt;</code>")
                return True
            pack_key = args[0].lower()
            link = " ".join(args[1:])
            if pack_key not in PACKS:
                send_message(chat_id, "❌ Pack inconnu. Utilisez : starter, pro, ou elite.")
                return True
            links = load_json(LINKS_FILE)
            links[pack_key] = link
            save_json(LINKS_FILE, links)
            send_message(chat_id, f"✅ Lien du pack <b>{pack_key}</b> mis à jour.")
            log_admin_action("SET_LINK", f"{pack_key} -> {link}")
            return True

        if command == "/liens":
            links = load_json(LINKS_FILE)
            text = get_links_report_text(links)
            send_message(chat_id, text)
            return True

        return False

    except Exception as exc:
        logger.error("Erreur dans la gestion de la commande admin %s : %s", command, exc)
        send_message(chat_id, "⚠️ Une erreur interne est survenue.")
        return True


def _handle_public_command(
    command: str,
    args: List[str],
    update: Dict[str, Any],
    orders: Dict[str, Any],
    accepted_users: List[int],
) -> None:
    message = update.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    if chat_id is None:
        return

    try:
        if command == "/start":
            if chat_id in accepted_users:
                accepted_users.remove(chat_id)
                save_json(USERS_FILE, accepted_users)
            send_message(chat_id, get_consent_text(), get_consent_keyboard())
            return

        if command == "/tarifs":
            if chat_id in accepted_users:
                send_message(chat_id, get_prices_text(), get_prices_keyboard())
            else:
                send_message(chat_id, get_consent_text(), get_consent_keyboard())
            return

        if command == "/lien":
            if chat_id not in accepted_users:
                send_message(chat_id, get_consent_text(), get_consent_keyboard())
                return
            user_orders = [
                oid for oid, order in orders.items()
                if order.get("user_id") == chat_id and order.get("status") == "PAID"
            ]
            if not user_orders:
                send_message(chat_id, "⛔ Aucune commande validée à votre nom.")
                return
            latest_order = user_orders[-1]
            pack_key = orders[latest_order]["pack"]
            links = load_json(LINKS_FILE)
            link = links.get(pack_key, "Lien non configuré.")
            send_message(chat_id, f"✅ <b>Accès autorisé !</b>\n\nVoici votre lien de téléchargement :\n{link}")
            return

        if command == "/securite":
            send_message(chat_id, get_security_text())
            return

        if command == "/support":
            if chat_id in accepted_users:
                send_message(chat_id, f"📞 Contact : {TELEGRAM_CONTACT}")
            else:
                send_message(chat_id, get_consent_text(), get_consent_keyboard())
            return

        if command == "/myid":
            send_message(chat_id, f"🆔 <b>Votre ID Telegram :</b> <code>{chat_id}</code>")
            return

    except Exception as exc:
        logger.error("Erreur dans la gestion de la commande publique %s : %s", command, exc)


def _handle_callback_query(
    data: str,
    update: Dict[str, Any],
    orders: Dict[str, Any],
    accepted_users: List[int],
) -> None:
    callback = update.get("callback_query", {})
    chat_id = callback.get("message", {}).get("chat", {}).get("id")
    message_id = callback.get("message", {}).get("message_id")
    if chat_id is None or message_id is None:
        return

    try:
        if data == "accept_terms":
            if chat_id not in accepted_users:
                accepted_users.append(chat_id)
                save_json(USERS_FILE, accepted_users)
            edit_message(chat_id, message_id, get_main_menu_text(), get_main_menu_keyboard())
            return

        if data == "refuse_terms":
            banned = load_json(BANNED_FILE)
            ban_until = datetime.now() + timedelta(days=365)
            banned[str(chat_id)] = ban_until.strftime("%Y-%m-%d %H:%M:%S")
            save_json(BANNED_FILE, banned)
            edit_message(chat_id, message_id, "❌ Vous avez refusé les conditions. L'accès est bloqué.", None)
            log_admin_action("REFUSE_TERMS", str(chat_id))
            return

        if data == "show_prices":
            edit_message(chat_id, message_id, get_prices_text(), get_prices_keyboard())
            return

        if data == "back_to_menu":
            edit_message(chat_id, message_id, get_main_menu_text(), get_main_menu_keyboard())
            return

        if data == "show_proof":
            proof_path = os.path.join(PROOFS_DIR, "proof_1.jpg")
            if os.path.exists(proof_path):
                delete_message(chat_id, message_id)
                send_photo(chat_id, proof_path, "📸 <b>Preuve de gains récents</b>")
                send_message(chat_id, get_main_menu_text(), get_main_menu_keyboard())
            else:
                send_message(chat_id, "⚠️ Aucune preuve disponible pour le moment.")
            return

        if data.startswith("buy_"):
            pack_key = data.replace("buy_", "")
            if pack_key not in PACKS:
                return
            text = get_payment_method_text(pack_key)
            kb = get_payment_method_keyboard(pack_key)
            edit_message(chat_id, message_id, text, kb)
            return

        if data.startswith("pay_om_") or data.startswith("pay_mtn_"):
            is_orange = data.startswith("pay_om_")
            pack_key = data.replace("pay_om_", "").replace("pay_mtn_", "")
            if pack_key not in PACKS:
                return
            order_id = f"ORD-{int(datetime.now().timestamp())}"
            orders[order_id] = {
                "user_id": chat_id,
                "pack": pack_key,
                "status": "PENDING",
                "date": str(datetime.now()),
            }
            save_json(ORDERS_FILE, orders)
            method_label = "Orange Money 🟠" if is_orange else "MTN Mobile Money 🟡"
            number = ORANGE_MONEY if is_orange else MTN_MONEY
            text = get_recap_text(order_id, pack_key, method_label, number)
            kb = get_recap_keyboard(order_id, pack_key, is_orange)
            edit_message(chat_id, message_id, text, kb)
            return

        if data.startswith("gen_ussd_"):
            is_mtn = data.startswith("gen_ussd_mtn_")
            order_id = data.replace("gen_ussd_om_", "").replace("gen_ussd_mtn_", "")
            if order_id not in orders:
                return
            pack_key = orders[order_id]["pack"]
            amount = PACKS[pack_key]["price_num"]
            code = _generate_ussd_code("mtn" if is_mtn else "om", amount)
            provider_label = "MTN Mobile Money" if is_mtn else "Orange Money"
            text = get_ussd_text(code, provider_label)
            kb = get_ussd_keyboard(order_id, pack_key)
            edit_message(chat_id, message_id, text, kb)
            return

        if data.startswith("confirm_pay_"):
            order_id = data.replace("confirm_pay_", "")
            if order_id not in orders:
                return
            if orders[order_id]["status"] != "PENDING":
                return
            notif_channel = _get_current_notification_channel()
            user_name = callback.get("message", {}).get("chat", {}).get("first_name", "Inconnu")
            pack_name = PACKS[orders[order_id]["pack"]]["name"]
            admin_notif = (
                f"🚨 <b>COMMANDE À VÉRIFIER</b> 🚨\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 <b>Client :</b> {user_name}\n"
                f"🆔 <b>ID :</b> <code>{chat_id}</code>\n"
                f"📦 <b>Pack :</b> {pack_name}\n"
                f"🔖 <b>Réf :</b> <code>{order_id}</code>\n"
                f"━━━━━━━━━━━━━━━━━━━━\n"
                f"👉 <b>Valider :</b> <code>/confirm {order_id}</code>\n"
                f"👉 <b>Rejeter :</b> <code>/false {order_id}</code>"
            )
            sent_to_channel = send_message(notif_channel, admin_notif)
            if not sent_to_channel and str(notif_channel) != str(ADMIN_ID):
                send_message(ADMIN_ID, admin_notif)
            orders[order_id]["status_msg_id"] = message_id
            save_json(ORDERS_FILE, orders)
            edit_message(chat_id, message_id, get_waiting_text(order_id), get_waiting_keyboard(order_id))
            return

        if data.startswith("check_payment_"):
            order_id = data.replace("check_payment_", "")
            if order_id not in orders:
                return
            order = orders[order_id]
            if order["status"] == "PAID":
                links = load_json(LINKS_FILE)
                link = links.get(order["pack"], "Lien non configuré.")
                send_message(chat_id, f"✅ <b>Accès autorisé !</b>\n\nVotre lien :\n{link}")
            elif order["status"] == "REJECTED":
                send_message(chat_id, get_rejected_text())
            else:
                send_message(chat_id, "⏳ Votre paiement est toujours en attente de vérification.")
            return

    except Exception as exc:
        logger.error("Erreur dans le traitement du callback %s : %s", data, exc)


def _handle_photo_upload(update: Dict[str, Any]) -> None:
    message = update.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    if chat_id is None or chat_id != ADMIN_ID:
        return
    if user_states.get(chat_id) != "waiting_proof":
        return
    photos = message.get("photo")
    if not isinstance(photos, list) or not photos:
        return
    file_id = photos[-1].get("file_id")
    if not file_id:
        return
    file_path = get_file(file_id)
    if not file_path:
        send_message(chat_id, "⚠️ Impossible de récupérer le fichier.")
        return
    destination = os.path.join(PROOFS_DIR, "proof_1.jpg")
    if download_file(file_path, destination):
        user_states[chat_id] = None
        send_message(chat_id, "✅ <b>Preuve enregistrée avec succès !</b>")
        log_admin_action("UPLOAD_PROOF", destination)
    else:
        send_message(chat_id, "❌ Échec du téléchargement de la preuve.")


def process_update(
    update: Dict[str, Any],
    orders: Dict[str, Any],
    accepted_users: List[int],
) -> None:
    if not isinstance(update, dict):
        return
    if "message" not in update and "callback_query" not in update:
        return

    chat_id = None
    if "message" in update and isinstance(update["message"], dict):
        chat_id = update["message"].get("chat", {}).get("id")
    elif "callback_query" in update and isinstance(update["callback_query"], dict):
        chat_id = update["callback_query"].get("message", {}).get("chat", {}).get("id")

    if chat_id is None:
        return

    is_banned, hours_left = check_ban(chat_id)
    if is_banned:
        if "message" in update:
            text = update["message"].get("text", "")
            if text != "/start":
                send_message(chat_id, f"⛔ Vous êtes temporairement banni.\nRéessayez dans {hours_left} heures.")
        return

    if "message" in update:
        message = update["message"]
        text = message.get("text", "")
        if text.startswith("/"):
            command, args = _parse_command(text)
            if is_admin_command(command):
                notif_channel = _get_current_notification_channel()
                _handle_admin_command(command, args, update, orders, notif_channel)
            else:
                _handle_public_command(command, args, update, orders, accepted_users)
        elif "photo" in message:
            _handle_photo_upload(update)
        return

    if "callback_query" in update:
        callback = update["callback_query"]
        data = callback.get("data", "")
        if data:
            _handle_callback_query(data, update, orders, accepted_users)
