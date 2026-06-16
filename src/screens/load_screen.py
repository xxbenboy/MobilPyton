"""
Ecran "Charger".

Affiche TOUTES les sauvegardes existantes (la plus recente en haut). Pour
chaque partie :
- un bouton large pour la charger et reprendre,
- un bouton "X" pour la supprimer.

La liste est reconstruite a chaque arrivee sur l'ecran (on_pre_enter) pour
refleter les sauvegardes du moment.
"""
from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView

from src.save_manager import MAX_SAVES
from src.widgets.animated_background import AnimatedBackground
from src.widgets.responsive import scale_font, font_for


class LoadScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        root = FloatLayout()
        root.add_widget(AnimatedBackground(size_hint=(1, 1),
                                           pos_hint={"x": 0, "y": 0}))

        column = BoxLayout(orientation="vertical", padding=20, spacing=10,
                           size_hint=(0.92, 0.9),
                           pos_hint={"center_x": 0.5, "center_y": 0.5})

        # Titre + compteur de parties (mis a jour dans refresh_list).
        self.title = scale_font(Label(text="Charger une partie",
                                bold=True, size_hint=(1, 0.1)), 0.032)
        column.add_widget(self.title)

        # Message affiche quand il n'y a aucune sauvegarde.
        self.empty_label = scale_font(Label(
            text="Aucune sauvegarde pour l'instant.",
            color=(0.85, 0.85, 0.85, 1),
            size_hint=(1, 0.1)), 0.018)
        column.add_widget(self.empty_label)

        # Liste defilante des sauvegardes.
        scroll = ScrollView(size_hint=(1, 0.66))
        self.list_box = BoxLayout(orientation="vertical", spacing=8,
                                  size_hint_y=None, padding=(0, 4))
        # La hauteur du conteneur s'ajuste a son contenu (pour le scroll).
        self.list_box.bind(minimum_height=self.list_box.setter("height"))
        scroll.add_widget(self.list_box)
        column.add_widget(scroll)

        back_btn = Button(text="Retour", font_size="15sp", size_hint=(1, 0.1))
        back_btn.bind(on_release=lambda *_: setattr(self.manager, "current",
                                                    "menu"))
        column.add_widget(back_btn)

        root.add_widget(column)
        self.add_widget(root)

    def on_pre_enter(self):
        self.refresh_list()

    def refresh_list(self):
        self.list_box.clear_widgets()
        saves = App.get_running_app().save_manager.list_saves()
        self.empty_label.opacity = 0 if saves else 1
        # Compteur de parties (ex. "Charger  3/5").
        self.title.text = f"Charger  {len(saves)}/{MAX_SAVES}"

        # Hauteur des lignes et tailles de texte proportionnelles a l'ecran.
        row_height = font_for(0.09, minimum=48)
        detail_size = int(font_for(0.015, minimum=10))

        for save in saves:
            row = BoxLayout(orientation="horizontal", spacing=6,
                            size_hint_y=None, height=row_height)

            load_btn = scale_font(Button(
                text=f"{save['name']}\n[size={detail_size}]{save['difficulty']} - "
                     f"Jour {save['day']} {save['clock']}[/size]",
                markup=True, halign="center",
                size_hint_x=0.8), 0.02)
            load_btn.bind(on_release=lambda _w, n=save["name"]: self.load(n))
            row.add_widget(load_btn)

            del_btn = scale_font(Button(text="X", size_hint_x=0.2,
                             background_color=(0.7, 0.2, 0.2, 1)), 0.024)
            del_btn.bind(on_release=lambda _w, n=save["name"]: self.delete(n))
            row.add_widget(del_btn)

            self.list_box.add_widget(row)

    def load(self, name):
        app = App.get_running_app()
        state = app.save_manager.load(name)
        if state is None:
            # Sauvegarde devenue illisible : on rafraichit la liste.
            self.refresh_list()
            return
        app.game_state = state
        self.manager.current = "game"

    def delete(self, name):
        App.get_running_app().save_manager.delete(name)
        self.refresh_list()
