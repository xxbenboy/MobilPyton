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
boutons restent : Assembler, a sa place, et Retour devenu Annuler. Une fois
rapproche, le decor se FLOUTE et s'assombrit (une profondeur de champ ;
un voile gris si la carte graphique ne s'y prete pas) : les objets du plan
se detachent d'un sol qui montre parfois les memes images (une pierre, une
brindille).
Annuler recule la vue et remet chaque objet dans sa case, et ce que
tenaient les mains reapparait : on revient exactement a l'etat d'avant.

Si les objets du plan (deux au moins) forment EXACTEMENT une recette, le
carre de droite montre un "?" (recette inconnue) ou l'objet qu'il sait deja
fabriquer ; sinon il reste vide. ASSEMBLER N'APPARAIT QU'AVEC LUI.

LE CARNET DE SAVOIRS (voir carnet.py) est garde de cote : son galet ne
paraitra que lorsque le joueur saura fabriquer le carnet (CARNET). Les
crafts connus et leurs dispositions sont retenus des maintenant : le carnet
les aura tous des sa fabrication.

DANS LA VUE, ASSEMBLER AVERTIT d'abord : des objets mal places seront
DETRUITS. Si le joueur continue :
  - mal places (voir assemblages.valide) : ils disparaissent, sauf les
    OUTILS de la recette, qui s'usent comme pour une reussite et restent ;
  - bien places : son MINI-JEU se lance, a chaque fois (voir minijeux.py),
    puis l'objet est fabrique.
    Reussi, un message annonce le craft APPRIS, que le joueur confirme.
L'objet fabrique va dans la main droite, sinon la gauche, sinon dans la
proximite. Puis la vue revient EN FONDU sur l'ecran de craft.
"""
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.screenmanager import Screen
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.widget import Widget
from kivy.uix.label import Label
from kivy.graphics import Color, Rectangle
from kivy.metrics import dp

from src.widgets.player_hands import PlayerHands
from src.widgets.styled_button import StyledButton
from src.widgets.responsive import (scale_font, ROW_TITLE, ROW_BODY,
                                    ROW_HANDS, ROW_HINT, ROW_BACK)
from src.widgets.menu_toggle import MenuToggle
from src.widgets.sol_de_craft import SolDeCraft, coins_rect, TAILLE_OBJET
from src.screens.inventory_screen import gabarit_proximite, coins_estimes
from src.widgets.assemblage import Assemblage, Loupe, DUREE_ZOOM, vue_inverse
from src.widgets.flou import floute
from src.widgets.minijeux import MINIJEUX
from src.widgets.demo_feuille import DemoFeuille, etale_sur_les_cotes
from src.widgets.panels import panel
from src.widgets.bois import plaque, BoutonGalet, TEXTE_BOIS, TITRE_BOIS
from src.widgets.carnet import Carnet
from src import assemblages, items
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


# LE VOILE DE LA VUE D'ASSEMBLAGE : un gris qui laisse deviner le sol sans
# qu'on confonde ses pierres et ses brindilles avec celles du plan. Il
# apparait en DUREE_VOILE secondes, une fois le zoom termine.
VOILE = (0.50, 0.51, 0.53, 0.78)
DUREE_VOILE = 0.25
# Mieux que le gris : le decor FLOU et assombri (voir flou.py), comme une
# profondeur de champ. Sa teinte, multipliee a l'image floue.
TEINTE_FLOU = (0.50, 0.50, 0.53)
# Duree d'un message bref (assemblage rate), en secondes.
DUREE_MESSAGE = 2.5
# LE RETOUR EN FONDU vers l'ecran de craft : l'ecran s'assombrit, la vue
# normale revient dessous, puis il s'eclaircit. Duree de chaque moitie.
DUREE_FONDU = 0.35
# L'objet qui donne le carnet de savoirs (pas encore de recette).
CARNET = "Carnet_De_Savoirs"


def _police(label, remplit=0.62):
    """Le texte du label tient dans sa boite, en hauteur ET en largeur
    (environ 0,55 em par caractere)."""
    def _maj(*_):
        lignes = (label.text or "").split("\n")
        long = max(1, max(len(l) for l in lignes))
        label.font_size = max(10.0, min(label.height * remplit / len(lignes),
                                        label.width * 0.92 / (long * 0.55)))
    label.bind(size=_maj, text=_maj)
    _maj()
    return label


class _Fondu(Widget):
    """Un voile noir plein ecran ; tant qu'il est actif, il prend les
    touchers (rien ne doit bouger pendant le fondu)."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.actif = False
        self.opacity = 0.0
        with self.canvas:
            Color(0, 0, 0, 1)
            self._rect = Rectangle(pos=self.pos, size=self.size)
        self.bind(pos=self._sync, size=self._sync)

    def _sync(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size

    def on_touch_down(self, touch):
        return self.actif

    def on_touch_move(self, touch):
        return self.actif

    def on_touch_up(self, touch):
        return self.actif


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
                              tape=self._tape,
                              coins_prox=coins_estimes(),
                              size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        self.sol.opacity = 0.0
        self.loupe.add_widget(self.sol)
        self.sol.bind(size=self._cale_proximite)
        # LA PROXIMITE A LA PLACE QU'ELLE A DANS L'INVENTAIRE, sous le meme
        # titre : une copie invisible de sa colonne (voir
        # inventory_screen.gabarit_proximite) donne sa place, au pixel pres.
        self._gabarit, self.prox_title, self._place_prox = \
            gabarit_proximite()
        self._place_prox.bind(pos=self._cale_proximite,
                              size=self._cale_proximite)
        # Le titre parait et s'efface avec la grille.
        self.prox_title.opacity = self.sol.opacity
        self.sol.bind(opacity=lambda _w, v: setattr(self.prox_title,
                                                    "opacity", v))

        # LE VOILE GRIS de la vue d'assemblage, entre le decor et les objets
        # libres : il zoome avec eux et couvre donc toujours l'ecran.
        self.voile = Widget(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        with self.voile.canvas:
            self._voile_gris = Color(*VOILE)
            self._voile_rect = Rectangle(pos=self.voile.pos,
                                         size=self.voile.size)
            self._flou_couleur = Color(*TEINTE_FLOU, 0.0)
            self._flou_rect = Rectangle(pos=self.voile.pos, size=(1, 1))
        self._flou = None

        def _sync_voile(*_):
            self._voile_rect.pos = self.voile.pos
            self._voile_rect.size = self.voile.size
        self.voile.bind(pos=_sync_voile, size=_sync_voile)
        self.voile.opacity = 0.0
        self.loupe.add_widget(self.voile)

        # LES MAINS DU JOUEUR, hors du monde : elles restent en place pendant
        # que le regard se baisse, et ne zooment pas.
        self.hands = PlayerHands(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})

        # LA VUE D'ASSEMBLAGE : les objets libres dans la loupe, et ceux que
        # portent les mains dans une couche JUSTE SOUS ELLES : l'objet est
        # tenu dans la paume, la main passe devant lui.
        self.couche_portes = Widget(size_hint=(1, 1),
                                    pos_hint={"x": 0, "y": 0})
        self.assemblage = Assemblage(mains=self.hands,
                                     couche=self.couche_portes,
                                     size_hint=(1, 1),
                                     pos_hint={"x": 0, "y": 0})
        self.loupe.add_widget(self.assemblage)
        root.add_widget(self.couche_portes)
        root.add_widget(self.hands)
        # LA MAIN FANTOME des mini-jeux et leurs encoches : par-dessus les
        # vraies mains.
        self.couche_fantome = Widget(size_hint=(1, 1),
                                     pos_hint={"x": 0, "y": 0})
        root.add_widget(self.couche_fantome)
        # LES MODELES D'EQUIPEMENT EN FEUILLE, en fantome au milieu de la vue
        # d'assemblage (voir demo_feuille.py).
        self.couche_demo = Widget(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        root.add_widget(self.couche_demo)
        self._demo = DemoFeuille(self.assemblage, self.couche_demo,
                                 self.hands, annonce=self._annonce_modele)
        self._famille_feuille = False
        # Ou en est le rapprochement : "sol" (vue normale), "entre", "zoom"
        # ou "sort" ; son avancement (0 a 1) et son horloge.
        self._mode = "sol"
        self._zoom = 0.0
        self._zoom_depart = 0.0
        self._zoom_cible = 0.0
        self._zoom_ecoule = 0.0
        self._zoom_horloge = None
        self._voile_horloge = None
        self._voile_depart = 0.0
        # Le mini-jeu en cours, l'avertissement ouvert, le message bref.
        self._minijeu = None
        self._alerte = None
        self._message = None
        self._message_horloge = None
        self._message_reste = 0.0
        self._appris = None
        self._fondu_horloge = None
        self._fondu_sens = 0

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

        # Le milieu, vide, avec en bas le rang d'Assembler, de la hauteur de
        # Retour. Il est a part pour que le titre et Retour gardent
        # exactement leurs places.
        milieu = BoxLayout(orientation="vertical", spacing=dp(8),
                           size_hint=(1, ROW_BODY + ROW_HANDS + ROW_HINT))
        milieu.add_widget(Widget(size_hint=(1, ROW_BODY + ROW_HANDS
                                            + ROW_HINT - ROW_BACK)))
        self._rang_bas = BoxLayout(orientation="horizontal",
                                   size_hint=(1, ROW_BACK))
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
        self._garnit(self._rang_bas, None)
        root.add_widget(col)
        root.add_widget(self._gabarit)
        root.add_widget(self.couche_glisse)

        # LA CONSIGNE DU MINI-JEU, a la place du titre.
        self._consigne = _police(Label(text="", bold=True, halign="center",
                                       valign="middle", color=(1, 1, 1, 1),
                                       size_hint=(1, 1)))
        panel(self._consigne, alpha=0.55)
        # LE CARNET DE SAVOIRS : un galet dans le coin bas droit, hors de la
        # vue d'assemblage (voir carnet.py).
        self._coin_carnet = BoxLayout(size_hint=(0.11, 0.085),
                                      pos_hint={"right": 0.985, "y": 0.025})
        self._bouton_carnet = BoutonGalet(text="Carnet")
        self._bouton_carnet.bind(on_release=lambda *_: self.ouvre_carnet())
        root.add_widget(self._coin_carnet)
        self._carnet = None
        self._disposition = None
        # LE FONDU, tout en haut : il prend les touchers tant qu'il est la.
        self.fondu = _Fondu(size_hint=(1, 1), pos_hint={"x": 0, "y": 0})
        root.add_widget(self.fondu)
        self._racine = root
        self.add_widget(root)

    def _cale_proximite(self, *_):
        """La proximite exactement sur sa place, sous son titre."""
        w, sol = self._place_prox, self.sol
        if sol.width <= 0 or sol.height <= 0 or w.height <= 0:
            return
        sol.set_coins_proximite(coins_rect(
            (w.x - sol.x) / float(sol.width),
            (w.y - sol.y) / float(sol.height),
            (w.x + w.width - sol.x) / float(sol.width),
            (w.y + w.height - sol.y) / float(sol.height)))

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
        self._arrete_fondu()
        self.ferme_carnet()
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
        plan = state.objets_du_plan()
        resultat = self.resultat_de(state, plan)
        self.sol.montre(cases, state.hands, resultat,
                        metres=state.metres_des_piles())
        if self._mode == "sol":
            # Assembler va avec le carre de droite : un ? ou un objet connu.
            self._garnit(self._rang_bas,
                         self._assembler if resultat is not None else None)
            self._garnit(self._coin_carnet, self._bouton_carnet
                         if self.carnet_disponible(state) else None, 1.0)

    @staticmethod
    def carnet_disponible(state):
        """Le carnet n'est la qu'une fois fabrique."""
        return state is not None and state.connait(CARNET)

    @staticmethod
    def resultat_de(state, plan):
        """Ce que montre le carre de droite pour ces objets du plan : rien
        sous deux objets, ni s'ils ne forment pas EXACTEMENT une recette
        (une partie seulement, ou avec d'autres objets en plus) ; l'objet
        s'il est connu ; sinon "?"."""
        if len(plan) < 2:
            return None
        r = assemblages.selon_objets(plan)
        if r is None:
            return None
        # Une famille (l'equipement en feuille) : la piece depend de la
        # forme qu'on donnera aux feuilles, on ne peut pas encore la montrer.
        if r["result"] is not None and state.connait(r["result"]):
            return r["result"]
        return "?"

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
        if self._mode == "sol":
            self.assemble()
        elif self._mode == "zoom" and self._alerte is None:
            self.avertit()

    # -- l'avertissement ------------------------------------------------ #
    def avertit(self):
        """Avant d'assembler : des objets mal places seront detruits."""
        self.assemblage.actif = False
        self.assemblage.lache_tout()
        boite = BoxLayout(orientation="vertical", padding=dp(26),
                          spacing=dp(10), size_hint=(0.46, 0.40),
                          pos_hint={"center_x": 0.5, "center_y": 0.56})
        plaque(boite)
        boite.add_widget(_police(Label(
            text="! ATTENTION !", bold=True, color=TITRE_BOIS,
            size_hint=(1, 0.30))))
        boite.add_widget(_police(Label(
            text="Si ces objets ne forment pas un assemblage valide,\n"
                 "ils seront detruits (les outils s'usent, mais restent).",
            halign="center", valign="middle",
            color=TEXTE_BOIS, size_hint=(1, 0.40))))
        rang = BoxLayout(orientation="horizontal", spacing=dp(12),
                         size_hint=(1, 0.30))
        oui = BoutonGalet(text="Continuer")
        oui.bind(on_release=lambda *_: self.confirme())
        non = BoutonGalet(text="Annuler")
        non.bind(on_release=lambda *_: self.ferme_alerte())
        rang.add_widget(non)
        rang.add_widget(oui)
        boite.add_widget(rang)
        self._alerte = boite
        self._alerte_oui, self._alerte_non = oui, non
        self._racine.add_widget(boite)

    def ferme_alerte(self, rend_la_main=True):
        if self._alerte is not None:
            if self._alerte.parent is not None:
                self._alerte.parent.remove_widget(self._alerte)
            self._alerte = None
        if rend_la_main and self._mode == "zoom":
            self.assemblage.actif = True

    def confirme(self):
        """Le joueur assemble pour de bon."""
        self.ferme_alerte(rend_la_main=False)
        self._arrete_demo()
        state = App.get_running_app().game_state
        if state is None or self._mode != "zoom":
            return
        asm = self.assemblage
        taille = asm.case_objet() * 3
        r = assemblages.valide(
            asm.objets, asm.contacts(),
            position=lambda o: tuple(v / taille for v in asm.a_l_ecran(o)))
        # La disposition validee, pour le carnet (les objets bougeront
        # pendant le mini-jeu).
        self._disposition = self.disposition() if r is not None else None
        if r is None:
            # Les outils de la recette tentee s'usent mais restent.
            state.detruit_le_plan(assemblages.selon_objets(
                [o["nom"] for o in self.assemblage.objets]))
            App.get_running_app().autosave()
            self._fin_assemblage()
            self.montre_message("Assemblage rate : les objets sont perdus")
            return
        # Le mini-jeu se joue A CHAQUE FABRICATION, pas seulement la
        # premiere fois.
        jeu = MINIJEUX.get(r.get("minijeu"))
        if jeu is None:
            self._reussit(r)
            return
        self._mode = "minijeu"
        self._recette = r
        self._garnit(self._rang_bas, None)
        self._garnit(self._rang_titre, self._consigne, 1.0)
        self._minijeu = jeu(self.assemblage, lambda: self._reussit(r),
                            self._dit_consigne, couche=self.couche_fantome,
                            mains=self.hands, recette=r)
        self._minijeu.demarre()
        self.assemblage.actif = True

    def disposition(self):
        """Ou sont les objets de la vue d'assemblage, en cases de leur grille
        invisible : [(nom, colonne, rangee)]."""
        asm = self.assemblage
        if not asm.objets:
            return []
        c = asm.case_objet()
        rx, ry = asm.a_l_ecran(asm.objets[0])
        out = []
        for o in asm.objets:
            x, y = asm.a_l_ecran(o)
            out.append((o["nom"], int(round((x - rx) / c)),
                        int(round((y - ry) / c))))
        return out

    # -- le carnet ------------------------------------------------------ #
    def ouvre_carnet(self):
        state = App.get_running_app().game_state
        if state is None or self._mode != "sol" or self._carnet is not None \
                or not self.carnet_disponible(state):
            return False
        self.sol.annule()
        self.sol.actif = False
        self._carnet = Carnet(fermer=self.ferme_carnet, size_hint=(1, 1),
                              pos_hint={"x": 0, "y": 0})
        self._racine.add_widget(self._carnet)
        self._carnet.montre([(o, state.dispositions.get(o))
                             for o in state.crafts_connus])
        return True

    def ferme_carnet(self):
        if self._carnet is not None:
            if self._carnet.parent is not None:
                self._carnet.parent.remove_widget(self._carnet)
            self._carnet = None
        self._place_camera()

    def _dit_consigne(self, texte):
        self._consigne.text = texte

    def _reussit(self, recette):
        """L'objet est fabrique. La premiere fois, le joueur confirme qu'il a
        appris le craft ; ensuite la vue revient en fondu."""
        state = App.get_running_app().game_state
        connu = state is not None and state.connait(recette["result"])
        objet = state.assemble(recette) if state is not None else None
        if objet is not None and not connu:
            state.retient_disposition(objet, self._disposition)
        if objet is not None:
            App.get_running_app().autosave()
        self._arrete_minijeu()
        self.assemblage.actif = False
        self.assemblage.lache_tout()
        if objet is not None and not connu:
            self.annonce_appris(objet)
        else:
            self.retour_en_fondu()

    # -- le craft appris ------------------------------------------------ #
    def annonce_appris(self, objet):
        """Le message du craft appris, a confirmer."""
        self._mode = "appris"
        self._garnit(self._rang_retour, None)
        self._garnit(self._rang_titre, None)
        boite = BoxLayout(orientation="vertical", padding=dp(26),
                          spacing=dp(10), size_hint=(0.46, 0.44),
                          pos_hint={"center_x": 0.5, "center_y": 0.56})
        plaque(boite)
        boite.add_widget(_police(Label(
            text="Nouveau craft appris !", bold=True, color=TITRE_BOIS,
            size_hint=(1, 0.28))))
        boite.add_widget(_police(Label(
            text="Tu sais maintenant fabriquer :\n%s"
                 % items.display_name(objet), halign="center",
            valign="middle", color=TEXTE_BOIS, size_hint=(1, 0.42))))
        rang = BoxLayout(orientation="horizontal", size_hint=(1, 0.30))
        rang.add_widget(Widget(size_hint_x=0.3))
        ok = BoutonGalet(text="Confirmer", size_hint_x=0.4)
        ok.bind(on_release=lambda *_: self.confirme_appris())
        rang.add_widget(ok)
        rang.add_widget(Widget(size_hint_x=0.3))
        boite.add_widget(rang)
        self._appris = boite
        self._appris_ok = ok
        self._racine.add_widget(boite)

    def confirme_appris(self):
        self._ferme_appris()
        self.retour_en_fondu()

    def _ferme_appris(self):
        if self._appris is not None and self._appris.parent is not None:
            self._appris.parent.remove_widget(self._appris)
        self._appris = None

    # -- le retour en fondu --------------------------------------------- #
    def retour_en_fondu(self):
        """L'ecran s'assombrit, la vue normale revient, il s'eclaircit."""
        self._mode = "fondu"
        self._garnit(self._rang_retour, None)
        self._garnit(self._rang_bas, None)
        self._fondu_sens = 1
        self.fondu.actif = True
        if self._fondu_horloge is None:
            self._fondu_horloge = Clock.schedule_interval(
                self._tick_fondu, 1.0 / FPS_CAMERA)

    def _tick_fondu(self, dt):
        pas = min(dt, 0.1) / DUREE_FONDU
        if self._fondu_sens > 0:
            self.fondu.opacity = min(1.0, self.fondu.opacity + pas)
            if self.fondu.opacity >= 1.0:
                # Tout est noir : la vue normale revient dessous.
                self._fin_assemblage()
                self._fondu_sens = -1
            return
        self.fondu.opacity = max(0.0, self.fondu.opacity - pas)
        if self.fondu.opacity <= 0.0:
            self._arrete_fondu()

    def _arrete_fondu(self):
        if self._fondu_horloge is not None:
            self._fondu_horloge.cancel()
            self._fondu_horloge = None
        self.fondu.opacity = 0.0
        self.fondu.actif = False
        self._fondu_sens = 0

    # -- le message bref ------------------------------------------------ #
    def montre_message(self, texte):
        self._efface_message()
        boite = BoxLayout(orientation="vertical", padding=dp(16),
                          size_hint=(0.40, 0.13),
                          pos_hint={"center_x": 0.5, "top": 0.86})
        plaque(boite, echelle_bord=0.35)
        boite.add_widget(_police(Label(text=texte, halign="center",
                                       valign="middle", color=TEXTE_BOIS,
                                       size_hint=(1, 1))))
        self._message = boite
        self._racine.add_widget(boite)
        self._message_reste = DUREE_MESSAGE
        self._message_horloge = Clock.schedule_interval(
            self._tick_message, 1.0 / 10.0)

    def _tick_message(self, dt):
        self._message_reste -= dt
        if self._message_reste <= 0.0:
            self._efface_message()

    def _efface_message(self):
        if self._message_horloge is not None:
            self._message_horloge.cancel()
            self._message_horloge = None
        if self._message is not None and self._message.parent is not None:
            self._message.parent.remove_widget(self._message)
        self._message = None

    # -- la vue d'assemblage -------------------------------------------- #
    def assemble(self):
        """Rapproche la vue du plan de travail (voir assemblage.py)."""
        state = App.get_running_app().game_state
        if state is None or self._mode != "sol" or self._pente < 0.999:
            return False
        objets = []
        for cle, (nom, n) in sorted(state.sol_en_cases().items()):
            if cle.startswith("C:"):
                x, y = self.sol.centre.centre(cle)
                fx = (x - self.sol.x) / self.sol.width
                fy = (y - self.sol.y) / self.sol.height
                # UNE PILE S'ETALE EN GRAPPE : chaque exemplaire est un objet
                # a part dans la vue, decale d'une case de la grille (trois
                # par rangee), et ils se chevauchent : la pile tient ensemble.
                case_x = TAILLE_OBJET * self.sol.height / 3.0 \
                    / max(1.0, self.sol.width)
                for k in range(n):
                    objets.append((nom, fx + (k % 3) * case_x,
                                   fy - (k // 3) * TAILLE_OBJET / 3.0))
        if not objets:
            return False
        self.sol.annule()
        self.sol.actif = False
        self.assemblage.charge(objets)
        # L'EQUIPEMENT EN FEUILLE : les objets vont sur les cotes de l'ecran,
        # le milieu montre les modeles en fantome (voir demo_feuille.py).
        r = assemblages.selon_objets([o[0] for o in objets])
        self._famille_feuille = r is not None and r.get("famille") == "feuille"
        if self._famille_feuille:
            etale_sur_les_cotes(self.assemblage)
        self.hands.set_items(None, None)
        # Seuls Assembler, a sa place, et Retour devenu Annuler.
        self._garnit(self._rang_bas, self._assembler)
        self._garnit(self._rang_titre, None)
        self._garnit(self._coin_carnet, None, 1.0)
        self._garnit(self._rang_retour, self._annuler)
        self._mode = "entre"
        self._anime_zoom(1.0)
        return True

    def annule_assemblage(self):
        """Recule la vue : chaque objet regagne sa case, et les mains ce
        qu'elles tenaient. Rien n'a change dans la partie."""
        if self._mode not in ("entre", "zoom", "minijeu"):
            return False
        self._arrete_demo()
        self._garnit(self._rang_titre, None)
        self.ferme_alerte(rend_la_main=False)
        self._arrete_minijeu()
        self.assemblage.actif = False
        self.assemblage.lache_tout()
        self.assemblage.fige_depart()
        self._arrete_voile()
        self._voile_depart = self.voile.opacity
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
            self._prepare_flou()
            if self._famille_feuille:
                self._garnit(self._rang_titre, self._consigne, 1.0)
                self._demo.demarre()
            # Le voile vient UNE FOIS LE ZOOM TERMINE.
            self._arrete_voile()
            self._voile_horloge = Clock.schedule_interval(
                self._tick_voile, 1.0 / FPS_CAMERA)
        else:
            self._fin_assemblage()

    def _applique_zoom(self):
        e = adoucir(self._zoom)
        self.loupe.regle(e)
        # Les grilles s'effacent en se rapprochant, et reviennent en
        # reculant ; les objets, eux, restent (voir Assemblage).
        self.sol.opacity = 1.0 - e
        self.assemblage.opacity = 1.0 if self._mode != "sol" else 0.0
        # En reculant, le voile s'en va avec le zoom.
        if self._mode == "sort" and self._zoom_depart > 0.0:
            self.voile.opacity = self._voile_depart * self._zoom \
                / self._zoom_depart

    def _prepare_flou(self):
        """Le decor tel qu'on le voit rapproche, sans les objets, flou : il
        remplace le voile gris. Calcule une fois, a l'arrivee du zoom."""
        caches = (self.assemblage.opacity, self.voile.opacity,
                  self.sol.opacity)
        self.assemblage.opacity = self.voile.opacity = 0.0
        self.sol.opacity = 0.0
        res = floute(self.loupe)
        (self.assemblage.opacity, self.voile.opacity,
         self.sol.opacity) = caches
        self._flou = res
        if res is None:
            self._flou_couleur.a = 0.0
            self._voile_gris.a = VOILE[3]
            return
        # Le voile est DANS la loupe (il passe sous les objets) : on le pose
        # la ou le zoom l'etale exactement sur tout l'ecran.
        lo = self.loupe
        x0, y0 = vue_inverse(1.0, lo.x, lo.y, lo.width, lo.height,
                             lo.x, lo.y)
        x1, y1 = vue_inverse(1.0, lo.x + lo.width, lo.y + lo.height,
                             lo.width, lo.height, lo.x, lo.y)
        self._flou_rect.texture = res[0]
        self._flou_rect.pos = (x0, y0)
        self._flou_rect.size = (x1 - x0, y1 - y0)
        self._flou_couleur.a = 1.0
        self._voile_gris.a = 0.0

    def _oublie_flou(self):
        self._flou = None
        self._flou_couleur.a = 0.0
        self._flou_rect.texture = None
        self._voile_gris.a = VOILE[3]

    def _tick_voile(self, dt):
        self.voile.opacity = min(1.0, self.voile.opacity
                                 + min(dt, 0.1) / DUREE_VOILE)
        if self.voile.opacity >= 1.0:
            self._arrete_voile()

    def _arrete_voile(self):
        if self._voile_horloge is not None:
            self._voile_horloge.cancel()
            self._voile_horloge = None

    def _arrete_zoom(self):
        if self._zoom_horloge is not None:
            self._zoom_horloge.cancel()
            self._zoom_horloge = None

    def _arrete_minijeu(self):
        if self._minijeu is not None:
            self._minijeu.arrete()
            self._minijeu = None

    def _annonce_modele(self, nom):
        self._consigne.text = "Modele : %s" % items.display_name(nom)

    def _arrete_demo(self):
        self._demo.arrete()

    def _fin_assemblage(self):
        """Retour a la vue normale, tout de suite."""
        self._arrete_demo()
        self._famille_feuille = False
        self._arrete_zoom()
        self.ferme_alerte(rend_la_main=False)
        self._ferme_appris()
        self._arrete_minijeu()
        self._mode = "sol"
        self._zoom = 0.0
        self.loupe.regle(0.0)
        self.assemblage.actif = False
        self.assemblage.vide()
        self.assemblage.opacity = 0.0
        self._garnit(self._rang_titre, self._titre, 1.0)
        self._garnit(self._rang_retour, self._retour)
        self._garnit(self._rang_bas, None)
        self._arrete_voile()
        self.voile.opacity = 0.0
        self._oublie_flou()
        self._place_camera()
        self.refresh()

    def _sur_camera(self):
        # Carnet ouvert : le sol attend qu'on le referme.
        if getattr(self, "_carnet", None) is not None:
            self.sol.actif = False
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

    def _tape(self, source):
        """Un simple toucher : l'objet d'une main va a proximite (le sac
        n'est pas montre ici) ; un objet de la proximite ou du plan vient en
        main (voir GameState.prend_rapide)."""
        state = App.get_running_app().game_state
        if state is None or self._mode != "sol":
            return False
        sorte, ou = source
        if sorte == "main":
            message = state.range_main(ou, sac=False)
        else:
            message = state.prend_rapide(("case", ou))
        if message is None:
            return False
        App.get_running_app().autosave()
        self.refresh()
        if message.startswith("Vide"):
            self.montre_message(message)
        elif sorte == "main":
            self.hands.geste(ou)
        return True
