# Copyright (C) 2011, Gonzalo Odiard <gonzalo@laptop.org>

import logging
import os
import shutil
import zipfile
import string
import random
import tempfile
from gettext import gettext as _

from sugar3 import mime
from sugar3 import profile

from imagecanvas import ImageCanvas

_title_page_template = """
    <html xmlns="http://www.w3.org/1999/xhtml">
    <head>
    <title>Book Title</title>
    <style type="text/css">
    body {
        font-family: Sans;
        text-align: center;
    }
    .title {
        font-size: 48px;
        margin-bottom: 50px;
        margin-top: 200px;
    }
    .author {
        font-size: 32px;
    }
    </style>
    </head>
    <body>
    <p class='title'>%s</p>
    <p class='author'>%s</p>
    </body>
    </html>"""


def create_ebub_from_book_model(title, book_model):
    # use a temp dir to create the files
    root_directory = tempfile.mkdtemp(prefix="html")
    logging.error('CREATE EPUB on dir %s', root_directory)
    logging.error('TITLE %s', title)
    if not os.path.exists(os.path.join(root_directory, 'images')):
        os.mkdir(os.path.join(root_directory, 'images'))

    # create a title page
    author = profile.get_nick_name()
    html = _title_page_template % (title, _('by %s') % author)
    with open(os.path.join(root_directory, 'title.html'), 'w') as html_file:
        html_file.write(html)

    # create the html with the text and images for every page (800 x 600)
    image_renderer = ImageCanvas()
    counter = 1
    html = """<html xmlns="http://www.w3.org/1999/xhtml">
              <head>
              <title>Content</title>
              <style type="text/css">
              p {
                 font-family: Sans;
                 font-size: 24px;
                 margin-bottom: 100px;
                }
              </style>
              </head>
              <body>
            """
    images = []
    for page in book_model.get_pages():
        image_path = os.path.join(root_directory, 'images/%s.png' % counter)
        images.append(image_path)
        image_renderer.write_to_png(
            image_path, 800, 600, page.background_path, page.images)
        html += '<div><img src="./images/%s" alt="%s"/></div>\n' % (
            os.path.basename(image_path), 'Image page %d' % counter)
        html += '<p>%s</p>\n' % page.text
        counter += 1

    html += '</body></html>'
    # write the html file
    with open(os.path.join(root_directory, 'pages.html'), 'w') as html_file:
        html_file.write(html)

    lang = os.environ.get('LANG')
    if lang and len(lang) > 2:
        lang = lang[:2]
    else:
        lang = 'en'
    factory = EpubFactory(title, author, lang)
    files = [{'title': 'Title',
              'filename': os.path.join(root_directory, 'title.html')},
             {'title': 'Content',
              'filename': os.path.join(root_directory, 'pages.html')}]
    logging.error('Adding files %s', files)
    if book_model.cover_path:
        factory.set_cover_image(book_model.cover_path)
    factory.make_epub(files, images=images)
    epub_file_name = factory.create_archive()
    factory.clean()
    shutil.rmtree(root_directory)
    return epub_file_name


class EpubFactory():

    def __init__(self, title, creator, language):
        self._title = title
        self._creator = self._remove_unsafe_chars(creator)
        random_string = ''.join(random.choice(
            string.ascii_uppercase) for i in range(30))
        self._id = '%s-%s' % (creator, random_string)
        self._language = language
        self._cover_image = None
        self._list_files = None

    def _remove_unsafe_chars(self, message):
        return message.replace('<', '_').replace('>', '_').replace('&', '_')

    def set_cover_image(self, cover_image):
        self._cover_image = cover_image

    def make_epub(self, file_list, images=None):
        self._list_files = file_list
        if self._list_files is None or not self._list_files:
            # TODO throw exception?
            return

        self.root_directory = tempfile.mkdtemp(prefix="epub")

        self.mimetype_file = self.create_mimetype_file()

        metainf_dir = self.root_directory + '/META-INF'
        os.mkdir(metainf_dir)
        self.create_container_file(metainf_dir)

        oebps_dir = self.root_directory + '/OEBPS'
        os.mkdir(oebps_dir)

        self.create_toc_file(oebps_dir, file_list)

        self.images = []
        if images is not None:
            self.images = images
        self.css = []
        for file_data in file_list:
            file_name = file_data['filename']
            shutil.copyfile(
                file_name,
                os.path.join(self.root_directory, 'OEBPS',
                             os.path.basename(file_name)))

        if len(self.images) > 0:
            os.mkdir(os.path.join(oebps_dir, 'images'))
        if len(self.css) > 0:
            os.mkdir(os.path.join(oebps_dir, 'css'))

        content_file_list = []
        for file_data in file_list:
            file_name = file_data['filename']
            content_file_list.append(os.path.basename(file_name))

        for img_name in self.images:
            shutil.copyfile(
                img_name,
                os.path.join(self.root_directory, 'OEBPS', 'images',
                             os.path.basename(img_name)))
            content_file_list.append(
                os.path.join('images', os.path.basename(img_name)))

        for css_name in self.css:
            shutil.copyfile(
                css_name,
                os.path.join(self.root_directory, 'OEBPS', 'css',
                             os.path.basename(css_name)))
            content_file_list.append(
                os.path.join('css', os.path.basename(css_name)))

        if self._cover_image:
            self._local_cover_image_path = os.path.join(
                self.root_directory, 'OEBPS',
                os.path.basename(self._cover_image))
            shutil.copyfile(
                self._cover_image, self._local_cover_image_path)
            self._create_html_cover()

        self.create_content_file(oebps_dir, content_file_list)

    def _create_html_cover(self):
        html_cover_template = """
        <!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN"
            "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
        <html xmlns="http://www.w3.org/1999/xhtml">
          <head>
            <title>Cover</title>
            <style type="text/css"> img {max-width: 100%%} </style>
          </head>
          <body>
            <div id="cover-image">
              <img src="%s" alt="Title"/>
            </div>
          </body>
        </html>"""

        file_name = os.path.join(self.root_directory, 'OEBPS', 'cover.html')
        with open(file_name, 'w') as fd:
            fd.write(html_cover_template % os.path.basename(self._cover_image))

    def create_mimetype_file(self):
        file_name = self.root_directory + "/mimetype"
        fd = open(file_name, 'w')
        fd.write('application/epub+zip')
        fd.close()
        return file_name

    def create_container_file(self, metainf_dir):
        fd = open(metainf_dir + "/container.xml", 'w')
        fd.write('<?xml version="1.0"?>\n')
        fd.write('<container version="1.0" ')
        fd.write('xmlns="urn:oasis:names:tc:opendocument:xmlns:container">\n')
        fd.write('<rootfiles>\n')
        fd.write('<rootfile full-path="OEBPS/content.opf" ')
        fd.write('media-type="application/oebps-package+xml" />\n')
        fd.write('</rootfiles>\n')
        fd.write('</container>')
        fd.close()

    def _guess_mime(self, file_name):
        logging.error('_guess_mime %s', file_name)
        mime_type = None
        if file_name.endswith('.html') or file_name.endswith('.htm'):
            mime_type = 'application/xhtml+xml'
        elif file_name.endswith('.css'):
            mime_type = 'text/css'
        elif file_name.endswith('.png'):
            mime_type = 'image/png'
        elif file_name.endswith('.jpg') or file_name.endswith('.jpeg'):
            mime_type = 'image/jpeg'
        elif file_name.endswith('.gif'):
            mime_type = 'image/gif'
        if mime is None:
            mime_type = mime.get_for_file(file_name)
        return mime_type

    def create_content_file(self, oebps_dir, file_list):
        fd = open(oebps_dir + "/content.opf", 'w')

        fd.write('<?xml version="1.0" encoding="utf-8"?>\n')
        fd.write('<package xmlns="http://www.idpf.org/2007/opf" ')
        fd.write('xmlns:dc="http://purl.org/dc/elements/1.1/" ')
        fd.write('unique-identifier="bookid" version="2.0">\n')

        # metadata
        fd.write('<metadata>\n')
        fd.write('<dc:title>%s</dc:title>\n' % self._title)
        fd.write('<dc:creator>%s</dc:creator>\n' % self._creator)
        fd.write('<dc:identifier id="bookid">' +
                 'urn:uuid:%s</dc:identifier>\n' % self._id)
        fd.write('<dc:language>%s</dc:language>\n' % self._language)
        if self._cover_image:
            fd.write('<meta name="cover" content="%s"/>\n' %
                     os.path.basename(self._cover_image))
        fd.write('</metadata>\n')

        # manifest
        fd.write('<manifest>\n')
        fd.write('<item id="ncx" href="toc.ncx" ' +
                 'media-type="application/x-dtbncx+xml"/>\n')

        if self._cover_image is not None:
            fd.write('<item id="cover" href="cover.html" ' +
                     'media-type="application/xhtml+xml"/>\n')
            cover_mime = self._guess_mime(self._cover_image)
            fd.write('<item id="cover-image" href="%s" media-type="%s"/>\n' %
                     (os.path.basename(self._cover_image), cover_mime))

        count = 0
        spine_elements = []
        for file_name in file_list:
            content_id = 'content'
            if count > 0:
                content_id = 'content%d' % count

            mime = self._guess_mime(file_name)
            if mime == 'application/xhtml+xml':
                spine_elements.append(content_id)

            fd.write('<item id="%s" href="%s" ' % (content_id, file_name) +
                     'media-type="%s"/>\n' % mime)
            count = count + 1

        fd.write('</manifest>\n')

        # spine
        fd.write('<spine toc="ncx">\n')
        if self._cover_image is not None:
            fd.write('<itemref idref="cover" linear="no"/>\n')
        for element_id in spine_elements:
            fd.write('<itemref idref="%s"/>\n' % element_id)
        fd.write('</spine>\n')

        # guide
        fd.write('<guide>\n')
        if self._cover_image is not None:
            fd.write('<reference href="cover.html" type="cover" ' +
                     'title="Cover"/>\n')
        fd.write('</guide>\n')
        fd.write('</package>\n')
        fd.close()

    def create_toc_file(self, oebps_dir, file_list):
        fd = open(oebps_dir + "/toc.ncx", 'w')
        fd.write('<?xml version="1.0" encoding="utf-8"?>\n')
        fd.write('<!DOCTYPE ncx PUBLIC "-//NISO//DTD ncx 2005-1//EN"\n')
        fd.write('"http://www.daisy.org/z3986/2005/ncx-2005-1.dtd">\n')
        fd.write('<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" ' +
                 'version="2005-1">\n')

        fd.write('<head>\n')
        fd.write('<meta name="dtb:uid" ' +
                 'content="urn:uuid:%s"/>\n' % self._id)
        fd.write('<meta name="dtb:depth" content="1"/>\n')
        fd.write('<meta name="dtb:totalPageCount" content="0"/>\n')
        fd.write('<meta name="dtb:maxPageNumber" content="0"/>\n')
        fd.write('</head>\n')

        fd.write('<docTitle>\n')
        fd.write('<text>%s</text>\n' % self._title)
        fd.write('</docTitle>\n')

        fd.write('<navMap>\n')
        np = 1
        if self._cover_image is not None:
            fd.write('<navPoint id="navpoint-1" playOrder="1">\n')
            fd.write('<navLabel>\n')
            fd.write('<text>Book cover</text>\n')
            fd.write('</navLabel>\n')
            fd.write('<content src="cover.html"/>\n')
            fd.write('</navPoint>\n')
            np = np + 1

        for file_data in file_list:
            fd.write('<navPoint id="navpoint-%d" playOrder="%d">\n' % (np, np))
            fd.write('<navLabel>\n')
            fd.write('<text>%s</text>\n' % file_data['title'])
            fd.write('</navLabel>\n')
            fd.write('<content src="%s"/>\n' % os.path.basename(
                file_data['filename']))
            fd.write('</navPoint>\n')
            np = np + 1

        fd.write('</navMap>\n')
        fd.write('</ncx>\n')
        fd.close()

    def create_archive(self):
        '''Create the ZIP archive.
        The mimetype must be the first file in the archive
        and it must not be compressed.'''

        tempdir = tempfile.mkdtemp()
        epub_name = os.path.join(tempdir, 'book.epub')

        # The EPUB must contain the META-INF and mimetype files at the root, so
        # we'll create the archive in the working directory first
        # and move it later
        current_dir = os.getcwd()
        os.chdir(self.root_directory)

        # Open a new zipfile for writing
        epub = zipfile.ZipFile(epub_name, 'w')

        # Add the mimetype file first and set it to be uncompressed
        epub.write('mimetype', compress_type=zipfile.ZIP_STORED)

        # For the remaining paths in the EPUB, add all of their files
        # using normal ZIP compression
        self._scan_dir('.', epub)
        epub.close()
        os.chdir(current_dir)
        return epub_name

    def _scan_dir(self, path, epub_file):
        for p in os.listdir(path):
            print "P", p
            if os.path.isdir(os.path.join(path, p)):
                self._scan_dir(os.path.join(path, p), epub_file)
            else:
                if p != 'mimetype':
                    epub_file.write(
                        os.path.join(path, p),
                        compress_type=zipfile.ZIP_DEFLATED)

    def clean(self):
        shutil.rmtree(self.root_directory)
