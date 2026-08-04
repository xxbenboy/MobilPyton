"""Projection des positions de la GRILLE 5x5 vers l'ecran, en vue 1re personne.

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
