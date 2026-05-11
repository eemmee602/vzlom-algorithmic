# Vzlom Bridge — Advin

Pont API REST pour la mémoire partagée + bash (isolé des projets MDT).

## Démarrage

```bash
cd /home/vzlom-bridge
screen -S vzlom python3 server.py
```

## Endpoints

| Endpoint | Méthode | Description |
|---|---|---|
| `/health` | GET | Test connexion |
| `/memory` | GET | Voir les 50 dernières entrées |
| `/memory` | POST | Ajouter `{"content":"...", "source":"..."}` |
| `/bash` | POST | Exécuter `{"command":"ls -la"}` |

## Isolation

- 🔴 JAMAIS de `rm -rf /`, `sudo`, `mkfs`
- 🟢 Tout bash s'exécute dans `/home/vzlom-bridge/workspace/`
- 🟢 Le fichier mémoire est dans `data/memory.json`
- 🟢 Rien à voir avec les projets Pascal
