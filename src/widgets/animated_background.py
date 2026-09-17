"""
Fond anime pilote par l'HEURE (cycle jour/nuit) avec astres et nuages.

Couches :
1. degrade du ciel, pris dans la LUT de la journee (assets/Atmospheres/
   sky_lut.png) ou calcule si elle est absente ;
2. LUEUR SOLAIRE : le large embrasement du ciel autour du soleil ;
3. etoiles, visibles seulement quand il fait sombre ;
4. SOLEIL et LUNE qui montent puis descendent selon l'heure (arc dans le ciel) ;
5. NUAGES qui derivent lentement.

Usages :
- MENU : le temps avance tout seul (time_scale) -> cycle visible.
- JEU  : on appelle `set_seconds(...)` pour coller a l'horloge de la partie.
"""
import math
import random

from kivy.uix.widget import Widget
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle, Ellipse, Mesh, Line
from kivy.graphics.texture import Texture
from kivy.metrics import dp

from src.widgets.gl_textures import texture_depuis_octets
from src.widgets import atmosphere, daylight

SECONDS_PER_DAY = 24 * 3600

# 24h en 4 minutes (240 s) => 360 secondes de jeu par seconde reelle.
MENU_TIME_SCALE = SECONDS_PER_DAY / 240.0

# Couleur du ciel heure par heure, DE REPLI : c'est ce que le jeu utilise quand
# sky_lut.png est absente. Sinon la ligne du BAS de la LUT prend le relais (et
# la LUT livree reproduit cette table a la quantification pres, pour que rien
# ne change cote nuit et etoiles -- voir sky_color).
#
# Le JOUR est volontairement clair : un bleu franc mais lumineux (le degrade
# assombrit deja le haut du cadre de 60 %, le ciel parait donc plus sombre a
# l'ecran que ces valeurs).
_SKY_KEYS = [
    (0.0,  (0.05, 0.07, 0.12)),
    (4.0,  (0.06, 0.08, 0.13)),
    (5.0,  (0.34, 0.23, 0.25)),
    (6.0,  (0.53, 0.69, 0.87)),
    (12.0, (0.63, 0.81, 1.00)),
    (17.0, (0.57, 0.74, 0.95)),
    (19.0, (0.58, 0.36, 0.28)),
    (20.0, (0.22, 0.18, 0.26)),
    (22.0, (0.07, 0.09, 0.14)),
    (24.0, (0.05, 0.07, 0.12)),
]


def _lut_place(lut, seconds):
    """Ou tombe cet instant dans la LUT : (colonne, colonne suivante, part).

    La journee est CYCLIQUE : la derniere colonne est voisine de la premiere,
    sinon minuit montrerait une couture."""
    w = lut[0]
    u = (seconds % SECONDS_PER_DAY) / SECONDS_PER_DAY * w
    i0 = int(u) % w
    return i0, (i0 + 1) % w, u - int(u)


def sky_color(seconds):
    """Couleur de REFERENCE du ciel a cet instant.

    C'est la couleur du ciel AU BAS DU CADRE -- la ligne du bas de la LUT. Le
    jeu ne s'en sert pas seulement pour peindre : sa luminosite decide de la
    clarte de la nuit (voir sky_luminance, night_darkness, night_factor), donc
    du voile sombre pose sur tout le decor et de l'apparition des etoiles.

    C'est voulu que ce soit la LUT qui decide : un ciel repeint plus sombre
    doit assombrir le decor avec lui. La contrepartie est qu'une LUT dont la
    ligne du bas serait claire en pleine nuit donnerait des nuits claires."""
    lut = atmosphere.sky_lut()
    if lut is not None:
        cols = lut[2]
        i0, i1, f = _lut_place(lut, seconds)
        a, b = cols[i0][0], cols[i1][0]
        return [a[k] + (b[k] - a[k]) * f for k in range(3)]
    h = (seconds % SECONDS_PER_DAY) / 3600.0
    for i in range(len(_SKY_KEYS) - 1):
        h0, c0 = _SKY_KEYS[i]
        h1, c1 = _SKY_KEYS[i + 1]
        if h0 <= h <= h1:
            t = 0.0 if h1 == h0 else (h - h0) / (h1 - h0)
            return [c0[j] + (c1[j] - c0[j]) * t for j in range(3)]
    return list(_SKY_KEYS[-1][1])


def sky_column(seconds):
    """Le ciel ENTIER a cet instant : du bas du cadre jusqu'au haut.

    Liste de triplets, l'indice 0 etant le bas du cadre. Rend None si aucune
    LUT n'est en place -- l'appelant retombe alors sur le degrade calcule."""
    lut = atmosphere.sky_lut()
    if lut is None:
        return None
    h, cols = lut[1], lut[2]
    i0, i1, f = _lut_place(lut, seconds)
    a, b = cols[i0], cols[i1]
    if f <= 0.0:
        return a
    return [(a[j][0] + (b[j][0] - a[j][0]) * f,
             a[j][1] + (b[j][1] - a[j][1]) * f,
             a[j][2] + (b[j][2] - a[j][2]) * f) for j in range(h)]


def _clamp01(v):
    return max(0.0, min(1.0, v))


def sky_luminance(seconds):
    """Luminosite (0..1) de la couleur du ciel a cette heure."""
    c = sky_color(seconds)
    return 0.3 * c[0] + 0.6 * c[1] + 0.1 * c[2]


# --------------------------------------------------------------------- #
# ASPECT DU CIEL SELON LA METEO
# --------------------------------------------------------------------- #
# Par meteo : presence des NUAGES (0 = aucun), GRISAILLE du ciel (fondu vers
# un gris) et ASSOMBRISSEMENT. Les astres (soleil, lune, etoiles) sont
# masques par les nuages : avec "cloud" a 1, plus de soleil visible.
_SKY_WEATHER = {
    "clair":    {"cloud": 0.00, "grey": 0.00, "dark": 0.00},
    "nuageux":  {"cloud": 1.00, "grey": 0.75, "dark": 0.16},
    "pluie":    {"cloud": 1.00, "grey": 0.85, "dark": 0.32},
    "orage":    {"cloud": 1.00, "grey": 0.95, "dark": 0.58},
    "neige":    {"cloud": 1.00, "grey": 0.80, "dark": 0.26},
    "blizzard": {"cloud": 1.00, "grey": 0.95, "dark": 0.52},
}
_WX_KEYS = ("cloud", "grey", "dark")

# Etat par defaut, utilise par les ecrans SANS systeme meteo (menu, craft) :
# nuages presents et ciel normal, exactement comme avant l'ajout de la meteo.
# La meteo ne prend la main que si `set_weather()` est appele.
_SKY_DEFAULT = {"cloud": 1.00, "grey": 0.00, "dark": 0.00}

# Duree caracteristique du fondu d'une meteo a l'autre (secondes reelles) :
# le ciel se couvre ou se degage progressivement, jamais d'un coup.
WEATHER_FADE = 4.0

# --------------------------------------------------------------------- #
# LES NUAGES ONT UNE DISTANCE
# --------------------------------------------------------------------- #
# Ils n'en avaient pas. Chaque nuage portait trois valeurs tirees au sort
# INDEPENDAMMENT : une hauteur a l'ecran (fy), une taille (scale) et une
# vitesse (speed). Rien ne les reliait, donc rien ne pouvait donner de
# profondeur : un nuage lointain n'etait ni plus petit, ni plus bas, ni plus
# lent, et aucun ne convergeait vers l'horizon. Ils etaient poses SUR le ciel.
#
# Desormais un nuage n'a qu'un seul parametre de position : sa DISTANCE. Tout
# le reste en decoule, par la meme perspective que le sol (voir GROUND_DEPTH
# dans zone_scenery). On la range a l'envers, en facteur k = 1/distance :
#
#   hauteur au-dessus de l'horizon   = NUAGE_ALTITUDE * ciel_libre * k
#   taille                           = NUAGE_ECHELLE  * k
#   vitesse apparente                = NUAGE_VENT     * k
#
# LES TROIS PARTAGENT LE MEME k, et c'est tout le point : un nuage deux fois
# plus loin est deux fois plus petit, deux fois plus pres de l'horizon et
# traverse l'ecran deux fois plus lentement. C'est ce dernier point qui donne
# la parallaxe -- le ciel cesse d'etre un decor qui glisse d'un bloc.
# QUATORZE ET NON SIX. Ce n'est pas une envie de ciel plus charge : avec la
# profondeur, les nuages lointains sont PETITS, donc la surface de ciel
# couverte a chute a nombre egal. On en remet pour retrouver la densite
# d'avant. Ils ne coutent presque rien -- ce sont justement les petits.
NUAGES = 14
NUAGE_PROCHE = 1.00     # k du nuage le plus proche
NUAGE_LOIN = 0.13       # k du plus lointain (donc ~7,7 fois plus loin)

# Hauteur du nuage le plus PROCHE, en part du CIEL LIBRE -- c'est-a-dire de ce
# qui reste entre la crete et le haut du cadre, et non de l'ecran entier.
#
# CETTE DISTINCTION N'EST PAS UN DETAIL. Mesuree sur l'ecran entiere, une
# altitude de 0,42 posee au-dessus de la crete du LAC (0,75) envoyait les
# nuages proches a 1,15 : hors du cadre. La planche d'apercu montrait un ciel
# de lac vide. Rapportee au ciel libre, la meme valeur marche a toutes les
# cretes, de la foret (0,47) au lac (0,75).
#
# Altitude et taille du nuage le plus PROCHE. Au plus loin, les deux sont
# multipliees par NUAGE_LOIN.
#
# NUAGE_ECHELLE N'EST PAS LA LARGEUR DU NUAGE. Un nuage est un amas d'ellipses
# qui s'etale bien au-dela de cette valeur : la largeur VISIBLE, mesuree, vaut
# environ 3,9 fois NUAGE_ECHELLE. A 0,34 -- la premiere valeur essayee -- le
# nuage le plus proche faisait 1 391 px de large sur un ecran de 1 080, ce que
# la mesure a montre aussitot. A 0,20 il occupe 0,78 de la largeur d'ecran,
# soit a peu pres le plus gros nuage d'avant, et c'est le LOINTAIN qui devient
# petit -- ce qu'on cherchait.
NUAGE_ALTITUDE = 0.85
NUAGE_ECHELLE = 0.20

NUAGE_VENT = 0.020

# De combien ils depassent de l'ecran avant de reapparaitre de l'autre cote.
# Il faut au moins la DEMI-LARGEUR VISIBLE du plus gros, sinon on le verrait
# disparaitre par morceaux. Mesuree, elle vaut 0,39 de la largeur d'ecran (et
# non 0,10 comme le donnerait NUAGE_ECHELLE / 2 : voir la remarque ci-dessus
# sur l'etalement de l'amas).
MARGE_NUAGE = 0.42

# BRUME : part de la couleur du CIEL que prend le nuage le plus lointain. Sans
# elle, un petit nuage loin reste aussi blanc qu'un gros tout pres, et l'oeil
# ne lit plus la distance -- il lit deux nuages de tailles differentes.
#
# La couleur visee est celle du ciel A LA HAUTEUR DU NUAGE, prise dans la
# colonne affichee. C'est ce qui accorde les nuages au reste : au couchant les
# lointains rosissent, parce que le ciel y est rose.
BRUME_NUAGE = 0.78

# ETALEMENT d'un nuage dessine : sa largeur visible vaut ce facteur fois
# NUAGE_ECHELLE (voir la remarque plus haut). Il sert a donner a une IMAGE de
# nuage exactement la taille qu'aurait l'amas d'ellipses qu'elle remplace, de
# sorte que deposer des images ne change pas les proportions du ciel.
ETALEMENT_NUAGE = 3.9

# Noms cherches dans assets/Atmospheres/ : le premier absent arrete la serie.
# Sans aucune image, le ciel garde ses nuages dessines au canvas.
NOMS_NUAGE = ("cloud", "cloud_2", "cloud_3", "cloud_4", "cloud_5", "cloud_6")


def images_de_nuage():
    """Les images de nuage en place, dans l'ordre. Vide s'il n'y en a pas."""
    out = []
    for nom in NOMS_NUAGE:
        tex = atmosphere.sprite(nom)
        if tex is None:
            break
        out.append(tex)
    return out

# Couleurs de base des 4 couches d'un nuage. Elles sont assombries par gros
# temps (voir "dark"), d'ou le besoin de les connaitre.
_CLOUD_RGB = {
    "c_halo": (0.95, 0.97, 1.00),
    "c_base": (0.74, 0.78, 0.86),
    "c_top":  (0.97, 0.98, 1.00),
    "c_hi":   (1.00, 1.00, 1.00),
}


# --------------------------------------------------------------------- #
# LUNE
# --------------------------------------------------------------------- #
# Mois SYNODIQUE reel : duree moyenne d'un cycle complet, d'une nouvelle lune
# a la suivante. C'est ce qui rend le cycle du jeu coherent avec la realite.
SYNODIC_DAYS = 29.53

# Phase au temps 0 : 0.5 = PLEINE lune. Les premieres nuits d'une partie sont
# donc bien eclairees, puis le cycle suit son cours naturellement.
MOON_EPOCH_PHASE = 0.5

# Part de l'assombrissement nocturne que la PLEINE lune vient compenser.
# Une nuit de pleine lune est donc nettement plus claire qu'une nuit noire.
MOON_LIGHT = 0.50

# La lumiere de la lune n'est PAS proportionnelle a la part eclairee : dans la
# realite un premier quartier (moitie du disque) n'eclaire pas la moitie d'une
# pleine lune, mais environ un dixieme. On garde cette progression rapide, un
# peu adoucie pour que les quatre etats restent bien distincts en jeu :
#   pleine 1.00 | demi 0.33 | quart 0.11 | nouvelle 0.00
MOON_LIGHT_EXPONENT = 1.6

# ------------------------------------------------------------------ #
# LES HALOS : un vrai degrade de lumiere, pas un empilement de disques.
# ------------------------------------------------------------------ #
# Les halos ont longtemps ete des cercles pleins empiles, du plus large au
# plus serre. Chaque cercle a un bord FRANC, donc chaque bord est une marche,
# et sur un ciel uni l'oeil lit chaque marche comme un ANNEAU. Ajouter des
# couches attenuait le defaut sans le supprimer : il en restait toujours un
# dernier, celui du bord exterieur, ou le halo s'arretait net.
#
# Un halo est desormais UNE SEULE image : une texture ou l'opacite decroit
# continument du centre au bord (voir glow_profile et _glow_texture). Il n'y
# a plus aucun bord franc, donc plus aucun anneau -- et c'est une seule forme
# a dessiner au lieu de sept.

# Rayon du halo, en multiples du rayon de l'astre, et opacite au bord de
# l'astre. Ces opacites ne sont pas choisies a vue : elles conservent la
# LUMIERE TOTALE que diffusaient les anciens empilements, pour que le ciel ne
# change pas de clarte.
MOON_GLOW_RADIUS, MOON_GLOW_ALPHA = 5.0, 0.793
SUN_GLOW_RADIUS, SUN_GLOW_ALPHA = 3.2, 0.560


def glow_profile(t):
    """Opacite du halo, de 1.0 au bord de l'astre a 0.0 au bord du halo.

    DEUX LOBES, parce que la lumiere diffusee se comporte de deux facons a la
    fois : une aureole serree qui colle a l'astre, et un voile large et pale
    qui s'etend bien au-dela. Un seul lobe donne soit un halo trop dur, soit
    une brume sans coeur ; les deux ensemble donnent le liseré vif contre
    l'astre ET la traine douce qui se perd dans le ciel.

    Le profil vaut exactement 0 en t = 1 : c'est ce qui garantit qu'aucun
    bord ne se voit."""
    u = max(0.0, 1.0 - t)
    return 0.55 * u ** 4 + 0.45 * u ** 1.4


# --------------------------------------------------------------------- #
# LA LUEUR SOLAIRE : le ciel qui s'embrase autour du soleil
# --------------------------------------------------------------------- #
# Le HALO (ci-dessus) est l'aureole serree de l'astre, large de trois fois son
# rayon. La LUEUR est autre chose : c'est la moitie du ciel qui blanchit ou
# rougeoie autour du soleil. C'est elle qui fait qu'un coucher de soleil se
# reconnait, et le degrade du ciel ne peut pas la porter -- un degrade varie de
# haut en bas, alors que la lueur est centree sur un POINT qui se deplace.
#
# ELLE EST FORTE QUAND LE SOLEIL EST BAS, et c'est de la physique, pas un
# reglage : au ras de l'horizon la lumiere traverse une epaisseur d'atmosphere
# bien plus grande, donc elle se diffuse beaucoup plus. A midi le soleil est un
# petit disque blanc dans un ciel propre, la lueur est presque absente.
WASH_RADIUS = 13.0      # rayon, en multiples du rayon de l'astre
WASH_ALPHA = 0.34       # opacite au bord de l'astre, soleil rasant
WASH_LOW = 1.00         # force quand le soleil rase l'horizon
WASH_HIGH = 0.20        # force au zenith

# La lueur prend la COULEUR DE LA LUMIERE de l'heure (daylight.light_tint) --
# la meme qui eclaire le decor. Le ciel et le sol rougeoient donc ensemble au
# couchant, au lieu de deux tables de couleurs a tenir d'accord a la main.
# On la melange un peu de blanc : une teinte pure, etalee sur un quart du
# cadre, vire a l'aplat colore.
WASH_WHITE = 0.30


def wash_profile(t):
    """Opacite de la lueur, de 1.0 au bord de l'astre a 0.0 au bord du ciel.

    UN SEUL LOBE, tres doux, contrairement au halo. Le halo a besoin d'un
    liseré vif contre l'astre ; la lueur, elle, ne doit avoir aucun coeur --
    son coeur est cache par l'astre et par le halo. Ce qui compte est sa
    TRAINEE, et qu'elle s'eteigne a zero sans laisser de bord."""
    return max(0.0, 1.0 - t) ** 2.2


def wash_strength(elev):
    """Force de la lueur selon la hauteur du soleil (0 = horizon, 1 = zenith)."""
    return WASH_HIGH + (WASH_LOW - WASH_HIGH) * (1.0 - elev) ** 1.6


# Finesse de la texture du halo. 128 suffit largement : elle est etiree sur
# quelques dizaines de pixels et lissee par le filtrage lineaire.
_GLOW_TEX_SIZE = 128
_GLOW_TEX = {}


def _glow_texture(inner, profil=None):
    """Texture d'un halo : blanche, l'opacite suivant glow_profile.

    `inner` est la part du rayon occupee par l'ASTRE lui-meme, ou le degrade
    n'a pas encore commence : ce coeur est de toute facon cache derriere
    l'image de l'astre. Le degrade court de la jusqu'au bord.

    Le blanc laisse la teinte au Color qui la dessine -- doree pour le soleil,
    bleutee pour la lune -- et permet de partager le meme code.

    `profil` permet d'en tirer aussi la LUEUR, qui a la meme forme radiale mais
    une decroissance bien plus douce (voir wash_profile)."""
    profil = profil or glow_profile
    key = (round(inner, 3), profil.__name__)
    if key in _GLOW_TEX:
        return _GLOW_TEX[key]
    n = _GLOW_TEX_SIZE
    half = (n - 1) / 2.0
    buf = bytearray(n * n * 4)
    for j in range(n):
        for i in range(n):
            u = math.hypot(i - half, j - half) / half
            if u >= 1.0:
                a = 0.0
            elif u <= inner:
                a = 1.0
            else:
                a = profil((u - inner) / (1.0 - inner))
            p = (j * n + i) * 4
            buf[p] = buf[p + 1] = buf[p + 2] = 255
            buf[p + 3] = int(a * 255.0 + 0.5)
    # Sans le wrap, le bord de la texture se repeterait en un liseré tout
    # autour. Et sans texture_depuis_octets, le halo resterait vide apres une
    # mise en arriere-plan : ce cache vit aussi longtemps que le processus.
    tex = texture_depuis_octets((n, n), bytes(buf), wrap="clamp_to_edge")
    _GLOW_TEX[key] = tex
    return tex

# SCINTILLEMENT du halo solaire : la lumiere qui respire autour du soleil.
#
# Trois ondes de frequences sans rapport simple. Ici, contrairement au souffle
# du joueur, le BATTEMENT est recherche : c'est lui qui fait qu'aucune pulsation
# ne ressemble a la precedente. Un scintillement regulier se lirait comme un
# clignotant.
#
# LES PERIODES SE COMPTENT EN DIZAINES DE SECONDES : 32, 19 et 12. Ce n'est pas
# un reglage fin, c'est une question de nature. Ce qui scintille VITE, ce sont
# les ETOILES -- des points que l'air fait trembler plusieurs fois par seconde.
# Un halo est une grande surface de ciel : il ne tremble pas, il respire, au
# rythme ou l'air lui-meme se deplace. Les premieres valeurs battaient a plus
# de deux fois par seconde, et cela se lisait comme un clignotement.
#
# CES VALEURS SONT CALCULEES, PAS CHOISIES A VUE. Ce qui se voit n'est ni la
# periode d'une onde ni l'amplitude, mais leur produit : la VITESSE a laquelle
# la clarte change. Elle vaut GLOW_SHIMMER * 2*pi * somme(amplitude *
# frequence), et on l'a fixee a 3 % par seconde -- le seuil sous lequel l'oeil
# ne surprend plus le mouvement, il constate seulement que le ciel n'est pas
# tout a fait fige. Les frequences en decoulent.
#
#   -> Si tu changes GLOW_SHIMMER, refais le calcul : doubler l'amplitude
#      double la vitesse, et le clignotement revient.
#
# Effet de bord heureux : les trois ondes mettent d'autant plus longtemps a
# se retrouver en phase, donc le motif ne se repete quasiment jamais.
_GLOW_WAVES = ((0.031, 0.50), (0.0535, 0.32), (0.084, 0.18))

# Le soleil DESSINE est plus grand que le soleil VU. Son image a le contour
# fondu : elle est encore franche a mi-rayon, puis s'eteint vers 0,73 -- le
# reste du cadre est le fondu, et il ne se voit pas. Plaquee telle quelle dans
# la boite d'un disque plein, elle donnerait donc un soleil un tiers plus
# petit qu'avant. On agrandit la boite d'autant (1 / 0,73) pour que le soleil
# garde sa taille A L'OEIL. Le halo, lui, reste cale sur le rayon nu : c'est
# la ou le disque se termine vraiment.
SUN_SPRITE_SCALE = 1.37

# Amplitude, en fraction de l'opacite du halo. Volontairement PETITE : le
# scintillement doit etre A PEINE PERCEPTIBLE. On ne doit pas le voir se
# produire, seulement s'apercevoir que le ciel n'est pas tout a fait fige.
# Des qu'on le remarque, le regard quitte le paysage pour aller au ciel.
GLOW_SHIMMER = 0.10


def glow_shimmer(t):
    """Facteur multiplicatif du halo a l'instant t (autour de 1.0)."""
    v = sum(a * math.sin(math.tau * f * t + i)
            for i, (f, a) in enumerate(_GLOW_WAVES))
    return 1.0 + GLOW_SHIMMER * v


# Finesse du contour de la lune (nombre de tranches horizontales).
_MOON_STEPS = 32

# Noms des 8 phases, dans l'ordre du cycle (une case = 1/8 de cycle).
_PHASE_NAMES = ("Nouvelle lune", "Premier croissant", "Premier quartier",
                "Gibbeuse croissante", "Pleine lune", "Gibbeuse decroissante",
                "Dernier quartier", "Dernier croissant")


def moon_phase(seconds):
    """Avancement du cycle lunaire : 0 = nouvelle lune, 0.5 = pleine lune."""
    return (MOON_EPOCH_PHASE + seconds / SECONDS_PER_DAY / SYNODIC_DAYS) % 1.0


def moon_illumination(seconds):
    """Part ECLAIREE du disque : 0 (nouvelle lune) a 1 (pleine lune)."""
    return (1.0 - math.cos(2.0 * math.pi * moon_phase(seconds))) / 2.0


def moon_light(seconds):
    """LUMIERE reellement apportee par la lune : 0 (nouvelle) a 1 (pleine).

    Ce n'est pas la part eclairee du disque : voir MOON_LIGHT_EXPONENT."""
    return moon_illumination(seconds) ** MOON_LIGHT_EXPONENT


def moon_phase_name(seconds):
    """Nom de la phase lunaire en cours (parmi les 8 phases usuelles)."""
    idx = int((moon_phase(seconds) + 1.0 / 16.0) % 1.0 * 8) % 8
    return _PHASE_NAMES[idx]


def _astro_darkness(seconds, max_dark):
    """Obscurite due au SEUL cycle du jour (sans tenir compte de la lune)."""
    d = (0.52 - sky_luminance(seconds)) / 0.45
    return max(0.0, min(max_dark, d * max_dark))


def night_darkness(seconds, max_dark=0.62):
    """Opacite d'un voile sombre a poser sur le decor selon l'heure.

    0 en plein jour, jusqu'a `max_dark` en pleine nuit. Suit la luminosite du
    ciel : l'assombrissement est donc progressif au crepuscule et a l'aube.

    La LUNE eclaire la nuit : plus elle est pleine, moins la nuit est noire
    (aucun effet le jour, ou l'assombrissement est deja nul). L'ecart entre
    les phases est net : une nuit de pleine lune est deux fois moins sombre
    qu'une nuit sans lune, un quartier n'apporte lui qu'un mince gain."""
    return _astro_darkness(seconds, max_dark) * (
        1.0 - MOON_LIGHT * moon_light(seconds))


# --------------------------------------------------------------------- #
# ETOILES FILANTES
# --------------------------------------------------------------------- #
# Tirage a CHAQUE HEURE DE JEU ecoulee, et seulement la nuit : une nuit de
# 10 h offre donc environ 40 % de chances d'en voir passer une.
SHOOTING_STAR_CHANCE = 0.05
SHOOTING_STAR_SECONDS = 1.1      # duree de la traversee (secondes reelles)
SHOOTING_STAR_MIN_NIGHT = 0.55   # il faut faire assez sombre pour la voir


def night_factor(seconds):
    """Avancement de la NUIT : 0 en plein jour, 1 en pleine nuit.

    Meme courbe (progressive) que l'assombrissement, mais normalisee. Ne
    depend PAS de la lune : une pleine lune ne fait pas revenir les papillons.
    Sert a faire disparaitre les insectes de jour et apparaitre les lucioles."""
    return _astro_darkness(seconds, 1.0)


class AnimatedBackground(Widget):
    def __init__(self, start_seconds=6 * 3600, time_scale=0.0, stars=120,
                 **kwargs):
        super().__init__(**kwargs)
        self._seconds = float(start_seconds) % SECONDS_PER_DAY
        # Temps ABSOLU (non ramene a la journee) : le cycle lunaire
        # s'etale sur ~29,5 jours, il lui faut le compte des jours.
        self._abs_seconds = float(start_seconds)
        self.time_scale = float(time_scale)
        # Meteo du ciel : valeurs AFFICHEES (lissees) et valeurs VISEES.
        self._wx = dict(_SKY_DEFAULT)
        self._wx_target = dict(_SKY_DEFAULT)
        # Ou le sol rencontre le ciel, en part de la hauteur. Les nuages y
        # convergent. La scene le dit (voir set_horizon) ; sans scene, on garde
        # cette valeur, celle de la plaine.
        self._horizon = 0.49
        # La colonne du ciel REELLEMENT affichee (meteo comprise), rangee du
        # bas vers le haut. Les nuages lointains s'y fondent.
        self._colonne_vue = None
        self._t = 0.0
        self._grad_accum = 0.0
        # Etoile filante : heure de jeu deja tiree, et animation en cours.
        self._last_hour = None
        self._shoot_left = 0.0
        self._shoot_path = None

        # Le degrade est une colonne d'un pixel de large, etiree sur tout le
        # cadre. Sa HAUTEUR est celle de la LUT : on recopie ses etages tels
        # quels, sans les reechantillonner.
        lut = atmosphere.sky_lut()
        self._grad_h = lut[1] if lut is not None else 64
        self._grad_tex = Texture.create(size=(1, self._grad_h),
                                        colorfmt="rgba")
        self._grad_tex.wrap = "clamp_to_edge"
        self._grad_tex.mag_filter = "linear"
        self._grad_tex.min_filter = "linear"

        with self.canvas.before:
            # 1. Ciel (degrade).
            Color(1, 1, 1, 1)
            self._rect = Rectangle(texture=self._grad_tex,
                                   pos=self.pos, size=self.size)

            # 1b. LUEUR SOLAIRE : juste au-dessus du ciel, donc DERRIERE tout
            #     le reste. Elle doit passer sous les etoiles (une etoile ne
            #     brille pas a travers l'embrasement du couchant), sous les
            #     nuages (ils sont devant le ciel) et sous le halo du soleil.
            self._wash_c = Color(1, 1, 1, 0.0)
            self._wash = Ellipse(
                texture=_glow_texture(1.0 / WASH_RADIUS, wash_profile))

            # 2. Etoiles : un halo diffus D'ABORD (donc dessous), puis le
            #    point lumineux par-dessus. Le halo est ce qui donne
            #    l'impression que l'etoile BRILLE plutot qu'elle n'est un
            #    simple pixel blanc.
            self._stars = []
            rng = random.Random(20240601)
            for i in range(stars):
                # Une etoile sur six est une BRILLANTE : plus grosse, plus
                # vive, avec un halo plus large. Le ciel a ainsi du relief au
                # lieu d'etre un semis uniforme.
                bright = (i % 6 == 0)
                glow = Color(0.85, 0.92, 1.0, 0.0)
                glow_e = Ellipse()
                col = Color(1, 1, 1, 0.0)
                self._stars.append({
                    "col": col, "e": Ellipse(),
                    "glow": glow, "ge": glow_e,
                    "fx": rng.uniform(0.02, 0.98),
                    "fy": rng.uniform(0.40, 0.98),
                    "size": dp(rng.uniform(2.6, 5.2) if bright
                               else rng.uniform(1.6, 3.4)),
                    "halo": rng.uniform(3.4, 4.6) if bright
                            else rng.uniform(2.6, 3.6),
                    "base": rng.uniform(0.85, 1.0) if bright
                            else rng.uniform(0.55, 0.9),
                    "phase": rng.uniform(0.0, 6.28),
                    "tw": rng.uniform(0.6, 1.8),
                })

            # 2b. ETOILE FILANTE (rare) : une trainee qui traverse le ciel.
            #     Creee une fois, invisible tant qu'aucune n'est en cours.
            self._shoot_glow_c = Color(0.80, 0.90, 1.0, 0.0)
            self._shoot_glow = Line(width=dp(3.2), cap="round")
            self._shoot_c = Color(1.0, 1.0, 1.0, 0.0)
            self._shoot = Line(width=dp(1.5), cap="round")

            # 3. Soleil (avec halo) et Lune.
            # Le HALO reste dessine au canvas (sa transparence varie avec
            # l'heure) ; l'image du soleil, si elle existe, se pose dessus.
            self._sun_glow_c = Color(1.0, 0.92, 0.55, 0.0)
            self._sun_glow = Ellipse(
                texture=_glow_texture(1.0 / SUN_GLOW_RADIUS))
            sun_tex = atmosphere.sprite("sun")
            self._sun_c = Color(1, 1, 1, 0.0) if sun_tex is not None \
                else Color(1.0, 0.95, 0.6, 0.0)
            self._sun = Ellipse(texture=sun_tex)
            self._sun_scale = SUN_SPRITE_SCALE if sun_tex is not None else 1.0
            # Lune : halo lumineux (plusieurs cercles de plus en plus
            # diffus), puis UNIQUEMENT la portion eclairee, dessinee comme
            # un maillage (voir _place_moon). Rien n'est dessine pour la
            # face sombre : elle est donc reellement invisible.
            self._moon_glow_c = Color(0.85, 0.90, 1.0, 0.0)
            self._moon_glow = Ellipse(
                texture=_glow_texture(1.0 / MOON_GLOW_RADIUS))
            moon_tex = atmosphere.sprite("moon")
            self._moon_c = Color(1, 1, 1, 0.0) if moon_tex is not None \
                else Color(0.97, 0.98, 1.0, 0.0)
            self._moon = Mesh(mode="triangle_strip", texture=moon_tex)
            # Les indices ne changent jamais : on les pose une fois pour
            # toutes (seuls les sommets sont recalcules a chaque frame).
            self._moon.indices = list(range(2 * (_MOON_STEPS + 1)))

            # 4. Nuages : chaque cumulus a sa PROPRE forme aleatoire (aucun
            #    identique). Base plate et grisee (volume) + bouffees blanches.
            #    4 couches par nuage (de l'arriere vers l'avant) :
            #    halo doux -> base ombree (dessous plat) -> bouffees blanches
            #    -> reflets clairs (cote eclaire). Les Color/Ellipse sont crees
            #    dans cet ORDRE pour respecter la profondeur.
            self._clouds = []
            crng = random.Random(777)
            # LES DISTANCES SONT ETALEES, PAS TIREES AU HASARD, puis rangees
            # du plus loin au plus pres.
            #
            # Etalees : un tirage uniforme peut donner dix nuages a peu pres a
            # la meme distance, et il n'y a alors plus de profondeur a voir.
            # C'est arrive a la premiere mesure -- dix tirages dans [0,13 ; 1]
            # etaient tous tombes entre 0,37 et 0,94, soit un rapport de 2,6
            # au lieu de 7,7. On decoupe donc la plage en NUAGES tranches et on
            # tire DANS chacune : le ciel a toujours du lointain et du proche.
            #
            # Rangees : l'ordre du canvas est fige une fois pour toutes, c'est
            # donc ici, et seulement ici, qu'on peut garantir qu'un nuage
            # proche passe DEVANT un nuage lointain.
            profondeurs = sorted(
                NUAGE_LOIN + (NUAGE_PROCHE - NUAGE_LOIN)
                * (i + crng.uniform(0.15, 0.85)) / NUAGES
                for i in range(NUAGES))
            # Des IMAGES de nuage si le dossier en contient ; sinon le ciel
            # garde ses amas d'ellipses. La PROJECTION est la meme dans les
            # deux cas -- c'est la peinture qui change, pas la profondeur.
            images = images_de_nuage()
            for k in profondeurs:
                nuage = {
                    # k = 1/distance : la SEULE valeur de position du nuage.
                    "k": k,
                    # Sa place de depart en travers du ciel.
                    "ang": crng.uniform(0.0, 1.0 + 2 * MARGE_NUAGE),
                    # Sa part de brume : 0 au plus proche, 1 au plus lointain.
                    "brume": (NUAGE_PROCHE - k)
                             / max(1e-6, NUAGE_PROCHE - NUAGE_LOIN),
                }
                if images:
                    tex = images[crng.randrange(len(images))]
                    nuage["c_img"] = Color(1, 1, 1, 0.0)
                    nuage["img"] = Rectangle(texture=tex)
                    tw, th = tex.size
                    nuage["ratio"] = th / float(tw or 1)
                else:
                    nha = crng.randint(2, 3)
                    halo_shape = [(crng.uniform(-1.2, 1.2),
                                   crng.uniform(0.05, 0.45),
                                   crng.uniform(1.8, 2.6),
                                   crng.uniform(1.0, 1.4)) for _ in range(nha)]
                    nb = crng.randint(4, 6)
                    base_shape = [((j / (nb - 1) - 0.5) * 2.7,
                                   crng.uniform(-0.04, 0.04),
                                   crng.uniform(1.05, 1.55),
                                   crng.uniform(0.45, 0.6)) for j in range(nb)]
                    nt = crng.randint(6, 8)
                    top_shape = [(crng.uniform(-1.1, 1.1),
                                  crng.uniform(0.16, 0.66),
                                  crng.uniform(0.8, 1.5),
                                  crng.uniform(0.7, 1.1)) for _ in range(nt)]
                    nl = crng.randint(3, 4)
                    hi_shape = [(crng.uniform(-0.85, 0.55),
                                 crng.uniform(0.5, 0.92),
                                 crng.uniform(0.5, 0.95),
                                 crng.uniform(0.5, 0.85)) for _ in range(nl)]
                    nuage.update({
                        "c_halo": Color(0.95, 0.97, 1.0, 0.0),
                        "halo_ell": [Ellipse() for _ in halo_shape],
                        "halo_shape": halo_shape,
                        "c_base": Color(0.74, 0.78, 0.86, 0.0),
                        "base_ell": [Ellipse() for _ in base_shape],
                        "base_shape": base_shape,
                        "c_top": Color(0.97, 0.98, 1.0, 0.0),
                        "top_ell": [Ellipse() for _ in top_shape],
                        "top_shape": top_shape,
                        "c_hi": Color(1, 1, 1, 0.0),
                        "hi_ell": [Ellipse() for _ in hi_shape],
                        "hi_shape": hi_shape,
                    })
                self._clouds.append(nuage)

        self._build_gradient()
        self.bind(pos=self._update_layout, size=self._update_layout)
        Clock.schedule_interval(self._tick, 1 / 60.0)

    # ------------------------------------------------------------------ #
    def set_weather(self, kind):
        """Definit la meteo du CIEL (nuages, grisaille, assombrissement).

        Le passage d'une meteo a l'autre est PROGRESSIF : on ne change que la
        cible, que `_tick` rejoint doucement."""
        self._wx_target = dict(_SKY_WEATHER.get(kind, _SKY_DEFAULT))

    def _weather_sky(self, c):
        """Applique la grisaille et l'assombrissement de la meteo a une
        couleur de ciel."""
        g, d = self._wx["grey"], self._wx["dark"]
        if g <= 0.001 and d <= 0.001:
            return list(c)
        lum = 0.3 * c[0] + 0.6 * c[1] + 0.1 * c[2]
        # Gris legerement bleute : plus naturel qu'un gris neutre.
        grey = (lum * 0.98, lum, lum * 1.06)
        out = [c[i] + (grey[i] - c[i]) * g for i in range(3)]
        return [v * (1.0 - d) for v in out]

    def set_seconds(self, seconds):
        self._seconds = float(seconds) % SECONDS_PER_DAY
        self._abs_seconds = float(seconds)

    def set_horizon(self, fraction):
        """Dit au ciel ou le sol le rencontre, en part de la hauteur d'ecran.

        C'est la scene qui sait : la crete est a 0,47 en foret et a 0,70 au
        lac (voir ZoneScenery.CRETE). Les nuages convergent vers ce point ; une
        valeur unique les aurait fait flotter au-dessus de la ligne d'eau."""
        self._horizon = max(0.0, min(1.0, float(fraction)))

    def _update_layout(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size
        for s in self._stars:
            cx = self.x + s["fx"] * self.width
            cy = self.y + s["fy"] * self.height
            sz = s["size"]
            s["e"].size = (sz, sz)
            s["e"].pos = (cx - sz / 2, cy - sz / 2)
            gz = sz * s["halo"]
            s["ge"].size = (gz, gz)
            s["ge"].pos = (cx - gz / 2, cy - gz / 2)

    def _sky_column(self):
        """Le ciel du bas vers le haut du cadre, AVANT la meteo.

        La LUT le donne etage par etage. Sans elle, on retombe sur l'ancien
        degrade : la couleur de reference en bas, la meme multipliee par 0,4 en
        haut. C'est ce repli qui ne pouvait pas changer de TEINTE en montant --
        un orange assombri est un brun, jamais un violet."""
        col = sky_column(self._seconds)
        if col is not None:
            return col
        h = self._grad_h
        bot = sky_color(self._seconds)
        top = [c * 0.4 for c in bot]
        return [[bot[k] + (top[k] - bot[k]) * (j / (h - 1)) for k in range(3)]
                for j in range(h)]

    def _build_gradient(self):
        # La meteo s'applique etage par etage : une grisaille est un fondu vers
        # le gris de MEME clarte, elle depend donc de la couleur locale et ne
        # peut pas se poser comme un voile uniforme par-dessus.
        buf = bytearray(self._grad_h * 4)
        vue = []
        for i, c in enumerate(self._sky_column()):
            r, g, b = self._weather_sky(c)
            vue.append((r, g, b))
            p = i * 4
            buf[p] = int(r * 255.0 + 0.5)
            buf[p + 1] = int(g * 255.0 + 0.5)
            buf[p + 2] = int(b * 255.0 + 0.5)
            buf[p + 3] = 255
        self._colonne_vue = vue
        self._grad_tex.blit_buffer(bytes(buf), colorfmt="rgba",
                                   bufferfmt="ubyte")

    def _ciel_a(self, part):
        """Couleur du ciel affichee a cette hauteur d'ecran (0 en bas)."""
        vue = self._colonne_vue
        if not vue:
            return self._weather_sky(sky_color(self._seconds))
        i = int(max(0.0, min(1.0, part)) * (len(vue) - 1))
        return vue[i]

    def _lum(self):
        """Luminosite du ciel due au SEUL cycle du jour.

        Volontairement independante de la meteo : un ciel d'orage assombri ne
        doit pas faire sortir les etoiles en plein midi."""
        return sky_luminance(self._seconds)

    def _place_disc(self, ellipse, cx, cy, r):
        ellipse.size = (r * 2, r * 2)
        ellipse.pos = (cx - r, cy - r)

    def _place_moon(self, cx, cy, r, night):
        """Dessine la lune a sa PHASE reelle, avec son halo lumineux.

        On ne dessine QUE la portion eclairee : aucune forme n'est posee sur
        la face sombre, qui est donc reellement invisible (pas de disque
        grisatre en croissant, en quartier ni a la nouvelle lune).

        La partie eclairee est construite tranche par tranche, en maillage
        (voir le detail dans le corps de la methode), a partir de
        k = cos(2*pi*phase) qui vaut +1 a la nouvelle lune et -1 a la pleine.
        """
        phase = moon_phase(self._abs_seconds)
        k = math.cos(2.0 * math.pi * phase)     # +1 nouvelle -> -1 pleine
        waxing = phase < 0.5                    # lune croissante

        illum = (1.0 - k) / 2.0                 # part eclairee, 0 a 1

        # 1) HALO : la lune brille d'autant plus qu'elle est pleine (aucune
        #    lueur a la nouvelle lune, ni le jour).
        glow = night * illum
        self._moon_glow_c.a = MOON_GLOW_ALPHA * glow
        self._place_disc(self._moon_glow, cx, cy, r * MOON_GLOW_RADIUS)

        # 2) Portion ECLAIREE uniquement, tranche par tranche.
        #    A la hauteur y, le disque s'etend de -xc a +xc, et le terminateur
        #    (ellipse de demi-largeur |k| * r) y passe en k * xc. La zone
        #    eclairee est donc la bande allant de k*xc au bord :
        #      k = +1 (nouvelle lune) -> bande de largeur nulle : rien ;
        #      k =  0 (quartier)      -> exactement une moitie ;
        #      k = -1 (pleine lune)   -> le disque entier.
        #    Rien n'est dessine ailleurs : la face sombre est donc invisible.
        self._moon_c.a = night
        verts = []
        for i in range(_MOON_STEPS + 1):
            t = -1.0 + 2.0 * i / _MOON_STEPS
            y = cy + t * r
            xc = r * math.sqrt(max(0.0, 1.0 - t * t))
            if waxing:                          # eclairee a droite
                x_in, x_out = k * xc, xc
            else:                               # eclairee a gauche
                x_in, x_out = -k * xc, -xc
            # Coordonnees d'image : le disque entier occupe l'image entiere.
            # La phase DECOUPE donc l'image au lieu de la deformer -- un
            # croissant montre bien le bord de la vraie lune. Sans image,
            # Kivy ignore ces valeurs : rien ne change.
            # v DESCEND quand l'ecran MONTE (voir la note de sens dans
            # textures.py) : sinon la lune se decoupe tete en bas.
            v = 0.5 - (y - cy) / (2.0 * r)
            verts += [cx + x_in, y, 0.5 + x_in / (2.0 * r), v,
                      cx + x_out, y, 0.5 + x_out / (2.0 * r), v]
        self._moon.vertices = verts

    def _start_shooting_star(self):
        """Tire une trajectoire : depart en haut du ciel, chute en diagonale."""
        rng = random
        going_right = rng.random() < 0.5
        self._shoot_path = {
            "fx": rng.uniform(0.10, 0.90),
            "fy": rng.uniform(0.62, 0.95),
            "dx": rng.uniform(0.28, 0.52) * (1 if going_right else -1),
            "dy": -rng.uniform(0.14, 0.30),
            "trail": rng.uniform(0.16, 0.26),
        }
        self._shoot_left = SHOOTING_STAR_SECONDS

    def _shape_shooting_star(self, astro):
        """Place la trainee selon l'avancement, et gere son fondu."""
        p = self._shoot_path
        if p is None:
            self._shoot_c.a = self._shoot_glow_c.a = 0.0
            return
        w, h, x0, y0 = self.width, self.height, self.x, self.y
        # 0 au depart -> 1 a l'arrivee.
        adv = 1.0 - _clamp01(self._shoot_left / SHOOTING_STAR_SECONDS)
        hx = x0 + (p["fx"] + p["dx"] * adv) * w
        hy = y0 + (p["fy"] + p["dy"] * adv) * h
        # La trainee suit la tete, raccourcie au depart comme a l'arrivee.
        tl = p["trail"] * min(1.0, adv * 4.0) * min(1.0, (1.0 - adv) * 3.0 + 0.3)
        tx = hx - p["dx"] * tl * w
        ty = hy - p["dy"] * tl * h
        pts = [tx, ty, hx, hy]
        self._shoot.points = pts
        self._shoot_glow.points = pts
        # Apparition franche, disparition douce ; masquee par les nuages.
        fade = min(1.0, adv * 6.0) * min(1.0, (1.0 - adv) * 2.6)
        self._shoot_c.a = fade * astro
        self._shoot_glow_c.a = fade * 0.35 * astro

    def _tick(self, dt):
        # Chaque ecran a son propre fond, mais un seul est AFFICHE : les autres
        # ne sont plus rattaches a la fenetre (le ScreenManager les retire).
        # Inutile de recalculer leur ciel et leurs etoiles a 60 images/s.
        if self.get_root_window() is None:
            return
        # Independant du framerate : tout se base sur dt (temps reel), avec un
        # plafond pour eviter un bond apres un ralentissement / reveil.
        dt = min(dt, 0.25)
        self._t += dt
        if self.time_scale:
            self._seconds = (self._seconds + dt * self.time_scale) \
                % SECONDS_PER_DAY
            self._abs_seconds += dt * self.time_scale
        # Fondu PROGRESSIF vers la meteo visee (jamais de bascule brutale).
        k = _clamp01(dt / WEATHER_FADE)
        for key in _WX_KEYS:
            self._wx[key] += (self._wx_target[key] - self._wx[key]) * k

        # Redessin du degrade a cadence fixe (~20/s), quel que soit le fps.
        self._grad_accum += dt
        if self._grad_accum >= 0.05:
            self._grad_accum = 0.0
            self._build_gradient()

        w, h, x0, y0 = self.width, self.height, self.x, self.y
        if w <= 0 or h <= 0:
            return
        hour = (self._seconds % SECONDS_PER_DAY) / 3600.0
        lum = self._lum()
        sun_a = _clamp01((lum - 0.10) / 0.25)     # 1 en plein jour
        night = _clamp01((0.20 - lum) / 0.18)     # 1 la nuit
        # Les nuages cachent les astres : couvert => plus de soleil, ni de
        # lune, ni d'etoiles.
        astro = 1.0 - self._wx["cloud"]

        # Etoiles.
        # Le clair de lune efface une partie des etoiles (comme en vrai) :
        # seule une lune bien pleine les fait vraiment palir.
        wash = 1.0 - 0.40 * moon_light(self._abs_seconds)
        for s in self._stars:
            twinkle = 0.35 + 0.65 * abs(math.sin(self._t * s["tw"] + s["phase"]))
            a = s["base"] * twinkle * night * astro * wash
            s["col"].a = a
            s["glow"].a = a * 0.30

        # Etoile filante : un tirage par HEURE DE JEU ecoulee, la nuit
        # seulement. Le compteur d'heures suit le temps absolu, il marche donc
        # aussi bien quand le fond avance seul (menu) que quand la partie lui
        # impose son horloge (jeu).
        hour_index = int(self._abs_seconds // 3600)
        if self._last_hour is None:
            self._last_hour = hour_index
        elif hour_index > self._last_hour:
            # Le temps peut SAUTER (sommeil, deplacement) : on tire pour
            # chaque heure franchie, en bornant pour ne pas boucler longtemps.
            steps = min(hour_index - self._last_hour, 24)
            self._last_hour = hour_index
            if night * astro >= SHOOTING_STAR_MIN_NIGHT and self._shoot_left <= 0:
                for _ in range(steps):
                    if random.random() < SHOOTING_STAR_CHANCE:
                        self._start_shooting_star()
                        break
        if self._shoot_left > 0:
            self._shoot_left -= dt
            if self._shoot_left <= 0:
                self._shoot_left = 0.0
                self._shoot_path = None
            self._shape_shooting_star(astro)
        else:
            self._shoot_c.a = self._shoot_glow_c.a = 0.0

        radius = min(w, h) * 0.055

        # Soleil : arc de 5h a 19h (gauche -> droite).
        sp = _clamp01((hour - 5.0) / 14.0)
        sx = x0 + w * (0.12 + 0.76 * sp)
        sy = y0 + h * (0.45 + 0.42 * math.sin(math.pi * sp))
        # LUEUR : large embrasement du ciel autour du soleil. Elle est forte
        # quand le soleil rase l'horizon, presque nulle au zenith, eteinte la
        # nuit (sun_a) et effacee par une couverture nuageuse (astro).
        #
        # Elle suit le soleil MEME APRES son coucher : `sp` est borne, donc
        # l'astre reste au bout de son arc, et la lueur y demeure en palissant.
        # C'est exactement ce qu'on veut -- la lueur crepusculaire traine du
        # cote ou le soleil s'est couche, pas au milieu du ciel.
        teinte = daylight.light_tint(self._seconds)
        self._wash_c.rgba = (
            teinte[0] + (1.0 - teinte[0]) * WASH_WHITE,
            teinte[1] + (1.0 - teinte[1]) * WASH_WHITE,
            teinte[2] + (1.0 - teinte[2]) * WASH_WHITE,
            WASH_ALPHA * wash_strength(daylight.sun_elevation(self._seconds))
            * sun_a * astro)
        self._place_disc(self._wash, sx, sy, radius * WASH_RADIUS)

        self._sun_c.a = sun_a * astro
        self._place_disc(self._sun, sx, sy, radius * self._sun_scale)
        # Le halo fremit. Le degrade entier respire d'un bloc : c'est
        # l'opacite de l'image qui varie, sa forme ne bouge pas.
        self._sun_glow_c.a = (sun_a * SUN_GLOW_ALPHA * astro
                              * glow_shimmer(self._t))
        self._place_disc(self._sun_glow, sx, sy, radius * SUN_GLOW_RADIUS)

        # Lune : arc de 19h a 5h (la nuit).
        nh = (hour - 19.0) % 24.0
        mp = _clamp01(nh / 10.0)
        mx = x0 + w * (0.12 + 0.76 * mp)
        my = y0 + h * (0.45 + 0.42 * math.sin(math.pi * mp))
        self._place_moon(mx, my, radius * 0.85, night * astro)

        # Nuages (cumulus) : halo doux, dessous ombre, bouffees blanches,
        # reflets clairs du cote eclaire.
        cloud_a = 0.55 * (0.30 + 0.70 * sun_a) * self._wx["cloud"]
        # Une IMAGE porte sa propre transparence : elle n'a pas besoin du 0,55
        # qui attenue l'empilement d'ellipses. Sans cela, un nuage photographie
        # apparaitrait a moitie efface.
        img_a = (0.30 + 0.70 * sun_a) * self._wx["cloud"]
        # Par gros temps, les nuages sont nettement plus sombres.
        shade = 1.0 - 0.55 * self._wx["dark"]

        def place(ellipses, shapes, cx, cy, s):
            for ell, (dx, dy, sw, sh) in zip(ellipses, shapes):
                ell.size = (sw * s, sh * s)
                ell.pos = (cx + dx * s - sw * s / 2, cy + dy * s)

        for cl in self._clouds:
            # TOUT DECOULE DE k. La place en travers du ciel est calculee et
            # non accumulee : a vitesse constante, une formule ne derive pas,
            # la ou une integration image par image finit par le faire.
            k = cl["k"]
            ang = (cl["ang"] + self._t * NUAGE_VENT * k) \
                % (1.0 + 2 * MARGE_NUAGE) - MARGE_NUAGE
            ciel_libre = 1.0 - self._horizon
            part = self._horizon + NUAGE_ALTITUDE * ciel_libre * k
            cx = x0 + ang * w
            cy = y0 + part * h
            s = w * NUAGE_ECHELLE * k
            # BRUME : le nuage se fond dans le ciel DE SA PROPRE HAUTEUR.
            brume = BRUME_NUAGE * cl["brume"]
            ciel = self._ciel_a(part)

            if "img" in cl:
                # UNE IMAGE. Sa largeur est celle qu'aurait eu l'amas
                # d'ellipses a la meme distance (voir ETALEMENT_NUAGE), pour
                # que deposer des images ne change pas l'echelle du ciel. Son
                # BAS -- le dessous plat du nuage -- se pose sur cy.
                larg = s * ETALEMENT_NUAGE
                cl["img"].size = (larg, larg * cl["ratio"])
                cl["img"].pos = (cx - larg / 2.0, cy)
                # L'image porte sa propre couleur : le Color ne fait que la
                # voiler de brume et l'assombrir par gros temps.
                cl["c_img"].rgba = tuple(
                    (1.0 + (ciel[i] - 1.0) * brume) * shade
                    for i in range(3)) + (img_a,)
                continue

            for key, ells, shapes, mult in (
                    ("c_halo", "halo_ell", "halo_shape", 0.22),
                    ("c_base", "base_ell", "base_shape", 0.85),
                    ("c_top", "top_ell", "top_shape", 1.00),
                    ("c_hi", "hi_ell", "hi_shape", 0.85)):
                base = _CLOUD_RGB[key]
                cl[key].rgba = tuple(
                    (base[i] + (ciel[i] - base[i]) * brume) * shade
                    for i in range(3)) + (cloud_a * mult,)
                place(cl[ells], cl[shapes], cx, cy, s)
