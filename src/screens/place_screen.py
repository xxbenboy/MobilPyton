"""Ecran PLACEMENT : vue de dessus + grille 5x5 pour choisir ou installer
un objet (feu de camp, ...) sur la case courante.

Le joueur est fixe au centre-bas de la grille (gx=2, gy=0), regardant vers le
haut (gy croissant). Un tap sur une case libre confirme la position ; l'objet
tenu dans la main _slot (definie par GameScreen avant la navigation) passe
dans state.installed et la vue revient au jeu.

Le placement est IRREVERSIBLE : un objet installe ne peut plus etre
ramasse ni deplace.
"""
from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.widget import Widget
from kivy.graphics import (Color, Rectangle, RoundedRectangle, Line, Ellipse,
                           Triangle)
from kivy.metrics import dp
import math

from src import items
from src.widgets.animated_background import AnimatedBackground, night_darkness
from src.widgets.zone_scenery import ZoneScenery
from src.widgets.styled_button import StyledButton
from src.widgets.responsive import scale_font, dh

# Couleurs de la grille. Definies ICI une seule fois : la grille ET la legende
# les utilisent, elles ne peuvent donc jamais se contredire.
CELL_BG = (0, 0, 0, 0.20)             # fond commun a toutes les cases
CELL_LINE = (1, 1, 1, 0.60)           # trait de separation
CELL_TAKEN = (0.90, 0.35, 0.30, 0.35)     # rouge  : deja utilise
CELL_NATURE = (0.25, 0.55, 0.30, 0.45)    # vert   : occupe par la nature
CELL_PLAYER = (0.30, 0.70, 1.00, 0.35)    # bleu   : le joueur
CELL_FREE = (0, 0, 0, 0)                  # aucune : libre

# Nom lisible de chaque obstacle naturel (cf. world.NATURE_BIG).
NATURE_LABEL = {"tree": "Arbre", "bush": "Buisson", "rock": "Rocher"}
NATURE_ORDER = ("tree", "bush", "rock")


def draw_nature_glyph(kind, cx, cy, size):
    """Dessine l'obstacle VU DE DESSUS, centre sur (cx, cy).

    A appeler dans un contexte `with canvas:`. La vue de placement regarde le
    sol d'en haut : un arbre est donc un houppier rond avec son tronc au
    centre, un buisson une touffe de lobes, un rocher une masse grise."""
    r = size * 0.5
    if kind == "tree":
        Color(0, 0, 0, 0.28)                                  # ombre portee
        Ellipse(pos=(cx - r, cy - r * 1.12), size=(r * 2, r * 2))
        Color(0.13, 0.38, 0.18, 1)                            # houppier
        Ellipse(pos=(cx - r, cy - r), size=(r * 2, r * 2))
        Color(0.20, 0.52, 0.25, 1)                            # feuillage clair
        Ellipse(pos=(cx - r * 0.66, cy - r * 0.66),
                size=(r * 1.32, r * 1.32))
        Color(0.34, 0.23, 0.13, 1)                            # tronc
        Ellipse(pos=(cx - r * 0.17, cy - r * 0.17),
                size=(r * 0.34, r * 0.34))
    elif kind == "bush":
        Color(0, 0, 0, 0.24)
        Ellipse(pos=(cx - r * 0.92, cy - r * 1.02),
                size=(r * 1.84, r * 1.84))
        Color(0.17, 0.44, 0.21, 1)                            # lobes
        for dx, dy, k in ((-0.44, 0.08, 0.60), (0.44, 0.08, 0.60),
                          (0.0, -0.36, 0.60), (0.0, 0.32, 0.66)):
            rr = r * k
            Ellipse(pos=(cx + dx * r - rr, cy + dy * r - rr),
                    size=(rr * 2, rr * 2))
        Color(0.26, 0.56, 0.28, 1)                            # coeur eclaire
        rr = r * 0.44
        Ellipse(pos=(cx - rr, cy - rr), size=(rr * 2, rr * 2))
    elif kind == "rock":
        Color(0, 0, 0, 0.28)
        Ellipse(pos=(cx - r, cy - r * 1.02), size=(r * 2, r * 1.7))
        Color(0.45, 0.45, 0.49, 1)                            # masse
        Ellipse(pos=(cx - r, cy - r * 0.85), size=(r * 2, r * 1.7))
        Color(0.62, 0.62, 0.66, 1)                            # facette eclairee
        Ellipse(pos=(cx - r * 0.55, cy - r * 0.28),
                size=(r * 1.0, r * 0.82))


def draw_object_glyph(name, cx, cy, size, lit=False):
    """Dessine un objet INSTALLE vu de dessus, centre sur (cx, cy).

    A appeler dans un contexte `with canvas:`. Un foyer eteint montre son
    cercle de pierres et son bois ; allume, il montre ses flammes."""
    r = size * 0.5
    if name != "Feu_de_camp":
        return
    Color(0.10, 0.08, 0.06, 0.90)                         # cendres
    Ellipse(pos=(cx - r * 0.78, cy - r * 0.78), size=(r * 1.56, r * 1.56))
    if lit:                                               # braises
        Color(0.75, 0.25, 0.08, 1)
        Ellipse(pos=(cx - r * 0.62, cy - r * 0.62), size=(r * 1.24, r * 1.24))
    else:                                                 # buches croisees
        Color(0.36, 0.24, 0.14, 1)
        for a in (0.6, -0.6):
            dx, dy = math.cos(a) * r * 0.62, math.sin(a) * r * 0.62
            Line(points=[cx - dx, cy - dy, cx + dx, cy + dy],
                 width=max(1.2, r * 0.13))
    n = 8                                                 # anneau de pierres
    sr = r * 0.20
    for i in range(n):
        a = 2 * math.pi * i / n
        sx = cx + (r - sr) * math.cos(a)
        sy = cy + (r - sr) * math.sin(a)
        if i % 2:
            Color(0.52, 0.42, 0.34, 1)
        else:
            Color(0.66, 0.58, 0.50, 1)
        Ellipse(pos=(sx - sr, sy - sr), size=(sr * 2, sr * 2))
    if lit:                                               # flammes
        Color(0.98, 0.62, 0.12, 1)
        Triangle(points=[cx - r * 0.42, cy - r * 0.10, cx + r * 0.42,
                         cy - r * 0.10, cx, cy + r * 0.78])
        Color(1.0, 0.88, 0.35, 1)
        Triangle(points=[cx - r * 0.22, cy - r * 0.05, cx + r * 0.22,
                         cy - r * 0.05, cx, cy + r * 0.44])


class _Swatch(Widget):
    """Petit carre de couleur, dessine EXACTEMENT comme une case de la grille.

    Meme fond sombre, meme contour et, le cas echeant, le meme pictogramme :
    une case "vacante" (sans couleur) est donc reconnaissable telle quelle."""

    def __init__(self, rgba, kind=None, **kwargs):
        super().__init__(**kwargs)
        self._rgba = rgba
        self._kind = kind
        self.bind(pos=self._redraw, size=self._redraw)
        self._redraw()

    def _redraw(self, *_):
        self.canvas.clear()
        s = min(self.width, self.height)
        if s <= 0:
            return
        x = self.x + (self.width - s) / 2.0
        y = self.y + (self.height - s) / 2.0
        with self.canvas:
            Color(*CELL_BG)
            Rectangle(pos=(x, y), size=(s, s))
            Color(*self._rgba)
            Rectangle(pos=(x, y), size=(s, s))
            if self._kind:
                draw_nature_glyph(self._kind, x + s / 2, y + s / 2, s * 0.66)
            Color(*CELL_LINE)
            Line(rectangle=(x, y, s, s), width=1.2)


class _Legend(BoxLayout):
    """Panneau explicatif : a quoi correspond la couleur de chaque case."""

    def __init__(self, **kwargs):
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("padding", dp(8))
        kwargs.setdefault("spacing", dp(4))
        super().__init__(**kwargs)
        with self.canvas.before:
            Color(0.05, 0.07, 0.10, 0.55)
            self._bg = RoundedRectangle(radius=[dp(10)])
        self.bind(pos=self._sync, size=self._sync)
        self._kinds = None
        self.rebuild(())

    def rebuild(self, kinds):
        """(Re)construit la legende pour les obstacles PRESENTS sur la case.

        Inutile d'annoncer "Rocher" dans une foret : on ne liste que ce que le
        joueur a reellement sous les yeux."""
        kinds = tuple(k for k in NATURE_ORDER if k in set(kinds))
        if kinds == self._kinds:
            return
        self._kinds = kinds
        self.clear_widgets()

        title = scale_font(Label(text="Legende", bold=True,
                                 color=(0.96, 0.82, 0.45, 1),
                                 halign="center", valign="middle",
                                 size_hint_y=None, height=dh(46)))
        title.bind(size=lambda w, *_: setattr(
            w, "text_size", (w.width, w.height)))
        self.add_widget(title)

        rows = [(CELL_TAKEN, None, "Emplacement\ndeja utilise")]
        if kinds:
            rows += [(CELL_NATURE, k, f"{NATURE_LABEL[k]}\n(zone occupee)")
                     for k in kinds]
        else:
            rows.append((CELL_NATURE, None, "Zone occupee\n(nature)"))
        rows += [(CELL_FREE, None, "Zone vacante"),
                 (CELL_PLAYER, None, "Vous")]

        for rgba, kind, text in rows:
            row = BoxLayout(orientation="horizontal", spacing=dp(8),
                            size_hint_y=None, height=dh(70))
            row.add_widget(_Swatch(rgba, kind, size_hint_x=None, width=dh(70)))
            lbl = scale_font(Label(text=text, color=(0.92, 0.92, 0.95, 1),
                                   halign="left", valign="middle"))
            lbl.bind(size=lambda w, *_: setattr(
                w, "text_size", (w.width, w.height)))
            row.add_widget(lbl)
            self.add_widget(row)

    def _sync(self, *_):
        self._bg.pos = self.pos
        self._bg.size = self.size


def _hm(hours):
    """Duree lisible : 1.25 -> "1 h 15", 0.4 -> "24 min"."""
    total = max(0, int(round(hours * 60)))
    if total >= 60:
        return f"{total // 60} h {total % 60:02d}"
    return f"{total} min"


class _ActionPanel(BoxLayout):
    """Fenetre d'ACTION d'un objet pose. Pour l'instant : le feu de camp.

    Un foyer demande du COMBUSTIBLE (branche, buche), du COMBURANT (feuille,
    ecorce) et une source d'ALLUMAGE. Chaque bouton est grise, avec sa raison,
    quand la matiere n'est pas a proximite."""

    ACTIONS = (("wood", "Alimenter\n(combustible)"),
               ("tinder", "Alimenter\n(comburant)"),
               ("light", "Allumer le feu"))

    def __init__(self, on_close, on_action, **kwargs):
        kwargs.setdefault("orientation", "vertical")
        kwargs.setdefault("padding", dp(12))
        kwargs.setdefault("spacing", dp(8))
        super().__init__(**kwargs)
        self._on_close = on_close
        self._on_action = on_action
        self.hidden = True
        with self.canvas.before:
            # Assez sombre pour rester lisible, assez transparent pour laisser
            # voir le decor et le feu derriere.
            Color(0.05, 0.07, 0.10, 0.68)
            self._bg = RoundedRectangle(radius=[dp(14)])
        self.bind(pos=self._sync, size=self._sync)

        def _label(size_hint_y, color=(0.92, 0.92, 0.95, 1), bold=False):
            lbl = Label(text="", bold=bold, color=color, halign="center",
                        valign="middle", size_hint_y=size_hint_y)
            lbl.bind(size=lambda w, *_: setattr(
                w, "text_size", (w.width, w.height)))
            return scale_font(lbl)

        self.title = _label(0.14, (0.96, 0.82, 0.45, 1), bold=True)
        self.add_widget(self.title)
        self.status = _label(0.20)
        self.add_widget(self.status)

        self.btns = {}
        for key, text in self.ACTIONS:
            b = scale_font(StyledButton(text=text, halign="center",
                                        size_hint_y=0.15))
            b.bind(on_release=lambda _w, k=key: self._on_action(k))
            self.btns[key] = b
            self.add_widget(b)

        self.reason = _label(0.14, (0.85, 0.72, 0.55, 1))
        self.add_widget(self.reason)
        back = scale_font(StyledButton(text="Retour", size_hint_y=0.15))
        back.bind(on_release=lambda *_: self._on_close())
        self.add_widget(back)

    def _sync(self, *_):
        self._bg.pos = self.pos
        self._bg.size = self.size

    def hide(self, hidden):
        """Montre / masque la fenetre.

        On ne se sert PAS de `disabled` pour la masquer : dans Kivy un widget
        desactive AVALE les touches qui tombent sur lui. Cette fenetre couvre
        le centre de l'ecran, elle bloquerait donc la grille en dessous."""
        self.hidden = hidden
        self.opacity = 0.0 if hidden else 1.0

    def on_touch_down(self, touch):
        if self.hidden:
            return False              # laisse passer vers la grille
        return super().on_touch_down(touch)

    @staticmethod
    def _set(btn, ok):
        btn.disabled = not ok
        btn.opacity = 1.0 if ok else 0.45

    def update(self, state, gx, gy, message=""):
        """Rafraichit l'etat du foyer et la disponibilite de chaque action."""
        f = state.fire_at(gx, gy)
        lit = bool(f.get("lit"))
        self.title.text = items.display_name("Feu_de_camp")
        pct = int(round(state.fire_light_chance(f) * 100))
        lines = ["Allume" if lit else "Eteint",
                 f"Combustible : {_hm(f['fuel'])}"]
        if lit:
            lines.append(f"S'eteint dans {_hm(state.fire_burn_hours(f))}")
        else:
            lines.append(f"Chance d'allumage : {pct} %")
        self.status.text = "\n".join(lines)

        why = [message] if message else []
        # Chaque bouton annonce CE QU'IL APPORTE avec la matiere qui serait
        # utilisee : autant de duree pour le combustible, autant de chance
        # d'allumage pour le comburant.
        wood = state.fire_source(items.FIRE_WOOD_HOURS)
        self.btns["wood"].text = "Alimenter\n(combustible)" + (
            f"\n+{_hm(items.FIRE_WOOD_HOURS[wood])}" if wood else "")
        self._set(self.btns["wood"], wood is not None)
        if wood is None:
            why.append("Combustible : aucune branche ni buche a proximite.")
        tinder = state.fire_source(items.FIRE_TINDER_CHANCE)
        self.btns["tinder"].text = "Alimenter\n(comburant)" + (
            f"\n+{int(round(items.FIRE_TINDER_CHANCE[tinder] * 100))} %"
            if tinder else "")
        self._set(self.btns["tinder"], tinder is not None)
        if tinder is None:
            why.append("Comburant : aucune feuille ni ecorce a proximite.")

        if lit:
            light_why = "Allumer : le feu brule deja."
        elif state.fire_starter_hand() is None:
            light_why = ("Allumer : il faut un silex ou une pierre "
                         "coupante en main.")
        elif f["fuel"] <= 0.0:
            light_why = "Allumer : il manque du combustible dans le foyer."
        else:
            light_why = None
        self.btns["light"].text = ("Allumer le feu" if lit else
                                   f"Allumer le feu\n{pct} %")
        self._set(self.btns["light"], light_why is None)
        if light_why:
            why.append(light_why)
        self.reason.text = "\n".join(why[:2])


class _GridOverlay(Widget):
    """Grille 5x5 avec joueur en (gx=2, gy=0). Cellules cliquables (sauf
    la case joueur et les cases deja prises)."""

    def __init__(self, on_cell_pick, **kwargs):
        super().__init__(**kwargs)
        self.on_cell_pick = on_cell_pick
        self.taken = set()               # {(gx, gy), ...} objets installes
        self.nature = {}                 # {(gx, gy): "tree"|"bush"|"rock"}
        self.objects = {}                # {(gx, gy): (nom, allume)}
        # "place" = choisir une case LIBRE ou poser un objet ;
        # "use"   = choisir un objet INSTALLE pour s'en servir.
        self.mode = "place"
        self.bind(pos=self._redraw, size=self._redraw)

    def _grid_geom(self):
        cs = min(self.width, self.height) / 5.2   # petite marge autour
        total = 5 * cs
        ox = self.center_x - total / 2
        oy = self.center_y - total / 2
        return ox, oy, cs

    def _redraw(self, *_):
        self.canvas.clear()
        if self.width <= 0 or self.height <= 0:
            return
        ox, oy, cs = self._grid_geom()
        with self.canvas:
            # Fond de la grille (semi-transparent pour laisser voir le decor).
            Color(*CELL_BG)
            Rectangle(pos=(ox, oy), size=(5 * cs, 5 * cs))
            # Lignes blanches translucides.
            Color(*CELL_LINE)
            for i in range(6):
                Line(points=[ox + i * cs, oy,
                             ox + i * cs, oy + 5 * cs], width=1.2)
                Line(points=[ox, oy + i * cs,
                             ox + 5 * cs, oy + i * cs], width=1.2)
            # Case joueur (gx=2, gy=0) : surlignee bleu, non cliquable.
            px = ox + 2 * cs
            py = oy + 0 * cs
            Color(*CELL_PLAYER)
            Rectangle(pos=(px, py), size=(cs, cs))
            # Point du joueur (petit disque bleu au centre de sa case).
            r = cs * 0.18
            Color(0.30, 0.70, 1.00, 1.0)
            Ellipse(pos=(px + cs / 2 - r, py + cs / 2 - r),
                    size=(r * 2, r * 2))
            # Fleche de direction (le joueur regarde vers le haut de la grille).
            Color(1, 1, 1, 0.95)
            aw, ah = cs * 0.28, cs * 0.28
            acx = px + cs / 2
            ay0 = py + cs * 0.55
            ay1 = py + cs * 0.90
            Line(points=[acx, ay0, acx, ay1], width=2.2)
            Line(points=[acx - aw / 2, ay1 - aw * 0.55, acx, ay1,
                         acx + aw / 2, ay1 - aw * 0.55], width=2.2)
            # Cases occupees par la NATURE (arbre, buisson, gros rocher) :
            # surlignees vertes et marquees du pictogramme de l'obstacle,
            # non cliquables.
            for (gx, gy), kind in sorted(self.nature.items()):
                tx = ox + gx * cs
                ty = oy + gy * cs
                Color(*CELL_NATURE)
                Rectangle(pos=(tx, ty), size=(cs, cs))
                draw_nature_glyph(kind, tx + cs / 2, ty + cs / 2, cs * 0.72)
            # Cases deja prises (installees) : surlignees rouge, avec le
            # pictogramme de l'objet pose (feu de camp...).
            for (gx, gy) in sorted(self.taken):
                tx = ox + gx * cs
                ty = oy + gy * cs
                Color(*CELL_TAKEN)
                Rectangle(pos=(tx, ty), size=(cs, cs))
                obj = self.objects.get((gx, gy))
                if obj:
                    draw_object_glyph(obj[0], tx + cs / 2, ty + cs / 2,
                                      cs * 0.72, lit=obj[1])

    def on_touch_down(self, touch):
        if not self.collide_point(*touch.pos):
            return super().on_touch_down(touch)
        ox, oy, cs = self._grid_geom()
        if not (ox <= touch.x < ox + 5 * cs and oy <= touch.y < oy + 5 * cs):
            return super().on_touch_down(touch)
        gx = int((touch.x - ox) / cs)
        gy = int((touch.y - oy) / cs)
        gx = max(0, min(4, gx))
        gy = max(0, min(4, gy))
        if self.mode == "use":
            # Seuls les objets poses repondent.
            if (gx, gy) in self.objects:
                self.on_cell_pick(gx, gy)
            return True
        if (gx, gy) == (2, 0):
            return True                  # case joueur : ignoree
        if (gx, gy) in self.taken or (gx, gy) in self.nature:
            return True                  # deja prise ou occupee par la nature
        self.on_cell_pick(gx, gy)
        return True


class PlaceScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._slot = None                # main dont on installe (0 ou 1)
        # "place" = poser l'objet tenu ; "use" = se servir d'un objet pose
        # (ouvert par le bouton Proximite).
        self.mode = "place"

        root = FloatLayout()
        self.background = AnimatedBackground(time_scale=0, size_hint=(1, 1),
                                             pos_hint={"x": 0, "y": 0})
        root.add_widget(self.background)
        # Fond = vue VERS LE BAS du sol de la case courante.
        self.scenery = ZoneScenery(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        root.add_widget(self.scenery)
        self._scene_key = None

        # Voile de nuit (comme dans la carte et le craft).
        self.night = Widget(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        with self.night.canvas:
            self._night_color = Color(0.03, 0.05, 0.12, 0.0)
            self._night_rect = Rectangle(pos=self.night.pos,
                                         size=self.night.size)

        def _sync_night(*_):
            self._night_rect.pos = self.night.pos
            self._night_rect.size = self.night.size
        self.night.bind(pos=_sync_night, size=_sync_night)
        root.add_widget(self.night)

        self.grid_overlay = _GridOverlay(on_cell_pick=self._on_cell_pick,
                                         size_hint=(0.90, 0.78),
                                         pos_hint={"center_x": 0.5,
                                                   "center_y": 0.46})
        root.add_widget(self.grid_overlay)

        # Legende, a GAUCHE de la grille : en paysage la grille est carree et
        # centree, la bande de gauche est donc libre.
        self.legend = _Legend(size_hint=(0.24, None),
                              pos_hint={"x": 0.02, "center_y": 0.46})
        self.legend.bind(minimum_height=self.legend.setter("height"))
        self.legend.height = self.legend.minimum_height
        root.add_widget(self.legend)

        # Titre (haut).
        self.title = scale_font(Label(text="Choisis une case",
                                bold=True, color=(1, 1, 1, 1),
                                halign="center", valign="middle",
                                size_hint=(0.90, 0.08),
                                pos_hint={"center_x": 0.5, "top": 0.98}),
                                0.028)
        self.title.bind(size=lambda w, *_: setattr(
            w, "text_size", (w.width, w.height)))
        root.add_widget(self.title)

        # Bouton Annuler (bas droite) : retour au jeu sans installer.
        cancel = scale_font(StyledButton(text="Annuler",
                            size_hint=(0.20, 0.08),
                            pos_hint={"right": 0.98, "y": 0.02}), 0.022)
        cancel.bind(on_release=lambda *_: setattr(self.manager,
                                                  "current", "game"))
        root.add_widget(cancel)

        # Fenetre d'ACTION : remplace la grille quand on choisit un objet
        # pose (mode "use"). Construite une fois, montree a la demande.
        self.action_panel = _ActionPanel(on_close=self._close_action,
                                         on_action=self._do_fire_action,
                                         size_hint=(0.56, 0.74),
                                         pos_hint={"center_x": 0.5,
                                                   "center_y": 0.48})
        self._action_cell = None          # (gx, gy) de l'objet en cours
        self._fire_msg = ""               # resultat de la derniere tentative
        self.action_panel.hide(True)      # masquee tant qu'on est sur la grille
        root.add_widget(self.action_panel)

        self.root_layout = root
        self.add_widget(root)

    # ------------------------------------------------------------------ #
    def _show_action(self, visible):
        """Bascule entre la GRILLE et la fenetre d'action."""
        self.action_panel.hide(not visible)
        for w in (self.grid_overlay, self.legend):
            w.opacity = 0.0 if visible else 1.0
            w.disabled = visible

    def _close_action(self):
        self._action_cell = None
        self._show_action(False)
        self.on_pre_enter()

    def on_pre_enter(self):
        state = App.get_running_app().game_state
        if state is None:
            return
        self.background.set_seconds(state.time_seconds)
        self.background.set_weather(state.effective_weather())
        self._night_color.a = night_darkness(state.time_seconds)
        zone = state.current_zone()
        objs = [(o[0], int(o[1]), int(o[2]),
                 o[0] == "Feu_de_camp"
                 and bool(state.fire_at(o[1], o[2]).get("lit")))
                for o in state.installed_objects_here()]
        # Fond : la GRILLE se lit d'en haut (vue du sol), mais la fenetre
        # d'action s'ouvre sur la SCENE du jeu -> on voit le decor et, si le
        # foyer est allume, ses flammes derriere la fenetre.
        seed = state.player_x * 131 + state.player_y
        on_action = self._action_cell is not None
        key = (zone, state.player_x, state.player_y, on_action, tuple(objs))
        if key != self._scene_key:
            if on_action:
                self.scenery.set_scene(zone, seed,
                                       taken=state.harvested_here(),
                                       installed=objs)
            else:
                self.scenery.set_ground(zone, seed)
            self._scene_key = key
        # Marque les positions deja installees comme non cliquables, et les
        # cases occupees par un GROS element du decor (arbre, buisson, rocher).
        self.grid_overlay.taken = {(gx, gy) for _n, gx, gy, _l in objs}
        self.grid_overlay.objects = {(gx, gy): (n, lit)
                                     for n, gx, gy, lit in objs}
        self.grid_overlay.nature = {(int(gx), int(gy)): kind for (gx, gy), kind
                                    in state.nature_cells_here().items()}
        self.grid_overlay.mode = self.mode
        self.grid_overlay._redraw()
        # La legende ne liste que les obstacles presents sur CETTE case.
        self.legend.rebuild(self.grid_overlay.nature.values())
        # Titre : selon qu'on POSE un objet ou qu'on s'en SERT.
        if self.mode == "use":
            self.title.text = "Choisis un objet a proximite"
        elif self._slot is not None and self._slot in (0, 1):
            item = state.hands[self._slot]
            self.title.text = (f"Placer : {items.display_name(item)}"
                               if item else "Choisis une case")
        else:
            self.title.text = "Choisis une case"
        # La fenetre d'action reste ouverte si on vient d'y agir.
        self._show_action(self._action_cell is not None)
        if self._action_cell is not None:
            self.action_panel.update(state, *self._action_cell,
                                     message=self._fire_msg)

    def _on_cell_pick(self, gx, gy):
        state = App.get_running_app().game_state
        if state is None:
            self.manager.current = "game"
            return
        if self.mode == "use":
            # Ouvre la fenetre d'action de l'objet choisi. on_pre_enter fait
            # tout : bascule le fond sur la scene et affiche la fenetre.
            self._action_cell = (gx, gy)
            self._fire_msg = ""
            self.on_pre_enter()
            return
        if self._slot is None:
            self.manager.current = "game"
            return
        if state.install_from_hand(self._slot, gx, gy):
            App.get_running_app().autosave()
        self._slot = None
        self.manager.current = "game"

    def _do_fire_action(self, what):
        """Une action de la fenetre du foyer : alimenter / attiser / allumer."""
        state = App.get_running_app().game_state
        if state is None or self._action_cell is None:
            return
        gx, gy = self._action_cell
        if what == "light":
            ok = state.fire_light(gx, gy)
            # Un echec est un vrai resultat de jeu (le comburant a brule) :
            # on le dit, et on sauvegarde quand meme.
            self._fire_msg = "" if ok else ("Le feu n'a pas pris. Ajoute du "
                                            "comburant et reessaie.")
            ok = True
        else:
            self._fire_msg = ""
            ok = state.fire_add(gx, gy, what)
        if ok:
            App.get_running_app().autosave()
        self.on_pre_enter()
