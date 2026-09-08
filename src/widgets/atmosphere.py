"""
IMAGES DU CIEL (soleil, lune).

Le dossier assets/Atmospheres/ etait RESERVE : y deposer une image ne faisait
rien. Ce module le branche.

Comme pour le decor, les images sont FACULTATIVES : sans elles, le ciel garde
ses disques dessines au canvas. Avec elles, le soleil et la lune prennent leur
vrai visage.

La LUNE est un cas a part. Elle n'est pas dessinee comme un disque mais comme
un maillage limite a sa portion ECLAIREE (c'est ce qui donne les croissants et
les quartiers). L'image n'est donc pas posee par-dessus : elle est plaquee SUR
ce maillage, et se trouve donc decoupee par la phase. Un croissant montre le
bon morceau de la vraie lune, pas une image entiere rognee au hasard.
"""
import os

from kivy.core.image import Image as CoreImage

_HERE = os.path.dirname(os.path.abspath(__file__))
ATMOSPHERE_DIR = os.path.abspath(os.path.join(_HERE, "..", "..", "assets",
                                              "Atmospheres"))

_EXTS = (".png", ".jpg", ".jpeg")
_CACHE = {}


def sprite(name):
    """Image du ciel portant ce nom (sun, moon...), ou None si absente."""
    if name not in _CACHE:
        tex = None
        for ext in _EXTS:
            path = os.path.join(ATMOSPHERE_DIR, name + ext)
            if os.path.isfile(path):
                try:
                    tex = CoreImage(path).texture
                    tex.wrap = "clamp_to_edge"
                except Exception:
                    tex = None
                break
        _CACHE[name] = tex
    return _CACHE[name]
