"""
Decor de zone en vue RAPPROCHEE (immersive).

Le joueur est AU MILIEU de la scene : la decoration remplit tout le cadre, pas
seulement une bande en bas. On voit donc :
- Foret    : on est entoure d'arbres (du sol a la canopee),
- Plaine   : on est dans les hautes herbes jusqu'a l'horizon,
- Montagne : on est sur la pente (la roche occupe le cadre),
- Lac      : on est au bord de l'eau (grande etendue d'eau + roseaux),
- Rive     : la meme scene que le lac -- c'est elle qui la montre, depuis que
             le lac ne se visite plus (voir SCENE_DE_ZONE).

`set_scene(zone_type, seed)` change la scene. Redessine seulement quand la zone
change (pas a chaque frame).

`set_daylight(secondes)` fait suivre l'HEURE a la scene : couleur de la
lumiere et ombres portees. Il ne redessine RIEN -- il ne fait que retoucher
deux uniformes du shader et repositionner les ombres deja en place. C'est ce
qui permet au decor de vivre au fil de la journee sans reconstruire ses
centaines de formes a chaque minute.
"""
import math
import random

from kivy.clock import Clock
from kivy.uix.widget import Widget
from kivy.graphics import (Color, Ellipse, Rectangle, Triangle, Line, Quad,
                           Mesh, RenderContext, PushMatrix, PopMatrix, Rotate,
                           Canvas)

from src import world, items
from src.widgets import textures, pbr, foliage, daylight
from src.widgets import horizon
from src.widgets import animated_background
from src.widgets import rive
from src.widgets.gl_textures import texture_depuis_octets
from src.widgets.textures import paint, paint_color, tiled_coords
from src.widgets.installed_layer import grid_to_screen
from src.widgets import build_grid
from src.widgets import log_skin

_ZONE_SEED = {"Foret": 1, "Plaine": 2, "Montagne": 3, "Lac": 4}

# LA RIVE SE DESSINE COMME LE LAC. La scene du lac a toujours ete vue DE SON
# BORD -- l'eau devant, la berge au premier plan : c'est exactement la rive.
# Depuis que le lac ne se visite plus (world.NON_PRATICABLES), c'est sa rive
# qui la montre. Les tables du decor par zone n'ont donc rien a apprendre :
# la scene recoit "Lac". Une rive VOISINE, elle, borde la scene comme le
# faisait le lac : du sable, puis l'eau (voir _edge_shore).
SCENE_DE_ZONE = {"Rive": "Lac"}

# Nombre d'objets RECOLTABLES (disponibles) par type et par case : petit nombre
# aleatoire (comme avant). Chaque recolte retire du DECOR une part egale du
# nombre d'objets visibles (ex. 9 visibles / 3 disponibles -> 3 retires/recolte).
_AVAIL_MIN = 2
_AVAIL_MAX = 5

# Plancher VERTICAL des objets recoltables : ils ne sont JAMAIS places sous ce
# niveau (~ la hauteur des jointures des mains du joueur). Fraction de la
# hauteur d'ecran. On les repartit donc de cette ligne jusqu'au haut du terrain.
_HARVEST_FLOOR = 0.18

# APLATISSEMENT DES FORMES POSEES A PLAT. Une case de la grille est un carre
# sur le sol ; vue depuis les yeux du joueur elle se couche, et sa profondeur
# a l'ecran ne fait plus que cette fraction de sa largeur. Tout ce qui repose
# a plat -- le foyer, un plan de construction, les cases interdites -- doit
# partager la MEME valeur, sinon ces formes ne se posent plus sur la meme
# grille et se decalent les unes des autres.
_PLAT_PROFONDEUR = 0.55

# Retrait du marquage d'une EMPRISE vers l'interieur de ses cases, en fraction
# de case. Pris pile au bord, deux emprises voisines se toucheraient et leurs
# cordes se liraient comme une seule cloture traversant le terrain.
_EMPRISE_RETRAIT = 0.14

# Retrecissement du bord du FOND par rapport a celui de devant. C'est la seule
# part de perspective qu'on garde pour ces formes : celle qui se lit.
_EMPRISE_FUITE = 0.82

# Hauteur d'un cube de construction, en fraction de la LARGEUR d'un cube.
# Un peu moins que sa largeur : la vue etant rasante, la hauteur n'est pas
# foreshortenue alors que le sol l'est, et un rapport de un pour un donnait
# une tour plutot qu'un abri. On ne prend PAS la profondeur pour reference :
# elle est ecrasee par la vue rasante -- elle ne fait que la moitie de la
# largeur -- et s'en servir donnerait une maison aplatie comme une galette.
_CUBE_HAUTEUR = 0.82

# ASSOMBRISSEMENT DES FACES D'UNE CONSTRUCTION. La vue du jeu est FIXE : il n'y
# a pas de normale a tourner ici comme dans le chantier, seulement quatre
# valeurs qui disent de combien chaque orientation est dans l'ombre. La face
# ARRIERE ne se dessine jamais, mais le flanc lointain d'une buche, lui, se
# voit : d'ou une valeur pour elle aussi.
_OMBRE_DESSUS = 1.00
_OMBRE_DEVANT = 0.62
_OMBRE_DERRIERE = 0.40
_OMBRE_GAUCHE = 0.44
_OMBRE_DROITE = 0.52


def _peau_bois(tex, ombre, points, tex_coords, eventail=False):
    """Un polygone habille de bois : la texture si on l'a, sinon la couleur.

    L'ECLAIREMENT EST ADOUCI quand il y a une texture. L'image de l'objet
    porte deja son propre modele -- elle a ete dessinee ronde -- et lui
    appliquer le notre par-dessus noircissait les flancs deux fois."""
    f = (1.0 - _ECLAT_BUCHE * (1.0 - ombre)) if tex is not None else ombre
    if tex is not None:
        Color(f, f, f, 1)
    else:
        r, g, b = log_skin.BOIS
        Color(min(1.0, r * f), min(1.0, g * f), min(1.0, b * f), 1)
    verts = []
    for i in range(0, len(points), 2):
        verts += [points[i], points[i + 1], tex_coords[i], tex_coords[i + 1]]
    n = len(points) // 2
    if eventail:
        indices, mode = list(range(n)), "triangle_fan"
    else:
        indices, mode = [0, 1, 2, 0, 2, 3], "triangles"
    Mesh(vertices=verts, indices=indices, mode=mode, texture=tex)


# Combien on garde de l'assombrissement quand la texture est la (voir
# _peau_bois).
_ECLAT_BUCHE = 0.55

# Ce qui reste de lumiere au fond de la rainure entre deux buches.
_CREUX_BUCHE = 0.42


# L'ATELIER est un etabli DE CAMPEMENT, monte a la main (voir _etabli). En
# fractions de la largeur de son emprise :
_ETABLI_HAUT = 0.21             # hauteur du plan de travail
_ETABLI_TRETEAUX = (0.22, 0.78)  # ou sont les deux treteaux en X
_ETABLI_ECART = 0.085           # demi-ecart des pieds d'un treteau, au sol
_ETABLI_BRANCHES = 4            # branches jointives du plan de travail
_ETABLI_PORTEE = 0.82           # leur longueur
_ETABLI_EPAIS = 1.15            # un peu plus epaisses que le bois mort
_ETABLI_PIEDS = 1.5             # les pieds, plus forts encore
_ETABLI_PENTE = 1.5             # de guingois : degres, au plus
_ETABLI_PIERRE = 0.042          # rayon des pierres qui calent les pieds
_ETABLI_ENCLUME = 0.055         # rayon de la pierre de travail
_ETABLI_LIEN = (0.72, 0.64, 0.46)   # la corde vegetale des ligatures
_ETABLI_LIEN_OMBRE = (0.30, 0.25, 0.17)

# Taille des flammes selon l'etat du feu (voir game_state.FIRE_LEVELS).
# "braise" = plus de flamme du tout, seules les braises rougeoient.
_FLAME_SCALE = {"grand": 1.00, "moyen": 0.66, "petit": 0.36, "braise": 0.0}

# Langues de flamme : (decalage horizontal, taille, couleur).
_FLAME_TONGUES = ((-0.20, 0.62, (0.90, 0.32, 0.07, 1)),
                  (0.19, 0.70, (0.94, 0.44, 0.10, 1)),
                  (0.00, 1.00, (0.98, 0.62, 0.14, 1)),
                  (0.00, 0.45, (1.00, 0.88, 0.38, 1)))

# Cadence de l'animation du feu. 30 images/s suffisent largement pour un
# vacillement credible, et c'est deux fois moins de travail que 60.
_FLAME_FPS = 30.0

# --- BALANCEMENT DE LA VEGETATION ----------------------------------------- #
# Une scene compte jusqu'a 130 touffes d'herbe de 5 brins : les animer toutes
# ferait 650 formes a repositionner par image, bien trop pour un telephone.
# On n'anime donc que les touffes du PREMIER PLAN (les plus grandes, celles
# qu'on regarde), et a cadence reduite : le reste est immobile et personne ne
# le remarque, parce que le regard suit ce qui bouge devant.
SWAY = True
_SWAY_MAX = 30          # nombre de brins animes au plus
_SWAY_FPS = 15.0        # images par seconde du balancement
# Amplitude du balancement, en fraction de la HAUTEUR du brin (a vent 1.0) :
# un brin haut se courbe donc plus qu'un brin ras, comme en vrai.
_SWAY_AMPLITUDE = 0.06
# Inclinaison PERMANENTE dans le sens du vent : l'herbe ne revient jamais tout
# a fait droite tant qu'il souffle, elle oscille autour d'une position penchee.
_SWAY_BIAS = 0.35

# UNE TOUFFE EN IMAGE PLIE AUSSI, parce qu'elle est posee en MAILLAGE et non
# en rectangle. C'etait la raison pour laquelle l'herbe etait restee dessinee
# en triangles : "une image ne pourrait pas plier" (LISEZMOI des feuillages).
# C'est vrai d'un rectangle, pas d'un maillage -- on decoupe l'image en
# tranches horizontales et on decale chacune d'autant plus qu'elle est haute.
#
# CINQ RANGEES suffisent : l'oeil lit la COURBURE, pas le nombre de tranches.
# A trois, le pli se voit par morceaux ; au-dela de cinq, on paie des sommets
# pour rien (il y a des centaines de touffes par scene).
RANGEES_HERBE = 5

# L'image des touffes. C'est le DEFAUT de _grass_tuft, et non un nom passe par
# chacun des huit endroits qui dessinent de l'herbe : une touffe d'herbe, par
# definition, utilise l'image d'une touffe d'herbe. Le roseau du lac, lui,
# passe la sienne et garde donc son propre aspect.
NOM_HERBE = "grass_tuft"

# COMBIEN DE TOUFFES EN PLUS, par zone. Elles sont decoratives : elles ne
# passent pas par _take_or_skip, donc elles n'ajoutent rien a ramasser et ne
# disparaissent pas quand on recolte.
#
# Le sol en porte ainsi 350 en plaine (230 + 120) et 190 en foret, contre 230
# et 130 avant. Et cela coute MOINS cher qu'avant : une touffe en image est un
# Color et un maillage, la ou une touffe dessinee etait cinq Color et cinq
# triangles.
HERBE_DECOR_PLAINE = 600   # x5 : l'herbe doit couvrir presque tout le sol
HERBE_FORET = 950          # x5 (etait 190)

# TOUFFES A RAMASSER de la foret, en plus des precedentes (voir _foret). Un
# lot separe, parce qu'une recolte masque une part egale des objets de son
# type : melangees aux 950 touffes decoratives, chaque poignee aurait emporte
# un cinquieme du tapis de sous-bois. Le chiffre se compare aux 525 de la
# plaine -- moins, parce que la foret est un sous-bois, pas un pre.
HERBE_RECOLTABLE_FORET = 240

# Touffes de la BANDE LOINTAINE de la plaine, entre le haut du champ proche et
# la crete. Elle etait a peu pres vide : `place` ne depasse jamais le champ, et
# la seule passe qui allait plus loin se serrait sur la crete meme. Elles sont
# petites, donc on peut en mettre beaucoup.
HERBE_LOIN_PLAINE = 750    # x5 (etait 150)

# Touffes AU PIED du joueur, sous le plancher des objets a ramasser (voir
# _plaine). Plus grandes a l'ecran que celles du champ -- elles sont tout
# pres -- il en faut donc moins pour couvrir la bande.
HERBE_PIED_PLAINE = 260

# Echelle apparente d'une touffe au SOMMET DU CHAMP PROCHE. C'est la valeur
# que `place` y donne (1 - 0,70 x 1) : la bande lointaine part de la, et
# continue de retrecir comme le fait la tuile du sol.
ECHELLE_HERBE_CHAMP = 0.30

# Comment la courbure se repartit sur la hauteur. AU-DESSUS DE 1 : le bas
# reste droit et seule la pointe se couche, ce qui est la definition meme d'un
# brin qui plie. A 1 la touffe entiere s'inclinerait comme un panneau.
COURBE_HERBE = 1.7

# --- LE VENT DANS LE FEUILLAGE DES ARBRES ---------------------------------- #
# Meme levier que pour l'herbe -- l'image est posee en MAILLAGE, donc elle peut
# se deformer -- mais un arbre n'est pas un brin d'herbe, et deux choses l'en
# separent.
#
# SON TRONC NE BOUGE PAS. Un brin plie a partir du sol ; un arbre a un fut
# rigide, et seul ce qui est au-dessus des premieres branches bruisse.
#
# SON HOUPPIER NE PIVOTE PAS D'UN BLOC. C'est pourquoi on pose une GRILLE et
# non des rangees : chaque COLONNE recoit sa propre phase, si bien qu'une
# rafale TRAVERSE le feuillage de gauche a droite au lieu de l'incliner tout
# entier. C'est ce qui distingue des feuilles qui remuent d'un panneau qui
# oscille -- et c'est aussi la seule chose qu'une simple rangee ne sait pas
# faire.
#
# 8 x 6 cases, soit 63 sommets : assez pour que la deformation soit continue a
# l'oeil, assez peu pour que six arbres animes a 15 images par seconde ne
# coutent que 378 sommets par image.
RANGEES_ARBRE = 8
COLONNES_ARBRE = 6

# Hauteur, en fraction de l'image depuis le bas, en dessous de laquelle RIEN
# ne bouge : le tronc. Mesuree sur l'image livree (voir
# scratchpad/arbre_pbr2.py, base_du_feuillage) : les premieres feuilles
# apparaissent a 0,256 de la hauteur.
#
# C'est une constante et non une mesure faite en jeu : la relever demanderait
# d'ouvrir les pixels de chaque image au moment de dessiner. Si quelqu'un
# depose un arbre de proportions tres differentes, le pire qui arrive est que
# le haut de son tronc frissonne un peu, ou que ses feuilles les plus basses
# restent immobiles. Rien ne casse.
TRONC_FIXE = 0.26

# Comment l'amplitude monte au-dessus du tronc. AU-DESSUS DE 1 : la base du
# houppier bouge a peine, la cime prend tout -- le comportement d'une branche
# encastree. Plus doux que pour l'herbe (1,7), parce que le tronc a deja
# retire le quart du bas du mouvement.
COURBE_ARBRE = 1.5

# Amplitude, en fraction de la HAUTEUR de l'arbre, a vent maximal.
#
# MESURE SUR L'ARBRE DE PREMIER PLAN DE LA FORET (1144 px de haut) : sa cime
# s'ecarte de 10 px par temps clair et de 54 px en blizzard, soit 0,9 % et
# 4,7 % de sa hauteur. C'est l'ordre de grandeur d'un vrai houppier. L'herbe,
# elle, va jusqu'a 29 % de sa hauteur : un brin se couche, un arbre non.
#
# Un premier reglage a 0,012 donnait 4 px par temps clair -- exact sur le
# papier, invisible a l'ecran, et c'est par temps clair qu'on joue le plus
# souvent.
VENT_ARBRE_AMPLITUDE = 0.030

# Les deux frequences du mouvement, en HERTZ (et non en radians comme la
# vitesse de l'herbe, qui se lit mal). Lentes, et dans un rapport irrationnel
# pour que le motif ne se referme pas a l'oeil.
#
# CE SONT LES VALEURS CENTRALES, pas les extremes : chaque arbre les ecarte de
# +/- 6 % (voir _sprite_feuillage) pour que la foret ne respire pas d'un seul
# souffle. 0,53 et 0,94 sont donc choisies pour que MEME APRES cet ecart tout
# reste dans la plage voulue -- 0,50 a 0,56 et 0,88 a 1,00. A 0,5 et 0,9 pile,
# les arbres les plus lents tombaient a 0,47 Hz, mesure.
VENT_ARBRE_HZ = (0.53, 0.94)
VENT_ARBRE_MELANGE = 0.35       # poids de la seconde onde

# Inclinaison permanente dans le sens du vent, comme pour l'herbe (0,35) mais
# plus discrete : un houppier s'appuie sur le vent, il ne se couche pas.
VENT_ARBRE_BIAIS = 0.25

# Decalage de phase entre le bord gauche et le bord droit du houppier, en
# radians. C'est LUI qui fait traverser la rafale : a 0 tout le feuillage
# bougerait ensemble, a 2*pi les deux bords seraient de nouveau en phase. A
# 1,9 le bord droit a un peu moins d'un tiers de cycle de retard.
VENT_ARBRE_TRAVERSE = 1.9

# --- CHAQUE ARBRE PENCHE A SA FACON ------------------------------------- #
# Deux images livrees penchent franchement -- mesure par le jeu lui-meme
# (foliage.inclinaison) : +6,0 et +7,0 degres, quand les dix autres tiennent
# entre -1 et +1. Le probleme n'etait pas l'angle mais qu'il soit TOUJOURS LE
# MEME, et toujours du meme cote : deux de ces arbres cote a cote se
# reconnaissaient au premier coup d'oeil.
#
# On fait donc deux choses a la fois, et une seule rotation suffit :
#
#   1. ON REDRESSE l'image de sa propre inclinaison, mesuree. L'arbre qui
#      penchait a +7 degres repart de zero, comme les autres ;
#   2. ON EN REDONNE, tiree de la POSITION. Chaque pied a donc son angle, et
#      les deux sens sortent aussi souvent l'un que l'autre.
#
# Le tirage est CUBIQUE : la plupart des arbres restent presque droits, et
# seule une minorite penche pour de bon. Un tirage uniforme aurait donne une
# foret entiere de travers, ce qui n'est pas plus credible qu'une foret au
# garde-a-vous. Avec 9 degres d amplitude : la moitie des arbres reste sous
# 1,6 degre, un sur trois passe 3, et un sur huit passe 6.
PENCHE_ARBRE = 9.0
# De combien on efface l'inclinaison propre de l'image. A 1, entierement.
REDRESSE_ARBRE = 1.0

# Combien d'arbres on anime. Ils ont leur QUOTA PROPRE, et c'est necessaire :
# le tri se fait sur la hauteur, et un arbre est dix fois plus haut qu'une
# touffe. Dans une seule liste, les arbres videraient le quota de l'herbe.
# Les deux sortes d'arbre le PARTAGENT : ce qui coute, c'est le nombre de
# maillages a repositionner, pas leur espece.
_SWAY_ARBRES = 6

# --- ET LE VENT DANS UN SAPIN, QUI N'EST PAS LE MEME ----------------------- #
# Un houppier de feuillu est une masse souple portee par un tronc : le vent le
# traverse de gauche a droite et le fait ondoyer. Un sapin est tout le
# contraire -- une fleche rigide portant des etages de branches raides. Ce qui
# bouge chez lui, ce n'est pas la masse, ce sont LES POINTES DES BRANCHES, et
# elles ne bougent pas dans le meme sens.
#
# D'ou trois differences, et non un simple reglage plus faible :
#
#   1. LE BALANCEMENT SE CONCENTRE DANS LA FLECHE. L'exposant passe de 1,5 a
#      2,6 : les etages du bas ne bougent presque pas, la cime fouette.
#
#   2. LES BRANCHES REBONDISSENT VERTICALEMENT. C'est la signature d'un
#      conifere, et aucun feuillu ne la montre : une branche de sapin est un
#      porte-a-faux souple, elle bat de haut en bas. L'amplitude ne depend
#      donc pas de la hauteur mais de la DISTANCE A L'AXE -- nulle sur le
#      tronc, maximale au bout des branches.
#
#   3. LE REBOND MONTE LE LONG DE L'ARBRE. Les etages ne battent pas
#      ensemble : une onde les parcourt du bas vers le haut.
#
# Le sapin est haut et etroit : on lui donne plus de RANGEES (ses etages) et
# moins de COLONNES (sa largeur) qu'au feuillu. 10 x 4 fait 55 sommets, huit
# de moins que la grille du feuillu.
RANGEES_SAPIN = 10
COLONNES_SAPIN = 4

# Les branches d'un sapin descendent presque jusqu'au sol : il ne reste qu'un
# empattement. Mesure sur l'image livree : les premieres aiguilles apparaissent
# a 0,109 de la hauteur (le feuillu, lui, est a 0,26).
TRONC_FIXE_SAPIN = 0.11
COURBE_SAPIN = 2.6

# Amplitude laterale, en fraction de la hauteur, a vent maximal. La MOITIE du
# feuillu (0,030) : un sapin est raide. Et il est plus haut -- jusqu'a toute
# la hauteur d'ecran contre 1144 px -- donc en pixels l'ecart reste du meme
# ordre.
VENT_SAPIN_AMPLITUDE = 0.016

# Le rebond vertical des pointes, meme unite.
#
# MESURE PLUTOT QUE DEDUITE. Le premier reglage, 0,006, venait d'un
# raisonnement sur du vrai bois -- une branche d'un metre qui bat de cinq
# centimetres sur un arbre de quinze metres, c'est bien 0,3 % de sa hauteur.
# Sauf qu'a l'ecran cela faisait 1,8 px par temps clair : la signature du
# conifere n'existait tout simplement pas. A 0,014 elle vaut 4 px par temps
# clair et 20 px par orage, soit un cisaillement de 4 % entre deux colonnes
# voisines -- visible comme un battement, pas comme une dechirure.
VENT_SAPIN_BOND = 0.014

# De combien la phase du rebond avance entre le pied et la cime, en radians.
# C'est ce qui fait MONTER l'onde d'un etage a l'autre au lieu de les faire
# battre tous ensemble.
VENT_SAPIN_MONTEE = 2.4

# Plus rapide que le feuillu (0,53 et 0,94 Hz) : une structure plus raide et
# plus legere vibre plus vite. Toujours dans la plage voulue, ecart de +/- 6 %
# par arbre compris (0,62 a 0,70 et 0,83 a 0,93).
VENT_SAPIN_HZ = (0.66, 0.88)
VENT_SAPIN_MELANGE = 0.30
VENT_SAPIN_BIAIS = 0.18

# La rafale traverse peu : l'arbre est etroit et raide, elle le prend presque
# d'un bloc. 0,8 radian contre 1,9 pour le feuillu.
VENT_SAPIN_TRAVERSE = 0.8

# De combien la HAUTEUR d'un sapin varie d'un pied a l'autre, en plus du
# tirage que fait deja la scene. Les quatre images livrees donnent quatre
# silhouettes (deux miroirs, une trapue, une elancee) ; ce facteur-ci y ajoute
# la taille, pour qu'une sapiniere n'aligne pas des arbres de meme stature.
# Il est tire de la POSITION, donc stable : un sapin ne change pas de taille
# quand on ramasse une pierre a cote.
HAUTEUR_SAPIN = (0.82, 1.18)

# --- LE BUISSON EN IMAGE --------------------------------------------------- #
# Un buisson est un feuillu SANS TRONC : ses tiges partent du sol, et c'est
# toute sa masse qui ondoie. Meme grille que le feuillu, reglee autrement :
#
#   - PLUS DE COLONNES QUE DE RANGEES : il est plus large que haut, et la
#     rafale a davantage de chemin a faire pour le traverser ;
#   - PRESQUE PAS DE PIED FIXE : le feuillage descend jusqu'au sol, seules
#     les tiges du bas (le dixieme de la hauteur) restent plantees ;
#   - UNE AMPLITUDE PLUS FORTE, en part de sa hauteur : des tiges fines
#     plient plus qu'un fut. Il est aussi trois fois moins haut qu'un arbre :
#     a 0,030 comme lui, il n'aurait bouge que de deux pixels par temps clair ;
#   - UN PEU PLUS VITE : plus petit et plus souple, il bat plus vite (le
#     feuillu est a 0,53 et 0,94 Hz).
RANGEES_BUISSON = 5
COLONNES_BUISSON = 8
TRONC_FIXE_BUISSON = 0.10
COURBE_BUISSON = 1.2
VENT_BUISSON_AMPLITUDE = 0.06
VENT_BUISSON_HZ = (0.71, 1.23)
VENT_BUISSON_TRAVERSE = 2.4

# SA HAUTEUR A L'ECRAN, en rayons. Le buisson est la REFERENCE de taille du
# decor -- les pepites se mesurent sur lui -- et il doit donc garder l'emprise
# de son ancien dessin : 2,89 r de large pour 1,51 r de haut. L'image est plus
# haute a proportion (1,63 fois plus large que haute) ; a 1,65 r de haut elle
# fait 2,67 r de large, soit la meme surface (4,4 r2). A la hauteur prevue
# auparavant pour une image quelconque (2,1 r), il aurait pris 60 % de place
# en plus et ecrase tout ce qui se mesure sur lui.
HAUTEUR_BUISSON = 1.65

# Clarte moyenne du buisson TEL QUE LE JEU LE DESSINE, a teinte neutre. Comme
# pour l'herbe : la scene demande une couleur de buisson -- vert de pre en
# plaine, vert sombre de sous-bois en foret -- et l'image en prend la clarte,
# pas la couleur.
#
# CE N'EST PAS LA CLARTE DE L'IMAGE (0,297), et c'est ce qui l'avait rendu
# presque noir au premier essai : ses cartes de relief l'assombrissent. Ses
# feuilles regardent dans tous les sens, et une feuille tournee vers le
# soleil ne gagne pas autant que perd celle qui s'en detourne ; son occlusion
# creuse encore le coeur. Simule sur le shader (scratchpad/simule_pbr.py) :
# il en reste 69 %, a 8 h comme a 17 h. 0,297 x 0,69 = 0,205.
#
# Recale ainsi, le buisson de plaine retrouve la clarte de son ancien dessin
# (0,23 a midi) sans qu'un pixel sur cent ne sature.
CLARTE_BUISSON = 0.205

# Et sa COULEUR, un peu reprise : la photo tire sur le bleu-gris a cote de
# l'herbe de la plaine, franchement jaune. Moins de bleu la range dans la
# meme famille de verts (voir TEINTE_HERBE_RVB, la meme idee en plus fort).
TEINTE_BUISSON_RVB = (0.97, 1.00, 0.84)

# Luminance moyenne de l'image d'herbe livree, MESUREE (voir
# scratchpad/herbe_images.py). La scene teinte l'image pour retrouver la
# couleur que ses triangles avaient : le facteur vaut la clarte voulue divisee
# par celle-ci. Sans ce rapport, une seule image ne pourrait pas servir a la
# fois le sous-bois sombre et le champ en pleine lumiere.
CLARTE_HERBE = 0.395

# Bornes de cette teinte. Le plancher evite qu'un vert de sous-bois ne rende
# l'herbe noire ; le plafond, qu'une couleur trop claire ne la delave.
TEINTE_HERBE_MIN, TEINTE_HERBE_MAX = 0.45, 1.25

# LA COULEUR DE L'HERBE, ET NON PLUS SEULEMENT SA CLARTE. L'image livree est
# d'un vert froid, presque cyan (ses pointes : 0,42 0,65 0,29), alors que le
# sol de la plaine est un vert olive chaud (0,33 0,42 0,10) : posees dessus,
# les touffes semblaient decoupees dans une autre photo -- pales, et d'une
# autre lumiere. On retire donc une part de leur bleu et un soupcon de leur
# vert, ce qui les ramene dans la famille du sol sans les rendre jaunes.
TEINTE_HERBE_RVB = (1.00, 0.95, 0.66)

# COULEUR D'UNE TOUFFE DE PLAINE : celle que prendrait l'image d'origine,
# avant que son pied soit assombri (voir foliage.planche_ombree). Un peu plus
# sombre que le sol (0,31 de clarte contre 0,36) : les pointes arrivent a peu
# pres a la clarte du sol, le pied descend nettement en dessous -- c'est ce
# qui fait qu'une touffe se POSE sur le sol au lieu de flotter dessus en plus
# clair.
#
# LA MEME PARTOUT DANS LA PLAINE, du premier plan a la crete. L'herbe du fond
# etait autrefois eclaircie a la main (jusqu'a 1,24 fois l'image) pour faire
# la distance ; c'est desormais la BRUME qui s'en charge (voir _brume), et un
# vert qui palit tout seul par-dessus aurait fait la distance deux fois --
# d'ou les touffes vert vif sur le fond.
HERBE_PLAINE = (0.25, 0.37, 0.10)

# TEINTE DES PLANTES FEUILLUES (le trefle). La photo livree est d'un vert plus
# clair et plus froid que l'herbe teintee -- sa moyenne (77, 114, 44) contre
# (64, 94, 26) pour une touffe -- et ses touffes ressortaient donc en pale
# sur le champ. Cette teinte la ramene dans la meme famille.
TEINTE_PLANTE = (0.86, 0.84, 0.66)

# --- DESSIN DE L'HERBE PAR LOTS -------------------------------------------- #
# Plus de deux mille touffes par scene de plaine : dessinees une par une, cela
# ferait autant de dessins par image, et Kivy redessine TOUTE la scene a
# chaque image (le ciel bouge sans arret). Les touffes immobiles qui se
# suivent en profondeur partagent la meme planche et la meme teinte : on les
# pose donc dans un seul maillage (voir _dessine). Un maillage Kivy compte ses
# sommets sur 16 bits, soit 65 535 au plus : 4 000 touffes de 4 sommets
# restent tres en dessous.
LOT_HERBE_MAX = 4000

# --- LA BRUME DU LOINTAIN -------------------------------------------------- #
# Entre l'oeil et une colline eloignee il y a de l'air, et l'air diffuse la
# lumiere du ciel : ce qui est loin se rapproche de la couleur du CIEL A
# L'HORIZON. Il palit, bleuit, perd son contraste -- il ne fonce jamais. C'est
# la perspective aerienne, et c'est la regle que suit l'oeil pour juger d'une
# distance.
#
# Le fond de la plaine faisait l'inverse : il etait ASSOMBRI (x 0,82) pour se
# detacher du champ. L'oeil le lisait comme une zone d'ombre, et la crete se
# decoupait en vert sombre sur un ciel clair -- le plus fort contraste de
# l'image, la ou il aurait du etre le plus faible.
#
# Part de brume a la crete (0 = aucune, 1 = le ciel lui-meme). Par temps
# clair, une colline a un kilometre reste verte : elle palit et bleuit, elle
# ne disparait pas. Au-dela de 0,45 elle virait au gris-bleu d'un jour de
# brouillard.
BRUME_CRETE = 0.46
# Hauteur, au-dessus de la crete, que couvre encore le voile. LES TOUFFES DE
# LA CRETE depassent du sol sur le ciel : un voile qui s'arretait au ras de la
# crete laissait leur sommet net, et la ligne d'horizon se herissait de petits
# buissons vert sombre. Le voile garde donc sa pleine force sur une hauteur de
# touffe, puis s'efface dans le ciel -- ou il se voit a peine, puisqu'il est
# de la couleur du ciel.
BRUME_AU_DESSUS = 0.036
# Part de cette hauteur ou le voile reste a pleine force avant de s'effacer.
BRUME_PALIER = 0.55
# Comment la brume monte entre le champ proche et la crete : AU-DESSUS DE 1,
# elle reste legere sur la premiere moitie de la bande et s'epaissit vers le
# fond -- la distance, elle, croit de plus en plus vite a mesure qu'on
# approche de l'horizon.
BRUME_COURBE = 1.5
# La brume est plus BLANCHE que le ciel a l'horizon : pres du sol, l'air
# porte de la vapeur et des poussieres qui diffusent toutes les couleurs a peu
# pres autant. Sans cela les collines viraient au bleu franc.
BRUME_BLANCHE = 0.45

class _BordDuSol(object):
    """Le bord REEL d'un sol dessine par _fill_curve.

    Pas la courbe lisse qu'on lui a donnee : la courbe PLUS sa dentelure
    (voir _frange), telle que le maillage la trace -- des segments droits
    d'un sommet au suivant. C'est ce bord-la que l'oeil voit contre le ciel,
    et c'est donc sur lui qu'une touffe doit reposer. Posee sur la courbe
    lisse, elle flottait au-dessus de chaque creux de la dentelure."""

    def __init__(self, x0, largeur, sommets):
        self.x0 = float(x0)
        self.largeur = max(1.0, float(largeur))
        self.ys = list(sommets)
        self.n = max(1, len(self.ys) - 1)

    def _u(self, x):
        return min(float(self.n),
                   max(0.0, (x - self.x0) / self.largeur * self.n))

    def __call__(self, x):
        """Hauteur du bord a l'abscisse x (en pixels)."""
        u = self._u(x)
        i = min(self.n - 1, int(u))
        f = u - i
        return self.ys[i] + (self.ys[i + 1] - self.ys[i]) * f

    def plus_bas(self, xa, xb):
        """Le point le plus BAS du bord entre xa et xb. Le bord etant fait de
        segments droits, il est a l'un des deux bouts ou sur un sommet."""
        bas = min(self(xa), self(xb))
        ia = int(math.ceil(self._u(min(xa, xb))))
        ib = int(math.floor(self._u(max(xa, xb))))
        for i in range(ia, ib + 1):
            bas = min(bas, self.ys[i])
        return bas


_RAMPE_BRUME = []


def _rampe_brume():
    """La rampe d'opacite de la brume : une petite texture, blanche.

    Lue de bas en haut (v = 0 au bord du champ proche) : l'opacite monte
    jusqu'a BRUME_CRETE a mi-hauteur (v = 0,5 : la crete), tient ce palier
    sur la hauteur des touffes de crete, puis retombe a zero en haut (v = 1).
    C'est la Color du voile qui lui donne sa couleur."""
    if _RAMPE_BRUME:
        return _RAMPE_BRUME[0]
    n, larg = 64, 4
    octets = bytearray()
    for j in range(n):
        v = (j + 0.5) / n
        if v <= 0.5:
            a = BRUME_CRETE * (v / 0.5) ** BRUME_COURBE
        else:
            s = (v - 0.5) / 0.5
            s = max(0.0, (s - BRUME_PALIER) / (1.0 - BRUME_PALIER))
            a = BRUME_CRETE * (1.0 - s * s * (3.0 - 2.0 * s))
        octets += bytes((255, 255, 255, int(max(0.0, min(1.0, a)) * 255
                                             + 0.5))) * larg
    try:
        tex = texture_depuis_octets((larg, n), octets, wrap="clamp_to_edge",
                                    mag_filter="linear", min_filter="linear")
    except Exception:
        tex = None
    _RAMPE_BRUME.append(tex)
    return tex

# --- L'EAU DU LAC ------------------------------------------------------ #
# Trois couches, sur la meme surface :
#
#   1. LE FOND (water_B) : des cailloux sous une eau claire. IMMOBILE -- un
#      lit de riviere ne bouge pas, c'est l'eau qui passe dessus.
#   2. LE REFLET DU CIEL, nul au bord et de plus en plus fort vers la rive
#      d'en face. Vue de pres, une eau claire laisse voir son fond ; vue de
#      loin et de biais, elle renvoie le ciel. C'est la couleur du ciel
#      AFFICHE (voir _applique_brume) : bleue a midi, orange au couchant,
#      noire la nuit.
#   3. L'ECUME (water_E), en DEUX COUCHES qui derivent de gauche a droite,
#      pas a la meme vitesse ni a la meme echelle -- la seconde est aussi
#      retournee. Une seule couche glisserait d'un bloc, comme un tapis
#      roulant ; deux qui se croisent font des motifs qui se defont et se
#      refont, comme sur une vraie eau qui coule.
#
# LES VIGNETTES ANIMEES LIVREES AVEC L'EAU NE SERVENT PAS. Mesure faite sur
# les deux planches, elles ne s'enchainent pas : d'une vignette a la
# suivante, l'ecume change de place sans direction -- et sur la seconde, les
# cailloux eux-memes ne sont plus les memes. Jouees a la suite, elles
# clignoteraient. L'ecume tiree de la grande image, elle, derive dans UN
# sens.
#
# Le decalage de l'ecume se fait dans l'espace de la TEXTURE : sur l'eau en
# perspective, elle avance donc moins vite au loin a l'ecran, comme il se
# doit.
#
# LA VITESSE SE JUGE SUR LE TELEPHONE. La tuile fait 900 px quel que soit
# l'ecran : a 0,030 tuile par seconde, l'ecume avancait de 27 px/s, soit
# moins de 2 mm par seconde sur un ecran de 2340 px -- une eau qu'on croyait
# figee. Au double, elle derive encore calmement (il faut une quarantaine de
# secondes pour traverser l'ecran), mais on la VOIT couler.
#
# 30 images par seconde, comme les flammes : le ciel redessine deja l'ecran
# soixante fois par seconde, et deplacer l'ecume coute 0,02 ms.
#
# (echelle de la tuile, vitesse en tuiles par seconde, opacite, retournee)
ECUME_COUCHES = ((1.00, 0.060, 0.85, False),
                 (1.45, 0.048, 0.50, True))
ECUME_FPS = 30.0
# L'OPACITE DE L'EAU SUIT LA DISTANCE, PAS LA HAUTEUR A L'ECRAN.
#
# Ce qui rend une eau opaque au loin, c'est l'EPAISSEUR D'EAU TRAVERSEE par le
# regard : a nos pieds on la perce presque a la verticale et l'on voit les
# cailloux ; au loin on la rase, le trajet dans l'eau s'allonge, et il ne
# reste que le ciel qu'elle renvoie. Cette longueur croit comme la distance,
# et ce qui traverse s'eteint exponentiellement avec elle -- c'est la loi de
# Beer-Lambert, et elle vaut ici parce que c'est exactement le phenomene.
#
# La rampe recoit donc la DISTANCE NORMALISEE (0 au bord, 1 a la rive d'en
# face) et non la hauteur a l'ecran. Les deux ne se ressemblent pas : a
# mi-hauteur de la nappe, on n'est qu'a 22 % du chemin vers la rive d'en face
# (voir GROUND_DEPTH), et l'ancienne rampe y voyait 50 %.
#
# CE QUE CELA CHANGE, mesure a trois hauteurs (mi-nappe, 80 %, rive d'en
# face) : l'eau passait de 0,24 / 0,50 / 0,72 d'opacite a 0,48 / 0,79 / 0,95.
# Elle reste claire sur les premiers metres et se ferme franchement ensuite.
OPACITE_EAU_LOIN = 0.95    # opacite du reflet contre la rive d'en face
ABSORPTION_EAU = 3.0       # plus grand = l'eau se ferme plus vite

# --- LA BERGE D'EN FACE ---------------------------------------------------- #
# De l'autre cote de l'eau il y a une VRAIE case, et le jeu sait laquelle
# (voir horizon.zone_den_face). On lui donne donc sa plage et sa vegetation,
# avec les images du jeu -- les memes arbres, les memes buissons qu'au premier
# plan, simplement petits et noyes de brume.
#
# POURQUOI PAS LES SILHOUETTES DE horizon.py. Elles servent a reconnaitre un
# paysage a UN KILOMETRE, d'un coup d'oeil, et pour cela une tache dentelee
# suffit. La berge d'en face n'est pas a un kilometre : c'est l'autre bord
# d'un lac, on la regarde longtemps, et une frange d'ellipses vertes s'y lit
# pour ce qu'elle est.
#
# (nom de l'image, hauteur en part de la hauteur d'ecran, poids du tirage)
# Les noms absents du dossier des feuillages sont ecartes a l'usage : une
# berge ne reste jamais vide a cause d'une image qu'on n'a pas encore.
PLANTES_DE_BERGE = {
    "Foret": (("forest_tree", 0.085, 3), ("pine_tree", 0.105, 4),
              ("bush_forest", 0.026, 2), ("fern", 0.020, 1)),
    "Plaine": (("bush_plain", 0.034, 3), ("plant_leafy", 0.026, 2),
               ("grass_tuft", 0.020, 3), ("berries_bush", 0.028, 1)),
    "Montagne": (("pine_tree", 0.070, 3), ("boulder", 0.040, 2),
                 ("stone_mountain", 0.022, 1)),
    "Rive": (("reed", 0.032, 3), ("grass_tuft", 0.022, 2),
             ("bush_plain", 0.030, 1)),
}
# Faute de savoir ce qu'il y a en face (bord de carte, ou lac trop large),
# on met de l'herbe : neutre, et vrai a peu pres partout.
PLANTES_DE_BERGE_DEFAUT = (("grass_tuft", 0.022, 3), ("bush_plain", 0.030, 1))

# COMMENT LA VEGETATION SE REPARTIT SUR LA BERGE.
#
# Elle etait posee en DEUX RANGS, chacun a pas regulier le long de sa crete
# (un pied par tranche de largeur, plus un petit jeu). Trois defauts qui se
# voyaient tous les trois :
#
#   - un pas regulier donne une LIGNE D'ARBRES, et l'oeil la lit
#     immediatement comme une haie plantee par un jardinier ;
#   - deux rangs donnent deux lignes, donc un decor en couches ;
#   - tous les pieds d'une meme espece avaient EXACTEMENT la meme taille.
#
# On les repartit maintenant en PROFONDEUR, d'un seul tenant : chaque pied
# tire sa distance entre le bord de l'eau et la crete du fond, et tout en
# decoule -- sa hauteur a l'ecran, sa teinte, l'ordre ou on le dessine. C'est
# la meme idee que la perspective du sol, appliquee a des sprites.
PIEDS_DE_BERGE = 60

# LE GROUPEMENT. Une position tiree uniformement donne une repartition
# reguliere a l'oeil (c'est le paradoxe du hasard : l'uniforme ne fait pas de
# paquets). On tire donc d'abord des BOSQUETS, puis les arbres autour d'eux.
BOSQUETS_DE_BERGE = 9
# Etalement d'un bosquet, en fraction de la largeur d'ecran.
ETALEMENT_BOSQUET = 0.085
# Part des pieds poses hors bosquet, pour ne pas laisser de trou net.
ISOLES_DE_BERGE = 0.30

# De combien un pied rapetisse entre le bord de l'eau et la crete du fond.
RETRAIT_BERGE = 0.55
# Et de combien sa taille varie d'un pied a l'autre, a distance egale. Sans
# cela une lisiere a le sommet plat d'une haie taillee.
TAILLE_BERGE = (0.60, 1.55)

# LES EMERGENTS : la part des pieds qui DEPASSENT franchement, et de combien.
# C'est ce qui manquait le plus. Avec une simple variation de taille autour
# d'une moyenne, la lisiere reste un mur vert d'epaisseur reguliere ; ce qui
# fait lire une foret de loin, c'est quelques houppiers qui percent la ligne
# et decoupent le ciel. Dans un vrai peuplement ce sont les arbres murs, et
# ils sont toujours une minorite.
EMERGENTS_DE_BERGE = 0.14
EMERGENT_FACTEUR = (1.5, 2.2)

# Epaisseur de la plage de sable de la berge, en part de la hauteur d'ecran.
#
# LA PLAGE A ETE EPAISSIE APRES COUP. A 0,012 elle existait -- cinq pixels sur
# un apercu de 400 -- mais on ne la voyait pas : l'eau touchait l'herbe, et
# c'est precisement ce qu'on voulait corriger. A 0,026 elle fait cinquante
# pixels sur un ecran de 1920, assez pour se lire comme une greve sans devenir
# une dune.
SABLE_DEN_FACE = 0.026

# La vegetation de la berge est plus SOMBRE que celle du premier plan, avant
# meme la brume : elle est vue de loin et de biais, on y voit surtout les
# faces ombrees. La brume l'eclaircira ensuite par-dessus.
TEINTE_BERGE = 0.72

_RAMPE_EAU = []


def _rampe_eau():
    """La rampe d'opacite du reflet : 0 au bord (v = 0), OPACITE_EAU_LOIN en
    face (v = 1), avec v qui porte la DISTANCE et non la hauteur a l'ecran.

    Blanche : c'est la Color du reflet qui lui donne la couleur du ciel."""
    if _RAMPE_EAU:
        return _RAMPE_EAU[0]
    n, larg = 64, 4
    plein = 1.0 - math.exp(-ABSORPTION_EAU)      # pour finir pile au but
    octets = bytearray()
    for j in range(n):
        d = (j + 0.5) / n
        a = OPACITE_EAU_LOIN * (1.0 - math.exp(-ABSORPTION_EAU * d)) / plein
        octets += bytes((255, 255, 255, int(a * 255 + 0.5))) * larg
    try:
        tex = texture_depuis_octets((larg, n), octets, wrap="clamp_to_edge",
                                    mag_filter="linear", min_filter="linear")
    except Exception:
        tex = None
    _RAMPE_EAU.append(tex)
    return tex


# Force du vent par meteo : le decor se courbe quand il souffle.
_WIND = {"clair": 0.55, "nuageux": 0.9, "pluie": 1.5, "neige": 1.0,
         "orage": 2.6, "blizzard": 3.0}
_WIND_DEFAULT = 0.8

# Ombre portee : aplatissement de l'ellipse (x la largeur de l'objet).
_SHADOW_FLAT = 0.30

# --- PROFONDEUR DU SOL ----------------------------------------------------- #
# Le sol est vu EN OBLIQUE, pas de face : ce qui est loin doit paraitre plus
# petit. Une texture simplement repetee a taille constante donne au contraire
# un papier peint -- l'oeil n'y lit aucune distance.
#
# On traite donc le sol comme un PLAN vu par une camera. A la profondeur t
# (0 en bas de l'ecran, 1 sur la crete), la distance vaut :
#
#       k(t) = 1 / (1 - t * (1 - 1/GROUND_DEPTH))
#
# soit 1 au premier plan et GROUND_DEPTH au fond. La texture n'est plus
# indexee par la position a l'ecran mais par CETTE distance : les tuiles se
# resserrent en montant (v) et s'ecartent du point de fuite (u), donc
# retrecissent dans les deux sens a la fois. C'est le sol des vieux jeux
# "mode 7".
#
# GROUND_DEPTH = de combien de fois le fond est PLUS LOIN que le premier plan.
# Attention, la tuile ne retrecit pas du meme facteur dans les deux sens : un
# sol vu en oblique est vu de plus en plus RASANT a mesure qu'il s'eloigne. Au
# fond, la tuile est donc GROUND_DEPTH fois plus etroite mais GROUND_DEPTH AU
# CARRE fois plus BASSE -- c'est cet ecrasement qui fait que l'oeil lit un sol
# qui file au loin, et non un mur.
#
# D'ou une valeur mesuree : a 3.6, la tuile d'herbe (448 px au sol) fait
# encore ~124 x 35 px sur la crete. La profondeur saute aux yeux et l'image
# reste lisible ; plus haut, elle se reduirait a quelques pixels de bouillie.
# Mettre 1.0 revient a l'ancienne repetition reguliere, sans profondeur.
GROUND_DEPTH = 3.6

# Nombre de bandes horizontales du maillage du sol. La perspective est une
# COURBE, mais la carte graphique interpole en LIGNE DROITE d'un sommet a
# l'autre : trop peu de bandes et la courbe se voit en segments. Les bandes
# sont reparties par distance egale, donc serrees pres de la crete, la ou tout
# change vite.
GROUND_ROWS = 14

# --------------------------------------------------------------------- #
# LE SOL SOUS LE BAS DE L'ECRAN (voir ZoneScenery.sous_sol)
# --------------------------------------------------------------------- #
# Quand le joueur baisse les yeux (ecran de craft), la camera GLISSE vers le
# bas : toute la scene monte a l'ecran, telle quelle, sans qu'un seul element
# change de taille ou de place par rapport a lui. Il faut donc du sol sous le
# bas de l'ecran -- celui qu'on decouvre en se penchant.
#
# CE SOL CONTINUE CELUI DE LA SCENE, A L'IDENTIQUE : meme image, meme tuile,
# et la meme perspective prolongee de l'autre cote du bord. Au bas de l'ecran
# la scene pose sa texture avec k = 1 ; en dessous, on est plus pres encore,
# k descend sous 1 et la tuile grandit -- par la meme formule que _fill_curve,
# si bien qu'il n'y a pas de couture au raccord, ni dans l'image ni dans son
# echelle.
#
# Le sol qui touche le bas de l'ecran, par scene : (surface, perspective).
# La montagne finit sur sa bande sombre, sans image (voir _montagne) ; le lac
# sur la bande de rive, traitee a part (voir _sous_sol_rive).
SOL_DU_BAS = {
    "Foret": ("forest_floor", GROUND_DEPTH),
    "Plaine": ("grass", GROUND_DEPTH),
    "Montagne": ("rock_dark", 1.0),
}
# Rangees du maillage sous l'ecran : la perspective y est une courbe, comme
# au-dessus (voir GROUND_ROWS).
SOUS_SOL_RANGEES = 16
# Touffes semees sous l'ecran, pour une profondeur egale a la hauteur de
# l'ecran : le bas de la scene en est couvert, et un sol nu juste dessous se
# lirait comme un trait tire en travers. Elles sont DECORATIVES (rien de plus
# a ramasser) et grandissent a mesure qu'on s'approche.
TOUFFES_SOUS_SOL = {"Foret": 700, "Plaine": 620}
# Dans l'image de rive (rive_B), la ligne ou commence le sable SEC, en v
# compte depuis le haut. Au-dessus, c'est deja l'eau qui lape : sous l'ecran,
# on ne montre que le sable, en miroir aller-retour (voir _sous_sol_rive).
V_SABLE_SEC = 0.62

# Fleurs de plaine : couleur de repli ET image correspondante. On tire la
# PAIRE d'un coup : sans cela, une fleur tiree "jaune" pouvait se voir poser
# l'image d'une fleur rouge.
_FLOWERS = (((1.00, 1.00, 0.92, 1), "flower_white"),
            ((0.96, 0.85, 0.28, 1), "flower_yellow"),
            ((0.92, 0.42, 0.52, 1), "flower_red"),
            ((0.72, 0.52, 0.92, 1), "flower_purple"),
            ((0.46, 0.58, 0.94, 1), "flower_blue"))

# Image du decor propre a chaque zone : une pierre de foret est moussue, une
# pierre de montagne est nue. Le decor pioche ici plutot que de coder le nom
# en dur a chaque appel.
_ZONE_SPRITES = {
    "Foret":    {"stone": "stone_forest", "branch": "branch_forest",
                 "bush": "bush_forest", "plant": "fern",
                 "mushroom": "mushroom_forest"},
    "Plaine":   {"stone": "stone_plain", "branch": "branch_plain",
                 "bush": "bush_plain", "plant": "plant_leafy",
                 "mushroom": "mushroom_forest"},
    "Montagne": {"stone": "stone_mountain", "branch": "branch_plain",
                 "bush": "bush_plain", "plant": "plant_leafy",
                 "mushroom": "mushroom_forest"},
    "Lac":      {"stone": "pebble", "branch": "branch_plain",
                 "bush": "bush_plain", "plant": "plant_leafy",
                 "mushroom": "mushroom_forest"},
}


class ZoneScenery(Widget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._zone = "Foret"
        self._seed = 0
        self._mode = "scene"        # "scene" = vue horizon ; "ground" = vue sol
        # Profondeur de sol dessinee SOUS le bas de l'ecran, en part de la
        # hauteur (voir SOL_DU_BAS). Nulle d'ordinaire : seul l'ecran de craft
        # en demande, pour que sa camera puisse se pencher.
        self.sous_sol = 0.0
        # Ce que montre_la_case a dessine en dernier (None : rien de connu).
        self._cle_case = None
        # L'APERCU de l'objet qu'on pose (voir montre_apercu) : son nom, les
        # places reservees pour lui dans la scene (une par rangee de la
        # grille), et ce qui y est dessine en ce moment.
        self._apercu_nom = None
        self._apercu_places = {}
        self._apercu_vu = None
        # L'ecume qui derive sur l'eau (voir _surface_eau) et son horloge.
        self._eau = []
        self._eau_t = 0.0
        self._eau_ev = None
        # La rive animee du lac (voir rive.py), sur la meme horloge.
        self._rive = None
        # Recolte : nombre deja recolte par objet (applique au dessin pour
        # MASQUER les objets recoltes) et totaux/budgets calcules a la
        # construction de la scene.
        self._taken = {}
        self._neighbours = {}
        self._berge = None
        self._ord = {}
        self._harvest_total = {}
        self._avail = {}            # {nom: nb recoltable} (aleatoire, par case)
        self.harvest_total = {}     # {nom: total visible dans la scene}
        self.harvest_max = {}       # {nom: nombre de recoltes possibles}
        # Cellules 5x5 occupees par un objet INSTALLE (fire pit, ...) :
        # les objets du decor qui tombent dans la zone visuelle de ces
        # cellules ne sont PAS dessines. Recalcule en debut de _redraw.
        self._blocked_grid = set()
        self._blocked_bboxes = []
        # Objets INSTALLES sur la case : [(nom, gx, gy), ...]. Ils sont
        # dessines DANS la scene (et non dans une couche au-dessus) pour que
        # le tri par profondeur s'applique aussi a eux : un feu de camp pose
        # derriere un buisson passe donc bien DERRIERE ce buisson.
        self._installed = []
        # Cellules dont le GROS element a ete RETIRE (arbre abattu) : elles
        # restent vides, contrairement aux cases bloquees par un objet pose,
        # qui masquent en plus les petits objets du sol.
        self._removed_grid = set()
        # Flammes ANIMEES : les instructions de dessin sont creees une seule
        # fois avec la scene (donc a la bonne profondeur, masquees par ce qui
        # est devant), puis seules leurs coordonnees et leur opacite changent
        # a chaque image. L'horloge ne tourne que s'il y a un feu allume.
        self._flames = []
        self._flame_ev = None
        self._flame_t = 0.0
        # Heure de la scene (midi par defaut) : commande la couleur de la
        # lumiere et la direction des ombres.
        self._seconds = 12 * 3600.0
        # Ombres portees deja dessinees : on les DEPLACE quand le soleil
        # tourne, au lieu de reconstruire la scene.
        self._shadows = []
        # Touffes animees par le vent + leur horloge (voir SWAY).
        self._sway = []
        self._sway_ev = None
        self._sway_t = 0.0
        self._wind = _WIND_DEFAULT
        # Herbe en attente d'etre dessinee d'un seul coup (voir _dessine) ;
        # None hors d'un dessin trie. Et la hauteur a partir de laquelle une
        # touffe ondule au vent -- celles-la sont dessinees une par une.
        self._lot = None
        self._seuil_vent = 0.0
        # Brume du lointain (voir _brume) : son instruction de couleur, et la
        # couleur du ciel a l'horizon telle que le fond l'affiche (None tant
        # que personne ne l'a donnee : on la lit alors dans la LUT du ciel).
        self._brume_couleur = None
        self._brume_ciel = None
        # Eclairage par shader. Il est desormais installe DES QUE l'eclairage
        # est actif, et non plus seulement quand des cartes de normales
        # existent : c'est lui qui porte aussi la COULEUR de la lumiere (doree
        # le matin, orange au couchant, bleue la nuit), qui doit fonctionner
        # meme sans aucune texture. Sans carte Normal, les cartes neutres
        # rendent le relief exactement nul : le rendu reste celui d'avant.
        self._pbr = pbr.LIGHTING
        if self._pbr:
            self.canvas = RenderContext(use_parent_projection=True,
                                        use_parent_modelview=True,
                                        use_parent_frag_modelview=True)
            pbr.setup(self.canvas)
        self.bind(pos=self._redraw, size=self._redraw)

    # -- heure du jour : lumiere et ombres ------------------------------- #
    def set_daylight(self, seconds):
        """Cale la scene sur l'heure : couleur de la lumiere et ombres.

        Aucune forme n'est recreee : on retouche les uniformes du shader et on
        replace les ombres existantes. Appelable a chaque rafraichissement sans
        crainte."""
        self._seconds = float(seconds)
        self._apply_light()
        self._applique_brume()
        off, length, alpha = daylight.shadow(self._seconds)
        for sh in self._shadows:
            self._place_shadow(sh, off, length, alpha)

    def set_brume(self, ciel):
        """Donne la couleur du CIEL A L'HORIZON telle que le fond l'affiche.

        C'est vers elle que le lointain se fond (voir _brume). La lire ici,
        plutot que la recalculer, fait suivre la brume a TOUT ce que le fond
        applique au ciel -- la meteo comprise, et ses transitions : un ciel
        qui se couvre grise aussi les collines, au meme rythme.

        Comme set_daylight, cela ne redessine rien : une seule couleur change."""
        self._brume_ciel = tuple(float(v) for v in ciel[:3])
        self._applique_brume()

    def _ciel_horizon(self):
        """Couleur du ciel a la hauteur de la crete (voir set_brume)."""
        if self._brume_ciel is not None:
            return self._brume_ciel
        colonne = animated_background.sky_column(self._seconds)
        if colonne:
            i = int(max(0.0, min(1.0, self.hauteur_horizon()))
                    * (len(colonne) - 1))
            return tuple(colonne[i])
        return tuple(animated_background.sky_color(self._seconds))

    def _applique_brume(self):
        """Colore la brume. Aucune forme n'est recreee.

        LA TEINTE DE LA LUMIERE EST RETIREE : le shader de la scene multiplie
        tout ce qu'il dessine par elle (doree le matin, orange au couchant),
        or la brume n'est pas une surface eclairee -- c'est la lumiere du ciel
        elle-meme. Sans cette division, la crete aurait pris au couchant un
        orange plus sombre que le ciel juste au-dessus, et la ligne d'horizon
        serait reapparue."""
        if not self._brume_couleur:
            return
        r, g, b = self._ciel_horizon()
        lum = min(1.0, (0.3 * r + 0.6 * g + 0.1 * b) * 1.15)
        teinte = (daylight.light_tint(self._seconds) if self._pbr
                  else (1.0, 1.0, 1.0))
        for c, k in self._brume_couleur:
            brume = (r + (lum - r) * k, g + (lum - g) * k, b + (lum - b) * k)
            c.rgb = tuple(brume[i] / max(0.05, teinte[i]) for i in range(3))

    def set_wind(self, kind):
        """Force du vent, d'apres la meteo : le decor se courbe davantage."""
        self._wind = _WIND.get(kind, _WIND_DEFAULT)

    def force_du_vent(self):
        """La force du vent RAMENEE ENTRE 0 ET 1.

        _WIND donne un multiplicateur non borne (0,55 par temps clair, 3,0 en
        blizzard). C'est commode pour l'herbe, dont l'amplitude est petite et
        qui peut se coucher franchement. Le feuillage d'un arbre demande au
        contraire une grandeur BORNEE : au-dela de 1 la grille se cisaillerait
        au lieu de bruire, et les feuilles glisseraient les unes sur les
        autres."""
        return min(1.0, self._wind / _WIND["blizzard"])

    def _apply_light(self):
        if self._pbr:
            pbr.set_light(self.canvas, daylight.light_dir(self._seconds),
                          daylight.light_tint(self._seconds))
        # La rive a son propre shader : elle recoit la meme lumiere.
        if self._rive is not None:
            rive.teinte(self._rive, daylight.light_tint(self._seconds))

    def _place_shadow(self, sh, off, length, alpha):
        """Etire et decale une ombre selon la position de l'astre."""
        w = sh["w"] * length
        h = sh["w"] * _SHADOW_FLAT
        cx = sh["cx"] + off * sh["w"]
        sh["e"].pos = (cx - w / 2.0, sh["y"] - h / 2.0)
        sh["e"].size = (w, h)
        sh["c"].a = alpha * sh["k"]

    def _shadow(self, cx, base, width, opacity=1.0):
        """Ombre portee au sol, orientee par l'heure.

        A appeler DANS un bloc `with canvas`, AVANT l'element lui-meme. Avant,
        chaque element ecrivait son ombre en dur, toujours au meme endroit et
        a la meme opacite : a midi comme au couchant, toutes les ombres
        tombaient du meme cote. Elles sont desormais enregistrees ici et
        suivent le soleil (voir set_daylight)."""
        off, length, alpha = daylight.shadow(self._seconds)
        sh = {"c": Color(0, 0, 0, 0), "e": Ellipse(),
              "cx": cx, "y": base, "w": float(width), "k": opacity}
        self._shadows.append(sh)
        self._place_shadow(sh, off, length, alpha)

    # -- liaison des cartes PBR (normal/packed) pour une surface ---------- #
    def _bind_pbr(self, name):
        if self._pbr:
            pbr.bind_maps(textures.normal_texture(name),
                          textures.packed_texture(name))

    def _reset_pbr(self):
        if self._pbr:
            pbr.reset_maps()

    def set_scene(self, zone_type, seed=0, taken=None, blocked_grid=None,
                  installed=None, removed_grid=None, neighbours=None,
                  berge=None):
        """Vue a l'horizon (sol en bas + ciel).

        `taken` = {nom: nombre deja recolte} pour masquer les objets recoltes.
        `installed` = [(nom, gx, gy[, allume[, niveau]]), ...] : objets poses
        sur la case. Ils sont dessines dans la scene, a leur profondeur ; un
        foyer allume y montre ses flammes, hautes ou basses selon `niveau`
        ("grand", "moyen", "petit", "braise").
        `removed_grid` = iterable de (gx, gy) : gros elements ABATTUS, qui ne
        sont plus dessines du tout.
        `blocked_grid` = iterable de (gx, gy) : cellules occupees par un objet
        INSTALLE (feu de camp, ...) ; deduit de `installed` si absent. Les
        objets du decor qui tombent dans la zone visuelle d'une case bloquee ne
        sont PAS dessines (mais restent collectables via explorer : le budget
        de recolte est preserve).
        `neighbours` = {"face"/"gauche"/"droite": type de zone ou None} : les
        cases voisines, qui apparaissent en silhouette a l'horizon (voir
        horizon.py). Depend de l'ORIENTATION du joueur, donc tourner change le
        fond de la scene.
        `berge` = le type de zone qu'il y a VRAIMENT de l'autre cote de l'eau
        (voir horizon.zone_den_face). La berge d'en face du lac s'y peuple de
        ses vrais arbres et de ses vraies plantes."""
        # Un appel direct ne dit pas de quelle case il s'agit : montre_la_case
        # ne peut plus rien supposer de ce qui est dessine.
        self._cle_case = None
        self._zone = SCENE_DE_ZONE.get(zone_type, zone_type)
        self._seed = seed
        self._mode = "scene"
        self._taken = dict(taken or {})
        self._installed = [(o[0], int(o[1]), int(o[2]),
                            bool(o[3]) if len(o) > 3 else False,
                            o[4] if len(o) > 4 else "grand")
                           for o in (installed or [])]
        if blocked_grid is None:
            # L'EMPRISE, pas seulement l'ancrage : un plan de construction
            # couvre quatre cases, et le decor doit s'ecarter des quatre.
            blocked_grid = [c for n, gx, gy, _l, _v in self._installed
                            for c in items.footprint_cells(n, gx, gy)]
        self._blocked_grid = set((int(g[0]), int(g[1]))
                                 for g in (blocked_grid or []))
        self._removed_grid = set((int(g[0]), int(g[1]))
                                 for g in (removed_grid or []))
        self._neighbours = {cote: SCENE_DE_ZONE.get(z, z)
                            for cote, z in (neighbours or {}).items()}
        # PAS DE SCENE_DE_ZONE ICI : une rive d'en face doit rester une rive.
        # La table rabat "Rive" sur "Lac" pour choisir quelle scene dessiner,
        # ce qui est juste quand on s'y tient -- on y voit le lac -- mais faux
        # pour ce qu'on regarde au loin : une rive porte du sable et des
        # roseaux, pas une seconde etendue d'eau.
        self._berge = berge
        self._redraw()

    def montre_la_case(self, state, apercu=None):
        """La case ou se tient le joueur, TELLE QU'ELLE EST MAINTENANT.

        `apercu` : le nom de l'objet qu'on s'apprete a poser, s'il y en a un.
        La scene lui reserve alors sa place a chaque profondeur ou il pourrait
        tomber (voir montre_apercu).

        Arbres abattus, objets recoltes, objets poses (et l'etat de leur feu),
        cases voisines : tout vient de l'etat du jeu, ici et nulle part
        ailleurs. Chaque ecran qui montre la scene de la case passe par la.

        C'EST CE QUI MANQUAIT. L'ecran de jeu et la fenetre d'action du foyer
        preparaient chacun leur decor de leur cote, et la fenetre avait oublie
        les arbres abattus : ils y repoussaient. Elle ne redessinait pas non
        plus apres une recolte, sa cle de cache ne regardant ni les recoltes
        ni les abattages -- une pierre ramassee y restait par terre.

        Ne redessine que si quelque chose a change depuis le dernier appel.
        Les recoltes se comparent a ce qui est DESSINE (self._taken), et non a
        une cle : set_taken peut les avoir deja appliquees, et la scene ne
        doit pas se refaire une seconde fois pour rien."""
        taken = state.harvested_here()
        decor = {
            "zone_type": state.current_zone(),
            "seed": world.scene_seed(state.player_x, state.player_y),
            # L'EMPRISE de chaque objet, pas seulement son ancrage : un plan
            # de construction couvre quatre cases, et le decor doit s'ecarter
            # des quatre.
            "blocked_grid": tuple(sorted(state.installed_cells_here())),
            # L'etat ALLUME en fait partie : la scene se redessine donc
            # (flammes) des que le feu prend, et de nouveau quand il meurt.
            "installed": tuple(state.scene_installed()),
            "removed_grid": tuple(sorted(state.chopped_here())),
            # Les cases VOISINES dependent de l'orientation : tourner sur
            # place doit redessiner le fond.
            "neighbours": horizon.neighbours_of(state),
            # Ce qu'il y a VRAIMENT de l'autre cote de l'eau, par-dela le lac
            # (voir horizon.zone_den_face). Dans la cle, donc : tourner le dos
            # a une foret pour faire face a une montagne redessine la berge.
            "berge": horizon.zone_den_face(state),
        }
        cle = tuple((k, tuple(sorted(v.items())) if isinstance(v, dict)
                     else v) for k, v in sorted(decor.items())) + (apercu,)
        if (self._mode == "scene" and cle == self._cle_case
                and dict(taken) == self._taken):
            return
        self._apercu_nom = apercu
        self.set_scene(taken=taken, **decor)
        self._cle_case = cle

    # -- apercu de pose -------------------------------------------------- #
    #
    # PENDANT QU'ON GLISSE UN OBJET SUR LA GRILLE, IL SE POSE AUSSI DANS LA
    # SCENE, en direct, la ou il tomberait. On voit donc le resultat -- sa
    # taille, ce qui le cache, ce qu'il cache -- avant de lacher.
    #
    # SANS REDESSINER LA SCENE. La refaire a chaque case survolee couterait
    # des dixiemes de seconde sur un telephone, et le glisse saccaderait. La
    # scene RESERVE donc, au moment ou elle se dessine, une place vide dans
    # son ordre de profondeur pour chaque rangee de la grille -- la ou l'objet
    # pose se trierait (voir _dessine). Pendant le geste, on ne fait que
    # dessiner l'objet dans la bonne place, et l'effacer de l'ancienne : ce
    # qui est plus pres que lui passe devant, comme une fois pose.
    #
    # Une seule chose differe du resultat final : le decor de sa case n'est
    # pas ecarte (voir _is_blocked). Une touffe qui pousse la le recouvre
    # encore un peu ; elle disparaitra a la pose.

    def _places_apercu(self):
        """[(cle de tri, gy)] des rangees ou l'objet a poser peut s'ancrer,
        de la plus LOINTAINE a la plus proche.

        La cle d'un objet ne depend que de sa rangee (voir grid_to_screen :
        la profondeur ne tient qu'a gy), d'ou une place par rangee et non par
        case."""
        if not self._apercu_nom or self._mode != "scene":
            return []
        _fw, fh = items.footprint(self._apercu_nom)
        out = []
        for gy in range(0, 5 - fh + 1):
            objet = self._objet_pose(self._apercu_nom, 0, gy)
            if objet is not None:
                out.append((objet[0], gy))
        out.sort(reverse=True)
        return out

    def _reserve_place(self, gy):
        """Pose une place vide dans le canvas, a l'endroit ou l'on dessine."""
        self._vide_lot()          # l'herbe en attente passe avant elle
        self._apercu_places[gy] = Canvas()

    def montre_apercu(self, gx=None, gy=None, ok=True):
        """Dessine l'objet a poser en (gx, gy) -- ou l'efface si gx est None.

        `ok` : la pose y est-elle permise ? Sinon, pas d'objet : une empreinte
        rouge au sol, de la taille qu'il prendrait -- la grille dit deja
        pourquoi en rouge, la scene montre ou."""
        self._efface_apercu()
        if gx is None or not self._apercu_nom:
            return
        place = self._apercu_places.get(gy)
        objet = self._objet_pose(self._apercu_nom, gx, gy)
        if place is None or objet is None:
            return
        # Ce que l'objet inscrit en dessinant (ombres a tourner avec le
        # soleil, flammes, feuillage au vent) : on le note pour le retirer
        # avec lui.
        avant = (len(self._shadows), len(self._flames), len(self._sway))
        with place:
            if ok:
                objet[1]()
            else:
                self._empreinte_refus(self._apercu_nom, gx, gy)
        self._apercu_vu = (place, self._shadows[avant[0]:],
                           self._flames[avant[1]:], self._sway[avant[2]:])
        self._sync_flame_clock()

    def _efface_apercu(self):
        vu, self._apercu_vu = self._apercu_vu, None
        if vu is None:
            return
        place, ombres, flammes, feuillages = vu
        place.clear()
        for liste, retires in ((self._shadows, ombres),
                               (self._flames, flammes),
                               (self._sway, feuillages)):
            for x in retires:
                if x in liste:
                    liste.remove(x)
        self._sync_flame_clock()

    def _empreinte_refus(self, name, gx, gy):
        """L'emprise au sol de l'objet, en rouge : ici, il ne tient pas."""
        fw, fh = items.footprint(name)
        if fw == 1 and fh == 1:
            fx, fy, size = self.grille(gx, gy)
            s = size * self.width
            cx, cy = self.x + fx * self.width, self.y + fy * self.height
            h = s * _PLAT_PROFONDEUR
            Color(1.0, 0.30, 0.25, 0.35)
            Ellipse(pos=(cx - s / 2.0, cy - h / 2.0), size=(s, h))
            Color(1.0, 0.42, 0.35, 0.90)
            Line(ellipse=(cx - s / 2.0, cy - h / 2.0, s, h),
                 width=max(1.5, s * 0.012))
            return
        coins = self._emprise_coins(name, gx, gy)
        pts = [v for c in coins for v in c]
        Color(1.0, 0.30, 0.25, 0.35)
        Quad(points=pts)
        Color(1.0, 0.42, 0.35, 0.90)
        Line(points=pts, close=True,
             width=max(1.5, (coins[1][0] - coins[0][0]) * 0.012))

    def set_taken(self, taken):
        """Met a jour les objets recoltes (masques) et redessine la scene."""
        self._taken = dict(taken or {})
        self._redraw()

    def _avail_for(self, name):
        """Nombre d'objets de ce type RECOLTABLES sur la case (petit, aleatoire
        mais stable pour une case donnee)."""
        if name not in self._avail:
            rng = random.Random(f"{self._seed}:{self._zone}:{name}:avail")
            self._avail[name] = rng.randint(_AVAIL_MIN, _AVAIL_MAX)
        return self._avail[name]

    def _take_or_skip(self, name):
        """Compte un objet recoltable et dit s'il faut le MASQUER (deja recolte).
        A appeler pour CHAQUE objet recoltable lors de la construction.

        Chaque recolte retire une PART EGALE des objets visibles : avec `avail`
        recoltes possibles, la k-ieme recolte a masque ~k/avail des objets."""
        i = self._ord.get(name, 0)
        self._ord[name] = i + 1
        self._harvest_total[name] = self._ord[name]
        taken = self._taken.get(name, 0)
        return (i % self._avail_for(name)) < taken

    # OU S'ARRETE LE SOL DE CHAQUE ZONE, en part de la hauteur de l'ecran :
    # le point le plus BAS de sa surface proche, celle ou reposent les
    # elements. C'est la valeur sur laquelle la grille se resserre.
    #
    # ON PREND LE MINIMUM de la courbe, pas sa valeur a l'endroit exact de la
    # case. Le sol ondule, et suivre l'ondulation aurait demande de connaitre
    # les phases tirees au sort A L'INTERIEUR de chaque scene -- or la grille
    # est aussi lue AVANT le dessin (les cases bloquees) et DEHORS (le toucher,
    # dans game_screen). Au minimum, un element du fond est au pire pose un peu
    # en avant de la crete ; il n'est JAMAIS en l'air, et c'est ce qui compte.
    #
    # Les zones absentes gardent la grille d'origine : la pente de la montagne
    # commence a 0,60 et le lac s'etend jusqu'a 0,60, tous deux au-dessus de
    # la derniere rangee -- rien n'y flotte.
    SOL_DE_GRILLE = {
        "Foret": 0.42 - 0.025 - 0.012,          # voir floor_curve dans _foret
        "Plaine": (0.55 - 0.06 - 0.13) - 0.030 - 0.014,   # voir field_curve
    }

    # OU LE SOL RENCONTRE LE CIEL, en part de la hauteur de l'ecran : la CRETE
    # de la scene. C'est le POINT DE FUITE DES NUAGES -- en s'eloignant ils s'y
    # rapetissent et s'y tassent (voir animated_background).
    #
    # ON PREND LA VALEUR MOYENNE de la courbe, et non son maximum comme le fait
    # SOL_DE_GRILLE juste au-dessus. Les deux ne servent pas a la meme chose :
    # la grille doit garantir que RIEN NE FLOTTE, elle prend donc le pire cas ;
    # les nuages doivent converger la ou l'oeil lit l'horizon, c'est-a-dire au
    # milieu de l'ondulation. Et le terrain, dessine par-dessus, cache l'ecart.
    #
    # CES QUATRE VALEURS SONT TRES DIFFERENTES, et c'est pour cela qu'il a fallu
    # ce dictionnaire plutot qu'une constante : entre la foret et le lac,
    # l'horizon se deplace de presque un quart de la hauteur de l'ecran. Une
    # valeur unique aurait fait flotter les nuages lointains bien au-dessus de
    # la ligne d'eau -- exactement le defaut qu'on cherche a corriger.
    CRETE = {
        "Foret": 0.42 + 0.05,       # voir horizon_curve dans _foret
        "Plaine": 0.55 - 0.06,      # voir edge / horizon_curve dans _plaine
        "Montagne": 0.60,           # surf(0.0) : le pied de la pente
        # LE LAC, C'EST 0,75 ET NON 0,70. On avait pris 0,70, qui est la
        # hauteur ou _lac appelle _horizon -- mais _horizon dessine les
        # silhouettes LOINTAINES, derriere la scene. Le sol, lui, ce sont les
        # collines d'herbe, dont la mesure donne un profil de 0,711 a 0,760.
        # A 0,70 les nuages auraient converge SOUS le sol.
        "Lac": 0.75,                # voir colline() dans _lac
    }

    # Pour les ecrans SANS scene (menu, inventaire, atelier...) : il n'y a pas
    # de sol, mais les nuages ont quand meme besoin d'un point de fuite.
    CRETE_DEFAUT = 0.49

    def _dessine_sous_sol(self):
        """Le sol sous le bas de l'ecran (voir SOL_DU_BAS), et ses touffes.

        DESSINE APRES LA SCENE, et c'est voulu : ce sol est plus PRES que tout
        ce qu'elle montre. Ses touffes qui depassent le bord de l'ecran passent
        donc devant le premier plan, comme elles le doivent -- dessinees
        avant, elles auraient ete recouvertes par le sol de la scene, et
        coupees net sur la ligne du bord.

        Son hasard est A PART : la scene ne tire pas un nombre de plus, et
        rien de ce qu'elle montre ne bouge."""
        w, h, x0, y0 = self.width, self.height, self.x, self.y
        prof = self.sous_sol * h
        if self._zone == "Lac":
            self._sous_sol_rive(prof)
            return
        nom, depth = SOL_DU_BAS.get(self._zone, SOL_DU_BAS["Plaine"])
        tile_px = textures.tile_for(nom)
        tex = paint(nom)
        self._bind_pbr(nom)
        tile_v = tile_px * textures.rapport(tex) if tex is not None \
            else tile_px
        depth = max(1.0, float(depth))
        a = 1.0 - 1.0 / depth
        # Le haut du sol proche, dont la perspective se prolonge ici. La crete
        # de la zone en est la mesure moyenne.
        haut = max(1.0, self.hauteur_horizon() * h)
        cx = x0 + w / 2.0
        colonnes = 6
        verts, ks = [], []
        for j in range(SOUS_SOL_RANGEES + 1):
            yy = y0 - prof * (1.0 - j / float(SOUS_SOL_RANGEES))
            k = self._k_sous_sol(yy, a, haut)
            ks.append((yy, k))
            for i in range(colonnes + 1):
                x = x0 + w * i / float(colonnes)
                # LA FORMULE DE _fill_curve : a yy = y0, k = 1 et l'on
                # retombe exactement sur sa rangee du bas.
                verts += [x, yy, (x - cx) * k / tile_px,
                          -(yy - y0) * k / tile_v]
        idx = []
        n = colonnes + 1
        for j in range(SOUS_SOL_RANGEES):
            for i in range(colonnes):
                p = j * n + i
                q = p + n
                idx += [p, p + 1, q + 1, p, q + 1, q]
        Mesh(vertices=verts, indices=idx, mode="triangles", texture=tex)
        self._reset_pbr()

        nb = TOUFFES_SOUS_SOL.get(self._zone, 0)
        if not nb:
            return
        # Le nombre suit la profondeur demandee : la densite reste celle du
        # bas de la scene.
        nb = int(nb * self.sous_sol)
        rng = random.Random("%s:%s:sous-sol" % (self._seed, self._zone))
        if self._zone == "Foret":
            teintes = [(0.10, 0.20, 0.12, 1), (0.08, 0.17, 0.10, 1),
                       (0.12, 0.24, 0.14, 1)]
            hauteurs = (0.03, 0.08)
        else:
            teintes = [HERBE_PLAINE + (1,)]
            hauteurs = (0.03, 0.08)
        items = []
        for _ in range(nb):
            gb = y0 - prof + rng.random() * prof
            # Plus pres, plus grand : 1/k, comme la tuile du sol.
            proche = 1.0 / self._k_sous_sol(gb, a, haut)
            gx = x0 + rng.uniform(-0.02, 1.02) * w
            gh = rng.uniform(*hauteurs) * h * proche
            items.append((gb, self._touffe(gx, gb, gh, rng.choice(teintes),
                                           proche)))
        # L'apercu de pose ne concerne pas ce sol : il n'est jamais sur la
        # grille. On le met de cote le temps de ce tri.
        nom_apercu, self._apercu_nom = self._apercu_nom, None
        try:
            self._dessine(items)
        finally:
            self._apercu_nom = nom_apercu

    def _k_sous_sol(self, yy, a, haut):
        """Le facteur de distance k au-dessous du bord (1 au bord, moins de 1
        plus pres). Celui de _fill_curve, prolonge : t devient negatif."""
        t = (yy - self.y) / haut
        return 1.0 / (1.0 - a * t)

    def _sous_sol_rive(self, prof):
        """Sous la rive du lac : son sable sec, prolonge.

        LA BANDE DE RIVE N'EST PAS UN MOTIF : c'est un bord, avec l'eau en
        haut et le sable sec en bas (voir rive.py). On ne peut donc pas la
        repeter vers le bas -- on retomberait dans l'eau. On lit sa partie
        SECHE en miroir, aller et retour, a partir de sa rangee du bas : au
        bord la texture est exactement la sienne, et elle ne remonte jamais
        jusqu'a l'eau.

        Sans shader ou sans image, la scene a pose un aplat de sable : on le
        prolonge tel quel."""
        w, h, x0, y0 = self.width, self.height, self.x, self.y
        fond = textures.base_texture(rive.NOM)
        if self._rive is None or fond is None:
            paint("sand")
            Rectangle(pos=(x0, y0 - prof), size=(w, prof))
            return
        # LES MESURES DE rive.bande, pour raccorder au pixel pres.
        bande = rive.HAUTEUR * h
        tuile = bande * (float(fond.width) / max(1, fond.height)) \
            * rive.ETIREMENT
        cx = x0 + w / 2.0
        u0, u1 = (x0 - cx) / tuile, (x0 + w - cx) / tuile
        bas_v = 0.998
        dv = (bas_v - 0.002) / bande
        # Les rangees tombent sur chaque demi-tour du miroir : entre deux, v
        # varie en ligne droite, ce que la carte graphique rend exactement.
        demi = (bas_v - V_SABLE_SEC) / dv
        points = [0.0]
        while points[-1] < prof:
            points.append(min(prof, points[-1] + demi))
        self._reset_pbr()
        Color(1, 1, 1, 1)
        verts, idx = [], []
        for j, d in enumerate(points):
            tour, reste = divmod(d, demi) if demi > 0 else (0, 0.0)
            if abs(reste) < 1e-6 and d > 0:
                # Pile sur un demi-tour : on prend l'extremite atteinte.
                tour, reste = tour - 1, demi
            part = reste / demi if demi > 0 else 0.0
            if int(tour) % 2 == 0:
                v = bas_v - part * (bas_v - V_SABLE_SEC)
            else:
                v = V_SABLE_SEC + part * (bas_v - V_SABLE_SEC)
            y = y0 - d
            verts += [x0, y, u0, v, x0 + w, y, u1, v]
            if j:
                p = (j - 1) * 2
                idx += [p, p + 1, p + 3, p, p + 3, p + 2]
        Mesh(vertices=verts, indices=idx, mode="triangles", texture=fond)

    def hauteur_horizon(self):
        """Part de la hauteur d'ecran ou le sol rencontre le ciel."""
        return self.CRETE.get(self._zone, self.CRETE_DEFAUT)

    def grille(self, gx, gy):
        """(fx, fy, taille) d'une case, corrige du sol de la zone.

        TOUT CE QUI TOUCHE A LA GRILLE PASSE PAR ICI : le decor de proximite,
        les objets installes, leur emprise, les cases bloquees et le toucher
        dans game_screen. Si deux d'entre eux projetaient differemment, un feu
        de camp ne serait plus la ou le doigt le cherche."""
        return grid_to_screen(gx, gy, self.SOL_DE_GRILLE.get(self._zone))

    def _compute_blocked_bboxes(self):
        """Reconstruit les rectangles d'ecran couverts par les objets installes
        (feu de camp, ...) a partir des cellules 5x5 (_blocked_grid)."""
        self._blocked_bboxes = []
        if not self._blocked_grid or self.width <= 0 or self.height <= 0:
            return
        w, h, x0, y0 = self.width, self.height, self.x, self.y
        for (gx, gy) in self._blocked_grid:
            fx, fy, size = self.grille(gx, gy)
            cx = x0 + fx * w
            cy = y0 + fy * h
            # Meme forme aplatie que tout ce qui repose a plat, + petite
            # marge (15 %) pour bien couvrir les objets qui debordent.
            hw = size * w * 0.5 * 1.15
            hh = size * w * _PLAT_PROFONDEUR * 0.5 * 1.15
            self._blocked_bboxes.append((cx, cy, hw, hh))

    def _is_blocked(self, x, y, top=None):
        """True si l'element tombe dans la zone visuelle d'un objet installe
        (feu de camp) sur cette case.

        `top` = hauteur atteinte par l'element. Les plantes poussent VERS LE
        HAUT depuis leur base : n'examiner que la base laisserait une touffe
        enracinee juste devant le foyer monter au milieu des flammes. Avec
        `top`, c'est tout le segment [base, sommet] qui est teste."""
        for cx, cy, hw, hh in self._blocked_bboxes:
            if abs(x - cx) >= hw:
                continue
            if top is None:
                if abs(y - cy) < hh:
                    return True
            elif y <= cy + hh and top >= cy - hh:
                return True
        return False

    def _iter_nature_big(self):
        """Itere les GROS elements du decor de la case, positionnes sur la
        GRILLE 5x5 (les memes cases sont refusees a l'installation d'objets).

        Genere (kind, rang, depth, tx, tb, jit) : type ("tree"/"bush"/
        "rock"/"nugget"), RANG de l'element parmi ceux de son type, profondeur
        0..1, position ecran de la base, et un rng stable pour les variations
        (taille...). Les cases occupees par un objet INSTALLE sont sautees
        (l'objet installe a la priorite d'affichage).

        LE RANG sert a REPARTIR les variantes d'un meme type. Le decor choisit
        d'ordinaire son image d'apres la position, ce qui peut donner cinq
        fois la meme pierre sur une case qui n'en porte que cinq ; avec le
        rang, on distribue les modeles en rond."""
        rangs = {}
        w, h, x0, y0 = self.width, self.height, self.x, self.y
        # Trie du plus LOINTAIN au plus proche (gy decroissant) : les zones qui
        # dessinent directement (sans liste triee) obtiennent ainsi le bon
        # ordre de recouvrement.
        for (ggx, ggy), kind in sorted(
                world.nature_blocked_cells(self._zone, self._seed).items(),
                key=lambda kv: (-kv[0][1], kv[0][0])):
            if ((ggx, ggy) in self._blocked_grid
                    or (ggx, ggy) in self._removed_grid):
                continue
            gfx, gfy, _gs = self.grille(ggx, ggy)
            jit = random.Random(f"{self._seed}:{ggx}:{ggy}:big")
            rang = rangs.get(kind, 0)
            rangs[kind] = rang + 1
            depth = ggy / 4.0
            # AUCUN decalage : l'element est pose EXACTEMENT au centre de sa
            # case, comme un objet installe. C'est ce qui permet de retrouver
            # la meme position dans la grille de placement et dans le jeu.
            tx = x0 + gfx * w
            tb = y0 + gfy * h
            yield kind, rang, depth, tx, tb, jit

    def _installed_items(self):
        """Objets INSTALLES, prets a etre tries avec le reste du decor.

        Renvoie [(y_base, fonction_de_dessin), ...] : la meme forme que les
        elements du decor, donc le tri par profondeur les melange correctement
        (ce qui est plus PROCHE est dessine par-dessus)."""
        out = []
        for name, gx, gy, lit, level in self._installed:
            objet = self._objet_pose(name, gx, gy, lit, level)
            if objet is not None:
                out.append(objet)
        return out

    def _objet_pose(self, name, gx, gy, lit=False, level="grand"):
        """(cle de tri, dessin) d'UN objet pose en (gx, gy), ou None.

        Ecrit a part pour servir deux fois : aux objets installes, et a
        l'APERCU de celui qu'on est en train de poser (voir montre_apercu).
        L'apercu est ainsi dessine par le meme code que l'objet pose -- il ne
        peut pas promettre autre chose que ce qui sortira."""
        w, h, x0, y0 = self.width, self.height, self.x, self.y
        fx, fy, size = self.grille(gx, gy)
        cx = x0 + fx * w
        cy = y0 + fy * h
        s = size * w
        if name == "Feu_de_camp":
            # Pose A PLAT et etale de part et d'autre de son centre : son bord
            # PROCHE descend d'une demi-profondeur sous (cx, cy). C'est la
            # qu'il touche le sol, donc c'est la sa cle de tri -- sans quoi il
            # passerait pour plus lointain qu'il ne parait, et l'herbe situee
            # derriere se dessinerait par-dessus (meme piege que les
            # buissons).
            return (cy - s * _PLAT_PROFONDEUR / 2.0,
                    lambda: self._fire_pit(cx, cy, s, lit, level, gy / 4.0))
        if name == items.BLUEPRINT_T1:
            coins = self._emprise_coins(name, gx, gy)
            base = min(c[1] for c in coins)
            if lit and level:
                # CHANTIER TERMINE : ce n'est plus un plan, c'est une
                # construction. Les piquets et la corde n'ont plus rien a dire
                # -- ils marquaient une intention, elle est realisee.
                return (base, lambda: self._batiment(coins, level))
            return (base, lambda: self._blueprint(coins))
        if name == items.WORKBENCH_T1:
            coins = self._emprise_coins(name, gx, gy)
            return (min(c[1] for c in coins),
                    lambda: self._etabli(coins, gy / 4.0))
        return None

    def _emprise_coins(self, name, gx, gy):
        """Les quatre coins ECRAN de l'emprise au sol d'un objet pose.

        Un objet qui couvre plusieurs cases ne peut pas etre dessine a partir
        d'un centre et d'une taille : la perspective retrecit chaque rangee, et
        sa rangee du fond est plus etroite que celle de devant. On projette
        donc les coins eux-memes, aux DEMI-cases qui bordent l'emprise.

        Rendus dans l'ordre : devant-gauche, devant-droite, fond-droite,
        fond-gauche -- le sens du tour de corde.

        LA FORME SUIT LA CONVENTION DU FOYER, et pas la geometrie vraie. La
        grille est en realite tres ecrasee -- une case fait environ trois fois
        plus large que profonde -- et le foyer ne la respecte pas : il est
        dessine comme un disque aplati a 0,55, donc bien plus rond que sa case.
        Un plan dessine, lui, avec les vrais coins projetes ressortait deux
        fois plus plat que le foyer d'a cote, et penche de surcroit, la grille
        convergeant vers le centre de l'ecran. Cela se lisait comme une cloture
        de travers.

        On garde donc de la perspective ce qui se LIT -- le bord du fond plus
        etroit que celui de devant -- et on laisse le reste, qui ne se lit pas
        et jure avec le decor."""
        fw, fh = items.footprint(name)
        w, h, x0, y0 = self.width, self.height, self.x, self.y
        # RETRAIT vers l'interieur. Pris exactement au bord des cases, le
        # marquage touchait ses voisins et se lisait comme une cloture qui
        # traverse le terrain. Un chantier est balise A L'INTERIEUR de son
        # emprise -- comme le foyer, qui n'occupe pas toute sa case non plus.
        m = _EMPRISE_RETRAIT
        cgx = gx + (fw - 1) / 2.0            # colonne du milieu de l'emprise
        cgy = gy + (fh - 1) / 2.0            # rangee du milieu
        fx_c, fy_c, taille = self.grille(cgx, cgy)
        cx, cy = x0 + fx_c * w, y0 + fy_c * h
        # Largeur : celle du foyer pour UNE case, multipliee par l'emprise.
        large = taille * w * (fw - 2.0 * m)
        # Profondeur : le meme aplatissement que le foyer, a l'echelle de
        # l'emprise. Un carre de cases reste donc un carre aplati, pas une
        # bande.
        prof = taille * w * _PLAT_PROFONDEUR * (fh - 2.0 * m)
        y_av, y_ar = cy - prof / 2.0, cy + prof / 2.0
        av, ar = large / 2.0, large / 2.0 * _EMPRISE_FUITE
        return [(cx - av, y_av), (cx + av, y_av),
                (cx + ar, y_ar), (cx - ar, y_ar)]

    def _batiment(self, coins, bati):
        """La construction achevee d'un chantier, vue depuis le jeu.

        `bati` est l'ensemble des (x, y, z, piece) batis. Le volume du chantier
        fait huit cubes de cote ; on plaque cette grille sur l'emprise au sol
        du plan par INTERPOLATION entre ses quatre coins -- ainsi le batiment
        se retrecit vers le fond exactement comme l'emprise qui le porte, sans
        qu'on ait a refaire une perspective a part.

        ON N'EN DESSINE QUE LA PEAU : une face qui a un cube voisin ne se voit
        pas, et la dessiner quand meme ne coutait pas seulement du temps -- les
        faces internes des cubes de devant recouvraient tout, et la maison se
        lisait comme un empilement de bandes plates. Ecartees, il ne reste que
        la silhouette, avec ses decrochements.

        La hauteur d'un cube est prise sur la LARGEUR de l'emprise, pas sur sa
        profondeur : la profondeur est ecrasee par la vue rasante (elle ne fait
        que la moitie de la largeur), et s'en servir donnerait une maison
        aplatie comme une galette.

        UN NIVEAU N'EST PAS A LA HAUTEUR DE SON INDICE : un pan de mur vaut
        quatre dalles. On passe donc par build_grid.z_bas / z_haut, les memes
        que le chantier -- sinon la maison finie n'aurait pas la silhouette du
        chantier qu'on vient de batir."""
        (x_ag, y_ag), (x_ad, y_ad), (x_fd, y_fd), (x_fg, y_fg) = coins
        nx, ny, _nz = build_grid.VOLUME_T1
        haut = (x_ad - x_ag) / float(nx) * _CUBE_HAUTEUR
        pleins = {(c[0], c[1], c[2]) for c in bati}

        def coin(cx, cy, hz):
            """Un sommet de la grille du chantier, en coordonnees ecran.

            `hz` est une hauteur CONTINUE en unites de cube, pas un indice de
            niveau."""
            u, v = cx / float(nx), cy / float(ny)
            xg = x_ag + (x_fg - x_ag) * v
            yg = y_ag + (y_fg - y_ag) * v
            xd = x_ad + (x_fd - x_ad) * v
            yd = y_ad + (y_fd - y_ad) * v
            return xg + (xd - xg) * u, yg + (yd - yg) * u + hz * haut

        # Les faces d'un cube : le voisin qui la cache, puis ses quatre
        # sommets et son assombrissement. Pas de face du DESSOUS ni de face
        # ARRIERE : dans une vue rasante venant du devant, elles ne se voient
        # jamais, meme au bord du batiment.
        FACES = (
            ((0, 0, 1), ((0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)),
             _OMBRE_DESSUS),
            ((0, -1, 0), ((0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)),
             _OMBRE_DEVANT),
            ((-1, 0, 0), ((0, 0, 0), (0, 1, 0), (0, 1, 1), (0, 0, 1)),
             _OMBRE_GAUCHE),
            ((1, 0, 0), ((1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)),
             _OMBRE_DROITE),
        )

        # LES BUCHES DU PLANCHER, calculees sur le sol ENTIER. C'est la meme
        # fonction que le chantier : on voit ici la maison qu'on vient d'y
        # batir, et un plancher qui changerait de buches en sortant du menu
        # dirait que ce n'est pas la meme.
        bandes = build_grid.buches_du_plancher(bati)

        # Du plus LOIN au plus proche, et du bas vers le haut : dans une vue
        # rasante, ce qui est devant et ce qui est haut recouvre le reste.
        for (x, y, z, piece) in sorted(bati,
                                       key=lambda c: (-c[1], c[2], c[0])):
            r, g, b = items.build_part_color(piece)
            bas, sommet = build_grid.z_bas(z), build_grid.z_haut(z)
            plancher = (bandes is not None and piece == "sol"
                        and build_grid.etape_de(z) == 0)
            if plancher:
                # LE PLANCHER EST FAIT DE BUCHES, comme dans le chantier : sa
                # surface est ronde et porte l'ecorce, ses bouts en travers
                # montrent les cernes. Il se dessine d'un seul tenant et non
                # face par face : l'ordre de ses morceaux lui est propre, et
                # le tableau des faces le prenait a l'envers.
                self._buches(coin, (x, y, z), bandes, pleins)
                continue
            for (dx, dy, dz), sommets, ombre in FACES:
                if (x + dx, y + dy, z + dz) in pleins:
                    continue                    # cachee par un voisin
                pts = []
                for sx, sy, sz in sommets:
                    px, py = coin(x + sx, y + sy, sommet if sz else bas)
                    pts += [px, py]
                Color(min(1.0, r * ombre), min(1.0, g * ombre),
                      min(1.0, b * ombre), 1)
                Quad(points=pts)
                # L'ARETE DE CHAQUE CUBE, sombre et fine. Sans elle, les
                # faces d'une meme couleur fusionnaient en larges bandes
                # plates et l'on ne voyait plus que la maison est BATIE de
                # pieces : c'est le quadrillage qui le dit.
                Color(r * 0.22, g * 0.22, b * 0.22, 0.85)
                Line(points=pts + pts[:2], width=1.0)

    @staticmethod
    def _buches(coin, cube, bandes, pleins):
        """Un cube de plancher, en BUCHES ENTIERES.

        `coin` est celui de _batiment : il plaque la grille du chantier sur
        l'emprise au sol du plan, donc les buches fuient vers le fond comme
        tout le reste, sans qu'il y ait de perspective a refaire ici.

        La vue du jeu est FIXE : pas de normale a tourner comme dans le
        chantier, seulement le tableau d'assombrissement des faces. Le rond
        d'une buche s'obtient en passant de l'ombre de son flanc a celle de sa
        crete -- les deux flancs ne regardent pas du meme cote, donc ils ne
        recoivent pas la meme lumiere.

        L'ORDRE COMPTE, et il n'est pas celui des faces d'un cube : l'ame,
        puis la surface, puis le noyau, puis les bouts. Les cernes viennent en
        dernier parce qu'ils sont a la face la plus proche de ce cote-la ;
        avant, l'ecorce des tranches leur mordait dessus."""
        axe, _bornes = bandes
        x, y, z = cube
        bas, haut = build_grid.z_bas(z), build_grid.z_haut(z)
        milieu = (bas + haut) / 2.0
        demi = build_grid.demi_buche(bandes, build_grid.hauteur_niveau(z))

        def expose(dx, dy):
            return (x + dx, y + dy, z) not in pleins

        # L'AME : deux buches voisines ne se touchent qu'en un POINT, et le
        # plancher serait fendu d'un trait fin tout du long. Elle le bouche,
        # et donne au passage sa profondeur a la rainure.
        pts = []
        for gx, gy in ((0, 0), (1, 0), (1, 1), (0, 1)):
            px, py = coin(x + gx, y + gy, milieu)
            pts += [px, py]
        _peau_bois(log_skin.ecorce(), _OMBRE_DESSUS * _CREUX_BUCHE, pts,
                   [0, 0, 1, 0, 1, 1, 0, 1])

        # LA SURFACE, vue de dessus : c'est tout ce qu'on en voit d'ici.
        gauche, droite = ((_OMBRE_DEVANT, _OMBRE_DERRIERE) if axe == 0
                          else (_OMBRE_GAUCHE, _OMBRE_DROITE))
        _a, tranches = build_grid.tranches_buches(cube, bandes)
        for l0, l1, s0, s1, t0, t1, _w0, _w1 in tranches:
            t = (t0 + t1) / 2.0
            flanc = gauche if t < 0.5 else droite
            f = flanc + (_OMBRE_DESSUS - flanc) * build_grid.profil_buche(t)
            h0 = milieu + build_grid.hauteur_buche(t0, demi)
            h1 = milieu + build_grid.hauteur_buche(t1, demi)
            pts, tc = [], []
            for l, s, tt, h in ((l0, s0, t0, h0), (l1, s0, t0, h0),
                                (l1, s1, t1, h1), (l0, s1, t1, h1)):
                gx, gy = (l, s) if axe == 0 else (s, l)
                px, py = coin(gx, gy, h)
                pts += [px, py]
                tc += [l / log_skin.MOTIF, tt]
            _peau_bois(log_skin.ecorce(), f, pts, tc)

        # LES BOUTS, sur les faces exposees EN TRAVERS des buches. Sur les
        # autres, le flanc d'une buche EST le bord du plancher : il n'y a rien
        # a ajouter. Sauf devant, ou l'on voit le dessous des rondins -- une
        # bande d'ombre, pas une dalle.
        for dx, dy, ombre in ((0, -1, _OMBRE_DEVANT), (-1, 0, _OMBRE_GAUCHE),
                              (1, 0, _OMBRE_DROITE)):
            if not expose(dx, dy):
                continue
            if ((dx != 0) if axe == 0 else (dy != 0)):
                ZoneScenery._bouts(coin, cube, bandes, demi, (dx, dy), ombre)
            elif dy < 0:
                # LE DESSOUS DES BUCHES, vu de devant : la ou le plancher
                # s'arrete dans le sens de leur longueur, on regarde sous le
                # ventre du premier rondin.
                pts = []
                for gx, gy, h in ((0, 0, bas), (1, 0, bas),
                                  (1, 0, milieu), (0, 0, milieu)):
                    px, py = coin(x + gx, y + gy, h)
                    pts += [px, py]
                u0 = x / log_skin.MOTIF
                _peau_bois(log_skin.ecorce(), ombre * _CREUX_BUCHE, pts,
                           [u0, 0.8, u0 + 1.0 / log_skin.MOTIF, 0.8,
                            u0 + 1.0 / log_skin.MOTIF, 0.2, u0, 0.2])

    @staticmethod
    def _bouts(coin, cube, bandes, demi, face, ombre):
        """Les cernes des rondins scies, sur une face en travers."""
        x, y, z = cube
        dx, dy = face
        bas, haut = build_grid.z_bas(z), build_grid.z_haut(z)
        milieu = (bas + haut) / 2.0
        bord = (x + (1 if dx > 0 else 0)) if dx else (y + (1 if dy > 0 else 0))

        def pt(s, h):
            return coin(*((bord, s) if dx else (s, bord)), h)

        # LE NOYAU d'abord : deux rondins voisins ne se touchent qu'en un
        # point, et les creux qui restent au-dessus et au-dessous laissaient
        # voir le decor au travers.
        c0, c1 = (y, y + 1) if dx else (x, x + 1)
        r0, r1 = c0 / log_skin.MOTIF, c1 / log_skin.MOTIF
        pts = []
        for s, h in ((c0, bas), (c1, bas), (c1, haut), (c0, haut)):
            px, py = pt(s, h)
            pts += [px, py]
        _peau_bois(log_skin.ecorce(), ombre * _CREUX_BUCHE, pts,
                   [r0, 0.9, r1, 0.9, r1, 0.1, r0, 0.1])
        for w0, w1, t0, t1 in build_grid.buches_du_cube(cube, bandes):
            pts, tc = [], []
            for s, dz in build_grid.contour_bout(w0, w1, demi, t0, t1):
                px, py = pt(s, milieu + dz)
                pts += [px, py]
                tc += list(build_grid.uv_bout(s, dz, w0, w1, demi))
            _peau_bois(log_skin.bout(), ombre, pts, tc, eventail=True)

    def _etabli(self, coins, depth=0.0):
        """L'atelier : un etabli DE CAMPEMENT, monte a la main avec ce qu'on
        trouve autour -- des branches, des pierres, une corde vegetale.

        Deux TRETEAUX EN X, chacun de deux branches croisees et liees a leur
        croisement ; dans la fourche du haut, un plan de travail de quatre
        branches jointives, ligaturees aux treteaux ; des pierres calent les
        pieds, et une derniere, posee sur le plan, sert d'enclume.

        IL A ETE TROP, PUIS PAS ASSEZ : une vraie table de menuisier (quatre
        pieds d'aplomb, un plateau de rondins sur toute l'emprise), puis deux
        tas de pierres portant deux branches. Le voici entre les deux :
        construit, mais a la main, et l'on voit de quoi.

        LES PIERRES ET LES BRANCHES SONT CELLES DE LA SCENE (voir _caillou et
        _baton), a la teinte de la zone : il est fait de ce qu'on a ramasse
        autour, elles ne changent pas d'aspect une fois montees.

        L'emprise ne change pas : c'est l'encombrement, ce qu'on ne peut plus
        traverser ni occuper."""
        (x_ag, y_ag), (x_ad, y_ad), (x_fd, y_fd), (x_fg, y_fg) = coins
        large = max(1.0, x_ad - x_ag)

        def coin(u, v, dz=0.0):
            """Un point de l'emprise (u : de gauche a droite, v : de l'avant
            vers le fond), eleve de `dz`."""
            xg = x_ag + (x_fg - x_ag) * v
            yg = y_ag + (y_fg - y_ag) * v
            xd = x_ad + (x_fd - x_ad) * v
            yd = y_ad + (y_fd - y_ad) * v
            return xg + (xd - xg) * u, yg + (yd - yg) * u + dz

        def echelle(v):
            """La perspective : ce qui est au fond de l'emprise est plus
            petit."""
            xg = x_ag + (x_fg - x_ag) * v
            xd = x_ad + (x_fd - x_ad) * v
            return (xd - xg) / large

        jit = random.Random("%s:%.1f:%.1f:etabli" % (self._seed, x_ag, y_ag))
        branche = self._zs("branch")
        haut = large * _ETABLI_HAUT
        k = echelle(0.5)

        def baton(p0, p1, epais):
            """Une branche d'un point de l'ecran a un autre."""
            (x0, y0), (x1, y1) = p0, p1
            longueur = math.hypot(x1 - x0, y1 - y0)
            angle = math.degrees(math.atan2(y1 - y0, x1 - x0))
            if not self._baton(branche, (x0 + x1) / 2.0, (y0 + y1) / 2.0,
                               longueur, pente=angle, epais=epais):
                Color(0.34, 0.23, 0.13, 1)
                Line(points=[x0, y0, x1, y1],
                     width=max(1.5, longueur * 0.035))

        t = large * 0.022              # taille d'une ligature
        fil = max(1.0, large * 0.007)  # epaisseur de la corde

        def tours(x0, y0, x1, y1, n, pas_x, pas_y):
            """`n` tours de corde serres, chacun de (x0, y0) a (x1, y1),
            decales de (pas_x, pas_y). CHAQUE TOUR A SON OMBRE, plus large
            que lui : c'est ce qui les separe. Poses d'un seul aplat, ils se
            lisaient comme une bande de papier collee."""
            for i in range(n):
                d = i - (n - 1) / 2.0
                pts = [x0 + d * pas_x, y0 + d * pas_y,
                       x1 + d * pas_x, y1 + d * pas_y]
                Color(*_ETABLI_LIEN_OMBRE, 1)
                Line(points=pts, width=fil * 1.25)
                Color(*_ETABLI_LIEN, 1)
                Line(points=[pts[0] - fil * 0.25, pts[1] + fil * 0.2,
                             pts[2] - fil * 0.25, pts[3] + fil * 0.2],
                     width=fil * 0.6)

        def pierre(u, v, dz, r, pose, enfonce=0.25):
            kv = echelle(v)
            x, y = coin(u, v, dz * kv)
            r = r * kv * jit.uniform(0.88, 1.12)
            if self._caillou(x, y, r, depth, enfonce=enfonce, pose=pose):
                return
            Color(0.42, 0.41, 0.40, 1)
            Ellipse(pos=(x - r * 1.1, y), size=(r * 2.2, r * 1.3))

        # L'OMBRE sous le plan de travail : sans elle, il flotte.
        Color(0.0, 0.0, 0.0, 0.18)
        Quad(points=[c for u, v in ((0.12, 0.30), (0.88, 0.30),
                                    (0.88, 0.72), (0.12, 0.72))
                     for c in coin(u, v)])

        # LES TRETEAUX : deux branches croisees chacun. Leurs pointes
        # depassent au-dessus du plan de travail, qui repose dans la fourche.
        e = _ETABLI_ECART
        pointe = haut * 1.18 * k
        croix = []
        for u0 in _ETABLI_TRETEAUX:
            for sens in (-1.0, 1.0):
                baton(coin(u0 + sens * e, 0.5),
                      coin(u0 - sens * e * 0.55, 0.5, pointe),
                      _ETABLI_PIEDS)
            # Les deux pieds se croisent au milieu, aux deux tiers de leur
            # hauteur (par symetrie : 1 / (1 + 0,55)).
            croix.append(coin(u0, 0.5, pointe / 1.55))
        # Lies au croisement : trois tours dans un sens, deux dans l'autre.
        for x, y in croix:
            tours(x - t, y - t * 0.6, x + t, y + t * 0.6, 3, 0.0, t * 0.45)
            tours(x - t, y + t * 0.6, x + t, y - t * 0.6, 2, 0.0, t * 0.45)
        # Les pierres qui calent les pieds, un peu en avant d'eux.
        for u0 in _ETABLI_TRETEAUX:
            for sens in (-1.0, 1.0):
                pierre(u0 + sens * e * 1.1, 0.44, 0.0,
                       large * _ETABLI_PIERRE, False)

        # LE PLAN DE TRAVAIL : des branches jointives, du fond vers l'avant.
        n = _ETABLI_BRANCHES
        rangs = [0.66 - 0.30 * i / max(1, n - 1) for i in range(n)]
        for v in rangs:
            kv = echelle(v)
            x, y = coin(0.5, v, haut * kv)
            longueur = large * kv * _ETABLI_PORTEE
            pente = jit.uniform(-_ETABLI_PENTE, _ETABLI_PENTE)
            if not self._baton(branche, x, y, longueur, pente=pente,
                               epais=_ETABLI_EPAIS):
                self._branch(x, y, longueur)
        # Ligaturees aux treteaux : trois tours de corde qui les enserrent
        # toutes, du devant au fond, un peu de biais.
        for u0 in _ETABLI_TRETEAUX:
            xa, ya = coin(u0, rangs[-1], haut * echelle(rangs[-1]))
            xb, yb = coin(u0, rangs[0], haut * echelle(rangs[0]))
            tours(xa - t * 0.25, ya - t * 0.8, xb + t * 0.25, yb + t * 0.6,
                  3, fil * 2.2, 0.0)

        # LA PIERRE DE TRAVAIL, sur le plan : l'enclume du campement.
        pierre(0.58, 0.50, haut + large * 0.012, large * _ETABLI_ENCLUME,
               True)

    def _blueprint(self, coins):
        """Plan de construction : quatre piquets relies par une corde.

        C'est un CHANTIER MARQUE AU SOL, pas un objet pose dessus : il ne doit
        rien cacher, seulement dire "ici". D'ou des piquets courts et une corde
        fine -- on doit pouvoir voir le sol a travers.

        `coins` vient de _emprise_coins : les quatre angles de l'emprise, deja
        mis en perspective. Le quadrilatere est donc plus etroit au fond qu'au
        devant, sans qu'on ait a le truquer -- un carre parfait, vu depuis le
        sol, se lirait comme un panneau dresse a la verticale."""
        (x_ag, y_ag), (x_ad, y_ad), (x_fd, y_fd), (x_fg, y_fg) = coins
        # Reference de taille : la largeur du bord PROCHE. Tout le reste en
        # decoule, donc un plan pose au loin s'amenuise de lui-meme.
        w = max(1.0, x_ad - x_ag)
        # LES PIQUETS SONT COURTS, et c'est ce qui fait tout. Hauts, la corde
        # s'eloignait du sol et l'ensemble se lisait comme un filet dresse
        # entre quatre poteaux -- un but de football. Bas, la corde epouse le
        # quadrilatere pose par terre, et l'oeil lit une EMPRISE. Un jalon de
        # chantier arrive au genou, pas a l'epaule.
        # Ceux du fond sont un peu plus courts : ils sont plus loin.
        pieux = ((x_ag, y_ag, w * 0.15), (x_ad, y_ad, w * 0.15),
                 (x_fd, y_fd, w * 0.115), (x_fg, y_fg, w * 0.115))

        # Pas d'ombre portee d'ensemble : quatre piquets fins n'en projettent
        # pas. Une tache sous le carre se lisait comme une fosse creusee.

        # La CORDE d'abord, les piquets par-dessus : elle est nouee derriere
        # eux, et cela evite un trait qui traverserait le bois.
        Color(0.76, 0.70, 0.54, 1)
        fil = max(1.0, w * 0.012)
        for i in range(4):
            x1, y1, t1 = pieux[i]
            x2, y2, t2 = pieux[(i + 1) % 4]
            # Une corde tendue entre deux piquets PEND. Trois points suffisent
            # a le dire ; deux donneraient un trait de regle, qui ne
            # ressemblerait pas a une corde.
            creux = (t1 + t2) * 0.5 * 0.16
            Line(points=[x1, y1 + t1, (x1 + x2) / 2.0,
                         (y1 + t1 + y2 + t2) / 2.0 - creux, x2, y2 + t2],
                 width=fil)

        for px, py, ht in pieux:
            ep = max(1.2, w * 0.022)
            # Le trait part LEGEREMENT AU-DESSUS du sol : son embout arrondi
            # deborde de la moitie de son epaisseur, et sans ce decalage le
            # piquet s'enfoncerait de quelques pixels sous le point ou il est
            # cense toucher terre -- donc sous sa propre cle de tri, ce qui
            # laissait passer une touffe d'herbe par-dessus.
            bas = py + ep * 0.68
            Color(0.30, 0.21, 0.13, 1)                    # cote a l'ombre
            Line(points=[px, bas, px, py + ht], width=ep * 1.35)
            Color(0.46, 0.33, 0.19, 1)                    # bois eclaire
            Line(points=[px - ep * 0.3, bas, px - ep * 0.3, py + ht], width=ep)

    # L'ANNEAU DU FOYER EST FAIT DES PETITES PIERRES DU SOL (voir _caillou) :
    # memes photos, meme relief, memes variantes. Ce sont les pierres qu'on
    # a ramassees pour le monter -- il serait etrange qu'elles changent
    # d'aspect une fois posees en cercle. Il etait fait de dix disques de deux
    # couleurs, les seuls ronds parfaits du decor.
    #
    # DOUZE PIERRES, qui se touchent : un foyer est un muret, pas un pointille.
    # A la taille des anciens disques (0,085), on voyait les cendres entre
    # elles, et elles pointaient comme des dents.
    #
    # PEU ENTERREES : on les a POSEES pour monter le foyer, elles n'affleurent
    # pas depuis toujours comme celles du sol. Enfoncees comme elles (du quart
    # a la moitie), on leur coupait la base, leur partie la plus large -- d'ou
    # ces dents espacees.
    PIERRES_FOYER = 12
    RAYON_PIERRE_FOYER = 0.098       # x la largeur du foyer (+/- 12 %)
    ENFONCE_FOYER = (0.10, 0.24)

    def _anneau_de_pierres(self, cx, cy, w, h, depth):
        """Les pierres du foyer : [(y au sol, dessin)], du FOND vers l'avant.

        Le y sert a les partager autour des flammes (voir _fire_pit) : celles
        du fond sont DERRIERE le feu, celles de devant le cachent en partie.

        Chaque foyer a son anneau, tire de sa POSITION comme le reste du
        decor : il ne change pas d'un redessin a l'autre, et deux foyers ne
        commencent pas leur cercle au meme angle.

        Sans les images de pierre, l'ancien anneau de disques revient."""
        out = []
        if foliage.planche_pierres("ore_nugget") is None:
            r = min(w, h) * 0.15
            for i in range(10):
                a = 2 * math.pi * i / 10
                sx = cx + (w / 2 - r) * math.cos(a)
                sy = cy + (h / 2 - r) * math.sin(a)
                col = (0.52, 0.42, 0.34) if i % 2 == 0 else (0.66, 0.58, 0.50)

                def disque(sx=sx, sy=sy, col=col):
                    Color(col[0], col[1], col[2], 1)
                    Ellipse(pos=(sx - r, sy - r), size=(r * 2, r * 2))
                out.append((sy, disque))
        else:
            n = self.PIERRES_FOYER
            rc = w * self.RAYON_PIERRE_FOYER
            jit = random.Random("%s:%.1f:%.1f:foyer" % (self._seed, cx, cy))
            depart = jit.uniform(0.0, 2.0 * math.pi / n)
            for i in range(n):
                a = depart + 2.0 * math.pi * i / n + jit.uniform(-0.10, 0.10)
                r = rc * jit.uniform(0.88, 1.12)
                # Le cercle passe par le MILIEU des pierres, en retrait du bord
                # des cendres : les pierres les bordent, elles ne debordent pas
                # sur l'herbe.
                sx = cx + (w / 2.0 - rc * 0.95) * math.cos(a)
                sy = cy + (h / 2.0 - rc * 0.50) * math.sin(a)
                e = jit.uniform(*self.ENFONCE_FOYER)
                # Posee par son PIED, un peu en avant de son milieu : vue de
                # biais, une pierre touche le sol devant son centre.
                out.append((sy, lambda sx=sx, base=sy - r * 0.30, r=r, e=e:
                            self._caillou(sx, base, r, depth, enfonce=e)))
        out.sort(key=lambda p: -p[0])
        return out

    def _fire_pit(self, cx, cy, w, lit=False, level="grand", depth=0.0):
        """Foyer de pierres vu en angle (cercle aplati + anneau de pierres).

        Allume, il montre ses braises et ses flammes, d'autant plus hautes
        qu'il lui reste du combustible (voir _FLAME_SCALE). C'est la MEME
        scene qui sert au jeu et au fond de l'ecran de proximite : le feu a
        donc partout le meme aspect.

        LES FLAMMES PASSENT ENTRE LES DEUX MOITIES DE L'ANNEAU : devant les
        pierres du fond, derriere celles de devant. Dessinees par-dessus tout
        l'anneau, comme avant, elles cachaient la rangee de devant -- le feu
        semblait bruler en avant du foyer, pas dedans."""
        h = w * _PLAT_PROFONDEUR
        scale = _FLAME_SCALE.get(level, 1.0) if lit else 0.0
        glow_c = ember_c = None
        if lit:                                        # lueur autour du foyer
            glow_c = Color(1.0, 0.55, 0.15, 0.14)
            glow_e = Ellipse(pos=(cx - w * 0.85, cy - h * 0.9),
                             size=(w * 1.7, w * 1.7))
        Color(0.10, 0.08, 0.06, 0.85)                  # cendres du foyer
        Ellipse(pos=(cx - w / 2, cy - h / 2), size=(w, h))
        if lit:                                        # braises rougeoyantes
            ember_c = Color(0.85, 0.30, 0.07, 0.95)
            Ellipse(pos=(cx - w * 0.32, cy - h * 0.30),
                    size=(w * 0.64, h * 0.60))
        anneau = self._anneau_de_pierres(cx, cy, w, h, depth)
        for sy, dessin in anneau:                      # la moitie du fond
            if sy > cy:
                dessin()
        tongues = []
        if scale > 0:                                  # langues de flamme
            for off, sc, col in _FLAME_TONGUES:
                c = Color(*col)
                tongues.append((c, Triangle(), off, sc))
        for sy, dessin in anneau:                      # la moitie de devant
            if sy <= cy:
                dessin()
        if lit:
            self._flames.append({
                "cx": cx, "cy": cy, "w": w, "h": h, "scale": scale,
                "glow_c": glow_c, "glow_e": glow_e, "ember_c": ember_c,
                "tongues": tongues, "phase": 1.7 * len(self._flames)})
            self._shape_flame(self._flames[-1], 0.0)

    # -- vacillement -------------------------------------------------- #
    def _shape_flame(self, fl, t):
        """Place les flammes d'un foyer a l'instant t (rien n'est recree).

        Deux sinusoides de frequences differentes par langue : le mouvement ne
        se repete pas de facon perceptible, et chaque langue vit sa vie."""
        cx, cy, w, h = fl["cx"], fl["cy"], fl["w"], fl["h"]
        ph, scale = fl["phase"], fl["scale"]
        for i, (col, tri, off, sc) in enumerate(fl["tongues"]):
            p = ph + i * 2.1
            flick = (1.0 + 0.20 * math.sin(t * (3.3 + 0.7 * i) + p)
                     + 0.09 * math.sin(t * (8.1 + 1.3 * i) + p * 1.9))
            sway = 0.05 * w * math.sin(t * 2.4 + p)
            fw = w * 0.34 * sc * scale
            fh = w * 0.80 * sc * scale * flick
            bx = cx + off * w
            tri.points = [bx - fw / 2, cy - h * 0.10,
                          bx + fw / 2, cy - h * 0.10,
                          bx + off * w * 0.35 + sway, cy + fh]
            col.a = min(1.0, 0.82 + 0.18 * flick)
        pulse = (0.80 + 0.20 * math.sin(t * 2.7 + ph)
                 + 0.08 * math.sin(t * 6.1 + ph * 1.4))
        if fl["glow_c"] is not None:
            # Une braise eclaire encore un peu : la lueur ne descend pas a 0.
            fl["glow_c"].a = 0.14 * max(0.35, scale) * pulse
            gr = w * 0.85 * max(0.5, scale) * (0.94 + 0.10 * pulse)
            fl["glow_e"].pos = (cx - gr, cy - h * 0.9)
            fl["glow_e"].size = (gr * 2, gr * 2)
        if fl["ember_c"] is not None:
            fl["ember_c"].a = min(1.0, 0.72 + 0.28 * pulse)

    def _sync_flame_clock(self):
        """L'horloge du feu ne tourne que s'il y a quelque chose a animer."""
        if self._flames and self._flame_ev is None:
            self._flame_ev = Clock.schedule_interval(self._tick_flames,
                                                     1.0 / _FLAME_FPS)
        elif not self._flames and self._flame_ev is not None:
            self._flame_ev.cancel()
            self._flame_ev = None

    def _tick_flames(self, dt):
        self._flame_t += dt
        for fl in self._flames:
            self._shape_flame(fl, self._flame_t)

    # -- balancement de la vegetation ----------------------------------- #
    def _keep_tallest_sway(self):
        """Ne garde que les elements du PREMIER PLAN pour l'animation.

        Les autres restent dessines, simplement immobiles : on lache juste
        leurs references. C'est ce qui garde le cout du vent constant, que la
        scene compte dix touffes ou cent trente.

        CHAQUE SORTE A SON QUOTA. Une seule liste triee sur la hauteur ne
        marcherait pas : un arbre fait dix fois la hauteur d'une touffe, les
        neuf arbres de la foret passeraient donc toujours devant, et une
        trentaine d'arbres d'horizon videraient le quota de l'herbe a eux
        seuls."""
        garde = []
        for sorte, quota in (("herbe", _SWAY_MAX), ("arbre", _SWAY_ARBRES)):
            lot = [bl for bl in self._sway if bl.get("sorte", "herbe") == sorte]
            if len(lot) > quota:
                lot.sort(key=lambda bl: bl["h"], reverse=True)
                del lot[quota:]
            garde += lot
        self._sway = garde

    def _sync_sway_clock(self):
        """L'horloge du vent ne tourne que s'il y a quelque chose a balancer."""
        self._keep_tallest_sway()
        if self._sway and self._sway_ev is None:
            self._sway_ev = Clock.schedule_interval(self._tick_sway,
                                                    1.0 / _SWAY_FPS)
        elif not self._sway and self._sway_ev is not None:
            self._sway_ev.cancel()
            self._sway_ev = None

    def _tick_sway(self, dt):
        """Courbe la pointe de chaque brin. La BASE ne bouge pas : un brin
        d'herbe plie, il ne glisse pas sur le sol."""
        # Chaque ecran a son propre decor, mais un seul est AFFICHE : inutile
        # de faire onduler l'herbe des quatre autres, que personne ne voit.
        if self.get_root_window() is None:
            return
        self._sway_t += dt
        push = _SWAY_AMPLITUDE * self._wind
        force = self.force_du_vent()
        n = RANGEES_HERBE
        for bl in self._sway:
            if "grille" in bl:
                self._tick_feuillage(bl, force)
                continue
            t = self._sway_t * bl["speed"] + bl["phase"]
            wave = _SWAY_BIAS + math.sin(t) + 0.35 * math.sin(t * 2.3 + 1.1)
            dx = wave * push * bl["h"]
            maillage = bl.get("mesh")
            if maillage is not None:
                # Une TOUFFE EN IMAGE : on repart des sommets AU REPOS et on
                # decale chaque rangee. Repartir du repos et non de l'etat
                # courant est ce qui empeche la touffe de deriver a force de
                # decalages ajoutes les uns aux autres.
                v = list(bl["repos"])
                for i in range(n + 1):
                    d = dx * (i / n) ** COURBE_HERBE
                    v[i * 8] += d
                    v[i * 8 + 4] += d
                maillage.vertices = v
                continue
            bl["tri"].points = [bl["x0"], bl["y"], bl["x1"], bl["y"],
                                bl["tipx"] + dx, bl["tipy"]]

    def _tick_feuillage(self, bl, force):
        """Le feuillage d'un arbre. Une seule boucle pour les deux especes :
        leurs reglages sont ranges dans l'inscription au vent, pas ici.

        CE QUI EST COMMUN AUX DEUX. L'onde depend de la COLONNE et pas
        seulement de la rangee -- le bord droit est en retard sur le gauche,
        donc le feuillage se deforme au lieu de se pencher d'un bloc, ce
        qu'aucune rangee seule ne sait faire. Et rien ne bouge en dessous du
        tronc.

        CE QUI LES SEPARE. Le sapin ajoute un REBOND VERTICAL des pointes de
        branches (`bond`), nul sur l'axe du tronc et maximal au bord, dont la
        phase MONTE le long de l'arbre. C'est la signature d'un conifere : ses
        branches sont des porte-a-faux qui battent, la ou une masse de feuilles
        ondoie. Le feuillu a `bond` a zero et ne paie donc rien pour cela.

        On repart des sommets AU REPOS -- comme pour l'herbe, et pour la meme
        raison : des decalages ajoutes les uns aux autres feraient deriver
        l'arbre hors de son sol."""
        v = list(bl["repos"])
        nc, nr = bl["nc"], bl["nr"]
        t = self._sway_t
        tronc = bl["tronc"]
        amp = bl["amp"] * force * bl["h"]
        bond = bl["bond"] * force * bl["h"]
        # UNE VALEUR D'ONDE PAR COLONNE, calculee une fois : elle ne depend
        # pas de la rangee, et la refaire a chaque sommet serait dix sinus
        # pour rien.
        ondes = []
        for i in range(nc + 1):
            u = bl["traverse"] * i / nc
            ondes.append(
                bl["biais"]
                + math.sin(bl["w1"] * t + bl["phase"] + u)
                + bl["melange"]
                * math.sin(bl["w2"] * t + bl["phase"] * 1.7 + 1.6 * u))
        # LES POINTES : 0 sur l'axe du tronc, 1 au bord des branches.
        pointes = [abs(i / nc - 0.5) * 2.0 for i in range(nc + 1)]
        for j in range(nr + 1):
            s = j / nr
            if s <= tronc:
                continue                       # le tronc ne bouge pas
            lin = (s - tronc) / (1.0 - tronc)
            r = lin ** bl["courbe"]
            depart = j * (nc + 1) * 4
            dy = 0.0
            if bond:
                # Le rebond suit l'onde RAPIDE (une pointe de branche bat plus
                # vite que le tronc ne se penche) et sa phase monte avec s.
                dy = bond * lin * math.sin(bl["w2"] * t + bl["phase"]
                                           + bl["montee"] * s)
            for i in range(nc + 1):
                v[depart + i * 4] += amp * r * ondes[i]
                if dy:
                    v[depart + i * 4 + 1] += dy * pointes[i]
        bl["grille"].vertices = v

    # -- image du decor (si elle a ete fournie) -------------------------- #
    @staticmethod
    def _pick(cx, base):
        """Le tirage de variante d'un element, deduit de sa POSITION.

        Deux voisins ne prennent donc pas la meme image, et un element garde
        la sienne quand la scene est redessinee. Sorti de _sprite parce que
        _pine a besoin de la MEME valeur avant de dessiner, pour connaitre la
        largeur de l'image et y poser son ombre."""
        return int(abs(cx) * 7.13 + abs(base) * 3.71)

    def _zs(self, key):
        """Nom de l'image de cet element pour la ZONE en cours.

        SI LA ZONE N'A PAS SON IMAGE, ELLE PREND CELLE DE LA PLAINE. La foret
        attend une fougere ("fern") et une branche de foret ; tant qu'elles
        n'ont pas ete livrees, elle dessinait des formes geometriques -- trois
        ovales verts, trois traits bruns -- a cote d'arbres photographiques.
        Le trefle et les branches de la plaine y font bien meilleure figure,
        et il suffira de deposer fern.png pour que la fougere reprenne sa
        place."""
        nom = _ZONE_SPRITES.get(self._zone, _ZONE_SPRITES["Foret"]).get(key)
        if nom and not foliage.variants(nom):
            repli = _ZONE_SPRITES["Plaine"].get(key)
            if repli and foliage.variants(repli):
                return repli
        return nom

    def _sprite(self, name, cx, base, height, pick=None, width=None,
                teinte=None, coupe_bas=0.0, crans=None, plie=False):
        """Dessine l'IMAGE de cet element, posee par son BAS sur (cx, base).

        Renvoie Vrai si une image existait et a ete dessinee ; Faux si aucune
        image n'a ete fournie, auquel cas l'appelant garde son dessin
        geometrique d'origine. C'est ce qui rend les images facultatives : le
        jeu tourne a l'identique sans elles, et s'habille au fur et a mesure
        qu'on en depose.

        La VARIANTE est deduite de la position : deux elements voisins ne
        prennent pas la meme image, et un element garde la sienne quand la
        scene est redessinee. `pick` permet de l'IMPOSER, pour les rares
        elements dont on veut garantir la variete plutot que la laisser au
        hasard des positions (voir les pepites).

        `teinte` multiplie l'image. Nos images viennent de photos, eclairees
        chacune dans son studio ; la scene, elle, a ses couleurs et sa
        lumiere. La teinte est ce qui rattache l'une a l'autre.

        `coupe_bas` en retranche le bas -- une fraction de sa hauteur -- au
        lieu de le dessiner. C'est ainsi qu'un element s'ENFONCE dans le sol :
        la part enterree n'est pas recouverte, elle n'est pas dessinee du
        tout, et l'on n'a donc aucune couleur de terre a faire correspondre.

        `crans` DENTELLE cette coupe au lieu de la laisser droite : une liste
        de decalages en pixels, un par colonne. C'est l'APPELANT qui la
        fabrique, parce qu'il est parfois seul a pouvoir le faire -- la pepite
        doit poser exactement les memes crans sur son image et sur les voiles
        qu'elle peint par-dessus (voir _etalonne_pepite). Deux tirages
        separes, et le voile debordait dans les echancrures.

        `plie` la pose en MAILLAGE plutot qu'en rectangle, et l'inscrit au
        vent. Trois facons de plier, parce que trois choses ne plient pas
        pareil :

            "herbe"     -- des rangees, la base plantee et la pointe qui se
                           couche (voir _sprite_plie) ;
            "feuillu"   -- une grille, le tronc immobile et une rafale qui
                           traverse le houppier ;
            "conifere"  -- la meme grille, mais la fleche fouette et les
                           pointes de branches rebondissent verticalement
                           (voir _sprite_feuillage et _tick_feuillage) ;
            "buisson"   -- la grille du feuillu, sans tronc : toute la masse
                           ondoie, plus large que haute (voir
                           RANGEES_BUISSON).

        Vrai vaut "herbe" : c'etait le seul cas quand le parametre est ne."""
        if not name:
            return False
        if pick is None:
            pick = self._pick(cx, base)
        # LES IMAGES FRANCHEMENT PENCHEES SE FONT RARES, et seulement pour
        # le feuillage : c'est le seul decor dont on mesure la pente, et
        # demander la mesure d'une pierre rouvrirait son image pour rien
        # (voir foliage.variante_droite). Le tirage corrige sert ENSUITE a
        # tout -- image, cartes de relief, mesures -- sinon l'arbre porterait
        # le relief d'un autre.
        if plie in self._FEUILLAGE:
            pick = foliage.variante_droite(name, pick)
        tex = foliage.sprite(name, pick)
        if tex is None:
            return False
        # On dimensionne d'ordinaire par la HAUTEUR : c'est elle qui compte
        # pour un arbre ou une plante. Un element large et bas -- une pierre
        # posee au sol -- se mesure au contraire a sa LARGEUR, sinon deux
        # images d'aplatissements differents ne font plus la meme taille.
        if width is not None:
            tw, th = tex.size
            height = width * (float(th) / float(tw)) if tw else width
        w, h = foliage.size_for(tex, height)
        # CARTES DE RELIEF, SI ELLES ONT ETE FOURNIES (nom_R / nom_P a cote de
        # l'image). L'element est alors eclaire par le soleil de la scene et
        # son cote clair suit l'heure, au lieu de porter un relief peint une
        # fois pour toutes. On ne lie que s'il y a quelque chose a lier : une
        # scene pose des centaines de sprites, et deux BindTexture par sprite
        # sans carte derriere ne seraient que du poids dans le canvas.
        nor, pak = foliage.relief(name, pick)
        relief = self._pbr and (nor is not None or pak is not None)
        if relief:
            pbr.bind_maps(nor, pak)
        Color(*((tuple(teinte[:3]) if teinte else (1, 1, 1)) + (1,)))
        f = min(0.90, max(0.0, float(coupe_bas)))
        if plie in self._FEUILLAGE:
            self._sprite_feuillage(tex, cx, base, w, h, plie, name, pick)
        elif plie:
            self._sprite_plie(tex, cx, base, w, h)
        elif f <= 0.0:
            Rectangle(pos=(cx - w / 2.0, base), size=(w, h), texture=tex)
        elif not crans:
            # Coins dans l'ordre de Kivy (bas-gauche, bas-droit, haut-droit,
            # haut-gauche) et v qui DESCEND dans l'image quand l'ecran monte :
            # voir la note de sens dans textures.py. Le bas du rectangle lit
            # donc la ligne 1-f du PNG, et tout ce qu'il y a dessous est
            # laisse sous terre.
            Rectangle(pos=(cx - w / 2.0, base), size=(w, h * (1.0 - f)),
                      texture=tex,
                      tex_coords=(0, 1.0 - f, 1, 1.0 - f, 1, 0, 0, 0))
        else:
            self._sprite_enfoui(tex, cx, base, w, h, f, crans)
        if relief:
            # Sans ce retour au neutre, TOUT ce qui est dessine ensuite --
            # l'herbe, les formes vectorielles, les autres sprites -- garderait
            # le relief de celui-ci.
            self._reset_pbr()
        return True

    def _sprite_plie(self, tex, cx, base, w, h):
        """L'image posee en MAILLAGE de rangees, pour qu'elle puisse PLIER.

        C'est ce qui leve l'objection qui tenait l'herbe a l'ecart des images :
        une touffe se courbe sous le vent, et un rectangle ne se courbe pas.
        Un maillage, si -- chaque rangee se decale horizontalement, d'autant
        plus qu'elle est haute, et la rangee du bas ne bouge jamais. Une
        touffe plie donc, elle ne glisse pas sur le sol.

        On garde les sommets au repos : le vent ne fait que les relire et y
        ajouter son decalage, ce qui evite de recalculer la geometrie et
        surtout de faire deriver la touffe a force de decalages cumules.

        v DESCEND quand l'ecran MONTE (voir la note de sens de textures.py) :
        la rangee du bas lit le bas du PNG."""
        n = RANGEES_HERBE
        gauche = cx - w / 2.0
        verts = []
        for i in range(n + 1):
            t = i / n
            y = base + h * t
            verts += [gauche, y, 0.0, 1.0 - t,
                      gauche + w, y, 1.0, 1.0 - t]
        m = Mesh(vertices=verts, indices=list(range(2 * (n + 1))),
                 mode="triangle_strip", texture=tex)
        if SWAY:
            # Meme allure que pour un brin dessine : sa propre vitesse et sa
            # propre phase, tirees de sa position. Une scene ou tout ondule
            # ensemble fait carton-pate.
            self._sway.append({
                "mesh": m, "repos": tuple(verts), "h": h, "sorte": "herbe",
                "speed": 1.35 + 0.0007 * (abs(cx) % 400),
                "phase": (cx * 0.11 + base * 0.07) % 6.28})

    def _touffe_pliee(self, planche, teinte, cx, base, w, h, uv):
        """Une touffe OMBREE posee seule, en rangees, pour qu'elle ondule.

        C'est _sprite_plie, lu dans la planche d'herbe plutot que dans une
        image entiere : `uv` = (u gauche, u droite, v du haut, v du pied) de
        sa variante. Meme maillage, meme inscription au vent."""
        u0, u1, v_haut, v_pied = uv
        Color(teinte[0], teinte[1], teinte[2], 1)
        n = RANGEES_HERBE
        gauche = cx - w / 2.0
        verts = []
        for i in range(n + 1):
            t = i / n
            y = base + h * t
            v = v_pied + (v_haut - v_pied) * t
            verts += [gauche, y, u0, v, gauche + w, y, u1, v]
        m = Mesh(vertices=verts, indices=list(range(2 * (n + 1))),
                 mode="triangle_strip", texture=planche.tex)
        if SWAY:
            self._sway.append({
                "mesh": m, "repos": tuple(verts), "h": h, "sorte": "herbe",
                "speed": 1.35 + 0.0007 * (abs(cx) % 400),
                "phase": (cx * 0.11 + base * 0.07) % 6.28})

    # Les deux especes d'arbre et le buisson, et tout ce qui les separe au
    # vent. Les ranger ici plutot que dans le corps du code evite des boucles
    # jumelles qui divergeraient a la premiere retouche -- et met les
    # differences cote a cote, ou on peut les lire.
    _FEUILLAGE = {
        "feuillu": {"nc": COLONNES_ARBRE, "nr": RANGEES_ARBRE,
                    "tronc": TRONC_FIXE, "courbe": COURBE_ARBRE,
                    "amp": VENT_ARBRE_AMPLITUDE, "bond": 0.0, "montee": 0.0,
                    "hz": VENT_ARBRE_HZ, "melange": VENT_ARBRE_MELANGE,
                    "biais": VENT_ARBRE_BIAIS,
                    "traverse": VENT_ARBRE_TRAVERSE},
        "conifere": {"nc": COLONNES_SAPIN, "nr": RANGEES_SAPIN,
                     "tronc": TRONC_FIXE_SAPIN, "courbe": COURBE_SAPIN,
                     "amp": VENT_SAPIN_AMPLITUDE, "bond": VENT_SAPIN_BOND,
                     "montee": VENT_SAPIN_MONTEE,
                     "hz": VENT_SAPIN_HZ, "melange": VENT_SAPIN_MELANGE,
                     "biais": VENT_SAPIN_BIAIS,
                     "traverse": VENT_SAPIN_TRAVERSE},
        "buisson": {"nc": COLONNES_BUISSON, "nr": RANGEES_BUISSON,
                    "tronc": TRONC_FIXE_BUISSON, "courbe": COURBE_BUISSON,
                    "amp": VENT_BUISSON_AMPLITUDE, "bond": 0.0, "montee": 0.0,
                    "hz": VENT_BUISSON_HZ, "melange": VENT_ARBRE_MELANGE,
                    "biais": VENT_ARBRE_BIAIS,
                    "traverse": VENT_BUISSON_TRAVERSE},
    }

    def _sprite_feuillage(self, tex, cx, base, w, h, espece, nom=None,
                          pick=None):
        """L'image d'un arbre posee en GRILLE, pour que son feuillage remue.

        Une rangee par bande horizontale suffisait a l'herbe : toute la touffe
        se couche du meme cote, seule la hauteur decide de combien. Un arbre
        non -- un feuillage qui s'inclinerait d'un bloc ferait une pancarte au
        bout d'un mat. Il faut donc aussi des COLONNES, chacune avec son
        retard de phase, pour qu'une rafale le traverse.

        Les sommets portent leurs coordonnees d'image, que le vent ne touche
        jamais : il ne deplace que la geometrie. LES CARTES DE RELIEF SUIVENT
        DONC TOUTES SEULES, puisque le shader les lit aux memes coordonnees
        que la couleur (voir pbr.py) -- le relief d'une aiguille reste sur
        cette aiguille pendant qu'elle bouge.

        v DESCEND quand l'ecran MONTE (voir la note de sens de textures.py) :
        la rangee du bas lit le bas du PNG."""
        reg = self._FEUILLAGE[espece]
        nc, nr = reg["nc"], reg["nr"]
        # SON INCLINAISON A LUI : on efface celle de l'image, puis on en
        # retire une de la position. Voir PENCHE_ARBRE.
        penche = 0.0
        if nom:
            # UN VRAI TIRAGE, GRAINE PAR LA POSITION. Deux hachages ont ete
            # essayes avant -- une combinaison lineaire de cx et base, puis
            # le sinus des shaders -- et les deux repartissaient mal : le
            # premier envoyait 49 % des arbres au-dela de 3 degres la ou le
            # cubique en prevoit 37, le second les serrait entre -2 et +5 et
            # sortait deux fois plus de droite que de gauche.
            #
            # La raison n'est pas le hachage mais ses ENTREES : les arbres se
            # posent sur une grille de cinq cases, donc cx et base ne
            # prennent qu'une poignee de valeurs, et aucune fonction lisse
            # n'en tire un bon melange. Un generateur graine, lui, s'en
            # moque. Il coute une microseconde par arbre et reste stable :
            # meme position, meme inclinaison.
            #
            # LA GRAINE EST UNE CHAINE, pas un entier. Deux raisons, toutes
            # deux mesurees : un pied peut se poser SOUS le bas de l'ecran
            # (base descend jusqu'a -12), et Python graine sur la VALEUR
            # ABSOLUE d'un entier -- deux arbres symetriques auraient penche
            # pareil ; et le melange d'une chaine passe par SHA-512, la ou un
            # ou-exclusif ne touche que les bits de poids faible de cx. Sur
            # la grille reelle du jeu, la moyenne des tirages tombe de 1,5 a
            # 0,4 ecart-type de zero.
            u = random.Random("%d:%d" % (int(cx * 8.0),
                                         int(base * 4.0))).uniform(-1.0, 1.0)
            penche = (u ** 3) * PENCHE_ARBRE
            penche -= REDRESSE_ARBRE * foliage.inclinaison(nom, pick)
        # LA LIGNE DU TRONC EST MESUREE SUR L'IMAGE, pas lue dans une
        # constante : les cinq feuillus livres la placent de 0,256 a 0,409, et
        # une valeur unique aurait fait balancer quinze pour cent de tronc nu
        # sur le plus elance. Le defaut ne sert que si la mesure echoue -- une
        # image dont les feuilles ne seraient pas vertes, par exemple.
        tronc = reg["tronc"]
        if nom:
            mesure = foliage.base_du_feuillage(nom, pick)
            if mesure is not None:
                tronc = mesure
        gauche = cx - w / 2.0
        # L'INCLINAISON EST CUITE DANS LES SOMMETS, autour du PIED. Pas de
        # PushMatrix : la rotation ne doit pas s'appliquer a ce qui vient
        # apres, le vent relit ces memes sommets, et un pivot au pied est ce
        # qui garde l'arbre plante -- il penche, il ne glisse pas.
        #
        # Les coordonnees d'IMAGE ne tournent pas : seule la geometrie
        # bouge, donc les cartes de relief suivent (voir pbr.py).
        ca = math.cos(math.radians(penche))
        sa = math.sin(math.radians(penche))
        verts = []
        for j in range(nr + 1):
            t = j / nr
            dy = h * t
            for i in range(nc + 1):
                u = i / nc
                dx = gauche + u * w - cx
                verts += [cx + dx * ca + dy * sa,
                          base + dy * ca - dx * sa, u, 1.0 - t]
        idx = []
        for j in range(nr):
            for i in range(nc):
                a = j * (nc + 1) + i
                c = a + nc + 1
                idx += [a, a + 1, c + 1, a, c + 1, c]
        m = Mesh(vertices=verts, indices=idx, mode="triangles", texture=tex)
        if SWAY:
            # Chaque arbre a sa phase ET ses frequences, tirees de sa
            # position : une allee ou tout bruisse ensemble fait carton-pate.
            # L'ecart reste petit (+/- 6 %), les deux frequences restent donc
            # dans la plage voulue.
            ecart = 1.0 + 0.12 * ((abs(cx) % 37) / 37.0 - 0.5)
            bl = {k: reg[k] for k in ("nc", "nr", "tronc", "courbe", "amp",
                                      "bond", "montee", "melange", "biais",
                                      "traverse")}
            bl.update({
                "grille": m, "repos": tuple(verts), "h": h, "sorte": "arbre",
                "tronc": tronc,
                "w1": 6.2832 * reg["hz"][0] * ecart,
                "w2": 6.2832 * reg["hz"][1] * ecart,
                "phase": (cx * 0.017 + base * 0.011) % 6.2832})
            self._sway.append(bl)

    def _sprite_enfoui(self, tex, cx, base, w, h, f, crans, uv=None):
        """L'image, coupee a la ligne du sol par un bord DENTELE.

        Un rectangle suffisait tant que la coupe etait droite ; une coupe
        irreguliere demande un maillage -- une colonne par cran, chacune avec
        son propre bas.

        POURQUOI DENTELER. La pierre etait tranchee par une horizontale
        parfaite, comme un sol l'etait avant sa frange. Le meme defaut appelle
        le meme remede : rien dans la nature ne finit au cordeau, et une
        pierre a demi enterree encore moins -- la terre monte plus haut d'un
        cote que de l'autre.

        V SUIT LE BORD, et c'est tout l'interet de le faire ici plutot que de
        masquer le bas avec quelque chose : la ou la coupe remonte, on lit
        PLUS HAUT dans l'image. La pierre n'est donc ni etiree ni comprimee,
        elle est reellement rognee -- exactement comme la coupe droite, mais
        en dents de scie.

        Le pas de v par pixel d'ecran vaut 1/h : l'image entiere (v de 0 a 1)
        occupe h pixels.

        `uv` = (u gauche, u droite, v du haut, v du pied) quand l'image n'est
        qu'une CASE d'une planche (voir _caillou) ; les u et v ci-dessus se
        lisent alors dans cette case."""
        n = len(crans) - 1
        gauche = cx - w / 2.0
        haut = base + h * (1.0 - f)
        u0, u1, vh, vp = uv or (0.0, 1.0, 0.0, 1.0)
        verts, idx = [], []
        for i in range(n + 1):
            u = i / n
            x = gauche + u * w
            d = crans[i]
            uu = u0 + (u1 - u0) * u
            verts += [x, base + d, uu,
                      vh + (vp - vh) * ((1.0 - f) - d / h)]  # bas, dentele
            verts += [x, haut, uu, vh]                       # haut, droit
            if i:
                p = (i - 1) * 2
                idx += [p, p + 1, p + 2, p + 1, p + 3, p + 2]
        Mesh(vertices=verts, indices=idx, mode="triangles", texture=tex)

    def _crans_de_pepite(self, largeur, variante):
        """Les crans du bas d'une pierre, de gauche a droite.

        Meme recette que la frange du sol (voir _frange) : un grain large pour
        les bosses, un grain fin pour la dentelure. Il n'y a PAS d'extinction
        aux extremites, au contraire du sol : une pierre a des bords, et c'est
        justement la, sur ses flancs, que la terre monte le plus."""
        n = max(8, int(largeur / self.SEGMENT_CRAN))
        ampl = largeur * self.FRANGE_PEPITE
        rng = random.Random("%s:%s:%s:crans" % (self._seed, largeur, variante))
        gros = [rng.uniform(-1.0, 1.0) for _ in range(n // 5 + 2)]
        out = []
        for i in range(n + 1):
            t = i / n * (len(gros) - 1)
            j = min(len(gros) - 2, int(t))
            large = gros[j] * (1 - (t - j)) + gros[j + 1] * (t - j)
            fin = rng.uniform(-1.0, 1.0)
            out.append(((1.0 - self.POIDS_FIN) * large
                        + self.POIDS_FIN * fin) * ampl)
        return out

    def reveille(self):
        """A appeler quand le jeu revient de l'arriere-plan.

        Le contexte graphique a pu etre detruit pendant ce temps. Le shader de
        relief est donc REINSTALLE -- ses uniformes (numeros d'unites de
        texture, direction et couleur de la lumiere) vivaient dans le contexte
        perdu, et sans eux la scene s'eclaire n'importe comment -- puis la
        scene est redessinee de zero."""
        if self._pbr:
            pbr.setup(self.canvas)
            self._apply_light()
        self._redraw()

    def set_ground(self, zone_type, seed=0):
        """Vue VERS LE BAS : on regarde le sol, qui remplit tout l'ecran."""
        self._cle_case = None
        self._zone = SCENE_DE_ZONE.get(zone_type, zone_type)
        self._seed = seed
        self._mode = "ground"
        self._redraw()

    # ------------------------------------------------------------------ #
    def _redraw(self, *_):
        # ON TESTE LA TAILLE AVANT D'EFFACER. L'inverse -- effacer puis
        # renoncer -- laissait un canvas VIDE derriere lui : une fenetre
        # reduite passe par une taille nulle, et si rien ne redemande de
        # redessiner ensuite, la scene ne revient jamais. Garder l'ancien
        # dessin ne coute rien : il n'est de toute facon pas visible.
        if self.width <= 0 or self.height <= 0:
            return
        self.canvas.clear()
        # Les anciennes instructions de flamme viennent d'etre effacees avec
        # le canvas : on repart d'une liste vide (elle sera remplie par
        # _fire_pit pour chaque foyer allume de la scene). Idem pour les
        # ombres portees et les touffes balancees par le vent, qui gardent des
        # references vers des instructions qui n'existent plus.
        self._flames = []
        self._shadows = []
        self._sway = []
        # Et les places de l'apercu, effacees avec lui (voir _dessine).
        self._apercu_places = {}
        self._apercu_vu = None
        self._eau = []
        self._rive = None
        # Idem pour la brume : seule une scene qui en pose une la recree.
        self._brume_couleur = None
        self._lot = None
        # Reinitialise le comptage des objets recoltables pour cette passe.
        self._ord = {}
        self._harvest_total = {}
        self._avail = {}
        # Recalcule les bboxes des cases bloquees (objets installes) au cas ou
        # la taille du widget a change depuis le dernier set_scene.
        self._compute_blocked_bboxes()
        rng = random.Random(_ZONE_SEED.get(self._zone, 0) * 100000 + self._seed)
        with self.canvas:
            self._reset_pbr()        # cartes neutres par defaut (unites 1 et 2)
            if self._mode == "ground":
                self._ground_view(rng)
            else:
                {
                    "Foret": self._foret,
                    "Plaine": self._plaine,
                    "Montagne": self._montagne,
                    "Lac": self._lac,
                }.get(self._zone, self._foret)(rng)
                if self.sous_sol > 0.0:
                    self._dessine_sous_sol()
        # Totaux visibles + nombre de recoltes possibles par objet : on ne peut
        # pas recolter plus de fois qu'il n'y a d'objets visibles.
        self.harvest_total = dict(self._harvest_total)
        self.harvest_max = {n: min(self._avail_for(n), t)
                            for n, t in self.harvest_total.items() if t > 0}
        self._apply_light()
        self._sync_flame_clock()
        self._sync_sway_clock()
        self._sync_eau_clock()

    # ------------------------------------------------------------------ #
    # BORDURES : la case voisine deborde dans la scene
    # ------------------------------------------------------------------ #
    # L'horizon dit ce qu'il y a AU LOIN. Mais une foret voisine ne commence
    # pas a l'horizon : elle commence au BORD DE LA CASE, donc au bord de
    # l'ecran, en vraie taille.
    #
    # LE PRINCIPE : on ne dessine pas "une bordure", on POSE LES ELEMENTS DE
    # LA CASE VOISINE SUR LA MEME GRILLE que ceux de la case actuelle, une
    # colonne plus loin. Ils passent par grid_to_screen comme tous les autres,
    # et leurs tailles sont calculees avec les MEMES formules. Ils se
    # comportent donc exactement comme s'ils appartenaient a la scene -- meme
    # perspective, meme taille, meme aspect -- et ils sont MELANGES au tri par
    # profondeur, si bien qu'un arbre voisin proche passe devant une touffe
    # d'herbe lointaine.
    #
    # UNE SEULE DIFFERENCE : ils ne sont pas interactifs. Ils ne passent ni par
    # _take_or_skip ni par _is_blocked -- ils ne sont pas sur la case du
    # joueur, on ne les ramasse pas et ils ne bloquent rien.
    #
    # Une PLAINE voisine n'ajoute rien : de l'herbe a cote de l'herbe ne se
    # verrait pas.

    # Colonne VIRTUELLE de chaque cote. La grille du jeu va de 0 a 4 ; -1 et 5
    # sont donc les premieres colonnes de la case d'a cote.
    _EDGE_COL = {"gauche": -1, "droite": 5}

    # Rangees utilisees, de la plus proche a la plus lointaine. On s'arrete a
    # la 3e : au-dela, la perspective ramene tout vers le centre de l'ecran, et
    # une colonne VOISINE y arriverait au milieu de l'image -- ce qui ne
    # voudrait plus rien dire.
    _EDGE_ROWS = (0, 1, 2)

    # LES ZONES SANS DEBORDEMENT SUR LES BORDS. La montagne et le lac ne
    # recoivent plus les elements de la case d'a cote le long de leurs bords :
    # ni les arbres, ni les rochers, ni les galets, ni la pente ou la rive
    # voisines. Leur decor s'arrete au cadre.
    #
    # L'HORIZON, LUI, RESTE. Ce sont deux choses differentes, et il ne faut
    # surtout pas les confondre : l'horizon montre ce qu'il y a AU LOIN, il
    # situe la case dans le monde et aide a s'orienter ; le debordement pose
    # des objets DANS la scene, au premier plan, le long du bord. C'est ce
    # second qui encombrait la pente et la berge. Les couper tous les deux --
    # ce qui avait ete fait d'abord -- privait la case de son paysage.
    SANS_BORDS_VOISINS = {"Montagne", "Lac"}

    def _edge_items(self):
        """Les elements de la case voisine qui debordent dans la scene.

        Renvoie [(y_base, fonction), ...] : la meme forme que le decor de la
        case, pour que le tri par profondeur les melange avec lui.

        Deux sortes d'elements :
        - un FOND par cote (la pente de la montagne, la rive du lac), pose une
          seule fois et tres en arriere : c'est le TERRAIN voisin, il doit
          passer derriere tout le reste ;
        - des OBJETS poses sur la grille, rang par rang, exactement comme ceux
          de la case."""
        out = []
        if self._zone in self.SANS_BORDS_VOISINS:
            return out
        for cote, col in self._EDGE_COL.items():
            zone = self._neighbours.get(cote)
            fond = {"Montagne": self._edge_slope,
                    "Lac": self._edge_shore}.get(zone)
            if fond is not None:
                fond(out, cote)
            pose = {"Foret": self._edge_tree,
                    "Montagne": self._edge_boulder,
                    "Lac": self._edge_pebble}.get(zone)
            if pose is None:
                continue
            for row in self._EDGE_ROWS:
                # Hasard STABLE par emplacement, et propre aux bordures : la
                # scene garde ainsi exactement le meme decor, qu'il y ait des
                # voisins ou non (cf. _graine_voisins).
                jit = random.Random("%d:%s:%d:bord" % (self._seed, cote, row))
                gfx, gfy, _gs = self.grille(col, row)
                pose(out, self.x + gfx * self.width,
                     self.y + gfy * self.height, row / 4.0, jit)
        return out

    def _edge_side(self, cote):
        """(x du bord d'ecran, sens vers l'interieur) pour un cote."""
        if cote == "gauche":
            return self.x, 1.0
        return self.x + self.width, -1.0

    def _edge_tree(self, out, tx, tb, depth, jit):
        """Un arbre de la foret voisine.

        Les formules de taille sont RECOPIEES de _foret, volontairement : ces
        arbres doivent etre indiscernables de ceux de la case, sinon la
        frontiere se verrait."""
        w, h = self.width, self.height
        th = (1.00 - 0.58 * depth) * jit.uniform(0.85, 1.10) * h
        if jit.random() < 0.5:
            tw = (0.11 - 0.05 * depth) * jit.uniform(0.85, 1.15) * w
            out.append((tb, lambda: self._pine(tx, tb, tw, th,
                                               (0.06, 0.15, 0.09, 1))))
        else:
            sc = 1.0 - 0.6 * depth
            out.append((tb, lambda: self._forest_tree(tx, tb, th, sc)))

    def _edge_boulder(self, out, tx, tb, depth, jit):
        """Un bloc de la montagne voisine, taille comme ceux de _montagne."""
        rr = (0.085 - 0.045 * depth) * jit.uniform(0.85, 1.15) * self.height
        out.append((tb, lambda: self._big_rock(tx, tb, rr)))

    def _edge_pebble(self, out, tx, tb, depth, jit):
        """Un galet de la rive voisine, comme ceux de _lac."""
        rr = jit.uniform(0.012, 0.03) * self.height
        out.append((tb - self.DEBORD_CAILLOU * rr,
                    lambda: self._pebble(tx, tb, rr, depth)))

    def _edge_slope(self, out, cote):
        """LE PIED de la montagne voisine : la ou le terrain commence a monter.

        Pas un sommet. Un sommet a cette distance serait enorme, et faux : la
        case d'a cote commence a quelques dizaines de metres, on n'en voit donc
        que le bas. Ce qu'il faut lire, c'est "le sol se releve a partir
        d'ici" -- d'ou un pan qui part du niveau du terrain vers l'interieur et
        s'eleve franchement en approchant du bord de l'ecran."""
        w, h = self.width, self.height
        bord, vers = self._edge_side(cote)
        dedans = bord + vers * 0.34 * w
        bas = self.y
        def dessin():
            self._tquad("rock", [bord, bas, dedans, bas,
                                 dedans, bas + 0.17 * h,
                                 bord, bas + 0.54 * h])
            # Bas plus sombre, comme la pente de _montagne : c'est ce qui lui
            # donne du volume au lieu d'un aplat triangulaire.
            self._tquad("rock_dark", [bord, bas, dedans, bas,
                                      dedans, bas + 0.05 * h,
                                      bord, bas + 0.14 * h])
        # Tres "loin" : le terrain voisin passe derriere tout le decor.
        out.append((self.y + 0.95 * h, dessin))

    def _edge_shore(self, out, cote):
        """LE BORD du lac voisin : la rive d'abord, l'eau ensuite.

        L'eau seule se lirait comme une flaque. C'est la bande de sable entre
        l'herbe et l'eau qui dit qu'il y a une BERGE, donc une etendue
        derriere. Les deux sont dessinees avec les textures du lac, et la rive
        s'amincit en remontant : elle s'eloigne."""
        w, h = self.width, self.height
        bord, vers = self._edge_side(cote)
        def bande(part, haut):
            loin = bord + vers * part * w
            return [bord, self.y, loin, self.y,
                    bord + vers * part * 0.55 * w, self.y + haut * h,
                    bord, self.y + haut * 1.20 * h]
        def dessin():
            self._tquad("sand", bande(0.34, 0.34))
            # L'eau reste EN RETRAIT du bord interieur : le liseré de sable
            # laisse visible est exactement ce qui fait la berge.
            self._tquad("water", bande(0.22, 0.27))
        out.append((self.y + 0.95 * h, dessin))

    def _graine_voisins(self):
        """Graine de hasard propre aux VOISINS : elle depend de la case et de
        ce qui l'entoure, et de rien d'autre."""
        graine = self._seed
        for cote in sorted(self._neighbours):
            graine = graine * 31 + hash(self._neighbours[cote]) % 9973
        return graine

    def _horizon(self, crest):
        """Pose les paysages voisins sur la ligne d'horizon de la scene.

        `crest(fx)` donne le y de cette ligne. A appeler AVANT le terrain : le
        sol dessine ensuite recouvre le pied des silhouettes, qui n'ont donc
        pas besoin d'etre decoupees proprement en bas.

        L'HORIZON A SON PROPRE HASARD, et ce n'est pas un detail. Toute la
        scene est tiree d'un seul generateur : s'il servait aussi a l'horizon,
        le nombre de tirages changerait avec les voisins, et TOUT le decor se
        reorganiserait -- les touffes d'herbe, les pierres, les objets a
        recolter. Le joueur verrait sa case se reconstruire rien qu'en
        tournant sur lui-meme. Ici, la ligne d'horizon depend des voisins,
        et rien d'autre n'en depend."""
        horizon.draw(self._neighbours, self.x, self.width, crest,
                     self.height, random.Random(self._graine_voisins()))

    # -- helpers textures (surface plane texturee, sinon couleur de repli) - #
    def _trect(self, name, x, y, w, h, tile_px=None):
        """Rectangle texture (repete) si la texture existe, sinon aplat couleur."""
        if tile_px is None:
            tile_px = textures.tile_for(name)
        tex = paint(name)
        self._bind_pbr(name)
        if tex is not None:
            Rectangle(pos=(x, y), size=(w, h), texture=tex,
                      tex_coords=tiled_coords(w, h, tile_px,
                                              textures.rapport(tex)))
        else:
            Rectangle(pos=(x, y), size=(w, h))
        self._reset_pbr()
        return tex

    def _tquad(self, name, points, tile_px=None):
        """Quad texture (repetition basee sur la position monde), sinon aplat."""
        if tile_px is None:
            tile_px = textures.tile_for(name)
        tex = paint(name)
        self._bind_pbr(name)
        if tex is not None:
            x0, y0 = self.x, self.y
            tile_v = tile_px * textures.rapport(tex)
            tc = []
            for i in range(0, 8, 2):
                # v NEGATIF vers le haut : voir la note de sens dans
                # textures.py (sans quoi la roche s'affiche a l'envers).
                tc += [(points[i] - x0) / tile_px,
                       -(points[i + 1] - y0) / tile_v]
            Quad(points=points, texture=tex, tex_coords=tc)
        else:
            Quad(points=points)
        self._reset_pbr()

    # -- vue VERS LE BAS (sol qui remplit l'ecran) ---------------------- #
    def _ground_view(self, rng):
        w, h, x0, y0 = self.width, self.height, self.x, self.y
        zone = self._zone

        if zone == "Lac":                              # surface de l'eau vue d'en haut
            tex = self._trect("water", x0, y0, w, h)
            if tex is not None:
                # Vue d'en haut, l'eau montre son fond : pas de reflet du
                # ciel, seulement l'ecume qui derive (voir _surface_eau).
                tile = textures.tile_for("water")
                tile_v = tile * textures.rapport(tex)
                coins = [(x0, y0), (x0 + w, y0), (x0 + w, y0 + h),
                         (x0, y0 + h)]
                verts = [v for x, y in coins
                         for v in (x, y, (x - x0) / tile, -(y - y0) / tile_v)]
                self._surface_eau("water", verts, [0, 1, 2, 0, 2, 3])
            for _ in range(70):                        # ondulations / reflets
                ly = y0 + rng.uniform(0, 1) * h
                lx = x0 + rng.uniform(0, 0.7) * w
                a = rng.uniform(0.2, 0.5)
                fin = lx + rng.uniform(0.1, 0.35) * w
                # Traits seulement sans image (voir _lac), tirages gardes.
                if tex is None:
                    Color(0.34, 0.58, 0.76, a)
                    Line(points=[lx, ly, fin, ly], width=1.4)
            for _ in range(rng.randint(4, 8)):         # nenuphars
                gx = x0 + rng.uniform(0, 1) * w
                gy = y0 + rng.uniform(0, 1) * h
                r = rng.uniform(0.03, 0.06) * h
                if self._sprite("lily_pad", gx, gy - r * 0.8, r * 1.6):
                    continue
                Color(0.16, 0.40, 0.20, 1)
                Ellipse(pos=(gx - r, gy - r * 0.8), size=(r * 2, r * 1.6))
            return

        if zone == "Montagne":
            base = (0.34, 0.34, 0.38)
            ground_tex = "rock"
        elif zone == "Foret":
            base = (0.16, 0.18, 0.11)
            ground_tex = "forest_floor"
        else:                                          # Plaine
            base = (0.24, 0.42, 0.18)
            ground_tex = "grass"

        self._trect(ground_tex, x0, y0, w, h)
        # Legeres taches de variation du sol : APLATIES et discretes (avant
        # c'etaient de gros ovales verts qui ressemblaient a des buissons vus
        # de haut). Larges et basses -> lisent comme des nuances de sol.
        for _ in range(10):
            gx = x0 + rng.uniform(0, 1) * w
            gy = y0 + rng.uniform(0, 1) * h
            rw = rng.uniform(0.10, 0.20) * w
            rh = rng.uniform(0.02, 0.05) * h
            Color(min(1, base[0] * 1.12), min(1, base[1] * 1.12),
                  min(1, base[2] * 1.12), 0.25)
            Ellipse(pos=(gx - rw / 2, gy - rh / 2), size=(rw, rh))

        def rnd():
            return x0 + rng.uniform(0, 1) * w, y0 + rng.uniform(0, 1) * h

        # Meme regle qu'a l'horizon : on collecte (base, dessin) et on trie du
        # plus loin au plus proche. Ces elements etaient dessines dans l'ordre
        # ou ils etaient tires, c'est-a-dire au hasard : une touffe du haut de
        # l'ecran pouvait recouvrir une touffe du bas, pourtant plus proche.
        # La composition ne change pas -- seul l'ordre de recouvrement.
        items = []

        if zone == "Plaine":
            greens = [(0.22, 0.42, 0.16, 1), (0.28, 0.48, 0.18, 1),
                      (0.18, 0.38, 0.14, 1)]
            for _ in range(110):                       # gazon partout
                gx, gy = rnd()
                gh = rng.uniform(0.04, 0.09) * h
                col = rng.choice(greens)
                items.append((gy, self._touffe(gx, gy, gh, col, 0.8)))
            for _ in range(rng.randint(8, 14)):        # petites pierres
                gx, gy = rnd()
                r = rng.uniform(0.015, 0.035) * h
                items.append((gy - self.DEBORD_CAILLOU * r,
                              lambda gx=gx, gy=gy, r=r:
                              self._stone(gx, gy, r,
                                          sprite=self._zs("stone"))))
            for _ in range(rng.randint(5, 9)):          # fleurs (peu nombreuses)
                gx, gy = rnd()
                col, fsprite = rng.choice(_FLOWERS)
                r = rng.uniform(0.018, 0.032) * h
                pet = rng.choice((5, 6))
                items.append((gy - self.DEBORD_FLEUR * r,
                              lambda gx=gx, gy=gy, r=r, col=col, pet=pet,
                              fsprite=fsprite:
                              self._flower(gx, gy, r, col, petals=pet,
                                           sprite=fsprite)))
        elif zone == "Foret":
            leaves = [(0.45, 0.32, 0.14, 1), (0.36, 0.40, 0.16, 1),
                      (0.52, 0.38, 0.18, 1), (0.30, 0.26, 0.12, 1)]
            for _ in range(150):                       # litiere de feuilles
                gx, gy = rnd()
                s = rng.uniform(0.012, 0.024) * h
                col = rng.choice(leaves)
                items.append((gy - self.DEBORD_FEUILLE * s,
                              lambda gx=gx, gy=gy, s=s, col=col:
                              self._leaf(gx, gy, s, col)))
            for _ in range(rng.randint(10, 16)):       # brindilles
                gx, gy = rnd()
                ln = rng.uniform(0.05, 0.10) * w
                items.append((gy - self.DEBORD_BRANCHE * ln,
                              lambda gx=gx, gy=gy, ln=ln:
                              self._branch(gx, gy, ln,
                                           sprite=self._zs("branch"))))
            for _ in range(45):                        # touffes sombres
                gx, gy = rnd()
                gh = rng.uniform(0.03, 0.07) * h
                items.append((gy, self._touffe(gx, gy, gh,
                                               (0.12, 0.22, 0.13, 1), 0.7)))
            for _ in range(rng.randint(8, 14)):        # pierres mousseuses
                gx, gy = rnd()
                r = rng.uniform(0.02, 0.045) * h
                items.append((gy - self.DEBORD_CAILLOU * r,
                              lambda gx=gx, gy=gy, r=r:
                              self._stone(gx, gy, r,
                                          sprite=self._zs("stone"))))
        else:                                          # Montagne (rocaille)
            for _ in range(rng.randint(45, 65)):       # rochers / galets
                gx, gy = rnd()
                r = rng.uniform(0.02, 0.06) * h
                items.append((gy - self.DEBORD_CAILLOU * r,
                              lambda gx=gx, gy=gy, r=r:
                              self._stone(gx, gy, r,
                                          sprite=self._zs("stone"))))
            for _ in range(rng.randint(8, 14)):        # touffes rares
                gx, gy = rnd()
                gh = rng.uniform(0.03, 0.06) * h
                items.append((gy, self._touffe(gx, gy, gh,
                                               (0.22, 0.34, 0.16, 1), 0.7)))

        self._dessine(items)

    # -- helpers -------------------------------------------------------- #
    def _pine(self, cx, base, tw, th, color, shadow=True):
        """Sapin : image si elle existe, sinon deux triangles.

        QUAND L'IMAGE EXISTE, C'EST ELLE QUI DECIDE DE LA LARGEUR, et donc de
        l'ombre. `tw` est la base du triangle dessine -- un neuvieme de
        l'ecran ; le sapin photographie fait 0,59 fois sa hauteur, soit
        plusieurs fois plus large. L'ombre calculee sur `tw` aurait fait une
        flaque sous un arbre de dix metres.

        LA HAUTEUR RECOIT SON PROPRE FACTEUR, tire de la position comme la
        variante. La scene tire deja une hauteur, mais la meme pour les deux
        especes ; ce facteur-ci est ce qui empeche une sapiniere d'aligner des
        arbres de meme stature. Il ne s'applique QUE quand l'image existe :
        les triangles, eux, avaient deja leur propre variete de forme."""
        # Le tirage est CORRIGE ICI, avant tout le reste : c'est lui qui
        # donne la largeur de l'ombre et le facteur de hauteur, et _sprite le
        # corrigerait a son tour plus bas. Sans cela, un sapin porterait
        # l'ombre d'un autre. La correction ne change rien quand on la
        # rejoue sur un tirage deja corrige (voir foliage.variante_droite).
        pick = foliage.variante_droite("pine_tree", self._pick(cx, base))
        tex = foliage.sprite("pine_tree", pick)
        if tex is not None:
            lo, hi = HAUTEUR_SAPIN
            th = th * (lo + (hi - lo) * ((pick * 0.6180339887) % 1.0))
            if shadow:
                self._shadow(cx, base, foliage.size_for(tex, th)[0] * 0.5)
            # LA LIGNE D'HORIZON NE BRUIT PAS (meme drapeau, meme raison que
            # pour le feuillu : a cette distance cela ne se verrait pas, et il
            # y a une trentaine d'arbres a poser).
            self._sprite("pine_tree", cx, base, th, pick=pick,
                         plie="conifere" if shadow else False)
            return
        if shadow:
            self._shadow(cx, base, tw * 0.9)
        tex = paint_color("foliage", color)
        self._bind_pbr("foliage")
        Triangle(points=[cx - tw / 2, base, cx + tw / 2, base,
                         cx, base + th * 0.72], texture=tex)
        Triangle(points=[cx - tw * 0.36, base + th * 0.32,
                         cx + tw * 0.36, base + th * 0.32, cx, base + th],
                 texture=tex)
        self._reset_pbr()

    # -- LE DEBORD : ou un element touche-t-il VRAIMENT le sol ? --------- #
    #
    # La scene est dessinee du plus loin au plus proche, chaque element
    # recouvrant ceux du fond. L'ordre vient d'une cle de tri, et cette cle
    # doit etre l'endroit ou l'element TOUCHE LE SOL -- son point le plus
    # proche du joueur.
    #
    # Or la plupart des elements sont poses par leur base, mais quelques-uns
    # sont dessines autour d'un point CENTRAL et descendent donc sous celui-ci.
    # Un buisson, par exemple, deborde de 40 % de son rayon -- six pour cent de
    # l'ecran. Trie sur son centre, il passait pour plus lointain qu'il ne
    # paraissait, et l'herbe situee DERRIERE lui se dessinait par-dessus.
    #
    # Ces valeurs sont donc le debord de chaque forme sous sa base, en fraction
    # de sa propre taille. Elles ne sont pas estimees : elles sont mesurees sur
    # le dessin reel (voir test_profondeur). Si tu modifies l'une de ces
    # methodes, remesure.
    DEBORD_PEPITE = 0.10       # x son rayon (l'ombre au sol comprise)
    DEBORD_BUISSON = 0.40      # x son rayon
    DEBORD_BAIES = 0.30        # x son rayon
    # x sa longueur. Le baton en IMAGE (voir _baton) est centre sur son
    # point : il en descend de sa demi-epaisseur (0,09 pour la plus epaisse
    # des variantes, fourche comprise), plus 0,5 x sin 9 = 0,078 quand il
    # penche, plus le decalage de son ombre (0,025).
    DEBORD_BRANCHE = 0.20
    DEBORD_FEUILLE = 0.40      # x sa taille
    DEBORD_FLEUR = 0.33        # x son rayon

    def _teinte_herbe(self, color, planche=None):
        """Le facteur qui donne a l'image d'herbe la clarte voulue.

        SURTOUT UNE CLARTE, PAS UNE COULEUR : l'image est deja verte, la
        multiplier par le vert demande la verdirait deux fois. On lui impose
        donc la CLARTE que le triangle avait, et elle garde l'essentiel de sa
        teinte -- ses jaunes de pointe, ses verts sombres de coeur, que jamais
        un aplat n'aurait eus. C'est ce qui permet a UNE image de servir le
        sous-bois sombre comme le champ en pleine lumiere.

        A une correction pres, la meme partout : TEINTE_HERBE_RVB, qui
        rapproche le vert froid de l'image du vert olive des sols.

        LA REFERENCE RESTE L'IMAGE D'ORIGINE, meme quand la planche ombree
        est dessinee (`planche` ne sert qu'a le dire). Se caler sur la
        moyenne de la planche aurait ete un piege : son pied a ete assombri,
        sa moyenne a donc baisse, et la teinte aurait ECLAIRCI les pointes
        d'autant pour la ramener au meme niveau -- l'ombrage aurait rendu
        l'herbe plus pale, exactement le contraire du but. Ici l'ombrage ne
        fait qu'assombrir le pied ; les pointes gardent leur clarte.

        La teinte est ARRONDIE au 1/32 : deux touffes de teintes presque
        egales doivent pouvoir se dessiner d'un seul coup (voir _dessine)."""
        r, g, b = color[0], color[1], color[2]
        lum = 0.3 * r + 0.6 * g + 0.1 * b
        clarte = CLARTE_HERBE
        k = lum / clarte if clarte else 1.0
        k = max(TEINTE_HERBE_MIN, min(TEINTE_HERBE_MAX, k))
        return tuple(round(k * c * 32.0) / 32.0 for c in TEINTE_HERBE_RVB)

    def _touffe(self, gx, gb, gh, col, sc=1.0, sprite=NOM_HERBE):
        """La fonction de dessin d'une touffe, MARQUEE comme de l'herbe.

        La marque (sa hauteur) sert a _dessine : elle lui dit que cette
        fonction peut rejoindre le lot d'herbe en cours, et lesquelles sont
        assez hautes pour onduler au vent."""
        def fn():
            self._grass_tuft(gx, gb, gh, col, scale=sc, sprite=sprite)
        fn.herbe = gh
        return fn

    def _dessine(self, items):
        """Dessine les elements du plus LOIN au plus PROCHE, l'herbe par lots.

        L'ORDRE NE CHANGE PAS : les elements sont tries comme avant, et un
        lot d'herbe est VIDE (dessine) des qu'autre chose doit passer -- une
        pierre, une fleur, un buisson. Seules les touffes qui se suivent sans
        rien entre elles partagent un dessin, et comme elles se suivent en
        profondeur, se recouvrent entre elles dans le meme ordre qu'avant.

        LES TOUFFES QUI ONDULENT sont les plus hautes, comme avant (voir
        _keep_tallest_sway) : on les repere ici, avant de dessiner, et elles
        seules sont posees une par une -- un lot ne sait pas plier."""
        items.sort(key=lambda it: it[0], reverse=True)
        hauteurs = sorted((getattr(fn, "herbe", 0.0) for _, fn in items),
                          reverse=True)
        if SWAY and len(hauteurs) >= _SWAY_MAX:
            self._seuil_vent = max(1e-6, hauteurs[_SWAY_MAX - 1])
        elif SWAY:
            self._seuil_vent = 1e-6
        else:
            self._seuil_vent = float("inf")
        self._lot = {"cle": None, "sommets": []}
        # LES PLACES DE L'APERCU, glissees dans l'ordre de profondeur la ou
        # l'objet pose se trierait (voir montre_apercu). Vide hors pose.
        places = self._places_apercu()
        try:
            for cle, fn in items:
                while places and cle < places[0][0]:
                    self._reserve_place(places.pop(0)[1])
                if not getattr(fn, "herbe", 0.0):
                    self._vide_lot()
                fn()
            for _cle, gy in places:
                self._reserve_place(gy)
            self._vide_lot()
        finally:
            self._lot = None

    def _vide_lot(self):
        """Dessine d'un coup les touffes en attente, puis repart a vide."""
        lot = self._lot
        if not lot or not lot["sommets"]:
            return
        tex, teinte = lot["cle"]
        sommets = lot["sommets"]
        n = len(sommets) // 16
        indices = []
        for i in range(n):
            p = 4 * i
            indices += (p, p + 1, p + 2, p, p + 2, p + 3)
        Color(teinte[0], teinte[1], teinte[2], 1)
        Mesh(vertices=sommets, indices=indices, mode="triangles", texture=tex)
        lot["sommets"] = []
        lot["cle"] = None

    def _grass_tuft(self, cx, base, height, color, scale=1.0,
                    sprite=NOM_HERBE):
        planche = foliage.planche_ombree(sprite) if sprite else None
        if planche is not None:
            teinte = self._teinte_herbe(color, planche)
            h = height * 1.15
            u0, u1, v_haut, v_pied, pw, ph = planche.case(
                self._pick(cx, base))
            w = h * float(pw) / float(ph) if ph else h
            lot = self._lot
            if lot is not None and height < self._seuil_vent:
                cle = (planche.tex, teinte)
                if lot["cle"] != cle or len(lot["sommets"]) >= 16 * LOT_HERBE_MAX:
                    self._vide_lot()
                    lot["cle"] = cle
                g, d, haut = cx - w / 2.0, cx + w / 2.0, base + h
                lot["sommets"] += (g, base, u0, v_pied, d, base, u1, v_pied,
                                   d, haut, u1, v_haut, g, haut, u0, v_haut)
                return
            self._vide_lot()
            self._touffe_pliee(planche, teinte, cx, base, w, h,
                               (u0, u1, v_haut, v_pied))
            return
        self._vide_lot()
        if self._sprite(sprite, cx, base, height * 1.15,
                        teinte=self._teinte_herbe(color), plie=True):
            return
        bw = max(1.2, self.width * 0.0035 * scale)
        r, g, b, a = color
        # 5 brins fins en eventail, longueurs/inclinaisons/teintes variees.
        for off, hsc, lean in ((-1.3, 0.65, -0.55), (-0.6, 0.85, -0.25),
                               (0.0, 1.0, 0.08), (0.6, 0.88, 0.30),
                               (1.3, 0.70, 0.60)):
            bx = cx + off * bw
            tipx = bx + lean * bw * 2.4
            tipy = base + height * hsc
            sh = 0.88 + 0.24 * ((off + 1.3) / 2.6)        # nuance par brin
            Color(min(1.0, r * sh), min(1.0, g * sh), min(1.0, b * sh), a)
            tri = Triangle(points=[bx - bw, base, bx + bw, base, tipx, tipy])
            if SWAY:
                # Chaque brin garde sa propre allure et son propre depart : une
                # touffe qui ondulerait d'un seul bloc ferait carton-pate.
                self._sway.append({
                    "tri": tri, "x0": bx - bw, "x1": bx + bw, "y": base,
                    "tipx": tipx, "tipy": tipy, "h": height * hsc,
                    "speed": 1.5 + 0.55 * hsc + 0.3 * off,
                    "phase": (cx * 0.11 + base * 0.07 + off * 1.9) % 6.28})

    def _teinte_buisson(self, color):
        """La teinte qui donne a l'image du buisson la CLARTE de `color`.

        Meme principe que _teinte_herbe : une seule photo sert le buisson de
        pre et celui de sous-bois, deux fois plus sombre. On ne lui impose que
        sa clarte -- un gris -- et elle garde ses verts, ses reflets et ses
        creux, que jamais les ovales d'avant n'auraient eus."""
        lum = 0.3 * color[0] + 0.6 * color[1] + 0.1 * color[2]
        k = max(0.35, min(1.60, lum / CLARTE_BUISSON))
        return tuple(k * c for c in TEINTE_BUISSON_RVB)

    def _bush(self, cx, cy, r, color, sprite=None):
        cr, cg, cb, ca = color
        self._shadow(cx, cy - r * 0.1, r * 2.6)           # ombre au sol
        # L'image : ses cartes de relief, sa variante (l'original ou son
        # miroir, tiree de la position) et le vent dans son feuillage.
        if self._sprite(sprite, cx, cy - r * 0.35, r * HAUTEUR_BUISSON,
                        teinte=self._teinte_buisson(color), plie="buisson"):
            return
        self._bind_pbr("foliage")
        dtex = paint_color("foliage", (cr * 0.7, cg * 0.7, cb * 0.7, 1))  # masse sombre
        Ellipse(pos=(cx - r * 1.4, cy - r * 0.3), size=(r * 1.3, r * 1.0), texture=dtex)
        Ellipse(pos=(cx + r * 0.2, cy - r * 0.3), size=(r * 1.3, r * 1.0), texture=dtex)
        Ellipse(pos=(cx - r, cy - r * 0.4), size=(r * 2, r * 1.2), texture=dtex)
        ltex = paint_color("foliage", (cr, cg, cb, 1))    # feuillage clair (haut)
        Ellipse(pos=(cx - r * 0.9, cy + r * 0.1), size=(r * 1.8, r * 1.0), texture=ltex)
        Ellipse(pos=(cx - r * 1.2, cy), size=(r * 1.1, r * 0.8), texture=ltex)
        Ellipse(pos=(cx + r * 0.2, cy), size=(r * 1.1, r * 0.8), texture=ltex)
        self._reset_pbr()

    # -- scenes (plein cadre) ------------------------------------------- #
    def _leaf(self, cx, cy, size, color):
        """Feuille morte au sol (litiere). Posee a plat : aucune ombre."""
        if self._sprite("leaf_litter", cx, cy - size * 0.4, size * 0.8):
            return
        Color(*color)
        Ellipse(pos=(cx - size, cy - size * 0.4), size=(size * 2, size * 0.8))

    def _forest_tree(self, cx, base, th, scale, shadow=True):
        """Arbre feuillu : tronc conique + amas de feuillage sombre.

        `shadow` est coupe pour la ligne d'arbres de l'HORIZON : une ombre
        portee n'a pas de sens a cette distance, et il y en aurait une
        trentaine a replacer a chaque mouvement du soleil pour rien."""
        if shadow:
            self._shadow(cx, base, th * 0.45)
        # LA LIGNE D'HORIZON NE BRUIT PAS, et c'est le meme drapeau qui le dit
        # que pour l'ombre portee, parce que c'est la meme raison : a cette
        # distance le mouvement ne se verrait pas, et il y a une trentaine
        # d'arbres a poser -- autant de grilles de 63 sommets au lieu de
        # simples rectangles, pour rien.
        if self._sprite("forest_tree", cx, base, th,
                        plie="feuillu" if shadow else False):
            return
        tw = max(2.0, self.width * 0.012 * scale)
        btex = paint_color("bark", (0.28, 0.19, 0.11, 1))
        self._bind_pbr("bark")
        Quad(points=[cx - tw, base, cx + tw, base,
                     cx + tw * 0.5, base + th * 0.6, cx - tw * 0.5, base + th * 0.6],
             texture=btex)
        self._reset_pbr()
        fr = th * 0.32
        fy = base + th * 0.55
        ftex = paint_color("foliage", (0.09, 0.18, 0.11, 1))
        self._bind_pbr("foliage")
        for dx, dy in ((-0.5, 0.0), (0.5, 0.05), (0.0, 0.35),
                       (-0.3, 0.42), (0.35, 0.40), (0.0, 0.05)):
            Ellipse(pos=(cx + dx * fr - fr * 0.7, fy + dy * fr),
                    size=(fr * 1.4, fr * 1.3), texture=ftex)
        self._reset_pbr()
        Color(0.14, 0.26, 0.15, 1)                        # reflet de lumiere
        Ellipse(pos=(cx - fr * 0.45, fy + fr * 0.3), size=(fr * 0.9, fr * 0.8))

    def _foret(self, rng):
        w, h, x0, y0 = self.width, self.height, self.x, self.y
        floor = 0.42                      # hauteur moyenne du sol forestier

        p1 = rng.uniform(0, 6.28)
        p2 = rng.uniform(0, 6.28)

        def far_curve(fx):
            return y0 + (floor + 0.05 + 0.03 * math.sin(fx * 6.28 * 1.3 + p1)
                         + 0.015 * math.sin(fx * 6.28 * 2.7 + p2)) * h

        def floor_curve(fx):
            return y0 + (floor + 0.025 * math.sin(fx * 6.28 * 1.1 + p1 + 1.0)
                         + 0.012 * math.sin(fx * 6.28 * 2.4 + p2)) * h

        def place(maxt=1.0, fx=None, floor=0.0):
            if fx is None:
                fx = rng.uniform(0, 1)
            fx = min(0.999, max(0.001, fx))
            surf = (floor_curve(fx) - y0) / h
            lo = min(floor, surf)              # plancher (jointures des mains)
            hi = surf * maxt
            if hi < lo:
                hi = lo
            fy = lo + (hi - lo) * rng.random()
            t = (fy / surf) if surf else 0.0
            return (x0 + fx * w, y0 + fy * h, 1.0 - 0.70 * t, t)

        def clusters(count, spread):
            centers = [rng.uniform(0.05, 0.95) for _ in range(max(1, count))]
            return lambda: rng.choice(centers) + rng.gauss(0, spread)

        leaf_pick = clusters(rng.randint(4, 6), 0.13)
        grass_pick = clusters(rng.randint(3, 5), 0.12)
        stone_pick = clusters(rng.randint(2, 3), 0.06)
        fern_pick = clusters(rng.randint(3, 4), 0.09)
        mush_pick = clusters(rng.randint(2, 3), 0.05)

        # Sol forestier (terre/mousse) ondule, deux tons.
        # Les paysages voisins d'abord : ils sont derriere tout le reste.
        self._horizon(lambda fx: far_curve(fx) - 0.010 * h)

        self._fill_curve(far_curve, "forest_floor_far")
        self._fill_curve(floor_curve, "forest_floor", estompe=True)

        GREENS = [(0.10, 0.20, 0.12), (0.08, 0.17, 0.10), (0.12, 0.24, 0.14)]
        LEAVES = [(0.45, 0.32, 0.14, 1), (0.36, 0.40, 0.16, 1),
                  (0.52, 0.38, 0.18, 1), (0.30, 0.26, 0.12, 1)]

        def f_grass(gx, gb, gh, col, sc):
            return self._touffe(gx, gb, gh, col, sc)

        items = []   # (y_base, fonction) -> tri par profondeur

        # Litiere de feuilles mortes (beaucoup, en plaques). [recoltable: Feuille]
        for _ in range(100):
            fx = leaf_pick() if rng.random() < 0.8 else None
            lx, ly, sc, t = place(fx=fx, floor=_HARVEST_FLOOR)
            s = rng.uniform(0.010, 0.022) * h * sc
            col = rng.choice(LEAVES)
            if not self._take_or_skip("Feuille") and not self._is_blocked(lx, ly):
                items.append((ly - self.DEBORD_FEUILLE * s,
                              lambda lx=lx, ly=ly, s=s, col=col:
                              self._leaf(lx, ly, s, col)))
        # Pierres mousseuses (en tas). [recoltable: Pierre]
        for _ in range(rng.randint(6, 10)):
            sx, sy, sc, t = place(1.0, fx=stone_pick(), floor=_HARVEST_FLOOR)
            r = rng.uniform(0.02, 0.05) * h * sc
            if not self._take_or_skip("Pierre") and not self._is_blocked(sx, sy):
                items.append((sy - self.DEBORD_CAILLOU * r,
                              lambda sx=sx, sy=sy, r=r, t=t:
                              self._stone(sx, sy, r, sprite=self._zs("stone"),
                                          depth=t)))
        # Branches au sol. [recoltable: Small_Stick]
        for _ in range(rng.randint(7, 11)):
            bx, by, sc, t = place(1.0, floor=_HARVEST_FLOOR)
            ln = rng.uniform(0.06, 0.13) * w * sc
            if not self._take_or_skip("Small_Stick") and not self._is_blocked(bx, by):
                items.append((by - self.DEBORD_BRANCHE * ln,
                              lambda bx=bx, by=by, ln=ln:
                              self._branch(bx, by, ln,
                                           sprite=self._zs("branch"))))
        # Herbe de sous-bois (sombre), en touffes (dense). DECORATIVE : elle
        # couvre tout le sol, jusqu'au fond, et la faire disparaitre a chaque
        # recolte deshabillerait la foret.
        for _ in range(HERBE_FORET):
            fx = grass_pick() if rng.random() < 0.72 else None
            gx, gb, sc, t = place(fx=fx)
            gh = rng.uniform(0.05, 0.13) * h * sc
            if self._is_blocked(gx, gb, gb + gh):
                continue
            items.append((gb, f_grass(gx, gb, gh, rng.choice(GREENS) + (1,), sc)))
        # ET DE L'HERBE A RAMASSER, A PORTEE DE MAIN. [recoltable: Herbe]
        #
        # La foret n'en donnait pas : il fallait retourner en plaine pour la
        # moindre fibre, alors qu'il pousse de l'herbe sous les arbres et
        # qu'on en voit partout dans la scene. C'est un TYPE DE PLUS sur la
        # case, pas un partage de ce qui s'y trouvait : la foret gagne donc
        # les deux a cinq ramassages d'herbe en plus de tout le reste (voir
        # _avail_for).
        #
        # UN LOT A PART, et non les touffes ci-dessus : une recolte masque
        # une part egale des objets de son type (voir _take_or_skip), et
        # rendre les 950 touffes recoltables aurait fait fondre le tapis de
        # sous-bois d'un cinquieme a chaque poignee. Celles-ci sont posees
        # sous la hauteur des mains, la ou l'on peut vraiment les atteindre.
        for _ in range(HERBE_RECOLTABLE_FORET):
            fx = grass_pick() if rng.random() < 0.72 else None
            gx, gb, sc, t = place(fx=fx, floor=_HARVEST_FLOOR)
            gh = rng.uniform(0.06, 0.15) * h * sc
            if (not self._take_or_skip("Herbe")
                    and not self._is_blocked(gx, gb, gb + gh)):
                items.append((gb, f_grass(gx, gb, gh,
                                          rng.choice(GREENS) + (1,), sc)))
        # Fougeres / plantes (bosquets).
        for _ in range(rng.randint(8, 12)):
            px, py, sc, t = place(fx=fern_pick())
            s = rng.uniform(0.05, 0.10) * h * sc
            if self._is_blocked(px, py, py + s * 1.05):
                continue
            items.append((py, lambda px=px, py=py, s=s:
                          self._plant(px, py, s, sprite=self._zs("plant"))))
        # (Les buissons de sous-bois sont desormais des GROS elements places
        #  sur la grille 5x5, voir plus bas.)
        # Champignons (uniquement bruns pour l'instant).
        # [recoltable: Brown_Mushroom]
        if rng.random() < 0.8:
            for _ in range(rng.randint(2, 4)):
                mx, my, sc, t = place(1.0, fx=mush_pick(), floor=_HARVEST_FLOOR)
                s = rng.uniform(0.03, 0.05) * h * sc
                cap = (0.62, 0.30, 0.18, 1)
                if (not self._take_or_skip("Brown_Mushroom")
                        and not self._is_blocked(mx, my)):
                    items.append((my, lambda mx=mx, my=my, s=s, cap=cap:
                                  self._mushroom(mx, my, s, cap,
                                                 sprite=self._zs("mushroom"))))
        # Arbres + buissons PROCHES : GROS elements positionnes sur la GRILLE
        # 5x5 (les memes cases sont interdites a l'installation d'un objet :
        # impossible de mettre un feu de camp sous un arbre).
        for kind, rang, depth, tx, tb, jit in self._iter_nature_big():
            if kind == "nugget":
                items.extend(self._pepite_de_grille(rang, depth, tx, tb, jit))
                continue
            if kind == "tree":
                th = (1.00 - 0.58 * depth) * jit.uniform(0.85, 1.10) * h
                if jit.random() < 0.5:
                    tw = (0.11 - 0.05 * depth) * jit.uniform(0.85, 1.15) * w
                    items.append((tb, lambda tx=tx, tb=tb, tw=tw, th=th:
                                  self._pine(tx, tb, tw, th,
                                             (0.06, 0.15, 0.09, 1))))
                else:
                    sc = 1.0 - 0.6 * depth
                    items.append((tb, lambda tx=tx, tb=tb, th=th, sc=sc:
                                  self._forest_tree(tx, tb, th, sc)))
            else:                                     # buisson de sous-bois
                g2 = jit.uniform(0.0, 0.06)
                r = (0.13 - 0.06 * depth) * jit.uniform(0.85, 1.15) * h
                items.append((tb - self.DEBORD_BUISSON * r,
                              lambda bx=tx, by=tb, r=r, g2=g2:
                              self._bush(bx, by, r,
                                         (0.06 + g2, 0.16 + g2, 0.09, 1),
                                         sprite=self._zs("bush"))))
        # Ligne d'arbres DENSE a l'horizon (lointains et petits) : HORS grille
        # (au-dela de la zone d'installation), purement decorative.
        m = rng.randint(24, 32)
        for i in range(m):
            fx = min(0.999, max(0.001, i / (m - 1) + rng.uniform(-0.02, 0.02)))
            tb = floor_curve(fx) - rng.uniform(0.0, 0.03) * h
            tx = x0 + fx * w
            if rng.random() < 0.55:
                tw = rng.uniform(0.03, 0.06) * w
                th = rng.uniform(0.12, 0.22) * h
                items.append((tb, lambda tx=tx, tb=tb, tw=tw, th=th:
                              self._pine(tx, tb, tw, th, (0.09, 0.17, 0.11, 1),
                                         shadow=False)))
            else:
                th = rng.uniform(0.12, 0.20) * h
                items.append((tb, lambda tx=tx, tb=tb, th=th:
                              self._forest_tree(tx, tb, th, 0.4, shadow=False)))
        # (Les insectes sont desormais une couche ANIMEE separee : InsectLayer.)

        items += self._installed_items()     # feu de camp... a leur profondeur
        items += self._edge_items()          # la case d'a cote, qui deborde
        self._dessine(items)

    # -- objets recoltables / insectes (details) ----------------------- #
    def _mushroom(self, cx, base, size, cap, sprite=None):
        self._shadow(cx, base + size * 0.10, size * 1.4)  # ombre au sol
        if self._sprite(sprite, cx, base, size * 1.45):
            return
        Color(0.92, 0.88, 0.78, 1)                       # tige
        Rectangle(pos=(cx - size * 0.18, base), size=(size * 0.36, size * 0.9))
        Color(0, 0, 0, 0.18)                             # ombre sous le chapeau
        Ellipse(pos=(cx - size * 0.55, base + size * 0.58),
                size=(size * 1.1, size * 0.28))
        Color(*cap)                                      # chapeau
        Ellipse(pos=(cx - size * 0.6, base + size * 0.62),
                size=(size * 1.2, size * 0.8))
        Color(1, 1, 1, 0.85)                             # points
        for dx in (-0.3, 0.05, 0.32):
            Ellipse(pos=(cx + dx * size, base + size * 0.85),
                    size=(size * 0.14, size * 0.14))

    def _berries(self, cx, cy, r):
        self._shadow(cx, cy - r * 0.2, r * 2.2)
        if self._sprite("berries_bush", cx, cy - r * 0.3, r * 2.0):
            return
        Color(0.10, 0.28, 0.13, 1)                       # buisson
        for off in (-0.6, 0.0, 0.6):
            Ellipse(pos=(cx + off * r - r * 0.6, cy - r * 0.3),
                    size=(r * 1.2, r * 1.0))
        Color(0.85, 0.16, 0.20, 1)                       # baies
        for dx, dy in ((-0.4, 0.2), (0.1, 0.45), (0.5, 0.15),
                       (-0.1, 0.0), (0.3, 0.5)):
            d = r * 0.32
            Ellipse(pos=(cx + dx * r - d / 2, cy + dy * r - d / 2), size=(d, d))

    @staticmethod
    def _ell_c(ex, ey, w, hh):
        """Ellipse CENTREE sur (ex, ey)."""
        Ellipse(pos=(ex - w / 2, ey - hh / 2), size=(w, hh))

    def _flower(self, cx, cy, size, color, petals=5, sprite=None):
        """Fleur : petales allonges disposes en etoile + coeur, au lieu d'un
        simple rond. `size` ~ rayon de la fleur."""
        if self._sprite(sprite, cx, cy - size * 0.6, size * 2.6):
            return
        r, g, b, a = color
        pw = size * 0.62                                   # largeur d'un petale
        pl = size * 1.25                                   # longueur d'un petale
        for k in range(petals):
            PushMatrix()
            Rotate(angle=360.0 * k / petals, origin=(cx, cy))
            Color(r * 0.78, g * 0.78, b * 0.78, a)         # bord du petale
            Ellipse(pos=(cx - pw / 2, cy + size * 0.10), size=(pw, pl))
            Color(r, g, b, a)                              # petale
            Ellipse(pos=(cx - pw * 0.4, cy + size * 0.16),
                    size=(pw * 0.8, pl * 0.88))
            Color(min(1, r + 0.18), min(1, g + 0.18), min(1, b + 0.18), a)
            Ellipse(pos=(cx - pw * 0.22, cy + size * 0.45),
                    size=(pw * 0.44, pl * 0.5))            # reflet clair
            PopMatrix()
        Color(0.85, 0.62, 0.16, 1)                         # coeur (contour)
        self._ell_c(cx, cy, size * 0.66, size * 0.66)
        Color(0.98, 0.82, 0.28, 1)                         # coeur (clair)
        self._ell_c(cx, cy, size * 0.44, size * 0.44)
        Color(0.78, 0.55, 0.14, 0.9)                       # grains au centre
        for dx, dy in ((-0.12, 0.08), (0.12, 0.06), (0.0, -0.12)):
            self._ell_c(cx + dx * size, cy + dy * size, size * 0.12, size * 0.12)

    # -- pepites de mineraux --------------------------------------------- #
    #
    # Elles sont dans TOUTES les zones, et c'est le meme code qui les pose
    # partout : une pierre est une pierre, la foret n'a pas les siennes.
    #
    # LEUR TAILLE SE MESURE SUR LE BUISSON DE PLAINE. C'est la reference
    # demandee, et c'est aussi le seul gros element qu'on trouve a toutes les
    # profondeurs : une pepite fait de -20 % a +20 % de sa hauteur, donc elle
    # grossit et retrecit avec la distance comme lui.
    RAYON_BUISSON_PLAINE = (0.17, 0.09)   # au premier plan, puis ce qu'il
    ECART_PEPITE = 0.20                   # perd au fond ; -20 % a +20 %

    # LARGEUR D'UNE PEPITE, en rayons. Elle vient d'une mesure, pas d'un
    # calcul : on dessine un buisson et une pepite au meme rayon, on releve
    # les deux boites, et on cherche le facteur qui leur donne la MEME
    # EMPRISE (largeur x hauteur).
    #
    # Pourquoi l'emprise et non la seule largeur : un buisson mesure 2,89 r de
    # large pour 1,51 r de haut, une pepite 2,89 r pour 2,33 r. A largeur
    # egale -- ce qu'on faisait -- la pierre etait donc une fois et demie plus
    # haute que le buisson, et elle ecrasait la scene comme un rocher. Le
    # facteur qui egalise les emprises vaut racine(1,51 / 2,33) = 0,81, d'ou
    # 2,89 x 0,81.
    LARGEUR_PEPITE = 2.35

    # UN CRAN TOUS LES N PIXELS a la base d'une pierre. Plus fin que le pas
    # du sol (quatorze) : le sol se dentelle sur toute la largeur de l'ecran,
    # une pierre sur deux cents pixels. Au pas du sol elle n'aurait eu que
    # huit crans -- des marches d'escalier, pas une dentelure.
    SEGMENT_CRAN = 8.0

    # DE COMBIEN SA COUPE EST DENTELEE, en part de sa LARGEUR. La frange du
    # sol se mesure a la tuile de la texture ; celle d'une pierre se mesure a
    # la pierre -- une petite pierre a de petits crans. A 3,5 %, une pierre de
    # 190 px en a de sept, soit l'ordre de grandeur de la frange du sol sur un
    # telephone : les deux bords se ressemblent, ce qui est le but.
    FRANGE_PEPITE = 0.035

    # DE COMBIEN ELLE EST ENTERREE, en part de sa hauteur. Une pierre posee
    # SUR le sol est une pierre qu'on vient d'y deposer : le decor en paraît
    # meuble. Enfoncee, elle a toujours ete la.
    ENFONCE_PEPITE = (0.25, 0.50)

    # LA TERRE DE CHAQUE ZONE, pour le bourrelet au pied de la pierre. C'est
    # la surface PROCHE de la zone -- celle sur laquelle reposent les elements
    # de la grille -- et non celle de l'horizon.
    #
    # Le lac reste de l'EAU. Un haut-fond de sable y avait ete essaye ; il
    # dessinait une galette brune autour de chaque pierre, et la pierre avait
    # l'air posee sur un radeau. L'eau, elle, ne se voit pas contre l'eau : il
    # ne reste que la ligne de flottaison sombre, qui est exactement ce qu'on
    # veut voir.
    SOL_DE_ZONE = {"Foret": "forest_floor", "Plaine": "grass",
                   "Montagne": "rock", "Lac": "water"}

    # TEINTE DE LA PIERRE, PAR ZONE. Les images sont des photos de granit :
    # mesure faite, elles sortent a 0,55 de luminosite pour 0,06 de saturation
    # -- un gris clair et parfaitement neutre. Le sol de foret, lui, est a
    # 0,12. La pierre etait donc de loin la chose la plus claire de l'ecran,
    # et sans la moindre couleur commune avec ce qui l'entoure : elle se
    # decollait de la scene comme un autocollant.
    #
    # Chaque zone la ramene donc a sa propre lumiere et lui prete un peu de sa
    # couleur -- vert sous les arbres, chaud dans l'herbe. C'est le meme
    # granit partout, vu sous plusieurs ciels.
    #
    # LES VALEURS NE SONT PAS CHOISIES A L'OEIL. Ce qui fait qu'un element
    # "sort" d'une scene n'est pas sa couleur en soi, c'est son ECART avec ce
    # qui l'entoure. On a donc mesure ce rapport sur le decor que le jeu
    # dessine DEJA -- c'est lui la direction artistique, pas une intuition :
    #
    #   gros rocher de montagne  0,90 x la luminosite de son sol
    #   buisson de foret         1,81 x
    #   buisson de plaine        0,66 x
    #
    # La pepite etait a 2,36 x en foret : plus de deux fois plus claire que le
    # sol, la chose la plus lumineuse de l'ecran. Les teintes ci-dessous la
    # ramenent a 1,35 x -- ENTRE les deux references que le jeu se donne. Plus
    # claire que le sol, parce qu'une pierre prend le jour du ciel ; moins
    # qu'un buisson, parce qu'elle n'est pas censee attirer l'oeil avant lui.
    #
    # LA FORET PREND LA MEME TEINTE QUE LA PLAINE, sur epreuve dans le jeu.
    # Calee a 1,35 x d'un sol aussi sombre, la pierre y devenait une tache
    # noire : la regle du rapport constant tenait sur le papier, pas devant
    # l'ecran. Et elle avait tort sur le fond -- la foret est sombre parce
    # qu'elle est A L'OMBRE DES ARBRES, alors qu'une pierre qui affleure
    # recoit le meme ciel qu'ailleurs. Une seule teinte pour les deux zones
    # dit exactement cela : c'est le meme granit, sous le meme ciel.
    #
    # Le rapport au sol n'est donc plus le meme partout. Le test l'affiche
    # toujours, mais comme un CONSTAT, plus comme une regle a tenir.
    #
    # L'entree du LAC ne sert plus : il n'y a plus de pepites dans l'eau (voir
    # world.SANS_PEPITES). Elle reste pour le jour ou il en reprendrait, mais
    # elle n'a PAS ete mesuree comme les autres.
    # LA TEINTE NE SUFFIT PAS, ET NE PEUT PAS SUFFIRE. Multiplier une image
    # change sa couleur mais JAMAIS son contraste : la photo garde des noirs
    # et des blancs que rien d'autre dans la scene ne possede, et la pierre
    # continue de se detacher comme un decoupage. Deux aplats poses par-dessus
    # sa silhouette corrigent cela (voir _etalonne_pepite) :
    #
    #  - un VOILE de la couleur du decor, d'autant plus epais que la pierre
    #    est loin : c'est l'air entre l'oeil et elle. Il rapproche ses tons de
    #    ceux du fond, donc il ecrase son contraste -- exactement ce qu'il
    #    faut ;
    #  - un DEGRADE sombre a son pied, qui s'eteint a mi-hauteur : la lumiere
    #    vient du ciel, le haut d'un caillou la recoit, son pied ne la recoit
    #    plus. C'est le signal de relief le plus fort dont on dispose sans
    #    carte de normales.
    #
    # L'HEURE n'entre pas ici : le voile de nuit passe sur TOUTE la scene une
    # fois celle-ci dessinee (voir daylight.veil_color et les ecrans). Teinter
    # la pierre une deuxieme fois l'aurait desynchronisee du reste.
    VOILE_PEPITE = (0.12, 0.34)    # epaisseur du voile : au plus pres, au fond
    PIED_PEPITE = 0.45             # noirceur au pied de la pierre
    PIED_HAUTEUR = 0.55            # sur quelle part de sa hauteur il s'eteint
    BANDES_PEPITE = 7              # en combien de marches (assez pour ne pas
    #                                se voir : mesure, 5 se voyaient)

    TEINTE_PEPITE = {"Foret": (0.815, 0.783, 0.661),   # la meme que la plaine
                     "Plaine": (0.815, 0.783, 0.661),
                     "Montagne": (0.858, 0.858, 0.879),
                     "Lac": (0.607, 0.644, 0.662)}

    def _pepite_de_grille(self, rang, depth, cx, base, jit):
        """Une pepite posee sur la grille 5x5, comme un arbre ou un buisson.

        Elle y a sa place pour deux raisons : on la voit alors dans l'ecran de
        PROXIMITE au meme titre que le reste du decor, et on ne peut plus
        installer un feu de camp dessus. Combien il y en a par case est decide
        par le monde (voir world.nature_blocked_cells) : ici, on ne fait que
        les dessiner.

        LE RANG REPARTIT LES MODELES : une case a cinq pepites en montre cinq
        differentes, au lieu de laisser le hasard des positions en repeter.
        Il est DECALE d'un cran tire de la graine de la case -- sans ce
        decalage, le premier modele sortait sur toutes les cases qui portent
        au moins une pepite et le cinquieme seulement sur celles qui en
        portent cinq : mesure, un contre huit."""
        a, b = self.RAYON_BUISSON_PLAINE
        r = (a - b * depth) * jit.uniform(1.0 - self.ECART_PEPITE,
                                          1.0 + self.ECART_PEPITE) * self.height
        decalage = random.Random("%s:variante" % self._seed).randrange(5)
        enfonce = jit.uniform(*self.ENFONCE_PEPITE)
        # LA PIERRE ET SON HERBE SONT DES ELEMENTS SEPARES pour le tri par
        # profondeur, et il le faut : une touffe qui pousse devant la pierre
        # doit passer devant elle, une touffe de cote derriere ce qui est plus
        # proche. Dessinees toutes ensemble a la cle de la pierre, elles
        # recouvraient ce qui etait devant -- mesure, jusqu'a 72 recouvrements
        # fautifs par scene de foret, dont des troncs d'arbres.
        return [(base - self.DEBORD_PEPITE * r,
                 lambda cx=cx, base=base, r=r, v=rang + decalage,
                 e=enfonce, d=depth: self._pepite(cx, base, r, v, e, d))] \
            + self._herbe_de_pepite(cx, base, r * self.LARGEUR_PEPITE, depth)

    def _pepite(self, cx, base, r, variante, enfonce=0.35, depth=0.0):
        """Une pepite : un bloc de pierre a demi enterre.

        Cent pour cent de pierre grise pour l'instant -- aucun minerai. Quand
        il y en aura, ils se distingueront ici et nulle part ailleurs : la
        pepite est un element du decor, pas un objet, et c'est le decor qui
        dit de quoi elle a l'air.

        TROIS CHOSES L'ANCRENT AU SOL, et il les faut toutes les trois : la
        part enterree n'est pas dessinee, la terre remonte contre elle, et
        elle est teintee de la lumiere de sa zone."""
        # ON LA POSE PAR SA LARGEUR, pas par sa hauteur : les cinq images
        # n'ont pas le meme aplatissement, et c'est la place prise AU SOL qui
        # doit rester la meme de l'une a l'autre.
        largeur = r * self.LARGEUR_PEPITE
        # UNE OMBRE PORTEE COURTE : la pierre est a demi enterree, elle n'a
        # plus grand-chose au-dessus du sol pour porter loin. A la taille
        # qu'elle avait quand la pierre etait POSEE, elle s'etalait autour
        # d'elle en flaque grise.
        self._shadow(cx, base - largeur * 0.02, largeur * 0.88, opacity=0.85)
        teinte = self.TEINTE_PEPITE.get(self._zone,
                                        self.TEINTE_PEPITE["Plaine"])
        # LES MEMES CRANS POUR L'IMAGE ET POUR SES VOILES : tires une seule
        # fois ici, puis passes aux deux. Chacun les tirant de son cote, le
        # voile aurait peint sa couleur dans les echancrures de la pierre.
        crans = self._crans_de_pepite(largeur, variante)
        if self._sprite("ore_nugget", cx, base, None, pick=variante,
                        width=largeur, teinte=teinte, coupe_bas=enfonce,
                        crans=crans):
            self._etalonne_pepite(cx, base, largeur, variante, enfonce, depth,
                                  crans)
            self._pied_de_pepite(cx, base, largeur, depth)
            return
        # Sans image : un bloc anguleux, plus sombre et plus trapu qu'un
        # galet, pour qu'on ne le confonde pas avec les pierres a ramasser.
        # Il est rogne du meme enfoncement, par le bas.
        w2 = largeur / 2.0
        plein = largeur * 0.78
        haut = plein * (1.0 - enfonce)

        def y(part):
            """La hauteur `part` du bloc entier, ramenee au-dessus du sol."""
            return base + max(0.0, plein * part - plein * enfonce)

        Color(0.34, 0.34, 0.37, 1)
        Quad(points=[cx - w2, base, cx + w2, base,
                     cx + w2 * 0.72, y(0.66), cx - w2 * 0.80, y(0.58)])
        Color(0.48, 0.48, 0.52, 1)
        Quad(points=[cx - w2 * 0.80, y(0.58), cx + w2 * 0.72, y(0.66),
                     cx + w2 * 0.18, base + haut,
                     cx - w2 * 0.52, base + haut * 0.92])
        self._pied_de_pepite(cx, base, largeur, depth)

    def _etalonne_pepite(self, cx, base, largeur, variante, enfonce, depth,
                         crans=None):
        """Rapproche la photo de pierre des couleurs de la scene.

        Voir VOILE_PEPITE : un voile de la couleur du decor, epaissi par la
        distance, puis un degrade sombre a son pied. Les deux sont poses sur
        sa SILHOUETTE -- un simple rectangle teinterait aussi le vide autour.

        Sans silhouette (pas d'image, ou image illisible), on ne fait rien :
        le repli geometrique porte deja ses propres couleurs."""
        sil = foliage.silhouette("ore_nugget", variante)
        if sil is None:
            return
        tw, th = sil.size
        if not tw or not th:
            return
        self._voiles(sil, None, cx, base, largeur,
                     largeur * (float(th) / float(tw)), enfonce, depth, crans,
                     self.SOL_DE_ZONE.get(self._zone, "rock"),
                     self.BANDES_PEPITE)

    def _voiles(self, sil, uv, cx, base, largeur, h_pleine, enfonce, depth,
                crans, sol, bandes):
        """Le voile et le degrade du pied (voir _etalonne_pepite), poses sur
        la silhouette `sil` -- une image entiere, ou une case de planche si
        `uv` est donne (voir _caillou). `h_pleine` est la hauteur a l'ecran
        de l'image ENTIERE, part enterree comprise ; `sol`, le nom de la
        texture du sol dans lequel la pierre doit se fondre."""
        haut = h_pleine * (1.0 - enfonce)
        gauche = cx - largeur / 2.0
        vu = 1.0 - enfonce          # la part de l'image qui sort de terre
        u0, u1, vh, vp = uv or (0.0, 1.0, 0.0, 1.0)

        # LES BANDES SUIVENT LA COUPE DENTELEE, colonne par colonne. Posees a
        # plat, elles debordaient dans les crans : la ou la pierre remonte, la
        # silhouette est encore opaque, et le voile peignait donc sa couleur
        # sur le SOL, dans l'echancrure meme qu'on venait de creuser.
        n_cols = len(crans) - 1 if crans else 1

        def bande(y0, y1, coul, alpha):
            """Un morceau de la silhouette, de y0 a y1 (0 = sol, 1 = sommet)."""
            if alpha <= 0.002 or y1 <= y0:
                return
            bas_nom, haut_nom = base + haut * y0, base + haut * y1
            Color(coul[0], coul[1], coul[2], alpha)
            verts, idx = [], []
            for i in range(n_cols + 1):
                u = i / n_cols
                x = gauche + u * largeur
                uu = u0 + (u1 - u0) * u
                # Le bas de la colonne : le plus HAUT de la ligne nominale et
                # du cran. Borne par le haut de la bande, sinon elle
                # s'inverserait la ou le cran la depasse.
                cran = base + (crans[i] if crans else 0.0)
                bas = min(max(bas_nom, cran), haut_nom)
                # v DESCEND dans l'image quand l'ecran MONTE (voir
                # textures.py) : un pixel d'ecran vaut 1/h_pleine de v.
                verts += [x, bas, uu,
                          vh + (vp - vh) * (vu - (bas - base) / h_pleine)]
                verts += [x, haut_nom, uu,
                          vh + (vp - vh) * (vu - (haut_nom - base) / h_pleine)]
                if i:
                    p = (i - 1) * 2
                    idx += [p, p + 1, p + 2, p + 1, p + 3, p + 2]
            Mesh(vertices=verts, indices=idx, mode="triangles", texture=sil)

        # LA COULEUR REELLEMENT POSEE AU SOL, texture comprise -- pas celle du
        # repli. Les deux s'ecartent beaucoup des qu'une image existe (voir
        # textures.average_color), et c'est dans le sol tel qu'on le VOIT que
        # la pierre doit se fondre.
        decor = textures.average_color(sol)
        pres, loin = self.VOILE_PEPITE
        bande(0.0, 1.0, decor, pres + (loin - pres) * max(0.0, min(1.0, depth)))

        # LE DEGRADE DU PIED, en marches : une Mesh ne sait pas donner une
        # couleur par sommet, et c'est la facon la plus simple d'obtenir un
        # fondu. Sept marches ne se voient pas ; cinq se voyaient.
        sombre = tuple(c * 0.35 for c in decor)
        n = bandes
        for i in range(n):
            y0, y1 = i / n, (i + 1) / n
            t = (y0 + y1) / 2.0 / self.PIED_HAUTEUR
            if t >= 1.0:
                break
            bande(y0, y1, sombre, self.PIED_PEPITE * (1.0 - t) ** 2)

    # L'HERBE AU PIED DE LA PIERRE : combien de touffes, sur quelle largeur
    # (en part de la largeur de la pierre) et quelle hauteur.
    # Valeurs prises sur une planche d'essais (9 / 14 / 18 / 24 touffes) : a 9
    # le trait de coupe se lit encore entre les touffes, a 24 l'herbe avale la
    # pierre et fait une haie.
    TOUFFES_PEPITE = 14
    DEBORD_HERBE = 1.10
    HAUTEUR_HERBE = (0.16, 0.26)      # au milieu, puis sur les flancs

    # LA COULEUR DE L'HERBE DE CHAQUE ZONE, reprise de sa scene. La foret a
    # son vert sombre de sous-bois, la plaine son vert de pre, la montagne ses
    # touffes rases et grises. Le lac n'en a pas besoin : plus de pepites dans
    # l'eau.
    HERBE_DE_ZONE = {"Foret": (0.10, 0.20, 0.12, 1),
                     "Plaine": (0.20, 0.40, 0.14, 1),
                     "Montagne": (0.22, 0.34, 0.16, 1),
                     "Lac": (0.18, 0.34, 0.16, 1)}

    def _pied_de_pepite(self, cx, base, largeur, depth):
        """L'OMBRE DE CONTACT au pied de la pierre, dessinee avec elle.

        La terre au pied d'une pierre ne recoit plus le ciel. Sans ce lisere
        sombre, la pierre coupee net a la ligne du sol a l'air posee derriere
        un muret.

        ELLE RESTE SOUS LA PIERRE et s'amincit vers les flancs. Etalee plus
        largement -- ce qui avait ete fait d'abord -- elle debordait de part et
        d'autre en deux croissants sombres : la pierre portait une moustache.
        Une ombre de contact n'existe que la ou il y a contact.

        SA COURBE EST UN SOURIRE : on regarde d'en haut et de biais, le point
        du sol le plus PROCHE est celui droit devant la pierre, et le plus
        proche est le plus BAS a l'ecran ; les flancs, eux, sont plus loin
        donc plus hauts.

        L'herbe qui acheve de la raccorder au sol est ailleurs : elle se trie
        avec le reste du decor (voir _herbe_de_pepite)."""
        demi = largeur / 2.0
        creux_max = largeur * 0.065
        verts, idx, segs = [], [], 22
        for i in range(segs + 1):
            dx = -demi + 2.0 * demi * i / segs
            haut = base + creux_max * 0.35 * (dx / demi) ** 2
            creux = creux_max * (1.0 - (dx / demi) ** 2)
            for yy in (haut - creux, haut):
                verts += [cx + dx, yy, 0, 0]
            if i:
                p = (i - 1) * 2
                idx += [p, p + 1, p + 2, p + 1, p + 3, p + 2]
        Color(0.04, 0.04, 0.03, 0.30)
        Mesh(vertices=verts, indices=idx, mode="triangles", texture=None)

    def _herbe_de_pepite(self, cx, base, largeur, depth):
        """L'herbe qui pousse au pied de la pierre : [(cle de tri, dessin)].

        ON NE SOULEVE PLUS LE TERRAIN. Un bourrelet de terre etait dessine ici,
        avec la vraie matiere du sol : il faisait le travail, mais il ajoutait
        une bosse la ou il n'y en a pas, et cela se voyait des qu'on regardait.
        L'herbe fait mieux et ne ment pas : elle POUSSE au pied des pierres,
        c'est meme la qu'elle pousse le mieux -- a l'abri du pietinement. Et
        comme elle est deja partout dans la scene, rien ne signale qu'elle a
        ete mise la pour cacher quelque chose.

        CHAQUE TOUFFE EST TRIEE POUR ELLE-MEME, a sa propre profondeur : celle
        qui pousse devant la pierre passe devant elle, celle de cote passe
        derriere ce qui est plus proche.

        LES TOUFFES SONT PLUS HAUTES SUR LES FLANCS que droit devant, pour la
        meme raison que l'ombre dessine un sourire : les flancs sont plus loin,
        donc plus haut a l'ecran, donc il en faut davantage pour couvrir la
        coupe.

        Elles se balancent au vent comme toutes les autres (voir _grass_tuft) :
        c'est ce qui acheve de les faire passer pour de l'herbe de la scene et
        non pour un cache-misere fige."""
        col = self.HERBE_DE_ZONE.get(self._zone)
        if not col:
            return []
        demi = largeur / 2.0
        # Le hasard tient a la POSITION : la touffe ne change pas d'un
        # redessin a l'autre, comme tout le reste du decor.
        jit = random.Random("%s:%.1f:%.1f:herbe" % (self._seed, cx, base))
        h0, h1 = self.HAUTEUR_HERBE
        n = self.TOUFFES_PEPITE
        out = []
        for i in range(n):
            # Reparties sur la largeur, avec un peu de flou : alignees, elles
            # auraient fait une haie.
            t = (i + 0.5) / n + jit.uniform(-0.35, 0.35) / n
            dx = (t * 2.0 - 1.0) * demi * self.DEBORD_HERBE
            f = min(1.0, abs(dx) / demi)
            haut = largeur * (h0 + (h1 - h0) * f) * jit.uniform(0.75, 1.25)
            by = base + largeur * 0.055 * f ** 2 - largeur * 0.02
            g = jit.uniform(-0.03, 0.05)
            teinte = (max(0.0, col[0] + g), max(0.0, col[1] + g),
                      max(0.0, col[2] + g * 0.5), col[3])
            ech = (1.0 - 0.45 * depth) * jit.uniform(0.8, 1.2)
            out.append((by, self._touffe(cx + dx, by, haut, teinte, ech)))
        return out

    # -- petites pierres ------------------------------------------------- #
    #
    # CE SONT DES PEPITES EN PETIT : memes photos, memes cartes de relief,
    # memes astuces. Elles etaient dessinees en ovales gris -- trois ellipses
    # et un trait -- a cote de pepites photographiques eclairees par le
    # soleil : deux mondes sur le meme sol.
    #
    # Elles se lisent dans une PLANCHE reduite, et non dans les images de la
    # pepite : dessinees trois a six fois plus petites que celles-ci, elles
    # fourmillaient sans versions reduites (voir foliage.planche_pierres).
    #
    # LES MEMES STRATAGEMES QUE LA PEPITE POUR QU'AUCUNE NE SE RESSEMBLE. Il
    # y en a des dizaines par scene -- une quarantaine sur la pente de
    # montagne -- pour cinq photos. Chacune tire donc, de sa position :
    #   - sa FORME parmi dix : les cinq photos, et chacune en miroir ;
    #   - son ENFONCEMENT (ENFONCE_PEPITE) : la meme photo coupee au quart ou
    #     a la moitie n'a plus la meme silhouette -- c'est le stratageme qui
    #     change le plus une pierre ;
    #   - sa COUPE DENTELEE, propre a elle (voir _crans_de_pepite) ;
    #   - une CLARTE et une NUANCE a elle, un peu plus chaude ou plus froide :
    #     des cailloux d'un meme tas n'ont jamais tout a fait le meme gris.
    # Et comme la pepite, elle prend la teinte de sa zone, le voile de sa
    # distance, un pied sombre et une ombre de contact.
    #
    # PAS D'HERBE A SON PIED, a la difference de la pepite : a cette taille,
    # quatorze touffes l'auraient noyee, et le sol en porte deja partout.
    LARGEUR_CAILLOU = 2.2        # x son rayon : l'emprise de l'ancien ovale
    ECLAT_CAILLOU = 0.08         # clarte : +/- 8 % d'une pierre a l'autre
    NUANCE_CAILLOU = 0.04        # plus chaude ou plus froide : +/- 4 %
    # Cinq marches suffisent au degrade du pied : il fait ici une quinzaine
    # de pixels, pas une centaine (voir BANDES_PEPITE).
    BANDES_CAILLOU = 5
    # Son debord sous sa base (voir DEBORD_PEPITE) : la meme forme que la
    # pepite, donc le meme debord a proportion de sa largeur.
    DEBORD_CAILLOU = DEBORD_PEPITE * LARGEUR_CAILLOU / LARGEUR_PEPITE

    def _caillou(self, cx, base, r, depth=0.0, enfonce=None, pose=False):
        """Une petite pierre, tiree des photos de la pepite (voir plus haut).

        `enfonce` impose la part enterree au lieu de la tirer (voir le foyer,
        dont les pierres sont posees et non affleurantes).

        `pose` : une pierre POSEE SUR UNE AUTRE (voir l'etabli). Elle ne
        touche pas le sol : rien d'enterre, ni ombre portee, ni voile de terre
        a son pied.

        Faux si la planche n'a pas pu etre faite : l'appelant garde alors son
        dessin d'origine."""
        planche = foliage.planche_pierres("ore_nugget")
        if planche is None:
            return False
        pick = self._pick(cx, base)
        uv, uv_sil, pw, ph = planche.case(pick)
        if not pw or not ph:
            return False
        jit = random.Random("%s:%.1f:%.1f:caillou" % (self._seed, cx, base))
        tire = jit.uniform(*self.ENFONCE_PEPITE)
        enfonce = tire if enfonce is None else enfonce
        if pose:
            enfonce = 0.0
        eclat = 1.0 + jit.uniform(-self.ECLAT_CAILLOU, self.ECLAT_CAILLOU)
        nuance = jit.uniform(-self.NUANCE_CAILLOU, self.NUANCE_CAILLOU)
        base_teinte = self.TEINTE_PEPITE.get(self._zone,
                                             self.TEINTE_PEPITE["Plaine"])
        # Le vert suit le rouge a moitie : une pierre chaude tire sur le
        # beige. Le rouge seul la faisait tirer sur le rose.
        teinte = (min(1.0, base_teinte[0] * eclat * (1.0 + nuance)),
                  min(1.0, base_teinte[1] * eclat * (1.0 + nuance * 0.5)),
                  min(1.0, base_teinte[2] * eclat * (1.0 - nuance)))
        largeur = r * self.LARGEUR_CAILLOU
        h_pleine = largeur * float(ph) / float(pw)
        # Posee, elle n'a pas de coupe : son bas est droit, et entier.
        crans = ([0.0, 0.0] if pose
                 else self._crans_de_pepite(largeur, pick))

        if not pose:
            self._shadow(cx, base - largeur * 0.02, largeur * 0.88,
                         opacity=0.85)
        # Les cartes de relief restent liees pendant les voiles : leurs
        # silhouettes tombent, dans la planche des normales, sur des cases
        # PLATES -- le voile n'est donc pas eclaire, comme sur la pepite.
        if self._pbr:
            pbr.bind_maps(planche.normales, planche.packed)
        Color(teinte[0], teinte[1], teinte[2], 1)
        self._sprite_enfoui(planche.tex, cx, base, largeur, h_pleine, enfonce,
                            crans, uv)
        if not pose:
            self._voiles(planche.tex, uv_sil, cx, base, largeur, h_pleine,
                         enfonce, depth, crans,
                         self.SOL_DE_ZONE.get(self._zone, "rock"),
                         self.BANDES_CAILLOU)
        if self._pbr:
            self._reset_pbr()
        if not pose:
            self._pied_de_pepite(cx, base, largeur, depth)
        return True

    def _stone(self, cx, cy, r, sprite=None, depth=0.0):
        # UNE IMAGE PROPRE A LA ZONE passe avant tout : il suffit d'en deposer
        # une (stone_plain.png...). A defaut, la pierre prend les photos de
        # la pepite (voir _caillou), et ce n'est que sans elles qu'elle
        # retombe sur son dessin geometrique.
        if not (sprite and foliage.variants(sprite)) \
                and self._caillou(cx, cy, r, depth):
            return
        self._shadow(cx, cy - r * 0.05, r * 2.1)          # ombre portee
        if self._sprite(sprite, cx, cy, r * 1.5):
            return
        Color(0.30, 0.31, 0.34, 1)                        # bas sombre
        Ellipse(pos=(cx - r, cy), size=(r * 2, r * 1.25))
        Color(0.46, 0.47, 0.51, 1)                        # corps
        Ellipse(pos=(cx - r * 0.95, cy + r * 0.18), size=(r * 1.9, r * 1.05))
        Color(0.60, 0.61, 0.66, 1)                        # reflet (haut-gauche)
        Ellipse(pos=(cx - r * 0.7, cy + r * 0.55), size=(r * 1.0, r * 0.6))
        Color(0.22, 0.22, 0.25, 0.5)                      # fissure
        Line(points=[cx - r * 0.3, cy + r * 0.2,
                     cx + r * 0.1, cy + r * 0.95], width=1.0)

    # Inclinaison maximale d'un baton pose au sol, en degres. Tous a plat et
    # alignes, ils se liraient comme des traits de regle ; un peu de pente,
    # et ils tombent au hasard comme de vrais bois morts.
    BATON_PENTE = 9.0
    # Opacite de son ombre de contact. Sans elle, un baton sur l'herbe
    # semblait colle par-dessus l'image, pas pose sur le sol.
    BATON_OMBRE = 0.32

    def _branch(self, cx, cy, length, sprite=None):
        wdt = max(1.5, length * 0.07)
        if sprite and self._baton(sprite, cx, cy, length):
            return
        Color(0, 0, 0, 0.14)                              # ombre
        Line(points=[cx - length / 2, cy - wdt * 0.6,
                     cx + length / 2, cy - wdt * 0.6 + length * 0.08],
             width=wdt)
        Color(0.34, 0.23, 0.13, 1)                        # bois
        Line(points=[cx - length / 2, cy, cx + length / 2, cy + length * 0.08],
             width=wdt)
        Color(0.30, 0.20, 0.11, 1)                        # ramures
        Line(points=[cx + length * 0.1, cy + length * 0.05,
                     cx + length * 0.28, cy + length * 0.20],
             width=max(1.0, wdt * 0.6))
        Line(points=[cx - length * 0.2, cy + length * 0.01,
                     cx - length * 0.34, cy + length * 0.16],
             width=max(1.0, wdt * 0.6))
        Color(0.48, 0.35, 0.21, 0.7)                      # reflet sur le dessus
        Line(points=[cx - length * 0.42, cy + wdt * 0.3,
                     cx + length * 0.42, cy + wdt * 0.3 + length * 0.08],
             width=max(1.0, wdt * 0.35))

    def _baton(self, name, cx, centre, length, pente=None, epais=1.0):
        """Un baton en IMAGE, couche au sol, centre sur (cx, centre). Faux si
        aucune image.

        `pente` impose son inclinaison (degres) au lieu de la tirer : une
        branche posee sur l'etabli repose a plat, elle ne tombe pas au hasard.
        `epais` l'epaissit (les branches de l'etabli sont des pieces choisies,
        plus fortes que le bois mort du sol).

        DIMENSIONNE PAR SA LONGUEUR, pas par sa hauteur : les images livrees
        sont des batons fins, dix a vingt fois plus longs que larges. Par la
        hauteur (ce que fait _sprite), un baton fin serait devenu plusieurs
        fois plus long que prevu.

        POSE PAR SON CENTRE, parce que chaque image est un cadre de 512 x 128
        (puissance de 2, pour les mipmaps) ou le baton est centre, plus ou
        moins epais selon la variante : c'est son axe qui est connu, pas son
        bord.

        Chaque baton recoit, tires de sa POSITION (donc stables d'un redessin
        a l'autre) : une legere pente et un sens (l'image ou son miroir) --
        dix images suffisent alors a ne jamais voir deux fois le meme baton.
        Son ombre est sa propre silhouette, en noir, glissee sous lui."""
        pick = self._pick(cx, centre)
        tex = foliage.sprite(name, pick)
        if tex is None:
            return False
        tw, th = tex.size
        w = float(length)
        h = (w * float(th) / float(tw) if tw else w * 0.1) * epais
        jit = random.Random(pick)
        angle = jit.uniform(-self.BATON_PENTE, self.BATON_PENTE)
        if pente is not None:
            angle = pente
        miroir = jit.random() < 0.5
        tc = tuple(tex.tex_coords)
        if miroir:
            tc = (tc[2], tc[3], tc[0], tc[1], tc[6], tc[7], tc[4], tc[5])
        bas = centre - h / 2.0
        PushMatrix()
        Rotate(angle=angle, origin=(cx, centre))
        sil = foliage.silhouette(name, pick)
        if sil is not None:
            # La silhouette n'a pas de coordonnees retournees par defaut
            # (voir foliage.silhouette) : on les donne toujours. Son decalage
            # suit la LONGUEUR du baton, pas la hauteur du cadre, dont une
            # bonne part est du vide.
            stc = ((1, 1, 0, 1, 0, 0, 1, 0) if miroir
                   else (0, 1, 1, 1, 1, 0, 0, 0))
            Color(0, 0, 0, self.BATON_OMBRE)
            Rectangle(pos=(cx - w / 2.0, bas - max(1.0, w * 0.025)),
                      size=(w, h), texture=sil, tex_coords=stc)
        Color(1, 1, 1, 1)
        Rectangle(pos=(cx - w / 2.0, bas), size=(w, h), texture=tex,
                  tex_coords=tc)
        PopMatrix()
        return True

    def _plant(self, cx, base, size, sprite=None):
        # L'ombre suit la LARGEUR de ce qui est dessine : le trefle livre est
        # une touffe deux fois plus large que haute, l'ancienne plante en
        # formes geometriques tenait dans un carre.
        tex = foliage.sprite(sprite, self._pick(cx, base)) if sprite else None
        large = (size * 1.05 * float(tex.width) / float(tex.height)
                 if tex is not None and tex.height else size * 1.1)
        self._shadow(cx, base, large * 0.85, opacity=0.7)
        if self._sprite(sprite, cx, base, size * 1.05, teinte=TEINTE_PLANTE):
            return
        Color(0.18, 0.36, 0.16, 1)                       # tige
        Rectangle(pos=(cx - size * 0.06, base), size=(size * 0.12, size * 0.8))
        Color(0.24, 0.46, 0.20, 1)                       # feuilles
        Ellipse(pos=(cx - size * 0.55, base + size * 0.20),
                size=(size * 0.60, size * 0.30))
        Ellipse(pos=(cx - size * 0.05, base + size * 0.30),
                size=(size * 0.60, size * 0.30))
        Ellipse(pos=(cx - size * 0.22, base + size * 0.55),
                size=(size * 0.44, size * 0.50))

    def _hay(self, cx, base, height, scale):
        """Touffe de foin (graminees dorees)."""
        if self._sprite("hay", cx, base, height):
            return
        bw = max(1.5, self.width * 0.004 * scale)
        Color(0.74, 0.64, 0.30, 1)
        for off, sc in ((-1.5, 0.8), (-0.7, 1.0), (0.0, 0.9),
                        (0.7, 1.0), (1.5, 0.75)):
            bx = cx + off * bw
            Triangle(points=[bx - bw, base, bx + bw, base,
                             bx + off * bw * 0.15, base + height * sc])

    def _wheat(self, cx, base, height, scale):
        """Epi de cereale : tige + grains."""
        if self._sprite("wheat", cx, base, height):
            return
        Color(0.80, 0.70, 0.34, 1)
        Line(points=[cx, base, cx, base + height], width=max(1.0, 2.0 * scale))
        Color(0.87, 0.74, 0.34, 1)
        rr = max(2.0, 3.2 * scale)
        for i in range(4):
            yy = base + height * (0.56 + 0.11 * i)
            Ellipse(pos=(cx - rr, yy), size=(rr * 2, rr * 1.5))

    # UN SOMMET TOUS LES N PIXELS pour le bord du sol. C'est ce qui fixe la
    # FINESSE de la dentelure : on ne peut pas decrire un cran plus etroit que
    # deux segments. A quarante segments pour tout l'ecran -- l'ancienne
    # valeur, fixe -- le plus fin relief possible faisait cinquante pixels de
    # large sur un telephone : une ondulation, pas un bord.
    #
    # QUATORZE ET NON SIX. A six, la crete de montagne etait une scie : un
    # cran tous les douze pixels sur toute la largeur de l'ecran. Ce n'est pas
    # ainsi qu'un terrain se decoupe -- il a quelques accidents, pas cent.
    SEGMENT_FRANGE = 14.0

    # DE COMBIEN LE BORD S'EFFILOCHE, en part de la TUILE de la texture vue a
    # la crete. C'est ce qui l'accorde a la matiere : une frange se mesure a
    # la taille des brins, pas a la taille de l'ecran. Un sol a grosse maille
    # s'effiloche donc en gros morceaux, un sol fin en petits.
    FRANGE_TUILE = 0.06
    # ... et jamais plus que cela en part de la hauteur de l'ecran : sur un
    # telephone etroit, la tuile peut faire la moitie de l'image.
    FRANGE_MAX = 0.007

    # PART DU GRAIN FIN dans la frange (le reste est le grain large). Plus il
    # monte, plus le bord est herisse ; plus il baisse, plus il ondule.
    POIDS_FIN = 0.28

    def _frange(self, tex_name, tile_px, depth, segs):
        """Le decalage a ajouter au bord du sol, sommet par sommet.

        DEUX GRAINS SUPERPOSES, parce qu'un seul ne suffit pas : un bruit fin
        seul donne un peigne regulier, un bruit large seul une simple
        ondulation de plus. Ensemble ils font une frange -- des touffes
        irregulieres, chacune dentelee.

        LE BORD SE REFERME AUX DEUX BOUTS (la frange s'eteint sur les
        cinquante premiers et derniers pixels). Le sol est un ruban qui sort
        de l'ecran des deux cotes ; un cran au ras du bord se lirait comme un
        defaut d'affichage.

        Le hasard tient a la GRAINE de la case et au nom de la texture : la
        meme case garde sa frange d'un redessin a l'autre, et les deux bandes
        d'un meme sol (la proche et la lointaine) ne se decoupent pas
        pareil."""
        if segs < 2:
            return [0.0] * (segs + 1)
        # La tuile telle qu'on la voit A LA CRETE : c'est la que se trouve le
        # bord, et la texture y est deja resserree par la perspective.
        tuile = tile_px / max(1.0, float(depth))
        ampl = min(tuile * self.FRANGE_TUILE, self.height * self.FRANGE_MAX)
        rng = random.Random("%s:%s:frange" % (self._seed, tex_name))
        gros = [rng.uniform(-1.0, 1.0) for _ in range(segs // 12 + 2)]
        out = []
        for i in range(segs + 1):
            # Grain large, interpole : les touffes.
            u = i / segs * (len(gros) - 1)
            j = min(len(gros) - 2, int(u))
            f = u - j
            large = gros[j] * (1 - f) + gros[j + 1] * f
            # Grain fin, sommet par sommet : la dentelure.
            fin = rng.uniform(-1.0, 1.0)
            v = (1.0 - self.POIDS_FIN) * large + self.POIDS_FIN * fin
            # Extinction aux deux bouts.
            bord = min(1.0, (min(i, segs - i) / segs) * self.width / 50.0)
            out.append(v * ampl * bord)
        return out

    def _fill_curve(self, top_fn, tex_name, segs=None, tile_px=None,
                    depth=GROUND_DEPTH, rows=GROUND_ROWS, estompe=False,
                    frange=True, eau=False):
        """Remplit du bas du widget jusqu'a la courbe top_fn(fx) (terrain).

        Habille avec la texture `tex_name` si elle existe (sinon couleur de
        repli), EN PERSPECTIVE : la tuile retrecit a mesure que le terrain
        s'eloigne (voir GROUND_DEPTH).

        `depth=1.0` redonne une repetition reguliere, sans profondeur.

        LE BORD DU HAUT EST DECHIQUETE, et c'est le point de ce dessin. La
        courbe est une somme de sinus : parfaitement lisse, elle tranchait la
        texture au rasoir et le sol se lisait comme une decoupe de papier
        posee sur le fond. Un sol ne finit jamais ainsi -- il s'effiloche en
        brins, en feuilles, en cailloux. Voir _frange.

        `frange=False` rend le bord LISSE. Le lac s'en sert : sa rive d'en
        face est une ligne d'eau, et l'eau ne s'effiloche pas -- elle a un
        niveau.

        `estompe` ajoute en plus un fondu de matiere au-dessus du bord. IL NE
        VAUT QUE LA OU LE SOL RENCONTRE UN AUTRE SOL -- la bande proche
        par-dessus la bande lointaine. Contre le CIEL il est nuisible, et cela
        s'est vu tout de suite : la crete de la montagne trainait une bavure
        grise en diagonale dans le ciel, et la rive du lac un halo bleu
        par-dessus la berge d'en face. Contre le ciel, la dentelure seule fait
        le travail -- c'est une silhouette qu'on veut, pas un degrade.

        `eau=True` pose en plus, sur la meme surface, le reflet du ciel et
        l'ecume qui derive (voir _surface_eau)."""
        if tile_px is None:
            tile_px = textures.tile_for(tex_name)
        if segs is None:
            # Assez de sommets pour que la frange ait du grain : un segment
            # tous les quelques pixels. A quarante segments pour tout l'ecran
            # -- l'ancienne valeur -- le plus fin relief qu'on puisse decrire
            # fait vingt-cinq pixels de large, soit une ondulation, pas un
            # bord.
            segs = max(40, int(self.width / self.SEGMENT_FRANGE))
        x0, y0, w = self.x, self.y, self.width
        cx = x0 + w / 2.0                      # point de fuite : le milieu
        tex = paint(tex_name)
        self._bind_pbr(tex_name)

        depth = max(1.0, float(depth))
        rows = max(1, int(rows)) if depth > 1.0 else 1
        # a = part du chemin vers l'horizon reellement parcourue. k = 1/(1-a*t)
        # va donc de 1 (tout pres) a `depth` (au fond) quand t va de 0 a 1.
        a = 1.0 - 1.0 / depth

        # Bandes reparties uniformement en DISTANCE (donc resserrees a
        # l'ecran pres de la crete) : c'est la que la perspective se courbe
        # le plus, et donc la qu'il faut des sommets.
        ks = [1.0 + (depth - 1.0) * j / rows for j in range(rows + 1)]
        if a:
            ts = [(1.0 - 1.0 / k) / a for k in ks]
        else:
            # SANS PERSPECTIVE (depth = 1), les rangees se repartissent
            # simplement sur la hauteur. La formule ci-dessus divise par a,
            # qui vaut alors zero ; elle rendait 0 pour toutes les rangees, et
            # le maillage etait PLAT -- hauteur nulle, donc invisible.
            #
            # Le cas n'avait jamais servi : la documentation annoncait
            # "depth=1.0 redonne une repetition reguliere", et personne
            # n'avait essaye. Le jour ou la pente de montagne est passee par
            # ici, elle a disparu de l'ecran.
            ts = [j / rows for j in range(rows + 1)]

        frange = (self._frange(tex_name, tile_px, depth, segs) if frange
                  else [0.0] * (segs + 1))
        # Une tuile qui n'est pas carree (l'eau, en 2:1) a un pas vertical a
        # elle : sinon ses cailloux seraient etires en hauteur.
        tile_v = tile_px * textures.rapport(tex)
        verts = []
        rampe = []           # la meme surface, lue dans la rampe du reflet
        bord = []
        for i in range(segs + 1):
            fx = i / segs
            x = x0 + fx * w
            top = top_fn(fx) + frange[i]
            bord.append(top)
            for k, t in zip(ks, ts):
                # A la distance k, l'ecran couvre k fois plus de terrain :
                # u s'ecarte du point de fuite, v s'enfonce. La tuile
                # retrecit donc des deux cotes a la fois (pas d'etirement).
                #
                # v SE DEDUIT DE LA HAUTEUR A L'ECRAN, pas de (k-1) : les deux
                # donnent le meme resultat quand il y a de la perspective
                # (span*(k-1) vaut exactement (y-y0)*k), mais seule celle-ci
                # garde un sens quand il n'y en a pas.
                yy = y0 + t * (top - y0)
                verts += [x, yy, (x - cx) * k / tile_px,
                          -(yy - y0) * k / tile_v]
                # LA RAMPE LIT LA DISTANCE, pas la hauteur a l'ecran : c'est
                # l'epaisseur d'eau traversee qui l'opacifie (voir
                # _rampe_eau). Sans perspective il n'y a pas de distance a
                # lire, et t reste la seule mesure disponible.
                rampe += [x, yy, 0.5,
                          (k - 1.0) / (depth - 1.0) if depth > 1.0 else t]

        stride = rows + 1
        idx = []
        for i in range(segs):
            for j in range(rows):
                p = i * stride + j
                q = p + stride
                idx += [p, q, q + 1, p, q + 1, p + 1]
        Mesh(vertices=verts, indices=idx, mode="triangles", texture=tex)
        if eau and tex is not None:
            self._reset_pbr()
            self._surface_eau(tex_name, verts, idx, rampe)
        if estompe:
            self._estompe(top_fn, frange, tex, tex_name, tile_px, depth, segs)
        self._reset_pbr()
        return _BordDuSol(x0, w, bord)

    # LE PIED D'UNE TOUFFE POSEE PRES D'UN BORD DE SOL, sous ce bord, en part
    # de sa hauteur dessinee. Posee pile sur le bord, une touffe tient en
    # equilibre sur une ligne ; enfoncee, elle se lit comme une touffe du
    # versant qui depasse de la crete -- ce qu'elle est.
    ENFONCE_BORD = 0.15

    # Demi-largeur du PIED d'une touffe, en part de la largeur de son image.
    # Mesuree sur l'image livree : a 3 % de sa hauteur la touffe n'occupe que
    # +/- 0,16 de sa largeur, mais des 6 % elle en occupe +/- 0,32. C'est
    # toute cette largeur qui doit reposer sur le sol, sinon le ciel passe
    # sous l'un de ses cotes.
    PIED_TOUFFE = 0.35

    def _plante_sur(self, bord, gx, gb, gh):
        """La base d'une touffe, ramenee SOUS le bord reel du sol.

        `bord` est ce que rend _fill_curve : le bord tel qu'il est DESSINE,
        dentelure comprise. La touffe est descendue sous son point le plus
        bas sur toute la largeur de son pied -- elle ne remonte jamais."""
        haut = gh * 1.15                         # hauteur dessinee (_grass_tuft)
        tex = foliage.sprite(NOM_HERBE)
        rapport = (float(tex.width) / float(tex.height)
                   if tex is not None and tex.height else 1.0)
        demi = self.PIED_TOUFFE * haut * rapport
        plafond = bord.plus_bas(gx - demi, gx + demi) - self.ENFONCE_BORD * haut
        return min(gb, plafond)

    # LA MECHE QUI S'EFFACE au-dessus du bord : sur quelle hauteur (en part de
    # la frange) et en combien de paliers.
    ESTOMPE_HAUTEUR = 2.2
    ESTOMPE_PALIERS = 4

    def _estompe(self, top_fn, frange, tex, tex_name, tile_px, depth, segs):
        """Prolonge le sol au-dessus de son bord, en s'effacant.

        POURQUOI CELA NE SUFFISAIT PAS DE DECHIQUETER LE BORD. Un bord
        dentele reste un BORD : la matiere s'y arrete net, a un pixel pres, et
        l'oeil lit toujours une decoupe -- une decoupe aux ciseaux cranteurs
        plutot qu'aux ciseaux droits. Ce qui enleve la coupure, c'est que la
        matiere s'ECLAIRCISSE en montant, comme un sol qui se perd dans la
        distance.

        C'est aussi ce qui accorde le bord a LA TEXTURE de la scene, au sens
        propre : ce qui deborde au-dessus n'est pas une couleur choisie, c'est
        le sol lui-meme, la meme image, a la meme echelle.

        EN PALIERS, parce qu'un maillage Kivy ne sait pas donner une opacite
        par sommet. Quatre suffisent : le degrade porte sur une vingtaine de
        pixels, et l'oeil n'y distingue pas les marches.

        Chaque palier a sa PROPRE dentelure, sinon les quatre se
        superposeraient exactement et le degrade redeviendrait un bord franc,
        juste plus epais."""
        n = self.ESTOMPE_PALIERS
        ampl = max(abs(v) for v in frange) if frange else 0.0
        if ampl <= 0.5 or n <= 0:
            return
        haut = ampl * self.ESTOMPE_HAUTEUR
        x0, y0, w = self.x, self.y, self.width
        cx = x0 + w / 2.0
        k = max(1.0, float(depth))
        rng = random.Random("%s:%s:estompe" % (self._seed, tex_name))
        bas = list(frange)
        for etage in range(n):
            # Opacite decroissante : 0.62, 0.42, 0.26, 0.13 pour quatre.
            alpha = 0.62 * (1.0 - etage / float(n)) ** 1.6
            dessus = [frange[i] + haut * (etage + 1) / n
                      + rng.uniform(-0.45, 0.45) * ampl
                      for i in range(segs + 1)]
            verts, idx = [], []
            for i in range(segs + 1):
                fx = i / segs
                x = x0 + fx * w
                for yy in (top_fn(fx) + bas[i], top_fn(fx) + dessus[i]):
                    verts += [x, yy, (x - cx) * k / tile_px, -(yy - y0) / tile_px]
                if i:
                    p = (i - 1) * 2
                    idx += [p, p + 1, p + 2, p + 1, p + 3, p + 2]
            if tex is not None:
                Color(1, 1, 1, alpha)
            else:
                r, g, b = textures.fallback(tex_name)[:3]
                Color(r, g, b, alpha)
            Mesh(vertices=verts, indices=idx, mode="triangles", texture=tex)
            bas = dessus

    def _plaine(self, rng):
        w, h, x0, y0 = self.width, self.height, self.x, self.y
        hor = 0.55
        edge = hor - 0.06

        def green_at(_t):
            # La meme couleur a toute profondeur : c'est la brume qui fait la
            # distance (voir HERBE_PLAINE). Le parametre reste, pour que les
            # appels qui passent la profondeur n'aient pas a changer.
            return HERBE_PLAINE + (1,)

        # Terrain ONDULE : deux courbes (sommes de sinus) pour un relief
        # naturel. horizon_curve = crete lointaine (l'horizon) ; field_curve =
        # surface du champ proche, ou reposent tous les elements.
        p1 = rng.uniform(0, 6.28)
        p2 = rng.uniform(0, 6.28)

        def horizon_curve(fx):
            return y0 + (edge + 0.035 * math.sin(fx * 6.28 * 1.4 + p1)
                         + 0.018 * math.sin(fx * 6.28 * 3.1 + p2)) * h

        def field_curve(fx):
            return y0 + ((edge - 0.13)
                         + 0.030 * math.sin(fx * 6.28 * 1.1 + p1 + 1.0)
                         + 0.014 * math.sin(fx * 6.28 * 2.5 + p2)) * h

        def place(maxt=1.0, fx=None, floor=0.0):
            if fx is None:
                fx = rng.uniform(0, 1)
            fx = min(0.999, max(0.001, fx))
            surf = (field_curve(fx) - y0) / h         # sommet du sol a cet x
            lo = min(floor, surf)              # plancher (jointures des mains)
            hi = surf * maxt
            if hi < lo:
                hi = lo
            fy = lo + (hi - lo) * rng.random()
            t = (fy / surf) if surf else 0.0
            return (x0 + fx * w, y0 + fy * h, 1.0 - 0.70 * t, t)

        # Distribution en AMAS : chaque type pousse autour de quelques foyers
        # (touffes d'herbe, tas de pierres, bosquets...) au lieu d'un saupoudrage
        # uniforme -> bien plus naturel.
        def clusters(count, spread):
            centers = [rng.uniform(0.05, 0.95) for _ in range(max(1, count))]
            return lambda: rng.choice(centers) + rng.gauss(0, spread)

        grass_pick = clusters(rng.randint(4, 6), 0.13)
        stone_pick = clusters(rng.randint(2, 3), 0.05)
        plant_pick = clusters(rng.randint(3, 4), 0.08)
        mush_pick = clusters(rng.randint(2, 3), 0.05)
        berry_pick = clusters(rng.randint(2, 3), 0.05)
        hay_pick = clusters(rng.randint(2, 3), 0.10)
        wheat_pick = clusters(rng.randint(2, 3), 0.10)


        # Ce qu'il y a AUTOUR, tout au fond, avant le moindre brin d'herbe.
        self._horizon(lambda fx: horizon_curve(fx) - 0.012 * h)

        # Collines : crete lointaine puis champ proche, ondules. La bande
        # lointaine est de la MEME herbe, a pleine couleur ("grass_loin") :
        # c'est la brume, posee plus bas, qui la recule -- elle ne se detache
        # plus du champ en plus sombre.
        crete = self._fill_curve(horizon_curve, "grass_loin")
        self._fill_curve(field_curve, "grass", estompe=True)

        # Petites fabriques de "fonctions de dessin" (pour differer le rendu).
        def f_grass(gx, gb, gh, col, sc, flower, fr):
            if not flower:
                return self._touffe(gx, gb, gh, col, sc)

            def fn():
                self._grass_tuft(gx, gb, gh, col, scale=sc)
                # La fleur passe PAR-DESSUS sa touffe : celle-ci doit donc
                # etre dessinee avant, et non rester dans le lot en attente.
                self._vide_lot()
                fcol, fsprite = flower
                self._flower(gx, gb + gh, fr * 2.4, fcol, sprite=fsprite)
            fn.herbe = gh
            return fn

        # On collecte chaque element avec sa PROFONDEUR (= y de sa base), puis
        # on dessine du plus LOIN (base haute) au plus PROCHE (base basse) :
        # les elements proches recouvrent ceux du fond, de facon realiste.
        items = []   # (y_base, fonction)

        for _ in range(rng.randint(9, 13)):            # pierres (en tas) [Pierre]
            sx, sy, sc, t = place(1.0, fx=stone_pick(), floor=_HARVEST_FLOOR)
            r = rng.uniform(0.018, 0.045) * h * sc
            if not self._take_or_skip("Pierre") and not self._is_blocked(sx, sy):
                items.append((sy - self.DEBORD_CAILLOU * r,
                              lambda sx=sx, sy=sy, r=r, t=t:
                              self._stone(sx, sy, r, sprite=self._zs("stone"),
                                          depth=t)))
        for _ in range(rng.randint(6, 9)):             # branches [Small_Stick]
            bx, by, sc, t = place(1.0, floor=_HARVEST_FLOOR)
            ln = rng.uniform(0.06, 0.12) * w * sc
            # Un baton est trie sur son BOIS, ombre comprise. Il l'etait
            # auparavant sur un biais fixe de 12 % de l'ecran, cense le faire
            # passer par-dessus l'herbe de sa profondeur ; mais c'etait sept
            # fois sa propre emprise, et cela le faisait aussi passer devant
            # des buissons et des arbres nettement plus proches que lui.
            if not self._take_or_skip("Small_Stick") and not self._is_blocked(bx, by):
                items.append((by - self.DEBORD_BRANCHE * ln,
                              lambda bx=bx, by=by, ln=ln:
                              self._branch(bx, by, ln,
                                           sprite=self._zs("branch"))))
        # Buissons (taille humaine) : GROS elements positionnes sur la GRILLE
        # 5x5 (cases interdites a l'installation d'un objet).
        for kind, rang, depth, bx, by, jit in self._iter_nature_big():
            if kind == "nugget":
                items.extend(self._pepite_de_grille(rang, depth, bx, by, jit))
                continue
            g = jit.uniform(0.0, 0.10)
            r = (0.17 - 0.09 * depth) * jit.uniform(0.85, 1.15) * h
            col = (0.12 + g, 0.30 + g, 0.15, 1)
            items.append((by - self.DEBORD_BUISSON * r,
                          lambda bx=bx, by=by, r=r, col=col:
                          self._bush(bx, by, r, col,
                                     sprite=self._zs("bush"))))
        for _ in range(525):                           # gazon x5 (etait 105) [Herbe]
            fx = grass_pick() if rng.random() < 0.72 else None  # amas + un peu partout
            gx, gb, sc, t = place(fx=fx, floor=_HARVEST_FLOOR)
            gh = rng.uniform(0.05, 0.16) * h * sc
            # UNE FLEUR POUR CINQUANTE TOUFFES, et non pour dix : les touffes
            # ont ete multipliees par cinq, pas les fleurs. A une sur dix, le
            # champ s'etait couvert de fleurs du jour au lendemain -- une
            # quarantaine au lieu d'une dizaine, chacune dessinee petale par
            # petale (une soixantaine d'instructions la fleur).
            fcol = rng.choice(_FLOWERS) if rng.random() < 0.02 else None
            fr = max(1.5, w * 0.004 * sc)
            if (not self._take_or_skip("Herbe")
                    and not self._is_blocked(gx, gb, gb + gh)):
                items.append((gb, f_grass(gx, gb, gh, green_at(t), sc, fcol, fr)))
        # HERBE DE LA BANDE LOINTAINE -- entre le haut du champ proche et la
        # crete. C'est la bande ou l'on voit le sol "grass_far", et elle etait
        # a peu pres vide : `place` ne depasse jamais field_curve, et la seule
        # passe qui allait plus loin se serrait sur la crete.
        #
        # ET SURTOUT, ELLE EST MISE A L'ECHELLE. Cette passe posait
        # gh = uniform(0,05 ; 0,11) x hauteur d'ecran, SANS facteur de
        # profondeur, alors que toutes les passes du premier plan en ont un.
        # Mesure : les touffes de la crete faisaient 112 a 239 px quand celles
        # de devant en font 110 a 218. L'herbe RAGRANDISSAIT avec la distance.
        # (Cela ne se voyait pas tant qu'elles etaient cinq triangles fins :
        # la passe leur donnait scale=0,5, qui amincit les brins. Une image,
        # elle, garde ses proportions -- le defaut de hauteur est devenu
        # visible d'un coup.)
        def echelle_loin(gb):
            """L'echelle apparente a cette hauteur, par la MEME perspective
            que le sol.

            On la raccorde a celle de `place` au sommet du champ proche
            (0,30), puis on la laisse decroitre comme le fait la tuile du sol
            -- soit 1/k avec k = 1/(1 - t(1 - 1/GROUND_DEPTH)). A la crete
            cela donne 0,18 : une touffe y est donc trois fois plus petite
            qu'au premier plan, et deux fois plus petite qu'au bout du champ."""
            t = min(1.0, max(0.0, (gb - y0) / max(1.0, hor * h)))
            k = 1.0 / (1.0 - t * (1.0 - 1.0 / GROUND_DEPTH))
            t_champ = (edge - 0.13) / hor
            k_champ = 1.0 / (1.0 - t_champ * (1.0 - 1.0 / GROUND_DEPTH))
            return ECHELLE_HERBE_CHAMP * k_champ / k

        def pose_loin(n, recoltable):
            for i in range(n):
                fx = (i + rng.uniform(0.0, 1.0)) / n
                gx = x0 + fx * w + rng.uniform(-0.010, 0.010) * w
                bas = field_curve(fx)
                haut = horizon_curve(fx)
                gb = bas + (haut - bas) * rng.random() ** 0.7
                sc = echelle_loin(gb)
                gh = rng.uniform(0.05, 0.16) * h * sc
                # SOUS LE BORD REEL DE LA CRETE, a l'endroit ou la touffe est
                # vraiment posee. La hauteur ci-dessus est prise en fx, AVANT
                # le petit decalage de gx : la ou la crete descend, la touffe
                # se retrouvait au-dessus du vide. Et la courbe lisse ignore
                # la dentelure du bord, dont chaque creux laissait passer le
                # ciel sous une touffe. Aucun tirage en plus : le decor ne
                # bouge pas, seules les touffes de crete descendent.
                gb = self._plante_sur(crete, gx, gb, gh)
                if recoltable and self._take_or_skip("Herbe"):
                    continue
                if self._is_blocked(gx, gb, gb + gh):
                    continue
                items.append((gb, f_grass(gx, gb, gh,
                                          green_at(rng.uniform(0.85, 1.0)),
                                          sc, None, 0)))

        # Recoltables x5 (etait 125) : le nombre affecte l'aspect visuel mais
        # pas la quantite recoltable (harvest_max reste plafonne par _avail_for
        # qui tire 2 a 5).
        pose_loin(625, True)
        # Et de quoi garnir la bande, celles-ci decoratives.
        pose_loin(HERBE_LOIN_PLAINE, False)
        # GAZON DE REMPLISSAGE, et il est DECORATIF : aucun appel a
        # _take_or_skip, donc rien de plus a ramasser.
        #
        # Ce n'etait de toute facon pas la ou se decidait la recolte : le
        # nombre de ramassages possibles vaut min(_avail_for, touffes
        # dessinees), et _avail_for tire entre 2 et 5. Avec 230 touffes deja
        # dessinees pour 2 a 5 recoltes, le nombre de touffes n'a jamais ete
        # le facteur limitant -- mesure faite avant d'ecrire ceci.
        #
        # Le laisser hors du comptage a quand meme un effet, et c'est le bon :
        # ce gazon-la ne disparait pas quand on recolte. Un champ ne se
        # denude pas parce qu'on y a cueilli quelques poignees d'herbe -- il
        # s'eclaircit, et c'est ce que font les 230 autres.
        for _ in range(HERBE_DECOR_PLAINE):
            fx = grass_pick() if rng.random() < 0.55 else None
            gx, gb, sc, t = place(fx=fx, floor=_HARVEST_FLOOR)
            gh = rng.uniform(0.04, 0.13) * h * sc
            if self._is_blocked(gx, gb, gb + gh):
                continue
            items.append((gb, f_grass(gx, gb, gh, green_at(t), sc, None, 0)))
        for _ in range(rng.randint(10, 14)):           # plantes feuillues (bosquets)
            px, py, sc, t = place(fx=plant_pick())
            s = rng.uniform(0.05, 0.09) * h * sc
            if self._is_blocked(px, py, py + s * 1.05):
                continue
            items.append((py, lambda px=px, py=py, s=s:
                          self._plant(px, py, s, sprite=self._zs("plant"))))

        # --- Plantes de champ OPTIONNELLES (tirage generatif) ---
        if rng.random() < 0.75:                        # foin (en parcelles)
            for _ in range(rng.randint(6, 12)):
                fx, fb, sc, t = place(0.95, fx=hay_pick())
                ht = rng.uniform(0.10, 0.20) * h * sc
                if self._is_blocked(fx, fb, fb + ht):
                    continue
                items.append((fb, lambda fx=fx, fb=fb, ht=ht, sc=sc:
                              self._hay(fx, fb, ht, sc)))
        if rng.random() < 0.65:                        # epis / graminees (parcelles)
            for _ in range(rng.randint(8, 16)):
                ex, eb, sc, t = place(0.95, fx=wheat_pick())
                ht = rng.uniform(0.10, 0.18) * h * sc
                if self._is_blocked(ex, eb, eb + ht):
                    continue
                items.append((eb, lambda ex=ex, eb=eb, ht=ht, sc=sc:
                              self._wheat(ex, eb, ht, sc)))
        # Pas de champignons en plaine (uniquement en foret pour l'instant).
        if rng.random() < 0.5:                         # baies (buissons) [Baie]
            for _ in range(rng.randint(3, 6)):
                bx, by, sc, t = place(1.0, fx=berry_pick(), floor=_HARVEST_FLOOR)
                r = rng.uniform(0.03, 0.045) * h * sc
                if not self._take_or_skip("Baie") and not self._is_blocked(bx, by):
                    items.append((by - self.DEBORD_BAIES * r,
                                  lambda bx=bx, by=by, r=r:
                                  self._berries(bx, by, r)))

        # (Les insectes sont desormais une couche ANIMEE separee : InsectLayer.)

        # HERBE AU PIED DU JOUEUR. Tout le gazon s'arretait au plancher des
        # objets a ramasser (_HARVEST_FLOOR, la hauteur des mains) : dessous,
        # le sol restait nu, et la limite se lisait comme un trait tire en
        # travers du champ. Cette herbe-la est DECORATIVE (elle ne passe pas
        # par _take_or_skip : rien de plus a ramasser) et plus BASSE que le
        # reste -- au pied, une touffe haute boucherait la vue.
        #
        # Tiree EN DERNIER, apres tout le reste de la scene : le hasard de ce
        # qui precede ne bouge donc pas, et les pierres, les fleurs, les
        # objets a ramasser restent exactement ou ils etaient.
        for _ in range(HERBE_PIED_PLAINE):
            fx = grass_pick() if rng.random() < 0.55 else rng.uniform(0, 1)
            fx = min(0.999, max(0.001, fx))
            surf = (field_curve(fx) - y0) / h
            fy = rng.uniform(0.0, _HARVEST_FLOOR)
            t = (fy / surf) if surf else 0.0
            sc = 1.0 - 0.70 * t
            gx, gb = x0 + fx * w, y0 + fy * h
            gh = rng.uniform(0.03, 0.08) * h * sc
            if self._is_blocked(gx, gb, gb + gh):
                continue
            items.append((gb, f_grass(gx, gb, gh, green_at(t), sc, None, 0)))

        # LA BRUME DU LOINTAIN, posee DANS le tri et non par-dessus la scene :
        # tout ce qui est plus loin que le bord du champ proche -- la bande
        # lointaine, son herbe, ce qu'on y a installe -- est dessine AVANT
        # elle, donc voile ; le champ proche, dessine apres, reste net. Un
        # buisson du premier plan qui monte jusque dans la bande lointaine ne
        # prend donc pas le voile du fond. Une seule forme pour toute la scene.
        bas_champ = min(field_curve(i / 64.0) for i in range(65))
        items.append((bas_champ - 0.5,
                      lambda: self._brume(field_curve, horizon_curve)))

        # Rendu trie : plus loin (base haute) d'abord, plus proche par-dessus.
        items += self._installed_items()     # feu de camp... a leur profondeur
        items += self._edge_items()          # la case d'a cote, qui deborde
        self._dessine(items)

    def _brume(self, bas_fn, crete_fn):
        """Le voile d'air entre l'oeil et le lointain (voir BRUME_CRETE).

        Une bande qui suit le terrain : nulle au bord du champ proche, elle
        s'epaissit jusqu'a la crete puis s'efface juste au-dessus. Sa couleur
        est celle du ciel a l'horizon (voir _applique_brume) : a la crete, la
        colline se fond a moitie dans le ciel, et la ligne d'horizon cesse
        d'etre une decoupe.

        UNE TEXTURE PORTE LE DEGRADE, parce qu'un maillage Kivy ne sait pas
        donner une opacite par sommet : le voile est une couleur unie dont
        l'alpha est lu, rangee par rangee, dans une rampe (voir _rampe_brume).

        DEUX BANDES, DEUX COULEURS. Sur le TERRAIN, la brume est blanchie
        (BRUME_BLANCHE). AU-DESSUS DE LA CRETE, elle recouvre surtout du ciel
        -- elle n'est la que pour voiler le sommet des touffes de crete -- et
        prend donc la couleur exacte du ciel : blanchie, elle y dessinait un
        halo pale qui suivait le contour des collines."""
        rampe = _rampe_brume()
        if rampe is None:
            return
        x0, w, h = self.x, self.width, self.height
        segs = max(24, int(w / 36.0))
        dessus = BRUME_AU_DESSUS * h
        terrain, ciel, idx = [], [], []
        for i in range(segs + 1):
            fx = i / float(segs)
            x = x0 + fx * w
            bas = bas_fn(fx)
            crete = max(bas + 1.0, crete_fn(fx))
            terrain += [x, bas, 0.5, 0.0, x, crete, 0.5, 0.5]
            ciel += [x, crete, 0.5, 0.5, x, crete + dessus, 0.5, 1.0]
            if i:
                p, q = (i - 1) * 2, i * 2
                idx += [p, q, q + 1, p, q + 1, p + 1]
        self._brume_couleur = []
        for sommets, blanche in ((terrain, BRUME_BLANCHE), (ciel, 0.0)):
            self._brume_couleur.append((Color(1, 1, 1, 1), blanche))
            Mesh(vertices=sommets, indices=idx, mode="triangles",
                 texture=rampe)
        self._applique_brume()

    def _montagne(self, rng):
        w, h, x0, y0 = self.width, self.height, self.x, self.y

        def surf(fx):                      # hauteur de la pente a la position fx
            return y0 + (0.60 + 0.36 * fx) * h

        # Paysages voisins : poses au POINT LE PLUS BAS de la pente, pas sur
        # la pente elle-meme. Une ligne d'arbres qui grimperait le long du
        # versant se lirait comme une foret accrochee a la montagne ; posee a
        # plat, elle reste ce qu'elle est -- le fond de vallee, que la pente
        # (dessinee juste apres) vient masquer a mesure qu'elle monte.
        self._horizon(lambda fx: surf(0.0))

        # Pente principale (remplit le cadre, monte vers la droite). Elle
        # passe par _fill_curve et non par un quadrilatere : sa crete est le
        # bord du SOL contre le ciel, et elle etait dessinee ici comme un
        # trait parfaitement droit -- une regle posee sur le paysage. Elle y
        # gagne la meme frange que les autres sols.
        #
        # depth=1.0 : la pente monte, elle ne s'enfonce pas vers un horizon.
        # Sa tuile ne doit donc pas se resserrer.
        self._fill_curve(lambda fx: surf(fx), "rock", depth=1.0)
        # Bas plus sombre (profondeur).
        self._tquad("rock_dark",
                    [x0, y0, x0 + w, y0, x0 + w, y0 + 0.22 * h, x0, y0 + 0.14 * h])
        # Rochers disperses sur la pente (vers le haut). [recoltable: Pierre]
        for _ in range(42):
            fx = rng.uniform(0, 1)
            sx = x0 + fx * w
            top = (surf(fx) - y0) / h
            lo = min(_HARVEST_FLOOR, top - 0.05)   # plancher (jointures)
            hi = max(lo + 0.02, top - 0.05)
            sy = y0 + rng.uniform(lo, hi) * h
            rr = rng.uniform(0.015, 0.05) * h
            s = rng.uniform(-0.06, 0.06)
            if not self._take_or_skip("Pierre") and not self._is_blocked(sx, sy):
                # Une petite pierre comme les autres (voir _caillou) : la
                # pente monte vers le fond, sa hauteur dit donc sa distance.
                propre = self._zs("stone")
                if (not (propre and foliage.variants(propre))
                        and self._caillou(sx, sy, rr,
                                          min(1.0, (sy - y0) / h))):
                    continue
                if not self._sprite(propre, sx, sy, rr * 1.5):
                    Color(0.45 + s, 0.44 + s, 0.49 + s, 1)
                    Ellipse(pos=(sx - rr, sy), size=(rr * 2.2, rr * 1.5))
        # Plaques de neige en haut de la pente.
        for _ in range(8):
            fx = rng.uniform(0.4, 1.0)
            sx = x0 + fx * w
            sy = surf(fx) - rng.uniform(0.02, 0.10) * h
            rr = rng.uniform(0.02, 0.05) * h
            if self._is_blocked(sx, sy, sy + rr * 1.2):
                continue
            if not self._sprite("snow_patch", sx, sy, rr * 1.2):
                Color(0.92, 0.95, 1.0, 1)
                Ellipse(pos=(sx - rr, sy), size=(rr * 2.4, rr * 1.2))
        # GROS rochers : elements FIXES positionnes sur la GRILLE 5x5 (cases
        # interdites a l'installation d'un objet). Non recoltables : la Pierre
        # se recolte sur les petits rochers de la pente. Ils sont tries AVEC
        # les objets installes : un feu de camp pose derriere un rocher passe
        # donc derriere lui.
        items = self._installed_items() + self._edge_items()
        # Touffes sur la pente basse : x5 (etait 8), pour qu'elles couvrent
        # bien le sol de montagne au lieu d'y flotter.
        for _ in range(40):
            sx = x0 + rng.uniform(0, 1) * w
            sy = y0 + rng.uniform(0.03, 0.18) * h
            gh = rng.uniform(0.03, 0.06) * h
            if self._is_blocked(sx, sy, sy + gh):
                continue
            items.append((sy, self._touffe(sx, sy, gh, (0.22, 0.34, 0.16, 1))))
        for kind, rang, depth, rx, ry, jit in self._iter_nature_big():
            if kind == "nugget":
                items.extend(self._pepite_de_grille(rang, depth, rx, ry, jit))
                continue
            rr = (0.085 - 0.045 * depth) * jit.uniform(0.85, 1.15) * h
            items.append((ry, lambda rx=rx, ry=ry, rr=rr:
                          self._big_rock(rx, ry, rr)))
        self._dessine(items)

    def _big_rock(self, rx, ry, rr):
        self._shadow(rx, ry + rr * 0.15, rr * 2.4)
        if self._sprite("boulder", rx, ry, rr * 1.8):
            return
        Color(0.38, 0.37, 0.43, 1)
        Ellipse(pos=(rx - rr, ry), size=(rr * 2.4, rr * 1.8))

    # -- l'eau du lac (voir ECUME_COUCHES) -------------------------------- #
    def _surface_eau(self, tex_name, verts, idx, rampe=None):
        """Le reflet du ciel (si `rampe` est donnee) puis l'ecume qui derive,
        poses sur la surface d'eau que decrivent `verts` (x, y, u, v) -- celle
        qu'on vient de dessiner, dont ils reprennent la geometrie."""
        if rampe is not None:
            tex_r = _rampe_eau()
            if tex_r is not None:
                # L'opacite est TOUTE ENTIERE dans la rampe (voir
                # _rampe_eau), qui monte jusqu'a OPACITE_EAU_LOIN : la Color
                # reste a 1 et ne sert qu'a porter la couleur du ciel. Un
                # second facteur ici multiplierait deux fois la meme chose.
                couleur = Color(1, 1, 1, 1)
                Mesh(vertices=rampe, indices=idx, mode="triangles",
                     texture=tex_r)
                # Sa couleur est celle du ciel a l'horizon, tenue a jour avec
                # la brume de la plaine (voir _applique_brume) : elle suit
                # l'heure et la meteo sans rien redessiner.
                if self._brume_couleur is None:
                    self._brume_couleur = []
                self._brume_couleur.append((couleur, 0.0))
                self._applique_brume()
        ecume = textures.ecume_texture(tex_name)
        if ecume is None:
            return
        for echelle, vitesse, opacite, retourne in ECUME_COUCHES:
            sens = -1.0 if retourne else 1.0
            vs = list(verts)
            for i in range(0, len(vs), 4):
                vs[i + 2] *= echelle
                vs[i + 3] *= echelle * sens
            Color(1, 1, 1, opacite)
            m = Mesh(vertices=vs, indices=idx, mode="triangles",
                     texture=ecume)
            self._eau.append({"mesh": m, "repos": tuple(vs),
                              "vitesse": vitesse})
        # Tout de suite a sa place du moment : une scene redessinee (une
        # recolte, un objet pose) ne doit pas faire sauter l'ecume en arriere.
        self._place_ecume()

    def _rive_animee(self, x0, y0, w, h):
        """La rive proche du lac, ou l'eau vient laper le sable (voir
        rive.py). Rend False si elle ne peut pas etre posee -- pas de shader,
        ou pas d'images : la scene garde alors son aplat de sable."""
        if not self._pbr:
            return False
        fond = textures.base_texture(rive.NOM)
        reflets = textures.ecume_texture(rive.NOM)
        if fond is None or reflets is None:
            return False
        self._reset_pbr()
        ctx = rive.bande(x0, y0, w, rive.HAUTEUR * h, fond, reflets)
        # La bande a lie ses reflets sur l'unite 1, que le shader du decor lit
        # comme carte de RELIEF : on lui rend ses cartes neutres, sans quoi les
        # galets et les roseaux dessines ensuite s'eclaireraient de travers.
        self._reset_pbr()
        if ctx is None:
            return False
        self._rive = ctx
        # Tout de suite a l'heure de l'eau et a la lumiere du moment : une
        # scene redessinee ne doit pas faire repartir la vague a zero.
        rive.place(ctx, self._eau_t)
        rive.teinte(ctx, daylight.light_tint(self._seconds))
        return True

    def _place_ecume(self):
        """Decale l'ecume de ce qu'elle a derive depuis le debut.

        On repart des sommets AU REPOS, comme pour l'herbe au vent : des
        decalages ajoutes les uns aux autres finiraient par deriver. Et le
        decalage revient a zero a chaque tuile entiere -- la texture se
        repete, le saut ne se voit pas. u DIMINUE : l'image lue vient de la
        gauche, l'ecume va donc vers la droite."""
        for couche in self._eau:
            dec = (self._eau_t * couche["vitesse"]) % 1.0
            v = list(couche["repos"])
            for i in range(2, len(v), 4):
                v[i] -= dec
            couche["mesh"].vertices = v

    def _tick_eau(self, dt):
        # Seul l'ecran affiche fait couler son eau.
        if self.get_root_window() is None:
            return
        self._eau_t += dt
        self._place_ecume()
        if self._rive is not None:
            rive.place(self._rive, self._eau_t)

    def _sync_eau_clock(self):
        """L'horloge de l'eau ne tourne que s'il y a de l'eau a animer :
        de l'ecume a deplacer, ou la rive."""
        anime = bool(self._eau) or self._rive is not None
        if anime and self._eau_ev is None:
            self._eau_ev = Clock.schedule_interval(self._tick_eau,
                                                   1.0 / ECUME_FPS)
        elif not anime and self._eau_ev is not None:
            self._eau_ev.cancel()
            self._eau_ev = None

    def _lac(self, rng):
        w, h, x0, y0 = self.width, self.height, self.x, self.y

        # COLLINES / BERGE D'EN FACE : c'est de l'HERBE, et c'est la meme que
        # celle de la plaine -- elle prend donc sa texture. Ces deux bandes
        # etaient deux ellipses d'un vert plat, et elles etaient devenues la
        # derniere grande surface unie du jeu.
        #
        # Deux plans, comme en plaine : le lointain assombri (grass_far), le
        # plus proche a pleine couleur. Chacun est dessine par _fill_curve,
        # qui repete la tuile en perspective -- sur une bande aussi lointaine,
        # l'herbe doit etre tres fine, et une ellipse texturee l'aurait
        # simplement etiree d'un bord a l'autre.
        def colline(cx, demi, bas, haut):
            """La silhouette d'une colline : l'arc de l'ellipse d'avant."""
            def f(fx):
                d = (fx - cx) / demi
                return y0 + h * (bas + haut * math.sqrt(max(0.0, 1.0 - d * d)))
            return f

        # LES DEUX CRETES SONT BOSSELEES, elles ne sont plus des arcs
        # d'ellipse. Un arc parfait se lit comme un trait de compas : c'est
        # la premiere chose qui rendait cette berge invraisemblable. On y
        # ajoute deux ondulations lentes, tirees de la graine des voisins --
        # donc stables, et differentes d'une case a l'autre.
        bos = random.Random(self._graine_voisins() ^ 0x51D1)
        p1, p2 = bos.uniform(0, 6.28), bos.uniform(0, 6.28)

        def bosselee(f, ampleur):
            def g(fx):
                return f(fx) + h * ampleur * (
                    math.sin(fx * 6.28 * 1.7 + p1)
                    + 0.55 * math.sin(fx * 6.28 * 3.3 + p2))
            return g

        crete_loin = bosselee(colline(0.55, 0.80, 0.58, 0.18), 0.011)
        crete = bosselee(colline(0.52, 0.85, 0.54, 0.14), 0.008)

        # LA BERGE D'EN FACE, du plus loin au plus proche : le relief qui la
        # domine, son herbe, sa vegetation, sa greve, et l'air entre tout
        # cela et nous.
        #
        # L'HERBE GARDE SA FRANGE, contrairement a l'eau. Le bord du haut
        # d'une berge, c'est de l'herbe contre le ciel : elle s'effiloche.
        # Elle etait coupee au rasoir par habitude -- le lac passe frange=False
        # pour sa ligne d'eau, ou c'est juste, et les deux collines avaient
        # herite du reglage sans raison.
        self._relief_den_face(crete_loin)
        self._fill_curve(crete_loin, "grass_far")
        self._fill_curve(crete, "grass")
        eau_y = y0 + 0.60 * h
        self._foret_den_face(eau_y, crete, crete_loin)
        self._greve_den_face(eau_y, crete)
        # LE VOILE D'AIR, de la ligne d'eau au sommet de la berge. Il ne prend
        # que ce qui precede : l'eau, dessinee apres, reste nette.
        self._brume(lambda fx: eau_y, crete_loin)
        # Grande etendue d'eau (on est au bord), jusqu'a 0.60h.
        #
        # SANS FRANGE : l'eau ne s'effiloche pas, elle a un NIVEAU. Une rive
        # dentelee se lisait comme une cote decoupee vue d'avion, alors qu'on
        # regarde une surface plane par la tranche.
        # (Le bas est recouvert par la rive proche, juste apres : remplir
        # depuis y0 ne change rien a ce qu'on voit.)
        #
        # EN PERSPECTIVE, depuis que l'eau a une image : ses cailloux
        # rapetissent vers la rive d'en face. Et elle recoit son reflet et
        # son ecume qui derive (voir ECUME_COUCHES). Peu de colonnes
        # suffisent -- sans frange, u varie en ligne droite d'un bord a
        # l'autre -- et c'est autant de sommets en moins a deplacer trente fois
        # par seconde (ECUME_FPS).
        texturee = textures.base_texture("water") is not None
        self._fill_curve(lambda fx: eau_y, "water", segs=12,
                         depth=GROUND_DEPTH if texturee else 1.0,
                         frange=False, eau=True)
        # Reflets clairs : des traits, seulement pour l'eau SANS image -- sur
        # la photo ils faisaient des rayures de dessin anime. Les tirages
        # restent faits dans les deux cas : les galets et les roseaux tirent
        # leur place ensuite, et la rive ne doit pas se reorganiser selon
        # qu'une image est presente ou non.
        Color(0.32, 0.56, 0.74, 1)
        for _ in range(11):
            ly = y0 + rng.uniform(0.13, 0.58) * h
            lx = x0 + rng.uniform(0, 0.6) * w
            fin = lx + rng.uniform(0.2, 0.45) * w
            if not texturee:
                Line(points=[lx, ly, fin, ly], width=1.4)
        # Rive proche (premier plan) : l'eau vient y laper le sable (voir
        # rive.py). Sans shader ou sans ses images, un aplat de sable comme
        # avant. Les galets recoltables sont remontes a partir des jointures
        # (rien en bas). [recoltable: Pierre]
        if not self._rive_animee(x0, y0, w, h):
            self._trect("sand", x0, y0, w, 0.12 * h)

        # Galets, roseaux et objets installes sont tries ENSEMBLE par
        # profondeur : un feu de camp pose au fond passe derriere les roseaux
        # du premier plan.
        items = self._installed_items() + self._edge_items()
        for _ in range(12):
            rx = x0 + rng.uniform(0, 1) * w
            ry = y0 + rng.uniform(_HARVEST_FLOOR, 0.28) * h
            rr = rng.uniform(0.012, 0.03) * h
            if not self._take_or_skip("Pierre") and not self._is_blocked(rx, ry):
                # Leur distance se lit sur l'eau, qui monte jusqu'a 0,60 h.
                items.append((ry - self.DEBORD_CAILLOU * rr,
                              lambda rx=rx, ry=ry, rr=rr,
                              d=(ry - y0) / (0.60 * h):
                              self._pebble(rx, ry, rr, d)))
        # Roseaux (remontes a partir des jointures). [recoltable: Roseau]
        for _ in range(34):
            gx = x0 + rng.uniform(0, 1) * w
            gb = y0 + rng.uniform(_HARVEST_FLOOR, 0.30) * h
            gh = rng.uniform(0.08, 0.22) * h
            if (not self._take_or_skip("Roseau")
                    and not self._is_blocked(gx, gb, gb + gh)):
                items.append((gb, self._touffe(gx, gb, gh,
                                               (0.18, 0.38, 0.20, 1),
                                               sprite="reed")))
        # Pepites de mineraux, sur la GRILLE comme partout ailleurs. C'est le
        # seul gros element du lac : il n'y pousse ni arbre ni buisson.
        for kind, rang, depth, px, pb, jit in self._iter_nature_big():
            if kind == "nugget":
                items.extend(self._pepite_de_grille(rang, depth, px, pb, jit))
        self._dessine(items)

    def _plantes_de_berge(self, zone):
        """Ce qui pousse sur la berge d'en face, images manquantes ecartees.

        La table nomme plus de plantes que le dossier n'en contient : c'est
        voulu, le decor s'habille image par image. Mais un nom sans image ne
        dessine RIEN -- une berge de foret aurait pu se retrouver a moitie
        chauve sans que personne ne sache pourquoi. On filtre donc, et si
        rien ne reste on prend l'herbe, qui est toujours la."""
        lot = PLANTES_DE_BERGE.get(zone, PLANTES_DE_BERGE_DEFAUT)
        lot = [p for p in lot if foliage.variants(p[0])]
        return lot or [p for p in PLANTES_DE_BERGE_DEFAUT
                       if foliage.variants(p[0])]

    def _zone_de_berge(self, fx):
        """Quel paysage la berge d'en face montre A CETTE ABSCISSE.

        LA BERGE N'EST PAS D'UN SEUL TENANT, pas plus que l'horizon : ce qu'on
        voit a gauche de l'ecran est la case de gauche, ce qu'on voit au
        milieu est ce qu'il y a par-dela l'eau. Une berge uniforme perdrait
        justement l'information de direction, qui est tout l'interet de
        regarder au loin.

        Les bornes sont celles de horizon.SPANS, et volontairement : les
        silhouettes de relief et les arbres se posent aux memes endroits, donc
        une montagne et ses sapins tombent bien l'un sur l'autre."""
        gauche = horizon.SPANS["gauche"][1]
        droite = horizon.SPANS["droite"][0]
        milieu = self._berge or self._neighbours.get("face")
        if fx < gauche:
            return self._neighbours.get("gauche") or milieu
        if fx > droite:
            return self._neighbours.get("droite") or milieu
        return milieu

    def _relief_den_face(self, crete):
        """Le relief qui domine la berge d'en face, pose sur sa crete.

        SEULEMENT CE QU'AUCUNE IMAGE NE SAIT DONNER, c'est-a-dire la montagne.
        Les silhouettes de horizon.py servent a reconnaitre un paysage a un
        kilometre : une ligne d'ellipses pales dit "foret" tres bien de loin,
        mais posee juste derriere la berge d'un lac elle se lisait pour ce
        qu'elle est, des boules de coton. La foret d'en face est donc faite de
        vrais arbres (voir _foret_den_face) ; la montagne, elle, n a pas
        d'image et sa silhouette est de toute facon ce qui la definit -- une
        crete.

        SUR LA CRETE, ET NON AU RAS DE L'EAU. Ces silhouettes se posaient a
        0,70 h alors que la berge monte a 0,76 : elles etaient entierement
        recouvertes par l'herbe, et le lac n'a jamais rien montre de ses
        voisins.

        AU MILIEU, C'EST LA BERGE QUI COMMANDE : la case droit devant est
        presque toujours le lac lui-meme, qui n'a pas de silhouette. On y met
        ce qu'on a trouve de l'autre cote de l'eau, si bien que le relief du
        fond et les arbres du bord racontent la meme case."""
        voisins = dict(self._neighbours)
        if self._berge:
            voisins["face"] = self._berge
        voisins = {c: z for c, z in voisins.items() if z == "Montagne"}
        if voisins:
            horizon.draw(voisins, self.x, self.width, crete, self.height,
                         random.Random(self._graine_voisins()))

    def _abscisses_de_berge(self, brg, n):
        """Les positions horizontales des pieds, EN BOSQUETS.

        Un tirage uniforme ne fait pas de paquets -- c'est le paradoxe du
        hasard, et a l'oeil cela se lit comme une plantation reguliere. On
        tire donc d'abord des centres de bosquet, puis on repartit les
        arbres autour d'eux, en laissant une part d'isoles pour ne pas
        creuser de trou net entre deux groupes."""
        centres = [brg.random() for _ in range(BOSQUETS_DE_BERGE)]
        out = []
        for _ in range(n):
            if brg.random() < ISOLES_DE_BERGE or not centres:
                out.append(brg.random())
            else:
                c = centres[brg.randrange(len(centres))]
                out.append(min(0.999, max(0.001,
                                          brg.gauss(c, ETALEMENT_BOSQUET))))
        return out

    def _foret_den_face(self, eau_y, crete, crete_loin):
        """La vegetation de la berge d'en face, repartie EN PROFONDEUR.

        Chaque pied tire sa DISTANCE entre le bord de l'eau (0) et la crete
        du fond (1), et tout en decoule : ou il se pose, de combien il
        rapetisse, de quelle teinte il s'assombrit, et dans quel ordre on le
        dessine. C'est la perspective du sol appliquee a des sprites.

        CE QU'ON Y MET EST CE QUI S'Y TROUVE VRAIMENT. `self._berge` porte le
        type de la premiere case solide droit devant, par-dela l'eau (voir
        horizon.zone_den_face), et les bords de l'ecran montrent les cases de
        gauche et de droite (voir _zone_de_berge). Regarder l'autre rive
        renseigne donc sur ou l'on va, avec les vraies images du jeu.

        RIEN DE TOUT CELA N'EST RECOLTABLE et rien n'entre dans la grille :
        c'est de l'autre cote de l'eau. Ces plantes ne passent donc ni par
        _take_or_skip ni par _is_blocked."""
        w, x0, h = self.width, self.x, self.height
        # Une graine a part, comme pour l'horizon : la berge depend de ce
        # qu'il y a en face, et tourner sur place ne doit pas reorganiser le
        # decor de la case ou l'on se tient.
        brg = random.Random(self._graine_voisins() ^ 0x8E36)
        lots = {}
        pieds = []
        for fx in self._abscisses_de_berge(brg, PIEDS_DE_BERGE):
            zone = self._zone_de_berge(fx)
            if zone not in lots:
                lot = self._plantes_de_berge(zone)
                lots[zone] = (lot, [p[2] for p in lot]) if lot else None
            if lots[zone] is None:
                continue
            lot, poids = lots[zone]
            cx = x0 + fx * w
            # LA DISTANCE, tiree au carre : il y a plus de place au fond
            # qu'au bord, et une lisiere est plus dense en s'eloignant.
            t = brg.random() ** 0.65
            sol = eau_y + (max(crete(fx), crete_loin(fx)) - eau_y) * t
            if sol <= eau_y + 2.0:
                continue
            nom, ech, _ = brg.choices(lot, weights=poids)[0]
            # Sa taille : le retrait de la distance, un jeu d'un pied a
            # l'autre, et pour quelques-uns le coup de pouce qui les fait
            # PERCER la ligne (voir EMERGENTS_DE_BERGE).
            taille = (ech * h * (1.0 - RETRAIT_BERGE * t)
                      * brg.uniform(*TAILLE_BERGE))
            if brg.random() < EMERGENTS_DE_BERGE:
                taille *= brg.uniform(*EMERGENT_FACTEUR)
            pieds.append((sol, cx, nom, taille, t))
        # Du plus loin au plus proche : un arbre du fond ne doit pas se
        # dessiner par-dessus celui qui est devant lui.
        for sol, cx, nom, taille, t in sorted(pieds, reverse=True):
            k = TEINTE_BERGE * (1.0 - 0.22 * t)
            # LES IMAGES PENCHEES SE FONT RARES ICI AUSSI. Ces arbres-la ne
            # peuvent pas etre redresses -- ils sont poses en rectangle, sans
            # grille a faire tourner -- donc la seule chose a faire est de
            # les voir moins souvent. Une lisiere ou un sapin sur quatre
            # penche du meme cote se lit comme un motif repete, ce qui est
            # exactement le reproche fait a cette berge.
            self._sprite(nom, cx, sol, taille, teinte=(k, k, k),
                         pick=foliage.variante_droite(nom,
                                                      self._pick(cx, sol)))

    def _greve_den_face(self, eau_y, crete):
        """La plage de la berge d'en face : une bande de sable au ras de
        l'eau.

        C'EST ELLE QUI FAIT LA RIVE. Sans elle, l'eau touchait l'herbe
        directement -- une berge de gazon plongeant dans un lac, ce qu'on ne
        voit nulle part. La bande est coupee par la crete la ou la colline est
        trop basse pour en porter une : la, c'est la greve qui occupe toute la
        berge, et c'est juste."""
        sable = eau_y + SABLE_DEN_FACE * self.height
        self._fill_curve(lambda fx: min(crete(fx), sable), "sand",
                         frange=False)

    def _pebble(self, rx, ry, rr, depth=0.0):
        # Un galet est une petite pierre comme les autres (voir _stone).
        if not foliage.variants("pebble") and self._caillou(rx, ry, rr, depth):
            return
        self._shadow(rx, ry + rr * 0.1, rr * 2.2, opacity=0.8)
        if self._sprite("pebble", rx, ry, rr * 1.4):
            return
        Color(0.42, 0.40, 0.32, 1)
        Ellipse(pos=(rx - rr, ry), size=(rr * 2.4, rr * 1.4))
