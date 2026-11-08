import html
from typing import Any, Dict, List

from config import PACKS

_MAX_TEXT_LENGTH = 4096

_HTML_ESCAPE_MAP = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
}


def _escape_html(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    return html.escape(text, quote=False)


def _validate_text(text: str, context: str) -> str:
    if not isinstance(text, str):
        raise ValueError(f"{context} : le texte doit être une chaîne.")
    if not text.strip():
        raise ValueError(f"{context} : le texte ne peut pas être vide.")
    if len(text) > _MAX_TEXT_LENGTH:
        raise ValueError(f"{context} : le texte dépasse la limite Telegram ({_MAX_TEXT_LENGTH} caractères).")
    return text


def _validate_packs() -> None:
    if not isinstance(PACKS, dict) or not PACKS:
        raise ValueError("PACKS doit être un dictionnaire non vide.")
    for key, pack in PACKS.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError("Clé de pack invalide.")
        if not isinstance(pack, dict):
            raise ValueError(f"Pack {key} : la valeur doit être un dictionnaire.")
        for field in ("name", "price"):
            if field not in pack or not isinstance(pack[field], str) or not pack[field].strip():
                raise ValueError(f"Pack {key} : champ '{field}' invalide.")
        if "price_num" not in pack or not isinstance(pack["price_num"], int) or pack["price_num"] <= 0:
            raise ValueError(f"Pack {key} : 'price_num' doit être un entier strictement positif.")
        if "features" not in pack or not isinstance(pack["features"], list) or not pack["features"]:
            raise ValueError(f"Pack {key} : 'features' doit être une liste non vide.")
        for feature in pack["features"]:
            if not isinstance(feature, str) or not feature.strip():
                raise ValueError(f"Pack {key} : une fonctionnalité est invalide.")


_validate_packs()


def get_main_menu_text() -> str:
    text = (
        "🤖 <b>GOANGEL Quant Engine</b> | <i>Système Institutionnel</i>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Entraîné sur <b>plus de 50 000 matchs</b>.\n"
        "✅ MLOps Pipeline (XGBoost, Poisson)\n"
        "✅ Validation Walk-Forward (Zéro fuite)\n"
        "✅ Calibration Pro\n\n"
        "🔒 <i>Paiements sécurisés Mobile Money.</i>"
    )
    return _validate_text(text, "get_main_menu_text")


def get_main_menu_keyboard() -> Dict[str, List[List[Dict[str, str]]]]:
    return {
        "inline_keyboard": [
            [{"text": "💼 Tarifs", "callback_data": "show_prices"}],
            [{"text": "📸 Preuves", "callback_data": "show_proof"}],
        ]
    }


def get_consent_text() -> str:
    text = (
        "🛡️ <b>CONDITIONS D'UTILISATION & SÉCURITÉ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Avant d'accéder au moteur GOANGEL, veuillez prendre connaissance de nos conditions :\n\n"
        "<b>1. 🔐 Paiements</b> : Les transactions Mobile Money sont vérifiées manuellement. "
        "Nous ne demandons jamais vos codes PIN.\n"
        "<b>2. 📜 Propriété</b> : Licence d'utilisation personnelle. Revente interdite.\n"
        "<b>3. 📈 Performance</b> : GOANGEL est un moteur d'analyse avancé conçu pour optimiser vos décisions.\n\n"
        "<i>Pour continuer, vous devez accepter ces conditions.</i>"
    )
    return _validate_text(text, "get_consent_text")


def get_consent_keyboard() -> Dict[str, List[List[Dict[str, str]]]]:
    return {
        "inline_keyboard": [
            [{"text": "✅ J'accepte les conditions", "callback_data": "accept_terms"}],
            [{"text": "❌ Je refuse", "callback_data": "refuse_terms"}],
        ]
    }


def get_prices_text() -> str:
    parts: List[str] = [
        "👑 <b>GOANGEL QUANT ENGINE</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        "Découvrez nos offres pour accéder au moteur de prédiction.",
        "",
    ]
    for key, pack in PACKS.items():
        name = _escape_html(pack["name"])
        price = _escape_html(pack["price"])
        parts.append(f"🔹 <b>{name}</b>")
        parts.append(f"💰 <b>{price}</b>")
        parts.append("📋 <b>Inclus :</b>")
        for feature in pack["features"]:
            parts.append(f"  ✅ {_escape_html(feature)}")
        parts.append("━━━━━━━━━━━━━━━━━━━━")
    text = "\n".join(parts)
    return _validate_text(text, "get_prices_text")


def get_prices_keyboard() -> Dict[str, List[List[Dict[str, str]]]]:
    buttons: List[List[Dict[str, str]]] = []
    for key, pack in PACKS.items():
        label = f"Acheter {pack['name']}"
        buttons.append([{"text": label, "callback_data": f"buy_{key}"}])
    buttons.append([{"text": "📸 Voir les Preuves", "callback_data": "show_proof"}])
    buttons.append([{"text": "⬅️ Retour au menu", "callback_data": "back_to_menu"}])
    return {"inline_keyboard": buttons}


def get_payment_method_text(pack_key: str) -> str:
    if pack_key not in PACKS:
        raise ValueError(f"Pack inconnu : {pack_key}")
    pack = PACKS[pack_key]
    text = (
        f"🛒 <b>SÉLECTION DU PAIEMENT</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Produit : <b>{_escape_html(pack['name'])}</b>\n"
        f"Montant : <b>{_escape_html(pack['price'])}</b>\n\n"
        f"Veuillez choisir votre mode de paiement :"
    )
    return _validate_text(text, "get_payment_method_text")


def get_payment_method_keyboard(pack_key: str) -> Dict[str, List[List[Dict[str, str]]]]:
    if pack_key not in PACKS:
        raise ValueError(f"Pack inconnu : {pack_key}")
    return {
        "inline_keyboard": [
            [{"text": "🟠 Orange Money", "callback_data": f"pay_om_{pack_key}"}],
            [{"text": "🟡 MTN Mobile Money", "callback_data": f"pay_mtn_{pack_key}"}],
            [{"text": "⬅️ Annuler", "callback_data": "show_prices"}],
        ]
    }


def get_recap_text(order_id: str, pack_key: str, method_label: str, number: str) -> str:
    if pack_key not in PACKS:
        raise ValueError(f"Pack inconnu : {pack_key}")
    pack = PACKS[pack_key]
    text = (
        f"🧾 <b>FACTURE SÉCURISÉE : {_escape_html(order_id)}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"📦 Produit : <b>{_escape_html(pack['name'])}</b>\n"
        f"💰 Montant : <b>{_escape_html(pack['price'])}</b>\n"
        f"💳 Mode : <b>{_escape_html(method_label)}</b>\n"
        f"📱 Numéro : <code>{_escape_html(number)}</code>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"⚠️ <b>Instructions :</b>\n"
        f"1. Effectuez le transfert de <b>{_escape_html(pack['price'])}</b> au numéro ci-dessus.\n"
        f"2. Envoyez la capture d'écran à l'administrateur.\n"
        f"3. Cliquez sur le bouton ci-dessous pour confirmer."
    )
    return _validate_text(text, "get_recap_text")


def get_recap_keyboard(order_id: str, pack_key: str, is_orange: bool) -> Dict[str, List[List[Dict[str, str]]]]:
    if not isinstance(order_id, str) or not order_id.strip():
        raise ValueError("order_id invalide.")
    if pack_key not in PACKS:
        raise ValueError(f"Pack inconnu : {pack_key}")
    ussd_button = {
        "text": "📱 Code USSD Orange" if is_orange else "📱 Code USSD MTN",
        "callback_data": f"gen_ussd_{'om' if is_orange else 'mtn'}_{order_id}",
    }
    return {
        "inline_keyboard": [
            [ussd_button],
            [{"text": "✅ J'ai payé", "callback_data": f"confirm_pay_{order_id}"}],
            [{"text": "⬅️ Annuler", "callback_data": f"buy_{pack_key}"}],
        ]
    }


def get_ussd_text(code: str, provider_label: str) -> str:
    if not isinstance(code, str) or not code.strip():
        raise ValueError("Code USSD invalide.")
    text = (
        f"📱 <b>CODE USSD {_escape_html(provider_label)}</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"Pour payer, copiez ce code et collez-le dans votre clavier téléphonique :\n\n"
        f"👉 <code>{_escape_html(code)}</code> 👈\n\n"
        f"⚠️ <b>Instructions :</b>\n"
        f"1. Appuyez longuement sur le code pour le copier.\n"
        f"2. Ouvrez l'application Téléphone.\n"
        f"3. Collez le code et appuyez sur Appeler.\n"
        f"4. Validez avec votre code PIN.\n\n"
        f"Une fois le transfert effectué, envoyez la capture d'écran à l'administrateur "
        f"puis cliquez sur <b>« J'ai payé »</b>."
    )
    return _validate_text(text, "get_ussd_text")


def get_ussd_keyboard(order_id: str, pack_key: str) -> Dict[str, List[List[Dict[str, str]]]]:
    if not isinstance(order_id, str) or not order_id.strip():
        raise ValueError("order_id invalide.")
    if pack_key not in PACKS:
        raise ValueError(f"Pack inconnu : {pack_key}")
    return {
        "inline_keyboard": [
            [{"text": "✅ J'ai payé", "callback_data": f"confirm_pay_{order_id}"}],
            [{"text": "⬅️ Retour", "callback_data": f"buy_{pack_key}"}],
        ]
    }


def get_waiting_text(order_id: str) -> str:
    if not isinstance(order_id, str) or not order_id.strip():
        raise ValueError("order_id invalide.")
    text = (
        f"⏳ <b>PAIEMENT EN ATTENTE DE VÉRIFICATION</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"🆔 Réf : <code>{_escape_html(order_id)}</code>\n\n"
        f"Veuillez patienter pendant que notre administrateur vérifie votre transaction. "
        f"Vous recevrez une notification dès validation."
    )
    return _validate_text(text, "get_waiting_text")


def get_waiting_keyboard(order_id: str) -> Dict[str, List[List[Dict[str, str]]]]:
    if not isinstance(order_id, str) or not order_id.strip():
        raise ValueError("order_id invalide.")
    return {
        "inline_keyboard": [
            [{"text": "🔄 Vérifier mon statut", "callback_data": f"check_payment_{order_id}"}],
            [{"text": "⬅️ Retour au menu", "callback_data": "back_to_menu"}],
        ]
    }


def get_success_text(pack_name: str) -> str:
    text = (
        f"✅ <b>TRANSACTION VALIDÉE !</b>\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Merci pour votre achat : <b>{_escape_html(pack_name)}</b>.\n"
        f"👉 Tapez /lien ou utilisez le bouton ci-dessous pour récupérer votre accès."
    )
    return _validate_text(text, "get_success_text")


def get_success_keyboard(order_id: str) -> Dict[str, List[List[Dict[str, str]]]]:
    if not isinstance(order_id, str) or not order_id.strip():
        raise ValueError("order_id invalide.")
    return {
        "inline_keyboard": [
            [{"text": "🔗 Récupérer mon lien", "callback_data": f"check_payment_{order_id}"}],
            [{"text": "⬅️ Retour au menu", "callback_data": "back_to_menu"}],
        ]
    }


def get_rejected_text() -> str:
    text = (
        "❌ <b>PAIEMENT REJETÉ</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "L'administrateur n'a pas reçu votre paiement. "
        "Attention aux avertissements : au bout de 3 faux paiements, votre accès sera suspendu."
    )
    return _validate_text(text, "get_rejected_text")


def get_links_report_text(links: Dict[str, str]) -> str:
    parts: List[str] = [
        "🔗 <b>LIENS DE TÉLÉCHARGEMENT ACTUELS</b>",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
    ]
    for key, pack in PACKS.items():
        url = links.get(key, "Non configuré") if isinstance(links, dict) else "Non configuré"
        parts.append(f"📦 <b>{_escape_html(pack['name'])}</b>")
        parts.append(_escape_html(url))
        parts.append("")
    parts.append("Pour modifier : <code>/setlien &lt;pack&gt; &lt;lien&gt;</code>")
    text = "\n".join(parts)
    return _validate_text(text, "get_links_report_text")
