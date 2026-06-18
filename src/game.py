"""
Application principale.

Le ScreenManager gere la navigation entre les ecrans (menu, jeu...).

C'est aussi ici qu'on centralise la SAUVEGARDE :
- `self.save_manager` : lecture/ecriture du fichier de sauvegarde.
- `self.game_state`   : la partie en cours (ou None si on est au menu sans
                        partie chargee). Les ecrans y accedent via
                        `App.get_running_app().game_state`.
- `autosave()`        : sauvegarde la partie en cours, si elle existe.

Sauvegarde "juste avant la fermeture" : on branche `autosave()` sur les
evenements de fin de l'app :
- `on_request_close` (fermeture de la fenetre sur PC),
- `on_stop`          (arret de l'application),
- `on_pause`         (passage en arriere-plan sur Android).
"""
from kivy.app import App
from kivy.core.window import Window
from kivy.uix.screenmanager import ScreenManager, FadeTransition

from src.save_manager import SaveManager
from src.audio_manager import AudioManager
from src.screens.menu_screen import MenuScreen
from src.screens.new_game_screen import NewGameScreen
from src.screens.load_screen import LoadScreen
from src.screens.settings_screen import SettingsScreen
from src.screens.stats_screen import StatsScreen
from src.screens.game_screen import GameScreen
from src.screens.map_screen import MapScreen
from src.screens.craft_screen import CraftScreen


class MobilPytonApp(App):
    title = "MobilPyton"

    def build(self):
        # `user_data_dir` est un dossier accessible en ecriture, propre a
        # l'app (gere correctement sur Android comme sur PC).
        self.save_manager = SaveManager(self.user_data_dir)
        # Reglages audio (volume, son coupe), sauvegardes dans user_data_dir.
        self.audio_manager = AudioManager(self.user_data_dir)
        self.game_state = None

        sm = ScreenManager(transition=FadeTransition())
        sm.add_widget(MenuScreen(name="menu"))
        sm.add_widget(NewGameScreen(name="newgame"))
        sm.add_widget(LoadScreen(name="load"))
        sm.add_widget(SettingsScreen(name="settings"))
        sm.add_widget(StatsScreen(name="stats"))
        sm.add_widget(GameScreen(name="game"))
        sm.add_widget(MapScreen(name="map"))
        sm.add_widget(CraftScreen(name="craft"))

        # Sauvegarde juste avant la fermeture de la fenetre (PC).
        Window.bind(on_request_close=self._on_request_close)
        return sm

    # ------------------------------------------------------------------ #
    # Sauvegarde
    # ------------------------------------------------------------------ #
    def autosave(self):
        """Sauvegarde la partie en cours s'il y en a une."""
        if self.game_state is not None:
            self.save_manager.save(self.game_state)

    def _on_request_close(self, *args, **kwargs):
        self.autosave()
        return False  # False = on autorise la fermeture a continuer.

    def on_stop(self):
        # Appele quand l'application s'arrete (filet de securite).
        self.autosave()

    def on_pause(self):
        # Android : appele quand l'app passe en arriere-plan. On sauvegarde
        # et on renvoie True pour que l'app reste en memoire.
        self.autosave()
        return True
