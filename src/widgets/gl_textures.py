"""Textures FABRIQUEES A LA MAIN, qui survivent a une perte de contexte.

POURQUOI CE MODULE EXISTE. Quand Android met le jeu en arriere-plan, il peut
detruire le contexte graphique : toutes les textures deposees sur la carte
graphique disparaissent. Kivy sait recharger celles qui viennent d'un FICHIER
-- il en connait le chemin, il le relit. Mais une texture construite a la main
(Texture.create + blit_buffer) n'a pas de fichier derriere elle : personne ne
sait plus ce qu'il y avait dedans, et elle revient vide.

Le jeu en fabrique a plusieurs endroits, et toutes vivent dans des caches de
module -- c'est-a-dire pour toute la duree du processus. Une fois videes, rien
ne les reconstruisait : il fallait fermer le jeu et le rouvrir. C'est
exactement le symptome qu'on nous a rapporte.

CE QU'ON FAIT : on garde les octets, et on s'abonne au rechargement. Kivy
appelle l'observateur quand le contexte revient, et la texture se remplit
toute seule.

Le prix est de garder les octets en memoire. C'est voulu : sans eux il n'y a
rien a recharger. Cela ne concerne qu'une poignee d'images (les silhouettes
des pepites, les tuiles de buche, deux pixels pour l'eclairage) -- pas les
grandes textures de sol, qui viennent de fichiers et se rechargent seules.
"""
from kivy.graphics.texture import Texture


def reveille_arbre(racine):
    """Remet d'aplomb un widget et toute sa descendance apres un reveil.

    Chaque widget qui a quelque chose a reconstruire expose `reveille()` ; les
    autres n'ont rien a faire. On redemande ensuite un rendu de leur canvas,
    ce qui est gratuit quand il n'y a rien a reparer.

    UN WIDGET QUI SE REVEILLE MAL NE DOIT PAS BLOQUER LES AUTRES : on est
    precisement au moment ou l'affichage est deja en mauvais etat, et laisser
    une exception remonter rendrait l'ecran definitivement noir -- le defaut
    qu'on cherche a corriger.

    C'est ici et non dans l'application parce que cela ne demande rien d'elle :
    juste un arbre de widgets. Et parce que cela se teste sans monter tout le
    jeu."""
    if racine is None:
        return
    pile = [racine]
    while pile:
        widget = pile.pop()
        pile.extend(getattr(widget, "children", ()))
        reveil = getattr(widget, "reveille", None)
        if callable(reveil):
            try:
                reveil()
            except Exception:
                pass
        canvas = getattr(widget, "canvas", None)
        if canvas is not None:
            try:
                canvas.ask_update()
            except Exception:
                pass


def texture_depuis_octets(size, data, colorfmt="rgba", wrap=None,
                          mag_filter=None, min_filter=None):
    """Une texture remplie avec `data`, qui se REREMPLIT apres coup.

    Meme signature d'usage que Texture.create + blit_buffer, avec les
    reglages courants en prime pour qu'ils soient reappliques eux aussi : un
    wrap perdu fait baver le bord oppose sur la silhouette."""
    octets = bytes(data)
    tex = Texture.create(size=size, colorfmt=colorfmt)

    def remplir(*_):
        tex.blit_buffer(octets, colorfmt=colorfmt, bufferfmt="ubyte")
        if wrap is not None:
            tex.wrap = wrap
        if mag_filter is not None:
            tex.mag_filter = mag_filter
        if min_filter is not None:
            tex.min_filter = min_filter

    remplir()
    # L'observateur garde une reference sur `tex` : la texture ne sera donc
    # pas liberee tant qu'il vit. Ici c'est sans consequence -- ces textures
    # sont dans des caches de module, elles vivent de toute facon jusqu'a la
    # fin du processus.
    try:
        tex.add_reload_observer(remplir)
    except Exception:
        # Un faux Kivy (les tests) n'a pas forcement ce mecanisme : la texture
        # reste utilisable, elle ne sait juste pas se recharger.
        pass
    return tex
