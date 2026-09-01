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

# --------------------------------------------------------------------- #
# FAIM ET SOIF : alerte, puis degats
# --------------------------------------------------------------------- #
# A partir de ce niveau, la faim (ou la soif) devient un EFFET visible et
# commence a couter de la vie.
SURVIVAL_ALERT = 75
# Entre le seuil et 100, chaque tranche franchie coute des points de vie.
SURVIVAL_STEP = 5
SURVIVAL_STEP_DAMAGE = 1
# Au-dela de 100, c'est l'inanition : la vie tombe de 5 points par MINUTE
# REELLE. Le jeu ne compte qu'en temps de JEU, on convertit donc avec
# l'echelle du temps (cf. game_screen.TIME_SCALE : 24 h de jeu en 10 min
# reelles, soit 144 minutes de jeu par minute reelle).
STARVING_DAMAGE = 5.0
GAME_MINUTES_PER_REAL_MINUTE = 144.0

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


# --------------------------------------------------------------------- #
# FEUX DE CAMP
# --------------------------------------------------------------------- #
# Un foyer se nourrit de deux apports, tous deux ramasses A PROXIMITE (mains
# ou sol) : le COMBUSTIBLE (branche, buche) donne la DUREE du feu, le
# COMBURANT (feuille, ecorce) donne la CHANCE de reussir a l'allumer. Il faut
# de plus un ALLUME-FEU en main (items.FIRE_STARTER_ITEMS).
FIRE_LIGHT_BASE = 0.10      # chance d'allumage sans aucun comburant
FIRE_LIGHT_MAX = 0.95       # on n'est jamais sur a 100 %
FIRE_LIGHT_FAIL_LOSS = 0.5  # part du comburant partie en fumee a chaque echec

# Un feu FAIBLIT en brulant : son aspect suit la part de combustible qui lui
# reste (par rapport a la plus grosse charge qu'il a recue). Seuil = minimum
# pour atteindre ce niveau.
FIRE_LEVELS = (("grand", 0.66), ("moyen", 0.33), ("petit", 0.05),
               ("braise", 0.0))


def _as_wear(name, value):
    """Normalise une usure lue d'une sauvegarde.

    L'usure a d'abord ete enregistree en NOMBRE d'utilisations, elle l'est
    maintenant en PART usee (0..1). Une valeur superieure a 1 vient donc d'une
    ancienne sauvegarde : on la reconvertit."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return 0.0
    if v > 1.0:
        total = items.tool_max_uses(name)
        v = (v / total) if total > 0 else 0.0
    return max(0.0, min(1.0, v))


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
                 effects=None, fires=None, hand_wear=None, ground_wear=None,
                 chopped=None, equipment=None, bag=None,
                 penalty_steps=None, bag_wear=None):
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
        # Usure des outils TENUS : [nom, part_usee] par main, la part allant
        # de 0.0 (neuf) a 1.0 (casse). Le nom est memorise avec l'usure pour
        # qu'elle ne puisse jamais s'appliquer a un autre objet (voir
        # tool_wear).
        raw_w = list(hand_wear) if hand_wear else []
        self.hand_wear = [[raw_w[i][0], _as_wear(raw_w[i][0], raw_w[i][1])]
                          if i < len(raw_w) and raw_w[i] else [None, 0.0]
                          for i in range(2)]
        self.ground = ground if ground else {}      # {"x,y": {objet: nombre}}
        # Usure des outils POSES AU SOL : {"x,y": {nom: [utilisations, ...]}},
        # une valeur par exemplaire.
        self.ground_wear = {}
        for cell, per_item in (ground_wear or {}).items():
            self.ground_wear[cell] = {n: [_as_wear(n, u) for u in lst]
                                      for n, lst in per_item.items()}
        # EQUIPEMENT porte : {emplacement: objet ou None}. Une partie sans
        # equipement enregistre (nouvelle partie, ou sauvegarde d'avant cette
        # fonctionnalite) demarre avec la tenue de rescape.
        base = items.STARTING_EQUIPMENT if equipment is None else equipment
        self.equipment = {slot: (base or {}).get(slot)
                          for slot in items.EQUIP_SLOTS}
        # Contenu du SAC A DOS. Sans sac, aucune place : la liste reste vide.
        # `bag_wear` suit exactement `bag` : l'usure d'un outil range dans le
        # sac ne se perd pas.
        self.bag = [b for b in (bag or []) if b]
        raw_bw = list(bag_wear or [])
        self.bag_wear = [_as_wear(self.bag[i], raw_bw[i]) if i < len(raw_bw)
                         else 0.0 for i in range(len(self.bag))]
        # Paliers de faim/soif deja factures en points de vie (voir
        # _survival_damage) : evite de repayer le meme palier a chaque frame.
        self.penalty_steps = {"hunger": 0, "thirst": 0}
        for stat, n in (penalty_steps or {}).items():
            if stat in self.penalty_steps:
                self.penalty_steps[stat] = int(n)
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
        # Arbres ABATTUS par case : {"x,y": [[gx, gy], ...]}. Un arbre coupe
        # ne repousse pas : sa cellule reste vide dans le decor.
        self.chopped = {}
        for cell, lst in (chopped or {}).items():
            self.chopped[cell] = [[int(c[0]), int(c[1])] for c in lst]
        # Etat de chaque FOYER installe : {"x,y:gx,gy": {...}}. Voir fire_at().
        # Un foyer ne brule que s'il a du COMBUSTIBLE et du COMBURANT ; il
        # faut de plus l'ALLUMER (allume-feu en main).
        self.fires = {}
        for key, f in (fires or {}).items():
            self.fires[key] = {"lit": int(f.get("lit", 0)),
                               "fuel": float(f.get("fuel", 0.0)),
                               "air": float(f.get("air", 0.0)),
                               "fuel_max": float(f.get("fuel_max",
                                                       f.get("fuel", 0.0))),
                               "t": int(f.get("t", time_seconds))}
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
        # FAIM et SOIF ne sont pas des effets a duree : ils durent tant que le
        # niveau reste critique. L'anneau se vide a mesure qu'on approche de
        # 100, ou commence l'inanition.
        span = max(1.0, 100.0 - SURVIVAL_ALERT)
        for stat, name in (("hunger", "Faim"), ("thirst", "Soif")):
            value = getattr(self, stat)
            if value >= SURVIVAL_ALERT:
                out.append((name, max(0.0, (100.0 - value) / span)))
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
        # Epuisement (sommeil ou energie a zero) : la vie baisse doucement.
        if self.sleep <= 0 or self.energy <= 0:
            self.health = _clamp100(self.health - HEALTH_RATE * minutes)
        # Faim et soif : paliers, puis inanition.
        damage = self._survival_damage(minutes)
        if damage:
            self.health = _clamp100(self.health - damage)

    def _survival_damage(self, minutes):
        """Points de vie coutes par la faim et la soif sur cette duree.

        Deux regimes :
        - entre le seuil d'alerte et 100, chaque tranche de 5 points FRANCHIE
          coute 1 point de vie, une seule fois (manger fait repartir le
          compteur, il se represente donc si on remonte) ;
        - a 100, c'est l'inanition : 5 points de vie par minute reelle."""
        total = 0.0
        for stat in ("hunger", "thirst"):
            value = getattr(self, stat)
            steps = max(0, int((value - SURVIVAL_ALERT) // SURVIVAL_STEP))
            done = int(self.penalty_steps.get(stat, 0))
            if steps > done:
                total += (steps - done) * SURVIVAL_STEP_DAMAGE
            if steps != done:
                self.penalty_steps[stat] = steps
            if value >= 100:
                total += STARVING_DAMAGE * minutes / GAME_MINUTES_PER_REAL_MINUTE
        return total

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

    def add_ground(self, item, n=1, wear=0.0):
        g = self.ground.setdefault(self._cell_key(), {})
        g[item] = g.get(item, 0) + n
        if items.is_tool(item):
            # L'usure suit l'outil au sol : le poser puis le reprendre ne le
            # repare pas. Un exemplaire = une valeur dans la liste.
            for _ in range(n):
                self._push_ground_wear(item, wear)

    def _push_ground_wear(self, item, wear):
        self.ground_wear.setdefault(self._cell_key(), {}) \
            .setdefault(item, []).append(float(wear))

    def _take_ground_wear(self, item):
        """Retire et renvoie l'usure d'un exemplaire pose au sol.

        On rend le plus USE en premier : le joueur garde ainsi ses outils
        neufs pour plus tard sans avoir a y penser."""
        cell = self.ground_wear.get(self._cell_key(), {})
        lst = cell.get(item)
        if not lst:
            return 0.0
        worst = max(lst)
        lst.remove(worst)
        if not lst:
            del cell[item]
        if not cell:
            self.ground_wear.pop(self._cell_key(), None)
        return worst

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
        self.set_hand(hand, item, self._take_ground_wear(item))
        return True

    def drop_from_hands(self, index):
        """Depose au sol l'objet tenu dans la main donnee (0=gauche, 1=droite)."""
        if index in (0, 1) and self.hands[index] is not None:
            self.add_ground(self.hands[index], wear=self.tool_wear(index))
            self.set_hand(index, None)
            return True
        return False

    # ------------------------------------------------------------------ #
    # Solidite des outils (hache, lance, couteau)
    # ------------------------------------------------------------------ #
    def set_hand(self, index, name, wear=0.0):
        """Place un objet dans une main en fixant son usure."""
        self.hands[index] = name
        self.hand_wear[index] = [name, float(wear)] if name else [None, 0.0]

    def tool_wear(self, index):
        """Part DEJA usee de l'outil tenu (0.0 = neuf, 1.0 = casse).

        L'usure est memorisee avec le NOM de l'outil : si la main change de
        contenu sans passer par set_hand, elle repart de zero d'elle-meme."""
        name = self.hands[index]
        rec = self.hand_wear[index]
        if name is None or rec[0] != name:
            return 0.0
        return float(rec[1])

    def tool_health(self, index):
        """Solidite restante de l'outil tenu, de 1.0 (neuf) a 0.0 (casse).
        Renvoie None si ce n'est pas un outil a usage multiple."""
        name = self.hands[index]
        if not name or items.tool_max_uses(name) <= 0:
            return None
        return max(0.0, 1.0 - self.tool_wear(index))

    def use_tool(self, index, amount=None):
        """Use l'outil tenu. Renvoie True s'il CASSE.

        `amount` = part de solidite consommee ; par defaut une utilisation
        pleine, soit 1 / TOOL_USES. Une recette peut demander autre chose
        (la fibre vegetale coute 10 % du couteau).

        Un outil casse disparait de la main : c'est ce qui donne son prix a
        l'entretien du materiel."""
        name = self.hands[index]
        total = items.tool_max_uses(name) if name else 0
        if total <= 0:
            return False
        if amount is None:
            amount = 1.0 / total
        wear = self.tool_wear(index) + amount
        if wear >= 1.0 - 1e-9:
            self.set_hand(index, None)
            self.add_log(f"{items.display_name(name)} casse")
            return True
        self.hand_wear[index] = [name, wear]
        return False

    def wear_tool_nearby(self, name, amount):
        """Use un outil A PROXIMITE : celui en main d'abord, sinon un du sol.
        Renvoie True s'il casse (il disparait alors)."""
        if amount <= 0:
            return False
        hand = self.hand_holding(name)
        if hand is not None:
            return self.use_tool(hand, amount)
        if self.ground_here().get(name, 0) <= 0:
            return False
        wear = self._take_ground_wear(name) + amount
        if wear >= 1.0 - 1e-9:
            key = self._cell_key()
            g = self.ground.get(key, {})
            g[name] = g.get(name, 1) - 1
            if g[name] <= 0:
                del g[name]
            if not g:
                self.ground.pop(key, None)
            self.add_log(f"{items.display_name(name)} casse")
            return True
        self._push_ground_wear(name, wear)
        return False

    def hand_holding(self, name):
        """Indice de la main tenant cet objet (droite d'abord), ou None."""
        for i in (1, 0):
            if self.hands[i] == name:
                return i
        return None

    def installed_objects_here(self):
        """Liste des objets INSTALLES sur la case actuelle : [(nom, gx, gy), ...].
        Les elements peuvent etre tuples ou listes (JSON serialize en liste)."""
        return self.installed.get(self._cell_key(), [])

    # ------------------------------------------------------------------ #
    # Equipement et sac a dos
    # ------------------------------------------------------------------ #
    def bag_capacity(self):
        """Nombre d'emplacements du sac porte (0 si le joueur n'en a pas)."""
        return items.bag_capacity(self.equipment.get("sac"))

    def bag_free(self):
        """Emplacements encore libres dans le sac."""
        return max(0, self.bag_capacity() - len(self.bag))

    def bag_store(self, hand):
        """Range dans le sac l'objet tenu dans cette main.

        L'usure de l'outil voyage avec lui : un couteau range a moitie use
        ressort a moitie use."""
        name = self.hands[hand] if hand in (0, 1) else None
        if name is None or self.bag_free() <= 0:
            return False
        self.bag.append(name)
        self.bag_wear.append(self.tool_wear(hand))
        self.set_hand(hand, None)
        return True

    def bag_take(self, index, hand):
        """Sort du sac l'objet d'un emplacement, vers une main LIBRE."""
        if not (0 <= index < len(self.bag)) or hand not in (0, 1):
            return False
        if self.hands[hand] is not None:
            return False
        wear = self.bag_wear.pop(index) if index < len(self.bag_wear) else 0.0
        self.set_hand(hand, self.bag.pop(index), wear)
        return True

    def can_equip(self, index):
        """L'objet tenu dans cette main se porte-t-il ?"""
        name = self.hands[index] if index in (0, 1) else None
        return name is not None and items.equip_slot(name) is not None

    def equip_from_hand(self, index):
        """Porte l'objet tenu dans cette main.

        La piece deja portee revient DANS LA MAIN : on echange, la main ne se
        retrouve donc jamais encombree d'un objet perdu."""
        if not self.can_equip(index):
            return False
        name = self.hands[index]
        slot = items.equip_slot(name)
        previous = self.equipment.get(slot)
        self.equipment[slot] = name
        self.set_hand(index, previous)
        self._spill_bag()
        self.add_log(f"{items.display_name(name)} equipe")
        return True

    def equip_from_bag(self, index):
        """Porte une piece rangee dans le sac.

        La piece deja portee prend sa PLACE DANS LE SAC : on echange, rien
        ne se perd. Renvoie le nombre d'objets tombes au sol (changer de sac
        peut reduire la place), ou None si l'echange est impossible."""
        if not (0 <= index < len(self.bag)):
            return None
        name = self.bag[index]
        slot = items.equip_slot(name)
        if slot is None:
            return None
        previous = self.equipment.get(slot)
        self.bag.pop(index)
        if index < len(self.bag_wear):
            # L'equipement ne retient pas d'usure (aucune piece portable
            # n'est un outil a usage multiple) : celle-ci s'arrete ici.
            self.bag_wear.pop(index)
        self.equipment[slot] = name
        if previous is not None:
            self.bag.insert(index, previous)
            self.bag_wear.insert(index, 0.0)
        spilled = self._spill_bag()
        self.add_log(f"{items.display_name(name)} equipe")
        return spilled

    def _spill_bag(self):
        """Fait tomber au sol ce que le sac ne peut plus contenir.

        Changer de sac — ou le retirer — REDUIT la place disponible. Le
        surplus tombe au sol plutot que de disparaitre : il reste
        ramassable. Renvoie le nombre d'objets tombes."""
        lost = 0
        while len(self.bag) > self.bag_capacity():
            name = self.bag.pop()
            self.add_ground(name, wear=self.bag_wear.pop()
                            if self.bag_wear else 0.0)
            lost += 1
        return lost

    def unequip_to_hand(self, slot, hand):
        """Retire la piece portee et la met dans une main LIBRE.

        Renvoie le nombre d'objets tombes du sac (retirer le sac le vide),
        ou None si le retrait est impossible."""
        name = self.equipment.get(slot)
        if name is None or hand not in (0, 1) or self.hands[hand] is not None:
            return None
        self.equipment[slot] = None
        self.set_hand(hand, name)
        spilled = self._spill_bag()
        self.add_log(f"{items.display_name(name)} retire")
        return spilled

    def unequip_to_bag(self, slot):
        """Retire la piece portee et la range dans le sac.

        Un sac a dos ne peut evidemment pas se ranger dans lui-meme."""
        name = self.equipment.get(slot)
        if name is None or slot == "sac" or self.bag_free() <= 0:
            return False
        self.equipment[slot] = None
        self.bag.append(name)
        self.bag_wear.append(0.0)
        self.add_log(f"{items.display_name(name)} retire")
        return True

    # ------------------------------------------------------------------ #
    # Arbres abattus
    # ------------------------------------------------------------------ #
    def chopped_here(self):
        """Cellules 5x5 dont le GROS element a ete abattu sur cette case."""
        return {(int(c[0]), int(c[1]))
                for c in self.chopped.get(self._cell_key(), [])}

    def trees_here(self):
        """Arbres encore DEBOUT sur la case : [(gx, gy), ...].

        Ce sont les gros elements du decor de type "tree" que le joueur n'a
        pas encore coupes : le bouton "Couper du bois" en depend."""
        gone = self.chopped_here()
        return [cell for cell, kind in sorted(self.nature_cells_here().items())
                if kind == "tree" and cell not in gone]

    def chop_tree(self):
        """Abat l'arbre le plus PROCHE. Renvoie sa cellule, ou None.

        La cellule reste marquee pour toujours : l'arbre ne repousse pas et
        disparait donc definitivement du decor."""
        trees = self.trees_here()
        if not trees:
            return None
        # gy croissant = de plus en plus loin : on coupe le plus proche.
        cell = min(trees, key=lambda c: (c[1], c[0]))
        self.chopped.setdefault(self._cell_key(), []).append([cell[0], cell[1]])
        return cell

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
        self.set_hand(index, None)
        if name == "Feu_de_camp":
            # Un foyer monte est ETEINT : il faut y mettre du combustible,
            # l'aerer, puis l'allumer (voir fire_light).
            self.fires[self._fire_key(gx, gy)] = {
                "lit": 0, "fuel": 0.0, "air": 0.0, "fuel_max": 0.0,
                "t": self.time_seconds}
        else:
            self.start_effect(name)
        return True

    # ------------------------------------------------------------------ #
    # Feux de camp : combustible + comburant + allumage
    # ------------------------------------------------------------------ #
    def _fire_key(self, gx, gy):
        return f"{self._cell_key()}:{int(gx)},{int(gy)}"

    def fire_at(self, gx, gy):
        """Etat du foyer a cette position de la grille (cree s'il manque).

        - "fuel" : heures de COMBUSTIBLE restant (bois : branche, buche) ;
        - "air"  : bonus de CHANCE d'allumage accumule (comburant : feuille,
                   ecorce). Ce n'est pas une duree : il ne sert qu'a faire
                   partir la flamme, et disparait une fois le feu allume ;
        - "lit"  : le feu brule (le combustible se consume) ;
        - "t"    : date du dernier calcul de combustion."""
        key = self._fire_key(gx, gy)
        f = self.fires.get(key)
        if f is None:
            f = {"lit": 0, "fuel": 0.0, "air": 0.0, "fuel_max": 0.0,
                 "t": self.time_seconds}
            self.fires[key] = f
        return f

    def fire_burn_hours(self, f):
        """Heures avant extinction : ce qu'il reste de COMBUSTIBLE."""
        return max(0.0, f.get("fuel", 0.0))

    def fire_ratio(self, f):
        """Part du combustible restante (0..1), par rapport a la plus grosse
        charge que ce foyer a recue."""
        top = max(f.get("fuel_max", 0.0), f.get("fuel", 0.0))
        return (max(0.0, f.get("fuel", 0.0)) / top) if top > 0 else 0.0

    def fire_level(self, f):
        """Aspect du feu : "grand", "moyen", "petit", "braise" (ou "" eteint)."""
        if not f.get("lit"):
            return ""
        ratio = self.fire_ratio(f)
        for name, floor in FIRE_LEVELS:
            if ratio >= floor:
                return name
        return "braise"

    def fire_light_chance(self, f):
        """Probabilite (0..1) de reussir a allumer ce foyer.

        Elle part d'une base tres faible, monte surtout avec le COMBURANT
        accumule (feuilles, ecorce), et un peu avec la qualite de l'allume-feu
        tenu en main. Elle ne peut jamais atteindre la certitude."""
        hand = self.fire_starter_hand()
        bonus = items.starter_bonus(self.hands[hand]) if hand is not None else 0.0
        return min(FIRE_LIGHT_MAX,
                   FIRE_LIGHT_BASE + max(0.0, f.get("air", 0.0)) + bonus)

    def update_fires(self):
        """Fait bruler les foyers allumes : seul le COMBUSTIBLE se consume.
        Quand il n'en reste plus, le feu s'eteint."""
        for f in self.fires.values():
            dt = max(0, self.time_seconds - int(f.get("t", self.time_seconds)))
            f["t"] = self.time_seconds
            if not f.get("lit") or dt <= 0:
                continue
            f["fuel"] = max(0.0, f["fuel"] - dt / 3600.0)
            if f["fuel"] <= 0.0:
                f["lit"] = 0
        self._sync_fire_effect()

    def _sync_fire_effect(self):
        """L'effet "Feu de camp" dure tant qu'un foyer BRULE sur la case.

        On garde la date de debut d'origine pour que l'anneau de l'effet
        montre bien le temps qui s'ecoule (et remonte quand on rajoute du
        combustible)."""
        best = 0.0
        for obj in self.installed_objects_here():
            if obj[0] != "Feu_de_camp":
                continue
            f = self.fires.get(self._fire_key(obj[1], obj[2]))
            if f and f.get("lit"):
                best = max(best, self.fire_burn_hours(f))
        if best > 0.0:
            prev = self.effects.get("Feu_de_camp")
            start = prev[0] if prev else self.time_seconds
            self.effects["Feu_de_camp"] = [
                int(start), int(self.time_seconds + best * 3600)]
        else:
            self.effects.pop("Feu_de_camp", None)

    def fire_source(self, table):
        """Meilleur apport de `table` disponible A PROXIMITE (mains ou sol).

        "A proximite" = ce que le joueur tient ET ce qui traine sur la case,
        comme pour le craft. On choisit celui qui brule le plus longtemps."""
        pool = self.craft_pool()
        best = None
        for name, hours in table.items():
            if pool.get(name, 0) > 0 and (best is None or hours > table[best]):
                best = name
        return best

    def consume_nearby(self, name):
        """Retire un exemplaire de l'objet : au SOL d'abord, puis en main."""
        key = self._cell_key()
        g = self.ground.get(key, {})
        if g.get(name, 0) > 0:
            self._take_ground_wear(name)
            g[name] -= 1
            if g[name] <= 0:
                del g[name]
            if not g:
                self.ground.pop(key, None)
            return True
        for i in (0, 1):
            if self.hands[i] == name:
                self.set_hand(i, None)
                return True
        return False

    def fire_starter_hand(self):
        """Main tenant le MEILLEUR allume-feu, ou None si aucune n'en a."""
        best = None
        for i in (1, 0):
            name = self.hands[i]
            if name and items.is_fire_starter(name):
                if (best is None or items.starter_bonus(name)
                        > items.starter_bonus(self.hands[best])):
                    best = i
        return best

    def fire_table(self, kind):
        """Table des matieres acceptees par un bouton du foyer."""
        return (items.FIRE_TINDER_CHANCE if kind == "tinder"
                else items.FIRE_WOOD_HOURS)

    def fire_next(self, kind):
        """Matiere que le bouton utiliserait, ou None s'il n'y en a aucune.

        En mode DEBUG le foyer s'alimente sans reserve : quand rien n'est a
        proximite, une matiere par defaut est fournie (branche / ecorce)."""
        name = self.fire_source(self.fire_table(kind))
        if name is None and self.debug:
            name = (items.FIRE_DEFAULT_TINDER if kind == "tinder"
                    else items.FIRE_DEFAULT_WOOD)
        return name

    def fire_add(self, gx, gy, kind):
        """Ajoute un apport au foyer.

        `kind` designe la MATIERE : "wood" (branche, buche) ajoute de la DUREE
        au feu, "tinder" (feuille, ecorce) ajoute de la CHANCE de l'allumer.
        L'objet est pris a proximite (ou fourni, en mode debug)."""
        table = self.fire_table(kind)
        name = self.fire_next(kind)
        if name is None:
            return False
        # On ne consomme que ce qui est REELLEMENT la : en debug, la matiere
        # manquante est offerte, mais celle qu'on possede part quand meme.
        if not self.consume_nearby(name) and not self.debug:
            return False
        f = self.fire_at(gx, gy)
        f["fuel" if kind == "wood" else "air"] += table[name]
        # Reference pour l'ASPECT du feu : la plus grosse charge recue.
        f["fuel_max"] = max(f.get("fuel_max", 0.0), f["fuel"])
        self._sync_fire_effect()
        return True

    def fire_can_light(self, gx, gy):
        """Peut-on TENTER d'allumer ce foyer ? (la reussite, elle, se joue)"""
        f = self.fire_at(gx, gy)
        return (not f.get("lit") and self.fire_starter_hand() is not None
                and f.get("fuel", 0.0) > 0.0)

    def fire_light(self, gx, gy):
        """TENTE d'allumer le foyer : la reussite depend du comburant.

        L'ALLUME-FEU est detruit dans tous les cas, reussite comme echec : une
        tentative l'use. En cas d'echec, une bonne partie du comburant part de
        plus en fumee, il faut en remettre pour retrouver ses chances."""
        if not self.fire_can_light(gx, gy):
            return False
        f = self.fire_at(gx, gy)
        # La chance se calcule AVANT de detruire l'allume-feu : c'est lui qui
        # apporte une partie du bonus.
        chance = self.fire_light_chance(f)
        hand = self.fire_starter_hand()
        if hand is not None:
            self.set_hand(hand, None)
        if random.random() >= chance:
            f["air"] = max(0.0, f["air"] * (1.0 - FIRE_LIGHT_FAIL_LOSS))
            return False
        f["lit"] = 1
        f["air"] = 0.0             # l'amadou s'est consume en prenant feu
        f["t"] = self.time_seconds
        self._sync_fire_effect()
        return True

    def take_found(self, item):
        """Prend un objet trouve : dans une main libre si possible, sinon au sol."""
        hand = self.free_hand()
        if hand is not None:
            self.set_hand(hand, item)
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
            self.set_hand(1, item)
            return 1
        if self.hands[0] is None:
            self.set_hand(0, item)
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

    def recipe_choice(self, recipe):
        """Matiere retenue parmi les alternatives ("any_of") d'une recette.

        On prend la plus ABONDANTE a proximite, pour entamer en premier ce
        dont on a le plus. None si aucune n'est disponible."""
        pool = self.craft_pool()
        best = None
        for name in recipe.get("any_of", ()):
            if pool.get(name, 0) > 0 and (best is None
                                          or pool[name] > pool.get(best, 0)):
                best = name
        return best

    def recipe_tool_ok(self, recipe):
        """L'outil demande par la recette est-il a proximite ?"""
        name = recipe.get("tool")
        return name is None or self.craft_pool().get(name, 0) > 0

    def can_craft(self, recipe):
        if self.debug:
            return True            # debug : tout craftable, sans ingredients
        pool = self.craft_pool()
        if not all(pool.get(k, 0) >= v
                   for k, v in recipe["ingredients"].items()):
            return False
        if recipe.get("any_of") and self.recipe_choice(recipe) is None:
            return False
        return self.recipe_tool_ok(recipe)

    def do_craft(self, recipe):
        """Fabrique : consomme les ingredients (sol d'abord, puis mains).

        En mode DEBUG le craft ne peut jamais echouer (voir can_craft), mais
        les ingredients REELLEMENT presents sont quand meme consommes : ce
        qu'on voit dans les mains et au sol reste coherent avec l'inventaire.
        Seul ce qui manque est offert."""
        if not self.can_craft(recipe):
            return False
        for item, qty in recipe["ingredients"].items():
            need = qty
            g = self.ground.get(self._cell_key(), {})
            take = min(need, g.get(item, 0))
            if take:
                for _ in range(take):
                    self._take_ground_wear(item)
                g[item] -= take
                if g[item] <= 0:
                    del g[item]
                need -= take
            # Puis dans les mains (on vide l'emplacement correspondant).
            for i in range(len(self.hands)):
                if need <= 0:
                    break
                if self.hands[i] == item:
                    self.set_hand(i, None)
                    need -= 1
            if not g:
                self.ground.pop(self._cell_key(), None)
        # Matiere au CHOIX (feuille ou herbe...) : une seule est consommee.
        choice = self.recipe_choice(recipe)
        if choice is not None:
            self.consume_nearby(choice)
        # OUTIL : pas consomme, mais il s'use. S'il n'y en a pas (mode debug),
        # il n'y a simplement rien a user.
        tool = recipe.get("tool")
        if tool:
            self.wear_tool_nearby(tool, recipe.get("tool_wear", 0.0))
        result = recipe["result"]
        hand = self.free_hand()
        if hand is not None:
            self.set_hand(hand, result)
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
            "fires": self.fires,
            "hand_wear": self.hand_wear,
            "ground_wear": self.ground_wear,
            "chopped": self.chopped,
            "equipment": self.equipment,
            "bag": self.bag,
            "bag_wear": self.bag_wear,
            "penalty_steps": self.penalty_steps,
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
            fires=data.get("fires"),
            hand_wear=data.get("hand_wear"),
            ground_wear=data.get("ground_wear"),
            chopped=data.get("chopped"),
            equipment=data.get("equipment"),
            bag=data.get("bag"),
            bag_wear=data.get("bag_wear"),
            penalty_steps=data.get("penalty_steps"),
            explores=data.get("explores"),
            harvested=data.get("harvested"),
            facing=data.get("facing", 0),
            revealed=data.get("revealed", []),
            action_count=data.get("action_count", 0),
            log=data.get("log", []),
            player_x=data.get("player_x"),
            player_y=data.get("player_y"),
        )
