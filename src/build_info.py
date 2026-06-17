"""
Numero de build de l'application.

En LOCAL, la valeur reste "dev". Lors d'un build dans le cloud, GitHub Actions
remplace automatiquement ce fichier par le vrai numero de build + le commit
(voir l'etape "Estampiller la version" dans .github/workflows/build-apk.yml).

Le menu affiche ce numero pour qu'on puisse verifier d'un coup d'oeil quelle
version est reellement installee sur le telephone.
"""
BUILD = "dev"
SHA = ""
