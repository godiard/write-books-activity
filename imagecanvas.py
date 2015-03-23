# Copyright 2015 Gonzalo Odiard
#
import cairo
import logging
import math

from gi.repository import GObject
from gi.repository import Gtk
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from sugar3.graphics import style

WIDTH_CONTROL_LINES = 2
CONTROL_SIZE = style.GRID_CELL_SIZE / 2


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
        self._image_models = []
        self._images = []
        self._active_image = None
        self._press_on_image = False
        self._press_on_resize = False
        self._modified = False

        self.connect('size_allocate', self.__size_allocate_cb)
        self.connect("draw", self.__draw_cb)

        self._bt_press_id = self.connect(
            'button_press_event', self.__button_press_cb)
        self._motion_id = self.connect(
            'motion_notify_event', self.__motion_cb)
        self._bt_release_id = self.connect(
            'button_release_event', self.__button_release_cb)

        # load pixbufs for controls
        self._rotate_pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
            './icons/object_rotate_right.svg', CONTROL_SIZE, CONTROL_SIZE)
        self._mirror_h_pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
            './icons/mirror-horizontal.svg', CONTROL_SIZE, CONTROL_SIZE)
        self._mirror_v_pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
            './icons/mirror-vertical.svg', CONTROL_SIZE, CONTROL_SIZE)
        self._resize_pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(
            './icons/resize.svg', CONTROL_SIZE, CONTROL_SIZE)

    def __size_allocate_cb(self, widget, allocation):
        logging.debug('allocation called in the canvas %s x %s',
                      allocation.width, allocation.height)
        width, height = allocation.width, allocation.height
        if allocation.width == 1 and allocation.height == 1:
            return
        self._width = width
        self._height = height
        self._background = None
        self._create_view_images()

    def set_editable(self, editable):
        if not editable:
            self.disconnect(self._bt_press_id)
            self.disconnect(self._motion_id)
            self.disconnect(self._bt_release_id)
        else:
            self._bt_press_id = self.connect(
                'button_press_event', self.__button_press_cb)
            self._motion_id = self.connect(
                'motion_notify_event', self.__motion_cb)
            self._bt_release_id = self.connect(
                'button_release_event', self.__button_release_cb)

    def set_background(self, file_path):
        self._background_path = file_path
        self._background = None
        self.queue_draw()

    def set_images(self, image_models):
        self._image_models = image_models
        self._create_view_images()
        self.queue_draw()

    def _create_view_images(self):
        self._images = []
        for image_model in self._image_models:
            image_view = ImageView(
                image_model.path, image_model.width, image_model.height,
                self._width, self._height)
            image_view.x = image_model.x
            image_view.y = image_model.y
            image_view.h_mirrored = image_model.h_mirrored
            image_view.v_mirrored = image_model.v_mirrored
            image_view.angle = image_model.angle
            self._images.append(image_view)

    def __draw_cb(self, widget, context):
        self.draw_in_context(context)
        return False

    def create_pixbuf(self, width, height, background_path, images):
        # this method is here to not need copy all the logic
        # to draw the iconview icons in the sorting screen
        # do not use the same widget as is used to edit in different sizes
        # or the cached pixbuf will be broken
        self._width = width
        self._height = height
        self.set_background(background_path)
        self.set_images(images)
        surface = cairo.ImageSurface(
            cairo.FORMAT_ARGB32, self._width, self._height)
        ctx = cairo.Context(surface)
        self.draw_in_context(ctx)
        surface.flush()
        return Gdk.pixbuf_get_from_surface(surface, 0, 0,
                                           self._width, self._height)

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

            if image_view.angle != 0:
                radians_angle = math.pi * float(image_view.angle) / 180.0
                ctx.rotate(radians_angle)
                if image_view.angle == 90:
                    ctx.translate(0, -height)
                elif image_view.angle == 180:
                    ctx.translate(-width, -height)
                elif image_view.angle == 270:
                    ctx.translate(-width, 0)

            h_mirrored = image_view.h_mirrored
            v_mirrored = image_view.v_mirrored
            if image_view.angle == 90 or image_view.angle == 270:
                h_mirrored, v_mirrored = v_mirrored, h_mirrored

            if h_mirrored:
                ctx.translate(width, 0)
                ctx.scale(-1.0, 1.0)
            if v_mirrored:
                ctx.translate(0, height)
                ctx.scale(1.0, -1.0)

            scale_x = width / image_view.pixbuf.get_width() * 1.0
            scale_y = height / image_view.pixbuf.get_height() * 1.0
            ctx.scale(scale_x, scale_y)
            Gdk.cairo_set_source_pixbuf(ctx, image_view.pixbuf, 0, 0)
            if self._press_on_resize:
                ctx.get_source().set_filter(cairo.FILTER_NEAREST)

            ctx.paint()
            ctx.restore()
            if image_view == self._active_image:
                if image_view.angle == 90 or image_view.angle == 270:
                    width, height = height, width

                ctx.save()
                ctx.translate(x_ini, y_ini)
                ctx.set_line_width(WIDTH_CONTROL_LINES)
                # draw a line around the image
                ctx.rectangle(0, 0, width, height)
                ctx.set_source_rgb(1, 1, 1)
                ctx.stroke_preserve()
                ctx.set_dash([4, 4])
                ctx.set_source_rgb(0, 0, 0)
                ctx.stroke()
                # draw the rotate corner
                self._draw_control(ctx, -CONTROL_SIZE / 2, -CONTROL_SIZE / 2,
                                   self._rotate_pixbuf)
                # draw the horizontal mirror
                self._draw_control(ctx, width - CONTROL_SIZE / 2,
                                   -CONTROL_SIZE / 2,
                                   self._mirror_h_pixbuf)
                self._draw_control(ctx, -CONTROL_SIZE / 2,
                                   height - CONTROL_SIZE / 2,
                                   self._mirror_v_pixbuf)
                self._draw_control(ctx, width - CONTROL_SIZE / 2,
                                   height - CONTROL_SIZE / 2,
                                   self._resize_pixbuf)
                ctx.restore()

        # Draw the border
        ctx.save()
        ctx.set_line_width(2)
        ctx.rectangle(0, 0, self._width, self._height)
        ctx.set_source_rgb(0, 0, 0)
        ctx.stroke()
        ctx.restore()

    def _draw_control(self, ctx, x, y, pixbuf):
        ctx.save()
        ctx.translate(x, y)
        ctx.rectangle(0, 0, CONTROL_SIZE, CONTROL_SIZE)
        ctx.set_source_rgb(0, 0, 0)
        ctx.fill()
        Gdk.cairo_set_source_pixbuf(ctx, pixbuf, 0, 0)
        ctx.paint()
        ctx.restore()

    def __button_press_cb(self, widget, event):
        # Check if clicked over a image
        for image_view in self._images:
            in_image = False

            if image_view.is_in_size_area(event.x, event.y):
                in_image = True
                self._press_on_resize = True
            elif image_view.is_in_horizontal_mirror_area(event.x, event.y):
                in_image = True
                image_view.h_mirrored = not image_view.h_mirrored
                self._modified = True
            elif image_view.is_in_vertical_mirror_area(event.x, event.y):
                in_image = True
                image_view.v_mirrored = not image_view.v_mirrored
                self._modified = True
            elif image_view.is_in_rotate_area(event.x, event.y):
                in_image = True
                image_view.angle = image_view.angle - 90
                if image_view.angle < 0:
                    image_view.angle = 270
                logging.error('Image angle %s', image_view.angle)
                self._modified = True
            elif image_view.is_inside(event.x, event.y):
                in_image = True
                self._press_on_image = True

            if in_image:
                self._active_image = image_view
                self.queue_draw()
                return

        self._active_image = None
        self._press_on_image = False
        self.queue_draw()

    def is_image_active(self):
        return self._active_image is not None

    def remove_active_image(self):
        if self._active_image is not None:
            self._images.remove(self._active_image)
            self.emit('images-modified', self._images)
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

        self.h_mirrored = False
        self.v_mirrored = False
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
        if self._check_point_in_corner_control(x, y, 'BR'):
            self._resize_from_x, self._resize_from_y = x, y
            self._resize_width, self._resize_heigth = self.get_size()
            return True
        return False

    def is_in_horizontal_mirror_area(self, x, y):
        return self._check_point_in_corner_control(x, y, 'TR')

    def is_in_vertical_mirror_area(self, x, y):
        return self._check_point_in_corner_control(x, y, 'BL')

    def is_in_rotate_area(self, x, y):
        return self._check_point_in_corner_control(x, y, 'TL')

    def _check_point_in_corner_control(self, x, y, corner):
        """
        x, y -- (int) coordinates in points
        corner -- (str) one of ['TL', 'TR', 'BL', 'BR']
            (Top Left, Top Right, Bottom Left and Bottom Right)
        """
        half_ctrl_size = CONTROL_SIZE / 2
        x_ini, y_ini = self.get_coordinates()
        width, height = self.get_size()
        if self.angle == 90 or self.angle == 270:
            width, height = height, width

        if corner == 'TL':
            x_btn = x_ini
            y_btn = y_ini
        elif corner == 'TR':
            x_btn = x_ini + width
            y_btn = y_ini
        elif corner == 'BL':
            x_btn = x_ini
            y_btn = y_ini + height
        elif corner == 'BR':
            x_btn = x_ini + width
            y_btn = y_ini + height
        else:
            logging.error('_check_point_in_corner_control bad corner %s',
                          corner)

        return x_btn - half_ctrl_size < x < x_btn + half_ctrl_size \
            and y_btn - half_ctrl_size < y < y_btn + half_ctrl_size

    def is_inside(self, x, y):
        x_ini, y_ini = self.get_coordinates()
        width, height = self.get_size()
        if self.angle == 90 or self.angle == 270:
            width, height = height, width

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
        if self.angle == 90 or self.angle == 270:
            delta_x, delta_y = delta_y, delta_x

        # set a minimal size
        width_new = max(style.GRID_CELL_SIZE,
                        self._resize_width + delta_x)
        height_new = max(style.GRID_CELL_SIZE,
                         self._resize_heigth + delta_y)
        # set as percentage
        self.width = width_new * 100. / self._canvas_width
        self.height = height_new * 100. / self._canvas_height
