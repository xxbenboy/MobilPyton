"""
Mini-carte : affiche toute la carte 25x25 et la position du joueur.

Chaque case est un petit rectangle colore selon le type de zone. La case du
joueur est marquee par un carre dore. On redessine seulement quand c'est utile
(arrivee sur l'ecran, deplacement, redimensionnement) : pas a chaque frame.
"""
from kivy.app import App
from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle, Line

from src import world


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
            for ry in range(n_h):
                draw_y = oy + (n_h - 1 - ry) * cell
                row = state.grid[ry]
                for rx in range(n_w):
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
