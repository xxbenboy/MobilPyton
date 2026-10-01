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
gauche ce qui traine a proximite, 5 cases sur 5 ; au centre, entre ses mains,
un plan de travail de 4 sur 4 ; a droite, plus tard, le resultat. Les objets
se glissent d'une case a l'autre et entre le sol et les mains, et la main qui
prend ou pose un objet fait le geste. En sortant, ce qui reste sur le plan
de travail retourne a la proximite.

LE FOND EST LA VRAIE SCENE DE LA CASE, vue par un joueur qui se penche
(voir src/widgets/penche.py, partage avec l'inventaire).

ASSEMBLER : des qu'un objet est pose sur le plan de travail, un bouton
Assembler apparait entre les mains, juste au-dessus de Retour. Il rapproche
la vue du plan de travail (voir src/widgets/assemblage.py). La, seuls deux
boutons restent : Annuler, a la place d'Assembler, et Assembler juste
au-dessus. Annuler recule la vue et remet chaque objet dans sa case, et ce
que tenaient les mains reapparait : on revient exactement a l'etat d'avant.
"""
from kivy.app import App
from kivy.clock import Clock
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
from src.widgets.assemblage import Assemblage, Loupe, DUREE_ZOOM
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

        # LA LOUPE : le decor, le sol et les objets du plan de travail y
        # zooment ensemble quand on assemble. Les mains n'y sont pas.
        self.loupe = Loupe(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        root.add_widget(self.loupe)
        self.construit_monde(self.loupe)

        # LE SOL EN CASES : sous les mains, qui passent devant lui. L'objet
        # qu'on glisse, lui, se dessine dans une couche tout en haut (voir
        # plus bas) : il doit passer par-dessus les mains.
        self.couche_glisse = Widget(size_hint=(1, 1),
                                    pos_hint={"x": 0, "y": 0})
        self.sol = SolDeCraft(depose=self._depose, couche=self.couche_glisse,
                              size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        self.sol.opacity = 0.0
        self.loupe.add_widget(self.sol)

        # LES MAINS DU JOUEUR, hors du monde : elles restent en place pendant
        # que le regard se baisse, et ne zooment pas.
        self.hands = PlayerHands(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})

        # LA VUE D'ASSEMBLAGE : les objets libres dans la loupe, et ceux que
        # portent les mains dans une couche au-dessus d'elles.
        self.couche_portes = Widget(size_hint=(1, 1),
                                    pos_hint={"x": 0, "y": 0})
        self.assemblage = Assemblage(mains=self.hands,
                                     couche=self.couche_portes,
                                     size_hint=(1, 1),
                                     pos_hint={"x": 0, "y": 0})
        self.loupe.add_widget(self.assemblage)
        root.add_widget(self.hands)
        root.add_widget(self.couche_portes)
        # Ou en est le rapprochement : "sol" (vue normale), "entre", "zoom"
        # ou "sort" ; son avancement (0 a 1) et son horloge.
        self._mode = "sol"
        self._zoom = 0.0
        self._zoom_depart = 0.0
        self._zoom_cible = 0.0
        self._zoom_ecoule = 0.0
        self._zoom_horloge = None

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
        # parte vers l'inventaire. Il disparait dans la vue d'assemblage.
        self._rang_titre = BoxLayout(orientation="horizontal",
                                     size_hint=(1, ROW_TITLE))
        self._titre = MenuToggle(self, "craft", size_hint=(1, 1),
                                 switch=self.partir)
        self._rang_titre.add_widget(self._titre)
        col.add_widget(self._rang_titre)

        # Le milieu, vide, avec en bas les deux rangs des boutons
        # d'assemblage, de la hauteur de Retour. Il est a part pour que
        # le titre et Retour gardent exactement leurs places.
        milieu = BoxLayout(orientation="vertical", spacing=dp(8),
                           size_hint=(1, ROW_BODY + ROW_HANDS + ROW_HINT))
        milieu.add_widget(Widget(size_hint=(1, ROW_BODY + ROW_HANDS
                                            + ROW_HINT - 2 * ROW_BACK)))
        self._rang_haut = BoxLayout(orientation="horizontal",
                                    size_hint=(1, ROW_BACK))
        self._rang_bas = BoxLayout(orientation="horizontal",
                                   size_hint=(1, ROW_BACK))
        milieu.add_widget(self._rang_haut)
        milieu.add_widget(self._rang_bas)
        col.add_widget(milieu)

        self._rang_retour = BoxLayout(orientation="horizontal",
                                      size_hint=(1, ROW_BACK))
        self._retour = scale_font(StyledButton(text="Retour",
                                               size_hint_x=LARGEUR_RETOUR),
                                  0.022)
        self._retour.bind(on_release=lambda *_: self.partir("game"))
        col.add_widget(self._rang_retour)

        self._assembler = scale_font(StyledButton(
            text="Assembler", size_hint_x=LARGEUR_RETOUR), 0.022)
        self._assembler.bind(on_release=self._sur_assembler)
        self._annuler = scale_font(StyledButton(
            text="Annuler", size_hint_x=LARGEUR_RETOUR), 0.022)
        self._annuler.bind(on_release=lambda *_: self.annule_assemblage())
        self._garnit(self._rang_retour, self._retour)
        self._garnit(self._rang_haut, None)
        self._garnit(self._rang_bas, None)
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
        if self._mode != "sol":
            self._fin_assemblage()
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
        cases = state.sol_en_cases()
        # Dans la vue d'assemblage, ce que tiennent les mains n'est pas
        # montre ; il reapparait en la quittant.
        if self._mode == "sol":
            self.hands.set_items(state.hands[0], state.hands[1])
        else:
            self.hands.set_items(None, None)
        self.hands.set_glove(state.equipment.get("gant"))
        self.sol.montre(cases, state.hands)
        if self._mode == "sol":
            plan = any(k.startswith("C:") for k in cases)
            self._garnit(self._rang_bas, self._assembler if plan else None)

    # -- les boutons ---------------------------------------------------- #
    @staticmethod
    def _garnit(rang, bouton, largeur=LARGEUR_RETOUR):
        """Un rang de bouton : `bouton` au milieu, entre les avant-bras, ou
        rien du tout (un bouton cache ne doit pas prendre les touchers)."""
        rang.clear_widgets()
        if bouton is None:
            rang.add_widget(Widget(size_hint_x=1.0))
            return
        if bouton.parent is not None:
            bouton.parent.remove_widget(bouton)
        if largeur >= 1.0:
            rang.add_widget(bouton)
            return
        marge = (1.0 - largeur) / 2.0
        rang.add_widget(Widget(size_hint_x=marge))
        rang.add_widget(bouton)
        rang.add_widget(Widget(size_hint_x=marge))

    def _sur_assembler(self, *_):
        # Dans la vue d'assemblage, il ne fait rien pour l'instant.
        if self._mode == "sol":
            self.assemble()

    # -- la vue d'assemblage -------------------------------------------- #
    def assemble(self):
        """Rapproche la vue du plan de travail (voir assemblage.py)."""
        state = App.get_running_app().game_state
        if state is None or self._mode != "sol" or self._pente < 0.999:
            return False
        objets = []
        for cle, (nom, _n) in sorted(state.sol_en_cases().items()):
            if cle.startswith("C:"):
                x, y = self.sol.centre.centre(cle)
                objets.append((nom, (x - self.sol.x) / self.sol.width,
                               (y - self.sol.y) / self.sol.height))
        if not objets:
            return False
        self.sol.annule()
        self.sol.actif = False
        self.assemblage.charge(objets)
        self.hands.set_items(None, None)
        # Seuls Annuler, a la place d'Assembler, et Assembler au-dessus.
        self._garnit(self._rang_titre, None)
        self._garnit(self._rang_retour, None)
        self._garnit(self._rang_bas, self._annuler)
        self._garnit(self._rang_haut, self._assembler)
        self._mode = "entre"
        self._anime_zoom(1.0)
        return True

    def annule_assemblage(self):
        """Recule la vue : chaque objet regagne sa case, et les mains ce
        qu'elles tenaient. Rien n'a change dans la partie."""
        if self._mode not in ("entre", "zoom"):
            return False
        self.assemblage.actif = False
        self.assemblage.lache_tout()
        self.assemblage.fige_depart()
        self._mode = "sort"
        self._anime_zoom(0.0)
        return True

    def _anime_zoom(self, cible):
        self._zoom_depart = self._zoom
        self._zoom_cible = float(cible)
        self._zoom_ecoule = 0.0
        if self._zoom_horloge is None:
            self._zoom_horloge = Clock.schedule_interval(self._tick_zoom,
                                                         1.0 / FPS_CAMERA)

    def _tick_zoom(self, dt):
        self._zoom_ecoule += min(dt, 0.1)
        duree = max(1e-3, DUREE_ZOOM * abs(self._zoom_cible
                                           - self._zoom_depart))
        p = min(1.0, self._zoom_ecoule / duree)
        self._zoom = self._zoom_depart + (self._zoom_cible
                                          - self._zoom_depart) * p
        self._applique_zoom()
        if self._mode == "sort" and self._zoom_depart > 0.0:
            self.assemblage.ramene(adoucir(1.0 - self._zoom
                                           / self._zoom_depart))
        if p < 1.0:
            return
        self._arrete_zoom()
        if self._zoom_cible >= 1.0:
            self._mode = "zoom"
            self.assemblage.actif = True
        else:
            self._fin_assemblage()

    def _applique_zoom(self):
        e = adoucir(self._zoom)
        self.loupe.regle(e)
        # Les grilles s'effacent en se rapprochant, et reviennent en
        # reculant ; les objets, eux, restent (voir Assemblage).
        self.sol.opacity = 1.0 - e
        self.assemblage.opacity = 1.0 if self._mode != "sol" else 0.0

    def _arrete_zoom(self):
        if self._zoom_horloge is not None:
            self._zoom_horloge.cancel()
            self._zoom_horloge = None

    def _fin_assemblage(self):
        """Retour a la vue normale, tout de suite."""
        self._arrete_zoom()
        self._mode = "sol"
        self._zoom = 0.0
        self.loupe.regle(0.0)
        self.assemblage.actif = False
        self.assemblage.vide()
        self.assemblage.opacity = 0.0
        self._garnit(self._rang_titre, self._titre, 1.0)
        self._garnit(self._rang_retour, self._retour)
        self._garnit(self._rang_haut, None)
        self._garnit(self._rang_bas, None)
        self._place_camera()
        self.refresh()

    def _sur_camera(self):
        # Pendant l'assemblage, la camera ne rend pas les grilles.
        if getattr(self, "_mode", "sol") != "sol":
            self.sol.opacity = 1.0 - adoucir(self._zoom)
            self.sol.actif = False

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
