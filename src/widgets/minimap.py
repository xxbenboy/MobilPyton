"""
Mini-carte : une fenetre de 25 x 25 cases du monde (sans fin), le joueur
TOUJOURS AU MILIEU.

Le joueur ne se deplace pas sur la carte : c'est la carte qui glisse sous
lui. Un pas vers le nord fait disparaitre la rangee du bas et apparaitre une
nouvelle rangee en haut, calculee a la demande (voir world.Monde).

Chaque case est un petit rectangle colore selon le type de zone. La case du
joueur est marquee par un carre dore. On redessine seulement quand c'est utile
(arrivee sur l'ecran, deplacement, redimensionnement) : pas a chaque frame.

Une FLECHE ROUGE dans la case du joueur indique son ORIENTATION. Elle n'est
affichee que si le joueur peut se reperer :
- en mode debug (partie de test), toujours ;
- en jeu normal, seulement avec une BOUSSOLE (objet a crafter plus tard).

En mode debug, TOUTE la carte est visible : pas de brouillard sur les cases
encore inexplorees. C'est un affichage seulement -- les cases revelees de la
partie ne changent pas.
"""
import math

from kivy.app import App
from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle, Line, Triangle

from src import world, items
from src.game_state import CARDINALS


class MiniMap(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # LE REGARD (degres, 0 au nord, sens horaire), quand un ecran fait
        # tourner la vue derriere la carte : la fleche le suit en continu.
        # None : l'orientation du joueur, par quart de tour.
        self.regard = None
        self._case_joueur = None
        self.bind(pos=self.refresh, size=self.refresh)

    def set_regard(self, lacet):
        """La fleche suit ce regard ; seule elle est redessinee."""
        self.regard = None if lacet is None else float(lacet)
        self._dessine_fleche()

    def refresh(self, *_):
        self.canvas.clear()
        state = App.get_running_app().game_state
        if state is None or self.width <= 0 or self.height <= 0:
            return

        n_w, n_h = world.GRID_W, world.GRID_H
        rx0 = state.player_x - n_w // 2      # la colonne de gauche
        ry0 = state.player_y - n_h // 2      # la rangee du haut (le nord)
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
            # (toutes, en mode debug).
            for j in range(n_h):
                ry = ry0 + j
                draw_y = oy + (n_h - 1 - j) * cell
                row = state.grid[ry]
                for i in range(n_w):
                    rx = rx0 + i
                    key = f"{rx},{ry}"
                    if state.debug or key in state.revealed:
                        Color(*world.zone_color(row[rx]))
                        Rectangle(pos=(ox + i * cell, draw_y),
                                  size=(cell - 1, cell - 1))

            # Marqueur du joueur (carre dore), TOUJOURS au milieu.
            mx = ox + (n_w // 2) * cell
            my = oy + (n_h - 1 - n_h // 2) * cell
            Color(1.0, 0.85, 0.25, 1)
            Rectangle(pos=(mx, my), size=(cell - 1, cell - 1))
            Color(0, 0, 0, 0.9)
            Line(rectangle=(mx, my, cell - 1, cell - 1), width=1.2)

        # Orientation du joueur (flechee rouge), si on peut se reperer.
        self._case_joueur = (mx, my, cell)
        self._dessine_fleche()

    def _dessine_fleche(self):
        self.canvas.after.clear()
        state = App.get_running_app().game_state
        if state is None or self._case_joueur is None:
            return
        if not (state.debug or state.has_item(items.COMPASS_ITEM)):
            return
        mx, my, cell = self._case_joueur
        with self.canvas.after:
            if self.regard is None:
                self._facing_arrow(mx, my, cell, state.facing)
            else:
                a = math.radians(self.regard)
                self._facing_arrow(mx, my, cell, None,
                                   (math.sin(a), math.cos(a)))

    def _facing_arrow(self, mx, my, cell, facing, vers=None):
        """Fleche ROUGE centree dans la case du joueur, pointant vers la
        direction regardee (`vers` : le vecteur a l'ecran, sinon celui de
        `facing`)."""
        # CARDINALS est en coordonnees GRILLE (y croissant vers le sud) ; sur
        # la mini-carte, l'ecran a son y croissant vers le HAUT (le nord). On
        # inverse donc dy pour obtenir la direction a l'ecran.
        if vers is None:
            dx, dy = CARDINALS[facing % len(CARDINALS)]
            ux, uy = dx, -dy
        else:
            ux, uy = vers
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
