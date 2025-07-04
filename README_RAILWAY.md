# 🚂 Déployer Voralith sur Railway.app

## Guide étape par étape pour héberger votre bot Discord 24/7

### 1. Créer un compte Railway
1. Allez sur **https://railway.app**
2. Cliquez sur "Login" puis "Sign up with GitHub"
3. Connectez votre compte GitHub
4. Vérifiez votre email si demandé

### 2. Créer un nouveau projet
1. Dans Railway, cliquez sur "New Project"
2. Choisissez "Deploy from GitHub repo"
3. Connectez votre compte GitHub si pas déjà fait
4. Sélectionnez ce repository (votre bot Voralith)

### 3. Configurer les variables d'environnement
Dans Railway, allez dans votre projet puis "Variables" et ajoutez :

```
DISCORD_TOKEN=votre_token_discord_ici
DISCORD_CLIENT_SECRET=votre_client_secret_ici
DATABASE_URL=postgresql://railway_postgres_url_ici
```

**Important :** Railway vous donnera automatiquement une base de données PostgreSQL

### 4. Configurer la base de données
1. Dans Railway, cliquez sur "New" puis "Database" puis "PostgreSQL"
2. Railway va créer automatiquement la variable `DATABASE_URL`
3. Votre bot utilisera automatiquement cette base de données

### 5. Déployer
1. Railway va automatiquement déployer votre bot
2. Attendez que le build soit terminé (status vert)
3. Votre bot sera en ligne 24/7 !

### 6. Vérifier le déploiement
- Allez dans "Deployments" pour voir les logs
- Vérifiez que votre bot est en ligne sur Discord
- Testez une commande comme `/vouch`

## Avantages de Railway :
✅ **24/7 uptime garanti**
✅ **Base de données PostgreSQL incluse**
✅ **Redémarrages automatiques**
✅ **Plan gratuit généreux**
✅ **Déploiement automatique depuis GitHub**
✅ **Logs en temps réel**
✅ **Scaling automatique**

## Notes importantes :
- Railway redémarre automatiquement votre bot en cas de crash
- Les variables d'environnement sont sécurisées
- Vous gardez toutes les fonctionnalités de votre bot
- La base de données PostgreSQL est persistante

## Support :
Si vous avez des questions, vérifiez les logs dans Railway ou contactez le support Railway.