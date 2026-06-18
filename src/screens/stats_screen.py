"""
Ecran "Statistiques".

Pour l'instant VIERGE (contenu a venir) : un titre et un bouton pour revenir.
Le contenu sera elabore plus tard.
"""
from kivy.uix.screenmanager import Screen
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp

from src.widgets.menu_backdrop import MenuBackdrop
from src.widgets.styled_button import StyledButton
from src.widgets.responsive import scale_font
from src.widgets.fonts import title_font, ui_font


class StatsScreen(Screen):
    # Ecran vers lequel revenir (defini par l'appelant ; "game" depuis la pause).
    return_to = "game"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        root = FloatLayout()
        root.add_widget(MenuBackdrop())

        content = BoxLayout(orientation="vertical",
                            padding=dp(26), spacing=dp(14),
                            size_hint=(0.6, 0.7),
                            pos_hint={"center_x": 0.5, "center_y": 0.5})
        with content.canvas.before:
            Color(0, 0, 0, 0.30)
            self._panel = RoundedRectangle(radius=[dp(22)])

        def _sync_panel(*_):
            self._panel.pos = content.pos
            self._panel.size = content.size
        content.bind(pos=_sync_panel, size=_sync_panel)

        content.add_widget(scale_font(Label(
            text="Statistiques", bold=True, font_name=title_font(),
            color=(0.96, 0.82, 0.45, 1), size_hint=(1, 0.3)), 0.05))

        content.add_widget(scale_font(Label(
            text="(a venir)", halign="center", font_name=ui_font(),
            color=(0.82, 0.86, 0.92, 1), size_hint=(1, 0.4)), 0.022))

        back_btn = scale_font(StyledButton(text="Retour",
                              font_name=ui_font(), size_hint=(1, 0.2)), 0.024)
        back_btn.bind(on_release=lambda *_: setattr(self.manager, "current",
                                                    self.return_to))
        content.add_widget(back_btn)

        root.add_widget(content)
        self.add_widget(root)
