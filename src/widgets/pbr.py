"""
Eclairage par carte de normales (effet "PBR") pour les surfaces texturees.

Kivy n'a pas de PBR integre : on installe ici un petit shader maison qui
eclaire chaque pixel selon la carte de NORMALES (relief) et assombrit selon le
canal R de la carte PACKED (occlusion ambiante). C'est volontairement simple
(diffus + ambiant + AO) pour rester fiable sur telephone (OpenGL ES 2).

Principe d'integration :
- On remplace le canvas d'un widget par un RenderContext qui utilise ce shader.
- La BaseColor est liee normalement (texture0, gere par Kivy via `texture=`).
- Avant chaque surface texturee, on lie sa Normal sur l'unite 1 et sa Packed
  sur l'unite 2 (bind_maps) ; apres, on remet des cartes "neutres" (reset_maps)
  pour que les formes vectorielles (herbe, pierres dessinees...) restent neutres.

L'eclairage ne s'active QUE si au moins une carte de normales existe
(textures.has_any_normal()). Sans cartes, on n'installe pas le shader : aucun
risque, rendu identique a avant.
"""
from kivy.graphics import BindTexture
from kivy.graphics.texture import Texture

# Mettre False pour desactiver completement l'eclairage (depannage).
LIGHTING = True

# Direction de la lumiere (x, y, z). z eleve = lumiere de face.
LIGHT = (-0.28, 0.34, 0.90)

# Reglages d'eclairage (tu peux les ajuster) :
# - RELIEF      : force du relief donne par la carte Normal (0 = aucun relief).
#                 Une surface PLATE reste a la luminosite d'origine (pas
#                 d'assombrissement global) ; le relief ne fait qu'ajouter des
#                 zones un peu plus claires / plus sombres autour.
# - AO_STRENGTH : influence de l'occlusion (canal R de la carte Packed). 0 =
#                 ignoree (utile si ton Packed ne range pas l'AO dans le rouge).
# - BRIGHTNESS  : luminosite globale (monte au-dessus de 1 pour eclaircir).
RELIEF = 0.45
AO_STRENGTH = 0.30
BRIGHTNESS = 1.0

# Shader fragment compatible OpenGL ES 2. Utilise les noms de varying/uniform
# par defaut de Kivy (frag_color, tex_coord0, texture0).
FS = """
#ifdef GL_ES
precision highp float;
#endif

varying vec4 frag_color;
varying vec2 tex_coord0;

uniform sampler2D texture0;     /* BaseColor (unite 0, liee par Kivy) */
uniform sampler2D pbr_normal;   /* Normal   (unite 1) */
uniform sampler2D pbr_packed;   /* Packed   (unite 2) : R = occlusion */
uniform vec3 pbr_light;
uniform float pbr_relief;
uniform float pbr_ao;
uniform float pbr_brightness;

void main(void) {
    vec4 base = frag_color * texture2D(texture0, tex_coord0);
    vec3 L = normalize(pbr_light);
    vec3 n = normalize(texture2D(pbr_normal, tex_coord0).xyz * 2.0 - 1.0);
    float diff = max(dot(n, L), 0.0);
    float ref = max(L.z, 0.001);                 /* eclairage d'une surface plate */
    /* Relief CENTRE sur 1.0 : une surface plate garde sa luminosite ; seules
       les bosses/creux varient autour. -> pas d'assombrissement global. */
    float lit = 1.0 + pbr_relief * (diff - ref);
    float ao = mix(1.0, texture2D(pbr_packed, tex_coord0).r, pbr_ao);
    lit = clamp(lit * ao * pbr_brightness, 0.0, 2.0);
    gl_FragColor = vec4(base.rgb * lit, base.a);
}
"""

_flat_normal = None
_flat_packed = None


def _flat(color):
    tex = Texture.create(size=(1, 1), colorfmt="rgba")
    tex.blit_buffer(bytes(color), colorfmt="rgba", bufferfmt="ubyte")
    tex.wrap = "repeat"
    return tex


def flat_normal():
    """Normale "plate" (pointe vers la camera) : pas de relief."""
    global _flat_normal
    if _flat_normal is None:
        _flat_normal = _flat((128, 128, 255, 255))     # (0,0,1)
    return _flat_normal


def flat_packed():
    """Packed neutre : occlusion = 1 (aucun assombrissement)."""
    global _flat_packed
    if _flat_packed is None:
        _flat_packed = _flat((255, 255, 255, 255))
    return _flat_packed


def setup(render_context):
    """Installe le shader + uniformes sur un RenderContext, et lie les cartes
    neutres par defaut. A appeler une fois (canvas du widget)."""
    render_context.shader.fs = FS
    render_context["pbr_normal"] = 1
    render_context["pbr_packed"] = 2
    render_context["pbr_light"] = [float(v) for v in LIGHT]
    render_context["pbr_relief"] = float(RELIEF)
    render_context["pbr_ao"] = float(AO_STRENGTH)
    render_context["pbr_brightness"] = float(BRIGHTNESS)


def bind_maps(normal_tex, packed_tex):
    """Lie Normal (unite 1) et Packed (unite 2). None -> carte neutre.
    A appeler DANS un bloc `with canvas` juste avant la surface texturee."""
    BindTexture(texture=normal_tex or flat_normal(), index=1)
    BindTexture(texture=packed_tex or flat_packed(), index=2)


def reset_maps():
    """Remet des cartes neutres (apres une surface texturee)."""
    BindTexture(texture=flat_normal(), index=1)
    BindTexture(texture=flat_packed(), index=2)
