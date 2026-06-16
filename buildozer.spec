# Configuration Buildozer — fabrication de l'APK Android.
# Doc complete : https://buildozer.readthedocs.io

[app]

# Nom affiche de l'application sur le telephone
title = MobilPyton

# Nom interne du paquet (sans espace ni majuscule) + domaine (reverse-DNS)
package.name = mobilpyton
package.domain = org.ben

# Dossier source = racine du projet
source.dir = .

# Types de fichiers a embarquer dans l'APK
source.include_exts = py,png,jpg,jpeg,kv,atlas,ttf,wav,ogg,mp3

# Dossiers a NE PAS embarquer (evite un APK gonfle / des erreurs de build).
source.exclude_dirs = tests, bin, .buildozer, .git, .github, .claude, .venv, venv, __pycache__, saves

# Fichiers a ignorer
source.exclude_patterns = README.md, *.spec.tmp, *.pyc

# Version de l'application
version = 0.1

# Bibliotheques Python necessaires (ajouter ici : pillow, requests, etc.)
requirements = python3,kivy

# Orientation : paysage (le jeu se joue de cote). Le telephone bascule
# automatiquement en horizontal au lancement de l'app.
orientation = landscape

# Plein ecran : 0 = barre de statut visible, 1 = plein ecran
fullscreen = 0

# Icone et ecran de demarrage — a fournir plus tard dans assets/
# icon.filename = %(source.dir)s/assets/icon.png
# presplash.filename = %(source.dir)s/assets/presplash.png


[android]

# --- COMPATIBILITE (ne pas durcir sans raison) ---------------------------
# minapi = version Android MINIMALE acceptee. 21 = Android 5.0 (2014).
#   => l'app s'installe sur plus de 99 % des appareils Android actifs.
#   /!\ NE PAS AUGMENTER cette valeur : cela exclurait des telephones plus
#       anciens. La laisser basse = compatibilite maximale.
# api = version Android CIBLE (la plus recente testee). Une app qui cible
#   l'API 33 fonctionne quand meme sur Android 14/15+ (compatibilite
#   ascendante geree par Android). A monter seulement si un jour tu publies
#   sur le Play Store (qui exige une cible recente).
android.api = 33
android.minapi = 21

# Architectures processeur. arm64-v8a + armeabi-v7a = TOUS les telephones
# reels (64 bits modernes + 32 bits anciens). Ne pas retirer pour garder la
# compatibilite. (Optionnel : ajouter "x86_64" couvre les emulateurs et
# Chromebooks, mais alourdit l'APK et rallonge le build.)
android.archs = arm64-v8a, armeabi-v7a

# Permissions Android — decommenter/ajouter selon les besoins
# android.permissions = INTERNET, VIBRATE

# Accepter automatiquement les licences du SDK Android
android.accept_sdk_license = True


[buildozer]

# Niveau de detail des logs (2 = verbeux, pratique pour deboguer le build)
log_level = 2
warn_on_root = 1
