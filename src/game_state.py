"""
Etat d'une partie.

Contient tout ce qui definit une partie en cours et doit etre sauvegarde :
- `seed`         : graine aleatoire. Le monde (carte 25x25) en est entierement
                   deduit, donc on ne sauvegarde pas la carte : on la regenere.
- `time_seconds` : temps de jeu ecoule (avance en continu + par sauts).
- `player_x/y`   : position du joueur sur la carte (case courante).
- stats joueur   : energie, faim, bois, nourriture...
- `log`          : journal des dernieres actions.

`to_dict` / `from_dict` font la conversion avec le format de sauvegarde JSON.
"""
import random

from src import world

SAVE_VERSION = 2

SECONDS_PER_DAY = 24 * 60 * 60

# Heure a laquelle commence chaque nouvelle partie (6h du matin).
START_HOUR = 6

DIFFICULTIES = ["Facile", "Moyen", "Difficile"]
START_RESOURCES = {
    "Facile": {"food": 6, "wood": 4},
    "Moyen": {"food": 3, "wood": 2},
    "Difficile": {"food": 0, "wood": 0},
}


class GameState:
    def __init__(self, seed, name="Partie", difficulty="Moyen", time_seconds=0,
                 energy=100, hunger=0, wood=0, food=0, action_count=0,
                 log=None, player_x=None, player_y=None):
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

        # Carte regeneree depuis la graine (jamais sauvegardee).
        self.grid = world.generate_map(seed)

        # Position du joueur : fournie (sauvegarde) ou case centrale au hasard.
        if player_x is None or player_y is None:
            self.player_x, self.player_y = world.random_center_cell(seed)
        else:
            self.player_x = player_x
            self.player_y = player_y

    # ------------------------------------------------------------------ #
    # Creation
    # ------------------------------------------------------------------ #
    @classmethod
    def new_random(cls, name, difficulty="Moyen", seed=None):
        if seed is None:
            seed = random.randrange(1_000_000)
        if difficulty not in DIFFICULTIES:
            difficulty = "Moyen"
        state = cls(seed=seed, name=name, difficulty=difficulty)
        state.time_seconds = START_HOUR * 3600        # debut a 6h
        start = START_RESOURCES[difficulty]
        state.food = start["food"]
        state.wood = start["wood"]
        state.log.append(f"Nouvelle partie ({difficulty}).")
        return state

    # ------------------------------------------------------------------ #
    # Carte / deplacement
    # ------------------------------------------------------------------ #
    def current_zone(self):
        """Type de la zone ou se trouve le joueur."""
        return self.grid[self.player_y][self.player_x]

    def can_move(self, dx, dy):
        nx, ny = self.player_x + dx, self.player_y + dy
        return 0 <= nx < world.GRID_W and 0 <= ny < world.GRID_H

    def move(self, dx, dy):
        """Deplace le joueur d'une case si possible. Renvoie True si bouge."""
        if not self.can_move(dx, dy):
            return False
        self.player_x += dx
        self.player_y += dy
        return True

    # ------------------------------------------------------------------ #
    # Temps
    # ------------------------------------------------------------------ #
    @property
    def day(self):
        return self.time_seconds // SECONDS_PER_DAY + 1

    @property
    def clock(self):
        s = self.time_seconds % SECONDS_PER_DAY
        return f"{s // 3600:02d}:{(s % 3600) // 60:02d}:{s % 60:02d}"

    def advance_time(self, minutes):
        self.time_seconds += max(0, int(minutes)) * 60

    def tick(self, seconds=1):
        self.time_seconds += max(0, int(seconds))

    # ------------------------------------------------------------------ #
    # Journal
    # ------------------------------------------------------------------ #
    def add_log(self, message):
        self.log.append(message)
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
            "player_x": self.player_x,
            "player_y": self.player_y,
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
            player_x=data.get("player_x"),
            player_y=data.get("player_y"),
        )
