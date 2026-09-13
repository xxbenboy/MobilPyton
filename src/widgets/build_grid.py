"""
LA GRILLE DE CONSTRUCTION : le volume d'un chantier, en cubes, ORIENTABLE.

Un plan de construction reserve une surface au sol. Batir dessus demande de
designer un endroit DANS L'ESPACE -- pas seulement ou, mais a quelle hauteur.
Le volume est donc decoupe en cubes.

ON N'EN MONTRE QUE CE QU'IL Y A A FAIRE. Le chantier avance par ETAGES, du bas
vers le haut, et seuls les niveaux de l'etage en cours sont ouverts. Soixante
cubes vides d'un coup ne se lisent pas ; huit si.

LE VOLUME SE TOURNE AU DOIGT. Une orientation figee laisse trois faces du cube
dans le dos, et les cubes qui s'y trouvent sont impossibles a designer. On
garde donc deux angles -- le tour (autour de la verticale) et l'inclinaison --
qui permettent d'amener n'importe quel point face a soi. Les deux suffisent :
une troisieme rotation ne ferait que pencher l'image sans montrer un cube de
plus.

LA PROJECTION EST ORTHOGRAPHIQUE : deux cubes de meme taille se dessinent de
la meme taille, qu'ils soient devant ou derriere. C'est ce qu'on attend d'un
plan de construction -- on y compare des longueurs, on ne s'y promene pas.

    p tourne d'abord du TOUR autour de la verticale, puis de l'INCLINAISON
    autour de l'axe horizontal de l'ecran. Il reste (x, y, z) :
        x -> abscisse ecran
        z -> ordonnee ecran
        y -> PROFONDEUR, la camera etant en y negatif. Un y plus grand est
             donc plus LOIN.

TOUT SE CADRE SUR UNE BOITE, pas sur le volume entier. C'est ce qui permet a
un etage de deux niveaux d'occuper l'ecran au lieu d'y flotter en miniature :
on cadre ce qu'on montre. L'ECHELLE, elle, est calculee sur la SPHERE
englobante de cette boite, et non sur son encombrement a l'orientation
courante : une sphere se projette en cercle, donc de la meme taille sous tous
les angles. Le contenu ne peut ainsi ni deborder ni se mettre a respirer
pendant qu'on le fait tourner.

CE MODULE NE CONTIENT AUCUN DESSIN : seulement la projection et les regles du
chantier. Il se verifie donc au calcul, sans construire d'ecran.
"""
import math

# Le volume d'un plan de palier 1, en cubes : largeur, profondeur, hauteur.
# CHAQUE CASE du plan vaut 4 x 4 cubes. Le plan couvrant 2 x 2 cases, cela
# fait 8 x 8 au sol. La hauteur est de 8 elle aussi : elle ne vient d'aucune
# case, c'est la hauteur batissable.
VOLUME_T1 = (8, 8, 8)

# --------------------------------------------------------------------- #
# LES ETAPES
# --------------------------------------------------------------------- #
ETAPES = ("sol", "bas des murs", "haut des murs", "toit")

# LA PIECE QUE CHAQUE ETAGE ATTEND. Un etage ne se batit pas de n'importe
# quoi : le sol veut des sols, les deux etages de murs veulent des murs, le
# toit veut des toits. Les autres pieces sont grisees -- montrees, pour qu'on
# sache qu'elles existent, mais refusees.
#
# Les DEUX etages de murs prennent la meme piece : c'est la hauteur qui les
# distingue, pas la matiere. Un mur bas et un mur haut sont le meme mur.
PIECE_PAR_ETAPE = ("sol", "mur", "mur", "toit")

# HAUTEUR D'UNE PIECE, en unites de cube. Un sol et un toit sont des DALLES :
# larges et minces. Un mur est un PAN : aussi large qu'une dalle, mais quatre
# fois plus haut. C'est ce qui donne a l'abri sa hauteur -- deux etages de
# murs font huit unites, de quoi tenir debout -- sans multiplier les etages.
#
# Un niveau de grille ne vaut donc plus une unite de hauteur mais celle de son
# etage : toute la projection passe par z_bas et z_haut, jamais par z.
HAUTEUR_ETAPE = (1.0, 4.0, 4.0, 1.0)

# Les modeles de pose : combien de cubes d'un coup. Poser un mur de neuf cubes
# case par case demandait neuf touchers et autant de chances de se tromper.
MODELES = (1, 4, 9)

# UN ETAGE = UN NIVEAU de cubes. C'est ce qui donne son sens a la regle du
# chantier : tant qu'un etage n'est pas finalise, le niveau du dessus n'existe
# pas encore a l'ecran. Avec deux niveaux par etage, le second s'ouvrait des
# que le premier portait une piece -- donc AVANT la fin de l'etage -- et
# l'ordre du chantier se perdait.
#
# Les quatre etages occupent donc les quatre premiers niveaux du volume. Les
# suivants restent en reserve : un plan de palier superieur y ajoutera ses
# propres etages.
NIVEAUX_PAR_ETAPE = 1

# Numero de l'etape du TOIT : la derniere. Elle a une regle a elle (voir
# cubes_utilisables).
ETAPE_TOIT = len(ETAPES) - 1

# Valeur d'etape signifiant que le chantier est TERMINE.
TERMINE = len(ETAPES)

# --------------------------------------------------------------------- #
# ORIENTATION
# --------------------------------------------------------------------- #
# De trois quarts et vue d'un peu au-dessus : celle qui montre le plus de
# cubes d'un coup, donc celle qui demande le moins de manipulation pour
# commencer.
TOUR_DEFAUT = math.radians(35.0)
INCLINAISON_DEFAUT = math.radians(28.0)

# L'inclinaison ne va pas jusqu'au zenith : pile a la verticale, la vue
# s'aplatit en une grille de dessus ou les niveaux se confondent, et le sens
# de rotation s'inverse d'un cheveu de doigt.
INCLINAISON_MAX = math.radians(88.0)

# Combien tourner pour un doigt qui traverse tout l'ecran.
TOUR_PAR_ECRAN = math.radians(300.0)


def volume_for(name):
    """Le volume batissable d'un plan pose. (0, 0, 0) s'il n'en offre pas."""
    from src import items
    return VOLUME_T1 if name == items.BLUEPRINT_T1 else (0, 0, 0)


# --------------------------------------------------------------------- #
# BOITES
# --------------------------------------------------------------------- #
def boite_du_volume(volume):
    """La boite qui contient tout le volume, hauteurs d'etage comprises."""
    nx, ny, nz = volume
    return ((0, 0, 0), (nx, ny, z_haut(nz - 1)))


def boite_des(cubes, volume):
    """La boite qui contient juste ces cubes.

    Rend la boite du volume entier si la liste est vide : il faut toujours
    quelque chose a cadrer."""
    if not cubes:
        return boite_du_volume(volume)
    xs = [c[0] for c in cubes]
    ys = [c[1] for c in cubes]
    return ((min(xs), min(ys), min(z_bas(c[2]) for c in cubes)),
            (max(xs) + 1, max(ys) + 1, max(z_haut(c[2]) for c in cubes)))


def centre_boite(boite):
    (x0, y0, z0), (x1, y1, z1) = boite
    return ((x0 + x1) / 2.0, (y0 + y1) / 2.0, (z0 + z1) / 2.0)


def rayon_boite(boite):
    """Le rayon de la sphere englobante de la boite, en cubes."""
    (x0, y0, z0), (x1, y1, z1) = boite
    dx, dy, dz = x1 - x0, y1 - y0, z1 - z0
    return math.sqrt(dx * dx + dy * dy + dz * dz) / 2.0


def echelle(boite, largeur, hauteur, marge=0.92):
    """Taille d'un cube a l'ecran, pour que la boite tienne SOUS TOUS LES
    ANGLES (voir l'entete)."""
    r = rayon_boite(boite)
    if r <= 0:
        return 0.0
    return min(largeur, hauteur) * marge / (2.0 * r)


# --------------------------------------------------------------------- #
# PROJECTION
# --------------------------------------------------------------------- #
def tourne(p, tour, inclinaison):
    """Tourne un point autour de l'origine. Rend (x, y, z) oriente."""
    x, y, z = p
    ct, st = math.cos(tour), math.sin(tour)
    x, y = x * ct - y * st, x * st + y * ct        # tour, autour de Z
    ci, si = math.cos(inclinaison), math.sin(inclinaison)
    y, z = y * ci - z * si, y * si + z * ci        # inclinaison, autour de X
    return x, y, z


def project(gx, gy, gz, boite, cx, cy, taille, tour, inclinaison):
    """Projette un SOMMET de la grille en (x_ecran, y_ecran, profondeur).

    (cx, cy) est le point de l'ecran ou tombe le CENTRE de la boite. La
    profondeur rendue croit vers le LOIN : elle sert a trier."""
    mx, my, mz = centre_boite(boite)
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


def _coins(cube, boite, cx, cy, taille, tour, inclinaison):
    """Les huit sommets d'un cube, en coordonnees ecran.

    La coordonnee verticale passe par z_bas / z_haut, jamais par z : depuis
    que les etages ont des epaisseurs differentes -- un pan de mur vaut quatre
    dalles -- l'indice d'un niveau n'est plus sa hauteur."""
    x, y, z = cube
    bas, haut = z_bas(z), z_haut(z)
    return [project(x + dx, y + dy, haut if dz else bas, boite, cx, cy,
                    taille, tour, inclinaison)
            for dx, dy, dz in _SOMMETS]


def cube_aretes(cube, boite, cx, cy, taille, tour, inclinaison):
    """Les douze aretes d'un cube, en segments ecran [(x1,y1),(x2,y2)]."""
    c = _coins(cube, boite, cx, cy, taille, tour, inclinaison)
    return [((c[a][0], c[a][1]), (c[b][0], c[b][1])) for a, b in _ARETES]


# LA LUMIERE DU CHANTIER, dans le repere de l'ECRAN : elle tombe d'en haut,
# un peu de face et un peu de la gauche. Elle est FIXE par rapport a l'ecran et
# non au volume : c'est le volume qu'on tourne sous la lampe, pas la lampe
# autour du volume, et une face qui passe de l'ombre a la lumiere pendant
# qu'on pivote est justement ce qui donne son relief au geste.
#
# Rappel du repere tourne : x = abscisse ecran, z = ordonnee ecran, y =
# profondeur vers le LOIN. Une lumiere qui vient de face a donc un y negatif.
_LUMIERE = (-0.35, -0.55, 0.76)

# Ce qui reste d'eclairement a une face qui tourne le dos a la lampe. Zero
# donnerait des faces noires, et une maison n'a pas de face noire en plein
# jour : le ciel eclaire aussi ce que le soleil manque.
_AMBIANTE = 0.42


def cube_faces_eclairees(cube, boite, cx, cy, taille, tour, inclinaison):
    """Les faces vues d'un cube, CHACUNE AVEC SON ECLAIREMENT.

    Rend [(polygone ecran, facteur)]. Le facteur sert a nuancer la couleur :
    sans lui, un cube plein d'une seule couleur se lit comme une tache et le
    volume disparait. Les aretes suffisaient tant que les cubes etaient
    transparents ; des qu'ils deviennent pleins, c'est l'ombre qui doit dire
    ou une face s'arrete et ou la suivante commence."""
    c = _coins(cube, boite, cx, cy, taille, tour, inclinaison)
    out = []
    for indices, normale in _FACES:
        # Le seuil n'est pas de la prudence numerique gratuite. PILE dans
        # l'axe, une face est vue par la TRANCHE : son aire a l'ecran est
        # nulle, et le signe de sa normale ne tient plus qu'au signe du zero
        # en virgule flottante. Elle serait donc retenue ou non selon
        # l'humeur du calcul, sans rien changer a l'image.
        n = tourne(normale, tour, inclinaison)
        if n[1] > -1e-9:
            continue
        eclat = sum(a * b for a, b in zip(n, _LUMIERE))
        facteur = _AMBIANTE + (1.0 - _AMBIANTE) * max(0.0, eclat)
        out.append(([(c[i][0], c[i][1]) for i in indices], facteur))
    return out


def cube_faces_vues(cube, boite, cx, cy, taille, tour, inclinaison):
    """Les faces d'un cube qui REGARDENT la camera, en polygones ecran.

    Les autres sont dans le dos : les remplir n'ajouterait que du voile."""
    return [pts for pts, _f in cube_faces_eclairees(
        cube, boite, cx, cy, taille, tour, inclinaison)]


def coin_haut_droit(cube, boite, cx, cy, taille, tour, inclinaison):
    """Le sommet du cube le plus HAUT et le plus a DROITE a l'ecran.

    Sert a poser la croix de retrait : elle doit se trouver au meme endroit
    relatif quel que soit l'angle, et ce coin-la est celui que l'oeil
    identifie comme "en haut a droite" du cube."""
    c = _coins(cube, boite, cx, cy, taille, tour, inclinaison)
    return max(c, key=lambda p: (p[1] + p[0]) )[:2]


def ordre_dessin(cubes, boite, tour, inclinaison):
    """Les cubes donnes, du plus LOIN au plus proche.

    L'ordre depend de l'angle : c'etait une constante tant que la vue etait
    figee, ce n'en est plus une. On trie sur la profondeur du CENTRE de
    chaque cube -- pour des cubes tous identiques, poses sur une grille
    reguliere, cela suffit."""
    mx, my, mz = centre_boite(boite)

    def prof(c):
        milieu_z = (z_bas(c[2]) + z_haut(c[2])) / 2.0
        return tourne((c[0] + 0.5 - mx, c[1] + 0.5 - my, milieu_z - mz),
                      tour, inclinaison)[1]

    return sorted(cubes, key=prof, reverse=True)     # le plus loin d'abord


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


def cube_sous(x, y, cubes, boite, cx, cy, taille, tour, inclinaison):
    """Lequel des cubes donnes se trouve sous le point (x, y) ? None si aucun.

    On parcourt du PLUS PROCHE au plus loin et on garde le premier touche :
    deux cubes alignes sur l'axe de vue se projettent au meme endroit, et
    c'est celui de devant qu'on designe -- comme partout ailleurs."""
    for cube in reversed(ordre_dessin(cubes, boite, tour, inclinaison)):
        for pts in cube_faces_vues(cube, boite, cx, cy, taille,
                                   tour, inclinaison):
            if dans_polygone(x, y, pts):
                return cube
    return None


def boite_aretes(boite):
    """Les douze aretes d'une boite, en sommets de grille."""
    (x0, y0, z0), (x1, y1, z1) = boite
    coins = [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
    out = []
    for i, a in enumerate(coins):
        for b in coins[i + 1:]:
            # Deux coins ne forment une arete que s'ils different sur UN seul
            # axe : sinon c'est une diagonale, qui traverserait la boite.
            if sum(1 for k in range(3) if a[k] != b[k]) == 1:
                out.append((a, b))
    return out


# --------------------------------------------------------------------- #
# REGLES DU CHANTIER
# --------------------------------------------------------------------- #
def niveaux_de(etape):
    """Les niveaux de cubes (z) que couvre une etape."""
    if etape < 0 or etape >= len(ETAPES):
        return ()
    bas = etape * NIVEAUX_PAR_ETAPE
    return tuple(range(bas, bas + NIVEAUX_PAR_ETAPE))


def etape_de(z):
    """L'etape a laquelle appartient un niveau."""
    return z // NIVEAUX_PAR_ETAPE


def piece_de_etape(etape):
    """La seule piece qu'on puisse poser a cette etape, ou None."""
    if 0 <= etape < len(PIECE_PAR_ETAPE):
        return PIECE_PAR_ETAPE[etape]
    return None


def hauteur_niveau(z):
    """La hauteur d'un niveau, en unites de cube.

    Elle depend de l'etage : une dalle vaut une unite, un pan de mur quatre.
    Les niveaux au-dela des etages definis valent une unite -- ils sont en
    reserve, rien n'y est encore batissable."""
    e = etape_de(z)
    return HAUTEUR_ETAPE[e] if 0 <= e < len(HAUTEUR_ETAPE) else 1.0


def z_bas(z):
    """La hauteur a laquelle COMMENCE un niveau, en unites de cube.

    C'est la somme des hauteurs des niveaux du dessous : un niveau n'est plus
    a la hauteur de son indice des lors que les etages ont des epaisseurs
    differentes."""
    return sum(hauteur_niveau(k) for k in range(int(z)))


def z_haut(z):
    """La hauteur a laquelle FINIT un niveau."""
    return z_bas(z) + hauteur_niveau(z)


def cubes_modele(nombre, cube, volume):
    """Les cubes qu'un modele de `nombre` pieces couvre, ancre sur `cube`.

    Les modeles sont carres -- 1, 2x2, 3x3 -- et CENTRES sur le cube vise
    quand leur cote est impair. Un modele qui partirait toujours du coin
    obligerait a viser a cote de ce qu'on veut couvrir.

    Ceux qui deborderaient de la grille sont simplement omis : viser le bord
    doit poser ce qui tient, et non tout refuser."""
    cote = int(round(nombre ** 0.5))
    depart = -((cote - 1) // 2)
    nx, ny, _nz = volume
    x, y, z = cube
    out = []
    for dx in range(cote):
        for dy in range(cote):
            cx, cy = x + depart + dx, y + depart + dy
            if 0 <= cx < nx and 0 <= cy < ny:
                out.append((cx, cy, z))
    return out


def cubes_utilisables(volume, etape, batis):
    """Les cubes ou l'on peut poser une piece a cette etape.

    DEUX REGLES, et la seconde est la raison d'etre des etapes :

    - on ne batit QUE dans les niveaux de l'etape en cours. Le reste du
      volume n'a pas a etre montre : il n'y a rien a y faire ;
    - un cube demande UN APPUI, c'est-a-dire une piece juste en dessous. On ne
      pose pas un mur en l'air. Le niveau du bas (z = 0) fait exception : son
      appui, c'est la terre.

    LE TOIT ECHAPPE A LA SECONDE. Un toit franchit l'espace entre ses murs --
    c'est meme sa fonction -- donc ses cubes n'ont pas a etre appuyes. A cette
    etape tout l'etage est ouvert, comme a la premiere."""
    nx, ny, _nz = volume
    out = []
    for z in niveaux_de(etape):
        for x in range(nx):
            for y in range(ny):
                if (x, y, z) in batis:
                    continue
                if etape == ETAPE_TOIT or z == 0 or (x, y, z - 1) in batis:
                    out.append((x, y, z))
    return out


def cubes_visibles(volume, etape, batis):
    """Les cubes a MONTRER.

    Deux familles, et rien d'autre :

    - CE QUI EST BATI, a l'etage en cours comme a ceux du dessous. Un etage
      finalise ne montre donc plus que ses pieces : ses cubes restes vides
      disparaissent, puisqu'on ne peut plus rien y mettre. Ce qui est bati
      plus bas n'est pas manipulable, mais le cacher priverait le joueur du
      seul repere qu'il ait -- sans ses murs, il poserait son toit dans le
      vide sans savoir ou tombent les pieces ;
    - CE QUI EST OUVERT a l'etage en cours.

    Rien de l'etage SUIVANT n'apparait : il n'existe pas encore."""
    if etape >= TERMINE:
        return sorted(batis)
    niveaux = niveaux_de(etape)
    hauts = max(niveaux) if niveaux else -1
    dessous = [c for c in batis if c[2] <= hauts]
    return sorted(set(cubes_utilisables(volume, etape, batis)) | set(dessous))


def boite_etage(volume, etape):
    """La boite de l'ETAGE en cours, dans toute son etendue.

    C'est le CONTOUR qu'on trace : il montre jusqu'ou va l'etage, y compris
    la ou aucun cube n'est encore ouvert. Sans lui, un etage a peine commence
    se reduirait a deux ou trois cubes flottants et le joueur ne saurait plus
    quelle surface il a le droit de couvrir.

    Sa hauteur est celle de l'etage : quatre fois plus haute pour un etage de
    murs que pour une dalle."""
    nx, ny, _nz = volume
    niveaux = niveaux_de(etape)
    if not niveaux:
        return boite_du_volume(volume)
    return ((0, 0, z_bas(min(niveaux))), (nx, ny, z_haut(max(niveaux))))


def boite_cadre(volume, etape, batis):
    """La boite a CADRER : l'etage en cours en entier, plus ce qui est bati.

    On cadre sur l'etage ENTIER et non sur les seuls cubes montres : sinon la
    vue sauterait et changerait d'echelle a chaque piece posee, puisque
    l'etendue de ce qui est montre grandit au fur et a mesure."""
    if etape >= TERMINE:
        return boite_des(sorted(batis), volume)
    bas, haut = boite_etage(volume, etape)
    xs = [bas[0], haut[0]]
    ys = [bas[1], haut[1]]
    zs = [bas[2], haut[2]]
    for c in batis:
        xs += [c[0], c[0] + 1]
        ys += [c[1], c[1] + 1]
        zs += [z_bas(c[2]), z_haut(c[2])]
    return ((min(xs), min(ys), min(zs)), (max(xs), max(ys), max(zs)))


def etape_complete(etape, batis):
    """L'etage en cours a-t-il de quoi passer au suivant ?

    Il suffit d'UNE piece. Exiger un etage plein interdirait une porte, une
    fenetre, un mur en L -- or c'est le joueur qui dessine sa maison. Mais
    zero piece est refuse : l'etage suivant n'aurait alors aucun appui, et le
    chantier serait bloque sans que rien ne le dise."""
    return any(etape_de(c[2]) == etape for c in batis)


def cubes_de_etape(etape, batis):
    """Les cubes batis qui appartiennent a cette etape."""
    return [c for c in batis if etape_de(c[2]) == etape]
