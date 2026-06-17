"""
Gestionnaire audio centralise.

Pour l'instant le jeu n'a pas encore de sons, mais ce gestionnaire prepare
le terrain : il MEMORISE les reglages audio (volume general + son coupe) et
les SAUVEGARDE sur le telephone pour qu'ils soient conserves d'une session a
l'autre.

Les reglages sont ranges dans un petit fichier `settings.json` du dossier
prive de l'app (`App.user_data_dir`, accessible en ecriture sur PC comme sur
Android), a cote des sauvegardes de parties.

Quand des sons seront ajoutes (dans assets/sounds/), il suffira d'appeler
`play(nom)` ici : le volume et le mode "muet" seront automatiquement
respectes. Si la lecture audio n'est pas disponible (ex. certains
environnements), tout degrade proprement sans planter.
"""
import json
import os

# Chargement audio de Kivy : optionnel. Sur certains environnements (build de
# test, machine sans peripherique son), l'import peut echouer : on continue
# sans audio plutot que de planter l'application.
try:
    from kivy.core.audio import SoundLoader
except Exception:                       # pragma: no cover - depend de l'env
    SoundLoader = None


class AudioManager:
    def __init__(self, directory, filename="settings.json"):
        self._path = os.path.join(directory, filename)

        # Valeurs par defaut (avant lecture du fichier).
        self.volume = 1.0       # 0.0 (silence) a 1.0 (max)
        self.muted = False      # True = son completement coupe

        self._sounds = {}       # cache des sons charges (nom -> Sound)

        self._load()

    # ------------------------------------------------------------------ #
    # Persistance
    # ------------------------------------------------------------------ #
    def _load(self):
        """Relit les reglages sauvegardes (ignore silencieusement si absent)."""
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.volume = float(data.get("volume", self.volume))
            self.muted = bool(data.get("muted", self.muted))
        except (json.JSONDecodeError, KeyError, ValueError, OSError):
            pass
        # Securite : volume toujours dans [0, 1].
        self.volume = max(0.0, min(1.0, self.volume))

    def _save(self):
        """Ecrit les reglages de facon atomique (jamais de fichier corrompu)."""
        tmp_path = self._path + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump({"volume": self.volume, "muted": self.muted}, f,
                          ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self._path)
        except OSError:
            pass

    # ------------------------------------------------------------------ #
    # Reglages (appeles par l'ecran Parametres)
    # ------------------------------------------------------------------ #
    def set_volume(self, volume):
        """Definit le volume general (0.0 a 1.0) et le sauvegarde."""
        self.volume = max(0.0, min(1.0, float(volume)))
        self._apply_to_loaded()
        self._save()

    def set_muted(self, muted):
        """Coupe / retablit completement le son, et le sauvegarde."""
        self.muted = bool(muted)
        self._apply_to_loaded()
        self._save()

    def effective_volume(self):
        """Volume reellement applique (0 si le son est coupe)."""
        return 0.0 if self.muted else self.volume

    # ------------------------------------------------------------------ #
    # Lecture de sons (pret pour quand des sons seront ajoutes)
    # ------------------------------------------------------------------ #
    def _apply_to_loaded(self):
        vol = self.effective_volume()
        for sound in self._sounds.values():
            if sound:
                sound.volume = vol

    def load(self, name, path):
        """Charge (et met en cache) un son. Renvoie None si indisponible."""
        if SoundLoader is None:
            return None
        if name not in self._sounds:
            try:
                self._sounds[name] = SoundLoader.load(path)
            except Exception:           # pragma: no cover - depend de l'env
                self._sounds[name] = None
        return self._sounds[name]

    def play(self, name):
        """Joue un son deja charge, en respectant volume et mode muet."""
        sound = self._sounds.get(name)
        if sound and not self.muted and self.volume > 0:
            sound.volume = self.effective_volume()
            sound.play()
