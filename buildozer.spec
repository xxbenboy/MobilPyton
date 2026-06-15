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

# Orientation : portrait pour un jeu mobile vertical
orientation = portrait

# Plein ecran : 0 = barre de statut visible, 1 = plein ecran
fullscreen = 0

# Icone et ecran de demarrage — a fournir plus tard dans assets/
# icon.filename = %(source.dir)s/assets/icon.png
# presplash.filename = %(source.dir)s/assets/presplash.png


[android]

# Versions Android visees
android.api = 33
android.minapi = 21

# Architectures processeur (couvre la quasi-totalite des telephones)
android.archs = arm64-v8a, armeabi-v7a

# Permissions Android — decommenter/ajouter selon les besoins
# android.permissions = INTERNET, VIBRATE

# Accepter automatiquement les licences du SDK Android
android.accept_sdk_license = True


[buildozer]

# Niveau de detail des logs (2 = verbeux, pratique pour deboguer le build)
log_level = 2
warn_on_root = 1
