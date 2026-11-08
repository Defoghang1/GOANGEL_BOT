import os
from datetime import datetime
from config import PACKS, ORANGE_MONEY, MTN_MONEY, TELEGRAM_CONTACT, LINKS_FILE, WARNINGS_FILE, BANNED_FILE, CONFIG_FILE, PROOFS_DIR, ORDERS_FILE, DEFAULT_NOTIF_CHANNEL
from telegram_api import load_json, save_json, send_message, edit_message, delete_message, send_photo
from security import handle_admin_security
from texts import *

user_states = {}

def process_update(update, orders, accepted_users):
    config = load_json(CONFIG_FILE)
    notif_channel = config.get("notification_channel", DEFAULT_NOTIF_CHANNEL)
    
    chat_id, message_id, text = None, None, ""
    if "callback_query" in update:
        cb = update["callback_query"]
        chat_id = cb["message"]["chat"]["id"]
        message_id = cb["message"]["message_id"]
        data = cb["data"]
    elif "message" in update:
        chat_id = update["message"]["chat"]["id"]
        text = update["message"].get("text", "")

    if not chat_id: return

    if text.startswith("/"):
        cmd = text.split()[0]
        admin_cmds = ["/setchannel", "/confirm", "/false", "/block", "/unlock", "/preuve", "/delete_preuve", "/orders", "/setlien", "/liens"]
        
        if cmd in admin_cmds:
            if not handle_admin_security(update, cmd, notif_channel): return
            
            if cmd == "/setchannel":
                parts = text.split()
                if len(parts) == 2:
                    config["notification_channel"] = parts[1]
                    save_json(CONFIG_FILE, config)
                    send_message(chat_id, f"✅ Canal : {parts[1]}")
            elif cmd == "/confirm":
                parts = text.split()
                if len(parts) == 2 and parts[1] in orders:
                    oid = parts[1]
                    if orders[oid]["status"] != "PAID":
                        orders[oid]["status"] = "PAID"
                        save_json(ORDERS_FILE, orders)
                        buyer = orders[oid]["user_id"]
                        pname = PACKS[orders[oid]["pack"]]["name"]
                        msg = f"✅ <b>TRANSACTION VALIDÉE !</b>\n\nMerci ({pname}).\n👉 /lien ou bouton."
                        kb = {"inline_keyboard": [[{"text": "🔗 Lien", "callback_data": f"check_payment_{oid}"}]]}
                        if orders[oid].get("status_msg_id"): edit_message(buyer, orders[oid]["status_msg_id"], msg, kb)
                        else: send_message(buyer, msg, kb)
                        send_message(chat_id, f"✅ Commande {oid} validée.")
            elif cmd == "/false":
                parts = text.split()
                if len(parts) == 2 and parts[1] in orders:
                    oid = parts[1]
                    if orders[oid]["status"] != "PAID":
                        orders[oid]["status"] = "REJECTED"
                        save_json(ORDERS_FILE, orders)
                        buyer = orders[oid]["user_id"]
                        w = load_json(WARNINGS_FILE)
                        w[str(buyer)] = w.get(str(buyer), 0) + 1
                        save_json(WARNINGS_FILE, w)
                        wc = w[str(buyer)]
                        if wc >= 3:
                            b = load_json(BANNED_FILE)
                            b[str(buyer)] = (datetime.now() + datetime.timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
                            save_json(BANNED_FILE, b)
                            send_message(buyer, "🚫 <b>BANNI 3 JOURS.</b>\nFaux paiement répété.")
                        else:
                            send_message(buyer, f"⚠️ <b>AVERTISSEMENT {wc}/3</b>\nPaiement non reçu.")
            elif cmd == "/block":
                parts = text.split()
                if len(parts) == 2:
                    target = parts[1]
                    b = load_json(BANNED_FILE)
                    b[str(target)] = (datetime.now() + datetime.timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
                    save_json(BANNED_FILE, b)
                    send_message(chat_id, f"🚫 Utilisateur {target} bloqué 3 jours.")
                    send_message(int(target), "🚫 Vous avez été bloqué.")
            elif cmd == "/unlock":
                parts = text.split()
                if len(parts) == 2:
                    target = parts[1]
                    b = load_json(BANNED_FILE)
                    if target in b: del b[target]; save_json(BANNED_FILE, b)
                    send_message(chat_id, f"✅ Utilisateur {target} débloqué.")
                    send_message(int(target), "✅ Accès rétabli.")
            elif cmd == "/preuve":
                user_states[chat_id] = "waiting_proof"
                send_message(chat_id, "📸 Envoyez l'image.")
            elif cmd == "/delete_preuve":
                if os.path.exists(os.path.join(PROOFS_DIR, "proof_1.jpg")):
                    os.remove(os.path.join(PROOFS_DIR, "proof_1.jpg"))
                    send_message(chat_id, "🗑️ Preuve supprimée.")
            elif cmd == "/orders":
                p = [f"{k} ({v['pack']})" for k, v in orders.items() if v["status"] == "PENDING"]
                send_message(chat_id, "📋 En attente :\n" + "\n".join(p) if p else "✅ Aucune commande.")
            elif cmd == "/setlien":
                parts = text.split(maxsplit=2)
                if len(parts) == 3 and parts[1].lower() in PACKS:
                    l = load_json(LINKS_FILE)
                    l[parts[1].lower()] = parts[2]
                    save_json(LINKS_FILE, l)
                    send_message(chat_id, f"✅ Lien {parts[1]} mis à jour.")
            elif cmd == "/liens":
                l = load_json(LINKS_FILE)
                txt = "🔗 <b>LIENS</b>\n\n"
                for k, p in PACKS.items(): txt += f"📦 {p['name']} :\n{l.get(k, 'Non configuré')}\n\n"
                send_message(chat_id, txt)
            return

    if "callback_query" in update:
        if data == "accept_terms":
            if chat_id not in accepted_users:
                accepted_users.append(chat_id)
                save_json("accepted_users.json", accepted_users)
            edit_message(chat_id, message_id, get_main_menu_text(), get_main_menu_keyboard())
        elif data == "refuse_terms":
            b = load_json(BANNED_FILE)
            b[str(chat_id)] = (datetime.now() + datetime.timedelta(days=30)).strftime("%Y-%m-%d %H:%M:%S")
            save_json(BANNED_FILE, b)
            edit_message(chat_id, message_id, "❌ Accès bloqué.", None)
        elif data == "show_prices": edit_message(chat_id, message_id, get_prices_text(), get_prices_keyboard())
        elif data == "back_to_menu": edit_message(chat_id, message_id, get_main_menu_text(), get_main_menu_keyboard())
        elif data == "show_proof":
            delete_message(chat_id, message_id)
            send_photo(chat_id, os.path.join(PROOFS_DIR, "proof_1.jpg"), "📸 <b>Preuve de gains récents</b>")
            send_message(chat_id, get_main_menu_text(), get_main_menu_keyboard())
        elif data.startswith("buy_"):
            pk = data.replace("buy_", "")
            if pk in PACKS:
                p = PACKS[pk]
                txt = f"🛒 <b>PAIEMENT</b>\nProduit : <b>{p['name']}</b>\nMontant : <b>{p['price']}</b>\n\nChoisissez :"
                kb = {"inline_keyboard": [[{"text": "🟠 Orange", "callback_data": f"pay_om_{pk}"}], [{"text": "🟡 MTN", "callback_data": f"pay_mtn_{pk}"}], [{"text": "⬅️ Annuler", "callback_data": "show_prices"}]]}
                edit_message(chat_id, message_id, txt, kb)
        elif data.startswith("pay_om_") or data.startswith("pay_mtn_"):
            is_om = data.startswith("pay_om_")
            pk = data.replace("pay_om_", "").replace("pay_mtn_", "")
            if pk in PACKS:
                oid = f"ORD-{int(datetime.now().timestamp())}"
                orders[oid] = {"user_id": chat_id, "pack": pk, "status": "PENDING", "date": str(datetime.now())}
                save_json(ORDERS_FILE, orders)
                num = ORANGE_MONEY if is_om else MTN_MONEY
                meth = "Orange Money 🟠" if is_om else "MTN Mobile Money 🟡"
                txt = f"🧾 <b>FACTURE : {oid}</b>\nProduit : <b>{PACKS[pk]['name']}</b>\nMontant : <b>{PACKS[pk]['price']}</b>\nMode : {meth}\nNuméro : <code>{num}</code>\n\n⚠️ Transférez le montant exact."
                kb = {"inline_keyboard": [[{"text": f"📱 Code USSD", "callback_data": f"gen_ussd_{'om' if is_om else 'mtn'}_{oid}"}], [{"text": "✅ J'ai payé", "callback_data": f"confirm_pay_{oid}"}], [{"text": "⬅️ Annuler", "callback_data": f"buy_{pk}"}]]}
                edit_message(chat_id, message_id, txt, kb)
        elif data.startswith("gen_ussd_"):
            is_mtn = "mtn" in data
            oid = data.replace("gen_ussd_om_", "").replace("gen_ussd_mtn_", "")
            pk = orders[oid]["pack"]
            amt = PACKS[pk]["price_num"]
            if is_mtn:
                n = "".join(filter(str.isdigit, MTN_MONEY))[-9:]
                code = f"*126*1*1*{n}*{amt}#"
                t = "MTN MOBILE MONEY"
            else:
                n = "".join(filter(str.isdigit, ORANGE_MONEY))[-9:]
                code = f"#150*1*1*{n}*1*{amt}*2#"
                t = "ORANGE MONEY"
            txt = f"📱 <b>CODE USSD {t}</b>\nCopiez ce code dans votre clavier téléphonique :\n\n👉 <code>{code}</code> 👈\n\nUne fois payé, envoyez la capture à {TELEGRAM_CONTACT} et cliquez sur 'J'ai payé'."
            kb = {"inline_keyboard": [[{"text": "✅ J'ai payé", "callback_data": f"confirm_pay_{oid}"}], [{"text": "⬅️ Retour", "callback_data": f"buy_{pk}"}]]}
            edit_message(chat_id, message_id, txt, kb)
        elif data.startswith("confirm_pay_"):
            oid = data.replace("confirm_pay_", "")
            user_name = cb["message"]["chat"].get("first_name", "Inconnu")
            admin_notif = f"🚨 <b>COMMANDE À VÉRIFIER</b> 🚨\nClient : {user_name}\nID : <code>{chat_id}</code>\nPack : {PACKS[orders[oid]['pack']]['name']}\nRéf : <code>{oid}</code>\n\n👉 Valider : <code>/confirm {oid}</code>\n👉 Rejeter : <code>/false {oid}</code>"
            if not send_message(notif_channel, admin_notif) and notif_channel != ADMIN_ID: send_message(ADMIN_ID, admin_notif)
            orders[oid]["status_msg_id"] = message_id
            save_json(ORDERS_FILE, orders)
            txt = f"⏳ <b>EN ATTENTE</b>\nRéf : {oid}\nVérification en cours."
            kb = {"inline_keyboard": [[{"text": "🔄 Vérifier", "callback_data": f"check_payment_{oid}"}], [{"text": "⬅️ Menu", "callback_data": "back_to_menu"}]]}
            edit_message(chat_id, message_id, txt, kb)
        elif data.startswith("check_payment_"):
            oid = data.replace("check_payment_", "")
            if oid in orders and orders[oid]["status"] == "PAID":
                link = load_json(LINKS_FILE).get(orders[oid]["pack"], "Lien non configuré")
                send_message(chat_id, f"✅ <b>Accès autorisé !</b>\n\nVotre lien :\n{link}")
            elif oid in orders and orders[oid]["status"] == "REJECTED":
                send_message(chat_id, "❌ <b>Paiement rejeté.</b>")
            else:
                send_message(chat_id, "⏳ En attente de vérification.")
        return

    if chat_id == ADMIN_ID and user_states.get(chat_id) == "waiting_proof" and "photo" in update["message"]:
        file_id = update["message"]["photo"][-1]["file_id"]
        import requests
        from config import BASE_URL
        file_path = requests.get(f"{BASE_URL}/getFile?file_id={file_id}").json()["result"]["file_path"]
        img_data = requests.get(f"https://api.telegram.org/file/bot{TOKEN}/{file_path}").content
        with open(os.path.join(PROOFS_DIR, "proof_1.jpg"), "wb") as f: f.write(img_data)
        user_states[chat_id] = None
        send_message(chat_id, "✅ <b>Preuve enregistrée !</b>")
        return

    if text == "/start":
        if chat_id in accepted_users:
            accepted_users.remove(chat_id)
            save_json("accepted_users.json", accepted_users)
        send_message(chat_id, get_consent_text(), get_consent_keyboard())
    elif text == "/tarifs":
        if chat_id in accepted_users: send_message(chat_id, get_prices_text(), get_prices_keyboard())
        else: send_message(chat_id, get_consent_text(), get_consent_keyboard())
    elif text == "/lien":
        if chat_id in accepted_users:
            uo = [k for k, v in orders.items() if v["user_id"] == chat_id and v["status"] == "PAID"]
            if uo: send_message(chat_id, f"✅ Lien :\n{load_json(LINKS_FILE).get(orders[uo[-1]]['pack'], 'Erreur')}")
            else: send_message(chat_id, "⛔ Aucune commande payée.")
    elif text == "/support":
        if chat_id in accepted_users: send_message(chat_id, f"Contact : {TELEGRAM_CONTACT}")
    elif text == "/myid":
        send_message(chat_id, f"🆔 <b>Votre ID Telegram :</b> <code>{chat_id}</code>")
