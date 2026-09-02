"""
Ecran de REPARTITION des points d'aptitude, au debut d'une partie.

Les sept aptitudes partent toutes au niveau 1. Le joueur dispose de 35
points a placer ou il veut : rien ne l'oblige a les etaler, il peut tout
mettre dans une seule aptitude.

L'ecran ne laisse pas commencer tant qu'il reste des points : sinon on les
perdrait sans le vouloir, puisqu'ils ne se recuperent pas ensuite.
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
        self.remaining = scale_font(Label(text="", size_hint=(1, 0.07)), 0.022)
        column.add_widget(self.remaining)

        scroll = ScrollView(size_hint=(1, 0.66))
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

        texts = BoxLayout(orientation="vertical", size_hint_x=0.52)
        texts.add_widget(_fit(Label(text=stats_mod.STAT_NAMES[key], bold=True,
                                    color=_GOLD, halign="left",
                                    valign="middle"), 0.60))
        texts.add_widget(_fit(Label(text=stats_mod.STAT_NOTES[key], color=_DIM,
                                    halign="left", valign="middle"), 0.42))
        row.add_widget(texts)

        minus = scale_font(StyledButton(text="-", size_hint_x=0.13), 0.03)
        minus.bind(on_release=lambda _w, k=key: self._change(k, -1))
        row.add_widget(minus)

        value = _fit(Label(text="1", bold=True, halign="center",
                           valign="middle", size_hint_x=0.22), 0.62)
        row.add_widget(value)

        plus = scale_font(StyledButton(text="+", size_hint_x=0.13), 0.03)
        plus.bind(on_release=lambda _w, k=key: self._change(k, +1))
        row.add_widget(plus)

        self._rows[key] = (value, minus, plus)
        return row

    # ------------------------------------------------------------------ #
    def on_pre_enter(self):
        self._reset()

    def _left(self):
        return stats_mod.START_POINTS - sum(self._spent.values())

    def _change(self, key, delta):
        if delta > 0 and self._left() <= 0:
            return
        if delta < 0 and self._spent[key] <= 0:
            return
        self._spent[key] += delta
        self._refresh()

    def _reset(self, *_):
        self._spent = {key: 0 for key in stats_mod.STAT_ORDER}
        self._refresh()

    def _spread(self, *_):
        """Le meme partage que la partie de test : 5 points partout."""
        self._spent = {key: stats_mod.DEBUG_POINTS_EACH
                       for key in stats_mod.STAT_ORDER}
        self._refresh()

    def _refresh(self):
        left = self._left()
        self.remaining.text = (f"{left} point(s) a placer"
                               if left else "Tous les points sont places")
        self.remaining.color = _GOLD if left else (0.60, 0.90, 0.65, 1)
        for key, (value, minus, plus) in self._rows.items():
            value.text = str(stats_mod.START_LEVEL + self._spent[key])
            minus.disabled = self._spent[key] <= 0
            plus.disabled = left <= 0
        # On ne part pas en laissant des points derriere soi : ils ne se
        # recuperent plus une fois la partie commencee.
        self.start_btn.disabled = left > 0

    def _start(self, *_):
        from src.game_state import GameState
        app = App.get_running_app()
        levels = {key: stats_mod.START_LEVEL + self._spent[key]
                  for key in stats_mod.STAT_ORDER}
        app.game_state = GameState.new_random(
            name=self.pending_name, difficulty=self.pending_difficulty,
            stats=levels)
        app.autosave()
        self.manager.current = "game"
