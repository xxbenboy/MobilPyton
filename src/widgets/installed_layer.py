"""Couche des objets INSTALLES (feu de camp, etc.) en vue 1re personne.

Chaque objet a une position sur une grille 5x5 par case (voir PlaceScreen) :
gx dans 0..4 (colonne gauche->droite), gy dans 0..4 (ligne proche->loin).
Le joueur regarde toujours vers gy croissant, en position (gx=2, gy=0).

Projection perspective simple (pas de vraie 3D) : plus la ligne est loin,
plus l'objet est petit et proche de la ligne d'horizon.
"""
import math

from kivy.uix.widget import Widget
from kivy.graphics import Color, Ellipse


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


class InstalledLayer(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._objects = []               # [(nom, gx, gy), ...]
        self.bind(pos=self._redraw, size=self._redraw)

    def set_objects(self, objects):
        lst = [tuple(o) for o in objects]
        if lst == self._objects:
            return
        self._objects = lst
        self._redraw()

    def _redraw(self, *_):
        self.canvas.clear()
        if self.width <= 0 or self.height <= 0:
            return
        # Trie par gy DECROISSANT : les objets LOINTAINS d'abord, puis les
        # proches par-dessus (pour un ordre de couverture correct).
        for obj in sorted(self._objects, key=lambda o: -o[2]):
            name = obj[0]
            gx, gy = int(obj[1]), int(obj[2])
            if name == "Feu_de_camp":
                self._draw_stone_circle(gx, gy)

    def _draw_stone_circle(self, gx, gy):
        fx, fy, size = grid_to_screen(gx, gy)
        cx = self.x + fx * self.width
        cy = self.y + fy * self.height
        # Diametre X (largeur au sol) : proportionnel a l'ecran.
        w = size * self.width
        # Aplati verticalement pour effet vue en angle (~ 55 % de la largeur).
        h = w * 0.55
        with self.canvas:
            # Fond fonce (cendres du foyer).
            Color(0.10, 0.08, 0.06, 0.85)
            Ellipse(pos=(cx - w / 2, cy - h / 2), size=(w, h))
            # Anneau de 10 pierres alternees brun/gris.
            n = 10
            r = min(w, h) * 0.15
            for i in range(n):
                a = 2 * math.pi * i / n
                sx = cx + (w / 2 - r) * math.cos(a)
                sy = cy + (h / 2 - r) * math.sin(a)
                if i % 2 == 0:
                    Color(0.52, 0.42, 0.34, 1)
                else:
                    Color(0.66, 0.58, 0.50, 1)
                Ellipse(pos=(sx - r, sy - r), size=(r * 2, r * 2))
