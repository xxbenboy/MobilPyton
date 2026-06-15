"""
Point d'entree du jeu.

Buildozer (l'outil qui fabrique l'APK Android) EXIGE un fichier `main.py`
a la racine du projet : c'est lui qui est lance au demarrage de l'app.

Resolution de BASE (resolution "cible") : celle d'un telephone courant,
2340x1080, mais en PORTRAIT (le jeu est un menu vertical), donc
1080 de large x 2340 de haut.

- Sur Android, ces reglages sont IGNORES : c'est l'ecran reel du telephone
  qui est utilise (et l'interface s'y adapte toute seule).
- Sur PC, on ouvre une fenetre a cette taille MAIS on la reduit pour qu'elle
  tienne dans l'ecran, en gardant les memes proportions. Comme toute
  l'interface est en proportions (size_hint / pos_hint) + polices qui suivent
  la taille de la fenetre, elle s'ajuste automatiquement a toute resolution.
"""
from kivy.config import Config
from kivy.utils import platform

# Resolution de base (portrait).
BASE_WIDTH = 1080
BASE_HEIGHT = 2340

# Taille minimale de la fenetre, en proportion de la base (30 %). En dessous,
# l'interface deviendrait trop petite : on empeche donc de retrecir plus.
MIN_SCALE = 0.30

# /!\ Ces reglages doivent etre definis AVANT tout autre import de Kivy.
# Sur mobile, l'OS impose la taille reelle : on ne touche a rien.
if platform not in ("android", "ios"):
    win_w, win_h = BASE_WIDTH, BASE_HEIGHT
    try:
        # On demande la taille de l'ecran au systeme (tkinter, fourni avec
        # Python sur PC) pour ne jamais ouvrir une fenetre plus grande que
        # l'ecran.
        import tkinter
        tk = tkinter.Tk()
        tk.withdraw()
        screen_w = tk.winfo_screenwidth()
        screen_h = int(tk.winfo_screenheight() * 0.92)  # marge (barre taches)
        tk.destroy()
        # Facteur de reduction qui garde les proportions (<= 1 : jamais agrandi).
        scale = min(screen_w / BASE_WIDTH, screen_h / BASE_HEIGHT, 1.0)
        win_w = int(BASE_WIDTH * scale)
        win_h = int(BASE_HEIGHT * scale)
    except Exception:
        # Repli si tkinter indisponible : une fenetre portrait raisonnable.
        scale = 820 / BASE_HEIGHT
        win_w = int(BASE_WIDTH * scale)
        win_h = 820

    Config.set("graphics", "width", str(win_w))
    Config.set("graphics", "height", str(win_h))
    # Redimensionnable : on peut voir l'interface se reajuster en direct.
    Config.set("graphics", "resizable", "1")
    # Seuil minimal : impossible de retrecir la fenetre en dessous (garde les
    # proportions portrait de la base).
    Config.set("graphics", "minimum_width", str(int(BASE_WIDTH * MIN_SCALE)))
    Config.set("graphics", "minimum_height", str(int(BASE_HEIGHT * MIN_SCALE)))

from src.game import MobilPytonApp


if __name__ == "__main__":
    MobilPytonApp().run()
