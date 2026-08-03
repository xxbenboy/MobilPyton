"""
Fond anime pilote par l'HEURE (cycle jour/nuit) avec astres et nuages.

Couches (canvas, aucune image) :
1. degrade du ciel dont la couleur suit l'heure ;
2. etoiles, visibles seulement quand il fait sombre ;
3. SOLEIL et LUNE qui montent puis descendent selon l'heure (arc dans le ciel) ;
4. NUAGES qui derivent lentement.

Usages :
- MENU : le temps avance tout seul (time_scale) -> cycle visible.
- JEU  : on appelle `set_seconds(...)` pour coller a l'horloge de la partie.
"""
import math
import random

from kivy.uix.widget import Widget
from kivy.clock import Clock
from kivy.graphics import Color, Rectangle, Ellipse, Mesh
from kivy.graphics.texture import Texture
from kivy.metrics import dp

SECONDS_PER_DAY = 24 * 3600

# 24h en 4 minutes (240 s) => 360 secondes de jeu par seconde reelle.
MENU_TIME_SCALE = SECONDS_PER_DAY / 240.0

_SKY_KEYS = [
    (0.0,  (0.05, 0.07, 0.12)),
    (4.0,  (0.06, 0.08, 0.13)),
    (5.0,  (0.34, 0.23, 0.25)),
    (6.0,  (0.42, 0.56, 0.72)),
    (12.0, (0.52, 0.70, 0.92)),
    (17.0, (0.46, 0.62, 0.82)),
    (19.0, (0.58, 0.36, 0.28)),
    (20.0, (0.22, 0.18, 0.26)),
    (22.0, (0.07, 0.09, 0.14)),
    (24.0, (0.05, 0.07, 0.12)),
]


def sky_color(seconds):
    h = (seconds % SECONDS_PER_DAY) / 3600.0
    for i in range(len(_SKY_KEYS) - 1):
        h0, c0 = _SKY_KEYS[i]
        h1, c1 = _SKY_KEYS[i + 1]
        if h0 <= h <= h1:
            t = 0.0 if h1 == h0 else (h - h0) / (h1 - h0)
            return [c0[j] + (c1[j] - c0[j]) * t for j in range(3)]
    return list(_SKY_KEYS[-1][1])


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
MOON_LIGHT = 0.22

# Halo lumineux de la lune : (rayon x le rayon du disque, opacite de base).
# Du plus large et diffus au plus serre. L'intensite suit la part eclairee :
# une pleine lune brille fort, une nouvelle lune pas du tout.
_MOON_HALO = ((3.4, 0.045), (2.4, 0.075), (1.6, 0.13))

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
    (aucun effet le jour, ou l'assombrissement est deja nul)."""
    return _astro_darkness(seconds, max_dark) * (
        1.0 - MOON_LIGHT * moon_illumination(seconds))


def night_factor(seconds):
    """Avancement de la NUIT : 0 en plein jour, 1 en pleine nuit.

    Meme courbe (progressive) que l'assombrissement, mais normalisee. Ne
    depend PAS de la lune : une pleine lune ne fait pas revenir les papillons.
    Sert a faire disparaitre les insectes de jour et apparaitre les lucioles."""
    return _astro_darkness(seconds, 1.0)


class AnimatedBackground(Widget):
    def __init__(self, start_seconds=6 * 3600, time_scale=0.0, stars=28,
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
        self._current = sky_color(self._seconds)
        self._t = 0.0
        self._grad_accum = 0.0

        self._grad_tex = Texture.create(size=(1, 64), colorfmt="rgba")
        self._grad_tex.wrap = "clamp_to_edge"
        self._grad_tex.mag_filter = "linear"
        self._grad_tex.min_filter = "linear"

        with self.canvas.before:
            # 1. Ciel (degrade).
            Color(1, 1, 1, 1)
            self._rect = Rectangle(texture=self._grad_tex,
                                   pos=self.pos, size=self.size)

            # 2. Etoiles.
            self._stars = []
            rng = random.Random(20240601)
            for _ in range(stars):
                col = Color(1, 1, 1, 0.0)
                self._stars.append({
                    "col": col, "e": Ellipse(),
                    "fx": rng.uniform(0.02, 0.98),
                    "fy": rng.uniform(0.40, 0.98),
                    "size": dp(rng.uniform(1.5, 3.5)),
                    "base": rng.uniform(0.25, 0.75),
                    "phase": rng.uniform(0.0, 6.28),
                    "tw": rng.uniform(0.6, 1.8),
                })

            # 3. Soleil (avec halo) et Lune.
            self._sun_glow_c = Color(1.0, 0.92, 0.55, 0.0)
            self._sun_glow = Ellipse()
            self._sun_c = Color(1.0, 0.95, 0.6, 0.0)
            self._sun = Ellipse()
            # Lune : halo lumineux (plusieurs cercles de plus en plus
            # diffus), puis UNIQUEMENT la portion eclairee, dessinee comme
            # un maillage (voir _place_moon). Rien n'est dessine pour la
            # face sombre : elle est donc reellement invisible.
            self._moon_glow = []
            for _mult, _a in _MOON_HALO:
                self._moon_glow.append((Color(0.85, 0.90, 1.0, 0.0),
                                        Ellipse()))
            self._moon_c = Color(0.97, 0.98, 1.0, 0.0)
            self._moon = Mesh(mode="triangle_strip")
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
            for _ in range(6):
                nha = crng.randint(2, 3)
                halo_shape = [(crng.uniform(-1.2, 1.2),
                               crng.uniform(0.05, 0.45),
                               crng.uniform(1.8, 2.6),
                               crng.uniform(1.0, 1.4)) for _ in range(nha)]
                nb = crng.randint(4, 6)
                base_shape = [((k / (nb - 1) - 0.5) * 2.7,
                               crng.uniform(-0.04, 0.04),
                               crng.uniform(1.05, 1.55),
                               crng.uniform(0.45, 0.6)) for k in range(nb)]
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
                self._clouds.append({
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
                    "fy": crng.uniform(0.55, 0.90),
                    "scale": crng.uniform(0.10, 0.20),
                    "speed": crng.uniform(0.005, 0.016),
                    "base": crng.uniform(0.0, 1.0),
                })

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

    def _update_layout(self, *_):
        self._rect.pos = self.pos
        self._rect.size = self.size
        for s in self._stars:
            sz = s["size"]
            s["e"].size = (sz, sz)
            s["e"].pos = (self.x + s["fx"] * self.width - sz / 2,
                          self.y + s["fy"] * self.height - sz / 2)

    def _build_gradient(self):
        h = 64
        bot = self._current
        top = [c * 0.4 for c in self._current]
        buf = bytearray(h * 4)
        for i in range(h):
            t = i / (h - 1)
            buf[i * 4] = int((bot[0] * (1 - t) + top[0] * t) * 255)
            buf[i * 4 + 1] = int((bot[1] * (1 - t) + top[1] * t) * 255)
            buf[i * 4 + 2] = int((bot[2] * (1 - t) + top[2] * t) * 255)
            buf[i * 4 + 3] = 255
        self._grad_tex.blit_buffer(bytes(buf), colorfmt="rgba",
                                   bufferfmt="ubyte")

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
        for (col, ell), (mult, base_a) in zip(self._moon_glow, _MOON_HALO):
            col.a = base_a * glow
            self._place_disc(ell, cx, cy, r * mult)

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
            verts += [cx + x_in, y, 0.0, 0.0,
                      cx + x_out, y, 0.0, 0.0]
        self._moon.vertices = verts

    def _tick(self, dt):
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
        self._current = self._weather_sky(sky_color(self._seconds))

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
        for s in self._stars:
            twinkle = 0.35 + 0.65 * abs(math.sin(self._t * s["tw"] + s["phase"]))
            # Le clair de lune efface une partie des etoiles (comme en vrai).
            s["col"].a = (s["base"] * twinkle * night * astro
                          * (1.0 - 0.45 * moon_illumination(self._abs_seconds)))

        radius = min(w, h) * 0.055

        # Soleil : arc de 5h a 19h (gauche -> droite).
        sp = _clamp01((hour - 5.0) / 14.0)
        sx = x0 + w * (0.12 + 0.76 * sp)
        sy = y0 + h * (0.45 + 0.42 * math.sin(math.pi * sp))
        self._sun_c.a = sun_a * astro
        self._place_disc(self._sun, sx, sy, radius)
        self._sun_glow_c.a = sun_a * 0.35 * astro
        self._place_disc(self._sun_glow, sx, sy, radius * 2.1)

        # Lune : arc de 19h a 5h (la nuit).
        nh = (hour - 19.0) % 24.0
        mp = _clamp01(nh / 10.0)
        mx = x0 + w * (0.12 + 0.76 * mp)
        my = y0 + h * (0.45 + 0.42 * math.sin(math.pi * mp))
        self._place_moon(mx, my, radius * 0.85, night * astro)

        # Nuages (cumulus) : halo doux, dessous ombre, bouffees blanches,
        # reflets clairs du cote eclaire.
        cloud_a = 0.55 * (0.30 + 0.70 * sun_a) * self._wx["cloud"]
        # Par gros temps, les nuages sont nettement plus sombres.
        shade = 1.0 - 0.55 * self._wx["dark"]

        def place(ellipses, shapes, cx, cy, s):
            for ell, (dx, dy, sw, sh) in zip(ellipses, shapes):
                ell.size = (sw * s, sh * s)
                ell.pos = (cx + dx * s - sw * s / 2, cy + dy * s)

        for cl in self._clouds:
            fx = (cl["base"] + self._t * cl["speed"]) % 1.4 - 0.2
            cx = x0 + fx * w
            cy = y0 + cl["fy"] * h
            s = w * cl["scale"]
            for key, ells, shapes, mult in (
                    ("c_halo", "halo_ell", "halo_shape", 0.22),
                    ("c_base", "base_ell", "base_shape", 0.85),
                    ("c_top", "top_ell", "top_shape", 1.00),
                    ("c_hi", "hi_ell", "hi_shape", 0.85)):
                cr, cg, cb = _CLOUD_RGB[key]
                cl[key].rgba = (cr * shade, cg * shade, cb * shade,
                                cloud_a * mult)
                place(cl[ells], cl[shapes], cx, cy, s)
