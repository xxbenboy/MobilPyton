"""
LE FLOU DU DECOR : une image floue de ce que montre un widget, pour faire
une PROFONDEUR DE CHAMP (le sol derriere le plan de travail, dans la vue
d'assemblage).

On rend le widget dans une image a moitie taille, puis on la reduit de
moitie en moitie : chaque reduction, en filtrage lineaire, fait la moyenne
de quatre pixels. A 1/16 de la taille, agrandie en filtrage lineaire, c'est
un flou doux -- calcule UNE fois, pas a chaque image.

Rend (texture, fbos) -- les fbos doivent rester en vie tant que la texture
sert -- ou None si la carte graphique ne s'y prete pas.
"""
from kivy.graphics import (Color, Rectangle, Scale, Translate, Fbo,
                           ClearColor, ClearBuffers)

# Taille finale, en part de la taille du widget.
REDUCTION = 16


def floute(widget, reduction=REDUCTION):
    if widget.width < 8 or widget.height < 8:
        return None
    parent = widget.parent.canvas if widget.parent is not None else None
    rang = -1
    try:
        if parent is not None:
            rang = parent.indexof(widget.canvas)
            if rang > -1:
                parent.remove(widget.canvas)
        w, h = max(4, int(widget.width / 2)), max(4, int(widget.height / 2))
        fbo = Fbo(size=(w, h), with_stencilbuffer=True)
        with fbo:
            ClearColor(0, 0, 0, 0)
            ClearBuffers()
            Scale(w / float(widget.width), h / float(widget.height), 1)
            Translate(-widget.x, -widget.y, 0)
        fbo.add(widget.canvas)
        fbo.draw()
        fbo.remove(widget.canvas)
    except Exception:
        return None
    finally:
        if parent is not None and rang > -1:
            parent.insert(rang, widget.canvas)
    fbos = [fbo]
    tex = fbo.texture
    cible = widget.width / float(reduction)
    try:
        while w > cible:
            w, h = max(4, w // 2), max(4, h // 2)
            tex.min_filter = "linear"
            tex.mag_filter = "linear"
            f = Fbo(size=(w, h))
            with f:
                ClearColor(0, 0, 0, 0)
                ClearBuffers()
                Color(1, 1, 1, 1)
                Rectangle(texture=tex, pos=(0, 0), size=(w, h))
            f.draw()
            fbos.append(f)
            tex = f.texture
        tex.mag_filter = "linear"
    except Exception:
        return None
    return tex, fbos


__all__ = ["floute", "REDUCTION"]
