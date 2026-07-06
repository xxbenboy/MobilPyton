"""
Affichage d'un objet : son image (assets/items/<nom>.png) si elle existe,
sinon un "?" — avec le nom dessous (et le nombre si > 1).

`show_name=False` : n'affiche QUE l'image (ou le "?"), sans le nom dessous.
Utile quand le nom est deja ecrit a cote (ex. liste des recettes de craft).
"""
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.label import Label

from src import items
from src.widgets.responsive import scale_font


class ItemIcon(BoxLayout):
    def __init__(self, name, count=1, show_name=True, **kwargs):
        super().__init__(orientation="vertical", **kwargs)
        icon_h = 0.72 if show_name else 1.0
        path = items.image_path(name)
        if path:
            self.add_widget(Image(source=path, size_hint=(1, icon_h),
                                  allow_stretch=True, keep_ratio=True))
        else:
            self.add_widget(scale_font(Label(text="?", bold=True,
                            color=(0.9, 0.9, 0.95, 1), size_hint=(1, icon_h))))

        if not show_name:
            return

        text = items.display_name(name)
        if count and count > 1:
            text += f"  x{count}"
        lbl = Label(text=text, halign="center", valign="middle",
                    color=(1, 1, 1, 1), size_hint=(1, 0.28))

        def _fit_name(*_):
            """Reduit la police pour que TOUT le nom tienne dans la boite, meme
            sur 2 lignes : un nom long n'est plus coupe (il retrecit au besoin)."""
            if lbl.width <= 1 or lbl.height <= 1:
                return
            # Retour a la ligne autorise dans la largeur dispo...
            lbl.text_size = (lbl.width, None)
            f = lbl.height * 0.72
            lbl.font_size = f
            lbl.texture_update()
            # ...puis on reduit si le texte (eventuellement sur 2 lignes) depasse
            # la hauteur.
            if lbl.texture_size[1] > lbl.height:
                lbl.font_size = max(8, f * lbl.height / lbl.texture_size[1])
            lbl.text_size = (lbl.width, lbl.height)

        lbl.bind(size=_fit_name, text=_fit_name)
        _fit_name()
        self.add_widget(lbl)
