import time
import logging
import requests
import os
from config import TOKEN, ADMIN_ID, BASE_URL, MAX_RUNTIME, LINKS_FILE, CONFIG_FILE, WARNINGS_FILE, SECURITY_STRIKES_FILE, DEFAULT_NOTIF_CHANNEL, STATE_FILE, ORDERS_FILE, USERS_FILE, PROOFS_DIR
from telegram_api import load_json, save_json
from handlers import process_update

logging.basicConfig(level=logging.INFO)

def setup_bot_menus():
    if not TOKEN or not ADMIN_ID: return
    try: requests.post(f"{BASE_URL}/deleteMyCommands", timeout=5)
    except Exception: pass
    public_cmds = [
        {"command": "start", "description": "🔄 Démarrer / Réinitialiser"},
        {"command": "tarifs", "description": "💼 Voir les packs et prix"},
        {"command": "lien", "description": "🔗 Obtenir mon lien de téléchargement"},
        {"command": "securite", "description": "🔒 Politique de sécurité"},
        {"command": "support", "description": "📞 Contacter l'assistance"},
        {"command": "myid", "description": "🆔 Afficher mon ID Telegram"}
    ]
    admin_cmds = public_cmds + [
        {"command": "setchannel", "description": "📡 [ADMIN] Canal des notifications"},
        {"command": "setlien", "description": "🔧 [ADMIN] Modifier un lien"},
        {"command": "liens", "description": "🔗 [ADMIN] Voir les liens actuels"},
        {"command": "preuve", "description": "📸 [ADMIN] Uploader une preuve"},
        {"command": "delete_preuve", "description": "🗑️ [ADMIN] Supprimer la preuve"},
        {"command": "confirm", "description": "✅ [ADMIN] Valider une commande"},
        {"command": "false", "description": "❌ [ADMIN] Rejeter un faux paiement"},
        {"command": "block", "description": "🚫 [ADMIN] Bloquer un utilisateur"},
        {"command": "unlock", "description": "🔓 [ADMIN] Débloquer un utilisateur"},
        {"command": "orders", "description": "📋 [ADMIN] Voir les commandes"}
    ]
    try:
        requests.post(f"{BASE_URL}/setMyCommands", json={"commands": public_cmds}, timeout=5)
        admin_payload = {"commands": admin_cmds, "scope": {"type": "chat", "chat_id": ADMIN_ID}}
        requests.post(f"{BASE_URL}/setMyCommands", json=admin_payload, timeout=5)
        logging.info("✅ Menus Telegram configurés.")
    except Exception as e:
        logging.error(f"Erreur config menu: {e}")

def main():
    os.makedirs(PROOFS_DIR, exist_ok=True)
    for f, default in [
        (LINKS_FILE, {"starter": "https://...", "pro": "https://...", "elite": "https://..."}),
        (CONFIG_FILE, {"notification_channel": DEFAULT_NOTIF_CHANNEL}),
        (WARNINGS_FILE, {}),
        (SECURITY_STRIKES_FILE, {})
    ]:
        if not os.path.exists(f): save_json(f, default)

    setup_bot_menus()
    
    state = load_json(STATE_FILE)
    orders = load_json(ORDERS_FILE)
    accepted_users = load_json(USERS_FILE)
    offset = state.get("offset", 0) if isinstance(state, dict) else 0
    start_time = time.time()
    
    while time.time() - start_time < MAX_RUNTIME:
        try:
            res = requests.get(f"{BASE_URL}/getUpdates", params={"offset": offset, "timeout": 10}, timeout=15)
            data = res.json()
            if data.get("ok") and data.get("result"):
                for update in data["result"]:
                    process_update(update, orders, accepted_users)
                    offset = update["update_id"] + 1
                state["offset"] = offset
                save_json(STATE_FILE, state)
        except requests.exceptions.Timeout: pass
        except Exception as e:
            logging.error(f"Erreur loop: {e}")
            time.sleep(3)
    save_json(STATE_FILE, state)

if __name__ == "__main__":
    main()
