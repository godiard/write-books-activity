# Copyright (C) 2013, Gonzalo Odiard
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

import logging
import cairo
import StringIO
import dbus
import os

from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GdkPixbuf

from gettext import gettext as _

from jarabe.journal import model
from sugar3.graphics import style

DS_DBUS_SERVICE = 'org.laptop.sugar.DataStore'
DS_DBUS_INTERFACE = 'org.laptop.sugar.DataStore'
DS_DBUS_PATH = '/org/laptop/sugar/DataStore'

try:
    from sugar3.activity.activity import PREVIEW_SIZE
except:
    PREVIEW_SIZE = style.zoom(300), style.zoom(225)


class IconModel(GObject.GObject, Gtk.TreeModel, Gtk.TreeDragSource):
    __gtype_name__ = 'JournalIconModel'

    __gsignals__ = {
        'ready': (GObject.SignalFlags.RUN_FIRST, None, ([])),
        'progress': (GObject.SignalFlags.RUN_FIRST, None, ([])),
    }

    COLUMN_UID = 0
    COLUMN_TITLE = 1
    COLUMN_PREVIEW = 2

    _COLUMN_TYPES = {
        COLUMN_UID: str,
        COLUMN_TITLE: str,
        COLUMN_PREVIEW: str,
    }

    _PAGE_SIZE = 100

    def __init__(self, query):
        GObject.GObject.__init__(self)

        self._last_requested_index = None
        self._cached_row = None
        self._result_set = model.find(query, IconModel._PAGE_SIZE)
        self._temp_drag_file_path = None

        # HACK: The view will tell us that it is resizing so the model can
        # avoid hitting D-Bus and disk.
        self.view_is_resizing = False

        self._result_set.ready.connect(self.__result_set_ready_cb)
        self._result_set.progress.connect(self.__result_set_progress_cb)

    def __result_set_ready_cb(self, **kwargs):
        self.emit('ready')

    def __result_set_progress_cb(self, **kwargs):
        self.emit('progress')

    def setup(self):
        self._result_set.setup()

    def stop(self):
        self._result_set.stop()

    def get_metadata(self, path):
        return model.get(self[path][IconModel.COLUMN_UID])

    def do_get_n_columns(self):
        return len(IconModel._COLUMN_TYPES)

    def do_get_column_type(self, index):
        return IconModel._COLUMN_TYPES[index]

    def do_iter_n_children(self, iterator):
        if iterator is None:
            return self._result_set.length
        else:
            return 0

    def do_get_value(self, iterator, column):
        if self.view_is_resizing:
            return None

        index = iterator.user_data
        if index == self._last_requested_index:
            return self._cached_row[column]

        if index >= self._result_set.length:
            return None

        self._result_set.seek(index)
        metadata = self._result_set.read()

        self._last_requested_index = index
        self._cached_row = []
        self._cached_row.append(metadata['uid'])

        title = GObject.markup_escape_text(metadata.get('title',
                                           _('Untitled')))
        self._cached_row.append(title)

        preview_data = metadata.get('preview', '')

        if preview_data == '':
            if metadata['uid'].startswith('/'):
                image_path = metadata['uid']
                # check if there are a preview cached
                directory = os.path.dirname(image_path)
                basename = os.path.basename(image_path)
                preview_file_name = os.path.join(directory, '.Sugar-Metadata',
                                                 basename + '.preview')
                if os.path.exists(preview_file_name):
                    preview_data = open(preview_file_name).read()
                else:
                    # create the preview and save it
                    preview_width, preview_height = PREVIEW_SIZE
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
                        image_path, preview_width, preview_height)

                    preview_surface = cairo.ImageSurface(
                        cairo.FORMAT_ARGB32, preview_width, preview_height)

                    ctx = cairo.Context(preview_surface)
                    Gdk.cairo_set_source_pixbuf(ctx, pixbuf, 0, 0)
                    ctx.paint()

                    preview_str = StringIO.StringIO()
                    preview_surface.write_to_png(preview_str)
                    preview_data = preview_str.getvalue()
                    try:
                        metadata_dir = os.path.join(
                            directory, '.Sugar-Metadata')
                        if not os.path.exists(metadata_dir):
                            os.makedirs(metadata_dir)
                        with open(preview_file_name, 'w') as preview_file:
                            preview_file.write(preview_data)
                    except:
                        logging.error('Couldn\'t save preview cache in %s',
                                      preview_file_name)

        self._cached_row.append(dbus.ByteArray(preview_data))

        return self._cached_row[column]

    def do_iter_nth_child(self, parent_iter, n):
        return (False, None)

    def do_get_path(self, iterator):
        treepath = Gtk.TreePath((iterator.user_data,))
        return treepath

    def do_get_iter(self, path):
        idx = path.get_indices()[0]
        iterator = Gtk.TreeIter()
        iterator.user_data = idx
        return (True, iterator)

    def do_iter_next(self, iterator):
        idx = iterator.user_data + 1
        if idx >= self._result_set.length:
            iterator.stamp = -1
            return (False, iterator)
        else:
            iterator.user_data = idx
            return (True, iterator)

    def do_get_flags(self):
        return Gtk.TreeModelFlags.ITERS_PERSIST | Gtk.TreeModelFlags.LIST_ONLY

    def do_iter_children(self, iterator):
        return (False, iterator)

    def do_iter_has_child(self, iterator):
        return False

    def do_iter_parent(self, iterator):
        return (False, Gtk.TreeIter())
