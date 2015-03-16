# the book model


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


class Page():

    def __init__(self):
        self.background_path = None
        self.images = []
        self.text = ''


class Image():

    def __init__(self):
        self.path = None
        # the size is stored as a percentage of the background image
        self.width = 100
        self.height = 100
        self.mirrored = False
        self.angle = 0
