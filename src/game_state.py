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

# Directions cardinales dans le sens HORAIRE : Nord, Est, Sud, Ouest.
# (y augmente vers le bas, donc Nord = (0, -1).)
CARDINALS = [(0, -1), (1, 0), (0, 1), (-1, 0)]

# Chaque case a un "stock" de trouvailles : entre 5 et 15 (tire au hasard,
# mais STABLE pour une case donnee). Une fois epuise, explorer cette case ne
# donne plus rien.
FIND_BUDGET_MIN = 5
FIND_BUDGET_MAX = 15

# --------------------------------------------------------------------- #
# METEO
# --------------------------------------------------------------------- #
# La meteo est GLOBALE (une seule en cours sur toute la carte), mais son rendu
# depend de la zone : en MONTAGNE la pluie devient de la neige et l'orage un
# blizzard (voir effective_weather()).
WEATHERS = ["clair", "nuageux", "pluie", "orage"]
WEATHER_WEIGHTS = [45, 40, 10, 5]           # en % du temps

# Duree d'un episode meteo (heures de jeu). Comme toutes les meteos tirent
# leur duree dans le meme intervalle, la part de TEMPS de chacune correspond
# bien aux poids ci-dessus.
WEATHER_MIN_HOURS = 2
WEATHER_MAX_HOURS = 6

# Par temps nuageux : une fois sur deux, du brouillard s'ajoute (sauf en
# montagne, ou l'on est au-dessus).
FOG_CHANCE = 0.5
FOG_ZONES = ("Foret", "Plaine", "Lac")

# Equivalents en montagne.
MOUNTAIN_WEATHER = {"pluie": "neige", "orage": "blizzard"}


# --------------------------------------------------------------------- #
# EFFETS TEMPORAIRES
# --------------------------------------------------------------------- #
# Effets en cours sur le joueur, avec leur duree en HEURES DE JEU. Chacun
# s'affiche dans le panneau "Effet" avec un anneau montrant le temps restant.
EFFECT_HOURS = {
    "Feu_de_camp": 6.0,     # duree pendant laquelle le feu reste allume
    "Repos": 2.0,           # bien repose, apres un sommeil complet
    "Mouille": 1.0,         # duree par defaut (voir WET_HOURS)
}

# Combien de temps on reste MOUILLE, selon l'averse qui vient de se terminer.
WET_HOURS = {"pluie": 0.5, "orage": 1.0}


def _clamp100(v):
    return max(0, min(100, v))


class GameState:
    def __init__(self, seed, name="Partie", difficulty="Moyen", time_seconds=0,
                 health=100, energy=100, sleep=100, hunger=0, thirst=0,
                 wood=0, food=0, water=0, action_count=0,
                 hands=None, ground=None, explores=None, harvested=None,
                 log=None, player_x=None, player_y=None, revealed=None,
                 facing=0, installed=None, debug=False,
                 weather=None, fog=False, weather_until=0,
                 effects=None):
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
        # Objets recoltes par case : {"x,y": {nom: nombre}} -> sert a masquer
        # les objets recoltes dans la scene (coherence decor/recolte).
        self.harvested = harvested if harvested else {}
        # Objets INSTALLES par case, avec leur position dans la grille 5x5.
        # {"x,y": [(nom, gx, gy), ...]} avec gx et gy dans [0..4] (gx =
        # colonne gauche->droite, gy = ligne bas->haut/proche->loin). Un
        # objet installe est irreversible (ne peut plus etre ramasse ni
        # deplace) et rend le bouton Proximite actif s'il est interactif.
        self.installed = installed if installed else {}
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

        # Orientation du joueur (indice dans CARDINALS) : Nord par defaut.
        self.facing = facing % 4

        # Mode DEBUG (partie "Partie D" lancee depuis le bouton du menu) :
        # carte toujours utilisable, craft illimite sans ingredients.
        self.debug = bool(debug)

        # Effets temporaires : {nom: [debut, fin]} en secondes de jeu.
        # Initialises AVANT la meteo, qui peut declencher l'effet "Mouille".
        self.effects = {}
        for name, span in (effects or {}).items():
            if name in EFFECT_HOURS and len(span) == 2:
                self.effects[name] = [int(span[0]), int(span[1])]

        # Meteo en cours (voir WEATHERS) : globale, avec brouillard eventuel,
        # renouvelee quand `time_seconds` depasse `weather_until`.
        self.weather = weather
        self.fog = bool(fog)
        self.weather_until = int(weather_until)
        self.update_weather()

    # ------------------------------------------------------------------ #
    # Creation
    # ------------------------------------------------------------------ #
    @classmethod
    def new_random(cls, name, difficulty="Moyen", seed=None, debug=False):
        if seed is None:
            seed = random.randrange(1_000_000)
        if difficulty not in DIFFICULTIES:
            difficulty = "Moyen"
        state = cls(seed=seed, name=name, difficulty=difficulty, debug=debug)
        state.time_seconds = START_HOUR * 3600        # debut a 6h
        start = START_RESOURCES[difficulty]
        state.food = start["food"]
        state.wood = start["wood"]
        state.log.append(f"Nouvelle partie ({difficulty}).")
        # Meteo tiree a partir de l'heure de depart (et non de 0h).
        state.weather = None
        state.update_weather()
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

    # -- Orientation (le joueur "regarde" dans une direction) ----------- #
    def dir_vector(self, turn):
        """(dx, dy) absolu pour une direction RELATIVE a l'orientation :
        0 = en face, 1 = a droite, 2 = derriere, 3 = a gauche."""
        return CARDINALS[(self.facing + turn) % 4]

    def turn_of(self, dx, dy):
        """Direction relative (0=face, 1=droite, 2=arriere, 3=gauche) d'un
        deplacement absolu (dx, dy) selon l'orientation actuelle."""
        if (dx, dy) not in CARDINALS:
            return 0
        return (CARDINALS.index((dx, dy)) - self.facing) % 4

    def face(self, dx, dy):
        """Oriente le joueur dans la direction du deplacement -> la case
        d'origine se retrouve DERRIERE lui."""
        if (dx, dy) in CARDINALS:
            self.facing = CARDINALS.index((dx, dy))

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
    # Meteo
    # ------------------------------------------------------------------ #
    def update_weather(self):
        """Renouvelle la meteo quand l'episode en cours est termine.

        Appelable a chaque frame : ne fait rien tant que l'episode dure."""
        if self.weather in WEATHERS and self.time_seconds < self.weather_until:
            self._apply_wet()
            return
        self.weather = random.choices(WEATHERS, weights=WEATHER_WEIGHTS, k=1)[0]
        # Brouillard : seulement par temps nuageux, une fois sur deux.
        self.fog = (self.weather == "nuageux"
                    and random.random() < FOG_CHANCE)
        hours = random.uniform(WEATHER_MIN_HOURS, WEATHER_MAX_HOURS)
        self.weather_until = int(self.time_seconds + hours * 3600)
        self._apply_wet()

    def _apply_wet(self):
        """Le joueur est MOUILLE des que l'averse commence.

        Tant qu'il pleut, l'effet est maintenu au maximum (il est relance a
        chaque appel) ; il ne commence donc a decroitre qu'a la FIN de
        l'averse, pour 30 min apres une pluie ou 1 h apres un orage."""
        hours = WET_HOURS.get(self.weather)
        if hours:
            self.start_effect("Mouille", hours=hours)

    # ------------------------------------------------------------------ #
    # Effets temporaires
    # ------------------------------------------------------------------ #
    def start_effect(self, name, hours=None):
        """Declenche (ou relance) un effet.

        `hours` permet une duree particuliere (ex. "Mouille", plus long apres
        un orage qu'apres une simple pluie) ; sinon on prend EFFECT_HOURS."""
        if hours is None:
            hours = EFFECT_HOURS.get(name)
        if hours is None:
            return False
        self.effects[name] = [self.time_seconds,
                              int(self.time_seconds + hours * 3600)]
        return True

    def active_effects(self):
        """Effets en cours : [(nom, part de temps restante 0..1), ...].

        Les effets termines sont oublies au passage."""
        out = []
        for name in list(self.effects):
            start, end = self.effects[name]
            if self.time_seconds >= end:
                del self.effects[name]        # effet termine
                continue
            total = max(1, end - start)
            out.append((name, (end - self.time_seconds) / total))
        return out

    def effective_weather(self):
        """Meteo telle qu'elle se manifeste DANS LA ZONE actuelle : en
        montagne, la pluie devient neige et l'orage un blizzard."""
        w = self.weather if self.weather in WEATHERS else "clair"
        if self.current_zone() == "Montagne":
            return MOUNTAIN_WEATHER.get(w, w)
        return w

    def fog_active(self):
        """Y a-t-il du brouillard ici ? (temps nuageux + zone concernee)"""
        return (self.fog and self.weather == "nuageux"
                and self.current_zone() in FOG_ZONES)

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

    def harvested_here(self):
        """Objets deja recoltes sur la case actuelle : {nom: nombre}."""
        return self.harvested.setdefault(self._cell_key(), {})

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

    def installed_objects_here(self):
        """Liste des objets INSTALLES sur la case actuelle : [(nom, gx, gy), ...].
        Les elements peuvent etre tuples ou listes (JSON serialize en liste)."""
        return self.installed.get(self._cell_key(), [])

    def nature_cells_here(self):
        """Cellules 5x5 de la case occupees par un GROS element du decor
        (arbre, buisson, gros rocher) : {(gx, gy): type}. On ne peut pas y
        installer d'objet."""
        return world.nature_blocked_cells(
            self.current_zone(),
            world.scene_seed(self.player_x, self.player_y))

    def install_from_hand(self, index, gx, gy):
        """Installe l'objet tenu dans la main donnee sur la case courante a
        la position grille (gx, gy). Echoue si la main est vide, si l'objet
        n'est pas installable, ou si la position est deja prise (par un objet
        installe OU par un gros element du decor : arbre, buisson, rocher)."""
        if index not in (0, 1):
            return False
        name = self.hands[index]
        if name is None or name not in items.INSTALLABLE_ITEMS:
            return False
        # Refuse une case occupee par la nature (arbre, buisson, rocher).
        if (int(gx), int(gy)) in self.nature_cells_here():
            return False
        key = self._cell_key()
        lst = self.installed.setdefault(key, [])
        # Refuse une position deja occupee.
        for obj in lst:
            if int(obj[1]) == int(gx) and int(obj[2]) == int(gy):
                return False
        lst.append((name, int(gx), int(gy)))
        self.hands[index] = None
        # Un feu de camp installe s'allume : l'effet demarre pour sa duree.
        self.start_effect(name)
        return True

    def take_found(self, item):
        """Prend un objet trouve : dans une main libre si possible, sinon au sol."""
        hand = self.free_hand()
        if hand is not None:
            self.hands[hand] = item
            return True
        self.add_ground(item)
        return False

    def auto_take(self, item):
        """Range un objet trouve apres exploration.

        - Objet non ramassable a la main -> directement AU SOL.
        - Sinon : main DROITE en priorite, puis main GAUCHE ; si les deux sont
          pleines (cas limite), au sol.
        Renvoie l'indice de la main (0=gauche, 1=droite) ou None si pose au sol.
        """
        if not items.is_hand_collectable(item):
            self.add_ground(item)
            return None
        if self.hands[1] is None:
            self.hands[1] = item
            return 1
        if self.hands[0] is None:
            self.hands[0] = item
            return 0
        self.add_ground(item)
        return None

    def has_item(self, name):
        """Possede l'objet (tenu en main OU au sol sur la case actuelle) ?"""
        if name in self.hands:
            return True
        return self.ground_here().get(name, 0) > 0

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
        if self.debug:
            return True            # debug : tout craftable, sans ingredients
        pool = self.craft_pool()
        return all(pool.get(k, 0) >= v for k, v in recipe["ingredients"].items())

    def do_craft(self, recipe):
        """Fabrique : consomme les ingredients (sol d'abord, puis mains).
        En mode DEBUG, rien n'est consomme (craft illimite)."""
        if not self.can_craft(recipe):
            return False
        for item, qty in (() if self.debug else recipe["ingredients"].items()):
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
            "installed": self.installed,
            "debug": self.debug,
            "weather": self.weather,
            "fog": self.fog,
            "weather_until": self.weather_until,
            "effects": self.effects,
            "explores": self.explores,
            "harvested": self.harvested,
            "facing": self.facing,
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
            installed=data.get("installed"),
            debug=data.get("debug", False),
            weather=data.get("weather"),
            fog=data.get("fog", False),
            weather_until=data.get("weather_until", 0),
            effects=data.get("effects"),
            explores=data.get("explores"),
            harvested=data.get("harvested"),
            facing=data.get("facing", 0),
            revealed=data.get("revealed", []),
            action_count=data.get("action_count", 0),
            log=data.get("log", []),
            player_x=data.get("player_x"),
            player_y=data.get("player_y"),
        )
