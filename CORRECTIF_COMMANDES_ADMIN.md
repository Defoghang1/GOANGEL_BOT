# Correctif v2 : commandes admin jamais visibles dans un menu Telegram

- Aucune commande admin n'est plus enregistrée dans un menu Telegram (même pas pour l'admin).
  L'admin tape /admin pour obtenir la liste. (ADMIN_MENU=1 réactive un menu limité au chat admin.)
- Purge au démarrage : tous scopes x langues + menus par chat de tous les utilisateurs connus.
- /start d'un non-admin : efface tout menu résiduel propre à son chat (auto-réparation).
- verify_menus() relit Telegram après reconstruction et re-purge en cas de fuite.
- Tests : python -m unittest discover -s tests -v (14 tests, aussi lancés dans le workflow).

DÉPLOIEMENT : pousser ces fichiers sur GitHub, lancer le workflow (Run workflow), vérifier dans
les logs : "Vérification des menus OK". Arrêter toute autre instance du bot (ancien hébergeur).
Tester avec un AUTRE compte Telegram que l'admin, après avoir fermé/rouvert le chat.
