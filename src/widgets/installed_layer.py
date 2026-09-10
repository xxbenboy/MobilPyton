"""Le lien entre la GRILLE 5x5 et l'ecran, dans les deux sens.

En vue 1re personne, `grid_to_screen` projette une case vers l'ecran (voir
plus bas). Dans la grille de POSE, vue de dessus, c'est l'inverse qu'il faut :
sous quel point de la grille le doigt se trouve-t-il, et ou faut-il ancrer un
objet pour que son emprise tombe la ? C'est `anchor_at`.

Les deux sont de la geometrie pure, sans Kivy : elles se verifient donc au
calcul, sans avoir a construire un ecran.

--- Projection en vue 1re personne ---

Chaque case du monde est decoupee en une grille 5x5 (voir PlaceScreen) :
gx dans 0..4 (colonne gauche->droite), gy dans 0..4 (ligne proche->loin).
Le joueur regarde toujours vers gy croissant, en position (gx=2, gy=0).

Projection perspective simple (pas de vraie 3D) : plus la ligne est loin,
plus l'objet est petit et proche de la ligne d'horizon.

Le DESSIN des objets installes appartient a ZoneScenery : ils doivent etre
tries par profondeur avec le reste du decor (un feu de camp pose au fond
passe derriere un buisson du premier plan), ce qu'une couche posee par-dessus
la scene ne permettait pas.
"""


def grid_to_screen(gx, gy):
    """Projette une position grille (gx, gy) en (fx, fy, size_frac).

    fx, fy : fraction de la surface du widget (0..1).
    size_frac : diametre du cercle en fraction de la largeur du widget.
    """
    depth = gy / 4.0                     # 0 (proche) -> 1 (lointain)
    lx = gx - 2                          # -2 (gauche) .. +2 (droite)
    # Y ecran : du bas de la scene (0.05) jusqu'a la ligne d'horizon (~0.47).
    fy = 0.05 + 0.42 * depth
    # Compression laterale : loin, tout se rapproche du centre.
    horiz = 0.42 * (1 - 0.78 * depth)
    fx = 0.5 + (lx / 2.0) * horiz
    # Taille du cercle : shrink net avec la profondeur.
    size = 0.18 * (1 - 0.72 * depth)
    return fx, fy, size


def anchor_at(x, y, ox, oy, cs, fw, fh):
    """Ou ancrer un objet de fw x fh cases pour qu'il tombe sous (x, y) ?

    (ox, oy) est le coin bas-gauche de la grille a l'ecran, `cs` le cote d'une
    case. Rend None si (x, y) est hors de la grille.

    L'EMPRISE EST CENTREE SUR LE DOIGT : c'est ce qu'on attend en posant une
    piece sur un plateau -- on vise le milieu de ce qu'on tient, pas son coin.
    Pour une emprise paire (2x2), le milieu tombe entre deux cases ; l'arrondi
    tranche, et le bloc bascule d'un cran quand le doigt franchit une ligne.

    AU BORD, LE BLOC SE CALE au lieu de deborder : viser le coin de la grille
    doit donner l'emplacement du coin, pas rien du tout."""
    if not (ox <= x < ox + 5 * cs and oy <= y < oy + 5 * cs):
        return None
    # Position CONTINUE du doigt en cases (0.0 = centre de la case 0).
    cgx = (x - ox) / cs - 0.5
    cgy = (y - oy) / cs - 0.5
    gx = int(round(cgx - (fw - 1) / 2.0))
    gy = int(round(cgy - (fh - 1) / 2.0))
    return max(0, min(5 - fw, gx)), max(0, min(5 - fh, gy))
