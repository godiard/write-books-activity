# Copyright (C) 2007, One Laptop Per Child
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

from gettext import gettext as _
import logging

from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import Wnck

from sugar3.graphics import style
from sugar3.graphics.toolbutton import ToolButton
from sugar3.graphics.toolbarbox import ToolbarBox
from sugar3.graphics.icon import Icon
from sugar3.graphics import iconentry
from sugar3 import mime
from sugar3 import profile

from iconview import IconView

_AUTOSEARCH_TIMEOUT = 1000


class ImageFileChooser(Gtk.Window):

    __gsignals__ = {
        'response': (GObject.SignalFlags.RUN_FIRST, None, ([int])),
    }

    def __init__(self, path, title=None, parent=None, categories=None):
        """
            path (str) -- The path with the images to display
            title (str) -- A optional string to display in the main toolbar
            parent -- the widget calling ObjectChooser
            categories (dict) -- A dictionary with categories and path
                associated.
        """
        Gtk.Window.__init__(self)
        self.set_type_hint(Gdk.WindowTypeHint.DIALOG)
        self.set_decorated(False)
        self.set_position(Gtk.WindowPosition.CENTER_ALWAYS)
        self.set_border_width(style.LINE_WIDTH)
        self.set_has_resize_grip(False)

        self._selected_object_id = None

        self.add_events(Gdk.EventMask.VISIBILITY_NOTIFY_MASK)
        self.connect('visibility-notify-event',
                     self.__visibility_notify_event_cb)
        self.connect('delete-event', self.__delete_event_cb)
        self.connect('key-press-event', self.__key_press_event_cb)

        if parent is None:
            logging.warning('ObjectChooser: No parent window specified')
        else:
            self.connect('realize', self.__realize_cb, parent)

            screen = Wnck.Screen.get_default()
            screen.connect('window-closed', self.__window_closed_cb, parent)

        self._vbox = Gtk.VBox()
        self.add(self._vbox)
        self._vbox.show()

        title_box = TitleBox(title)
        title_box.close_button.connect('clicked',
                                       self.__close_button_clicked_cb)
        title_box.set_size_request(-1, style.GRID_CELL_SIZE)
        self._vbox.pack_start(title_box, False, True, 0)
        title_box.show()
        title_box.journal_button.connect('clicked',
                                         self.__journal_button_clicked_cb)

        separator = Gtk.HSeparator()
        self._vbox.pack_start(separator, False, True, 0)
        separator.show()

        self._main_path = path
        self._toolbar = SearchToolbox(path, add_back_button=True)
        self._toolbar.connect('query-changed', self.__query_changed_cb)
        self._toolbar.connect('go-back', self.__go_back_cb)
        self._toolbar.set_size_request(-1, style.GRID_CELL_SIZE)
        self._toolbar.show()
        self._vbox.pack_start(self._toolbar, False, True, 0)

        width = Gdk.Screen.width() - style.GRID_CELL_SIZE * 2
        height = Gdk.Screen.height() - style.GRID_CELL_SIZE * 2
        self.set_size_request(width, height)

        self._icon_view = None
        self._buttons_vbox = None
        self._categories = categories
        if categories is None:
            self.show_icon_view(path)
        else:
            self.show_categories_buttons()

    def show_categories_buttons(self):
        if self._icon_view is not None:
            self._vbox.remove(self._icon_view)
            self._icon_view = None
        if self._buttons_vbox is not None:
            self._vbox.remove(self._buttons_vbox)

        # if categories are defined, show a list of buttons
        # with the categories, when the user press a button,
        # load the images in the catgories patch
        self._buttons_vbox = Gtk.VBox()
        for category in self._categories.keys():
            button = Gtk.Button(category)
            button.connect('clicked', self.__category_btn_clicked_cb,
                           self._categories[category])
            self._buttons_vbox.pack_start(button, False, False, 10)
        self._buttons_vbox.show_all()
        self._vbox.pack_start(self._buttons_vbox, True, True, 0)

    def __category_btn_clicked_cb(self, button, category_path):
        self.show_icon_view(category_path)

    def show_icon_view(self, path):
        self._vbox.remove(self._buttons_vbox)
        self._toolbar.set_path(path)
        self._icon_view = IconView(self._toolbar)
        self._icon_view.connect('entry-activated',
                                self.__entry_activated_cb)
        self._icon_view.connect('clear-clicked', self.__clear_clicked_cb)
        self._vbox.pack_start(self._icon_view, True, True, 0)
        self._icon_view.show()
        self._icon_view.update_with_query(self._toolbar.get_query())
        self._toolbar.show()

    def __go_back_cb(self, toolbar):
        self.show_categories_buttons()

    def __realize_cb(self, chooser, parent):
        self.get_window().set_transient_for(parent)
        # TODO: Should we disconnect the signal here?

    def __window_closed_cb(self, screen, window, parent):
        if window.get_xid() == parent.get_xid():
            self.destroy()

    def __journal_button_clicked_cb(self, button):
        # use reject to signal open the objectchooser
        self.emit('response', Gtk.ResponseType.REJECT)

    def __entry_activated_cb(self, list_view, uid):
        self._selected_object_id = uid
        self.emit('response', Gtk.ResponseType.ACCEPT)

    def __delete_event_cb(self, chooser, event):
        self.emit('response', Gtk.ResponseType.DELETE_EVENT)

    def __key_press_event_cb(self, widget, event):
        keyname = Gdk.keyval_name(event.keyval)
        if keyname == 'Escape':
            self.emit('response', Gtk.ResponseType.DELETE_EVENT)

    def __close_button_clicked_cb(self, button):
        self.emit('response', Gtk.ResponseType.DELETE_EVENT)

    def get_selected_object_id(self):
        return self._selected_object_id

    def __query_changed_cb(self, toolbar, query):
        if len(query['query']) < 3:
            logging.error('Don\'t query with a filter of less than 3 letters'
                          'to avoid big querys, slow in the XO-1')
            return
        if self._icon_view is None:
            self.show_icon_view(self._main_path)
        self._icon_view.update_with_query(query)

    def __volume_changed_cb(self, volume_toolbar, mount_point):
        logging.debug('Selected volume: %r.', mount_point)
        self._toolbar.set_mount_point(mount_point)

    def __visibility_notify_event_cb(self, window, event):
        logging.debug('visibility_notify_event_cb %r', self)
        visible = event.get_state() == Gdk.VisibilityState.FULLY_OBSCURED
        self._icon_view.set_is_visible(visible)

    def __clear_clicked_cb(self, list_view):
        self._toolbar.clear_query()


class TitleBox(Gtk.Toolbar):

    def __init__(self, title=None):
        Gtk.Toolbar.__init__(self)

        self.journal_button = ToolButton()
        icon = Icon(icon_name='activity-journal', xo_color=profile.get_color())
        self.journal_button.set_icon_widget(icon)
        self.journal_button.set_tooltip(_('Select from the Journal'))
        self.insert(self.journal_button, -1)
        self.journal_button.show_all()

        label = Gtk.Label()
        if title is None:
            title = _('Choose an image')
        label.set_markup('<b>%s</b>' % title)
        label.set_alignment(0, 0.5)
        label.set_margin_left(10)
        self._add_widget(label, expand=True)

        self.close_button = ToolButton(icon_name='dialog-cancel')
        self.close_button.set_tooltip(_('Close'))
        self.insert(self.close_button, -1)
        self.close_button.show()

    def _add_widget(self, widget, expand=False):
        tool_item = Gtk.ToolItem()
        tool_item.set_expand(expand)

        tool_item.add(widget)
        widget.show()

        self.insert(tool_item, -1)
        tool_item.show()


class SearchToolbox(ToolbarBox):

    __gsignals__ = {
        'query-changed': (GObject.SignalFlags.RUN_FIRST, None, ([object])),
        'go-back': (GObject.SignalFlags.RUN_FIRST, None, ([])),
    }

    def __init__(self, path, add_back_button=False):
        ToolbarBox.__init__(self)
        self._path = path
        self.search_entry = iconentry.IconEntry()
        try:
            self.search_entry.set_icon_from_name(iconentry.ICON_ENTRY_PRIMARY,
                                                 'entry-search')
        except:
            pass

        text = _('Search')
        self.search_entry.set_placeholder_text(text)
        self.search_entry.connect('activate', self._search_entry_activated_cb)
        self.search_entry.connect('changed', self._search_entry_changed_cb)
        self.search_entry.add_clear_button()
        self._autosearch_timer = None
        self._add_widget(self.search_entry, expand=True)

        if add_back_button:
            back_button = ToolButton(icon_name='go-previous')
            back_button.set_tooltip(_('Back'))
            self._add_widget(back_button, expand=False)
            back_button.connect('clicked', self.__back_button_clicked_cb)
            back_button.show()

        self._query = self._build_query()

    def __back_button_clicked_cb(self, button):
        self.emit('go-back')

    def _add_widget(self, widget, expand=False):
        tool_item = Gtk.ToolItem()
        tool_item.set_expand(expand)

        tool_item.add(widget)
        widget.show()

        self.toolbar.insert(tool_item, -1)
        tool_item.show()

    def get_query(self):
        return self._query

    def set_path(self, path):
        self._path = path
        self._query = self._build_query()
        self._update_if_needed()

    def _build_query(self):
        query = {}
        query['mountpoints'] = [self._path]

        generic_type = mime.get_generic_type('Image')
        mime_types = generic_type.mime_types
        query['mime_type'] = mime_types

        if self.search_entry.props.text:
            text = self.search_entry.props.text.strip()
            if text:
                query['query'] = text
        return query

    def _search_entry_activated_cb(self, search_entry):
        if self._autosearch_timer:
            GObject.source_remove(self._autosearch_timer)
        self._update_if_needed()

    def _update_if_needed(self):
        new_query = self._build_query()
        if self._query != new_query:
            self._query = new_query
            self.emit('query-changed', self._query)

    def _search_entry_changed_cb(self, search_entry):
        if not search_entry.props.text:
            search_entry.activate()
            return

        if self._autosearch_timer:
            GObject.source_remove(self._autosearch_timer)
        self._autosearch_timer = GObject.timeout_add(_AUTOSEARCH_TIMEOUT,
                                                     self._autosearch_timer_cb)

    def _autosearch_timer_cb(self):
        logging.debug('_autosearch_timer_cb')
        self._autosearch_timer = None
        self.search_entry.activate()
        return False

    def clear_query(self):
        self.search_entry.props.text = ''
