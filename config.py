import os

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.getenv("TELEGRAM_ADMIN_ID", "0"))
ORANGE_MONEY = os.getenv("ORANGE_MONEY", "Non configuré")
MTN_MONEY = os.getenv("MTN_MONEY", "Non configuré")
TELEGRAM_CONTACT = os.getenv("TELEGRAM_CONTACT", "@MRGHOSTROOT")
DEFAULT_NOTIF_CHANNEL = os.getenv("DEFAULT_NOTIF_CHANNEL", ADMIN_ID)

STATE_FILE = "bot_state.json"
ORDERS_FILE = "orders.json"
USERS_FILE = "accepted_users.json"
BANNED_FILE = "banned_users.json"
WARNINGS_FILE = "user_warnings.json"
SECURITY_STRIKES_FILE = "security_strikes.json"
LINKS_FILE = "download_links.json"
CONFIG_FILE = "bot_config.json"
AUDIT_LOG = "admin_audit.log"
PROOFS_DIR = "proofs"

MAX_RUNTIME = 21420
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"

PACKS = {
    "starter": {"name": "📦 STARTER", "price": "25 000 FCFA", "price_num": 25000, "features": ["Cache complet", "Script d'inférence", "Support standard"]},
    "pro": {"name": "🚀 PRO (Recommandé)", "price": "75 000 FCFA", "price_num": 75000, "features": ["Tout Starter", "Code source MLOps", "Documentation", "MAJ 1 mois"]},
    "elite": {"name": "💼 ELITE", "price": "150 000 FCFA", "price_num": 150000, "features": ["Tout Pro", "Accompagnement", "Déploiement", "MAJ à vie"]}
}

if ADMIN_ID == 0:
    raise RuntimeError("TELEGRAM_ADMIN_ID n'est pas défini.")
