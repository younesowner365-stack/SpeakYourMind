# Speak Your Mind

Application FastAPI de questionnaire RH anonyme.

## Installation Windows

Dans le dossier du projet :

```powershell
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

Ouvrir :

- Questionnaire : http://127.0.0.1:8000
- Administration : http://127.0.0.1:8000/admin
- Export Excel : http://127.0.0.1:8000/admin/export.xlsx

## Données

Les réponses sont stockées localement dans `responses.db`.

L'application ne demande ni nom, ni e-mail, ni matricule.

Important : un serveur web ou un hébergeur peut conserver des journaux techniques contenant les adresses IP. Pour une utilisation RH officielle, demander à l'administrateur de désactiver ou minimiser les journaux d'accès.
