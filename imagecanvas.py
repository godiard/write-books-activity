# Copyright 2015 Gonzalo Odiard
#
import cairo

from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from sugar3.graphics import style

WIDTH_CONTROL_LINES = 2
SIZE_RESIZE_AREA = style.GRID_CELL_SIZE / 2


class ImageCanvas(Gtk.DrawingArea):

    __gsignals__ = {
        'images-modified': (GObject.SignalFlags.RUN_FIRST, None, ([object])),
    }

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
        self._active_image = None
        self._press_on_image = False
        self._press_on_resize = False
        self._modified = False

        self._request_size()
        self.connect('size_allocate', self.__size_allocate_cb)
        self.connect("draw", self.__draw_cb)

        self.connect("button_press_event", self.__button_press_cb)
        self.connect("motion_notify_event", self.__motion_cb)
        self.connect("button_release_event", self.__button_release_cb)

        """
        self.connect("motion_notify_event", self.mouse_move)
        """

    def __size_allocate_cb(self, WIDGET, allocation):
        self._request_size()

    def _request_size(self):
        self._height = Gdk.Screen.height() / 4 * 3
        self._width = self._height / 3 * 4
        self.set_size_request(self._width, self._height)

    def set_background(self, file_path):
        self._background_path = file_path
        self._background = None
        self.queue_draw()

    def set_images(self, image_models):
        self._images = []
        for image_model in image_models:
            image_view = ImageView(
                image_model.path, image_model.width, image_model.height,
                self._width, self._height)
            image_view.x = image_model.x
            image_view.y = image_model.y
            image_view.mirrored = image_model.mirrored
            image_view.angle = image_model.angle
            self._images.append(image_view)

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

        for image_view in self._images:
            x_ini, y_ini = image_view.get_coordinates()
            width, height = image_view.get_size()
            ctx.save()
            ctx.translate(x_ini, y_ini)
            scale_x = width / image_view.pixbuf.get_width() * 1.0
            scale_y = height / image_view.pixbuf.get_height() * 1.0
            ctx.scale(scale_x, scale_y)
            Gdk.cairo_set_source_pixbuf(ctx, image_view.pixbuf, 0, 0)
            if self._press_on_resize:
                ctx.get_source().set_filter(cairo.FILTER_NEAREST)

            ctx.paint()
            ctx.restore()
            if image_view == self._active_image:
                ctx.save()
                ctx.translate(x_ini, y_ini)
                ctx.set_line_width(WIDTH_CONTROL_LINES)
                # draw a line around the image
                ctx.move_to(SIZE_RESIZE_AREA / 2, 0)
                ctx.line_to(width, 0)
                ctx.line_to(width, height)
                ctx.line_to(0, height)
                ctx.line_to(0, SIZE_RESIZE_AREA / 2)
                ctx.set_source_rgb(1, 1, 1)
                ctx.stroke_preserve()
                ctx.set_dash([4, 4])
                ctx.set_source_rgb(0, 0, 0)
                ctx.stroke()
                # draw the resize corner
                ctx.rectangle(-SIZE_RESIZE_AREA / 2, -SIZE_RESIZE_AREA / 2,
                              SIZE_RESIZE_AREA, SIZE_RESIZE_AREA)
                ctx.set_dash([])
                ctx.set_source_rgb(1, 1, 1)
                ctx.stroke_preserve()
                ctx.set_dash([4, 4])
                ctx.set_source_rgb(0, 0, 0)
                ctx.stroke()
                ctx.restore()

        # Draw the border
        ctx.save()
        ctx.set_line_width(2)
        ctx.rectangle(0, 0, self._width, self._height)
        ctx.set_source_rgb(0, 0, 0)
        ctx.stroke()
        ctx.restore()

    def __button_press_cb(self, widget, event):
        # Check if clicked over a image
        for image_view in self._images:
            if image_view.is_in_size_area(event.x, event.y):
                self._active_image = image_view
                self._press_on_resize = True
                self.queue_draw()
                return
            elif image_view.is_inside(event.x, event.y):
                self._active_image = image_view
                self._press_on_image = True
                self.queue_draw()
                return

        self._active_image = None
        self._press_on_image = False
        self.queue_draw()

    def __button_release_cb(self, widget, event):
        self._press_on_image = False
        self._press_on_resize = False
        self.queue_draw()
        if self._modified:
            self.emit('images-modified', self._images)
            self._modified = False

    def __motion_cb(self, widget, event):
        if self._press_on_image:
            self._active_image.move(event.x, event.y)
            self._modified = True
            self.queue_draw()
        if self._press_on_resize:
            self._active_image.resize(event.x, event.y)
            self._modified = True
            self.queue_draw()

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

    """


class ImageView():

    def __init__(self, path, width, height, canvas_width, canvas_height):
        self.path = path
        self._canvas_width = canvas_width
        self._canvas_height = canvas_height
        # the size is stored as a percentage of the background image
        self.x = 0
        self.y = 0
        self.pixbuf = GdkPixbuf.Pixbuf.new_from_file(self.path)

        self.width = width
        if width == 0:
            self.width = self.pixbuf.get_width() * 100. / self._canvas_width
        self.height = height
        if height == 0:
            self.height = self.pixbuf.get_height() * 100. / self._canvas_height

        self.mirrored = False
        self.angle = 0
        # points to the start of the image where the user click
        self._dx_click = 0
        self._dy_click = 0
        # this is used to resize
        self._resize_from_x, self._resize_from_y = 0, 0
        self._resize_width, self._resize_heigth = 0, 0

    def get_coordinates(self):
        """
        Return coordinates in points
        """
        return (self._canvas_width * self.x / 100.,
                self._canvas_height * self.y / 100.)

    def get_size(self):
        """
        Return size in points
        """
        return (self._canvas_width * self.width / 100.,
                self._canvas_height * self.height / 100.)

    def is_in_size_area(self, x, y):
        resize = SIZE_RESIZE_AREA / 2
        x_ini, y_ini = self.get_coordinates()
        if x_ini - resize < x < x_ini + resize \
                and y_ini - resize < y < y_ini + resize:
            self._resize_from_x, self._resize_from_y = x, y
            self._resize_width, self._resize_heigth = self.get_size()
            return True
        return False

    def is_inside(self, x, y):
        x_ini, y_ini = self.get_coordinates()
        width, height = self.get_size()
        if x_ini < x < x_ini + width and y_ini < y < y_ini + height:
            self._dx_click = x - x_ini
            self._dy_click = y - y_ini
            return True
        else:
            self._dx_click = 0
            self._dy_click = 0
            return False

    def move(self, x, y):
        x_new, y_new = x - self._dx_click, y - self._dy_click
        # set as percentage
        self.x = x_new * 100. / self._canvas_width
        self.y = y_new * 100. / self._canvas_height

    def resize(self, x, y):
        delta_x, delta_y = x - self._resize_from_x, y - self._resize_from_y
        # set a minimal size
        width_new = max(style.GRID_CELL_SIZE,
                        self._resize_width - delta_x * 2)
        height_new = max(style.GRID_CELL_SIZE,
                         self._resize_heigth - delta_y * 2)
        # set as percentage
        self.width = width_new * 100. / self._canvas_width
        self.height = height_new * 100. / self._canvas_height
        # set as percentage
        self.x = x * 100. / self._canvas_width
        self.y = y * 100. / self._canvas_height
