"""
Ecran d'accueil.

Le menu annonce le ton du jeu : un jeu de SURVIE, GENERATIF (chaque partie
genere une carte et des elements aleatoires), ou le temps s'ecoule sans
pouvoir etre arrete.

Visuel : fond anime (degrade + etoiles), panneau translucide arrondi derriere
le contenu, titre mis en valeur, et boutons stylises (StyledButton).
"""
from kivy.app import App
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


class MenuScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        root = FloatLayout()

        # Fond commun des ecrans de menu (ciel qui defile + foret).
        root.add_widget(MenuBackdrop())

        content = BoxLayout(orientation="vertical",
                            padding=dp(26), spacing=dp(14),
                            size_hint=(0.5, 0.88),
                            pos_hint={"center_x": 0.5, "center_y": 0.5})

        # Panneau translucide arrondi derriere le contenu (profondeur).
        with content.canvas.before:
            Color(0, 0, 0, 0.30)
            self._panel = RoundedRectangle(radius=[dp(22)])

        def _sync_panel(*_):
            self._panel.pos = content.pos
            self._panel.size = content.size
        content.bind(pos=_sync_panel, size=_sync_panel)

        # Titre (police speciale si assets/fonts/title.ttf existe).
        content.add_widget(scale_font(Label(
            text="Wild Breath", bold=True,
            font_name=title_font(),
            color=(0.96, 0.82, 0.45, 1),          # doré
            size_hint=(1, 0.34)), 0.11))

        content.add_widget(scale_font(Label(
            text="Trouve l'équilibre entre le souffle\n"
                 "de la nature et celui de la survie",
            halign="center", font_name=ui_font(),
            color=(0.82, 0.86, 0.92, 1), size_hint=(1, 0.18)), 0.017))

        new_btn = scale_font(StyledButton(text="Nouvelle partie",
                             font_name=ui_font(), size_hint=(1, 0.16)), 0.026)
        new_btn.bind(on_release=lambda *_: setattr(self.manager, "current",
                                                   "newgame"))
        content.add_widget(new_btn)

        # "Charger" : actif seulement s'il existe au moins une sauvegarde.
        self.load_btn = scale_font(StyledButton(text="Charger",
                                   font_name=ui_font(), size_hint=(1, 0.16)), 0.026)
        self.load_btn.bind(on_release=lambda *_: setattr(self.manager,
                                                         "current", "load"))
        content.add_widget(self.load_btn)

        quit_btn = scale_font(StyledButton(text="Quitter",
                              font_name=ui_font(), size_hint=(1, 0.13)), 0.022)
        quit_btn.bind(on_release=lambda *_: App.get_running_app().stop())
        content.add_widget(quit_btn)

        root.add_widget(content)
        self.add_widget(root)

    def on_pre_enter(self):
        # Pas de sauvegarde -> bouton "Charger" grise.
        has_save = App.get_running_app().save_manager.has_any()
        self.load_btn.disabled = not has_save
