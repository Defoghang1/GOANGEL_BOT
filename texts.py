from config import PACKS

def get_main_menu_text():
    return ("🤖 <b>GOANGEL Quant Engine</b> | <i>Système Institutionnel</i>\n"
            "━━━━━━━━━━━━━━━━━━━━\n\nEntraîné sur <b>plus de 50 000 matchs</b>.\n"
            "✅ MLOps Pipeline (XGBoost, Poisson)\n✅ Validation Walk-Forward (Zéro fuite)\n✅ Calibration Pro\n\n"
            "🔒 <i>Paiements sécurisés Mobile Money.</i>")

def get_main_menu_keyboard():
    return {"inline_keyboard": [[{"text": "💼 Tarifs", "callback_data": "show_prices"}], [{"text": "📸 Preuves", "callback_data": "show_proof"}]]}

def get_consent_text():
    return ("🛡️ <b>CONDITIONS D'UTILISATION & SÉCURITÉ</b>\n━━━━━━━━━━━━━━━━━━━━\n\n"
            "Avant d'accéder au moteur GOANGEL, veuillez prendre connaissance de nos conditions :\n\n"
            "<b>1. 🔐 Paiements</b> : Les transactions Mobile Money sont vérifiées manuellement. Nous ne demandons jamais vos codes PIN.\n"
            "<b>2. 📜 Propriété</b> : Licence d'utilisation personnelle. Revente interdite.\n"
            "<b>3. 📈 Performance</b> : GOANGEL est un moteur d'analyse avancé conçu pour optimiser vos décisions.\n\n"
            "<i>Pour continuer, vous devez accepter ces conditions.</i>")

def get_consent_keyboard():
    return {"inline_keyboard": [[{"text": "✅ J'accepte les conditions", "callback_data": "accept_terms"}], [{"text": "❌ Je refuse", "callback_data": "refuse_terms"}]]}

def get_prices_text():
    txt = "👑 <b>GOANGEL QUANT ENGINE</b>\n━━━━━━━━━━━━━━━━━━━━\nDécouvrez nos offres.\n\n"
    for k, p in PACKS.items():
        txt += f"🔹 <b>{p['name']}</b>\n💰 <b>{p['price']}</b>\n📋 <b>Inclus :</b>\n"
        for f in p["features"]: txt += f"  ✅ {f}\n"
        txt += "━━━━━━━━━━━━━━━━━━━━\n"
    return txt

def get_prices_keyboard():
    return {"inline_keyboard": [
        [{"text": f"Acheter {PACKS['starter']['name']}", "callback_data": "buy_starter"}],
        [{"text": f"Acheter {PACKS['pro']['name']}", "callback_data": "buy_pro"}],
        [{"text": f"Acheter {PACKS['elite']['name']}", "callback_data": "buy_elite"}],
        [{"text": "📸 Voir les Preuves", "callback_data": "show_proof"}],
        [{"text": "⬅️ Retour au menu", "callback_data": "back_to_menu"}]]}
