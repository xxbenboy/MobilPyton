"""
Affichage d'un objet : son image (assets/items/<nom>.png) si elle existe,
sinon un "?" — avec le nom dessous (et le nombre si > 1).
"""
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.image import Image
from kivy.uix.label import Label

from src import items
from src.widgets.responsive import scale_font


class ItemIcon(BoxLayout):
    def __init__(self, name, count=1, **kwargs):
        super().__init__(orientation="vertical", **kwargs)
        path = items.image_path(name)
        if path:
            self.add_widget(Image(source=path, size_hint=(1, 0.72),
                                  allow_stretch=True, keep_ratio=True))
        else:
            self.add_widget(scale_font(Label(text="?", bold=True,
                            color=(0.9, 0.9, 0.95, 1), size_hint=(1, 0.72))))

        text = items.display_name(name)
        if count and count > 1:
            text += f"  x{count}"
        lbl = Label(text=text, halign="center", valign="middle",
                    color=(1, 1, 1, 1), size_hint=(1, 0.28))
        lbl.bind(size=lambda w, *_: setattr(w, "text_size", (w.width, w.height)))
        scale_font(lbl)
        self.add_widget(lbl)
