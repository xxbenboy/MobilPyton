"""
Mini-carte : affiche toute la carte 25x25 et la position du joueur.

Chaque case est un petit rectangle colore selon le type de zone. La case du
joueur est marquee par un carre dore. On redessine seulement quand c'est utile
(arrivee sur l'ecran, deplacement, redimensionnement) : pas a chaque frame.

Une FLECHE ROUGE dans la case du joueur indique son ORIENTATION. Elle n'est
affichee que si le joueur peut se reperer :
- en mode debug (partie de test), toujours ;
- en jeu normal, seulement avec une BOUSSOLE (objet a crafter plus tard).
"""
from kivy.app import App
from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle, Line, Triangle

from src import world, items
from src.game_state import CARDINALS


class MiniMap(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.bind(pos=self.refresh, size=self.refresh)

    def refresh(self, *_):
        self.canvas.clear()
        state = App.get_running_app().game_state
        if state is None or self.width <= 0 or self.height <= 0:
            return

        n_w, n_h = world.GRID_W, world.GRID_H
        cell = min(self.width / n_w, self.height / n_h)
        # On centre la grille dans le widget.
        ox = self.x + (self.width - cell * n_w) / 2
        oy = self.y + (self.height - cell * n_h) / 2

        with self.canvas:
            # Cadre de fond.
            Color(0, 0, 0, 0.35)
            Rectangle(pos=(ox, oy), size=(cell * n_w, cell * n_h))

            # Les zones. Ligne 0 = Nord => dessinee en HAUT.
            # D'abord, fond gris pour toutes les zones (brouillard)
            Color(0.2, 0.2, 0.2, 1)  # Gris fonce = brouillard
            Rectangle(pos=(ox, oy), size=(cell * n_w, cell * n_h))
            
            # Ensuite, dessiner les zones revelees avec leur vraie couleur
            for ry in range(n_h):
                draw_y = oy + (n_h - 1 - ry) * cell
                row = state.grid[ry]
                for rx in range(n_w):
                    key = f"{rx},{ry}"
                    if key in state.revealed:
                        Color(*world.zone_color(row[rx]))
                        Rectangle(pos=(ox + rx * cell, draw_y),
                                  size=(cell - 1, cell - 1))

            # Marqueur du joueur (carre dore).
            px, py = state.player_x, state.player_y
            mx = ox + px * cell
            my = oy + (n_h - 1 - py) * cell
            Color(1.0, 0.85, 0.25, 1)
            Rectangle(pos=(mx, my), size=(cell - 1, cell - 1))
            Color(0, 0, 0, 0.9)
            Line(rectangle=(mx, my, cell - 1, cell - 1), width=1.2)

            # Orientation du joueur (flechee rouge), si on peut se reperer.
            if state.debug or state.has_item(items.COMPASS_ITEM):
                self._facing_arrow(mx, my, cell, state.facing)

    def _facing_arrow(self, mx, my, cell, facing):
        """Fleche ROUGE centree dans la case du joueur, pointant vers la
        direction regardee."""
        # CARDINALS est en coordonnees GRILLE (y croissant vers le sud) ; sur
        # la mini-carte, l'ecran a son y croissant vers le HAUT (le nord). On
        # inverse donc dy pour obtenir la direction a l'ecran.
        dx, dy = CARDINALS[facing % len(CARDINALS)]
        ux, uy = dx, -dy
        px, py = -uy, ux                      # perpendiculaire (base du triangle)

        cx = mx + (cell - 1) / 2.0
        cy = my + (cell - 1) / 2.0
        # Dimensions choisies pour que meme le liisere (x1.18) reste DANS la
        # case du joueur (demi-case = 0.5 * cell).
        length = cell * 0.40                  # du centre jusqu'a la pointe
        half = cell * 0.26                    # demi-largeur de la base

        def tri(scale):
            tipx, tipy = cx + ux * length * scale, cy + uy * length * scale
            bx, by = cx - ux * length * 0.55 * scale, cy - uy * length * 0.55 * scale
            return [tipx, tipy,
                    bx + px * half * scale, by + py * half * scale,
                    bx - px * half * scale, by - py * half * scale]

        # Liisere sombre (lisibilite sur le carre dore), puis la fleche rouge.
        Color(0.15, 0.05, 0.05, 0.85)
        Triangle(points=tri(1.18))
        Color(0.92, 0.13, 0.13, 1)
        Triangle(points=tri(1.0))
