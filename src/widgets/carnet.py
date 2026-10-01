"""
LE CARNET DE SAVOIRS : les crafts appris, dessines comme dans un carnet.

Chaque savoir prend un quart de la double page : l'objet fabrique et son nom
a gauche, et a droite le CROQUIS de son assemblage -- les objets places
comme le joueur les a places la premiere fois, chacun avec sa grille de
3 x 3 tracee au charbon (voir GameState.dispositions).

Quatre savoirs par double page ; des galets tournent les pages, un autre
referme le carnet. Tant qu'il est ouvert, il prend tous les touchers.
"""
from kivy.graphics import Color, Line, Rectangle
from kivy.uix.label import Label
from kivy.uix.widget import Widget

from src import items
from src.widgets.bois import BoutonGalet
from src.widgets.sol_de_craft import dessine_objet, texture_craft

# La double page, en part de la largeur de l'ecran (proportions de
# page.png), sans depasser cette part de la hauteur.
PART_LARGEUR = 0.80
PART_HAUTEUR = 0.88
RAPPORT_PAGE = 1280.0 / 800.0
PAR_PAGE = 4
# L'encre : un brun tres sombre, et le charbon des croquis.
ENCRE = (0.24, 0.16, 0.09, 1)
CHARBON = (0.12, 0.11, 0.10, 0.65)
FOND = (0.0, 0.0, 0.0, 0.55)
CASES = 3


class Carnet(Widget):
    """Le carnet ouvert. `fermer()` est appele quand on le referme."""

    def __init__(self, fermer=None, **kwargs):
        super().__init__(**kwargs)
        self.fermer = fermer
        self.entrees = []
        self.page = 0
        self._fermer = BoutonGalet(text="Fermer")
        self._fermer.bind(on_release=lambda *_: self._ferme())
        self._avant = BoutonGalet(text="<")
        self._avant.bind(on_release=lambda *_: self.tourne(-1))
        self._apres = BoutonGalet(text=">")
        self._apres.bind(on_release=lambda *_: self.tourne(1))
        self._labels = []
        self.bind(pos=self._redessine, size=self._redessine)

    # -- contenu ---------------------------------------------------------- #
    def montre(self, entrees):
        """[(objet, disposition)] : les savoirs, dans l'ordre."""
        self.entrees = list(entrees)
        self.page = 0
        self._redessine()

    def pages(self):
        return max(1, (len(self.entrees) + PAR_PAGE - 1) // PAR_PAGE)

    def tourne(self, sens):
        p = max(0, min(self.pages() - 1, self.page + sens))
        if p != self.page:
            self.page = p
            self._redessine()

    def _ferme(self):
        if self.fermer is not None:
            self.fermer()

    # -- geometrie -------------------------------------------------------- #
    def rect_page(self):
        w = PART_LARGEUR * self.width
        h = w / RAPPORT_PAGE
        if h > PART_HAUTEUR * self.height:
            h = PART_HAUTEUR * self.height
            w = h * RAPPORT_PAGE
        return (self.x + (self.width - w) / 2.0,
                self.y + (self.height - h) / 2.0, w, h)

    def cases_savoirs(self):
        """Les quatre emplacements de la double page : (x, y, l, h)."""
        x, y, w, h = self.rect_page()
        mx, haut, bas = w * 0.06, h * 0.16, h * 0.16
        demi = w / 2.0
        lh = (h - haut - bas) / 2.0
        out = []
        for cote in (0, 1):
            for rang in (0, 1):
                out.append((x + cote * demi + mx,
                            y + bas + (1 - rang) * lh,
                            demi - 2 * mx, lh))
        return out

    # -- dessin ----------------------------------------------------------- #
    def _texte(self, texte, x, y, l, h, taille, gras=False):
        lbl = Label(text=texte, color=ENCRE, bold=gras, font_size=taille,
                    halign="center", valign="middle")
        lbl.size = (l, h)
        lbl.pos = (x, y)
        lbl.text_size = (l, h)
        self.add_widget(lbl)
        self._labels.append(lbl)

    def _redessine(self, *_):
        self.canvas.clear()
        for w in self._labels + [self._fermer, self._avant, self._apres]:
            if w.parent is self:
                self.remove_widget(w)
        self._labels = []
        if self.width <= 0 or self.height <= 0:
            return
        x, y, w, h = self.rect_page()
        with self.canvas:
            Color(*FOND)
            Rectangle(pos=self.pos, size=self.size)
            page = texture_craft("page")
            if page is not None:
                Color(1, 1, 1, 1)
                Rectangle(texture=page, pos=(x, y), size=(w, h))
            else:
                Color(0.84, 0.77, 0.63, 1)
                Rectangle(pos=(x, y), size=(w, h))
        self._texte("Carnet de savoirs", x, y + h * 0.86, w / 2.0, h * 0.10,
                    h * 0.055, gras=True)
        debut = self.page * PAR_PAGE
        visibles = self.entrees[debut:debut + PAR_PAGE]
        if not visibles:
            self._texte("Aucun savoir pour l'instant.\n"
                        "Reussis un assemblage pour l'y inscrire.",
                        x, y + h * 0.35, w / 2.0, h * 0.3, h * 0.04)
        for (objet, disposition), case in zip(visibles,
                                              self.cases_savoirs()):
            self._dessine_savoir(objet, disposition, case)
        # Les galets : fermer au milieu, tourner les pages aux coins.
        gh = h * 0.10
        self._fermer.size = (gh * 2.7, gh)
        self._fermer.pos = (x + w / 2.0 - gh * 1.35, y + h * 0.03)
        self.add_widget(self._fermer)
        if self.page > 0:
            self._avant.size = (gh * 1.3, gh)
            self._avant.pos = (x + w * 0.05, y + h * 0.03)
            self.add_widget(self._avant)
        if self.page < self.pages() - 1:
            self._apres.size = (gh * 1.3, gh)
            self._apres.pos = (x + w * 0.95 - gh * 1.3, y + h * 0.03)
            self.add_widget(self._apres)

    def _dessine_savoir(self, objet, disposition, case):
        cx, cy, cl, ch = case
        # L'objet et son nom, a gauche.
        cote = min(cl * 0.34, ch * 0.62)
        with self.canvas:
            dessine_objet(objet, cx + cl * 0.18, cy + ch * 0.58, cote,
                          ombre=False)
        nom = items.display_name(objet)
        taille = min(ch * 0.12, cl * 0.40 / max(1, len(nom)) / 0.58)
        self._texte(nom, cx - cl * 0.02, cy + ch * 0.04, cl * 0.42,
                    ch * 0.24, taille, gras=True)
        if not disposition:
            return
        # Le croquis de l'assemblage, a droite.
        zx, zy, zl, zh = cx + cl * 0.42, cy + ch * 0.08, cl * 0.56, ch * 0.84
        cols = [c for _n, c, _r in disposition]
        rangs = [r for _n, _c, r in disposition]
        # Chaque objet couvre 3 x 3 cases autour de sa position.
        x0, x1 = min(cols) - 1.5, max(cols) + 1.5
        y0, y1 = min(rangs) - 1.5, max(rangs) + 1.5
        c = min(zl / (x1 - x0), zh / (y1 - y0))
        ox = zx + (zl - (x1 - x0) * c) / 2.0 - x0 * c
        oy = zy + (zh - (y1 - y0) * c) / 2.0 - y0 * c
        largeur = max(1.0, c * 0.06)
        with self.canvas:
            for nom, col, rang in disposition:
                px, py = ox + col * c, oy + rang * c
                dessine_objet(nom, px, py, c * CASES * 0.92, ombre=False,
                              alpha=0.85)
                Color(*CHARBON)
                g, b = px - 1.5 * c, py - 1.5 * c
                for k in range(CASES + 1):
                    Line(points=[g + k * c, b, g + k * c, b + CASES * c],
                         width=largeur)
                    Line(points=[g, b + k * c, g + CASES * c, b + k * c],
                         width=largeur)

    # -- les touchers : tous pour le carnet -------------------------------- #
    def on_touch_down(self, touch):
        parent = getattr(super(), "on_touch_down", None)
        if parent is not None:
            parent(touch)
        return True

    def on_touch_move(self, touch):
        parent = getattr(super(), "on_touch_move", None)
        if parent is not None:
            parent(touch)
        return True

    def on_touch_up(self, touch):
        parent = getattr(super(), "on_touch_up", None)
        if parent is not None:
            parent(touch)
        return True


__all__ = ["Carnet", "PAR_PAGE"]
