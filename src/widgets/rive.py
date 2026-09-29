"""
LA RIVE ANIMEE : l'eau qui vient laper le sable, au bord du lac.

Une bande posee au premier plan de la scene du lac (voir ZoneScenery._lac) :
en haut, de l'eau claire sur des galets, qui se fond dans le lac ; en bas, le
sable sec. Une image la dessine (rive_B), un petit shader l'anime :

- LA NAPPE : a chaque vague, une mince couche d'eau monte sur le sable puis
  se retire. Elle monte vite et redescend lentement, comme une vraie vague
  qui s'etale puis s'infiltre. Deux houles de periodes differentes se
  relaient : de temps en temps, une vague va plus loin que les autres.
- SON BORD n'est pas une regle : il arrive en festons, un peu en retard ici,
  un peu en avance la, et un lisere d'ecume le souligne tant qu'il monte.
- LE SABLE MOUILLE : derriere la nappe qui se retire, le sable reste plus
  sombre, puis seche jusqu'a la vague suivante.
- LES REFLETS (rive_E) : le reseau de lumiere que la surface projette sur le
  fond. Ils avancent et reculent avec l'eau, et le fond ondule sous elle,
  comme vu a travers une surface qui bouge.

LE SABLE ET LES GALETS NE BOUGENT PAS : c'est l'eau qui passe dessus.

Un contexte de rendu A PART, emboite dans celui du decor : ses uniformes
(l'heure de l'eau, la couleur de la lumiere) ne regardent que la bande. Sans
shader ou sans images, la scene garde son ancienne rive, un aplat de sable.

Tout ce qui depend du temps est calcule ICI, en Python, et passe au shader
deja ramene a un tour (phases entre 0 et 1, angles entre 0 et 2 pi) : un
telephone ne garantit pas la grande precision des flottants dans un shader,
et un temps qui grandit sans fin y ferait trembler les vagues au bout d'une
heure de jeu.
"""
import math

from kivy.graphics import BindTexture, Color, Mesh, RenderContext

# Les images : rive_B (la bande) et rive_E (ses reflets), dans
# assets/textures.
NOM = "rive"

# Hauteur de la bande, en part de la hauteur de la scene. Sa ligne d'eau au
# repos tombe vers 0,11 : la ou finissait l'ancienne rive.
HAUTEUR = 0.24

# Une tuile de la bande est ETIREE en largeur : c'est un sol vu de biais, et
# un sol vu de biais se tasse en hauteur. 2 = un galet deux fois plus large
# que haut a l'ecran.
ETIREMENT = 2.0

# Periodes des deux houles (secondes) et derive des reflets (tuiles par
# seconde, le long de la rive).
PERIODE_1 = 5.3
PERIODE_2 = 3.7
DERIVE = 0.012
# Vitesses des petites ondulations (radians par seconde).
ONDES = (1.3, 0.8, 2.1, 1.7)

FS = """
#ifdef GL_ES
#ifdef GL_FRAGMENT_PRECISION_HIGH
precision highp float;
#else
precision mediump float;
#endif
#endif

varying vec4 frag_color;
varying vec2 tex_coord0;

uniform sampler2D texture0;      /* rive_B : la bande (unite 0) */
uniform sampler2D rive_reflets;  /* rive_E : les reflets (unite 1) */
uniform vec3 rive_teinte;        /* couleur de la lumiere (daylight) */
uniform vec2 rive_p;             /* phases des deux houles, 0 a 1 */
uniform vec4 rive_a;             /* angles des ondulations, 0 a 2 pi */
uniform float rive_d;            /* derive des reflets, 0 a 1 */

/* v va de 0 (haut de la bande, cote lac) a 1 (bas, cote terre). */
const float REPOS = 0.55;        /* la ligne d'eau au repos */
const float COURSE = 0.26;       /* jusqu'ou monte une grande vague */

/* Une vague : monte vite (jusqu'a 0,25 du cycle), se retire lentement
   (jusqu'a 0,85), puis le sable reste a decouvert. */
float montee(float c) {
    if (c < 0.25) {
        float k = 1.0 - c / 0.25;
        return 1.0 - k * k;
    }
    return 1.0 - smoothstep(0.25, 0.85, c);
}

/* Le sable que la vague vient de quitter, et qui seche. RIEN pendant
   qu'elle monte : devant elle, c'est le sable de la vague d'avant, deja sec
   -- sinon il noircirait d'un coup la ou le cycle recommence. */
float mouille(float c, float bord, float atteinte, float v) {
    if (c < 0.25) {
        return 0.0;
    }
    float trace = step(bord, v)
                * (1.0 - smoothstep(atteinte - 0.01, atteinte + 0.03, v));
    return trace * (1.0 - smoothstep(0.25, 1.0, c));
}

void main(void) {
    float u = tex_coord0.x;
    float v = tex_coord0.y;
    /* Deux houles ; leur phase varie LE LONG DE LA RIVE : le bord arrive
       en festons, pas d'un bloc. */
    float c1 = fract(rive_p.x + 0.16 * sin(u * 2.1 + 0.7)
                     + 0.05 * sin(u * 7.3 + 1.9));
    float c2 = fract(rive_p.y + 0.21 * sin(u * 1.4 + 2.6)
                     + 0.06 * sin(u * 9.1));
    float r1 = montee(c1);
    float r2 = 0.55 * montee(c2);
    float frise = 0.010 * sin(u * 31.0 + rive_a.x)
                + 0.006 * sin(u * 57.0 - rive_a.y);
    float b1 = REPOS + COURSE * r1 + frise;
    float b2 = REPOS + COURSE * r2 + frise;
    float bord = max(b1, b2);
    float r = max(r1, r2);
    float c = r1 >= r2 ? c1 : c2;            /* la vague qui mene */

    /* Sous l'eau : tout ce qui est au-dessus du bord de la nappe. */
    float eau = 1.0 - smoothstep(bord - 0.02, bord + 0.004, v);
    /* La NAPPE : l'eau qui recouvre le sable, sous la ligne de repos. */
    float nappe = eau * smoothstep(REPOS - 0.06, REPOS + 0.02, v);

    /* Le fond ondule sous l'eau, vu a travers la surface. */
    vec2 uv = tex_coord0 + eau * 0.0035
            * vec2(sin(v * 60.0 + rive_a.z), cos(u * 45.0 + rive_a.w));
    vec4 fond = texture2D(texture0, uv);
    vec3 col = fond.rgb;

    /* Sable mouille, puis nappe : plus sombre, un rien plus froid. */
    float m = max(mouille(c1, b1, REPOS + COURSE + frise, v),
                  mouille(c2, b2, REPOS + 0.55 * COURSE + frise, v));
    col *= 1.0 - 0.20 * m;
    /* La nappe : le sable dessous est mouille (plus sombre), et sa surface
       renvoie un peu de ciel. */
    col = mix(col, col * vec3(0.78, 0.84, 0.86), 0.55 * nappe)
        + vec3(0.030, 0.045, 0.055) * nappe;

    /* Les reflets suivent l'eau : ils descendent quand elle monte. */
    vec4 refl = texture2D(rive_reflets,
                          vec2(u + rive_d, v - (bord - REPOS)));
    col += refl.rgb * refl.a * (0.30 + 0.15 * nappe) * eau;

    /* L'ecume du bord, vive tant que la vague monte, puis elle s'efface. */
    float vif = c < 0.25 ? 1.0 : 1.0 - smoothstep(0.25, 0.60, c);
    /* Son grain lui est propre : les reflets, eux, s'eteignent justement
       a la ligne d'eau. */
    float grain = 0.6 + 0.4 * sin(u * 83.0 + rive_a.z)
                            * sin(u * 37.0 - rive_a.x);
    float ecume = exp(-((v - bord) * (v - bord)) / 0.00025)
                * smoothstep(0.02, 0.10, r) * vif * grain;
    col = mix(col, vec3(0.95, 0.95, 0.92), clamp(0.85 * ecume, 0.0, 1.0));

    gl_FragColor = vec4(col * rive_teinte, fond.a) * frag_color;
}
"""


def bande(x0, y0, w, h, fond, reflets):
    """Pose la bande (a appeler DANS le bloc `with canvas` du decor) et rend
    son contexte, ou None si le shader ne s'est pas compile -- la scene
    garde alors son aplat de sable.

    `h` est la hauteur de la bande a l'ecran. La tuile en suit la mesure :
    le haut de l'image (l'eau) tombe en haut de la bande, le bas (le sable
    sec) au pied de l'ecran, quelle que soit sa taille."""
    ctx = RenderContext(use_parent_projection=True,
                        use_parent_modelview=True,
                        use_parent_frag_modelview=True)
    ctx.shader.fs = FS
    if not ctx.shader.success:
        return None
    ctx["rive_reflets"] = 1
    ctx["rive_teinte"] = [1.0, 1.0, 1.0]
    # Une tuile : toute la hauteur de la bande, et ETIREMENT fois plus en
    # largeur (en proportion de l'image, 1024 x 512).
    tuile = h * (float(fond.width) / max(1, fond.height)) * ETIREMENT
    cx = x0 + w / 2.0
    # v rentre d'un cheveu : a 0 et a 1 pile, le filtrage irait piocher
    # l'autre bord de l'image (la tuile se repete).
    haut, bas = 0.002, 0.998
    verts = [x0, y0, (x0 - cx) / tuile, bas,
             x0 + w, y0, (x0 + w - cx) / tuile, bas,
             x0 + w, y0 + h, (x0 + w - cx) / tuile, haut,
             x0, y0 + h, (x0 - cx) / tuile, haut]
    with ctx:
        Color(1, 1, 1, 1)
        BindTexture(texture=reflets, index=1)
        Mesh(vertices=verts, indices=[0, 1, 2, 0, 2, 3], mode="triangles",
             texture=fond)
    place(ctx, 0.0)
    return ctx


def place(ctx, t):
    """L'eau a l'instant `t` (secondes) : tout est ramene a un tour ici."""
    ctx["rive_p"] = [(t / PERIODE_1) % 1.0, (t / PERIODE_2) % 1.0]
    ctx["rive_a"] = [(t * f) % (2.0 * math.pi) for f in ONDES]
    ctx["rive_d"] = (t * DERIVE) % 1.0


def teinte(ctx, couleur):
    """La couleur de la lumiere (voir daylight.light_tint)."""
    ctx["rive_teinte"] = [float(c) for c in couleur[:3]]
