"""
Le MONDE : carte generative en zones.

La carte est une grille de GRID_W x GRID_H zones (625 = 25x25 pour commencer).
Chaque zone fait 1 km x 1 km et a un TYPE (foret, champ, montagne, lac).
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
    "Champ": {
        "weight": 4, "color": (0.55, 0.60, 0.24),
        "desc": "Champ : herbes et cueillette.",
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
