"""
Etat d'une partie.

C'est l'objet qui contient TOUT ce qui definit une partie en cours et qui
doit etre sauvegarde puis recharge a l'identique :

- `seed`        : la graine aleatoire. Le jeu etant "generatif", c'est elle
                  qui determine la carte et les elements de la partie. Memes
                  graine => meme monde. On la sauvegarde pour pouvoir
                  regenerer le monde sans stocker tous ses details.
- `time_seconds`: le temps de jeu ecoule (en secondes). Il avance en
                  continu (temps reel) ET par sauts a chaque action, et ne
                  peut jamais reculer.
- `day`         : le jour courant (deduit du temps).
- stats du joueur : energie, faim, bois, nourriture...
- `log`         : un petit journal des dernieres actions.

`to_dict` / `from_dict` font la conversion avec le format de sauvegarde
(un simple dictionnaire JSON).
"""
import random

# Format de sauvegarde : si un jour on change la structure des donnees,
# on incremente ce numero pour gerer les anciennes sauvegardes.
SAVE_VERSION = 1

SECONDS_PER_DAY = 24 * 60 * 60

# Heure a laquelle commence chaque nouvelle partie (6h du matin).
START_HOUR = 6

# Biomes possibles d'une tuile de carte (cote "generatif").
BIOMES = ["Foret", "Plaine", "Riviere", "Montagne", "Marais", "Ruines"]

# Difficultes proposees. Pour chaque difficulte : ressources de depart
# (nourriture, bois). Plus c'est facile, plus on commence avec des reserves.
DIFFICULTIES = ["Facile", "Moyen", "Difficile"]
START_RESOURCES = {
    "Facile": {"food": 6, "wood": 4},
    "Moyen": {"food": 3, "wood": 2},
    "Difficile": {"food": 0, "wood": 0},
}


class GameState:
    def __init__(self, seed, name="Partie", difficulty="Moyen", time_seconds=0,
                 energy=100, hunger=0, wood=0, food=0, action_count=0,
                 log=None, map_biomes=None):
        self.seed = seed
        self.name = name
        self.difficulty = difficulty
        self.time_seconds = time_seconds
        self.energy = energy
        self.hunger = hunger
        self.wood = wood
        self.food = food
        self.action_count = action_count
        self.log = log if log is not None else []
        # La carte est regeneree depuis la graine si absente (sauvegarde
        # ancienne ou nouvelle partie).
        self.map_biomes = map_biomes if map_biomes is not None \
            else self._generate_map()

    # ------------------------------------------------------------------ #
    # Creation
    # ------------------------------------------------------------------ #
    @classmethod
    def new_random(cls, name, difficulty="Moyen", seed=None):
        """Demarre une nouvelle partie generee aleatoirement."""
        if seed is None:
            seed = random.randrange(1_000_000)
        if difficulty not in DIFFICULTIES:
            difficulty = "Moyen"
        state = cls(seed=seed, name=name, difficulty=difficulty)
        # Chaque partie commence a 6h du matin.
        state.time_seconds = START_HOUR * 3600
        # Ressources de depart selon la difficulte.
        start = START_RESOURCES[difficulty]
        state.food = start["food"]
        state.wood = start["wood"]
        state.log.append(f"Nouvelle partie ({difficulty}).")
        return state

    def _generate_map(self):
        """Genere une petite carte 3x3 a partir de la graine."""
        rng = random.Random(self.seed)
        return [rng.choice(BIOMES) for _ in range(9)]

    # ------------------------------------------------------------------ #
    # Temps
    # ------------------------------------------------------------------ #
    @property
    def day(self):
        return self.time_seconds // SECONDS_PER_DAY + 1

    @property
    def clock(self):
        """Heure de la journee au format HH:MM:SS."""
        s = self.time_seconds % SECONDS_PER_DAY
        return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"

    def advance_time(self, minutes):
        """Saut de temps (ex. apres une action). Ne recule jamais."""
        self.time_seconds += max(0, int(minutes)) * 60

    def tick(self, seconds=1):
        """Ecoulement continu du temps (temps reel). Ne recule jamais."""
        self.time_seconds += max(0, int(seconds))

    # ------------------------------------------------------------------ #
    # Journal
    # ------------------------------------------------------------------ #
    def add_log(self, message):
        self.log.append(message)
        # On ne garde que les 6 dernieres lignes pour ne pas grossir sans fin.
        self.log = self.log[-6:]

    # ------------------------------------------------------------------ #
    # Sauvegarde / chargement
    # ------------------------------------------------------------------ #
    def to_dict(self):
        return {
            "version": SAVE_VERSION,
            "seed": self.seed,
            "name": self.name,
            "difficulty": self.difficulty,
            "time_seconds": self.time_seconds,
            "energy": self.energy,
            "hunger": self.hunger,
            "wood": self.wood,
            "food": self.food,
            "action_count": self.action_count,
            "log": self.log,
            "map_biomes": self.map_biomes,
        }

    @classmethod
    def from_dict(cls, data):
        # Compat : anciennes sauvegardes stockaient `time_minutes`.
        if "time_seconds" in data:
            time_seconds = data["time_seconds"]
        else:
            time_seconds = data.get("time_minutes", 0) * 60
        return cls(
            seed=data["seed"],
            name=data.get("name", "Partie"),
            difficulty=data.get("difficulty", "Moyen"),
            time_seconds=time_seconds,
            energy=data.get("energy", 100),
            hunger=data.get("hunger", 0),
            wood=data.get("wood", 0),
            food=data.get("food", 0),
            action_count=data.get("action_count", 0),
            log=data.get("log", []),
            map_biomes=data.get("map_biomes"),
        )
