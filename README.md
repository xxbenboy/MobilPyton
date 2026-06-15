# MobilPyton

Jeu mobile en Python, construit avec **Kivy** et compile en APK Android avec **Buildozer**.

## Structure du projet

```
MobilPyton/
├── main.py              # Point d'entree (obligatoire pour Buildozer)
├── buildozer.spec       # Configuration du build Android (APK)
├── requirements.txt     # Dependances pour developper sur PC
├── .gitignore
├── src/
│   ├── game.py          # Application + navigation entre ecrans
│   └── screens/
│       ├── menu_screen.py   # Ecran d'accueil (Jouer / Quitter)
│       └── game_screen.py   # Ecran de jeu (vide, a construire)
└── assets/
    ├── images/          # Sprites, fonds, icones
    ├── sounds/          # Sons et musiques
    └── fonts/           # Polices personnalisees
```

## 1. Tester sur PC

```powershell
# (recommande) Creer un environnement virtuel
py -m venv .venv
.venv\Scripts\Activate.ps1

# Installer Kivy
py -m pip install -r requirements.txt

# Lancer le jeu
py main.py
```

Une fenetre au format telephone (portrait) doit s'ouvrir sur le menu.

> **Resolution.** La resolution de base est celle d'un telephone, 2340x1080,
> utilisee en portrait (1080 de large x 2340 de haut). Sur PC, la fenetre est
> automatiquement reduite pour tenir dans l'ecran, en gardant ces proportions.
> Toute l'interface est en proportions (boutons, positions) et les polices
> suivent la taille de la fenetre : l'affichage s'ajuste donc a n'importe
> quelle resolution (et sur Android, c'est l'ecran reel qui est utilise).

## 2. Installer sur le telephone (APK Android)

Buildozer **ne fonctionne que sous Linux** : sous Windows, on passe par **WSL**.

➡️ **Guide complet pas-a-pas : [INSTALL_ANDROID.md](INSTALL_ANDROID.md)**
(installation de WSL, build de l'APK, et installation sur le telephone).

En resume :
```bash
# Dans WSL / Ubuntu, projet copie dans le systeme Linux
buildozer android debug
```
L'APK genere arrive dans `bin/`. On le copie sur le telephone puis on l'ouvre
pour l'installer.

> Le premier build telecharge le SDK/NDK Android (long, ~plusieurs Go).

## Sauvegarde

Chaque partie a **son propre fichier** de sauvegarde, range dans
`saves/` (sous-dossier de `App.user_data_dir`, gere automatiquement sur PC
comme sur Android). On garde **une seule sauvegarde par partie** : elle est
ecrasee a chaque fois par l'etat le plus recent.

- **Nouvelle partie** : on choisit un **nom** et une **difficulte**
  (Facile / Moyen / Difficile, qui change les ressources de depart).
- **Charger** : liste toutes les sauvegardes (la plus recente en haut), avec
  chargement et suppression. Le bouton est grise s'il n'y a aucune partie.
- **Sauvegarde automatique**, declenchee :
  - periodiquement (toutes les 30 s tant qu'on est en jeu),
  - apres chaque action,
  - juste avant la fermeture (fenetre fermee, app arretee, ou mise en
    arriere-plan sur Android).

L'ecriture est *atomique* (fichier temporaire + renommage) : une coupure en
pleine sauvegarde n'abime pas la sauvegarde precedente. Seule la **graine**
aleatoire est stockee pour la carte : le monde est regenere a l'identique au
chargement (jeu "generatif").

Fichiers : `src/game_state.py` (etat), `src/save_manager.py` (lecture/
ecriture), `src/game.py` (hooks de fermeture).

## Prochaines etapes

- Choisir le type de jeu et coder la boucle de jeu dans `game_screen.py`
- Ajouter une icone (`assets/icon.png`) et la declarer dans `buildozer.spec`
- Ajouter les sprites/sons dans `assets/`
