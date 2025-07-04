# 🚀 Guide de déploiement Railway.app - Voralith Bot

## Méthode 1 : Via GitHub (Recommandée)

### Étape 1 : Préparer GitHub
1. Allez sur **https://github.com**
2. Créez un nouveau repository public appelé "voralith-bot"
3. Uploadez tous vos fichiers du projet Replit

### Étape 2 : Railway Setup
1. **https://railway.app** → "Sign up with GitHub"
2. "New Project" → "Deploy from GitHub repo"
3. Sélectionnez votre repository "voralith-bot"

### Étape 3 : Variables d'environnement
Dans Railway, section "Variables", ajoutez :
```
DISCORD_TOKEN=votre_token_bot
DISCORD_CLIENT_SECRET=votre_client_secret
```

### Étape 4 : Base de données
1. "New" → "Database" → "PostgreSQL"
2. Railway crée automatiquement `DATABASE_URL`

### Étape 5 : Déploiement
- Railway build automatiquement
- Votre bot sera en ligne 24/7 !

## Méthode 2 : Via CLI Railway

### Installation
```bash
npm install -g @railway/cli
railway login
```

### Déploiement
```bash
railway new
railway add --database postgresql
railway deploy
```

## ✅ Résultat attendu
- Bot en ligne 24/7
- Base de données PostgreSQL persistante  
- Redémarrages automatiques
- Logs en temps réel
- Aucune mise en veille

## 🆘 Support
- Logs : Railway dashboard → "Deployments"
- Variables : Railway dashboard → "Variables"
- Base de données : Railway dashboard → "PostgreSQL"

**Temps total : 5-10 minutes pour un déploiement complet**