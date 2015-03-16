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

import os
import time
from gettext import gettext as _

from gi.repository import Gtk
from gi.repository import GObject
from gi.repository import Pango

from sugar3.activity import activity
from sugar3.activity.widgets import StopButton
from sugar3.activity.widgets import ActivityToolbarButton
from sugar3.activity.widgets import EditToolbar
from sugar3.graphics.toolbarbox import ToolbarBox
from sugar3.graphics.toolbarbox import ToolbarButton
from sugar3.graphics.toolbutton import ToolButton
from sugar3.graphics import style
from sugar3.datastore import datastore

from imagecanvas import ImageCanvas
from objectchooser import ImageFileChooser
from bookmodel import BookModel

# TODO: get the real scratch path
SCRATCH_PATH = '/home/olpc/Activities/Scratch.activity'
if not os.path.exists(SCRATCH_PATH):
    # this is only for development
    SCRATCH_PATH = \
        '/home/gonzalo/sugar-devel/scratch/scratchonlinux/trunk/scratch'
SCRATCH_BACKGROUNDS_PATH = SCRATCH_PATH + '/Media/Backgrounds'


class WriteBooksActivity(activity.Activity):

    def __init__(self, handle):
        activity.Activity.__init__(self, handle)

        self._book_model = BookModel()
        self._actual_page = 1

        # we do not have collaboration features
        # make the share option insensitive
        self.max_participants = 1

        toolbar_box = ToolbarBox()

        activity_button = ActivityToolbarButton(self)
        toolbar_box.toolbar.insert(activity_button, 0)

        self._edit_toolbar = EditToolbar()
        edit_toolbar_button = ToolbarButton(
            page=self._edit_toolbar, icon_name='toolbar-edit')
        toolbar_box.toolbar.insert(edit_toolbar_button, 1)

        set_background_button = ToolButton('set-background')
        set_background_button.set_tooltip(_('Set the background'))
        set_background_button.connect('clicked',
                                      self.__set_background_clicked_cb)
        toolbar_box.toolbar.insert(set_background_button, -1)

        insert_picture_button = ToolButton('insert-picture')
        insert_picture_button.set_tooltip(_('Add a picture'))
        toolbar_box.toolbar.insert(insert_picture_button, -1)

        rotate_left_button = ToolButton('object_rotate_left')
        rotate_left_button.set_tooltip(_('Rotate anticlockwise'))
        toolbar_box.toolbar.insert(rotate_left_button, -1)

        rotate_right_button = ToolButton('object_rotate_right')
        rotate_right_button.set_tooltip(_('Rotate clockwise'))
        toolbar_box.toolbar.insert(rotate_right_button, -1)

        mirror_horizontal_button = ToolButton('mirror-horizontal')
        mirror_horizontal_button.set_tooltip(_('Horizontal mirror'))
        toolbar_box.toolbar.insert(mirror_horizontal_button, -1)

        mirror_vertical_button = ToolButton('mirror-vertical')
        mirror_vertical_button.set_tooltip(_('Vertical mirror'))
        toolbar_box.toolbar.insert(mirror_vertical_button, -1)

        toolbar_box.toolbar.insert(Gtk.SeparatorToolItem(), -1)

        self._add_page_button = ToolButton('list-add')
        self._add_page_button.set_tooltip(_('Add a page'))
        self._add_page_button.connect('clicked', self.__add_page_clicked_cb)
        toolbar_box.toolbar.insert(self._add_page_button, -1)

        self._prev_page_button = ToolButton('go-previous-paired')
        self._prev_page_button.set_tooltip(_('Previous page'))
        self._prev_page_button.connect('clicked', self.__prev_page_clicked_cb)
        toolbar_box.toolbar.insert(self._prev_page_button, -1)

        self._next_page_button = ToolButton('go-next-paired')
        self._next_page_button.set_tooltip(_('Next page'))
        self._next_page_button.connect('clicked', self.__next_page_clicked_cb)
        toolbar_box.toolbar.insert(self._next_page_button, -1)

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
        self._image_canvas.set_valign(Gtk.Align.CENTER)
        self._image_canvas.set_vexpand(True)

        self._text_editor = TextEditor()
        self._text_changed_signal_id = self._text_editor.connect(
            'changed', self.__text_changed_cb)

        self._page_counter_label = Gtk.Label('1 / 1')
        font_desc = Pango.font_description_from_string('12')
        self._page_counter_label.modify_font(font_desc)
        self._page_counter_label.set_halign(Gtk.Align.END)
        self._page_counter_label.set_valign(Gtk.Align.END)
        self._page_counter_label.set_margin_right(style.DEFAULT_PADDING)
        self._page_counter_label.set_margin_top(style.DEFAULT_PADDING)

        background = Gtk.EventBox()

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.pack_start(self._page_counter_label, False, False, 0)
        box.pack_start(self._image_canvas, True, True, 0)
        box.pack_start(self._text_editor, False, False, style.DEFAULT_PADDING)
        background.add(box)

        self.set_canvas(background)
        self._update_page_buttons()

        self.show_all()

    def write_file(self, file_path):
        self._book_model.write(file_path)

    def read_file(self, file_path):
        self._book_model.read(file_path)
        self._update_page_buttons()

    def __set_background_clicked_cb(self, button):
        chooser = ImageFileChooser(path=SCRATCH_BACKGROUNDS_PATH,
                                   title=_('Select a background'))
        chooser.connect('response', self.__set_backgroud_chooser_response_cb)
        chooser.show()

    def __set_backgroud_chooser_response_cb(self, chooser, response_id):
        if response_id == Gtk.ResponseType.ACCEPT:
            jobject = datastore.get(chooser.get_selected_object_id())
            if jobject and jobject.file_path:
                tempfile_name = \
                    os.path.join(self.get_activity_root(),
                                 'instance', 'tmp%i' % time.time())
                os.link(jobject.file_path, tempfile_name)
                self._image_canvas.set_background(tempfile_name)
                self._book_model.set_page_background(self._actual_page,
                                                     tempfile_name)
        chooser.destroy()
        del chooser

    def _update_page_buttons(self):
        cant_pages = len(self._book_model.get_pages())
        self._page_counter_label.set_text('%d / %d' %
                                          (self._actual_page, cant_pages))
        self._prev_page_button.set_sensitive(self._actual_page > 1)
        self._next_page_button.set_sensitive(self._actual_page < cant_pages)
        self._update_page()

    def _update_page(self):
        page_model = self._book_model.get_page_model(self._actual_page)
        self._image_canvas.set_background(page_model.background_path)
        GObject.signal_handler_block(
            self._text_editor, self._text_changed_signal_id)
        self._text_editor.set_text(page_model.text)
        GObject.signal_handler_unblock(
            self._text_editor, self._text_changed_signal_id)

    def __add_page_clicked_cb(self, button):
        self._book_model.add_page()
        self._update_page_buttons()

    def __next_page_clicked_cb(self, button):
        self._actual_page += 1
        self._update_page_buttons()

    def __prev_page_clicked_cb(self, button):
        self._actual_page -= 1
        self._update_page_buttons()

    def __text_changed_cb(self, texteditor):
        self._book_model.set_page_text(self._actual_page,
                                       texteditor.get_text())


class TextEditor(Gtk.TextView):

    __gsignals__ = {
        'changed': (GObject.SignalFlags.RUN_FIRST, None, ([])),
    }

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
        self.get_buffer().connect('changed', self.__buffer_changed_cb)

    def __buffer_changed_cb(self, text_buffer):
        self.emit('changed')

    def get_text(self):
        return self.get_buffer().get_text(self.get_buffer().get_start_iter(),
                                          self.get_buffer().get_end_iter(),
                                          False)

    def set_text(self, text):
        self.get_buffer().set_text(text)
