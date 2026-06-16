"""
Gestionnaire de sauvegardes (plusieurs parties).

Chaque partie a SON fichier de sauvegarde (un seul), nomme d'apres le nom
de la partie. On garde donc toujours UNE sauvegarde par partie : a chaque
sauvegarde, le fichier de cette partie est ecrase par l'etat le plus
recent.

Les fichiers sont ranges dans un sous-dossier `saves/` du dossier prive de
l'app (`App.user_data_dir`, accessible en ecriture sur PC comme Android).

Ecriture ATOMIQUE : ecriture dans un fichier temporaire puis renommage,
pour ne jamais corrompre une sauvegarde existante si l'app est coupee.
"""
import json
import os
import re

from src.game_state import GameState

# Nombre maximal de parties sauvegardees en meme temps.
MAX_SAVES = 5


def slugify(name):
    """Transforme un nom de partie en nom de fichier sur (sans extension)."""
    slug = re.sub(r"[^A-Za-z0-9_-]+", "_", name.strip()).strip("_").lower()
    return slug or "partie"


class SaveManager:
    def __init__(self, directory, subdir="saves"):
        self.directory = os.path.join(directory, subdir)
        os.makedirs(self.directory, exist_ok=True)

    def _path(self, name):
        return os.path.join(self.directory, slugify(name) + ".json")

    def exists(self, name):
        return os.path.isfile(self._path(name))

    def has_any(self):
        """Y a-t-il au moins une sauvegarde ?"""
        return any(f.endswith(".json") for f in os.listdir(self.directory))

    def count(self):
        """Nombre de parties sauvegardees."""
        return sum(1 for f in os.listdir(self.directory) if f.endswith(".json"))

    def is_full(self):
        """A-t-on atteint la limite de parties (MAX_SAVES) ?"""
        return self.count() >= MAX_SAVES

    def save(self, state):
        """Ecrit (ou ecrase) la sauvegarde de cette partie, de facon atomique."""
        path = self._path(state.name)
        tmp_path = path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(state.to_dict(), f, ensure_ascii=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)

    def load(self, name):
        """Recharge une partie par son nom, ou None si absente/illisible."""
        return self._load_path(self._path(name))

    def _load_path(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return GameState.from_dict(json.load(f))
        except (json.JSONDecodeError, KeyError, OSError):
            return None

    def delete(self, name):
        path = self._path(name)
        if os.path.isfile(path):
            os.remove(path)

    def list_saves(self):
        """Liste toutes les sauvegardes, de la plus recente a la plus ancienne.

        Chaque entree est un dict pret a afficher :
        {name, difficulty, day, clock, mtime}.
        """
        entries = []
        for filename in os.listdir(self.directory):
            if not filename.endswith(".json"):
                continue
            path = os.path.join(self.directory, filename)
            state = self._load_path(path)
            if state is None:
                continue
            entries.append({
                "name": state.name,
                "difficulty": state.difficulty,
                "day": state.day,
                "clock": state.clock,
                "mtime": os.path.getmtime(path),
            })
        # Tri par date de modification : la plus recente en premier.
        entries.sort(key=lambda e: e["mtime"], reverse=True)
        return entries
