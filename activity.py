# Copyright 2015 Gonzalo Odiard
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin St, Fifth Floor, Boston, MA  02110-1301  USA

"""WriteBooks Activity: A tool to write simple books."""

from gi.repository import Gtk
from gi.repository import Pango

from sugar3.activity import activity
from sugar3.graphics.toolbarbox import ToolbarBox
from sugar3.activity.widgets import ActivityToolbarButton
from sugar3.activity.widgets import StopButton
from sugar3.graphics import style

from imagecanvas import ImageCanvas


class WriteBooksActivity(activity.Activity):

    def __init__(self, handle):
        activity.Activity.__init__(self, handle)

        # we do not have collaboration features
        # make the share option insensitive
        self.max_participants = 1

        toolbar_box = ToolbarBox()

        activity_button = ActivityToolbarButton(self)
        toolbar_box.toolbar.insert(activity_button, 0)

        separator = Gtk.SeparatorToolItem()
        separator.props.draw = False
        separator.set_expand(True)
        toolbar_box.toolbar.insert(separator, -1)

        stop_button = StopButton(self)
        toolbar_box.toolbar.insert(stop_button, -1)

        self.set_toolbar_box(toolbar_box)
        toolbar_box.show_all()

        self._image_canvas = ImageCanvas()
        self._image_canvas.set_halign(Gtk.Align.CENTER)

        self._text_editor = TextEditor()

        background = Gtk.EventBox()

        vbox = Gtk.VBox()
        vbox.pack_start(self._image_canvas, True, True, 10)
        vbox.pack_start(self._text_editor, False, False, 10)

        background.add(vbox)
        self.set_canvas(background)

        self.show_all()


class TextEditor(Gtk.TextView):

    def __init__(self):
        Gtk.TextView.__init__(self)

        self.set_wrap_mode(Gtk.WrapMode.WORD)
        self.set_pixels_above_lines(0)
        self.set_margin_left(style.GRID_CELL_SIZE)
        self.set_margin_right(style.GRID_CELL_SIZE)
        self.set_margin_bottom(style.DEFAULT_PADDING)
        self.set_size_request(-1, style.GRID_CELL_SIZE * 1.5)

        font_desc = Pango.font_description_from_string('14')
        self.modify_font(font_desc)
