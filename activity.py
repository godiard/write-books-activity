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
import shutil
from gettext import gettext as _
import logging

from gi.repository import Gtk
from gi.repository import GtkSource
from gi.repository import Gdk
from gi.repository import GObject
from gi.repository import Pango

from sugar3.activity import activity
from sugar3.activity.widgets import StopButton
from sugar3.activity.widgets import ActivityToolbarButton
from sugar3.activity.widgets import EditToolbar
from sugar3.graphics.toolbarbox import ToolbarBox
from sugar3.graphics.toolbarbox import ToolbarButton
from sugar3.graphics.toolbutton import ToolButton
from sugar3.graphics.toggletoolbutton import ToggleToolButton
from sugar3.graphics.alert import ConfirmationAlert
from sugar3.graphics.alert import Alert
from sugar3.graphics.icon import Icon
from sugar3.graphics import style
from sugar3.graphics.objectchooser import ObjectChooser
try:
    from sugar3.graphics.objectchooser import FILTER_TYPE_GENERIC_MIME
except:
    FILTER_TYPE_GENERIC_MIME = 'generic_mime'
from sugar3 import profile
from sugar3 import mime
from sugar3.datastore import datastore

from imagecanvas import ImageCanvas
from imagechooser import ImageFileChooser
from bookmodel import BookModel
from previewpanel import PreviewPanel
from epubfactory import create_ebub_from_book_model

# TODO: get the real scratch path
SCRATCH_PATH = '/home/olpc/Activities/Scratch.activity'
if not os.path.exists(SCRATCH_PATH):
    # this is only for development
    SCRATCH_PATH = \
        '/home/gonzalo/sugar-devel/scratch/scratchonlinux/trunk/scratch'
SCRATCH_BACKGROUNDS_PATH = SCRATCH_PATH + '/Media/Backgrounds'

SCRATCH_COSTUMES_PATH = SCRATCH_PATH + '/Media/Costumes'

TUXPAINT_STAMPS_PATH = '/usr/share/tuxpaint/stamps'


class WriteBooksActivity(activity.Activity):

    def __init__(self, handle):
        activity.Activity.__init__(self, handle)

        self._book_model = BookModel()
        self._actual_page = 1

        # we do not have collaboration features
        # make the share option insensitive
        self.max_participants = 1

        # get the language configured by the user
        # will be used to translate the names of the media files
        locale = os.environ.get('LANG', '')
        language_location = locale.split('.', 1)[0].lower()
        self._language = language_location.split('_')[0]
        if self._language == 'en':
            # we don't need translate the file names if langauage is 'en'
            self._language = None
        self._translations = None
        if self._language is not None:
            # read the translations file if available
            dict_path = os.path.join(activity.get_bundle_path(), 'data',
                                     "%s_dict.csv" % self._language)
            logging.debug('Looking for media translation dictionary %s',
                          dict_path)
            if os.path.exists(dict_path):
                logging.debug('Loading translations')
                self._translations = {}
                with open(dict_path) as dict_file:
                    for line in dict_file:
                        words = line.split(',')
                        self._translations[words[0]] = words[1].strip()

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
        insert_picture_button.connect('clicked',
                                      self.__add_image_clicked_cb)
        toolbar_box.toolbar.insert(insert_picture_button, -1)

        toolbar_box.toolbar.insert(Gtk.SeparatorToolItem(), -1)

        self._duplicate_page_button = ToolButton()
        icon = Icon(icon_name='edit-duplicate', xo_color=profile.get_color())
        self._duplicate_page_button.set_icon_widget(icon)

        self._duplicate_page_button.set_tooltip(_('Duplicate page'))
        self._duplicate_page_button.connect(
            'clicked', self.__duplicate_page_clicked_cb)
        toolbar_box.toolbar.insert(self._duplicate_page_button, -1)

        self._add_page_button = ToolButton('list-add')
        self._add_page_button.set_tooltip(_('Add a page'))
        self._add_page_button.connect('clicked', self.__add_page_clicked_cb)
        toolbar_box.toolbar.insert(self._add_page_button, -1)

        self._remove_button = ToolButton('edit-delete')
        self._remove_button.set_tooltip(_('Remove a image or page'))
        self._remove_button.connect('clicked', self.__remove_clicked_cb)
        toolbar_box.toolbar.insert(self._remove_button, -1)

        self._prev_page_button = ToolButton('go-previous-paired')
        self._prev_page_button.set_tooltip(_('Previous page'))
        self._prev_page_button.connect('clicked', self.__prev_page_clicked_cb)
        toolbar_box.toolbar.insert(self._prev_page_button, -1)

        self._next_page_button = ToolButton('go-next-paired')
        self._next_page_button.set_tooltip(_('Next page'))
        self._next_page_button.connect('clicked', self.__next_page_clicked_cb)
        toolbar_box.toolbar.insert(self._next_page_button, -1)

        self._view_list_button = ToggleToolButton('view-list')
        self._view_list_button.set_tooltip(_('View pages'))
        self._view_list_button.connect('toggled', self.__view_list_toggled_cb)
        toolbar_box.toolbar.insert(self._view_list_button, -1)

        separator = Gtk.SeparatorToolItem()
        separator.props.draw = False
        separator.set_expand(True)
        toolbar_box.toolbar.insert(separator, -1)

        stop_button = StopButton(self)
        toolbar_box.toolbar.insert(stop_button, -1)

        # add export buttons
        activity_toolbar = activity_button.props.page
        epub_button = ToolButton('save-as-epub')
        epub_button.set_tooltip(_('Save as EPUB book'))
        epub_button.connect('clicked', self.__save_ebook_clicked_cb)
        activity_toolbar.insert(epub_button, -1)
        epub_button.show()

        self.set_toolbar_box(toolbar_box)
        toolbar_box.show_all()

        edition_canvas = self.create_edition_canvas()

        hbox = Gtk.HBox()
        self._preview_panel = PreviewPanel(self._book_model.get_pages())
        self._preview_panel.connect('page-activated', self.__page_activated_cb)
        self._preview_panel.connect('page-moved', self.__page_moved_cb)
        hbox.pack_start(self._preview_panel, False, False, 0)
        hbox.pack_start(edition_canvas, True, True, 0)

        self.set_canvas(hbox)
        self.prepare_edit_toolbar()
        self._update_page_buttons()

        self.show_all()
        self._preview_panel.hide()

    def create_edition_canvas(self):
        self._image_canvas = ImageCanvas()
        self._image_canvas.connect('images-modified',
                                   self.__images_modified_cb)
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
        rgba = Gdk.RGBA()
        rgba.red, rgba.green, rgba.blue, rgba.alpha = 1., 1., 1., 1.
        background.override_background_color(Gtk.StateFlags.NORMAL, rgba)

        self._scrolled_window = Gtk.ScrolledWindow()
        self._scrolled_window.set_shadow_type(Gtk.ShadowType.ETCHED_IN)
        self._scrolled_window.set_size_request(
            Gdk.Screen.width() - style.GRID_CELL_SIZE * 2,
            style.GRID_CELL_SIZE * 2)
        self._scrolled_window.set_policy(Gtk.PolicyType.NEVER,
                                         Gtk.PolicyType.AUTOMATIC)
        self._scrolled_window.add(self._text_editor)
        self._scrolled_window.set_margin_left(style.GRID_CELL_SIZE)
        self._scrolled_window.set_margin_right(style.GRID_CELL_SIZE)

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.pack_start(self._page_counter_label, False, False, 0)
        box.pack_start(self._image_canvas, True, True, 0)
        box.pack_start(self._scrolled_window, False, False,
                       style.DEFAULT_PADDING)
        background.add(box)
        background.show_all()
        background.connect('size_allocate', self.__background_size_allocate_cb)
        return background

    def __background_size_allocate_cb(self, widget, allocation):
        height = allocation.height / 4 * 3
        width = height / 3 * 4
        logging.debug('size allocate %s x %s', width, height)
        self._image_canvas.set_size_request(width, height)
        widget.check_resize()

    def __view_list_toggled_cb(self, button):
        if button.get_active():
            self._preview_panel.update_model(self._book_model.get_pages())
            self._preview_panel.show()
            self._image_canvas.set_editable(False)
            self._text_editor.set_editable(False)
            self._scrolled_window.set_size_request(
                (Gdk.Screen.width() * 3 / 4) - style.GRID_CELL_SIZE * 2,
                style.GRID_CELL_SIZE * 2)
        else:
            self._preview_panel.hide()
            self._image_canvas.set_editable(True)
            self._text_editor.set_editable(True)
            self._scrolled_window.set_size_request(
                Gdk.Screen.width() - style.GRID_CELL_SIZE * 2,
                style.GRID_CELL_SIZE * 2)

    def write_file(self, file_path):
        self._book_model.write(file_path)
        self.metadata['mime_type'] = 'application/x-writebooks-activity'

    def read_file(self, file_path):
        self._book_model.read(file_path)
        self._update_page_buttons()

    def prepare_edit_toolbar(self):
        self._edit_toolbar.copy.connect('clicked', self.__copy_clicked_cb)
        self._edit_toolbar.paste.connect('clicked', self.__paste_clicked_cb)
        self._edit_toolbar.undo.connect('clicked', self.__undo_clicked_cb)
        self._edit_toolbar.redo.connect('clicked', self.__redo_clicked_cb)

    def __copy_clicked_cb(self, button):
        if self._text_editor.get_buffer().get_has_selection():
            self._text_editor.get_buffer().copy_clipboard(
                Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD))
        elif self._image_canvas.is_image_active():
            # if not text is selected
            # and a image is selected, copy as pixbuf
            clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
            pxb = self._image_canvas.create_pixbuf_with_active_image()
            clipboard.set_image(pxb)

    def __paste_clicked_cb(self, button):
        self._text_editor.get_buffer().paste_clipboard(
            Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD), None, True)

    def __undo_clicked_cb(self, button):
        self._text_editor.get_buffer().undo()

    def __redo_clicked_cb(self, button):
        self._text_editor.get_buffer().redo()

    def __set_background_clicked_cb(self, button):
        categories = {
            _('Indoors'): [os.path.join(SCRATCH_BACKGROUNDS_PATH, 'Indoors')],
            _('Nature'): [os.path.join(SCRATCH_BACKGROUNDS_PATH, 'Nature')],
            _('Outdoors'):
                [os.path.join(SCRATCH_BACKGROUNDS_PATH, 'Outdoors')],
            _('Sports'): [os.path.join(SCRATCH_BACKGROUNDS_PATH, 'Sports')]}

        chooser = ImageFileChooser(image_type='backgrounds',
                                   title=_('Select a background'),
                                   categories=categories,
                                   language=self._language,
                                   translations=self._translations,
                                   parent=self.get_window())
        chooser.connect('response', self.__chooser_response_cb,
                        self._change_background)
        self.set_sensitive(False)
        chooser.show()

    def __chooser_response_cb(self, chooser, response_id, operation_function):
        self.set_sensitive(True)
        if response_id == Gtk.ResponseType.ACCEPT:
            logging.error('selected %s', chooser.get_selected_object_id())
            file_path = chooser.get_selected_object_id()
            tempfile_name = \
                os.path.join(self.get_activity_root(),
                             'instance', 'tmp%i' % time.time())
            os.link(file_path, tempfile_name)
            operation_function(tempfile_name)
        chooser.destroy()
        del chooser
        if response_id == Gtk.ResponseType.REJECT:
            try:
                chooser = ObjectChooser(self, what_filter='Image',
                                        filter_type=FILTER_TYPE_GENERIC_MIME,
                                        show_preview=True)
            except:
                # for compatibility with older versions
                chooser = ObjectChooser(self, what_filter='Image')

            try:
                result = chooser.run()
                if result == Gtk.ResponseType.ACCEPT:
                    logging.error('ObjectChooser: %r' %
                                  chooser.get_selected_object())
                    jobject = chooser.get_selected_object()
                    if jobject and jobject.file_path:
                        logging.error("imagen seleccionada: %s",
                                      jobject.file_path)
                        tempfile_name = \
                            os.path.join(self.get_activity_root(),
                                         'instance', 'tmp%i' % time.time())
                        os.link(jobject.file_path, tempfile_name)
                        operation_function(tempfile_name)
            finally:
                chooser.destroy()
                del chooser

    def _change_background(self, file_name):
        self._book_model.set_page_background(self._actual_page, file_name)
        self._update_page_view()

    def __add_image_clicked_cb(self, button):
        categories = {
            _('Animals'): [os.path.join(SCRATCH_COSTUMES_PATH, 'Animals'),
                           os.path.join(TUXPAINT_STAMPS_PATH, 'animals')],
            _('Fantasy'): [os.path.join(SCRATCH_COSTUMES_PATH, 'Fantasy'),
                           os.path.join(TUXPAINT_STAMPS_PATH, 'cartoon')],
            _('Letters'): [os.path.join(SCRATCH_COSTUMES_PATH, 'Letters')],
            _('People'): [os.path.join(SCRATCH_COSTUMES_PATH, 'People'),
                          os.path.join(TUXPAINT_STAMPS_PATH, 'people')],
            _('Things'): [os.path.join(SCRATCH_COSTUMES_PATH, 'Things'),
                          os.path.join(TUXPAINT_STAMPS_PATH, 'clothes'),
                          os.path.join(TUXPAINT_STAMPS_PATH, 'hobbies'),
                          os.path.join(TUXPAINT_STAMPS_PATH, 'medical'),
                          os.path.join(TUXPAINT_STAMPS_PATH, 'household'),
                          os.path.join(TUXPAINT_STAMPS_PATH, 'food')],
            _('Transportation'): [
                os.path.join(SCRATCH_COSTUMES_PATH, 'Transportation'),
                os.path.join(TUXPAINT_STAMPS_PATH, 'vehicles')]}

        chooser = ImageFileChooser(image_type='actors',
                                   title=_('Select a image to add'),
                                   categories=categories,
                                   language=self._language,
                                   translations=self._translations,
                                   parent=self.get_window())
        chooser.connect('response', self.__chooser_response_cb,
                        self._add_image)
        self.set_sensitive(False)
        chooser.show()

    def _add_image(self, file_name):
        logging.error('Add image %s', file_name)
        self._book_model.add_image(self._actual_page, file_name)
        self._update_page_view()

    def __remove_clicked_cb(self, file_name):
        if self._image_canvas.is_image_active():
            alert = ConfirmationAlert()
            alert.props.title = _('Do you want remove the selected image?')
            # alert.props.msg = _('')
            alert.connect('response', self.__confirm_remove_image_cb)
            self.add_alert(alert)
        else:
            if len(self._book_model.get_pages()) > 1:
                alert = ConfirmationAlert()
                alert.props.title = _('Do you want remove the page?')
                # alert.props.msg = _('')
                alert.connect('response', self.__confirm_remove_page_cb)
                self.add_alert(alert)

    def __confirm_remove_image_cb(self, alert, response_id):
        # Callback for conf alert
        self.remove_alert(alert)
        if response_id is Gtk.ResponseType.OK:
            self._image_canvas.remove_active_image()

    def __confirm_remove_page_cb(self, alert, response_id):
        # Callback for conf alert
        self.remove_alert(alert)
        if response_id is Gtk.ResponseType.OK:
            if self._book_model.remove_page(self._actual_page):
                if self._actual_page > len(self._book_model.get_pages()):
                    self._actual_page -= 1
                self._update_page_buttons()
                self._preview_panel.update_model(self._book_model.get_pages())

    def __images_modified_cb(self, canvas, images_views):
        self._book_model.update_images(self._actual_page, images_views)

    def _update_page_buttons(self):
        cant_pages = len(self._book_model.get_pages())
        self._page_counter_label.set_text('%d / %d' %
                                          (self._actual_page, cant_pages))
        self._prev_page_button.set_sensitive(self._actual_page > 1)
        self._next_page_button.set_sensitive(self._actual_page < cant_pages)
        self._update_page_view()

    def _update_page_view(self):
        page_model = self._book_model.get_page_model(self._actual_page)
        self._image_canvas.set_background(page_model.background_path)
        self._image_canvas.set_images(page_model.images)
        self._text_editor.disconnect(self._text_changed_signal_id)
        self._text_editor.set_text(page_model.text)
        self._text_changed_signal_id = self._text_editor.connect(
            'changed', self.__text_changed_cb)

    def __add_page_clicked_cb(self, button):
        self._book_model.add_page()
        self._actual_page = len(self._book_model.get_pages())
        self._update_page_buttons()
        self._preview_panel.update_model(self._book_model.get_pages())

    def __duplicate_page_clicked_cb(self, button):
        actual_page_model = self._book_model.get_page_model(self._actual_page)
        self._book_model.add_page(actual_page_model)
        self._actual_page = len(self._book_model.get_pages())
        self._update_page_buttons()
        self._preview_panel.update_model(self._book_model.get_pages())

    def __next_page_clicked_cb(self, button):
        self._actual_page += 1
        self._update_page_buttons()
        self._preview_panel.update_position(1)

    def __prev_page_clicked_cb(self, button):
        self._actual_page -= 1
        self._update_page_buttons()
        self._preview_panel.update_position(-1)

    def __page_activated_cb(self, preview_panel, order):
        self._actual_page = order
        self._update_page_buttons()

    def __page_moved_cb(self, preview_panel, pages_order_array):
        new_pages = []
        for n in pages_order_array:
            new_pages.append(self._book_model.get_pages()[n])
        # actual_page is 1 based and order is 0 based
        actual_page_order = self._actual_page - 1
        new_order_actual_page = pages_order_array.index(actual_page_order)
        self._actual_page = new_order_actual_page + 1
        self._book_model.set_pages(new_pages)
        self._update_page_buttons()
        preview_panel.update_model(self._book_model.get_pages())

    def __text_changed_cb(self, texteditor):
        self._book_model.set_page_text(self._actual_page,
                                       texteditor.get_text())

    def __save_ebook_clicked_cb(self, button):
        alert = Alert()
        alert.props.title = _('Book creation')
        alert.props.msg = _('Do you want to add an image for the cover?')
        icon = Icon(icon_name='dialog-ok')
        alert.add_button(Gtk.ResponseType.YES, _('Yes'), icon)
        icon.show()
        icon = Icon(icon_name='dialog-cancel')
        alert.add_button(Gtk.ResponseType.NO, _('No'), icon)
        icon.show()
        alert.connect('response', self.__add_cover_response_cb,
                      self._set_cover_and_create_book)
        self.add_alert(alert)

    def __add_cover_response_cb(self, alert, response_id, operation_function):
        if response_id == Gtk.ResponseType.YES:
            try:
                chooser = ObjectChooser(self, what_filter='Image',
                                        filter_type=FILTER_TYPE_GENERIC_MIME,
                                        show_preview=True)
            except:
                # for compatibility with older versions
                chooser = ObjectChooser(self, what_filter='Image')

            try:
                result = chooser.run()
                if result == Gtk.ResponseType.ACCEPT:
                    logging.error('ObjectChooser: %r' %
                                  chooser.get_selected_object())
                    jobject = chooser.get_selected_object()
                    if jobject and jobject.file_path:
                        logging.error("imagen seleccionada: %s",
                                      jobject.file_path)
                        mime_type = mime.get_for_file(jobject.file_path)
                        extension = mime.get_primary_extension(mime_type)
                        tempfile_name = \
                            os.path.join(
                                self.get_activity_root(), 'instance',
                                'tmp%i.%s' % (time.time(), extension))
                        os.link(jobject.file_path, tempfile_name)
                        operation_function(tempfile_name)
            finally:
                chooser.destroy()
                del chooser

        elif response_id == Gtk.ResponseType.NO:
            self._save_epub()
        self.remove_alert(alert)

    def _set_cover_and_create_book(self, cover_file_name):
        self._book_model.cover_path = cover_file_name
        self._save_epub()

    def _save_epub(self):
        epub_file_name = create_ebub_from_book_model(
            self.metadata['title'], self._book_model)

        # create a new journal item
        fileObject = datastore.create()
        fileObject.metadata['title'] = \
            _('"%s" as book') % self.metadata['title']
        fileObject.metadata['mime_type'] = 'application/epub+zip'

        full_text = ''
        for page in self._book_model.get_pages():
            full_text += page.text + '\n'
        fileObject.metadata['fulltext'] = full_text
        fileObject.metadata['icon-color'] = self.metadata['icon-color']
        fileObject.metadata['keep'] = self.metadata.get('keep', '0')

        fileObject.metadata['preview'] = self.metadata['preview']
        fileObject.file_path = epub_file_name

        # store the journal item
        datastore.write(fileObject, transfer_ownership=True)
        book_object_id = fileObject.object_id

        fileObject.destroy()
        del fileObject
        shutil.rmtree(os.path.dirname(epub_file_name))

        finish_alert = Alert()
        finish_alert.props.title = _('Book created')
        finish_alert.props.msg = _('You can read the book in your Journal')
        open_icon = Icon(icon_name='zoom-activity')
        finish_alert.add_button(Gtk.ResponseType.APPLY,
                                _('Show in Journal'), open_icon)
        open_icon.show()
        ok_icon = Icon(icon_name='dialog-ok')
        finish_alert.add_button(Gtk.ResponseType.OK, _('Ok'), ok_icon)
        ok_icon.show()
        # Remove other alerts
        for alert in self._alerts:
            self.remove_alert(alert)

        self.add_alert(finish_alert)
        finish_alert.connect('response', self.__book_saved_alert_response_cb,
                             book_object_id)
        finish_alert.show()

    def __book_saved_alert_response_cb(self, alert, response_id,
                                       book_object_id):
        if response_id is Gtk.ResponseType.APPLY:
            activity.show_object_in_journal(book_object_id)
        self.remove_alert(alert)


class TextEditor(Gtk.TextView):

    __gsignals__ = {
        'changed': (GObject.SignalFlags.RUN_FIRST, None, ([])),
    }

    def __init__(self):
        Gtk.TextView.__init__(self)
        buffer = GtkSource.Buffer()
        self.set_buffer(buffer)
        buffer.set_highlight_syntax(False)
        buffer.set_max_undo_levels(30)

        self.set_wrap_mode(Gtk.WrapMode.WORD_CHAR)
        self.set_pixels_above_lines(0)
        self.set_size_request(-1, style.GRID_CELL_SIZE)

        font_desc = Pango.font_description_from_string('14')
        self.modify_font(font_desc)
        self.get_buffer().connect('changed', self.__buffer_changed_cb)

    def __buffer_changed_cb(self, text_buffer):
        cursor_iter = self.get_buffer().get_iter_at_mark(
            self.get_buffer().get_insert())
        self.scroll_to_iter(cursor_iter, 0, False, 0, 0)
        self.emit('changed')

    def get_text(self):
        return self.get_buffer().get_text(self.get_buffer().get_start_iter(),
                                          self.get_buffer().get_end_iter(),
                                          False)

    def set_text(self, text):
        self.get_buffer().begin_not_undoable_action()
        self.get_buffer().set_text(text)
        self.get_buffer().end_not_undoable_action()
