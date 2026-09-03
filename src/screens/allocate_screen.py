"""
Ecran de REPARTITION de l'experience, au debut d'une partie.

Les sept aptitudes partent toutes au NIVEAU 0. Le joueur dispose de 500
points d'experience a placer ou il veut, par tranches de 10 : rien ne
l'oblige a les etaler, il peut tout mettre dans une seule aptitude.

Comme un niveau coute deux fois plus que le precedent (20, 40, 80...), la
meme experience rapporte beaucoup dans une aptitude negligee et peu dans
une aptitude deja poussee. L'ecran affiche donc le NIVEAU obtenu a chaque
appui, pas seulement l'experience placee.

Il ne laisse pas commencer tant qu'il reste de l'experience : elle ne se
recupere pas une fois la partie lancee.
"""
from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp

from src import stats as stats_mod
from src.widgets.menu_backdrop import MenuBackdrop
from src.widgets.styled_button import StyledButton
from src.widgets.responsive import scale_font, dh

_GOLD = (0.96, 0.82, 0.45, 1)
_DIM = (0.72, 0.74, 0.80, 1)
_ROW = 128


def _fit(label, ratio=0.55):
    """Police proportionnelle a la hauteur de la ligne, reduite si trop large."""
    def _update(*_):
        if label.width <= 1 or label.height <= 1:
            return
        target = label.height * ratio
        label.text_size = (None, None)
        label.font_size = target
        label.texture_update()
        if label.texture_size[0] > label.width:
            label.font_size = max(9, target * label.width
                                  / label.texture_size[0])
        label.text_size = (label.width, label.height)
    label.bind(size=_update, text=_update)
    _update()
    return label


class _XpBar(Label):
    """Un texte pose SUR une barre de progression.

    La barre est dans `canvas.before` : le texte ("200/320") se lit donc
    par-dessus, et l'on voit d'un coup d'oeil ou en est le niveau sans
    avoir a comparer deux nombres."""

    def __init__(self, color=(0.42, 0.82, 0.52, 0.55), **kwargs):
        kwargs.setdefault("halign", "center")
        kwargs.setdefault("valign", "middle")
        super().__init__(**kwargs)
        self._part = 0.0
        self._alpha = color[3]
        with self.canvas.before:
            Color(1, 1, 1, 0.10)
            self._back = RoundedRectangle(radius=[dp(5)])
            self._fill_color = Color(*color)
            self._fill = RoundedRectangle(radius=[dp(5)])
        self.bind(pos=self._sync, size=self._sync)
        self._sync()

    def set_progress(self, done, needed, text=None):
        self._part = (max(0.0, min(1.0, done / float(needed)))
                      if needed else 0.0)
        self.text = text if text is not None else f"{done}/{needed}"
        self._sync()

    def _sync(self, *_):
        self._back.pos = self.pos
        self._back.size = self.size
        self._fill.pos = self.pos
        width = self.width * self._part

        # Une barre qu'on RAMENE A ZERO (passage de niveau : 10/20 devient
        # 0/40) restait affichee a moitie pleine. Un RoundedRectangle plus
        # etroit que ses coins arrondis ne reconstruit pas sa geometrie et
        # garde donc son ancien dessin : lui donner une taille nulle ne
        # l'efface pas. On coupe donc sa COULEUR, ce qui l'efface a coup sur,
        # et on rabat le rayon des coins tant qu'elle est plus etroite qu'eux.
        self._fill_color.a = self._alpha if width > 0.5 else 0.0
        radius = max(1.0, min(dp(5), self.height / 2.0, width / 2.0))
        self._fill.radius = [radius]
        self._fill.size = (max(0.0, width), self.height)


class AllocateScreen(Screen):
    """Repartition des points avant de lancer la partie."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Renseignes par NewGameScreen avant de basculer ici.
        self.pending_name = ""
        self.pending_difficulty = "Moyen"
        self._spent = {key: 0 for key in stats_mod.STAT_ORDER}
        self._rows = {}

        root = FloatLayout()
        root.add_widget(MenuBackdrop())

        column = BoxLayout(orientation="vertical", padding=dp(18),
                           spacing=dp(8), size_hint=(0.92, 0.94),
                           pos_hint={"center_x": 0.5, "center_y": 0.5})

        column.add_widget(scale_font(Label(text="Aptitudes", bold=True,
                          color=_GOLD, size_hint=(1, 0.09)), 0.03))
        column.add_widget(scale_font(Label(
            text="Un niveau coute deux fois plus que le precedent : "
                 "20, 40, 80, 160...",
            color=_DIM, size_hint=(1, 0.055)), 0.016))
        # Ce qu'il reste a placer, sur une barre qui montre la part deja
        # affectee : le nombre seul ne dit pas si l'on en est au debut ou a
        # la fin.
        self.remaining = _fit(_XpBar(bold=True, color=(0.85, 0.70, 0.35, 0.45),
                                     size_hint=(1, 0.085)), 0.50)
        column.add_widget(self.remaining)

        scroll = ScrollView(size_hint=(1, 0.61))
        body = BoxLayout(orientation="vertical", spacing=dp(6),
                         size_hint_y=None)
        body.bind(minimum_height=body.setter("height"))
        for key in stats_mod.STAT_ORDER:
            body.add_widget(self._make_row(key))
        scroll.add_widget(body)
        column.add_widget(scroll)

        buttons = BoxLayout(orientation="horizontal", spacing=dp(8),
                            size_hint=(1, 0.11))
        reset = scale_font(StyledButton(text="Tout remettre"), 0.02)
        reset.bind(on_release=self._reset)
        buttons.add_widget(reset)
        spread = scale_font(StyledButton(text="Repartir egalement"), 0.02)
        spread.bind(on_release=self._spread)
        buttons.add_widget(spread)
        column.add_widget(buttons)

        self.start_btn = scale_font(StyledButton(text="Commencer",
                                    size_hint=(1, 0.11)), 0.024)
        self.start_btn.bind(on_release=self._start)
        column.add_widget(self.start_btn)

        back = scale_font(StyledButton(text="Retour", size_hint=(1, 0.09)),
                          0.018)
        back.bind(on_release=lambda *_: setattr(self.manager, "current",
                                                "newgame"))
        column.add_widget(back)

        root.add_widget(column)
        self.add_widget(root)

    # ------------------------------------------------------------------ #
    def _make_row(self, key):
        row = BoxLayout(orientation="horizontal", spacing=dp(6),
                        padding=(dp(10), dp(4)), size_hint_y=None,
                        height=dh(_ROW))
        with row.canvas.before:
            Color(0, 0, 0, 0.35)
            bg = RoundedRectangle(radius=[dp(8)])
        row.bind(pos=lambda w, *_: setattr(bg, "pos", w.pos),
                 size=lambda w, *_: setattr(bg, "size", w.size))

        texts = BoxLayout(orientation="vertical", size_hint_x=0.46)
        texts.add_widget(_fit(Label(text=stats_mod.STAT_NAMES[key], bold=True,
                                    color=_GOLD, halign="left",
                                    valign="middle"), 0.60))
        texts.add_widget(_fit(Label(text=stats_mod.STAT_NOTES[key], color=_DIM,
                                    halign="left", valign="middle"), 0.42))
        row.add_widget(texts)

        minus = scale_font(StyledButton(text="-", size_hint_x=0.13), 0.03)
        minus.bind(on_release=lambda _w, k=key: self._change(k, -1))
        row.add_widget(minus)

        # Le niveau au-dessus, l'avancee vers le suivant en dessous.
        gauge = BoxLayout(orientation="vertical", spacing=dp(2),
                          size_hint_x=0.28)
        value = _fit(Label(text="niv. 0", bold=True, halign="center",
                           valign="middle"), 0.62)
        gauge.add_widget(value)
        bar = _fit(_XpBar(), 0.58)
        gauge.add_widget(bar)
        row.add_widget(gauge)

        plus = scale_font(StyledButton(text="+", size_hint_x=0.13), 0.03)
        plus.bind(on_release=lambda _w, k=key: self._change(k, +1))
        row.add_widget(plus)

        self._rows[key] = (value, bar, minus, plus)
        return row

    # ------------------------------------------------------------------ #
    def on_pre_enter(self):
        self._reset()

    def _left(self):
        """Experience encore a placer."""
        return stats_mod.START_XP - sum(self._spent.values())

    def _change(self, key, steps):
        """Place ou retire une tranche d'experience (10 points)."""
        delta = steps * stats_mod.XP_STEP
        if delta > 0 and self._left() < delta:
            return
        if delta < 0 and self._spent[key] < -delta:
            return
        self._spent[key] += delta
        self._refresh()

    def _reset(self, *_):
        self._spent = {key: 0 for key in stats_mod.STAT_ORDER}
        self._refresh()

    def _spread(self, *_):
        """Repartition aussi egale que possible.

        500 ne se divise pas en sept parts de 10 : on donne une tranche de
        plus aux premieres aptitudes plutot que de laisser du reste."""
        count = len(stats_mod.STAT_ORDER)
        steps = stats_mod.START_XP // stats_mod.XP_STEP
        base, extra = divmod(steps, count)
        self._spent = {
            key: (base + (1 if i < extra else 0)) * stats_mod.XP_STEP
            for i, key in enumerate(stats_mod.STAT_ORDER)}
        self._refresh()

    def _refresh(self):
        left = self._left()
        placed = stats_mod.START_XP - left
        self.remaining.set_progress(
            placed, stats_mod.START_XP,
            text=(f"Reste {left} xp a placer   ({placed}/"
                  f"{stats_mod.START_XP})" if left
                  else f"Toute l'experience est placee   "
                       f"({stats_mod.START_XP}/{stats_mod.START_XP})"))
        self.remaining.color = _GOLD if left else (0.60, 0.90, 0.65, 1)
        for key, (value, bar, minus, plus) in self._rows.items():
            spent = self._spent[key]
            level, rest = stats_mod.level_from_xp(spent)
            # Le niveau d'abord : c'est lui qui compte, l'experience placee
            # n'est que le moyen d'y arriver.
            value.text = f"niv. {level}"
            bar.set_progress(rest, stats_mod.xp_needed(level))
            minus.disabled = spent < stats_mod.XP_STEP
            plus.disabled = left < stats_mod.XP_STEP
        # On ne part pas en laissant de l'experience derriere soi : elle ne
        # se recupere plus une fois la partie commencee.
        self.start_btn.disabled = left > 0

    def _start(self, *_):
        from src.game_state import GameState
        app = App.get_running_app()
        levels, rests = {}, {}
        for key in stats_mod.STAT_ORDER:
            levels[key], rests[key] = stats_mod.level_from_xp(self._spent[key])
        app.game_state = GameState.new_random(
            name=self.pending_name, difficulty=self.pending_difficulty,
            stats=levels, stat_xp=rests)
        app.autosave()
        self.manager.current = "game"
