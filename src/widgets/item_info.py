"""
FICHE D'UN OBJET : la fenetre qui s'ouvre quand on tape sur un objet.

Elle se pose PAR-DESSUS l'ecran courant et avale tous les touchers : le menu
qu'elle recouvre ne reagit plus tant qu'elle est ouverte. On la ferme par le
petit "x" en haut a droite, ou en tapant a cote.

Le contenu vient de items.describe() : une phrase, puis des faits calcules a
partir des tables du jeu (recette, zones, solidite...). Rien n'est ecrit en
dur ici, donc la fiche suit les regles reelles.
"""
from kivy.uix.behaviors import ButtonBehavior
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.scrollview import ScrollView
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle, RoundedRectangle, Line
from kivy.metrics import dp

from src import items
from src.widgets.item_icon import ItemIcon
from src.widgets.responsive import dh

_GOLD = (0.96, 0.82, 0.45, 1)
_TEXT = (0.92, 0.92, 0.95, 1)
_DIM = (0.72, 0.74, 0.80, 1)


class _CloseButton(Button):
    """Petit "x" dessine au canvas.

    Dessine plutot qu'ecrit : la croix s'affiche donc quelle que soit la
    police, et reste nette a toutes les tailles."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.background_normal = ""
        self.background_down = ""
        self.background_color = (0, 0, 0, 0)
        self.text = ""
        with self.canvas.after:
            self._fill = Color(0.30, 0.10, 0.10, 0.55)
            self._disc = RoundedRectangle(radius=[dp(6)])
            self._line = Color(1, 0.80, 0.80, 0.95)
            self._a = Line(width=1.6)
            self._b = Line(width=1.6)
        self.bind(pos=self._sync, size=self._sync, state=self._sync)
        self._sync()

    def _sync(self, *_):
        side = min(self.width, self.height)
        x = self.center_x - side / 2
        y = self.center_y - side / 2
        self._disc.pos = (x, y)
        self._disc.size = (side, side)
        m = side * 0.30
        self._a.points = [x + m, y + m, x + side - m, y + side - m]
        self._b.points = [x + m, y + side - m, x + side - m, y + m]
        down = self.state == "down"
        self._fill.rgba = ((0.55, 0.18, 0.18, 0.80) if down
                           else (0.30, 0.10, 0.10, 0.55))


def _fit(label, max_font):
    """Reduit la police pour que le texte tienne dans une boite FIXE."""
    def _update(*_):
        if label.width <= 1 or label.height <= 1:
            return
        label.text_size = (label.width, None)
        label.font_size = max_font
        label.texture_update()
        if label.texture_size[1] > label.height:
            label.font_size = max(9, max_font * label.height
                                  / label.texture_size[1])
        label.text_size = (label.width, label.height)
    label.bind(size=_update, text=_update)
    _update()
    return label


def _wrapped(text, color, font_px):
    """Ligne de texte qui se replie et prend la HAUTEUR qu'il lui faut.

    La police reste la meme pour tous les faits : c'est la boite qui grandit,
    pas le texte qui retrecit. Une longue enumeration s'etale donc sur
    plusieurs lignes et la liste defile, au lieu de devenir minuscule."""
    label = Label(text=text, color=color, halign="left", valign="top",
                  size_hint_y=None, font_size=font_px)

    def _update(*_):
        if label.width <= 1:
            return
        label.text_size = (label.width, None)
        label.texture_update()
        label.height = label.texture_size[1]
    # On n'ecoute QUE la largeur : ecouter la hauteur bouclerait, puisque
    # c'est elle qu'on modifie.
    label.bind(width=_update, text=_update)
    _update()
    return label


class ItemInfoPanel(FloatLayout):
    """Fiche d'un objet, posee par-dessus l'ecran."""

    def __init__(self, name, **kwargs):
        kwargs.setdefault("size_hint", (1, 1))
        kwargs.setdefault("pos_hint", {"x": 0, "y": 0})
        super().__init__(**kwargs)
        self.item = name

        # Voile sombre sur tout l'ecran : la fiche detache l'oeil du menu.
        with self.canvas.before:
            Color(0, 0, 0, 0.55)
            veil = Rectangle()
        self.bind(pos=lambda w, *_: setattr(veil, "pos", w.pos),
                  size=lambda w, *_: setattr(veil, "size", w.size))

        panel = BoxLayout(orientation="vertical", padding=dp(12),
                          spacing=dp(8), size_hint=(0.52, 0.80),
                          pos_hint={"center_x": 0.5, "center_y": 0.5})
        with panel.canvas.before:
            Color(0.06, 0.08, 0.11, 0.97)
            bg = RoundedRectangle(radius=[dp(14)])
            Color(*_GOLD[:3], 0.45)
            edge = Line(width=1.4)

        def _sync(*_):
            bg.pos = panel.pos
            bg.size = panel.size
            edge.rounded_rectangle = (panel.x, panel.y, panel.width,
                                      panel.height, dp(14))
        panel.bind(pos=_sync, size=_sync)
        _sync()

        # ---- En-tete : le nom, et le "x" tout a droite ----
        head = BoxLayout(orientation="horizontal", spacing=dp(6),
                         size_hint_y=0.14)
        title = Label(text=items.display_name(name), bold=True, color=_GOLD,
                      halign="left", valign="middle")
        _fit(title, dh(56))
        head.add_widget(title)
        close = _CloseButton(size_hint_x=None)
        head.bind(height=lambda _w, h: setattr(close, "width", h))
        close.bind(on_release=lambda *_: self.close())
        head.add_widget(close)
        panel.add_widget(head)

        note, facts = items.describe(name)

        # ---- Corps : l'image a gauche, le texte a droite ----
        body = BoxLayout(orientation="horizontal", spacing=dp(10),
                         size_hint_y=0.86)
        picture = BoxLayout(size_hint_x=0.36)
        picture.add_widget(ItemIcon(name, show_name=False))
        body.add_widget(picture)

        scroll = ScrollView(size_hint_x=0.64)
        text = BoxLayout(orientation="vertical", spacing=dp(6),
                         size_hint_y=None)
        text.bind(minimum_height=text.setter("height"))
        if note:
            text.add_widget(_wrapped(note, _DIM, dh(40)))
            text.add_widget(_rule())
        for fact in facts:
            text.add_widget(_wrapped(f"-  {fact}", _TEXT, dh(38)))
        scroll.add_widget(text)
        body.add_widget(scroll)
        panel.add_widget(body)

        self.add_widget(panel)
        self._panel = panel

    # ------------------------------------------------------------------ #
    def close(self):
        if self.parent is not None:
            self.parent.remove_widget(self)

    def on_touch_down(self, touch):
        """Avale TOUT : le menu recouvert ne doit pas reagir a travers.

        Taper a cote de la fiche la ferme, comme le "x"."""
        super().on_touch_down(touch)
        if not self._panel.collide_point(*touch.pos):
            self.close()
        return True

    def on_touch_move(self, touch):
        super().on_touch_move(touch)
        return True

    def on_touch_up(self, touch):
        super().on_touch_up(touch)
        return True


def _rule():
    """Filet de separation sous la phrase d'introduction."""
    w = Widget(size_hint_y=None, height=dh(14))
    with w.canvas:
        Color(1, 1, 1, 0.14)
        line = Line(width=1.0)

    def _sync(*_):
        line.points = [w.x, w.center_y, w.right, w.center_y]
    w.bind(pos=_sync, size=_sync)
    return w


def show_item_info(root, name):
    """Ouvre la fiche de l'objet par-dessus `root`. Renvoie la fiche."""
    panel = ItemInfoPanel(name)
    root.add_widget(panel)
    return panel


class TappableIcon(ButtonBehavior, BoxLayout):
    """Image d'un objet sur laquelle on peut TAPER pour ouvrir sa fiche.

    On herite de ButtonBehavior plutot que de guetter les touchers a la
    main : c'est lui qui sait deja distinguer un tap d'un defilement quand
    l'image se trouve dans une liste qui glisse."""

    def __init__(self, name, on_tap, count=1, show_name=True, **kwargs):
        super().__init__(**kwargs)
        self.item = name
        self.add_widget(ItemIcon(name, count=count, show_name=show_name))
        self.bind(on_release=lambda *_: on_tap(name))
