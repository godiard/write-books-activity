# Copyright 2015 Gonzalo Odiard
#

from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GdkPixbuf


class ImageCanvas(Gtk.DrawingArea):

    def __init__(self):
        Gtk.DrawingArea.__init__(self)

        self.add_events(
            Gdk.EventMask.POINTER_MOTION_MASK |
            Gdk.EventMask.BUTTON_PRESS_MASK |
            Gdk.EventMask.BUTTON_RELEASE_MASK |
            Gdk.EventMask.BUTTON_MOTION_MASK)

        self._background = None
        self._background_path = None
        self._images = []

        """
        self.glob_press = False
        self.is_dimension = False
        self.is_punto = False
        self.image_name = ''
        self.image = None
        self.image_saved = False
        self.title_globe = None
        self.thumbnail = None
        self._globo_activo = None
        """

        self.connect('size_allocate', self.__size_allocate_cb)
        self.connect("draw", self.__draw_cb)

        """
        self.connect("button_press_event", self.pressing)
        self.connect("motion_notify_event", self.mouse_move)
        self.connect("motion_notify_event", self.moving)
        self.connect("button_release_event", self.releassing)
        """

        self.show_all()

    def __size_allocate_cb(self, WIDGET, allocation):
        self._height = Gdk.Screen.height() / 4 * 3
        self._width = self._height / 3 * 4
        self.set_size_request(self._width, self._height)

    def set_background(self, file_path):
        self._background_path = file_path
        self._background = None
        self.queue_draw()

    """
    def set_globo_activo(self, globo):
        if self._globo_activo is not None and self._globo_activo != globo:
            self._globo_activo.set_selected(False)
        if globo is not None:
            globo.set_selected(True)
        self._globo_activo = globo
        if globo is not None and globo.texto is not None:
            self._page._text_toolbar.setToolbarState(globo.texto)

    def redraw(self):
        self._drawingarea.queue_draw()

    def get_globo_activo(self):
        return self._globo_activo

    def add_globo(self, xpos, ypos, gmodo="normal",
                  gdireccion=globos.DIR_ABAJO,
                  font_name=globos.DEFAULT_FONT):
        globo = globos.Globo(self, x=xpos, y=ypos, modo=gmodo,
                             direccion=gdireccion, font_name=font_name)
        self.globos.append(globo)
        self._globo_activo = globo
        self.redraw()
    """

    def __draw_cb(self, widget, context):
        self.draw_in_context(context)
        return False

    def draw_in_context(self, ctx):
        # Draw the background image

        if self._background is None and self._background_path is not None:
            self._background = GdkPixbuf.Pixbuf.new_from_file_at_size(
                self._background_path, self._width, self._height)

        if self._background_path is None:
            # draw a white background
            ctx.rectangle(0, 0, self._width, self._height)
            ctx.set_source_rgb(1, 1, 1)
            ctx.fill()
        else:
            Gdk.cairo_set_source_pixbuf(ctx, self._background, 0, 0)
            ctx.paint()

        # Draw the border
        ctx.save()
        ctx.set_line_width(2)
        ctx.rectangle(0, 0, self._width, self._height)
        ctx.set_source_rgb(0, 0, 0)
        ctx.stroke()
        ctx.restore()

    """
    def get_thumbnail(self):
        if self.thumbnail is None:
            instance_path = os.path.join(activity.get_activity_root(),
                                         'instance')
            if (not self.image_name.startswith(instance_path)):
                self.thumbnail = GdkPixbuf.Pixbuf.new_from_file_at_size(
                    os.path.join(instance_path, self.image_name),
                    THUMB_SIZE[0], THUMB_SIZE[1])
            else:
                self.thumbnail = GdkPixbuf.Pixbuf.new_from_file_at_size(
                    self.image_name, THUMB_SIZE[0], THUMB_SIZE[1])
        return self.thumbnail

    def draw_globos(self, context):
        if len(self.globos) > 0:
            for g in self.globos:
                g.imprimir(context)

    def pressing(self, widget, event):
        # if is not the last box selected redraw this and the last
        # (possible optimization, draw only the border
        if (self._page.get_active_box() != self):
            self._page.set_active_box(self)

        # Check if clicked over a globe
        if self._globo_activo is not None:
            if self._globo_activo.is_selec_tam(event.x, event.y) or \
                    self._globo_activo.get_cursor_type(event.x, event.y) \
                    is not None:
                self.is_dimension = True
            elif self._globo_activo.is_selec_punto(event.x, event.y):
                self.is_punto = True

        if (not self.is_dimension) and not (self.is_punto):
            if self.globos:
                list_aux = self.globos[:]
                list_aux.reverse()
                for i in list_aux:
                    if i.is_selec(event.x, event.y):
                        self.glob_press = True
                        self.set_globo_activo(i)
                        self.redraw()
                        break

    def releassing(self, widget, event):
        self.glob_press = False
        self.is_dimension = False
        self.is_punto = False

    def mouse_move(self, widget, event):
        if self._globo_activo is not None:
            cursor_type = self._globo_activo.get_cursor_type(event.x, event.y)
            cursor = None
            if cursor_type is not None:
                cursor = Gdk.Cursor(cursor_type)
            self.get_window().set_cursor(cursor)

    def moving(self, widget, event):
        if self.is_dimension:
            self._globo_activo.set_dimension(event.x, event.y,
                                             self.get_allocation())
            self.redraw()
        elif self.is_punto:
            self._globo_activo.mover_punto(event.x, event.y,
                                           self.get_allocation())
            self.redraw()
        elif self.glob_press:
            self._globo_activo.mover_a(event.x, event.y,
                                       self.get_allocation())
            self.redraw()
    """
