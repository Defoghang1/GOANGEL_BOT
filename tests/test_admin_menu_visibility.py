import json
import os
import sys
import unittest
from unittest import mock

os.environ.setdefault("TELEGRAM_BOT_TOKEN", "123456:TEST")
os.environ.setdefault("TELEGRAM_ADMIN_ID", "999")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402
import telegram_api  # noqa: E402
import handlers  # noqa: E402

ADMIN_ID = config.ADMIN_ID
ADMIN_NAMES = set(config.ADMIN_COMMAND_NAMES)
PUBLIC_NAMES = {c["command"] for c in config.PUBLIC_COMMANDS}


class FakeTelegram:
    """Simule le stockage des menus de commandes côté Telegram."""

    def __init__(self):
        self.store = {}

    @staticmethod
    def _key(payload):
        scope = payload.get("scope", {"type": "default"})
        return json.dumps(scope, sort_keys=True) + "|" + payload.get("language_code", "")

    def post(self, method, payload, timeout=15):
        if method == "setMyCommands":
            self.store[self._key(payload)] = list(payload["commands"])
            return True
        if method == "deleteMyCommands":
            self.store.pop(self._key(payload), None)
            return True
        if method == "getMyCommands":
            return list(self.store.get(self._key(payload), []))
        return True

    def visible_to(self, chat_id, lang=""):
        """Ordre de priorité Telegram (simplifié pour un chat privé)."""
        for scope in (
            {"type": "chat", "chat_id": chat_id},
            {"type": "all_private_chats"},
            {"type": "default"},
        ):
            for l in ((lang, "") if lang else ("",)):
                key = json.dumps(scope, sort_keys=True) + "|" + l
                if key in self.store:
                    return {c["command"] for c in self.store[key]}
        return set()


class MenuVisibilityTests(unittest.TestCase):
    def setUp(self):
        self.fake = FakeTelegram()
        patcher = mock.patch.object(telegram_api, "_post", side_effect=self.fake.post)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_public_list_has_no_admin_command(self):
        self.assertFalse(ADMIN_NAMES & PUBLIC_NAMES)

    def test_clean_install(self):
        self.assertTrue(telegram_api.initialize_menus())
        self.assertEqual(self.fake.visible_to(12345), PUBLIC_NAMES)
        self.assertFalse(self.fake.visible_to(12345) & ADMIN_NAMES)

    def test_default_no_admin_command_even_for_admin(self):
        telegram_api.initialize_menus()
        self.assertFalse(self.fake.visible_to(ADMIN_ID) & ADMIN_NAMES)
        for cmds in self.fake.store.values():
            self.assertFalse({c["command"] for c in cmds} & ADMIN_NAMES)

    def test_optional_admin_menu_only_in_admin_chat(self):
        with mock.patch.object(telegram_api, "ADMIN_MENU_ENABLED", True):
            telegram_api.initialize_menus()
        self.assertTrue(ADMIN_NAMES <= self.fake.visible_to(ADMIN_ID))
        self.assertFalse(self.fake.visible_to(12345) & ADMIN_NAMES)

    def test_stale_per_chat_menu_of_known_user_is_purged(self):
        stale = config.PUBLIC_COMMANDS + config.ADMIN_ONLY_COMMANDS
        self.fake.post("setMyCommands", {"commands": stale, "scope": {"type": "chat", "chat_id": 777}})
        self.fake.post("setMyCommands", {"commands": stale, "scope": {"type": "chat", "chat_id": 777}, "language_code": "fr"})
        self.assertTrue(self.fake.visible_to(777) & ADMIN_NAMES)
        with mock.patch.object(telegram_api, "_known_chat_ids", return_value=[777]):
            self.assertTrue(telegram_api.initialize_menus())
        self.assertFalse(self.fake.visible_to(777) & ADMIN_NAMES)
        self.assertFalse(self.fake.visible_to(777, "fr") & ADMIN_NAMES)

    def test_start_purges_chat_menu_for_non_admin(self):
        stale = config.PUBLIC_COMMANDS + config.ADMIN_ONLY_COMMANDS
        self.fake.post("setMyCommands", {"commands": stale, "scope": {"type": "chat", "chat_id": 555}})
        update = {"message": {"from": {"id": 555}, "chat": {"id": 555}, "text": "/start"}}
        with mock.patch.object(handlers, "send_message"), \
             mock.patch.object(handlers, "save_json"):
            handlers._handle_public_command("/start", [], update, {}, [])
        self.assertFalse(self.fake.visible_to(555) & ADMIN_NAMES)

    def test_leftover_menus_are_purged(self):
        """Anciens menus (BotFather, autres scopes, langues) contenant des commandes admin."""
        leaked = config.PUBLIC_COMMANDS + config.ADMIN_ONLY_COMMANDS
        for scope in ({"type": "default"}, {"type": "all_private_chats"},
                      {"type": "all_group_chats"}, {"type": "all_chat_administrators"}):
            self.fake.post("setMyCommands", {"commands": leaked, "scope": scope})
            self.fake.post("setMyCommands", {"commands": leaked, "scope": scope, "language_code": "fr"})
        self.assertTrue(self.fake.visible_to(12345, "fr") & ADMIN_NAMES)  # le bug initial
        self.assertTrue(telegram_api.initialize_menus())
        for lang in ("", "fr", "en"):
            self.assertFalse(self.fake.visible_to(12345, lang) & ADMIN_NAMES, lang)
        self.assertTrue(telegram_api.verify_menus())

    def test_verify_detects_leak(self):
        self.fake.post("setMyCommands", {
            "commands": [{"command": "confirm", "description": "x"}],
            "scope": {"type": "all_private_chats"}, "language_code": "en"})
        self.assertFalse(telegram_api.verify_menus())

    def test_admin_scope_is_only_chat_scope_with_admin_commands(self):
        with mock.patch.object(telegram_api, "ADMIN_MENU_ENABLED", True):
            telegram_api.initialize_menus()
        for key, cmds in self.fake.store.items():
            if {c["command"] for c in cmds} & ADMIN_NAMES:
                scope = json.loads(key.split("|")[0])
                self.assertEqual(scope, {"type": "chat", "chat_id": ADMIN_ID})


class CommandParsingTests(unittest.TestCase):
    def test_is_admin_command_variants(self):
        for c in ("/confirm", "/CONFIRM", "/confirm@GoAngelBot", "confirm"):
            self.assertTrue(config.is_admin_command(c), c)
        for c in ("/start", "/tarifs", "/myid", "/start@GoAngelBot"):
            self.assertFalse(config.is_admin_command(c), c)

    def test_parse_command_strips_bot_suffix(self):
        self.assertEqual(handlers._parse_command("/confirm@GoAngelBot ORD-1"), ("/confirm", ["ORD-1"]))

    def test_non_admin_cannot_run_admin_command(self):
        update = {"message": {"from": {"id": 42, "username": "x"}, "chat": {"id": 42},
                              "text": "/confirm@GoAngelBot ORD-1"}}
        with mock.patch.object(handlers, "send_message"), \
             mock.patch("security.send_message"), \
             mock.patch("security.load_json", return_value={}), \
             mock.patch("security.save_json_locked"):
            cmd, args = handlers._parse_command(update["message"]["text"])
            self.assertTrue(config.is_admin_command(cmd))
            self.assertFalse(handlers.handle_admin_security(update, cmd, config.DEFAULT_NOTIF_CHANNEL))


class AdminCommandListTests(unittest.TestCase):
    def test_admin_command_lists_commands_for_admin_only(self):
        update = {"message": {"from": {"id": ADMIN_ID}, "chat": {"id": ADMIN_ID}, "text": "/admin"}}
        with mock.patch.object(handlers, "send_message") as sm, \
             mock.patch("security.log_admin_action"), mock.patch.object(handlers, "log_admin_action"):
            self.assertTrue(handlers._handle_admin_command("/admin", [], update, {}, ADMIN_ID))
        self.assertIn("/confirm", sm.call_args[0][1])

    def test_admin_command_refused_for_user(self):
        update = {"message": {"from": {"id": 42}, "chat": {"id": 42}, "text": "/admin"}}
        with mock.patch.object(handlers, "send_message") as sm, \
             mock.patch("security.send_message"), mock.patch("security.load_json", return_value={}), \
             mock.patch("security.save_json_locked"):
            self.assertFalse(handlers._handle_admin_command("/admin", [], update, {}, ADMIN_ID))
        sm.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
