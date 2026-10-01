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

LE FOND EST LA VRAIE SCENE DE LA CASE, celle de l'ecran de jeu, elements et
proportions compris. Seule la CAMERA bouge : en entrant, elle glisse vers le
bas, comme un regard qui se baisse vers le sol, et la scene entiere -- ciel
et decor ensemble -- monte a l'ecran sans qu'un seul element change de
taille ou de place par rapport au joueur. Ses mains, elles, restent ou elles
sont : elles sont attachees a lui, pas au paysage. En sortant, la camera se
releve avant de quitter l'ecran.
"""
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.screenmanager import Screen
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget
from kivy.graphics import Color, Rectangle, PushMatrix, PopMatrix, Translate
from kivy.metrics import dp

from src.widgets import daylight
from src.widgets.animated_background import AnimatedBackground, night_darkness
from src.widgets.zone_scenery import ZoneScenery
from src.widgets.player_hands import PlayerHands
from src.widgets.styled_button import StyledButton
from src.widgets.responsive import (scale_font, ROW_TITLE, ROW_BODY,
                                    ROW_HANDS, ROW_HINT, ROW_BACK)
from src.widgets.menu_toggle import MenuToggle
from src.widgets.sol_de_craft import SolDeCraft

# Largeur du bouton Retour, en part de l'ecran. Il n'occupe plus toute la
# largeur comme dans l'inventaire : il se glisse ENTRE LES DEUX AVANT-BRAS,
# qui descendent jusqu'au bas de l'ecran de part et d'autre (voir
# PlayerHands.HAND_FX). Sa hauteur, elle, est celle de l'inventaire.
LARGEUR_RETOUR = 0.20

# --- LA CAMERA QUI SE PENCHE ----------------------------------------- #
# Ou le regard amene l'horizon, en part de la hauteur d'ecran. La scene de
# jeu le pose entre 0,47 (foret) et 0,75 (lac) : baisser les yeux le fait
# monter tout en haut, et le sol occupe alors presque tout l'ecran. Il etait
# a 0,88 ; le joueur trouvait qu'on ne se penchait pas assez.
#
# LE GLISSEMENT EST DONC PROPRE A CHAQUE ZONE : 0,46 de l'ecran en foret,
# 0,22 au bord du lac, dont l'horizon est deja haut. Un glissement
# unique aurait envoye la berge d'en face hors de l'ecran, ou laisse la
# foret a mi-hauteur.
HORIZON_PENCHE = 0.93
# Bornes du glissement, en part de la hauteur. Le haut est aussi ce qui
# decide du sol prepare sous l'ecran (voir ZoneScenery.sous_sol).
#
# LE BAS NE DESCEND PAS SOUS 0,22 : au bord du lac, la formule donnait bien
# moins, et on sentait a peine le joueur se pencher. La berge d'en face y
# remonte au ras du haut de l'ecran -- ses cimes le touchent -- mais le
# geste se voit.
GLISSE_MIN = 0.22
GLISSE_MAX = 0.46
# AU BORD DU LAC, LE REGARD DESCEND JUSQU'A LA PLAGE. Les grilles du sol
# (voir sol_de_craft) montent jusqu'a 0,55 de l'ecran ; avec le glissement
# de 0,22, tout le plan de travail et le fond de la proximite tombaient sur
# l'eau -- des objets poses sur le lac. Le sable sec de la rive s'arrete a
# 0,108 de la hauteur de la scene (la ou l'eau commence a laper, dans
# rive_B) : a 0,42, il monte jusqu'a 0,53 de l'ecran, et les deux grilles
# reposent sur la greve. La berge d'en face sort alors par le haut : a la
# rive, se pencher, c'est regarder la plage.
GLISSE_RIVE = 0.42
# Durees du mouvement, en secondes. Se pencher prend un peu de temps ; se
# relever est plus vif, parce que c'est ce qui precede un changement
# d'ecran, et que personne n'aime attendre un bouton.
DUREE_PENCHE = 0.85
DUREE_RELEVE = 0.35
# Images par seconde de l'animation : elle ne deplace qu'une translation,
# c'est la carte graphique qui fait le reste.
FPS_CAMERA = 60.0
# Les grilles du sol apparaissent a la FIN du mouvement, en fondu, sur ce
# dernier bout de la course : elles sont posees sur le sol tel qu'on le voit
# penche, et glisser avec lui pendant le mouvement les aurait fait flotter.
# Elles ne repondent au doigt qu'une fois la camera arrivee.
APPARITION_GRILLES = 0.25


def adoucir(p):
    """Le trajet de la camera : depart et arrivee en douceur.

    Un mouvement a vitesse constante demarre et s'arrete d'un coup sec, ce
    qu'un cou ne fait pas. Cette courbe (le "smootherstep") part a vitesse
    nulle, accelere, puis se pose a vitesse nulle, sans a-coup d'acceleration
    ni au depart ni a l'arrivee."""
    p = max(0.0, min(1.0, p))
    return p * p * p * (p * (p * 6.0 - 15.0) + 10.0)


def glissement(crete, zone=None):
    """De combien la camera fait monter la scene, en part de la hauteur,
    pour amener une crete a `crete` jusqu'a HORIZON_PENCHE -- ou, au bord du
    lac, pour amener la plage sous les grilles (voir GLISSE_RIVE)."""
    if zone == "Lac":
        return GLISSE_RIVE
    return max(GLISSE_MIN, min(GLISSE_MAX, HORIZON_PENCHE - crete))


class CraftScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        root = FloatLayout()

        # LE MONDE : le ciel et la scene, qui bougent ENSEMBLE quand la
        # camera se penche. Une seule translation pour les deux, posee autour
        # d'eux : le decor dessine avec son propre shader (voir ZoneScenery)
        # reprend la matrice de son parent, il suit donc aussi.
        self.monde = FloatLayout(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        with self.monde.canvas.before:
            PushMatrix()
            self._camera = Translate(0, 0, 0)
        with self.monde.canvas.after:
            PopMatrix()
        self.background = AnimatedBackground(time_scale=0, size_hint=(1, 1),
                                             pos_hint={"x": 0, "y": 0})
        self.monde.add_widget(self.background)
        # La VRAIE scene de la case, avec du sol prepare sous le bas de
        # l'ecran : c'est celui que la camera decouvre en se penchant.
        self.scenery = ZoneScenery(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        self.scenery.sous_sol = GLISSE_MAX + 0.02
        self.monde.add_widget(self.scenery)
        root.add_widget(self.monde)

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

        # L'etat de la camera : ou elle en est (0 = regard du jeu, 1 =
        # penchee), d'ou elle part, ou elle va, et l'ecran a ouvrir une fois
        # relevee.
        self._pente = 0.0
        self._depart = 0.0
        self._cible = 0.0
        self._duree = DUREE_PENCHE
        self._ecoule = 0.0
        self._apres = None
        self._horloge = None
        self._glisse = GLISSE_MIN
        # Une fenetre qui change de taille garde son regard : la translation
        # se compte en part de la hauteur.
        self.bind(size=lambda *_: self._place_camera())

    # ------------------------------------------------------------------ #
    def on_pre_enter(self):
        state = App.get_running_app().game_state
        # On arrive TOUJOURS avec le regard du jeu : la scene est d'abord
        # exactement celle qu'on vient de quitter, puis le joueur se penche.
        self._arrete_camera()
        self._pente = 0.0
        self._apres = None
        self._place_camera()
        if state is None:
            return
        self.background.set_seconds(state.time_seconds)
        self.background.set_weather(state.effective_weather())
        self.scenery.set_wind(state.effective_weather())
        # Le voile de nuit prend AUSSI la teinte de l'heure, et le decor suit
        # le soleil (couleur de la lumiere, ombres portees).
        self._night_color.rgb = daylight.veil_color(state.time_seconds)
        self._night_color.a = night_darkness(state.time_seconds)
        self.scenery.set_daylight(state.time_seconds)
        # LA SCENE DE LA CASE, la meme que dans l'ecran de jeu (voir
        # ZoneScenery.montre_la_case).
        self.scenery.montre_la_case(state)
        self.background.set_horizon(self.scenery.hauteur_horizon())
        self.scenery.set_brume(self.background.couleur_ciel(
            self.scenery.hauteur_horizon()))
        self._glisse = glissement(self.scenery.hauteur_horizon(),
                                  self.scenery._zone)
        # Un plan de travail qui ne serait pas vide a l'arrivee (une partie
        # interrompue pendant qu'on s'en servait) est d'abord rendu a la
        # proximite : on arrive toujours devant un plan libre.
        if state.vide_le_centre():
            App.get_running_app().autosave()
        self.refresh()

    def on_enter(self):
        # Les mains respirent, comme dans l'ecran de jeu.
        self.hands.start_breathing()
        # Et le joueur baisse les yeux.
        self._anime_vers(1.0, DUREE_PENCHE)

    def on_leave(self):
        self.hands.stop_breathing()
        self._arrete_camera()
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

    # -- la camera ------------------------------------------------------ #
    def partir(self, ecran):
        """Se relever, PUIS ouvrir `ecran`. Un second toucher pendant le
        mouvement ne fait que changer la destination : on ne se releve pas
        deux fois."""
        self._apres = ecran
        # Plus de glisser des qu'on se releve : les grilles s'effacent.
        self.sol.annule()
        self.sol.actif = False
        if self._horloge is not None and self._cible == 0.0:
            return
        self._anime_vers(0.0, DUREE_RELEVE)

    def _anime_vers(self, cible, duree):
        self._depart = self._pente
        self._cible = float(cible)
        self._ecoule = 0.0
        # Partir d'une position intermediaire (un demi-mouvement interrompu)
        # prend la part de temps qui reste, pas la duree entiere.
        self._duree = max(1e-3, duree * abs(self._cible - self._depart))
        if self._horloge is None:
            self._horloge = Clock.schedule_interval(self._tick_camera,
                                                    1.0 / FPS_CAMERA)

    def _tick_camera(self, dt):
        # Un ralentissement (reveil, chargement) ne doit pas faire sauter la
        # camera : le pas est plafonne.
        self._ecoule += min(dt, 0.1)
        p = self._ecoule / self._duree
        self._pente = self._depart + (self._cible - self._depart) * adoucir(p)
        self._place_camera()
        if p < 1.0:
            return
        self._arrete_camera()
        if self._cible == 0.0 and self._apres and self.manager is not None:
            ecran, self._apres = self._apres, None
            self.manager.current = ecran

    def _arrete_camera(self):
        if self._horloge is not None:
            self._horloge.cancel()
            self._horloge = None

    def _place_camera(self):
        """La scene monte a l'ecran d'autant que la camera se penche, et les
        grilles du sol apparaissent a la fin du mouvement."""
        self._camera.y = self._pente * self._glisse * self.height
        debut = 1.0 - APPARITION_GRILLES
        self.sol.opacity = max(0.0, min(1.0, (self._pente - debut)
                                        / APPARITION_GRILLES))
        # Le doigt n'agit que camera arrivee ET tant qu'on ne repart pas.
        self.sol.actif = self._pente >= 0.999 and not (
            self._horloge is not None and self._cible == 0.0)
