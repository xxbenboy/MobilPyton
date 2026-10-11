"""
Mains du joueur (vue 1re personne) - APPROCHE HUD plein ecran.

UNE SEULE IMAGE par etat du joueur : un HUD plein ecran dans lequel les
mains sont deja positionnees au bon endroit (en bas). Le HUD est dessine
sur toute la surface du widget (== plein ecran).

AU REPOS, chaque main a sa propre pose, et les deux sont TOUJOURS visibles :
- une main VIDE prend la pose de repos ('idle'), main refermee ;
- une main qui POSE un objet dans sa paume ouvre la main ('haut') ;
- une main qui SERRE un manche (une hache, une lance, un baton) garde la
  pose refermee, et l'objet passe DERRIERE elle (voir _dessine_tenu).
Une main vide n'etait auparavant pas dessinee du tout : on ne voyait ses
mains qu'en portant quelque chose. Comme chaque image contient les deux
mains, on n'en prend que la moitie utile (voir _draw_half).

PENDANT L'EXPLORATION, les mains ne changent PAS d'image : elles descendent
et oscillent vite, comme si on les avait avancees devant soi (searching.py).
Aucune bascule de pose, donc aucune rupture au debut ni a la fin de l'action.

Les objets tenus (set_items) sont dessines AU-DESSUS du HUD, aux
positions correspondant aux mains dans l'image (HAND_FX / ITEM_FY).
"""
import math
import os

from kivy.clock import Clock
from kivy.uix.widget import Widget
from kivy.core.image import Image as CoreImage
from kivy.graphics import (Color, Rectangle, PushMatrix, PopMatrix,
                           Translate, Rotate)

from src import items
from src.widgets import breathing, searching

_HERE = os.path.dirname(os.path.abspath(__file__))
CHARACTER_DIR = os.path.abspath(os.path.join(_HERE, "..", "..", "assets",
                                             "Character"))

# Fichier image par ETAT du joueur. L'image est un HUD PLEIN ECRAN
# (taille de reference : 2340 x 1080 pour un telephone portrait) avec
# les mains deja positionnees en bas. Le HUD est etire pour remplir
# la totalite du widget.
HUD_IMAGES = {
    'haut': 'HandHUD.png',     # paume ouverte : une main qui TIENT un objet
    'idle': 'HandIdle.png',    # main VIDE, au repos
}

# Pose d'une main qui TIENT quelque chose (paume ouverte, l'objet s'y pose).
REST_STATE = 'haut'
# Pose d'une main vide au repos.
IDLE_STATE = 'idle'

# L'EXPLORATION N'A PAS DE POSE A ELLE. Les mains gardent celle du repos et
# ne font que DESCENDRE et osciller (voir searching.py) : aucune bascule
# d'image, donc aucune rupture au debut ni a la fin de l'action.

# --------------------------------------------------------------------- #
# GANTS : des mains qui changent d'apparence
# --------------------------------------------------------------------- #
# Enfiler des gants doit SE VOIR. Le joueur passe la partie a regarder ses
# mains ; c'est la seule piece d'equipement qu'il a en permanence sous les
# yeux, et donc la seule dont le port peut se lire sans ouvrir un menu.
#
# La cle est le nom de l'objet porte a l'emplacement "gant", la valeur un
# SUFFIXE de nom de fichier : HandIdle.png a cote de HandIdleFeuille.png.
# Ajouter une paire de gants ne demande donc que deux choses -- une ligne
# ici, et des images qui suivent la meme convention.
GLOVE_SUFFIX = {
    "Gant_De_Feuille": "Feuille",
}

_TEX_CACHE = {}


def _load(fname):
    """Charge une image du personnage (ou la recupere en cache).

    Un fichier ABSENT est retenu comme tel (None en cache) : sans cela, un
    etat sans variante gantee ferait un acces disque a chaque image."""
    if fname in _TEX_CACHE:
        return _TEX_CACHE[fname]
    p = os.path.join(CHARACTER_DIR, fname)
    tex = None
    if os.path.isfile(p):
        try:
            tex = CoreImage(p).texture
        except Exception:
            tex = None
    _TEX_CACHE[fname] = tex
    return tex


def _hud_texture(state, glove=None):
    """HUD d'un etat, GANTE si le joueur porte des gants qui se voient.

    Le repli sur les mains nues n'est pas un filet de securite mais la
    regle : toute pose sans variante gantee reprend la main nue. Les deux
    poses existantes en ont une, donc les gants se voient partout -- y
    compris pendant l'exploration, qui ne change pas d'image."""
    fname = HUD_IMAGES.get(state)
    if not fname:
        return None
    suffix = GLOVE_SUFFIX.get(glove)
    if suffix:
        tex = _load(fname[:-4] + suffix + fname[-4:])
        if tex is not None:
            return tex
    return _load(fname)


# CE QU'ON MESURE SUR L'IMAGE D'UN OBJET, et pourquoi.
#
# Une image d'objet, ce n'est pas que sa taille de fichier : c'est une
# MATIERE posee dans un cadre, et deux images du meme cadre ne remplissent
# pas la main pareil. La touffe d'herbe le montrait des deux facons a la
# fois -- elle paraissait trop petite ET trop basse :
#
#   - TROP PETITE parce qu'elle est AJOUREE. Mesure : 37 % de ses pixels
#     sont opaques, contre 75 % pour la pierre et 59 % pour les baies. A
#     cadre egal, il y a deux fois moins de matiere a voir ;
#   - TROP BASSE parce qu'elle est LOURDE DU BAS. Son centre de masse est a
#     0,655 de la hauteur depuis le haut du PNG, quand la pierre, la
#     branche, la baie, la feuille et la corde sont toutes entre 0,49 et
#     0,55. Centrer le CADRE dans la paume descendait donc sa masse d'un
#     sixieme de sa hauteur, et la touffe s'enfoncait vers le poignet.
#
# On mesure donc les deux, une fois par image, et on s'en sert pour poser
# l'objet. Aucune table de noms d'objets : une image livree demain est
# traitee comme les autres.
_ITEM_INFOS = {}

# Couverture (part de pixels opaques) au-dela de laquelle une image n'a
# besoin d'aucune correction de taille. Mesuree sur les images denses du
# jeu : pierre 75 %, baie 59 %, feuille 53 %.
COUVERTURE_PLEINE = 0.55
# Plafond du grossissement. Une branche ne couvre que 12 % de son cadre et
# un roseau 11 % : sans plafond, la regle les doublerait, et un objet long
# et fin deborderait la main. Le plafond est atteint par eux deux ; l'herbe
# (37 %) reste en dessous et prend son compte exact.
GROSSISSEMENT_MAX = 1.30
# Combien de pixels on regarde, quelle que soit la taille de l'image. Une
# image d'objet fait couramment 1024 x 1024, soit un million de pixels a
# parcourir en Python ; quelques milliers suffisent a une part et a un
# centre de masse.
#
# ON VISE UN NOMBRE D'ECHANTILLONS, PAS UN PAS FIXE. Avec un pas de seize,
# les grandes images etaient bien mesurees mais la pierre (256 x 200) ne
# donnait que deux cents points : sa couverture ressortait a 71 % contre
# 75 % en pleine resolution. Le pas se deduit donc de la taille, et une
# petite image est lue plus finement qu'une grande -- ce qui ne coute rien,
# puisqu'elle est petite.
_ECHANTILLONS = 4000


# PAR OU PREND-ON UN OBJET ? Un objet COURT tient dans la paume ; un objet
# LONG se prend par son manche (une hache, une lance, un baton). On le
# reconnait a son ALLONGEMENT, et son manche est son bout le PLUS MINCE --
# le fer d'une hache est large, son manche etroit. Deux bouts aussi minces
# l'un que l'autre (un baton, un os) : on prend celui du bas, ce qui garde
# le sens de l'image.
ELONG_OUTIL = 2.4
_MANCHE_PLUS_MINCE = 0.75
# DE COMBIEN LE BOUT DU MANCHE DEPASSE DU POING, par le bas. C'est lui qui
# fait lire la prise : un manche qui s'arrete net au bord de la main a l'air
# de passer DERRIERE elle, pas d'etre tenu. On le veut donc assez long pour
# ressortir a cote de l'avant-bras -- une part de la hauteur des mains --,
# sans jamais depasser une part de l'objet lui-meme : un couteau court ne
# peut pas se tenir au quart de sa lame.
DEPASSE_MAIN = 0.115
DEPASSE_MIN, DEPASSE_MAX = 0.14, 0.28
# LONGUEUR MINIMALE D'UN OBJET SERRE, en parts de la hauteur des mains. Le
# poing fait un septieme de cette hauteur : un objet guere plus long que lui
# disparait DERRIERE, et on ne voit plus qu'un bout depasser. Un couteau de
# pierre de dix-sept centimetres fait deja deux poings de long dans la vraie
# vie -- c'est ce rapport-la qu'on garde, au lieu de celui, trop ecrase, que
# donne la table des tailles pour les petits objets.
PRISE_MIN = 0.30
# L'outil tenu penche de cet angle sur la verticale, la tete vers le haut
# et vers l'EXTERIEUR : c'est le geste de qui tient un outil sans s'en
# servir.
ANGLE_OUTIL = 24.0
# LA MAIN QUI SERRE EST CELLE DU REPOS, et l'objet passe DERRIERE elle.
#
# C'est la seule facon de faire une vraie prise avec les images qu'on a. La
# pose 'haut' est une paume grande ouverte, doigts tendus : un outil pose
# dessus FLOTTE, quoi qu'on fasse, parce qu'une main ouverte ne serre rien.
# La pose de repos, elle, est une main DEJA REFERMEE, vue de dessus ; il
# suffit de faire passer le manche derriere elle pour qu'il ressorte au-
# dessus des phalanges et au-dessous de l'auriculaire -- c'est exactement
# ce qu'on voit de ses propres mains quand on tient une hache.
#
# Ou passe le manche, mesure sur HandIdle.png : au milieu du poing (en
# parts de la largeur de l'image) et a mi-hauteur de la main, entre le haut
# des doigts replies (0,274) et le poignet (0,13), en parts de la hauteur
# de l'IMAGE des mains depuis son bas.
PRISE_FX = (0.397, 0.601)
PRISE_FY = 0.202
# La taille reelle qui remplit la boite de reference, et de combien on
# RAPPROCHE les tailles les unes des autres (voir items.TAILLE_EN_MAIN) :
# 1 les montrerait telles quelles (une baie invisible), 0 les egaliserait
# comme avant. La racine carree tient le milieu.
TAILLE_REF = 0.12
COMPRESSION = 0.5
# On n'a RIEN A RAPETISSER : les petits objets (baie, pierre, silex)
# etaient deja a la bonne taille dans la main. C'est la hache qui etait
# trop petite. L'echelle ne descend donc jamais sous 1.
ECHELLE_MIN, ECHELLE_MAX = 1.0, 3.4


def _mesure_objet(brut):
    """Ce que l'image dit de l'objet : sa part de pixels vus, son centre de
    masse, son allongement et PAR OU ON LE PREND.

    `masse_y` et `bout` sont comptes DEPUIS LE HAUT du PNG, comme les
    lignes de l'image ; `tete` est la direction (degres, a l'ecran, qui
    monte) du manche vers le bout libre, et `long` la longueur de l'objet
    le long de cet axe, en parts de la HAUTEUR de l'image.

    Les valeurs de repli disent "image pleine, centree, sans manche" : un
    objet qu'on ne sait pas mesurer est pose comme avant."""
    defaut = {"couverture": 1.0, "masse_y": 0.5, "elong": 1.0,
              "bout": (0.5, 0.5), "tete": 90.0, "long": 1.0}
    try:
        octets = brut.data
        w, h = int(brut.width), int(brut.height)
        if (brut.fmt or "rgba") != "rgba" or not octets:
            return defaut
        if w < 4 or h < 4 or len(octets) < w * h * 4:
            return defaut
        # La couverture compte les pixels VUS (alpha > 8) ; le centre de
        # masse les pondere par leur opacite, parce qu'un bord a moitie
        # transparent pese moitie moins dans ce qu'on voit.
        pas = max(1, int(math.sqrt(w * h / float(_ECHANTILLONS))))
        pts = []
        poids = sx = sy = 0.0
        vus = n = 0
        for y in range(0, h, pas):
            ligne = y * w * 4
            yv = h - 1 - y               # l'image descend, l'ecran monte
            for x in range(0, w, pas):
                a = octets[ligne + x * 4 + 3]
                n += 1
                if a > 8:
                    vus += 1
                    poids += a
                    sx += a * x
                    sy += a * yv
                    pts.append((x, yv, a))
        if not n or poids <= 0.0 or len(pts) < 8:
            return defaut
        cx, cy = sx / poids, sy / poids
        out = dict(defaut)
        out["couverture"] = vus / float(n)
        out["masse_y"] = 1.0 - cy / float(h)
        # LE GRAND AXE : la direction ou l'objet s'etale le plus, et de
        # combien il s'y etale plus qu'en travers (moments d'ordre deux).
        sxx = syy = sxy = 0.0
        for x, yv, a in pts:
            dx, dy = x - cx, yv - cy
            sxx += a * dx * dx
            syy += a * dy * dy
            sxy += a * dx * dy
        sxx /= poids
        syy /= poids
        sxy /= poids
        axe = 0.5 * math.atan2(2.0 * sxy, sxx - syy)
        demi = 0.5 * math.hypot(sxx - syy, 2.0 * sxy)
        moy = 0.5 * (sxx + syy)
        out["elong"] = math.sqrt((moy + demi) / max(1e-9, moy - demi))
        # LES DEUX BOUTS, le long de cet axe : leur largeur (en travers) et
        # leur hauteur a l'ecran disent lequel est le manche.
        co, si = math.cos(axe), math.sin(axe)
        proj = [((x - cx) * co + (yv - cy) * si,
                 abs(-(x - cx) * si + (yv - cy) * co), yv) for x, yv, a in pts]
        umin = min(p[0] for p in proj)
        umax = max(p[0] for p in proj)
        long_ = max(1e-6, umax - umin)
        bas = [p for p in proj if p[0] < umin + 0.25 * long_]
        haut = [p for p in proj if p[0] > umax - 0.25 * long_]
        if len(bas) < 3 or len(haut) < 3:
            return out
        lb = sum(p[1] for p in bas) / len(bas)
        lh = sum(p[1] for p in haut) / len(haut)
        if min(lb, lh) < _MANCHE_PLUS_MINCE * max(lb, lh):
            manche_bas = lb < lh
        else:
            manche_bas = (sum(p[2] for p in bas) / len(bas)
                          < sum(p[2] for p in haut) / len(haut))
        u = umin if manche_bas else umax
        out["bout"] = ((cx + u * co) / float(w),
                       1.0 - (cy + u * si) / float(h))
        out["long"] = long_ / float(h)
        out["tete"] = math.degrees(axe if manche_bas
                                   else axe + math.pi) % 360.0
        return out
    except Exception:
        return defaut


def _item_mesure(name):
    """(texture, mesures) de l'image d'un objet -- voir _mesure_objet.

    UNE SEULE LECTURE DU FICHIER pour tout : `keep_data=True` garde les
    pixels que Kivy relache d'ordinaire des qu'il les a televerses vers la
    carte graphique (voir foliage, ou l'oubli de ce drapeau avait tue trois
    versions du jeu). On paie donc le decodage une fois, et seulement pour
    les objets qu'on prend VRAIMENT en main."""
    vide = {"couverture": 1.0, "masse_y": 0.5, "elong": 1.0,
            "bout": (0.5, 0.5), "tete": 90.0, "long": 1.0}
    if not name:
        return None, vide
    path = items.image_path(name)
    if not path:
        return None, vide
    if path not in _ITEM_INFOS:
        try:
            img = CoreImage(path, keep_data=True)
            _ITEM_INFOS[path] = (img.texture, _mesure_objet(img.image._data[0]))
        except Exception:
            _ITEM_INFOS[path] = (None, dict(vide))
    return _ITEM_INFOS[path]


def _item_infos(name):
    """(texture, couverture, centre de masse y) : ce qu'attendent les vues
    qui dessinent un objet a plat (voir sol_de_craft.dessine_objet)."""
    tex, m = _item_mesure(name)
    return tex, m["couverture"], m["masse_y"]


def _echelle_objet(nom, couverture):
    """De combien agrandir la boite de reference pour cet objet.

    SA TAILLE REELLE d'abord (items.taille_en_main), rapprochee des autres
    et bornee : une baie reste visible, une lance tient a l'ecran. Un objet
    dont la taille n'est pas declaree garde l'ancienne regle -- on egalise
    la MATIERE VISIBLE, pour qu'une image ajouree ne disparaisse pas (la
    racine carree parce que la couverture est une surface et l'echelle une
    longueur)."""
    if items.taille_connue(nom):
        k = (items.taille_en_main(nom) / TAILLE_REF) ** COMPRESSION
        return max(ECHELLE_MIN, min(ECHELLE_MAX, k))
    if 0.0 < couverture < COUVERTURE_PLEINE:
        return min(GROSSISSEMENT_MAX,
                   math.sqrt(COUVERTURE_PLEINE / couverture))
    return 1.0


# --------------------------------------------------------------------- #
# LE SOUFFLE
# --------------------------------------------------------------------- #
# Amplitude du mouvement, en fraction de la HAUTEUR du widget (donc de
# l'ecran). Les deux se mesurent sur la hauteur, et pas l'une sur la largeur :
# sinon le va-et-vient lateral serait plus ample sur un ecran large, et le
# souffle changerait de forme d'un telephone a l'autre.
#
# Ces valeurs sont PETITES a dessein. Le souffle doit se sentir sans se
# remarquer : au-dela, les mains ont l'air de flotter, et le regard va au
# mouvement au lieu d'aller au decor. 0.9 % de la hauteur fait ~10 px sur un
# telephone -- c'est le seuil ou l'oeil voit que "ca vit" sans savoir quoi.
BREATH_Y = 0.009
BREATH_X = 0.0035

# Images par seconde du souffle. Le mouvement est LENT (un cycle en 4 s) : le
# rafraichir 60 fois par seconde ne le rendrait pas plus fluide, cela
# doublerait juste le travail. 30 suffisent largement.
BREATH_FPS = 30.0

# Abaissement des mains pendant l'EXPLORATION, en fraction de la hauteur.
# Bien plus ample que le souffle : c'est un geste volontaire, il doit se voir
# franchement, la ou le souffle doit seulement se sentir. 5,5 % font ~60 px
# sur un telephone -- assez pour lire "les mains sont passees devant".
SEARCH_Y = 0.055

# LE GESTE D'UNE MAIN qui pose un objet au sol ou l'y reprend (voir geste).
# Elle plonge vers le sol puis revient : c'est ce qui dit, sans un mot, que
# l'objet est passe de la main a la terre ou l'inverse. Vers le BAS
# seulement, comme le souffle : les bras des images s'arretent au bord
# inferieur du cadre, et une main qui monterait laisserait voir du vide sous
# elle. 6 % de la hauteur, un tiers de seconde : assez pour se voir, pas
# assez pour faire attendre.
GESTE_Y = 0.06
GESTE_DUREE = 0.32
GESTE_FPS = 60.0


class PlayerHands(Widget):
    # x du centre de chaque main (gauche, droite) en fraction de la largeur
    # du widget. Mesures depuis HandHUD.png (mains a 34 % et 65 %).
    HAND_FX = (0.346, 0.654)
    # y des objets tenus (creux de la paume), en fraction de la hauteur du
    # widget depuis le bas. Mesures depuis HandHUD.png : palm center a
    # 21 % du bas de l'image, image affichee sur 21 % de la hauteur ecran.
    ITEM_FY = 0.225
    # x du creux de la main au REPOS (HandIdle.png), entre le pouce et les
    # doigts. Plus pres du centre que HAND_FX, mesure sur la pose 'haut' :
    # la main au repos se referme vers l'interieur. Un objet pose a HAND_FX
    # tombait sur le dos de la main, du cote exterieur.
    PAUME_REPOS_FX = (0.411, 0.589)
    # x du BAS DE L'AVANT-BRAS au repos, la ou l'image coupe le bras (au bas
    # du widget). Mesure sur HandIdle.png : le bras penche vers l'exterieur,
    # son bout est donc loin du creux de la main.
    BAS_AVANT_BRAS_FX = (0.322, 0.678)
    # Cote de la boite ou tient un objet, en fraction du PETIT cote de
    # l'ecran. C'est la taille de reference : une image pleine la remplit,
    # une image ajouree recoit un peu plus (voir COUVERTURE_PLEINE).
    BOITE_OBJET = 0.15

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._items = [None, None]      # objets tenus : [gauche, droite]
        self._glove = None               # gants portes (voir set_glove)
        # Exploration : avancement de l'action (0 a 1), ou None au repos.
        self._search = None
        # Souffle : l'horloge du temps qui passe, et les deux translations
        # qu'elle deplace (mains et objets tenus).
        self._breath_t = 0.0
        self._breath_event = None
        self._shift = None
        self._shift_items = None
        # Le geste de chaque main : son avancement (None au repos), et les
        # translations qu'il deplace -- celle de la main et celle de l'objet
        # qu'elle tient, pour qu'ils bougent ensemble.
        self._geste_t = [None, None]
        self._geste_tr = [[], []]
        self._geste_event = None
        # Le deplacement libre de chaque main (vue d'assemblage), en pixels.
        self._decale = [[0.0, 0.0], [0.0, 0.0]]
        self.bind(pos=self._redraw, size=self._redraw)

    # ---- API publique ----------------------------------------------------

    def set_items(self, left, right):
        """Definit les objets tenus (None = main vide).

        Comme la VISIBILITE des mains depend maintenant des items en main
        (main vide cachee en etat 'haut'), on redessine TOUT le widget
        (pas seulement les items).
        """
        new = [left, right]
        if new == self._items:
            return
        self._items = new
        self._redraw()

    def set_glove(self, name):
        """Definit les gants PORTES (None = mains nues).

        On garde le nom de l'objet, pas un simple oui/non : passer d'une
        paire de gants a une autre doit changer l'image, et un booleen ne
        le verrait pas."""
        if name == self._glove:
            return
        self._glove = name
        self._redraw()

    def start_breathing(self):
        """Met le souffle en route (a l'arrivee sur l'ecran de jeu)."""
        if self._breath_event is None:
            self._breath_event = Clock.schedule_interval(self._tick_breath,
                                                         1.0 / BREATH_FPS)

    def stop_breathing(self):
        """Arrete le souffle (en quittant l'ecran).

        Le temps ecoule, lui, est CONSERVE : au retour, la respiration reprend
        ou elle en etait, au lieu de repartir d'une inspiration franche a
        chaque fois qu'on ouvre un menu."""
        if self._breath_event is not None:
            self._breath_event.cancel()
            self._breath_event = None

    def set_search(self, progress):
        """Exploration en cours : `progress` va de 0 a 1 sur la duree de
        l'action, et vaut None en dehors.

        Aucun redessin : les mains gardent exactement la meme image, seule
        leur POSITION change. C'est justement ce qui evite les deux ruptures
        qu'on voyait quand elles prenaient une pose de fouille."""
        self._search = progress
        self._apply_motion()

    def geste(self, index):
        """La main `index` (0 = gauche, 1 = droite) plonge vers le sol et
        revient : elle vient d'y poser un objet, ou de l'y prendre.

        Relancer un geste deja en cours le reprend du debut : deux objets
        poses coup sur coup donnent deux gestes, pas un geste tronque."""
        if index not in (0, 1):
            return
        self._geste_t[index] = 0.0
        if self._geste_event is None:
            self._geste_event = Clock.schedule_interval(self._tick_geste,
                                                        1.0 / GESTE_FPS)

    def decale(self, index, dx, dy):
        """Deplace la main `index` (et ce qu'elle tient) de (dx, dy) pixels
        depuis sa place de base. (0, 0) la ramene a sa place."""
        self._decale[index] = [float(dx), float(dy)]
        self._place_gestes()

    def decalage(self, index):
        return tuple(self._decale[index])

    def paume(self, index):
        """Le creux de la main VIDE `index` (pose de repos) a sa place de
        base, en pixels : la ou elle refermerait les doigts sur un objet."""
        return (self.x + self.PAUME_REPOS_FX[index] * self.width,
                self.y + self.ITEM_FY * self.height)

    def image_main(self, index):
        """L'image de la main `index` au repos, gantee s'il le faut, et le
        rectangle qu'elle occupe a sa place de base : (texture, pos, taille),
        ou None."""
        tex = _hud_texture(IDLE_STATE, self._glove)
        if tex is None:
            return None
        tw, th = max(1, tex.width), max(1, tex.height)
        moitie = tw // 2
        lw = self.width / 2.0
        lh = self.width * th / tw
        return (tex.get_region(index * moitie, 0, moitie, th),
                (self.x + index * lw, self.y), (lw, lh))

    def bas_avant_bras(self, index):
        """Le bout coupe de l'avant-bras `index` a sa place de base."""
        return (self.x + self.BAS_AVANT_BRAS_FX[index] * self.width, self.y)

    def _tick_geste(self, dt):
        encore = False
        for i in (0, 1):
            t = self._geste_t[i]
            if t is None:
                continue
            t += min(dt, 0.1)
            if t >= GESTE_DUREE:
                self._geste_t[i] = None
            else:
                self._geste_t[i] = t
                encore = True
        self._place_gestes()
        if not encore and self._geste_event is not None:
            self._geste_event.cancel()
            self._geste_event = None

    def _place_gestes(self):
        """Porte l'avancement de chaque geste sur ses translations.

        Un demi-sinus : la main part a vitesse nulle, touche le sol au
        milieu du geste, et revient se poser sans a-coup."""
        for i in (0, 1):
            t = self._geste_t[i]
            dy = 0.0
            if t is not None:
                dy = -GESTE_Y * self.height * math.sin(
                    math.pi * t / GESTE_DUREE)
            ox, oy = self._decale[i]
            for tr in self._geste_tr[i]:
                tr.x = ox
                tr.y = dy + oy

    # ---- Mouvement (souffle + exploration) -------------------------------

    def _tick_breath(self, dt):
        self._breath_t += dt
        self._apply_motion()

    def _apply_motion(self):
        """Porte le mouvement du moment sur les deux translations.

        Les mains et les objets recoivent LE MEME decalage : c'est ce qui fait
        qu'un objet tenu reste dans la paume au lieu d'y glisser.

        LE MOUVEMENT NE MONTE JAMAIS au-dessus de la position dessinee, et ce
        n'est pas un detail de reglage. Les bras des images s'arretent au bord
        INFERIEUR du cadre : des que les mains montent, on voit du vide sous
        elles. Le souffle est donc ramene dans [-2, 0] au lieu de [-1, +1] --
        meme ampleur, mais il ne fait que descendre depuis sa position haute --
        et l'exploration, elle, ne rend que des valeurs negatives."""
        dx, dy = breathing.offset(self._breath_t)
        ox = dx * self.height * BREATH_X
        oy = (dy - 1.0) * self.height * BREATH_Y
        oy += searching.offset(self._breath_t, self._search) \
            * self.height * SEARCH_Y
        for shift in (self._shift, self._shift_items):
            if shift is not None:
                shift.x = ox
                shift.y = oy

    # ---- Rendu -----------------------------------------------------------

    def _redraw(self, *_):
        self.canvas.clear()
        self._shift = None
        if self.width <= 0 or self.height <= 0:
            return
        # Le souffle est une TRANSLATION posee devant tout le reste, pas une
        # position recalculee dans chaque forme. Deux raisons : les mains et
        # les objets tenus bougent forcement ENSEMBLE (un objet qui ne suivrait
        # pas la main flotterait), et une image de souffle ne coute alors que
        # deux nombres a changer -- au lieu de reconstruire tout le canvas
        # trente fois par seconde.
        with self.canvas:
            PushMatrix()
            self._shift = Translate(0, 0, 0)
        # CHAQUE MAIN EST DESSINEE A PART : les trois cas n'ont pas la meme
        # pose, et celle qui SERRE un manche a son objet dessine DERRIERE
        # elle, dans le meme groupe -- il suit donc son geste tout seul.
        self._geste_tr = [[], []]
        for i in (0, 1):
            with self.canvas:
                PushMatrix()
                self._geste_tr[i].append(Translate(0, 0, 0))
            if self._serre(i):
                self._dessine_tenu(i)
                self._draw_half(i, IDLE_STATE)
            else:
                self._draw_half(i, REST_STATE if self._items[i] is not None
                                else IDLE_STATE)
            with self.canvas:
                PopMatrix()
        with self.canvas:
            PopMatrix()
        self._draw_items()
        self._apply_motion()
        self._place_gestes()

    def _serre(self, index):
        """La main `index` SERRE-t-elle ce qu'elle tient ?

        Oui pour ce qui a un MANCHE (allonge : une hache, une lance, un
        baton, un os) et pour les outils, qu'on empoigne meme courts (un
        couteau de pierre). Non pour ce qui se POSE dans la paume : une
        baie, une pierre, une feuille, une corde roulee."""
        nom = self._items[index]
        if not nom:
            return False
        tex, m = _item_mesure(nom)
        if tex is None:
            return False
        return m["elong"] >= ELONG_OUTIL or items.is_tool(nom)

    def _hauteur_mains(self):
        """Hauteur a l'ecran de l'image des mains (voir _draw_half) : elle
        est posee au bas du widget et mise a sa LARGEUR, donc sa hauteur ne
        suit pas celle de l'ecran."""
        tex = _hud_texture(IDLE_STATE, self._glove) \
            or _hud_texture(REST_STATE, self._glove)
        if tex is None:
            return self.height
        return self.width * max(1, tex.height) / max(1, tex.width)

    def _taille_objet(self, nom, tex, m, serre=False):
        """(largeur, hauteur) a l'ecran de l'image d'un objet tenu.

        POSE DANS LA PAUME, c'est le CADRE de l'image qui recoit la taille
        voulue. SERRE, c'est l'objet LUI-MEME : un os pose en diagonale au
        milieu d'une image carree n'occupe que la moitie de son cadre, et
        un manche mis a la taille du cadre ressortait deux fois trop court.
        On ne change que ce cas : les objets poses gardent la taille qu'ils
        avaient."""
        cote = self.BOITE_OBJET * min(self.width, self.height) \
            * _echelle_objet(nom, m["couverture"])
        tw, th = tex.size
        if serre:
            cote = max(cote, PRISE_MIN * self._hauteur_mains())
            ih = cote / max(0.2, m["long"])
            return ih * tw / max(1, th), ih
        if tw >= th:
            return cote, cote * th / max(1, tw)
        return cote * tw / max(1, th), cote

    def _dessine_tenu(self, index):
        """Dessine DERRIERE la main `index` l'objet qu'elle serre.

        Le point de prise de l'image (voir _mesure_objet) est amene au
        milieu du poing, et l'objet tourne pour que sa tete -- le fer, la
        pointe -- monte vers l'EXTERIEUR. Le poing couvre alors le milieu
        du manche, qui ressort au-dessus des phalanges et au-dessous de la
        main : la prise se lit sans qu'on ait eu a redessiner un doigt."""
        nom = self._items[index]
        tex, m = _item_mesure(nom)
        if tex is None:
            return
        iw, ih = self._taille_objet(nom, tex, m, serre=True)
        haut = self._hauteur_mains()
        px = self.x + PRISE_FX[index] * self.width
        py = self.y + PRISE_FY * haut
        vise = (90.0 - ANGLE_OUTIL) if index else (90.0 + ANGLE_OUTIL)
        angle = (vise - m["tete"] + 180.0) % 360.0 - 180.0
        # ON POSE LE BOUT DU MANCHE, pas la main : il doit ressortir SOUS le
        # poing de `depasse` pixels, et la prise tombe alors d'elle-meme au
        # milieu de la main. Tourner autour du bout le laisse en place, et
        # l'objet part de la dans la direction voulue.
        longueur = m["long"] * ih
        if m["elong"] >= ELONG_OUTIL:
            depasse = max(DEPASSE_MIN * longueur,
                          min(DEPASSE_MAIN * haut, DEPASSE_MAX * longueur))
        else:
            # PAS DE MANCHE (un couteau de pierre, un eclat) : le poing se
            # ferme au milieu de l'objet, et non pres d'un bout.
            depasse = 0.5 * longueur
        rad = math.radians(vise)
        bx = px - depasse * math.cos(rad)
        by = py - depasse * math.sin(rad)
        fx, fy = m["bout"]
        with self.canvas:
            PushMatrix()
            Rotate(angle=angle, origin=(bx, by))
            Color(1, 1, 1, 1)
            Rectangle(texture=tex,
                      pos=(bx - fx * iw, by - (1.0 - fy) * ih),
                      size=(iw, ih))
            PopMatrix()

    def _draw_half(self, index, state):
        """Dessine UNE main (0 = gauche, 1 = droite) dans la pose demandee.

        Chaque image contient les deux mains : on n'en prend que la moitie
        correspondante, posee a sa place a l'ecran. L'echelle ne change pas,
        seule l'autre moitie est ecartee."""
        tex = _hud_texture(state, self._glove)
        if tex is None:
            return
        tw, th = max(1, tex.width), max(1, tex.height)
        half = tw // 2
        total_w = self.width
        total_h = total_w * th / tw
        sub = tex.get_region(index * half, 0, half, th)
        with self.canvas:
            Color(1, 1, 1, 1)
            Rectangle(texture=sub,
                      pos=(self.x + index * total_w / 2, self.y),
                      size=(total_w / 2, total_h))

    def _draw_items(self):
        """Dessine au-dessus du HUD les objets POSES dans la paume.

        Ceux qu'on SERRE n'y sont pas : ils passent derriere la main, et
        sont donc dessines avec elle (voir _dessine_tenu)."""
        self.canvas.after.clear()
        self._shift_items = None
        if self.width <= 0 or self.height <= 0:
            return
        # Les objets sont dans un AUTRE canvas (celui de devant) : il leur faut
        # donc leur propre translation. Elle recoit exactement la meme valeur
        # que celle des mains (voir _apply_motion), sans quoi un objet tenu
        # glisserait dans la paume au fil du souffle.
        with self.canvas.after:
            PushMatrix()
            self._shift_items = Translate(0, 0, 0)
        for i, name in enumerate(self._items):
            if self._serre(i):
                continue
            tex, m = _item_mesure(name)
            if tex is None:
                continue
            iw, ih = self._taille_objet(name, tex, m)
            # Le creux de la paume : c'est la que l'objet se pose. ON Y MET
            # LE CENTRE DE MASSE, pas le centre du cadre. `masse_y` est
            # compte depuis le HAUT du PNG et l'ecran monte, d'ou le
            # retournement : une image lourde du bas (masse_y > 0,5) doit
            # MONTER pour que sa masse tombe au creux de la main.
            px = self.x + self.HAND_FX[i] * self.width
            py = self.y + self.height * self.ITEM_FY
            with self.canvas.after:
                # L'objet suit le geste de SA main (voir geste).
                PushMatrix()
                self._geste_tr[i].append(Translate(0, 0, 0))
                Color(1, 1, 1, 1)
                Rectangle(texture=tex,
                          pos=(px - iw / 2.0,
                               py - ih * (1.0 - m["masse_y"])),
                          size=(iw, ih))
                PopMatrix()
        with self.canvas.after:
            PopMatrix()
