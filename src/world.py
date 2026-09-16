"""
Le MONDE : carte generative en zones.

La carte est une grille de GRID_W x GRID_H zones (625 = 25x25 pour commencer).
Chaque zone fait 1 km x 1 km et a un TYPE (foret, plaine, montagne, lac).
Le type determine sa couleur sur la mini-carte et, plus tard, ce qu'on peut y
faire.

La carte est GENERATIVE : entierement deduite de la graine (seed) de la
partie. Memes graine => meme monde. On n'a donc pas besoin de la sauvegarder :
on la regenere au chargement.

Generation : on remplit d'abord chaque case au hasard, puis on lisse plusieurs
fois (chaque case prend le type majoritaire de son voisinage). Ca cree des
REGIONS coherentes (forets, massifs, lacs) plutot qu'un bruit aleatoire.
"""
import random

# Taille de la carte (25 x 25 = 625 zones).
GRID_W = 25
GRID_H = 25

# Zone de DEPART : une case prise au hasard dans le carre central.
CENTER_RADIUS = 2          # 5x5 cases autour du centre

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
        "desc": "Lac : eau et peche.",
    },
}

DEFAULT_TYPE = "Foret"

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


def _smooth(grid, rng):
    """Une passe de lissage : chaque case prend le type majoritaire autour."""
    new = [[None] * GRID_W for _ in range(GRID_H)]
    for y in range(GRID_H):
        for x in range(GRID_W):
            counts = {}
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < GRID_W and 0 <= ny < GRID_H:
                        t = grid[ny][nx]
                        counts[t] = counts.get(t, 0) + 1
            best = max(counts.values())
            winners = [t for t, c in counts.items() if c == best]
            new[y][x] = rng.choice(winners) if len(winners) > 1 else winners[0]
    return new


def generate_map(seed):
    """Carte 2D grid[y][x] de types de zones, deduite de la graine."""
    rng = random.Random(seed)
    pool = []
    for name, info in ZONE_TYPES.items():
        pool += [name] * info["weight"]

    grid = [[rng.choice(pool) for _ in range(GRID_W)] for _ in range(GRID_H)]
    for _ in range(3):                 # 3 passes => regions bien dessinees
        grid = _smooth(grid, rng)
    return grid


def random_center_cell(seed):
    """Case de depart au hasard dans le carre central (x, y)."""
    rng = random.Random(seed + 99991)  # graine derivee, independante
    cx, cy = GRID_W // 2, GRID_H // 2
    x = cx + rng.randint(-CENTER_RADIUS, CENTER_RADIUS)
    y = cy + rng.randint(-CENTER_RADIUS, CENTER_RADIUS)
    return x, y


# --------------------------------------------------------------------- #
# Gros elements du decor (arbres, buissons, gros rochers) sur la grille
# --------------------------------------------------------------------- #
# Chaque case du monde a une scene avec une grille 5x5 (voir PlaceScreen).
# Les GROS elements du decor occupent des cellules de cette grille : le
# decor les dessine A CES POSITIONS, et on ne peut PAS y installer d'objet
# (feu de camp...). Stable par case (deduit de la graine de scene).

# COMBIEN D'ELEMENTS AU PLUS sur la grille d'une case. C'est un plafond pour
# TOUT ce qui pousse naturellement, pepites comprises : au-dela, la grille se
# remplit et il ne reste plus ou s'installer. La foret en porte le double --
# c'est ce qui fait qu'on y est a l'etroit, et c'est voulu.
PROXIMITE_MAX = 5
PROXIMITE_MAX_ZONE = {"Foret": 10}

# Ce qui pousse dans chaque zone A COTE des pepites, et en quel nombre. Les
# types sont tires au hasard AVEC REPETITION : "tree" trois fois = 75 %
# d'arbres en foret. Le Lac n'a rien de gros a lui -- il n'y porte que des
# pepites.
NATURE_BIG = {
    "Foret": ((6, 9), ("tree", "tree", "tree", "bush")),
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


def nugget_count(cell_seed):
    """Combien de pepites porte cette case. Stable : c'est sa graine qui
    decide, pas le moment ou l'on regarde."""
    rng = random.Random("%s:pepites" % cell_seed)
    valeurs = sorted(PEPITES_PAR_CASE)
    return rng.choices(valeurs,
                       weights=[PEPITES_PAR_CASE[v] for v in valeurs])[0]


def scene_seed(x, y):
    """Graine de la scene d'une case (partagee decor <-> logique de jeu)."""
    return x * 131 + y


def nature_blocked_cells(zone_type, cell_seed):
    """Cellules 5x5 occupees par un element de PROXIMITE pour cette case :
    {(gx, gy): "tree" | "bush" | "rock" | "nugget"}.

    LES PEPITES SERVENT LES PREMIERES, et le reste remplit ce qui reste sous
    le plafond. Leur nombre est une propriete de la case (voir nugget_count),
    pas un tirage parmi les autres types : une case a cinq pepites en a cinq,
    et ce sont alors les arbres ou les buissons qui cedent la place. C'est
    dans ce sens-la que le plafond agit, et non l'inverse -- sinon une case
    "riche" ne se distinguerait plus d'une autre.

    La case du joueur (2, 0) reste toujours libre : c'est la qu'il se tient."""
    plafond = proximite_max(zone_type)
    cells = [(gx, gy) for gy in range(5) for gx in range(5)
             if (gx, gy) != (2, 0)]
    plafond = min(plafond, len(cells))

    pepites = min(nugget_count(cell_seed), plafond)
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
    tires = rng.sample(cells, pepites + naturels)
    out = {cell: "nugget" for cell in tires[:pepites]}
    for cell in tires[pepites:]:
        out[cell] = rng.choice(kinds)
    return out
