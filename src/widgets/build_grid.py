"""
LA GRILLE DE CONSTRUCTION : le volume d'un chantier, en cubes, ORIENTABLE.

Un plan de construction reserve une surface au sol. Batir dessus demande de
designer un endroit DANS L'ESPACE -- pas seulement ou, mais a quelle hauteur.
Le volume est donc decoupe en cubes, et il faut les montrer tous a la fois :
ceux du sol comme ceux du toit, sans que les uns cachent les autres.

LE VOLUME SE TOURNE AU DOIGT. Une orientation figee ne suffit pas : quelle
qu'elle soit, elle laisse trois faces du cube dans le dos, et les cubes qui
s'y trouvent sont impossibles a designer. On garde donc deux angles -- le tour
(autour de la verticale) et l'inclinaison -- qui permettent d'amener n'importe
quel point du volume face a soi. Les deux suffisent : une troisieme rotation
ne ferait que pencher l'image, sans jamais montrer un cube de plus.

LA PROJECTION EST ORTHOGRAPHIQUE : deux cubes de meme taille se dessinent de
la meme taille, qu'ils soient devant ou derriere. C'est ce qu'on attend d'un
plan de construction -- on y compare des longueurs, on ne s'y promene pas.

    p tourne d'abord du TOUR autour de la verticale, puis de l'INCLINAISON
    autour de l'axe horizontal de l'ecran. Il reste (x, y, z) :
        x -> abscisse ecran
        z -> ordonnee ecran
        y -> PROFONDEUR, la camera etant en y negatif. Un y plus grand est
             donc plus LOIN.

L'ECHELLE NE CHANGE JAMAIS pendant qu'on tourne. Elle est calculee sur la
SPHERE englobante du volume, et non sur son encombrement a l'orientation
courante : une sphere se projette en cercle, donc ce cercle a la meme taille
sous tous les angles. Le volume ne peut ainsi ni deborder ni se mettre a
respirer pendant qu'on le fait tourner -- deux defauts qu'un recadrage a
chaque image aurait apportes.

CE MODULE NE CONTIENT AUCUN DESSIN : seulement la projection et le volume.
Il se verifie donc au calcul, sans construire d'ecran.
"""
import math

# Le volume d'un plan de palier 1, en cubes : largeur, profondeur, hauteur.
# La surface au sol (2 x 2 cases) est redecoupee en 4 x 4 : deux cubes par
# case et par axe. La hauteur, elle, ne vient d'aucune case -- c'est la
# hauteur batissable du plan.
VOLUME_T1 = (4, 4, 4)

# Orientation de depart : de trois quarts et vue d'un peu au-dessus. C'est
# celle qui montre le plus de cubes d'un coup -- on voit deux cotes et le
# dessus -- donc celle qui demande le moins de manipulation pour commencer.
TOUR_DEFAUT = math.radians(35.0)
INCLINAISON_DEFAUT = math.radians(28.0)

# L'inclinaison ne va pas jusqu'au zenith : pile a la verticale, la vue
# s'aplatit en une grille de dessus ou les etages se confondent, et le sens de
# rotation s'inverse d'un cheveu de doigt.
INCLINAISON_MAX = math.radians(88.0)

# Combien tourner pour un doigt qui traverse tout l'ecran.
TOUR_PAR_ECRAN = math.radians(300.0)


def volume_for(name):
    """Le volume batissable d'un plan pose. (0, 0, 0) s'il n'en offre pas."""
    from src import items
    return VOLUME_T1 if name == items.BLUEPRINT_T1 else (0, 0, 0)


def centre(volume):
    """Le milieu du volume, en sommets de grille."""
    nx, ny, nz = volume
    return (nx / 2.0, ny / 2.0, nz / 2.0)


def rayon(volume):
    """Le rayon de la sphere englobante, en cubes."""
    nx, ny, nz = volume
    return math.sqrt(nx * nx + ny * ny + nz * nz) / 2.0


def tourne(p, tour, inclinaison):
    """Tourne un point autour du centre du monde. Rend (x, y, z) oriente."""
    x, y, z = p
    ct, st = math.cos(tour), math.sin(tour)
    x, y = x * ct - y * st, x * st + y * ct        # tour, autour de Z
    ci, si = math.cos(inclinaison), math.sin(inclinaison)
    y, z = y * ci - z * si, y * si + z * ci        # inclinaison, autour de X
    return x, y, z


def echelle(volume, largeur, hauteur, marge=0.90):
    """Taille d'un cube a l'ecran, pour que le volume tienne SOUS TOUS LES
    ANGLES.

    Calculee sur la sphere englobante, donc constante quand on tourne (voir
    l'entete). C'est deliberement un peu petit -- la sphere depasse des coins
    du volume -- mais c'est le prix d'une image qui ne saute pas."""
    r = rayon(volume)
    if r <= 0:
        return 0.0
    return min(largeur, hauteur) * marge / (2.0 * r)


def project(gx, gy, gz, volume, cx, cy, taille, tour, inclinaison):
    """Projette un SOMMET de la grille en (x_ecran, y_ecran, profondeur).

    (gx, gy, gz) sont des indices de sommet, donc de 0 a n inclus : un volume
    de 4 cubes de cote a 5 sommets par axe. (cx, cy) est le point de l'ecran
    ou tombe le CENTRE du volume.

    La profondeur rendue croit vers le LOIN : elle sert a trier."""
    mx, my, mz = centre(volume)
    x, y, z = tourne((gx - mx, gy - my, gz - mz), tour, inclinaison)
    return cx + x * taille, cy + z * taille, y


_SOMMETS = ((0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0),
            (0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1))

# Les six faces d'un cube : les quatre sommets dans le sens direct, puis la
# normale sortante. La normale sert a savoir si la face regarde la camera.
_FACES = (
    ((0, 1, 2, 3), (0, 0, -1)),      # dessous
    ((4, 5, 6, 7), (0, 0, 1)),       # dessus
    ((0, 1, 5, 4), (0, -1, 0)),      # devant
    ((3, 2, 6, 7), (0, 1, 0)),       # derriere
    ((0, 3, 7, 4), (-1, 0, 0)),      # gauche
    ((1, 2, 6, 5), (1, 0, 0)),       # droite
)

# Les douze aretes d'un cube, en indices de sommets.
_ARETES = ((0, 1), (1, 2), (2, 3), (3, 0),
           (4, 5), (5, 6), (6, 7), (7, 4),
           (0, 4), (1, 5), (2, 6), (3, 7))


def _coins(cube, volume, cx, cy, taille, tour, inclinaison):
    x, y, z = cube
    return [project(x + dx, y + dy, z + dz, volume, cx, cy, taille,
                    tour, inclinaison)
            for dx, dy, dz in _SOMMETS]


def cube_aretes(cube, volume, cx, cy, taille, tour, inclinaison):
    """Les douze aretes d'un cube, en segments ecran [(x1,y1),(x2,y2)]."""
    c = _coins(cube, volume, cx, cy, taille, tour, inclinaison)
    return [((c[a][0], c[a][1]), (c[b][0], c[b][1])) for a, b in _ARETES]


def cube_faces_vues(cube, volume, cx, cy, taille, tour, inclinaison):
    """Les faces d'un cube qui REGARDENT la camera, en polygones ecran.

    Les autres sont dans le dos : les remplir n'ajouterait que du voile. On
    les reconnait a leur normale une fois tournee -- la camera etant en y
    negatif, une face lui fait face quand la sienne pointe vers les y
    negatifs."""
    c = _coins(cube, volume, cx, cy, taille, tour, inclinaison)
    out = []
    for indices, normale in _FACES:
        # Le seuil n'est pas de la prudence numerique gratuite. PILE dans
        # l'axe, une face est vue par la TRANCHE : son aire a l'ecran est
        # nulle, et le signe de sa normale ne tient plus qu'au signe du zero
        # en virgule flottante. Elle serait donc retenue ou non selon
        # l'humeur du calcul, sans rien changer a l'image. On l'ecarte
        # franchement.
        if tourne(normale, tour, inclinaison)[1] > -1e-9:
            continue
        out.append([(c[i][0], c[i][1]) for i in indices])
    return out


def ordre_dessin(volume, tour, inclinaison):
    """Les cubes, du plus LOIN au plus proche, pour l'orientation donnee.

    L'ordre depend de l'angle : c'etait une constante tant que la vue etait
    figee, ce n'en est plus une. On trie sur la profondeur du CENTRE de chaque
    cube -- pour des cubes tous identiques, poses sur une grille reguliere,
    cela suffit a ce qu'aucun proche ne passe derriere un lointain."""
    nx, ny, nz = volume
    if min(nx, ny, nz) <= 0:
        return []
    mx, my, mz = centre(volume)

    def prof(c):
        return tourne((c[0] + 0.5 - mx, c[1] + 0.5 - my, c[2] + 0.5 - mz),
                      tour, inclinaison)[1]

    cubes = [(x, y, z)
             for x in range(nx) for y in range(ny) for z in range(nz)]
    cubes.sort(key=prof, reverse=True)          # le plus loin d'abord
    return cubes


def dans_polygone(x, y, pts):
    """Le point (x, y) est-il dans le polygone ? (lancer de rayon)"""
    dedans = False
    n = len(pts)
    for i in range(n):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        if (y1 > y) != (y2 > y):
            xx = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < xx:
                dedans = not dedans
    return dedans


def cube_sous(x, y, volume, cx, cy, taille, tour, inclinaison):
    """Quel cube se trouve sous le point (x, y) ? None si aucun.

    On parcourt du PLUS PROCHE au plus loin et on garde le premier touche :
    deux cubes alignes sur l'axe de vue se projettent au meme endroit, et
    c'est celui de devant qu'on designe -- comme partout ailleurs."""
    for cube in reversed(ordre_dessin(volume, tour, inclinaison)):
        for pts in cube_faces_vues(cube, volume, cx, cy, taille,
                                   tour, inclinaison):
            if dans_polygone(x, y, pts):
                return cube
    return None


def boite_aretes(volume):
    """Les douze aretes de la boite englobante, en sommets de grille."""
    nx, ny, nz = volume
    coins = [(x, y, z) for x in (0, nx) for y in (0, ny) for z in (0, nz)]
    out = []
    for i, a in enumerate(coins):
        for b in coins[i + 1:]:
            # Deux coins ne forment une arete que s'ils different sur UN seul
            # axe : sinon c'est une diagonale, qui traverserait la boite.
            if sum(1 for k in range(3) if a[k] != b[k]) == 1:
                out.append((a, b))
    return out
