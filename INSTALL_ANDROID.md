# Construire l'APK et l'installer sur ton telephone

Ce guide explique comment transformer le projet en fichier **APK** (l'app
Android) puis l'installer sur ton telephone.

> **Important** : l'outil de build (**Buildozer**) ne fonctionne **que sous
> Linux**. Sous Windows 11, on utilise **WSL** (un Linux integre a Windows).
> C'est gratuit et officiel Microsoft.

---

## Etape 1 — Installer WSL (a faire une seule fois)

1. Ouvrir **PowerShell en administrateur** (clic droit sur le menu Demarrer →
   « Terminal (administrateur) »).
2. Lancer :
   ```powershell
   wsl --install -d Ubuntu
   ```
3. **Redemarrer** le PC si demande.
4. Au premier lancement, Ubuntu demande de creer un **nom d'utilisateur** et un
   **mot de passe** Linux (a retenir).

Tu as maintenant un terminal Ubuntu. Les commandes suivantes se tapent
**dans Ubuntu** (pas dans PowerShell).

---

## Etape 2 — Installer les outils de build (une seule fois)

Dans le terminal Ubuntu :

```bash
# Mettre Ubuntu a jour
sudo apt update && sudo apt upgrade -y

# Dependances systeme pour Buildozer / python-for-android
sudo apt install -y git zip unzip openjdk-17-jdk python3-pip python3-venv \
  autoconf libtool pkg-config zlib1g-dev libncurses-dev cmake libffi-dev \
  libssl-dev build-essential ccache libltdl-dev

# Buildozer + Cython (version connue pour bien marcher)
pip3 install --user buildozer "cython==0.29.36"

# Rendre la commande buildozer accessible
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

---

## Etape 3 — Copier le projet dans Linux

Le build est **beaucoup plus rapide et fiable** si le projet est dans le
systeme de fichiers Linux (et non sur `/mnt/c`). On copie donc le projet :

```bash
cp -r "/mnt/c/Users/ben/Documents/MobilPyton" ~/MobilPyton
cd ~/MobilPyton
```

> A refaire (ou utiliser `cp -r` a nouveau) chaque fois que tu modifies le code
> sous Windows et veux reconstruire.

---

## Etape 4 — Construire l'APK

```bash
buildozer android debug
```

- **Le premier build telecharge le SDK et le NDK Android (~1,5 a 3 Go)** et peut
  prendre **20 a 60 minutes**. Les builds suivants sont bien plus rapides.
- Si une licence Android est demandee, elle est acceptee automatiquement
  (`android.accept_sdk_license = True` dans `buildozer.spec`).

Quand c'est fini, l'APK se trouve dans le dossier `bin/` :

```
bin/mobilpyton-0.1-arm64-v8a_armeabi-v7a-debug.apk
```

Pour le recopier vers Windows (par ex. sur le Bureau) :

```bash
cp bin/*.apk "/mnt/c/Users/ben/Desktop/"
```

---

## Etape 5 — Installer l'APK sur le telephone

### Methode simple : par fichier (recommandee)

1. Transfere l'APK sur le telephone : **cable USB**, Google Drive, ou
   par email a toi-meme.
2. Sur le telephone, ouvre le fichier `.apk` (via l'appli « Fichiers »).
3. Android demande d'**autoriser l'installation d'applis inconnues** pour
   l'appli qui ouvre le fichier : accepte (c'est normal pour une app installee
   hors du Play Store).
4. Appuie sur **Installer**. L'app **MobilPyton** apparait dans le tiroir
   d'applications.

### Methode developpeur : par cable (ADB)

1. Sur le telephone : Parametres → A propos → appuie **7 fois** sur « Numero de
   build » pour activer le **mode developpeur**.
2. Parametres → Options pour les developpeurs → active **Debogage USB**.
3. Installe les *platform-tools* Android (qui contiennent `adb`) sur Windows,
   branche le telephone en USB, accepte la demande sur le telephone, puis :
   ```powershell
   adb install "C:\Users\ben\Desktop\mobilpyton-0.1-arm64-v8a_armeabi-v7a-debug.apk"
   ```

---

## Mettre a jour l'app plus tard

1. Modifie le code.
2. Augmente le numero de version dans `buildozer.spec` (ex. `version = 0.2`).
3. Recopie le projet dans Linux, relance `buildozer android debug`.
4. Reinstalle le nouvel APK (il met a jour l'app existante).

---

## En cas de probleme

- **Build qui echoue la 1re fois** : relance simplement `buildozer android debug`
  (un telechargement a parfois echoue). En dernier recours :
  `buildozer android clean` puis rebuild.
- **« buildozer : command not found »** : refais `source ~/.bashrc` ou rouvre
  Ubuntu (le PATH n'etait pas charge).
- **L'app se ferme au demarrage sur le telephone** : branche le telephone et
  regarde les logs avec `buildozer android logcat` (ou `adb logcat`).

---

## Alternative sans WSL : build dans le cloud

Si tu prefereres ne rien installer, on peut configurer **GitHub Actions** :
tu envoies le code sur GitHub, un serveur construit l'APK automatiquement, et
tu telecharges le fichier. Dis-le moi et je mets en place le fichier de
configuration.
