"""
LES BETES SAUVAGES : ce qui vit dans le monde, et qu'on peut chasser.

Trois especes pour commencer -- le CHEVREUIL, le SANGLIER et l'ORIGNAL.

ELLES NE SE DEDUISENT PAS DE LA GRAINE DU MONDE, comme les arbres et les
rochers. Une bete BOUGE, et ce qui bouge doit etre retenu dans la partie
(GameState.betes) : c'est la seule chose du paysage qui ne se recalcule pas.

LE MONDE EST SANS FIN, LA HARDE EST FINIE. Neuf betes lachees dans un monde
infini ne se rencontreraient jamais -- il faudrait marcher des heures pour en
croiser une. Elles vivent donc dans un RAYON autour du joueur : celle qui se
retrouve au-dela (parce que c'est LUI qui a marche, pas elle) rentre au bord
de ce rayon, du cote ou elle etait. On tombe ainsi sur une bete a peu pres
une fois sur douze en changeant de case -- assez rare pour que ce soit un
evenement, assez frequent pour qu'on puisse chasser.

LE COMPTE NE CHANGE JAMAIS. Une bete tuee en fait paraitre une autre
ailleurs, loin : la harde se reconstitue, et le joueur ne peut pas vider le
monde de son gibier.

ELLES FUIENT LE BRUIT. Arriver sur une case en fait un peu ; abattre un arbre
en fait beaucoup. Une bete assez proche pour l'entendre QUITTE la case, et
elle ne reviendra pas d'elle-meme : elle ne laisse que ses TRACES, par
lesquelles on peut la PISTER.

UNE BETE BLESSEE ne detale pas si loin, et elle SAIGNE : ses traces sont
alors faciles a suivre. C'est le coeur de la chasse au gros -- on ne tue pas
un orignal d'un seul coup de lance, on le blesse et on le suit.

Ce fichier ne connait ni Kivy ni l'ecran : il dit ou sont les betes et ce
qu'elles font. Leur dessin est dans widgets/bete_dessin.py, et la chasse
dans widgets/action_mode.py.
"""
import math
import random

from src import world

CHEVREUIL = "Chevreuil"
SANGLIER = "Sanglier"
ORIGNAL = "Orignal"

# CE QUI DEFINIT UNE ESPECE.
#
# "zones"    : ou elle vit (une bete ne traverse pas une case qui ne lui va
#              pas -- un orignal reste au bois et au bord de l'eau) ;
# "nombre"   : combien en vivent dans le monde, en meme temps, pour toujours ;
# "hauteur"  : au garrot, en metres -- c'est ce qui donne sa taille a l'ecran,
#              comme pour tout le reste du decor ;
# "peur"     : de combien le bruit la fait partir (1 = au moindre craquement) ;
# "sang"     : combien de blessures il faut pour l'abattre ;
# "minutes"  : le temps de jeu entre deux de ses pas ;
# "butin"    : ce qu'elle laisse. POUR L'INSTANT une carcasse -- la viande,
#              la peau et la fourrure viendront avec le depecage, qui reste a
#              ecrire (les images attendent dans assets/items/futur/).
ESPECES = {
    CHEVREUIL: {
        "zones": ("Foret", "Plaine"),
        "nombre": 4,
        "hauteur": 0.78,
        "longueur": 1.25,
        "peur": 1.00,
        "sang": 1,
        "minutes": 22,
        "butin": {"Carcasse": 1},
    },
    SANGLIER: {
        "zones": ("Foret",),
        "nombre": 3,
        "hauteur": 0.92,
        "longueur": 1.45,
        "peur": 0.55,
        "sang": 2,
        "minutes": 30,
        "butin": {"Carcasse": 1},
    },
    ORIGNAL: {
        "zones": ("Foret", "Rive"),
        "nombre": 2,
        "hauteur": 1.95,
        "longueur": 2.70,
        "peur": 0.40,
        "sang": 3,
        "minutes": 38,
        "butin": {"Carcasse": 2},
    },
}
ORDRE = (CHEVREUIL, SANGLIER, ORIGNAL)

NOMS = {CHEVREUIL: "chevreuil", SANGLIER: "sanglier", ORIGNAL: "orignal"}

# --------------------------------------------------------------------- #
# Les distances et les durees
# --------------------------------------------------------------------- #
# Le rayon ou vit la harde, en cases du monde. Plus grand, on ne croise plus
# rien ; plus petit, on tombe sur une bete a chaque pas et la chasse n'a plus
# de prix.
RAYON_MONDE = 7
RAYON_RETOUR = 6              # ou l'on remet une bete qui est sortie du rayon
# Une bete qui vient d'etre tuee reparait AU BORD du rayon : assez loin pour
# qu'on ne la voie pas surgir, assez pres pour qu'on puisse la retrouver.
RAYON_NAISSANCE = (5, 7)

# A QUELLE DISTANCE LE BRUIT PORTE, en cellules de la grille de proximite.
# Au-dela, la bete entend mais ne bouge pas ; en deca, elle part d'autant plus
# surement qu'on est pres et qu'on est bruyant (voir proba_fuite).
RAYON_ALERTE = 3.5

# De combien de cases une bete s'en va. Effrayee, elle court ; blessee, elle
# ne va pas loin -- c'est ce qui rend la poursuite possible.
FUITE_CASES = (2, 4)
FUITE_BLESSEE = (1, 2)

HEURE = 3600
FAROUCHE_HEURES = 5           # une bete effrayee ne se laisse plus approcher
PISTE_HEURES = 8              # au-dela, les traces ne disent plus rien
PISTE_SANG_HEURES = 14        # le sang tient plus longtemps que les foulees
GIBIER_HEURES = 3             # un gibier piste reste sur la carte ce temps-la

# LE BRUIT DE CHAQUE CHOSE QUE FAIT LE JOUEUR. Entre 0 (rien) et 1 (un arbre
# qui tombe). C'est la seule table a toucher pour rendre une action plus ou
# moins discrete.
BRUIT = {
    "pas": 0.35,              # arriver sur la case
    "cueille": 0.25,          # cueillir des baies
    "boire": 0.20,
    "fouille": 0.30,          # explorer la case
    "coupe": 1.00,            # abattre un arbre, arracher une souche
    "craft": 0.70,            # un assemblage
    "chantier": 1.00,         # batir
    "rate": 1.00,             # une arme qui tombe a cote
}


def espece_de(bete):
    """La fiche de l'espece d'une bete (celle du chevreuil par defaut : une
    sauvegarde d'une version ou l'espece n'existait plus ne doit pas faire
    tomber la partie)."""
    return ESPECES.get(bete.get("espece"), ESPECES[CHEVREUIL])


def nom_de(bete):
    return NOMS.get(bete.get("espece"), "animal")


def _hasard(seed, *parts):
    return random.Random("%s:%s" % (seed, ":".join(str(p) for p in parts)))


def _zones_ok(espece):
    return set(ESPECES.get(espece, ESPECES[CHEVREUIL])["zones"])


def case_qui_va(grid, espece, x, y, rng, rayon=(1, 3), essais=40):
    """Une case praticable PROCHE de (x, y) ou cette espece peut vivre, ou
    None. Tiree dans un anneau : une bete ne se teleporte pas a l'autre bout
    du monde, elle s'eloigne."""
    zones = _zones_ok(espece)
    lo, hi = rayon
    for _ in range(essais):
        d = rng.uniform(lo, hi)
        a = rng.uniform(0.0, 2.0 * math.pi)
        nx = int(round(x + math.cos(a) * d))
        ny = int(round(y + math.sin(a) * d))
        if (nx, ny) == (x, y):
            continue
        z = grid[ny][nx]
        if z in zones and world.praticable(z):
            return nx, ny
    return None


def cellule_libre(rng, prises, essais=60):
    """Une cellule de la grille de proximite ou une bete peut se tenir : ni
    celle du joueur, ni une case deja occupee par un gros element.

    Elle se tient de preference A L'ECART : une bete qui broute a deux pas du
    joueur n'a pas de sens, et c'est aussi ce qui laisse le temps de la voir
    avant qu'elle ne parte."""
    centre = world.CENTRE_GRILLE
    for _ in range(essais):
        gx = rng.randrange(world.GRILLE)
        gy = rng.randrange(world.GRILLE)
        if (gx, gy) in prises:
            continue
        if math.hypot(gx - centre, gy - centre) < 2.5:
            continue
        return gx, gy
    # Faute de mieux : n'importe quelle cellule libre, meme proche.
    for gy in range(world.GRILLE):
        for gx in range(world.GRILLE):
            if (gx, gy) not in prises and (gx, gy) != (centre, centre):
                return gx, gy
    return 0, 0


def prises_de_la_case(grid, x, y):
    """Les cellules deja occupees par le decor de la case (x, y), plus celle
    du joueur : une bete ne se tient pas dans un arbre."""
    centre = world.CENTRE_GRILLE
    try:
        zone = grid[y][x]
    except Exception:
        return {(centre, centre)}
    prises = set(world.nature_blocked_cells(zone, world.scene_seed(x, y)))
    prises.add((centre, centre))
    return prises


def nouvelle(espece, x, y, gx, gy, t, ident=0):
    """Une bete neuve, a sa place et a l'heure `t` (secondes de jeu).

    Son NUMERO la suit toute sa vie : c'est par lui que des traces
    retrouvent la bete qui les a laissees (voir GameState.suit_les_traces).
    """
    return {"id": int(ident), "espece": espece, "x": int(x), "y": int(y),
            "gx": int(gx), "gy": int(gy),
            "cap": 0.0,                 # ou elle va, en degres (0 = nord)
            "t": int(t),                # quand elle a bouge pour la derniere fois
            "sang": 0,                  # blessures encaissees
            "farouche": 0,              # avant cette heure, elle ne se montre pas
            }


def peuple(seed, x, y, grid, t):
    """La harde du debut de partie : chaque espece en son nombre, posee
    autour du joueur mais jamais sur sa case."""
    betes = []
    for i, espece in enumerate(ORDRE):
        for k in range(ESPECES[espece]["nombre"]):
            rng = _hasard(seed, "harde", i, k)
            case = case_qui_va(grid, espece, x, y, rng,
                               rayon=(3, RAYON_MONDE))
            if case is None:
                continue
            gx, gy = cellule_libre(rng, prises_de_la_case(grid, *case))
            bete = nouvelle(espece, case[0], case[1], gx, gy, t,
                            len(betes) + 1)
            bete["cap"] = rng.uniform(0.0, 360.0)
            betes.append(bete)
    return betes


def proba_fuite(bete, bruit, distance):
    """La chance qu'une bete parte, pour un bruit donne, a `distance`
    cellules d'elle.

    Le bruit porte en 1/distance : deux fois plus loin, deux fois moins de
    chances de la faire partir. Une bete deja FAROUCHE ne reste pas : elle a
    deja ete derangee une fois."""
    if bete.get("sang", 0) and distance <= RAYON_ALERTE:
        return 1.0            # une bete blessee ne laisse pas approcher
    peur = espece_de(bete)["peur"]
    d = max(1.0, float(distance))
    return max(0.0, min(1.0, peur * float(bruit) * RAYON_ALERTE / d))


def distance_au_joueur(bete):
    """De combien de cellules la bete est du joueur, sur sa grille."""
    c = world.CENTRE_GRILLE
    return math.hypot(bete["gx"] - c, bete["gy"] - c)


def avance(bete, grid, t, rng):
    """Fait vivre une bete jusqu'a l'heure `t` : elle broute et se deplace
    dans sa case, et change de case de temps en temps.

    PAR PAS, ET NON D'UN SEUL BOND : une partie laissee de cote une journee
    ne doit pas retrouver ses betes a l'autre bout du monde. On borne donc le
    nombre de pas rattrapes -- au-dela, la bete a simplement erre sur place.
    """
    fiche = espece_de(bete)
    pas = max(60, int(fiche["minutes"]) * 60)
    ecoule = int(t) - int(bete.get("t", t))
    if ecoule < pas:
        return False
    n = min(12, ecoule // pas)
    bete["t"] = int(t)
    for _ in range(n):
        # Elle tourne un peu, puis avance d'une cellule dans son cap.
        bete["cap"] = (bete.get("cap", 0.0) + rng.uniform(-55.0, 55.0)) % 360.0
        a = math.radians(bete["cap"])
        gx = bete["gx"] + int(round(math.sin(a)))
        gy = bete["gy"] + int(round(math.cos(a)))
        if 0 <= gx < world.GRILLE and 0 <= gy < world.GRILLE:
            bete["gx"], bete["gy"] = gx, gy
        else:
            # Au bord de sa case, elle passe dans la case d'a cote.
            case = case_qui_va(grid, bete["espece"], bete["x"], bete["y"],
                               rng, rayon=(1, 1))
            if case is not None:
                bete["x"], bete["y"] = case
                bete["gx"], bete["gy"] = cellule_libre(
                    rng, prises_de_la_case(grid, *case))
            bete["cap"] = (bete["cap"] + 180.0) % 360.0
    # Elle ne reste pas plantee dans un arbre pousse entre-temps.
    prises = prises_de_la_case(grid, bete["x"], bete["y"])
    if (bete["gx"], bete["gy"]) in prises:
        bete["gx"], bete["gy"] = cellule_libre(rng, prises)
    return True


def recentre(bete, px, py, grid, rng):
    """Ramene dans le rayon de jeu une bete que le joueur a laissee loin
    derriere lui, du cote ou elle etait. Renvoie True si elle a bouge."""
    dx, dy = bete["x"] - px, bete["y"] - py
    d = math.hypot(dx, dy)
    if d <= RAYON_MONDE:
        return False
    n = max(1e-6, d)
    vx, vy = dx / n, dy / n
    for r in (RAYON_RETOUR, RAYON_RETOUR - 1, RAYON_RETOUR - 2, 2):
        cx = int(round(px + vx * r))
        cy = int(round(py + vy * r))
        case = case_qui_va(grid, bete["espece"], cx, cy, rng, rayon=(0, 2))
        if case is not None:
            bete["x"], bete["y"] = case
            bete["gx"], bete["gy"] = cellule_libre(
                rng, prises_de_la_case(grid, *case))
            return True
    return False


def fuit(bete, grid, rng, t, blessee=False):
    """La bete quitte sa case. Renvoie (dx, dy) : par ou elle est partie,
    pour les traces qu'elle laisse -- ou None si elle n'a nulle part ou
    aller (elle reste alors, mais farouche)."""
    depart = (bete["x"], bete["y"])
    rayon = FUITE_BLESSEE if blessee else FUITE_CASES
    case = case_qui_va(grid, bete["espece"], bete["x"], bete["y"], rng,
                       rayon=rayon)
    if case is None:
        case = case_qui_va(grid, bete["espece"], bete["x"], bete["y"], rng,
                           rayon=(1, 2))
    # Une bete BLESSEE n'est pas farouche : elle est a bout, on peut la
    # rattraper. C'est le sens meme de la poursuite.
    bete["farouche"] = 0 if blessee else int(t) + FAROUCHE_HEURES * HEURE
    if case is None:
        return None
    bete["x"], bete["y"] = case
    bete["gx"], bete["gy"] = cellule_libre(rng, prises_de_la_case(grid, *case))
    bete["t"] = int(t)
    return case[0] - depart[0], case[1] - depart[1]


def nait_loin(espece, px, py, grid, rng, t):
    """Une bete neuve, au bord du rayon de jeu : celle qui remplace une bete
    tuee. None si l'espece n'a nulle part ou vivre par ici."""
    a = rng.uniform(0.0, 2.0 * math.pi)
    r = rng.uniform(*RAYON_NAISSANCE)
    cx = int(round(px + math.cos(a) * r))
    cy = int(round(py + math.sin(a) * r))
    case = case_qui_va(grid, espece, cx, cy, rng, rayon=(0, 3))
    if case is None:
        case = case_qui_va(grid, espece, px, py, rng,
                           rayon=(3, RAYON_MONDE))
    if case is None:
        return None
    gx, gy = cellule_libre(rng, prises_de_la_case(grid, *case))
    bete = nouvelle(espece, case[0], case[1], gx, gy, t)
    bete["cap"] = rng.uniform(0.0, 360.0)
    bete["farouche"] = int(t) + FAROUCHE_HEURES * HEURE
    return bete


def direction_lisible(dx, dy):
    """"vers le nord-est" : par ou filent des traces.

    SUR LA CARTE DU MONDE, le nord est le y DECROISSANT (GameState.CARDINALS
    commence par (0, -1), et la mini-carte met le nord en haut). C'est
    l'inverse de la grille de proximite, ou le nord monte avec gy : les deux
    conventions cohabitent depuis toujours, autant la nommer ici."""
    if dx == 0 and dy == 0:
        return "sur place"
    points = ((0, -1, "le nord"), (1, -1, "le nord-est"), (1, 0, "l'est"),
              (1, 1, "le sud-est"), (0, 1, "le sud"),
              (-1, 1, "le sud-ouest"), (-1, 0, "l'ouest"),
              (-1, -1, "le nord-ouest"))
    n = math.hypot(dx, dy)
    ux, uy = dx / n, dy / n
    meilleur = max(points, key=lambda p: (p[0] * ux + p[1] * uy)
                   / math.hypot(p[0], p[1]))
    return "vers " + meilleur[2]


__all__ = ["CHEVREUIL", "SANGLIER", "ORIGNAL", "ESPECES", "ORDRE", "NOMS",
           "BRUIT", "RAYON_ALERTE", "RAYON_MONDE", "PISTE_HEURES",
           "PISTE_SANG_HEURES", "GIBIER_HEURES", "HEURE",
           "espece_de", "nom_de", "peuple", "avance", "recentre", "fuit",
           "nait_loin", "proba_fuite", "distance_au_joueur", "cellule_libre",
           "prises_de_la_case", "case_qui_va", "direction_lisible",
           "nouvelle"]
