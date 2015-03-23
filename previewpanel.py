# Copyright 2015 Gonzalo Odiard
#

from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository.GdkPixbuf import Pixbuf

from imagecanvas import ImageCanvas

MAX_TEXT_SIZE = 25


class PreviewPanel(Gtk.VBox):

    __gsignals__ = {
        'pages-modified': (GObject.SignalFlags.RUN_FIRST, None, ([object])),
    }

    def __init__(self, pages):
        Gtk.VBox.__init__(self)
        self._pages = pages
        scrolled = Gtk.ScrolledWindow()
        self._width = Gdk.Screen.width() / 4
        self._icon_view = Gtk.IconView()
        self._icon_view.set_reorderable(True)
        self._icon_view.set_spacing(0)
        self._icon_view.set_row_spacing(0)
        self._icon_view.set_column_spacing(0)
        self._icon_view.set_margin(0)
        # TODO: No logic here.... set a bigger item size
        # display a very width item
        self._icon_view.set_item_width(self._width / 2)
        self.add(scrolled)
        scrolled.add(self._icon_view)
        self.set_size_request(self._width, -1)
        self.show_all()

    def update_model(self, pages):
        liststore = Gtk.ListStore(Pixbuf, str)
        self._icon_view.set_model(liststore)
        self._icon_view.set_pixbuf_column(0)
        self._icon_view.set_text_column(1)
        image_renderer = ImageCanvas()
        icon_width = self._width - 50
        icon_height = int(icon_width * 3 / 4.)
        for page in pages:
            text = page.text
            text = text.replace('\n', '')
            if len(text) > MAX_TEXT_SIZE:
                text = text[0:MAX_TEXT_SIZE - 3] + '...'
            pixbuf = image_renderer.create_pixbuf(
                icon_width, icon_height, page.background_path, page.images)
            liststore.append([pixbuf, text])
