"""
LES PAYSAGES VOISINS, vus a l'horizon.

Le monde est une grille de cases d'un kilometre, et chacune se dessinait comme
si elle etait seule au monde : on tenait au bord d'une plaine sans jamais
voir la foret qui commencait juste apres. La carte disait qu'elle etait la,
l'oeil ne la voyait pas.

Cette couche ajoute au fond de la scene ce qu'il y a AUTOUR : une ligne
d'arbres si la case suivante est une foret, une crete si c'est une montagne.
Le lac et la plaine, eux, ne s'y montrent pas -- rien de PLAT ne depasse
l'horizon a un kilometre (voir plus bas).

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

Tout est VOILE de la couleur du ciel : c'est ce que fait l'atmosphere sur un
kilometre, et c'est aussi ce qui empeche ces formes de concurrencer le decor
du premier plan. Elles doivent se lire d'un coup d'oeil et ne jamais retenir
le regard. La foret y est faite des IMAGES d'arbres du jeu (sapins et
feuillus) ; la montagne, qui n'a pas d'image, reste une silhouette.

CE MODULE NE FAIT QUE L'HORIZON. La case voisine entre AUSSI dans la scene
par les COTES de l'ecran, et la elle n'est pas une silhouette : ses elements
sont poses sur la meme grille que ceux de la case, avec les memes dessins et
les memes tailles. Cela vit dans zone_scenery -- voir _edge_items.
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
# EN PANORAMA, chaque panneau couvre un quart du tour (voir panorama.py) : le
# voisin de sa direction en occupe TOUTE la largeur. Vers un bord ou le
# panneau d'a cote montre un AUTRE paysage ("voisin_g" / "voisin_d"), sa
# silhouette S'ABAISSE jusqu'a rien (sur FONDU_BORD de la largeur) : pas de
# coupure verticale. Entre deux voisins pareils, elle continue d'un bloc.
SPAN_PLEIN = (0.0, 1.0)
FONDU_BORD = 0.22


def _enveloppe(x0, x1, part, gauche=True, droite=True):
    """1 au milieu de [x0, x1], descendant doucement a 0 vers les bords
    demandes."""
    marge = max(1.0, (x1 - x0) * part)

    def env(x):
        d = min(x - x0 if gauche else marge, x1 - x if droite else marge)
        t = max(0.0, min(1.0, d / marge))
        return t * t * (3.0 - 2.0 * t)
    return env

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
    "Foret": 0.100,
    "Montagne": 0.200,
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

def _foret(x0, x1, base, haut, dist, rng, env=None, au_ras=False,
           arbre=None):
    """Une ligne d'arbres : une frange dentelee, jamais des arbres separes.

    A un kilometre, on ne distingue plus les troncs : on voit une bande
    sombre au sommet irregulier. On empile donc beaucoup de petits arbres
    qui se CHEVAUCHENT -- des cimes isolees se liraient comme des buissons
    poses sur une colline, pas comme une foret.

    LES VRAIS ARBRES DU JEU, quand on les a : `arbre(nom, x, pied, hauteur,
    brume)` pose l'image d'un sapin ("pine_tree") ou d'un feuillu
    ("forest_tree"), voilee de `brume` (0 a 1), et rend Faux s'il n'y a pas
    d'image -- l'arbre est alors dessine en forme simple, comme avant. Les
    tirages sont les memes dans les deux cas."""
    fond = _hazy((0.16, 0.30, 0.19), dist)
    devant = _hazy((0.10, 0.22, 0.14), dist)
    largeur = x1 - x0
    for couche, (col, ech, dy) in enumerate(((fond, 1.0, 0.35),
                                             (devant, 0.78, 0.0))):
        # La rangee du fond est plus loin : plus voilee.
        brume = min(1.0, HAZE_FAR * dist + (0.14 if couche == 0 else 0.0))
        Color(*col, 1)
        n = max(8, int(largeur / (haut * 0.42)))
        for i in range(n + 1):
            fx = x0 + largeur * i / n
            k = env(fx) if env is not None else 1.0
            y = base(fx) + dy * haut * k
            th = haut * ech * rng.uniform(0.62, 1.0) * k
            tw = th * rng.uniform(0.55, 0.85)
            if th < 1.0:
                continue
            # Le pied plonge sous la crete, que le sol recouvre ; AU RAS
            # (sol en nappe, dessine dessous), il part de la crete meme.
            pied = y if au_ras else y - haut * 0.5
            conifere = rng.random() < 0.55
            # L'image entiere dans la tranche : au bord d'un panneau du
            # panorama, la decoupe la trancherait net.
            demi = (th + (y - pied)) * (0.32 if conifere else 0.50)
            xi = min(max(fx, x0 + demi), x1 - demi)
            if arbre is not None and arbre(
                    "pine_tree" if conifere else "forest_tree", xi, pied,
                    th + (y - pied), brume):
                Color(*col, 1)                 # l'image a change la couleur
                continue
            if conifere:                       # conifere : cime pointue
                Triangle(points=[fx - tw, pied, fx + tw, pied, fx, y + th])
            else:                              # feuillu : cime ronde
                Ellipse(pos=(fx - tw, pied), size=(tw * 2, th + (y - pied)))


def _montagne(x0, x1, base, haut, dist, rng, env=None, au_ras=False,
              arbre=None):
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
        k = env(cx) if env is not None else 1.0
        y = base(cx) - (0.0 if au_ras else haut * 0.10)
        Triangle(points=[cx - demi, y, cx + demi, y,
                         cx, y + haut * (0.10 + (ech - 0.10) * k)])


# NI LE LAC NI LA PLAINE N'APPARAISSENT A L'HORIZON, et c'est voulu.
#
# Ce sont les deux paysages PLATS du jeu. A un kilometre, rien de plat ne
# depasse la ligne d'horizon : c'est de la geometrie, pas un choix de style.
# Les faire apparaitre quand meme demandait de tricher -- une bande d'eau
# posee sur la crete, un renflement d'herbe -- et cela se voyait : une lame
# bleue accrochee a l'horizon ne ressemblait pas a un lac.
#
# Ces deux voisins-la se decouvrent donc par les COTES de l'ecran, ou ils sont
# assez proches pour se voir vraiment (voir _edge_shore dans zone_scenery), et
# par la carte. Seuls la foret et la montagne, qui s'elevent, se signalent de
# loin.


_SIGNATURES = {
    "Foret": _foret,
    "Montagne": _montagne,
}


def draw(neighbours, x0, width, base, height, rng, plein=False,
         au_ras=False, arbre=None):
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
    ils se chevauchent, c'est le plus proche qui gagne.

    `arbre` : de quoi poser les IMAGES d'arbres du jeu (voir _foret)."""
    if not neighbours:
        return
    for cote in ("face", "gauche", "droite"):
        zone = neighbours.get(cote)
        signature = _SIGNATURES.get(zone)
        if signature is None:
            continue
        dist = DIST[cote]
        a, b = SPAN_PLEIN if plein else SPANS[cote]
        # Un voisin proche est PLUS GRAND : la taille est ce qui dit la
        # distance, avant meme la couleur.
        haut = HEIGHTS[zone] * height / max(0.4, dist)

        def au_sol(x, _a=a, _b=b):
            return base(min(1.0, max(0.0, (x - x0) / max(1.0, width))))

        xa, xb = x0 + a * width, x0 + b * width
        env = _enveloppe(xa, xb, FONDU_BORD,
                         neighbours.get("voisin_g") != zone,
                         neighbours.get("voisin_d") != zone) if plein else None
        signature(xa, xb, au_sol, haut, dist, rng, env=env, au_ras=au_ras,
                  arbre=arbre)


# Jusqu'ou chercher la terre ferme de l'autre cote de l'eau. Au-dela, le
# paysage serait de toute facon trop loin pour se lire, et la berge d'en face
# garde alors sa vegetation par defaut.
PORTEE_BERGE = 6

# Ce qu'on traverse du regard sans y voir de rive : l'eau, et le sable de sa
# rive, qui n'arrete pas la vue non plus.
_TRAVERSABLE = ("Lac", "Rive")


def zone_den_face(state, portee=PORTEE_BERGE, direction=None):
    """Le premier paysage SOLIDE droit devant, par-dela l'eau -- ou None.

    C'est ce qu'il y a VRAIMENT sur l'autre berge. Depuis une rive, la case
    d'en face est presque toujours le lac lui-meme : demander le voisin
    immediat repondrait "de l'eau", ce qui ne dit rien de ce qu'on voit au
    bout. On avance donc droit devant, case par case, tant qu'on ne traverse
    que de l'eau et du sable.

    Rend None au bord de la carte ou si l'eau va plus loin que `portee` :
    la berge d'en face prend alors sa vegetation par defaut, faute de mieux
    -- mentir sur ce qui s'y trouve serait pire que de rester neutre."""
    from src import world
    from src.game_state import CARDINALS
    if direction is None:
        dx, dy = state.dir_vector(0)
    else:
        dx, dy = CARDINALS[direction % 4]
    for pas in range(1, portee + 1):
        nx, ny = state.player_x + dx * pas, state.player_y + dy * pas
        if not (0 <= nx < world.GRID_W and 0 <= ny < world.GRID_H):
            return None
        zone = state.grid[ny][nx]
        if zone not in _TRAVERSABLE:
            return zone
    return None


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
            # UNE CASE DU MEME TYPE COMPTE AUTANT QU'UNE AUTRE. Elle etait
            # ecartee ici, au motif que "le decor la montre deja" ; mais ce
            # qu'on voyait alors, dans une foret entouree de foret, c'etait le
            # VIDE au-dessus des arbres -- un ciel noir posE sur la cime, comme
            # si le bois s'arretait net au bout de la case. C'est le contraire
            # de ce que l'horizon est cense dire.
            #
            # Poser une ligne d'arbres sur l'horizon d'une foret etait le
            # risque redoute. Il ne se produit pas : les silhouettes lointaines
            # sont noyees de brume (voir _hazy) et decoupees irregulierement,
            # de sorte qu'elles se lisent comme un fond et non comme une haie.
            out[cote] = state.grid[ny][nx]
        else:
            out[cote] = None
    return out


def voisin_dans(state, direction):
    """Le type de la case voisine dans la direction ABSOLUE `direction`
    (0 nord, 1 est, 2 sud, 3 ouest), ou None au bord de la carte."""
    from src import world
    from src.game_state import CARDINALS
    dx, dy = CARDINALS[direction % 4]
    nx, ny = state.player_x + dx, state.player_y + dy
    if 0 <= nx < world.GRID_W and 0 <= ny < world.GRID_H:
        return state.grid[ny][nx]
    return None
