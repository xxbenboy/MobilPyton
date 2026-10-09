"""
Le MONDE : carte generative en zones, SANS FIN.

Chaque zone fait 1 km x 1 km et a un TYPE (foret, plaine, montagne, lac,
rive). Le type determine sa couleur sur la carte et ce qu'on peut y faire.

LE MONDE N'A PAS DE BORD : chaque case se calcule a la demande, d'apres la
graine de la partie et ses coordonnees (qui peuvent etre negatives), et
seulement quand on la regarde (voir Monde). Memes graine => meme monde,
partout : on n'a donc rien a sauvegarder, et marcher dans une direction en
fait apparaitre de nouvelles a l'infini.

LE LAC NE SE VISITE PAS : on le longe par sa RIVE, une bande de cases de sable
posee tout autour de chaque lac. La rive est la seule case d'un lac ou l'on
puisse aller.

Generation, case par case : un type tire au hasard (d'apres la case), puis
trois LISSAGES (chaque case prend le type majoritaire de son voisinage 3x3),
ce qui cree des REGIONS coherentes (forets, massifs, lacs) plutot qu'un
bruit ; enfin les rives. Une case ne depend que de ses voisines a quatre pas :
elle se calcule seule, sans connaitre le reste du monde.
"""
import math
import random

# LA FENETRE DE LA CARTE : combien de cases elle montre de cote, le joueur
# toujours au milieu (voir MiniMap). Le monde, lui, n'a pas de taille.
GRID_W = 25
GRID_H = 25

# Zone de DEPART : une case prise au hasard pres de l'origine (0, 0).
CENTER_RADIUS = 2

# Types de zones (on commence avec 4). 'weight' = frequence relative a la
# generation. 'color' = couleur sur la mini-carte. 'desc' = a quoi ca sert.
ZONE_TYPES = {
    "Foret": {
        "weight": 4, "color": (0.13, 0.35, 0.17),
        "desc": "Foret neutre : du bois, du calme.",
    },
    "Plaine": {
        "weight": 4, "color": (0.42, 0.60, 0.28),
        "desc": "Plaine : hautes herbes, fleurs et cueillette.",
    },
    "Montagne": {
        "weight": 2, "color": (0.46, 0.44, 0.41),
        "desc": "Montagne : roche et minerais.",
    },
    "Lac": {
        "weight": 2, "color": (0.18, 0.42, 0.62),
        "desc": "Lac : eau profonde. On le longe par sa rive.",
    },
    # LA RIVE n'est jamais tiree au hasard (poids nul) : elle se pose apres
    # coup, autour de chaque lac (voir _pose_les_rives). Couleur de sable sur
    # la carte : le contour qui dit ou l'eau commence.
    "Rive": {
        "weight": 0, "color": (0.83, 0.74, 0.50),
        "desc": "Rive : le bord d'un lac. Eau, roseaux et peche.",
    },
}

DEFAULT_TYPE = "Foret"

# LE LAC NE SE PARCOURT PAS : on n'y marche pas, on ne s'y tient pas. On le
# longe par sa RIVE, qui en est la seule case jouable.
NON_PRATICABLES = {"Lac"}


def praticable(zone_type):
    """Peut-on aller sur une case de ce type ?"""
    return zone_type not in NON_PRATICABLES

# Seules certaines forets et montagnes ont un RUISSEAU (eau potable).
# Les lacs ne sont PAS potables. ~35% des cases foret/montagne ont un ruisseau.
STREAM_TYPES = {"Foret", "Montagne"}


def has_stream(seed, x, y):
    """Cette case a-t-elle un ruisseau ? (deterministe, par case)."""
    rng = random.Random((seed * 73856093) ^ (x * 19349663) ^ (y * 83492791))
    return rng.random() < 0.35


def zone_color(zone_type):
    return ZONE_TYPES.get(zone_type, ZONE_TYPES[DEFAULT_TYPE])["color"]


def zone_desc(zone_type):
    return ZONE_TYPES.get(zone_type, ZONE_TYPES[DEFAULT_TYPE])["desc"]


def _hache(seed, x, y, sel):
    """Un entier pseudo-aleatoire STABLE pour (graine, x, y, sel)."""
    h = (int(seed) * 0x9E3779B1 + x * 0x85EBCA77 + y * 0xC2B2AE3D
         + sel * 0x27D4EB2F) & 0xFFFFFFFFFFFF
    h ^= h >> 23
    h = (h * 0x2127599BF4325C37) & 0xFFFFFFFFFFFFFFFF
    h ^= h >> 47
    return h


class Monde(object):
    """Le monde sans fin d'une graine : `monde[y][x]` est le type de la case
    (x, y), pour tous x et y entiers. Chaque case n'est calculee qu'une fois,
    quand on la demande ; le monde ne s'etend qu'aux endroits qu'on regarde.

    Les cases d'origine se tirent dans la meme reserve ponderee qu'avant
    (ZONE_TYPES, 'weight'), puis passent par LISSAGES lissages et les rives :
    le paysage a le meme caractere que l'ancienne carte de 25 x 25."""

    LISSAGES = 3
    # Au-dela de tant de cases retenues, on oublie tout : elles se
    # recalculeront a l'identique si on y revient.
    MEMOIRE_MAX = 200000

    def __init__(self, seed):
        self.seed = seed
        self._reserve = []
        for name, info in ZONE_TYPES.items():
            self._reserve += [name] * info["weight"]
        self._niveaux = [{} for _ in range(self.LISSAGES + 1)]
        self._final = {}

    def __getitem__(self, y):
        return _Rangee(self, int(y))

    def zone(self, x, y):
        """Le type de la case (x, y)."""
        cle = (x, y)
        z = self._final.get(cle)
        if z is None:
            if len(self._final) > self.MEMOIRE_MAX:
                self._oublie()
            z = self._niveau(self.LISSAGES, x, y)
            if z != "Lac" and any(
                    self._niveau(self.LISSAGES, x + dx, y + dy) == "Lac"
                    for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0))):
                # PAR UN COTE, ET PAS PAR UN COIN : deux cases qui ne se
                # touchent que par l'angle n'ont aucune frontiere commune, on
                # ne voit pas l'eau de l'une depuis l'autre. Le lac garde
                # toutes ses cases ; ce sont les terres autour qui cedent la
                # bande de sable.
                z = "Rive"
            self._final[cle] = z
        return z

    def _niveau(self, k, x, y):
        """Le type de (x, y) apres k lissages."""
        cache = self._niveaux[k]
        cle = (x, y)
        z = cache.get(cle)
        if z is not None:
            return z
        if k == 0:
            z = self._reserve[_hache(self.seed, x, y, 0) % len(self._reserve)]
        else:
            comptes = {}
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    t = self._niveau(k - 1, x + dx, y + dy)
                    comptes[t] = comptes.get(t, 0) + 1
            haut = max(comptes.values())
            gagnants = sorted(t for t, c in comptes.items() if c == haut)
            z = gagnants[_hache(self.seed, x, y, k) % len(gagnants)]
        cache[cle] = z
        return z

    def _oublie(self):
        self._final.clear()
        for cache in self._niveaux:
            cache.clear()


class _Rangee(object):
    """Une rangee du monde : `rangee[x]` est le type de la case (x, y)."""

    __slots__ = ("monde", "y")

    def __init__(self, monde, y):
        self.monde = monde
        self.y = y

    def __getitem__(self, x):
        return self.monde.zone(int(x), self.y)


def dans_le_monde(x, y):
    """Toute case existe : le monde n'a pas de bord."""
    return True


def generate_map(seed):
    """Le monde sans fin de cette graine (voir Monde)."""
    return Monde(seed)


def random_center_cell(seed):
    """Case de depart au hasard pres de l'origine (x, y)."""
    rng = random.Random(seed + 99991)  # graine derivee, independante
    x = rng.randint(-CENTER_RADIUS, CENTER_RADIUS)
    y = rng.randint(-CENTER_RADIUS, CENTER_RADIUS)
    return x, y


def case_de_depart(seed, grid):
    """La case de depart : au hasard pres de l'origine, ou -- si elle tombe
    dans un lac -- la case praticable la plus proche."""
    x, y = random_center_cell(seed)
    return plus_proche_praticable(grid, x, y)


def plus_proche_praticable(grid, x, y):
    """(x, y) si l'on peut s'y tenir, sinon la case praticable la plus proche
    -- une rive, puisque tout lac en est entoure.

    Sert aussi aux parties d'AVANT LES RIVES : un joueur sauvegarde au milieu
    d'un lac reprend sur sa rive. Stable : a distance egale, c'est l'ordre de
    parcours qui decide, toujours le meme."""
    if praticable(grid[y][x]):
        return x, y
    for r in range(1, 200):
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                nx, ny = x + dx, y + dy
                if (max(abs(dx), abs(dy)) == r
                        and praticable(grid[ny][nx])):
                    return nx, ny
    return x, y


# --------------------------------------------------------------------- #
# Gros elements du decor (arbres, buissons, gros rochers) sur la grille
# --------------------------------------------------------------------- #
# Chaque case du monde a une GRILLE de GRILLE x GRILLE cellules, le joueur
# au CENTRE (voir PlaceScreen et zone_scenery.polaire). Les GROS elements du
# decor y occupent une EMPRISE : un arbre une cellule ; un rocher, un
# buisson ou une pepite un carre de deux sur deux. Le decor les dessine A CES
# POSITIONS, et on ne peut PAS y installer d'objet (feu de camp...). Stable
# par case (deduit de la graine de scene).
GRILLE = 11
CENTRE_GRILLE = GRILLE // 2              # la cellule du joueur : (5, 5)
EMPRISE_NATURE = {"tree": (1, 1), "rock": (2, 2), "bush": (2, 2),
                  "nugget": (2, 2)}


# LE TRONC ABATTU : l'arbre coupe tombe A COTE DE SA SOUCHE, couche sur
# LONG_TRONC cases, a partir de DEPART_TRONC case de son ancre, dans l'une
# des huit directions -- tiree au hasard de l'arbre, mais toujours la meme
# pour lui. Il ne tombe ni hors de la grille, ni sur la case du joueur, ni
# sur une case deja prise (`prises`) ; s'il ne trouve pas la place, il tombe
# plus court (LONG_TRONC_COURT, puis LONG_TRONC_MINI : une seule case). Et
# si l'arbre est cerne de toutes parts, il tombe quand meme, par-dessus ce
# qui l'entoure : un arbre abattu laisse TOUJOURS son tronc.
LONG_TRONC = 2.2
LONG_TRONC_COURT = 1.4
LONG_TRONC_MINI = 0.65
DEPART_TRONC = 0.75
DIRECTIONS_TRONC = ((1, 0), (1, 1), (0, 1), (-1, 1), (-1, 0), (-1, -1),
                    (0, -1), (1, -1))


def cases_du_tronc(a, b):
    """Les cases que couvre un tronc couche de a a b (en cases, flottants)."""
    (ax, ay), (bx, by) = a, b
    n = max(2, int(math.hypot(bx - ax, by - ay) / 0.25) + 1)
    out = set()
    for k in range(n + 1):
        t = k / float(n)
        out.add((int(round(ax + (bx - ax) * t)),
                 int(round(ay + (by - ay) * t))))
    return out


def place_du_tronc(cell_seed, ancre, prises):
    """((ax, ay), (bx, by)) : les deux bouts du tronc de l'arbre `ancre`
    (le bout coupe pres de la souche), ou None s'il n'a pas la place."""
    gx, gy = ancre
    hasard = random.Random("%s:%d:%d:tronc" % (cell_seed, gx, gy))
    directions = list(DIRECTIONS_TRONC)
    hasard.shuffle(directions)
    prises = set(prises) | {(gx, gy), (CENTRE_GRILLE, CENTRE_GRILLE)}
    interdites = {(gx, gy), (CENTRE_GRILLE, CENTRE_GRILLE)}
    for evite in (prises, interdites):
        for longueur in (LONG_TRONC, LONG_TRONC_COURT, LONG_TRONC_MINI):
            for dx, dy in directions:
                n = math.hypot(dx, dy)
                ux, uy = dx / n, dy / n
                a = (gx + ux * DEPART_TRONC, gy + uy * DEPART_TRONC)
                b = (gx + ux * (DEPART_TRONC + longueur),
                     gy + uy * (DEPART_TRONC + longueur))
                cases = cases_du_tronc(a, b) - {(gx, gy)}
                if all(0 <= x < GRILLE and 0 <= y < GRILLE
                       and (x, y) not in evite for x, y in cases):
                    return (round(a[0], 3), round(a[1], 3)), \
                        (round(b[0], 3), round(b[1], 3))
    return None


def emprise_nature(kind, ancre):
    """Les cellules couvertes par un element `kind` ancre en `ancre` (son
    coin aux plus petits gx et gy)."""
    fw, fh = EMPRISE_NATURE.get(kind, (1, 1))
    return [(ancre[0] + i, ancre[1] + j) for j in range(fh) for i in range(fw)]


def centre_element(kind, ancre):
    """Le milieu de l'emprise d'un element, en cellules (peut tomber entre
    deux cellules pour une emprise paire)."""
    fw, fh = EMPRISE_NATURE.get(kind, (1, 1))
    return ancre[0] + (fw - 1) / 2.0, ancre[1] + (fh - 1) / 2.0


def distance_au_joueur(kind, ancre):
    """La distance (en cellules) du joueur au milieu d'un element."""
    cx, cy = centre_element(kind, ancre)
    return ((cx - CENTRE_GRILLE) ** 2 + (cy - CENTRE_GRILLE) ** 2) ** 0.5

# COMBIEN D'ELEMENTS AU PLUS sur la grille d'une case. C'est un plafond pour
# TOUT ce qui pousse naturellement, pepites comprises : au-dela, la grille se
# remplit et il ne reste plus ou s'installer. La foret en porte le double --
# c'est ce qui fait qu'on y est a l'etroit, et c'est voulu.
PROXIMITE_MAX = 5
PROXIMITE_MAX_ZONE = {"Foret": 18}

# Ce qui pousse dans chaque zone A COTE des pepites, et en quel nombre. Les
# types sont tires au hasard AVEC REPETITION : "tree" trois fois = 75 %
# d'arbres en foret. Le lac et sa rive n'ont rien de gros a eux -- ni meme de
# pepites (voir SANS_PEPITES).
NATURE_BIG = {
    "Foret": ((14, 18), ("tree", "tree", "tree", "bush")),
    "Plaine": ((3, 5), ("bush",)),
    "Montagne": ((3, 5), ("rock",)),
}


def proximite_max(zone_type):
    """Le plafond d'elements de proximite pour cette zone."""
    return PROXIMITE_MAX_ZONE.get(zone_type, PROXIMITE_MAX)


# --------------------------------------------------------------------- #
# Pepites de mineraux
# --------------------------------------------------------------------- #
# Une case du monde en porte de zero a cinq, dans TOUTES les zones. Le tirage
# n'est pas uniforme : les deux extremes -- aucune, ou le filon complet -- sont
# deux fois plus rares que les comptes intermediaires. Une case vide reste donc
# une deception ordinaire, et une case a cinq une vraie trouvaille.
#
# La table est ecrite en POURCENTS, et leur somme est verifiee au chargement :
# c'est le genre de chiffre qu'on retouche, et une somme a 95 ne se verrait
# jamais autrement qu'en jouant longtemps.
PEPITES_PAR_CASE = {0: 10, 1: 20, 2: 20, 3: 20, 4: 20, 5: 10}
assert sum(PEPITES_PAR_CASE.values()) == 100, PEPITES_PAR_CASE

# LES ZONES SANS PEPITES. Le lac n'en porte aucune : ses cases de proximite
# tombent dans l'eau, et une pierre a demi enfoncee dans un fond de lac ne
# raconte rien -- ni un filon a extraire, ni un decor de berge. Sa RIVE non
# plus : c'est la meme scene, le lac vu de son bord.
SANS_PEPITES = {"Lac", "Rive"}


def nugget_count(cell_seed, zone_type=None):
    """Combien de pepites porte cette case. Stable : c'est sa graine qui
    decide, pas le moment ou l'on regarde.

    La ZONE peut n'en vouloir aucune (voir SANS_PEPITES). Le compte reste
    calcule de la meme facon partout -- c'est la zone qui le met a zero, pas
    une graine differente : le jour ou le lac en reprendra, ses cases
    retrouveront exactement les pepites qu'elles auraient eues."""
    if zone_type in SANS_PEPITES:
        return 0
    rng = random.Random("%s:pepites" % cell_seed)
    valeurs = sorted(PEPITES_PAR_CASE)
    return rng.choices(valeurs,
                       weights=[PEPITES_PAR_CASE[v] for v in valeurs])[0]


def scene_seed(x, y):
    """Graine de la scene d'une case (partagee decor <-> logique de jeu)."""
    return x * 131 + y


def nature_blocked_cells(zone_type, cell_seed):
    """TOUTES les cellules couvertes par un element de PROXIMITE pour cette
    case (un buisson en couvre quatre) : {(gx, gy): type}."""
    out = {}
    for ancre, kind in nature_elements(zone_type, cell_seed).items():
        for cell in emprise_nature(kind, ancre):
            out[cell] = kind
    return out


def nature_elements(zone_type, cell_seed):
    """Les elements de PROXIMITE de cette case, par leur ANCRE (le coin de
    leur emprise aux plus petits gx et gy) :
    {(gx, gy): "tree" | "bush" | "rock" | "nugget"}.

    LES PEPITES SERVENT LES PREMIERES, et le reste remplit ce qui reste sous
    le plafond. Leur nombre est une propriete de la case (voir nugget_count),
    pas un tirage parmi les autres types : une case a cinq pepites en a cinq,
    et ce sont alors les arbres ou les buissons qui cedent la place. C'est
    dans ce sens-la que le plafond agit, et non l'inverse -- sinon une case
    "riche" ne se distinguerait plus d'une autre.

    La cellule du joueur, au CENTRE, reste toujours libre : c'est la qu'il
    se tient (voir zone_scenery.polaire). Les emprises ne se chevauchent pas
    et restent dans la grille ; un element qui ne trouve plus de place est
    simplement omis."""
    centre = (CENTRE_GRILLE, CENTRE_GRILLE)
    cells = [(gx, gy) for gy in range(GRILLE) for gx in range(GRILLE)
             if (gx, gy) != centre]
    plafond = min(proximite_max(zone_type), len(cells))

    pepites = min(nugget_count(cell_seed, zone_type), plafond)
    reste = plafond - pepites
    naturels = 0
    spec = NATURE_BIG.get(zone_type)
    if spec and reste > 0:
        (lo, hi), kinds = spec
        rng = random.Random(f"{cell_seed}:{zone_type}:bigcells")
        naturels = min(rng.randint(lo, hi), reste)
    else:
        kinds = ()

    rng = random.Random(f"{cell_seed}:{zone_type}:bigcells")
    voulus = ["nugget"] * pepites + [rng.choice(kinds)
                                     for _ in range(naturels)]
    prises = {centre}
    out = {}
    candidats = list(cells)
    rng.shuffle(candidats)
    for kind in voulus:
        for ancre in candidats:
            emprise = emprise_nature(kind, ancre)
            if all(0 <= x < GRILLE and 0 <= y < GRILLE
                   and (x, y) not in prises for x, y in emprise):
                out[ancre] = kind
                prises.update(emprise)
                candidats.remove(ancre)
                break
    return out
