"""
Ecran "Parametres".

Pour l'instant, ne sert qu'a regler l'AUDIO de l'application :
- un curseur pour le volume general,
- un interrupteur pour couper / retablir le son.

Les reglages sont geres et sauvegardes par l'AudioManager de l'app
(App.get_running_app().audio_manager) : ils sont donc conserves d'une
session a l'autre.

Visuel coherent avec les autres ecrans de menu : fond anime (MenuBackdrop),
panneau translucide arrondi, titre dore, et boutons stylises.
"""
from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.slider import Slider
from kivy.uix.switch import Switch
from kivy.graphics import Color, RoundedRectangle
from kivy.metrics import dp

from src.widgets.menu_backdrop import MenuBackdrop
from src.widgets.styled_button import StyledButton
from src.widgets.responsive import scale_font
from src.widgets.fonts import title_font, ui_font


class SettingsScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # Vrai pendant la synchro des widgets : evite que la maj des widgets
        # depuis les reglages enregistres ne reecrive ces memes reglages.
        self._loading = False

        root = FloatLayout()
        root.add_widget(MenuBackdrop())

        content = BoxLayout(orientation="vertical",
                            padding=dp(26), spacing=dp(14),
                            size_hint=(0.6, 0.78),
                            pos_hint={"center_x": 0.5, "center_y": 0.5})

        # Panneau translucide arrondi derriere le contenu (comme le menu).
        with content.canvas.before:
            Color(0, 0, 0, 0.30)
            self._panel = RoundedRectangle(radius=[dp(22)])

        def _sync_panel(*_):
            self._panel.pos = content.pos
            self._panel.size = content.size
        content.bind(pos=_sync_panel, size=_sync_panel)

        # Titre.
        content.add_widget(scale_font(Label(
            text="Parametres", bold=True,
            font_name=title_font(),
            color=(0.96, 0.82, 0.45, 1),
            size_hint=(1, 0.2)), 0.05))

        # --- Section Audio -------------------------------------------- #
        content.add_widget(scale_font(Label(
            text="Audio", bold=True, halign="center",
            font_name=ui_font(),
            color=(0.82, 0.86, 0.92, 1), size_hint=(1, 0.1)), 0.024))

        # Ligne "Volume" : libelle + curseur + pourcentage.
        vol_row = BoxLayout(orientation="horizontal", spacing=dp(10),
                            size_hint=(1, 0.16))
        vol_row.add_widget(scale_font(Label(
            text="Volume", halign="left", font_name=ui_font(),
            size_hint_x=0.3), 0.02))
        self.volume_slider = Slider(min=0, max=100, value=80,
                                    step=1, size_hint_x=0.5)
        self.volume_slider.bind(value=self._on_volume_change)
        vol_row.add_widget(self.volume_slider)
        self.volume_label = scale_font(Label(
            text="80%", font_name=ui_font(), size_hint_x=0.2), 0.02)
        vol_row.add_widget(self.volume_label)
        content.add_widget(vol_row)

        # Ligne "Couper le son" : libelle + interrupteur.
        mute_row = BoxLayout(orientation="horizontal", spacing=dp(10),
                             size_hint=(1, 0.16))
        mute_row.add_widget(scale_font(Label(
            text="Couper le son", halign="left", font_name=ui_font(),
            size_hint_x=0.7), 0.02))
        self.mute_switch = Switch(active=False, size_hint_x=0.3)
        self.mute_switch.bind(active=self._on_mute_toggle)
        mute_row.add_widget(self.mute_switch)
        content.add_widget(mute_row)

        # --- Retour --------------------------------------------------- #
        back_btn = scale_font(StyledButton(text="Retour",
                              font_name=ui_font(), size_hint=(1, 0.16)), 0.024)
        back_btn.bind(on_release=lambda *_: setattr(self.manager, "current",
                                                    "menu"))
        content.add_widget(back_btn)

        root.add_widget(content)
        self.add_widget(root)

    def on_pre_enter(self):
        """Synchronise les widgets avec les reglages enregistres."""
        audio = App.get_running_app().audio_manager
        self._loading = True
        self.volume_slider.value = round(audio.volume * 100)
        self.volume_label.text = f"{int(round(audio.volume * 100))}%"
        self.mute_switch.active = audio.muted
        self._loading = False

    def _on_volume_change(self, _slider, value):
        self.volume_label.text = f"{int(value)}%"
        if self._loading:
            return
        App.get_running_app().audio_manager.set_volume(value / 100.0)

    def _on_mute_toggle(self, _switch, value):
        if self._loading:
            return
        App.get_running_app().audio_manager.set_muted(value)
