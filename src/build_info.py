"""
Version et numero de build de l'application.

En LOCAL, les valeurs restent celles ci-dessous ("dev"). Lors d'un build dans
le cloud, GitHub Actions remplace automatiquement ce fichier (etape
"Estampiller la version" dans .github/workflows/build-apk.yml) :

- BUILD   : numero de build, +1 a CHAQUE build (= versionCode Android).
- VERSION : version lisible a 4 segments, ex. 0.0.1.0 -> 0.0.1.1 -> 0.0.1.2...
            (deduite du numero de build, voir le workflow).
- SHA     : debut du commit correspondant.

Le menu affiche VERSION + BUILD pour verifier d'un coup d'oeil quelle version
est reellement installee sur le telephone.
"""
BUILD = "dev"
VERSION = "0.0.0.0"
SHA = ""
