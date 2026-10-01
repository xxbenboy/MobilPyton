"""
Ecran CRAFT : pour l'instant, LE JOUEUR SE PENCHE VERS LE SOL, et rien
d'autre.

L'ancien systeme de fabrication est retire, en attendant sa nouvelle forme :
plus de recettes, plus de colonnes, plus de bande de mains ni de sac. Les
recettes sont gardees de cote dans src/recettes_archive.py.

CE QUI RESTE :
- le TITRE A DEUX VOLETS en haut, pour revenir a l'inventaire (voir
  src/widgets/menu_toggle.py). Il garde sa place exacte : basculer d'un
  ecran a l'autre ne doit rien deplacer sous le doigt ;
- le bouton RETOUR, pour sortir du menu, a la hauteur ou il est dans
  l'inventaire.

UNE FOIS PENCHE, LE JOUEUR VOIT SON SOL EN CASES (voir sol_de_craft) : a
gauche ce qui traine a proximite, 4 cases sur 7 ; au centre, entre ses mains,
un plan de travail de 4 sur 4 ; a droite, plus tard, le resultat. Les objets
se glissent d'une case a l'autre et entre le sol et les mains, et la main qui
prend ou pose un objet fait le geste. En sortant, ce qui reste sur le plan
de travail retourne a la proximite.

LE FOND EST LA VRAIE SCENE DE LA CASE, vue par un joueur qui se penche
(voir src/widgets/penche.py, partage avec l'inventaire).
"""
from kivy.app import App
from kivy.uix.screenmanager import Screen
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp

from src.widgets.player_hands import PlayerHands
from src.widgets.styled_button import StyledButton
from src.widgets.responsive import (scale_font, ROW_TITLE, ROW_BODY,
                                    ROW_HANDS, ROW_HINT, ROW_BACK)
from src.widgets.menu_toggle import MenuToggle
from src.widgets.sol_de_craft import SolDeCraft
# LA CAMERA QUI SE PENCHE vit dans penche.py, partagee avec l'inventaire.
# Ses reglages sont repris ici sous leurs noms : ce qui les lisait sur cet
# ecran les y trouve toujours.
from src.widgets.penche import (Penche, adoucir, glissement, HORIZON_PENCHE,
                                GLISSE_MIN, GLISSE_MAX, GLISSE_RIVE,
                                DUREE_PENCHE, DUREE_RELEVE, FPS_CAMERA,
                                APPARITION_GRILLES)

# Largeur du bouton Retour, en part de l'ecran. Il n'occupe plus toute la
# largeur comme dans l'inventaire : il se glisse ENTRE LES DEUX AVANT-BRAS,
# qui descendent jusqu'au bas de l'ecran de part et d'autre (voir
# PlayerHands.HAND_FX). Sa hauteur, elle, est celle de l'inventaire.
LARGEUR_RETOUR = 0.20


class CraftScreen(Penche, Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = FloatLayout()

        self.construit_monde(root)

        # LE SOL EN CASES : sous les mains, qui passent devant lui. L'objet
        # qu'on glisse, lui, se dessine dans une couche tout en haut (voir
        # plus bas) : il doit passer par-dessus les mains.
        self.couche_glisse = Widget(size_hint=(1, 1),
                                    pos_hint={"x": 0, "y": 0})
        self.sol = SolDeCraft(depose=self._depose, couche=self.couche_glisse,
                              size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        self.sol.opacity = 0.0
        root.add_widget(self.sol)

        # LES MAINS DU JOUEUR, hors du monde : elles restent en place pendant
        # que le regard se baisse.
        self.hands = PlayerHands(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        root.add_widget(self.hands)

        # Voile de NUIT : assombrit tout selon l'heure, mains comprises, comme
        # dans l'ecran de jeu.
        self.night = Widget(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        with self.night.canvas:
            self._night_color = Color(0.03, 0.05, 0.12, 0.0)
            self._night_rect = Rectangle(pos=self.night.pos,
                                         size=self.night.size)

        def _sync_night(*_):
            self._night_rect.pos = self.night.pos
            self._night_rect.size = self.night.size
        self.night.bind(pos=_sync_night, size=_sync_night)
        root.add_widget(self.night)

        # LES DEUX BOUTONS, AUX PLACES QU'ILS ONT DANS L'INVENTAIRE. On garde
        # la meme colonne, aux memes mesures (gabarit de responsive.py), en
        # remplacant simplement ce qui n'existe plus par du vide : le titre
        # et le Retour tombent ainsi exactement la ou le doigt les attend.
        # Aucun panneau derriere : la colonne est transparente.
        col = BoxLayout(orientation="vertical", padding=dp(10), spacing=dp(8),
                        size_hint=(0.96, 0.96),
                        pos_hint={"center_x": 0.5, "center_y": 0.5})
        # Le titre passe par `switch` : la camera se releve AVANT qu'on ne
        # parte vers l'inventaire.
        col.add_widget(MenuToggle(self, "craft", size_hint=(1, ROW_TITLE),
                                  switch=self.partir))
        col.add_widget(Widget(size_hint=(1, ROW_BODY + ROW_HANDS + ROW_HINT)))

        bas = BoxLayout(orientation="horizontal", size_hint=(1, ROW_BACK))
        marge = (1.0 - LARGEUR_RETOUR) / 2.0
        bas.add_widget(Widget(size_hint_x=marge))
        back = scale_font(StyledButton(text="Retour",
                                       size_hint_x=LARGEUR_RETOUR), 0.022)
        back.bind(on_release=lambda *_: self.partir("game"))
        bas.add_widget(back)
        bas.add_widget(Widget(size_hint_x=marge))
        col.add_widget(bas)
        root.add_widget(col)
        root.add_widget(self.couche_glisse)

        self.add_widget(root)

    # ------------------------------------------------------------------ #
    def on_pre_enter(self):
        state = App.get_running_app().game_state
        self.prepare_penche(state)
        if state is None:
            return
        # Un plan de travail qui ne serait pas vide a l'arrivee (une partie
        # interrompue pendant qu'on s'en servait) est d'abord rendu a la
        # proximite : on arrive toujours devant un plan libre.
        if state.vide_le_centre():
            App.get_running_app().autosave()
        self.refresh()

    def on_enter(self):
        # Les mains respirent, comme dans l'ecran de jeu.
        self.hands.start_breathing()
        # Et le joueur baisse les yeux (s'il ne l'est pas deja).
        self.lance_penche()

    def on_leave(self):
        self.hands.stop_breathing()
        self.quitte_penche()
        self.sol.annule()
        self.sol.actif = False
        # CE QUI RESTE SUR LE PLAN DE TRAVAIL RETOURNE A LA PROXIMITE, quelle
        # que soit la sortie -- Retour ou le titre vers l'inventaire. Ces
        # objets n'ont jamais quitte le sol (voir GameState.sol_en_cases) :
        # l'inventaire les montrait deja ; ils reprennent simplement une case
        # de la proximite.
        state = App.get_running_app().game_state
        if state is not None and state.vide_le_centre():
            App.get_running_app().autosave()

    def refresh(self):
        """Les mains montrent ce qu'elles tiennent, gants compris, et le sol
        ce qui y est pose."""
        state = App.get_running_app().game_state
        if state is None:
            return
        self.hands.set_items(state.hands[0], state.hands[1])
        self.hands.set_glove(state.equipment.get("gant"))
        self.sol.montre(state.sol_en_cases(), state.hands)

    # -- les depots ----------------------------------------------------- #
    def _depose(self, source, cible):
        """Un objet lache par le doigt. `source` et `cible` sont des couples
        ("case", "G:3") ou ("main", 0). Rend True si quelque chose a bouge.

        Les regles sont celles de l'inventaire : une main ne tient qu'un
        objet et refuse d'en prendre un second ; poser sur une case prise par
        un autre objet est refuse depuis une main (elle ne peut pas reprendre
        une pile en echange), mais deux piles du sol, elles, echangent leurs
        places."""
        state = App.get_running_app().game_state
        if state is None:
            return False
        (sorte_s, s), (sorte_c, c) = source, cible
        geste = None
        if sorte_s == "case" and sorte_c == "case":
            fait = state.deplace_au_sol(s, c)
        elif sorte_s == "case" and sorte_c == "main":
            fait = state.sol_vers_main(s, c)
            geste = c
        elif sorte_s == "main" and sorte_c == "case":
            fait = state.main_vers_sol(s, c)
            geste = s
        elif sorte_s == "main" and sorte_c == "main":
            fait = s != c and state.echange_mains()
        else:
            fait = False
        if not fait:
            return False
        App.get_running_app().autosave()
        self.refresh()
        # LA MAIN QUI A PRIS OU POSE fait le geste, apres le redessin : elle
        # plonge vers le sol avec l'objet qu'elle y prend, ou sans celui
        # qu'elle vient d'y laisser.
        if geste is not None:
            self.hands.geste(geste)
        return True
