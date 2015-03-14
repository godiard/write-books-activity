# the book model


class BookModel():

    def __init__(self):
        self._pages = [Page()]

    def get_pages(self):
        return self._pages

    def add_page(self):
        self._pages.append(Page())


class Page():

    def __init__(self):
        self._background_path = None
        self._images = []
        self.text = ''


class Image():

    def __init__(self):
        self.path = None
        # the size is stored as a percentage of the background image
        self._width = 100
        self.height = 100
        self.mirrored = False
        self.angle = 0
