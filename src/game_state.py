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
from src import items

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

# Derive naturelle des stats, PAR MINUTE de jeu (le temps qui passe).
HUNGER_RATE = 0.05    # on a de plus en plus faim
THIRST_RATE = 0.08    # on a soif plus vite
SLEEP_RATE = 0.07     # on devient fatigue (le sommeil baisse)
ENERGY_DRAIN = 0.02   # legere perte d'energie passive
HEALTH_RATE = 0.05    # la vie baisse si faim/soif au max ou sommeil/energie a 0

# On ne peut dormir (Se reposer) que si l'energie est <= a ce seuil.
SLEEP_ENERGY_MAX = 70

# Le joueur ne peut tenir que 2 objets dans ses mains a la fois.
HANDS_MAX = 2

# Chaque case a un "stock" de trouvailles : entre 5 et 15 (tire au hasard,
# mais STABLE pour une case donnee). Une fois epuise, explorer cette case ne
# donne plus rien.
FIND_BUDGET_MIN = 5
FIND_BUDGET_MAX = 15


def _clamp100(v):
    return max(0, min(100, v))


class GameState:
    def __init__(self, seed, name="Partie", difficulty="Moyen", time_seconds=0,
                 health=100, energy=100, sleep=100, hunger=0, thirst=0,
                 wood=0, food=0, water=0, action_count=0,
                 hands=None, ground=None, explores=None,
                 log=None, player_x=None, player_y=None, revealed=None):
        self.seed = seed
        self.name = name
        self.difficulty = difficulty
        self.time_seconds = time_seconds
        self.health = health        # vie
        self.energy = energy        # energie
        self.sleep = sleep          # sommeil (100 = bien repose)
        self.hunger = hunger        # faim (0 = rassasie, 100 = affame)
        self.thirst = thirst        # soif (0 = hydrate, 100 = assoiffe)
        self.wood = wood
        self.food = food
        self.water = water          # eau dans la gourde (unites a boire)
        # Mains : 2 emplacements [gauche, droite] ; None = main vide. On
        # normalise (compat. anciennes sauvegardes : liste plus courte ou sans
        # None).
        raw = list(hands) if hands else []
        self.hands = [raw[0] if len(raw) > 0 else None,
                      raw[1] if len(raw) > 1 else None]
        self.ground = ground if ground else {}      # {"x,y": {objet: nombre}}
        self.explores = explores if explores else {}  # {"x,y": nb trouvailles}
        self.revealed = set(revealed) if revealed else set()  # {"x,y", ...} zones revelees
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
        # Reveler la zone de depart
        state.reveal_zone(state.player_x, state.player_y)
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

    def advance_survival(self, seconds):
        """Fait deriver les stats selon le temps de jeu ecoule (en secondes)."""
        minutes = max(0, seconds) / 60.0
        self.hunger = _clamp100(self.hunger + HUNGER_RATE * minutes)
        self.thirst = _clamp100(self.thirst + THIRST_RATE * minutes)
        self.sleep = _clamp100(self.sleep - SLEEP_RATE * minutes)
        self.energy = _clamp100(self.energy - ENERGY_DRAIN * minutes)
        # En danger (faim/soif au max, ou sommeil/energie a zero) : la vie baisse.
        if (self.hunger >= 100 or self.thirst >= 100
                or self.sleep <= 0 or self.energy <= 0):
            self.health = _clamp100(self.health - HEALTH_RATE * minutes)

    def can_sleep(self):
        """On ne peut dormir que si on est assez fatigue (energie pas trop haute)."""
        return self.energy <= SLEEP_ENERGY_MAX

    def has_water_source(self):
        """Y a-t-il un ruisseau d'eau potable sur la case actuelle ?"""
        return (self.current_zone() in world.STREAM_TYPES
                and world.has_stream(self.seed, self.player_x, self.player_y))

    # ------------------------------------------------------------------ #
    # Inventaire (mains / sol) et craft
    # ------------------------------------------------------------------ #
    def _cell_key(self):
        return f"{self.player_x},{self.player_y}"

    def ground_here(self):
        """Objets au sol sur la case actuelle : {objet: nombre}."""
        return self.ground.get(self._cell_key(), {})

    # --- Trouvailles a proximite (stock limite par case) --------------- #
    def find_budget(self, x=None, y=None):
        """Nombre de trouvailles que cette case peut donner (5 a 15).
        Stable pour une case : derive de la graine + coordonnees."""
        x = self.player_x if x is None else x
        y = self.player_y if y is None else y
        rng = random.Random(f"{self.seed}:{x}:{y}:finds")
        return rng.randint(FIND_BUDGET_MIN, FIND_BUDGET_MAX)

    def explores_here(self):
        return self.explores.get(self._cell_key(), 0)

    def can_find(self):
        """La case a-t-elle encore des trouvailles ?"""
        return self.explores_here() < self.find_budget()

    def try_find(self):
        """Tente une trouvaille a proximite. Renvoie le nom de l'objet (deja
        pondere par la rarete) ou None si la case est epuisee."""
        if not self.can_find():
            return None
        key = self._cell_key()
        self.explores[key] = self.explores.get(key, 0) + 1
        # Reveler cette zone et les adjacentes
        self.reveal_zone(self.player_x, self.player_y)
        return items.random_find(self.current_zone())

    def reveal_zone(self, x, y):
        """Revele la zone (x,y) et les 8 zones adjacentes (carré 3x3) pour toujours."""
        # Reveler la zone centrale et les 8 alentours (carré 3x3)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                nx, ny = x + dx, y + dy
                if 0 <= nx < world.GRID_W and 0 <= ny < world.GRID_H:
                    self.revealed.add(f"{nx},{ny}")

    def hands_full(self):
        return all(h is not None for h in self.hands)

    def free_hand(self):
        """Indice d'une main libre (0=gauche, 1=droite), ou None si pleines."""
        for i, h in enumerate(self.hands):
            if h is None:
                return i
        return None

    def add_ground(self, item, n=1):
        g = self.ground.setdefault(self._cell_key(), {})
        g[item] = g.get(item, 0) + n

    def take_from_ground(self, item, hand):
        """Ramasse 1 objet du sol vers la main donnee (0=gauche, 1=droite).

        Echoue si la main visee est deja occupee ou si l'objet n'est plus la."""
        if hand not in (0, 1) or self.hands[hand] is not None:
            return False
        g = self.ground.get(self._cell_key(), {})
        if g.get(item, 0) <= 0:
            return False
        g[item] -= 1
        if g[item] <= 0:
            del g[item]
        if not g:
            self.ground.pop(self._cell_key(), None)
        self.hands[hand] = item
        return True

    def drop_from_hands(self, index):
        """Depose au sol l'objet tenu dans la main donnee (0=gauche, 1=droite)."""
        if index in (0, 1) and self.hands[index] is not None:
            self.add_ground(self.hands[index])
            self.hands[index] = None
            return True
        return False

    def take_found(self, item):
        """Prend un objet trouve : dans une main libre si possible, sinon au sol."""
        hand = self.free_hand()
        if hand is not None:
            self.hands[hand] = item
            return True
        self.add_ground(item)
        return False

    def craft_pool(self):
        """Objets disponibles pour le craft = mains + sol de la case."""
        pool = {}
        for it in self.hands:
            if it is not None:
                pool[it] = pool.get(it, 0) + 1
        for it, c in self.ground_here().items():
            pool[it] = pool.get(it, 0) + c
        return pool

    def can_craft(self, recipe):
        pool = self.craft_pool()
        return all(pool.get(k, 0) >= v for k, v in recipe["ingredients"].items())

    def do_craft(self, recipe):
        """Fabrique : consomme les ingredients (sol d'abord, puis mains)."""
        if not self.can_craft(recipe):
            return False
        for item, qty in recipe["ingredients"].items():
            need = qty
            g = self.ground.get(self._cell_key(), {})
            take = min(need, g.get(item, 0))
            if take:
                g[item] -= take
                if g[item] <= 0:
                    del g[item]
                need -= take
            # Puis dans les mains (on vide l'emplacement correspondant).
            for i in range(len(self.hands)):
                if need <= 0:
                    break
                if self.hands[i] == item:
                    self.hands[i] = None
                    need -= 1
            if not g:
                self.ground.pop(self._cell_key(), None)
        result = recipe["result"]
        hand = self.free_hand()
        if hand is not None:
            self.hands[hand] = result
        else:
            self.add_ground(result)
        return True

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
            "health": self.health,
            "energy": self.energy,
            "sleep": self.sleep,
            "hunger": self.hunger,
            "thirst": self.thirst,
            "wood": self.wood,
            "food": self.food,
            "water": self.water,
            "hands": self.hands,
            "ground": self.ground,
            "explores": self.explores,
            "revealed": list(self.revealed),
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
            health=data.get("health", 100),
            energy=data.get("energy", 100),
            sleep=data.get("sleep", 100),
            hunger=data.get("hunger", 0),
            thirst=data.get("thirst", 0),
            wood=data.get("wood", 0),
            food=data.get("food", 0),
            water=data.get("water", 0),
            hands=data.get("hands"),
            ground=data.get("ground"),
            explores=data.get("explores"),
            revealed=data.get("revealed", []),
            action_count=data.get("action_count", 0),
            log=data.get("log", []),
            player_x=data.get("player_x"),
            player_y=data.get("player_y"),
        )
