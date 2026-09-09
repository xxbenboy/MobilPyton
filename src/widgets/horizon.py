"""
LES PAYSAGES VOISINS, vus a l'horizon.

Le monde est une grille de cases d'un kilometre, et chacune se dessinait comme
si elle etait seule au monde : on tenait au bord d'une plaine sans jamais
voir la foret qui commencait juste apres. La carte disait qu'elle etait la,
l'oeil ne la voyait pas.

Cette couche ajoute au fond de la scene ce qu'il y a AUTOUR : une ligne
d'arbres si la case suivante est une foret, une crete si c'est une montagne,
un miroir d'eau si c'est un lac.

TROIS VOISINS SEULEMENT, et ils dependent de l'ORIENTATION du joueur : ce
qu'il a devant lui occupe le milieu de l'ecran, ce qu'il a a sa gauche et a sa
droite en occupe les bords. La case derriere lui ne se voit pas -- elle est
dans son dos. Tourner change donc le paysage, ce qui est le point : c'est ce
qui permet de reperer une foret AVANT d'y aller.

LES COTES SONT PLUS PROCHES QUE LE FOND. La case de devant commence a un
kilometre, celles des cotes commencent au bord de la case ou l'on se tient --
donc bien plus pres. Elles sont dessinees plus grandes et moins voilees. Sans
cet ecart, les trois voisins se liraient comme une seule ligne d'horizon
plate, et l'on perdrait justement l'information de direction.

Tout est dessine EN SILHOUETTE et VOILE de bleu pale : c'est ce que fait
l'atmosphere sur un kilometre, et c'est aussi ce qui empeche ces formes de
concurrencer le decor du premier plan. Elles doivent se lire d'un coup d'oeil
et ne jamais retenir le regard.
"""
from kivy.graphics import Color, Ellipse, Triangle

# Fenetre horizontale de chaque voisin, en fraction de la largeur de l'ecran.
# Les plages SE CHEVAUCHENT volontairement : deux voisins de meme type doivent
# se fondre l'un dans l'autre sans laisser de trou au raccord.
SPANS = {
    "face": (0.18, 0.82),
    "gauche": (-0.02, 0.34),
    "droite": (0.66, 1.02),
}

# Eloignement de chaque voisin. 1.0 = la case de devant (un kilometre) ; les
# cotes commencent au bord de la case actuelle, donc bien plus pres.
DIST = {"face": 1.0, "gauche": 0.62, "droite": 0.62}

# Couleur de la BRUME dans laquelle tout se fond au loin.
HAZE = (0.66, 0.74, 0.84)

# Part de brume a un kilometre. C'est ce voile qui fait la distance : sans
# lui, une foret lointaine aurait le meme vert franc que celle du premier plan
# et paraitrait a portee de main.
HAZE_FAR = 0.42

# Hauteur de reference des silhouettes, en fraction de la hauteur de l'ecran,
# pour un voisin situe a un kilometre. Les cotes sont plus grands (voir DIST).
HEIGHTS = {
    "Foret": 0.055,
    "Montagne": 0.115,
    "Lac": 0.014,
    "Plaine": 0.026,
}


def _hazy(color, dist):
    """Melange une couleur vers la brume, d'autant plus qu'elle est loin."""
    part = HAZE_FAR * dist
    return tuple(c + (HAZE[i] - c) * part for i, c in enumerate(color[:3]))


# --------------------------------------------------------------------- #
# Signatures : a quoi reconnait-on chaque paysage DE LOIN ?
# --------------------------------------------------------------------- #
# On ne cherche pas a dessiner la case voisine, seulement ce qui la rend
# reconnaissable en une fraction de seconde et de tres loin.

def _foret(x0, x1, base, haut, dist, rng):
    """Une ligne d'arbres : une frange dentelee, jamais des arbres separes.

    A un kilometre, on ne distingue plus les troncs : on voit une bande
    sombre au sommet irregulier. On empile donc beaucoup de petites formes qui
    se CHEVAUCHENT -- des cimes isolees se liraient comme des buissons poses
    sur une colline, pas comme une foret."""
    fond = _hazy((0.16, 0.30, 0.19), dist)
    devant = _hazy((0.10, 0.22, 0.14), dist)
    largeur = x1 - x0
    for couche, (col, ech, dy) in enumerate(((fond, 1.0, 0.35),
                                             (devant, 0.78, 0.0))):
        Color(*col, 1)
        n = max(8, int(largeur / (haut * 0.42)))
        for i in range(n + 1):
            fx = x0 + largeur * i / n
            y = base(fx) + dy * haut
            th = haut * ech * rng.uniform(0.62, 1.0)
            tw = th * rng.uniform(0.55, 0.85)
            if rng.random() < 0.55:            # conifere : cime pointue
                Triangle(points=[fx - tw, y - haut * 0.5, fx + tw,
                                 y - haut * 0.5, fx, y + th])
            else:                              # feuillu : cime ronde
                Ellipse(pos=(fx - tw, y - haut * 0.5),
                        size=(tw * 2, th + haut * 0.5))


def _montagne(x0, x1, base, haut, dist, rng):
    """Deux ou trois cretes qui se recouvrent.

    Une montagne se reconnait a sa SILHOUETTE, pas a sa matiere : des pentes
    droites et un sommet net. On les fait se chevaucher pour donner
    l'epaisseur d'un massif plutot qu'un pic isole."""
    largeur = x1 - x0
    for i, (part, ech) in enumerate(((0.62, 1.0), (0.42, 0.72), (0.30, 0.5))):
        col = _hazy((0.40, 0.41, 0.49), min(1.0, dist + 0.12 * i))
        Color(*col, 1)
        cx = x0 + largeur * (0.30 + 0.42 * ((i * 7 + 3) % 5) / 4.0)
        demi = largeur * part * 0.5
        y = base(cx) - haut * 0.10
        Triangle(points=[cx - demi, y, cx + demi, y, cx, y + haut * ech])


def _lac(x0, x1, base, haut, dist, rng):
    """Une lame d'eau claire, posee a plat sur la ligne d'horizon.

    Un lac ne DEPASSE pas : il est au niveau du sol. Ce qui le trahit de loin,
    c'est une bande horizontale plus claire et parfaitement plate -- rien
    d'autre dans un paysage n'a cette regularite."""
    y = base((x0 + x1) * 0.5)
    largeur = x1 - x0
    # Une LENTILLE tres aplatie, pas un rectangle : ses bouts s'amincissent
    # et se fondent dans le terrain. Un rectangle donnait deux coupures
    # verticales franches, qui se lisaient comme une bande peinte et non
    # comme une etendue d'eau.
    Color(*_hazy((0.28, 0.46, 0.62), dist), 1)
    Ellipse(pos=(x0, y - haut * 1.4), size=(largeur, haut * 2.8))
    # Un MINCE reflet du ciel le long du bord haut. Volontairement etroit :
    # etale sur toute l'eau, il la rendait blanche -- une soucoupe posee sur
    # l'horizon plutot qu'un lac.
    Color(*_hazy((0.58, 0.72, 0.84), dist * 0.5), 1)
    Ellipse(pos=(x0 + largeur * 0.08, y + haut * 0.55),
            size=(largeur * 0.84, haut * 0.55))


def _plaine(x0, x1, base, haut, dist, rng):
    """Une ondulation basse, a peine plus claire.

    Une plaine lointaine, ce n'est presque rien : de l'herbe qui continue.
    On ne pose donc qu'un renflement tres doux -- assez pour que l'horizon ne
    soit pas une ligne droite, pas assez pour attirer l'oeil."""
    col = _hazy((0.40, 0.54, 0.30), dist)
    Color(*col, 1)
    largeur = x1 - x0
    for i in range(3):
        cx = x0 + largeur * (0.2 + 0.3 * i)
        rw = largeur * rng.uniform(0.35, 0.55)
        rh = haut * rng.uniform(0.7, 1.3)
        Ellipse(pos=(cx - rw, base(cx) - rh), size=(rw * 2, rh * 2))


_SIGNATURES = {
    "Foret": _foret,
    "Montagne": _montagne,
    "Lac": _lac,
    "Plaine": _plaine,
}


def draw(neighbours, x0, width, base, height, rng):
    """Dessine les paysages voisins au fond de la scene.

    `neighbours` : {"face": type, "gauche": type, "droite": type}, chaque
                   valeur pouvant etre None (bord de carte, ou rien a montrer).
    `base`       : fonction fx (0 a 1) -> y de la ligne d'horizon a l'ecran.
                   C'est la crete de la scene actuelle ; les silhouettes s'y
                   posent, et le terrain dessine ENSUITE leur cache le pied.

    A appeler AVANT le terrain : ce qui est loin passe derriere ce qui est
    pres, et les silhouettes n'ont pas besoin d'etre decoupees proprement en
    bas -- le sol s'en charge.

    Le FOND est dessine en premier, les COTES par-dessus : sur les zones ou
    ils se chevauchent, c'est le plus proche qui gagne."""
    if not neighbours:
        return
    for cote in ("face", "gauche", "droite"):
        zone = neighbours.get(cote)
        signature = _SIGNATURES.get(zone)
        if signature is None:
            continue
        dist = DIST[cote]
        a, b = SPANS[cote]
        # Un voisin proche est PLUS GRAND : la taille est ce qui dit la
        # distance, avant meme la couleur.
        haut = HEIGHTS[zone] * height / max(0.4, dist)

        def au_sol(x, _a=a, _b=b):
            return base(min(1.0, max(0.0, (x - x0) / max(1.0, width))))

        signature(x0 + a * width, x0 + b * width, au_sol, haut, dist, rng)


def neighbours_of(state):
    """{"face"/"gauche"/"droite": type de zone ou None} pour l'etat courant.

    C'est ici que l'orientation entre en jeu : `dir_vector` traduit "devant",
    "a droite" et "a gauche" en deplacements absolus selon la direction que
    regarde le joueur. La case DERRIERE n'est pas demandee -- elle est dans
    son dos."""
    from src import world
    out = {}
    for cote, turn in (("face", 0), ("droite", 1), ("gauche", 3)):
        dx, dy = state.dir_vector(turn)
        nx, ny = state.player_x + dx, state.player_y + dy
        if 0 <= nx < world.GRID_W and 0 <= ny < world.GRID_H:
            voisin = state.grid[ny][nx]
            # Une case du MEME type que celle ou l'on est n'apporte rien : le
            # decor la montre deja. On evite ainsi de poser une ligne d'arbres
            # sur l'horizon d'une foret.
            out[cote] = None if voisin == state.current_zone() else voisin
        else:
            out[cote] = None
    return out
