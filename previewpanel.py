# Copyright 2015 Gonzalo Odiard
#

from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Gdk


class PreviewPanel(Gtk.VBox):

    __gsignals__ = {
        'pages-modified': (GObject.SignalFlags.RUN_FIRST, None, ([object])),
    }

    def __init__(self, pages):
        Gtk.VBox.__init__(self)
        self._pages = pages
        scrolled = Gtk.ScrolledWindow()
        self._icon_view = Gtk.IconView()
        self.add(scrolled)
        scrolled.add(self._icon_view)
        self.set_size_request(Gdk.Screen.width() / 5, -1)
        self.show_all()
