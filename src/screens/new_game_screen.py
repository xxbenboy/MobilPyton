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
from src.save_manager import MAX_SAVES
from src.widgets.animated_background import AnimatedBackground
from src.widgets.responsive import scale_font

# Longueur maximale du nom d'une partie.
MAX_NAME_LENGTH = 16


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
        self.name_input = TextInput(multiline=False, size_hint=(1, 0.12),
                                    padding=(10, 6))
        # Nom limite a 16 caracteres, verification en direct du nom (unique),
        # et police qui suit la HAUTEUR de la barre.
        self.name_input.bind(text=self._on_name_change, height=self._fit_font)
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

        self.start_btn = scale_font(Button(text="Commencer",
                           size_hint=(1, 0.18)), 0.024)
        self.start_btn.bind(on_release=self.start)
        column.add_widget(self.start_btn)

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
        self.start_btn.disabled = False
        for tb in self.diff_buttons:
            tb.state = "down" if tb.text == "Moyen" else "normal"

    def _on_name_change(self, instance, value):
        # Coupe le nom a 16 caracteres maximum.
        if len(value) > MAX_NAME_LENGTH:
            instance.text = value[:MAX_NAME_LENGTH]
            return  # le texte coupe redeclenche cet evenement
        self._validate_name()

    def _validate_name(self):
        # Empeche d'utiliser un nom deja pris : avertit + desactive "Commencer".
        name = self.name_input.text.strip()
        if name and App.get_running_app().save_manager.exists(name):
            self.error.text = "Ce nom existe deja.\nChoisis-en un autre."
            self.start_btn.disabled = True
        else:
            if self.error.text.startswith("Ce nom existe"):
                self.error.text = ""
            self.start_btn.disabled = False

    def _fit_font(self, instance, height):
        # La police occupe ~55 % de la hauteur de la barre.
        instance.font_size = max(10, height * 0.55)

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
        # Nom deja utilise : interdit (les noms doivent etre uniques).
        if app.save_manager.exists(name):
            self.error.text = "Ce nom existe deja.\nChoisis-en un autre."
            self.start_btn.disabled = True
            return
        # Limite a MAX_SAVES parties.
        if app.save_manager.is_full():
            self.error.text = (f"Maximum {MAX_SAVES} parties.\n"
                               "Supprime-en une dans 'Charger'.")
            return

        app.game_state = GameState.new_random(
            name=name, difficulty=self._selected_difficulty())
        # Sauvegarde immediate : la partie apparait dans "Charger".
        app.autosave()
        self.manager.current = "game"
