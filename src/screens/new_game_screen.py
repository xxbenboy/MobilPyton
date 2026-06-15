"""
Ecran "Nouvelle partie".

Avant de lancer une partie, le joueur :
- lui donne un NOM (sert aussi a nommer sa sauvegarde),
- choisit une DIFFICULTE (Facile / Moyen / Difficile).

On cree alors l'etat de partie, on le sauvegarde tout de suite (pour qu'il
apparaisse dans "Charger"), puis on bascule sur l'ecran de jeu.
"""
from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.togglebutton import ToggleButton

from src.game_state import GameState, DIFFICULTIES
from src.widgets.animated_background import AnimatedBackground
from src.widgets.responsive import scale_font


class NewGameScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        root = FloatLayout()
        root.add_widget(AnimatedBackground(size_hint=(1, 1),
                                           pos_hint={"x": 0, "y": 0}))

        column = BoxLayout(orientation="vertical", padding=24, spacing=12,
                           size_hint=(0.88, 0.8),
                           pos_hint={"center_x": 0.5, "center_y": 0.5})

        column.add_widget(scale_font(Label(text="Nouvelle partie",
                                bold=True, size_hint=(1, 0.16)), 0.034))

        column.add_widget(scale_font(Label(text="Nom de la partie",
                                size_hint=(1, 0.08)), 0.018))
        self.name_input = scale_font(TextInput(multiline=False,
                                    size_hint=(1, 0.12)), 0.022)
        column.add_widget(self.name_input)

        column.add_widget(scale_font(Label(text="Difficulte",
                                size_hint=(1, 0.08)), 0.018))
        diff_row = BoxLayout(orientation="horizontal", spacing=8,
                             size_hint=(1, 0.14))
        self.diff_buttons = []
        for difficulty in DIFFICULTIES:
            tb = scale_font(ToggleButton(text=difficulty, group="difficulty",
                              allow_no_selection=False), 0.02)
            if difficulty == "Moyen":
                tb.state = "down"
            diff_row.add_widget(tb)
            self.diff_buttons.append(tb)
        column.add_widget(diff_row)

        # Message d'erreur (ex. nom vide).
        self.error = scale_font(Label(text="",
                           color=(1, 0.5, 0.5, 1), size_hint=(1, 0.08)), 0.016)
        column.add_widget(self.error)

        start_btn = scale_font(Button(text="Commencer",
                           size_hint=(1, 0.18)), 0.024)
        start_btn.bind(on_release=self.start)
        column.add_widget(start_btn)

        back_btn = scale_font(Button(text="Retour", size_hint=(1, 0.12)), 0.018)
        back_btn.bind(on_release=lambda *_: setattr(self.manager, "current",
                                                    "menu"))
        column.add_widget(back_btn)

        root.add_widget(column)
        self.add_widget(root)

    def on_pre_enter(self):
        # Repart d'un formulaire propre a chaque arrivee.
        self.name_input.text = ""
        self.error.text = ""
        for tb in self.diff_buttons:
            tb.state = "down" if tb.text == "Moyen" else "normal"

    def _selected_difficulty(self):
        for tb in self.diff_buttons:
            if tb.state == "down":
                return tb.text
        return "Moyen"

    def start(self, *_):
        name = self.name_input.text.strip()
        if not name:
            self.error.text = "Donne un nom a la partie."
            return

        app = App.get_running_app()
        app.game_state = GameState.new_random(
            name=name, difficulty=self._selected_difficulty())
        # Sauvegarde immediate : la partie apparait dans "Charger".
        app.autosave()
        self.manager.current = "game"
