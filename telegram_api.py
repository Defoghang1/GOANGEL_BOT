import json
import os
import logging
import requests
from config import BASE_URL

def load_json(file):
    if os.path.exists(file):
        try:
            with open(file, "r") as f: return json.load(f)
        except Exception: return {}
    return {}

def save_json(file, data):
    tmp_file = file + ".tmp"
    try:
        with open(tmp_file, "w") as f:
            json.dump(data, f, indent=4)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_file, file)
    except Exception as e:
        logging.error(f"Erreur écriture {file} : {e}")
        if os.path.exists(tmp_file): os.remove(tmp_file)

def send_message(chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup: payload["reply_markup"] = json.dumps(reply_markup)
    try:
        r = requests.post(f"{BASE_URL}/sendMessage", json=payload, timeout=10)
        return r.json().get("result", {}).get("message_id") if r.status_code == 200 else None
    except Exception as e:
        logging.error(f"Erreur d'envoi : {e}")
        return None

def edit_message(chat_id, message_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "message_id": message_id, "text": text, "parse_mode": "HTML"}
    if reply_markup: payload["reply_markup"] = json.dumps(reply_markup)
    try: requests.post(f"{BASE_URL}/editMessageText", json=payload, timeout=10)
    except Exception: pass

def delete_message(chat_id, message_id):
    try: requests.post(f"{BASE_URL}/deleteMessage", json={"chat_id": chat_id, "message_id": message_id}, timeout=10)
    except Exception: pass

def send_photo(chat_id, photo_path, caption=""):
    if not os.path.exists(photo_path): return
    with open(photo_path, "rb") as photo:
        payload = {"chat_id": chat_id, "caption": caption, "parse_mode": "HTML"}
        try: requests.post(f"{BASE_URL}/sendPhoto", data=payload, files={"photo": photo}, timeout=20)
        except Exception: pass
