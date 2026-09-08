"""
ECLAIRAGE DU DECOR SELON L'HEURE : une seule source de verite.

Avant, trois choses decidaient chacune dans leur coin de quoi avait l'air une
scene : le shader PBR avait une lumiere FIXE, les ombres etaient ecrites en dur
sous chaque element (toujours au meme endroit, toujours la meme opacite), et le
voile de nuit etait un bleu marine constant. Resultat : a 19h le ciel virait a
l'orange mais le sol restait eclaire comme a midi, et les ombres pointaient
toujours dans la meme direction.

Ce module donne l'heure a tout le monde :
- `light_dir`    : d'ou vient la lumiere (pour le relief du shader PBR) ;
- `light_tint`   : sa COULEUR (doree a l'aube, blanche a midi, bleue la nuit) ;
- `shadow`       : direction, longueur et opacite des ombres portees ;
- `veil_color`   : la teinte du voile qui assombrit la scene.

Les fonctions ne dependent que du temps : aucune n'a besoin de Kivy, elles se
testent seules.

Le SOLEIL suit le meme arc que dans le ciel (voir animated_background) : il se
leve a 5h a gauche, culmine a midi, se couche a 19h a droite. La nuit, c'est la
LUNE qui prend le relais, en beaucoup plus faible.
"""
import math

SECONDS_PER_DAY = 24 * 3600

# Heures de lever et de coucher : les memes que l'arc du soleil dans le ciel.
SUNRISE = 5.0
SUNSET = 19.0

# COULEUR de la lumiere heure par heure. Ce sont des TEINTES : chaque cle est
# normalisee (son canal le plus fort vaut 1) pour ne jamais assombrir par
# elle-meme. L'obscurite est le travail du voile de nuit, pas de la teinte ;
# sans cette separation, la nuit serait assombrie DEUX fois.
_TINT_KEYS = [
    (0.0,  (0.64, 0.72, 1.00)),     # nuit : clair de lune bleu
    (4.0,  (0.64, 0.72, 1.00)),
    (5.0,  (1.00, 0.72, 0.66)),     # premieres lueurs, rose
    (6.5,  (1.00, 0.86, 0.68)),     # or du matin
    (9.0,  (1.00, 0.97, 0.92)),
    (12.0, (1.00, 1.00, 1.00)),     # midi : lumiere neutre
    (16.0, (1.00, 0.96, 0.88)),
    (18.5, (1.00, 0.80, 0.58)),     # or du soir
    (19.5, (1.00, 0.63, 0.49)),     # soleil couchant, orange
    (20.5, (0.86, 0.76, 1.00)),     # crepuscule violet
    (22.0, (0.64, 0.72, 1.00)),     # la nuit s'installe
    (24.0, (0.64, 0.72, 1.00)),
]

# TEINTE du voile qui assombrit le decor. Un voile toujours bleu marine donnait
# un crepuscule froid alors que le ciel, lui, flambait : ici le voile du soir
# est chaud et sombre, celui de la nuit franchement bleu.
_VEIL_KEYS = [
    (0.0,  (0.03, 0.05, 0.12)),
    (4.5,  (0.03, 0.05, 0.12)),
    (5.5,  (0.10, 0.06, 0.09)),     # avant l'aube, brun-violet
    (7.0,  (0.06, 0.06, 0.10)),
    (18.0, (0.06, 0.06, 0.10)),
    (19.5, (0.14, 0.06, 0.05)),     # coucher : ombres chaudes
    (21.0, (0.06, 0.05, 0.11)),
    (22.5, (0.03, 0.05, 0.12)),
    (24.0, (0.03, 0.05, 0.12)),
]

# Bornes de l'ombre portee. A midi le soleil est au zenith : ombre courte et
# franche, collee sous l'objet. Au ras de l'horizon elle s'etire et palit.
SHADOW_MIN_LEN = 1.0        # longueur (x la largeur de l'objet) au zenith
SHADOW_MAX_LEN = 3.4        # longueur au ras de l'horizon
SHADOW_MAX_ALPHA = 0.30     # opacite maximale (soleil haut)
SHADOW_NIGHT_ALPHA = 0.10   # ce qui reste la nuit (lumiere diffuse)

# Ce que la lune apporte comme lumiere DIRECTIONNELLE, compare au soleil.
MOON_STRENGTH = 0.22


def _hour(seconds):
    return (float(seconds) % SECONDS_PER_DAY) / 3600.0


def _ramp(keys, seconds):
    """Interpole une table (heure -> triplet) a l'heure donnee."""
    h = _hour(seconds)
    for i in range(len(keys) - 1):
        h0, c0 = keys[i]
        h1, c1 = keys[i + 1]
        if h0 <= h <= h1:
            t = 0.0 if h1 == h0 else (h - h0) / (h1 - h0)
            return tuple(c0[j] + (c1[j] - c0[j]) * t for j in range(3))
    return tuple(keys[-1][1])


def sun_elevation(seconds):
    """Hauteur du SOLEIL : 0 a l'horizon (ou sous terre), 1 au zenith."""
    h = _hour(seconds)
    if not (SUNRISE <= h <= SUNSET):
        return 0.0
    return math.sin(math.pi * (h - SUNRISE) / (SUNSET - SUNRISE))


def sun_course(seconds):
    """Avancement du soleil dans son arc : 0 au lever, 1 au coucher.

    Hors de la journee, on garde la valeur de l'extremite la plus proche : la
    lumiere ne saute pas d'un cote a l'autre du ciel a minuit."""
    h = _hour(seconds)
    if h < SUNRISE:
        return 0.0
    if h > SUNSET:
        return 1.0
    return (h - SUNRISE) / (SUNSET - SUNRISE)


def moon_elevation(seconds):
    """Hauteur de la LUNE : elle parcourt l'arc inverse, de 19h a 5h."""
    nh = (_hour(seconds) - SUNSET) % 24.0
    if nh > 10.0:
        return 0.0
    return math.sin(math.pi * nh / 10.0)


def moon_course(seconds):
    """Avancement de la lune dans son arc : 0 au lever (19h), 1 a 5h."""
    nh = (_hour(seconds) - SUNSET) % 24.0
    return max(0.0, min(1.0, nh / 10.0))


def key_elevation(seconds):
    """Hauteur de l'astre qui MENE l'eclairage (soleil, sinon lune).

    Sert aux ombres : c'est la hauteur de la lumiere qui decide si elles sont
    courtes et franches (astre haut) ou longues et diluees (astre rasant)."""
    return max(sun_elevation(seconds),
               moon_elevation(seconds) * MOON_STRENGTH)


def _astro_vec(course, elev):
    """Vecteur d'un astre : a gauche au lever, au-dessus au zenith, a droite
    au coucher. On garde toujours une composante vers la camera (z), sinon le
    relief des textures devient illisible quand l'astre rase l'horizon."""
    return (-math.cos(math.pi * course) * (1.0 - 0.55 * elev),
            0.18 + 0.62 * elev,
            0.58 + 0.42 * elev)


# Lumiere diffuse du ciel, presente meme quand les deux astres sont couches.
# Sans elle, la direction serait indefinie entre le coucher de la lune et le
# lever du soleil.
_AMBIENT_VEC = (0.0, 0.40, 0.90)
_AMBIENT_WEIGHT = 0.12


def light_dir(seconds):
    """Direction (x, y, z) de la lumiere pour le shader de relief.

    x : -1 = elle vient de la gauche, +1 = de la droite.
    y : vers le haut (la lumiere descend toujours d'en haut).
    z : vers la camera.

    Le soleil et la lune sont ADDITIONNES, chacun pondere par sa hauteur, au
    lieu d'etre choisis l'un ou l'autre : au lever comme au coucher la lumiere
    pivote doucement d'un astre a l'autre, sans le saut brutal de bord de cadre
    qu'un simple `if` produisait."""
    se = sun_elevation(seconds)
    me = moon_elevation(seconds) * MOON_STRENGTH
    sv = _astro_vec(sun_course(seconds), se)
    mv = _astro_vec(moon_course(seconds), me)
    comps = ((sv, se), (mv, me), (_AMBIENT_VEC, _AMBIENT_WEIGHT))
    x, y, z = (sum(v[i] * wt for v, wt in comps) for i in range(3))
    n = math.sqrt(x * x + y * y + z * z) or 1.0
    return (x / n, y / n, z / n)


def light_tint(seconds):
    """COULEUR de la lumiere (r, g, b), a multiplier sur le decor.

    Renormalisee APRES interpolation : entre deux teintes normalisees, la
    moyenne ne l'est plus (elle assombrit), et le decor aurait perdu de la
    lumiere aux heures intermediaires. Ici la teinte change la couleur, jamais
    la luminosite -- l'obscurite reste le travail du voile de nuit."""
    c = _ramp(_TINT_KEYS, seconds)
    top = max(c) or 1.0
    return tuple(v / top for v in c)


def veil_color(seconds):
    """Teinte du voile qui assombrit le decor (son opacite vient d'ailleurs)."""
    return _ramp(_VEIL_KEYS, seconds)


def shadow(seconds):
    """Ombre portee a cette heure : (decalage_x, longueur, opacite).

    - decalage_x : de combien l'ombre fuit l'astre, en fraction de la LARGEUR
      de l'objet. Positif = vers la droite.
    - longueur   : etirement de l'ombre (x sa largeur au repos).
    - opacite    : plus la lumiere est rasante, plus l'ombre est diluee.

    L'ombre s'allonge et palit quand l'astre descend : a midi elle est courte
    et marquee, au couchant elle traine loin sur le sol."""
    elev = key_elevation(seconds)
    lx, _ly, _lz = light_dir(seconds)
    length = SHADOW_MAX_LEN + (SHADOW_MIN_LEN - SHADOW_MAX_LEN) * elev
    # L'ombre part a l'oppose de la lumiere, d'autant plus loin qu'elle est
    # longue.
    offset = -lx * (length - SHADOW_MIN_LEN) * 0.5
    alpha = SHADOW_NIGHT_ALPHA + (SHADOW_MAX_ALPHA - SHADOW_NIGHT_ALPHA) * elev
    return offset, length, alpha
