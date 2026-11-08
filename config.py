import os
import re
from typing import Dict, Any, List

class ConfigError(Exception):
    pass

def _require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or not str(value).strip():
        raise ConfigError(f"Variable d'environnement obligatoire manquante ou vide : {name}")
    return str(value).strip()

def _optional_env(name: str, default: str) -> str:
    value = os.getenv(name)
    if value is None or not str(value).strip():
        return default
    return str(value).strip()

def _validate_positive_int(value: str, name: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ConfigError(f"{name} doit être un entier positif, reçu : {value!r}")
    if parsed <= 0:
        raise ConfigError(f"{name} doit être strictement positif, reçu : {parsed}")
    return parsed

def _validate_phone(value: str, name: str) -> str:
    if not re.fullmatch(r"\+?\d{7,15}", value):
        raise ConfigError(f"{name} ne respecte pas le format téléphonique attendu : {value!r}")
    return value

TOKEN = _require_env("TELEGRAM_BOT_TOKEN")
ADMIN_ID = _validate_positive_int(_require_env("TELEGRAM_ADMIN_ID"), "TELEGRAM_ADMIN_ID")
ORANGE_MONEY = _validate_phone(_optional_env("ORANGE_MONEY", "+237640841826"), "ORANGE_MONEY")
MTN_MONEY = _validate_phone(_optional_env("MTN_MONEY", "+237678422810"), "MTN_MONEY")
TELEGRAM_CONTACT = _optional_env("TELEGRAM_CONTACT", "@MRGHOSTROOT")
DEFAULT_NOTIF_CHANNEL_RAW = _optional_env("DEFAULT_NOTIF_CHANNEL", str(ADMIN_ID))
try:
    DEFAULT_NOTIF_CHANNEL = int(DEFAULT_NOTIF_CHANNEL_RAW) if DEFAULT_NOTIF_CHANNEL_RAW.lstrip("-").isdigit() else DEFAULT_NOTIF_CHANNEL_RAW
except ValueError:
    DEFAULT_NOTIF_CHANNEL = DEFAULT_NOTIF_CHANNEL_RAW

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

PACKS: Dict[str, Dict[str, Any]] = {
    "starter": {
        "name": "📦 STARTER",
        "price": "25 000 FCFA",
        "price_num": 25000,
        "features": [
            "Cache complet",
            "Script d'inférence",
            "Support standard"
        ]
    },
    "pro": {
        "name": "🚀 PRO (Recommandé)",
        "price": "75 000 FCFA",
        "price_num": 75000,
        "features": [
            "Tout Starter",
            "Code source MLOps",
            "Documentation",
            "MAJ 1 mois"
        ]
    },
    "elite": {
        "name": "💼 ELITE",
        "price": "150 000 FCFA",
        "price_num": 150000,
        "features": [
            "Tout Pro",
            "Accompagnement",
            "Déploiement",
            "MAJ à vie"
        ]
    }
}

PUBLIC_COMMANDS: List[Dict[str, str]] = [
    {"command": "start", "description": "🔄 Démarrer / Réinitialiser"},
    {"command": "tarifs", "description": "💼 Voir les packs et prix"},
    {"command": "lien", "description": "🔗 Obtenir mon lien de téléchargement"},
    {"command": "securite", "description": "🔒 Politique de sécurité"},
    {"command": "support", "description": "📞 Contacter l'assistance"},
    {"command": "myid", "description": "🆔 Afficher mon ID Telegram"}
]

ADMIN_ONLY_COMMANDS: List[Dict[str, str]] = [
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

ADMIN_COMMAND_NAMES: frozenset = frozenset(cmd["command"] for cmd in ADMIN_ONLY_COMMANDS)
_ADMIN_COMMAND_NAMES: frozenset = ADMIN_COMMAND_NAMES

# Garde-fou : aucune commande admin ne doit jamais figurer dans le menu public.
_leaked = ADMIN_COMMAND_NAMES & {cmd["command"] for cmd in PUBLIC_COMMANDS}
if _leaked:
    raise ConfigError(f"Commandes admin présentes dans PUBLIC_COMMANDS : {sorted(_leaked)}")

ADMIN_COMMANDS: List[Dict[str, str]] = PUBLIC_COMMANDS + ADMIN_ONLY_COMMANDS


def normalize_command(command: str) -> str:
    """'/Confirm@MonBot' -> 'confirm'"""
    if not isinstance(command, str):
        return ""
    return command.strip().lstrip("/").split("@", 1)[0].lower()


def is_admin_command(command: str) -> bool:
    return normalize_command(command) in ADMIN_COMMAND_NAMES
