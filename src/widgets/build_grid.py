"""
LA GRILLE DE CONSTRUCTION : le volume d'un chantier, en cubes.

Un plan de construction reserve une surface au sol. Batir dessus demande de
designer un endroit DANS L'ESPACE -- pas seulement ou, mais a quelle hauteur.
Le volume est donc decoupe en cubes, et il faut les montrer tous a la fois :
ceux du sol comme ceux du toit, sans que les uns cachent les autres.

POURQUOI UNE VUE ISOMETRIQUE, et pas la vue de dessus de l'ecran de pose.
Vue d'en haut, les quatre etages se superposent EXACTEMENT : le volume se
lirait comme une seule grille plate, et choisir une hauteur serait impossible.
La vue en premiere personne, elle, cache l'arriere derriere l'avant. L'axono-
metrie est la seule qui montre les trois dimensions d'un coup et garde chaque
cube a une place a lui.

    ecran_x = cx + (gx - gy) * DEMI_LARGEUR
    ecran_y = cy - (gx + gy) * DEMI_PROFONDEUR + gz * HAUTEUR

L'axe X part vers la droite-bas, l'axe Y vers la gauche-bas, l'axe Z vers le
haut. C'est la projection des jeux de construction, et elle se lit sans
explication.

CE MODULE NE CONTIENT AUCUN DESSIN : seulement la projection et le volume.
Il se verifie donc au calcul, sans construire d'ecran.
"""

# Le volume d'un plan de palier 1, en cubes : largeur, profondeur, hauteur.
# La surface au sol (2 x 2 cases) est redecoupee en 4 x 4 : deux cubes par
# case et par axe. La hauteur, elle, ne vient d'aucune case -- c'est la
# hauteur batissable du plan.
VOLUME_T1 = (4, 4, 4)

# Proportions d'un cube a l'ecran, en fraction de la taille de reference.
# La face du dessus est un losange deux fois plus large que haut : c'est la
# convention isometrique, et l'oeil la lit comme un carre pose a plat.
DEMI_LARGEUR = 1.0
DEMI_PROFONDEUR = 0.5
# La hauteur vaut EXACTEMENT deux fois la demi-profondeur, et ce n'est pas un
# reglage : c'est ce qui fait que le dessus d'un cube coincide avec le dessous
# de celui du dessus. A toute autre valeur les etages s'interpenetrent, et
# l'axe de profondeur cesse d'etre la diagonale (1, 1, 1) -- l'ordre de dessin
# ci-dessous n'y tiendrait plus.
HAUTEUR = 2.0 * DEMI_PROFONDEUR


def volume_for(name):
    """Le volume batissable d'un plan pose. (0, 0, 0) s'il n'en offre pas."""
    from src import items
    return VOLUME_T1 if name == items.BLUEPRINT_T1 else (0, 0, 0)


def project(gx, gy, gz, cx, cy, taille):
    """Projette un SOMMET de la grille en coordonnees ecran.

    (gx, gy, gz) sont des indices de sommet, donc de 0 a n inclus : un volume
    de 4 cubes de cote a 5 sommets par axe. `taille` est le cote d'un cube.
    (cx, cy) est le point ou tombe le sommet (0, 0, 0)."""
    x = cx + (gx - gy) * DEMI_LARGEUR * taille
    y = cy - (gx + gy) * DEMI_PROFONDEUR * taille + gz * HAUTEUR * taille
    return x, y


def fit(volume, largeur, hauteur, marge=0.86):
    """Taille de cube et point d'ancrage pour CENTRER le volume a l'ecran.

    Rend (taille, cx, cy) tels que le volume entier tienne dans la boite
    donnee, en occupant `marge` de sa plus petite dimension utile.

    On ne devine pas l'encombrement : on projette les huit coins avec une
    taille de 1, on mesure la boite obtenue, puis on met a l'echelle. Le
    volume reste ainsi centre quelle que soit sa forme -- un plan plus large
    que haut, plus tard, n'aura rien a changer ici."""
    nx, ny, nz = volume
    if nx <= 0 or ny <= 0 or nz <= 0:
        return 0.0, largeur / 2.0, hauteur / 2.0
    coins = [project(x, y, z, 0.0, 0.0, 1.0)
             for x in (0, nx) for y in (0, ny) for z in (0, nz)]
    xs = [p[0] for p in coins]
    ys = [p[1] for p in coins]
    span_x = max(xs) - min(xs)
    span_y = max(ys) - min(ys)
    taille = min(largeur * marge / span_x, hauteur * marge / span_y)
    # Le centre de la boite projetee doit tomber au centre de l'ecran : on en
    # deduit ou placer le sommet (0, 0, 0).
    cx = largeur / 2.0 - (min(xs) + max(xs)) / 2.0 * taille
    cy = hauteur / 2.0 - (min(ys) + max(ys)) / 2.0 * taille
    return taille, cx, cy


def cube_faces(x, y, z, cx, cy, taille):
    """Les trois faces VISIBLES d'un cube, en polygones ecran.

    Un cube en axonometrie ne montre jamais que trois faces : le dessus, et
    deux cotes. Les trois autres sont derriere, et les dessiner ne ferait que
    doubler les traits.

    Rend [(nom, [(x, y), ...]), ...] du plus loin au plus proche."""
    def p(dx, dy, dz):
        return project(x + dx, y + dy, z + dz, cx, cy, taille)

    return [
        ("dessus", [p(0, 0, 1), p(1, 0, 1), p(1, 1, 1), p(0, 1, 1)]),
        ("gauche", [p(0, 1, 0), p(0, 1, 1), p(0, 0, 1), p(0, 0, 0)]),
        ("droite", [p(0, 1, 0), p(1, 1, 0), p(1, 1, 1), p(0, 1, 1)]),
    ]


def ordre_dessin(volume):
    """Les cubes, du plus LOIN au plus proche.

    Dans cette projection, l'axe de PROFONDEUR est la diagonale (1, 1, 1) :
    c'est la direction le long de laquelle on peut avancer sans bouger a
    l'ecran (le decalage en x s'annule, celui en y aussi, HAUTEUR valant deux
    fois DEMI_PROFONDEUR). Un cube est donc d'autant plus PRES que x + y + z
    est grand.

    Les trier par cette somme croissante suffit : ce qui est devant se dessine
    par-dessus ce qui est derriere, sans avoir a trier face par face."""
    nx, ny, nz = volume
    cubes = [(x, y, z)
             for x in range(nx) for y in range(ny) for z in range(nz)]
    cubes.sort(key=lambda c: c[0] + c[1] + c[2])
    return cubes
