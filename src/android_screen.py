"""
PLEIN ECRAN REEL SUR ANDROID (bords a bords, sans barres noires).

Le jeu laissait des bandes noires sur les quatre cotes. Ce n'est pas UN
defaut mais TROIS, qui se cumulent et qui se reglent chacun a un endroit
different -- d'ou ce module, parce que deux d'entre eux ne peuvent pas se
regler depuis buildozer.spec.

1. LA BARRE D'ETAT (en haut : heure, batterie, notifications).
   Cause : buildozer.spec disait `fullscreen = 0`. C'est corrige la-bas, et
   c'est le seul des trois qui se regle ainsi.

2. LA BARRE DE NAVIGATION (les boutons du telephone).
   Le theme "plein ecran" d'Android ne la cache PAS : elle survit a
   `fullscreen = 1`. Il faut la demander explicitement, en posant des
   drapeaux sur la vue, ce qui n'est faisable que depuis le code.
   On demande le mode IMMERSIF COLLANT ("sticky") : les barres reviennent
   si le joueur balaie depuis un bord -- il garde donc l'acces a son
   telephone -- puis disparaissent d'elles-memes. Sans "collant", il
   faudrait redemander le plein ecran a chaque fois.

3. LES BANDES SUR LES COTES (l'encoche / le poincon de la camera).
   C'est la cause la moins evidente, et celle qu'on ne devine pas. Quand un
   ecran a une encoche, Android REFUSE par defaut de laisser l'application
   dessiner a sa hauteur : il rétrecit la fenetre jusqu'au bord de
   l'encoche. En paysage, l'encoche est sur un cote -> une bande noire sur
   ce cote. On demande donc le mode SHORT_EDGES : l'app occupe tout l'ecran,
   encoche comprise.
   CONTREPARTIE A CONNAITRE : l'encoche passe alors PAR-DESSUS l'image. Le
   decor n'en souffre pas, mais si un bouton se retrouve dessous, c'est ici
   qu'il faudra revenir (il existe un mode NEVER, qui rend la bande noire).

Hors Android, tout ce module ne fait rien : les fonctions rendent False.
"""
from kivy.clock import Clock
from kivy.utils import platform

# Le plein ecran est redemande plusieurs fois apres le lancement. Ce n'est
# pas de la superstition : la fenetre de jeu (SDL) est creee APRES le
# demarrage de l'app et pose ses propres reglages d'affichage. Une demande
# faite trop tot serait donc effacee par elle, sans erreur ni message. On
# repasse derriere, une fois installe.
_RETRY_SECONDS = (0.0, 0.5, 2.0)

# android.view.WindowManager$LayoutParams
#   LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES = 1
# (recopie ici pour le cas ou la constante manquerait sur une vieille
#  version ; la vraie est lue d'abord, voir _cutout_short_edges)
_CUTOUT_SHORT_EDGES = 1

# L'encoche n'existe comme reglage qu'a partir d'Android 9 (API 28).
_CUTOUT_MIN_API = 28


def _apply_now():
    """Pose reellement les reglages. A n'appeler que sur le fil d'interface
    d'Android (voir go_fullscreen) : toucher a une fenetre depuis un autre
    fil leve une exception cote Java."""
    from jnius import autoclass
    activity = autoclass("org.kivy.android.PythonActivity").mActivity
    if activity is None:
        return False
    window = activity.getWindow()

    # 3. L'encoche : autoriser le dessin jusqu'aux bords.
    version = autoclass("android.os.Build$VERSION")
    if version.SDK_INT >= _CUTOUT_MIN_API:
        params = window.getAttributes()
        params.layoutInDisplayCutoutMode = _cutout_short_edges()
        window.setAttributes(params)

    # 1 et 2. Les deux barres du systeme.
    view = autoclass("android.view.View")
    window.getDecorView().setSystemUiVisibility(
        # Les trois LAYOUT_* disent : "dessine SOUS les barres". Sans eux,
        # l'image sauterait a chaque apparition/disparition d'une barre,
        # puisque la surface changerait de taille.
        view.SYSTEM_UI_FLAG_LAYOUT_STABLE
        | view.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION
        | view.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
        # Les deux suivants les cachent pour de bon.
        | view.SYSTEM_UI_FLAG_HIDE_NAVIGATION
        | view.SYSTEM_UI_FLAG_FULLSCREEN
        # Et celui-ci les fait revenir d'elles-memes apres un balayage.
        | view.SYSTEM_UI_FLAG_IMMERSIVE_STICKY)
    return True


def _cutout_short_edges():
    """La constante SHORT_EDGES, lue chez Android si elle s'y trouve."""
    try:
        from jnius import autoclass
        params = autoclass("android.view.WindowManager$LayoutParams")
        return params.LAYOUT_IN_DISPLAY_CUTOUT_MODE_SHORT_EDGES
    except Exception:
        return _CUTOUT_SHORT_EDGES


def go_fullscreen(*_args):
    """Demande le plein ecran bord a bord. Renvoie True si la demande est
    partie (donc uniquement sur Android).

    Ne leve jamais : sur un telephone ou quelque chose manquerait, le jeu
    doit continuer avec ses barres plutot que de ne pas demarrer."""
    if platform != "android":
        return False
    try:
        from android.runnable import run_on_ui_thread
        run_on_ui_thread(_apply_now)()
        return True
    except Exception:
        return False


def keep_fullscreen(*_args):
    """A brancher au demarrage et a chaque retour de l'arriere-plan.

    Android rend les barres des qu'il reprend la main sur la fenetre (retour
    depuis l'ecran d'accueil, appel, rotation) : le plein ecran n'est pas un
    reglage qu'on pose une fois, c'est une demande a repeter."""
    if platform != "android":
        return False
    for delai in _RETRY_SECONDS:
        Clock.schedule_once(go_fullscreen, delai)
    return True
