# the book model
import logging
import os
import json
import zipfile

from sugar3.activity import activity


class BookModel():

    def __init__(self):
        self._pages = [Page()]

    def get_pages(self):
        return self._pages

    def add_page(self):
        self._pages.append(Page())

    def get_page_model(self, page_number):
        return self._pages[page_number - 1]

    def set_page_background(self, page_number, path):
        self._pages[page_number - 1].background_path = path

    def set_page_text(self, page_number, text):
        self._pages[page_number - 1].text = text

    def add_image(self, page_number, path):
        page = self._pages[page_number - 1]
        image = Image()
        image.path = path
        page.images.append(image)

    def update_images(self, page_number, images_views):
        page = self._pages[page_number - 1]
        cont = 0
        for image in page.images:
            image_view = images_views[cont]
            image.x = image_view.x
            image.y = image_view.y
            image.width = image_view.width
            image.height = image_view.height
            image.mirrored = image_view.mirrored
            image.angle = image_view.angle
            cont += 1

    def write(self, file_path):
        instance_path = os.path.join(activity.get_activity_root(), 'instance')

        book_data = {}
        book_data['version'] = '1'

        pages = []
        for page in self._pages:
            page_data = {}
            page_data['text'] = page.text
            page_data['background_path'] = page.background_path
            page_data['images'] = []
            for image in page.images:
                image_data = {}
                image_data['x'] = image.x
                image_data['y'] = image.y
                image_data['path'] = image.path
                image_data['width'] = image.width
                image_data['height'] = image.height
                image_data['mirrored'] = image.mirrored
                image_data['angle'] = image.angle
                page_data['images'].append(image_data)
            pages.append(page_data)
        book_data['pages'] = pages
        logging.debug('book_data %s', book_data)

        data_file_name = 'data.json'
        f = open(os.path.join(instance_path, data_file_name), 'w')
        try:
            json.dump(book_data, f)
        finally:
            f.close()

        logging.debug('file_path %s', file_path)

        z = zipfile.ZipFile(file_path, 'w')
        z.write(os.path.join(instance_path, data_file_name), data_file_name)

        # zip the iages
        for page in self._pages:
            if page.background_path is not None and \
                    page.background_path != '':
                z.write(page.background_path,
                        os.path.basename(page.background_path))
            for image in page.images:
                if image.path is not None and image.path != '':
                    z.write(image.path, os.path.basename(image.path))
        z.close()

    def read(self, file_path):
        instance_path = os.path.join(activity.get_activity_root(), 'instance')
        z = zipfile.ZipFile(file_path, 'r')
        for file_path in z.namelist():
            if (file_path != './'):
                try:
                    logging.debug('extracting %s', file_path)
                    # la version de python en las xo no permite hacer
                    # extract :(
                    # z.extract(file_path,instance_path)
                    data = z.read(file_path)
                    fout = open(os.path.join(instance_path, file_path), 'w')
                    fout.write(data)
                    fout.close()
                except:
                    logging.error('Error extracting %s', file_path)
        z.close()
        data_file_path = 'data.json'

        book_data = {}
        with open(os.path.join(instance_path, data_file_path)) as f:
            book_data = json.load(f)

        self._pages = []
        for page_data in book_data['pages']:
            page = Page()
            page.background_path = page_data['background_path']
            page.text = page_data['text']
            page.images = []
            for image_data in page_data['images']:
                image = Image()
                image.path = image_data['path']
                image.x = image_data['x']
                image.y = image_data['y']
                image.width = image_data['width']
                image.height = image_data['height']
                image.mirrored = image_data['mirrored']
                image.angle = image_data['angle']
                page.images.append(image)
            self._pages.append(page)


class Page():

    def __init__(self):
        self.background_path = None
        self.images = []
        self.text = ''


class Image():

    def __init__(self):
        self.path = None
        # the size and position is stored as a percentage of the background
        self.x = 0
        self.y = 0
        self.width = 30
        self.height = 30
        self.mirrored = False
        self.angle = 0
