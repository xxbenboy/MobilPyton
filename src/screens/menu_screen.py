"""
Ecran d'accueil.

Le menu annonce le ton du jeu : un jeu de SURVIE, GENERATIF (chaque partie
genere une carte et des elements aleatoires), ou le temps s'ecoule sans
pouvoir etre arrete. Le fond anime tourne en boucle pour l'ambiance.

Il oriente vers :
- "Nouvelle partie" : ecran de creation (nom + difficulte).
- "Charger"         : liste de toutes les sauvegardes (desactive s'il n'y
                      en a aucune).
"""
from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button

from src.widgets.animated_background import AnimatedBackground
from src.widgets.responsive import scale_font


class MenuScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        root = FloatLayout()

        # Fond anime, derriere le reste.
        root.add_widget(AnimatedBackground(size_hint=(1, 1),
                                           pos_hint={"x": 0, "y": 0}))

        content = BoxLayout(orientation="vertical", padding=40, spacing=16,
                            size_hint=(0.8, 0.7),
                            pos_hint={"center_x": 0.5, "center_y": 0.5})

        content.add_widget(scale_font(Label(text="SURVIVRE",
                                 bold=True, size_hint=(1, 0.3)), 0.05))

        content.add_widget(scale_font(Label(
            text="Un monde different a chaque partie.\nLe temps ne s'arrete jamais.",
            halign="center",
            color=(0.85, 0.85, 0.85, 1), size_hint=(1, 0.2)), 0.018))

        new_btn = scale_font(Button(text="Nouvelle partie",
                         size_hint=(1, 0.18)), 0.026)
        new_btn.bind(on_release=lambda *_: setattr(self.manager, "current",
                                                   "newgame"))
        content.add_widget(new_btn)

        # "Charger" : actif seulement s'il existe au moins une sauvegarde.
        self.load_btn = scale_font(Button(text="Charger",
                               size_hint=(1, 0.18)), 0.026)
        self.load_btn.bind(on_release=lambda *_: setattr(self.manager,
                                                         "current", "load"))
        content.add_widget(self.load_btn)

        quit_btn = scale_font(Button(text="Quitter", size_hint=(1, 0.14)), 0.022)
        quit_btn.bind(on_release=lambda *_: App.get_running_app().stop())
        content.add_widget(quit_btn)

        root.add_widget(content)
        self.add_widget(root)

    def on_pre_enter(self):
        # Pas de sauvegarde -> bouton "Charger" grise.
        has_save = App.get_running_app().save_manager.has_any()
        self.load_btn.disabled = not has_save
