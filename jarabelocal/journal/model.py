# Copyright (C) 2007-2011, One Laptop per Child
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
import os
import errno
import time
from stat import S_IFLNK, S_IFMT, S_IFDIR, S_IFREG
import re
from operator import itemgetter
import json

import dbus
from gi.repository import Gio
from gi.repository import GLib

from sugar3 import dispatch


MIN_PAGES_TO_CACHE = 3
MAX_PAGES_TO_CACHE = 5

JOURNAL_METADATA_DIR = '.Sugar-Metadata'

created = dispatch.Signal()
updated = dispatch.Signal()
deleted = dispatch.Signal()


class _Cache(object):

    __gtype_name__ = 'model_Cache'

    def __init__(self, entries=None):
        self._array = []
        if entries is not None:
            self.append_all(entries)

    def prepend_all(self, entries):
        self._array[0:0] = entries

    def append_all(self, entries):
        self._array += entries

    def __len__(self):
        return len(self._array)

    def __getitem__(self, key):
        return self._array[key]

    def __delitem__(self, key):
        del self._array[key]


class BaseResultSet(object):
    """Encapsulates the result of a query
    """

    def __init__(self, query, page_size):
        self._total_count = -1
        self._position = -1
        self._query = query
        self._page_size = page_size

        self._offset = 0
        self._cache = _Cache()

        self.ready = dispatch.Signal()
        self.progress = dispatch.Signal()

    def setup(self):
        self.ready.send(self)

    def stop(self):
        pass

    def get_length(self):
        if self._total_count == -1:
            query = self._query.copy()
            query['limit'] = self._page_size * MIN_PAGES_TO_CACHE
            entries, self._total_count = self.find(query)
            self._cache.append_all(entries)
            self._offset = 0
        return self._total_count

    length = property(get_length)

    def find(self, query):
        raise NotImplementedError()

    def seek(self, position):
        self._position = position

    def read(self):
        if self._position == -1:
            self.seek(0)

        if self._position < self._offset:
            remaining_forward_entries = 0
        else:
            remaining_forward_entries = self._offset + len(self._cache) - \
                self._position

        if self._position > self._offset + len(self._cache):
            remaining_backwards_entries = 0
        else:
            remaining_backwards_entries = self._position - self._offset

        last_cached_entry = self._offset + len(self._cache)

        if remaining_forward_entries <= 0 and remaining_backwards_entries <= 0:

            # Total cache miss: remake it
            limit = self._page_size * MIN_PAGES_TO_CACHE
            offset = max(0, self._position - limit / 2)
            logging.debug('remaking cache, offset: %r limit: %r', offset,
                          limit)
            query = self._query.copy()
            query['limit'] = limit
            query['offset'] = offset
            entries, self._total_count = self.find(query)

            del self._cache[:]
            self._cache.append_all(entries)
            self._offset = offset

        elif (remaining_forward_entries <= 0 and
              remaining_backwards_entries > 0):

            # Add one page to the end of cache
            logging.debug('appending one more page, offset: %r',
                          last_cached_entry)
            query = self._query.copy()
            query['limit'] = self._page_size
            query['offset'] = last_cached_entry
            entries, self._total_count = self.find(query)

            # update cache
            self._cache.append_all(entries)

            # apply the cache limit
            cache_limit = self._page_size * MAX_PAGES_TO_CACHE
            objects_excess = len(self._cache) - cache_limit
            if objects_excess > 0:
                self._offset += objects_excess
                del self._cache[:objects_excess]

        elif remaining_forward_entries > 0 and \
                remaining_backwards_entries <= 0 and self._offset > 0:

            # Add one page to the beginning of cache
            limit = min(self._offset, self._page_size)
            self._offset = max(0, self._offset - limit)

            logging.debug('prepending one more page, offset: %r limit: %r',
                          self._offset, limit)
            query = self._query.copy()
            query['limit'] = limit
            query['offset'] = self._offset
            entries, self._total_count = self.find(query)

            # update cache
            self._cache.prepend_all(entries)

            # apply the cache limit
            cache_limit = self._page_size * MAX_PAGES_TO_CACHE
            objects_excess = len(self._cache) - cache_limit
            if objects_excess > 0:
                del self._cache[-objects_excess:]

        return self._cache[self._position - self._offset]


class InplaceResultSet(BaseResultSet):
    """Encapsulates the result of a query on a mount point
    """
    def __init__(self, query, page_size, mount_point):
        BaseResultSet.__init__(self, query, page_size)
        self._mount_point = mount_point
        self._file_list = None
        self._pending_directories = []
        self._visited_directories = []
        self._pending_files = []
        self._stopped = False

        query_text = query.get('query', '')
        if query_text.startswith('"') and query_text.endswith('"'):
            self._regex = re.compile('*%s*' % query_text.strip(['"']))
        elif query_text:
            expression = ''
            for word in query_text.split(' '):
                expression += '(?=.*%s.*)' % word
            self._regex = re.compile(expression, re.IGNORECASE)
        else:
            self._regex = None

        if query.get('timestamp', ''):
            self._date_start = int(query['timestamp']['start'])
            self._date_end = int(query['timestamp']['end'])
        else:
            self._date_start = None
            self._date_end = None

        self._only_favorites = int(query.get('keep', '0')) == 1

        self._filter_by_activity = query.get('activity', '')

        self._mime_types = query.get('mime_type', [])

        self._sort = query.get('order_by', ['+timestamp'])[0]

    def setup(self):
        self._file_list = []
        self._pending_directories = [self._mount_point]
        self._visited_directories = []
        self._pending_files = []
        GLib.idle_add(self._scan)

    def stop(self):
        self._stopped = True

    def setup_ready(self):
        if self._sort[1:] == 'filesize':
            keygetter = itemgetter(3)
        else:
            # timestamp
            keygetter = itemgetter(2)
        self._file_list.sort(lambda a, b: cmp(b, a),
                             key=keygetter,
                             reverse=(self._sort[0] == '-'))
        self.ready.send(self)

    def find(self, query):
        if self._file_list is None:
            raise ValueError('Need to call setup() first')

        if self._stopped:
            raise ValueError('InplaceResultSet already stopped')

        t = time.time()

        offset = int(query.get('offset', 0))
        limit = int(query.get('limit', len(self._file_list)))
        total_count = len(self._file_list)

        files = self._file_list[offset:offset + limit]

        entries = []
        for file_path, stat, mtime_, size_, metadata in files:
            if metadata is None:
                metadata = _get_file_metadata(file_path, stat)
            metadata['mountpoint'] = self._mount_point
            entries.append(metadata)

        logging.debug('InplaceResultSet.find took %f s.', time.time() - t)

        return entries, total_count

    def find_ids(self, query):
        if self._file_list is None:
            raise ValueError('Need to call setup() first')

        if self._stopped:
            raise ValueError('InplaceResultSet already stopped')

        ids = []
        for file_path, stat, mtime_, size_, metadata in self._file_list:
            ids.append(file_path)
        return ids

    def _scan(self):
        if self._stopped:
            return False

        self.progress.send(self)

        if self._pending_files:
            self._scan_a_file()
            return True

        if self._pending_directories:
            self._scan_a_directory()
            return True

        self.setup_ready()
        self._visited_directories = []
        return False

    def _scan_a_file(self):
        full_path = self._pending_files.pop(0)
        metadata = None

        try:
            stat = os.lstat(full_path)
        except OSError, e:
            if e.errno != errno.ENOENT:
                logging.exception(
                    'Error reading metadata of file %r', full_path)
            return

        if S_IFMT(stat.st_mode) == S_IFLNK:
            try:
                link = os.readlink(full_path)
            except OSError, e:
                logging.exception(
                    'Error reading target of link %r', full_path)
                return

            if not os.path.abspath(link).startswith(self._mount_point):
                return

            try:
                stat = os.stat(full_path)

            except OSError, e:
                if e.errno != errno.ENOENT:
                    logging.exception(
                        'Error reading metadata of linked file %r', full_path)
                return

        if S_IFMT(stat.st_mode) == S_IFDIR:
            id_tuple = stat.st_ino, stat.st_dev
            if id_tuple not in self._visited_directories:
                self._visited_directories.append(id_tuple)
                self._pending_directories.append(full_path)
            return

        if S_IFMT(stat.st_mode) != S_IFREG:
            return

        if self._regex is not None and \
                not self._regex.match(full_path):
            metadata = _get_file_metadata(full_path, stat,
                                          fetch_preview=False)
            if not metadata:
                return
            add_to_list = False
            for f in ['fulltext', 'title',
                      'description', 'tags']:
                if f in metadata and \
                        self._regex.match(metadata[f]):
                    add_to_list = True
                    break
            if not add_to_list:
                return

        if self._only_favorites:
            if not metadata:
                metadata = _get_file_metadata(full_path, stat,
                                              fetch_preview=False)
            if 'keep' not in metadata:
                return
            try:
                if int(metadata['keep']) == 0:
                    return
            except ValueError:
                return

        if self._filter_by_activity:
            if not metadata:
                metadata = _get_file_metadata(full_path, stat,
                                              fetch_preview=False)
            if 'activity' not in metadata or \
                    metadata['activity'] != self._filter_by_activity:
                return

        if self._date_start is not None and stat.st_mtime < self._date_start:
            return

        if self._date_end is not None and stat.st_mtime > self._date_end:
            return

        if self._mime_types:
            mime_type, uncertain_result_ = \
                Gio.content_type_guess(filename=full_path, data=None)
            if mime_type not in self._mime_types:
                return

        file_info = (full_path, stat, int(stat.st_mtime), stat.st_size,
                     metadata)
        self._file_list.append(file_info)

        return

    def _scan_a_directory(self):
        dir_path = self._pending_directories.pop(0)

        try:
            entries = os.listdir(dir_path)
        except OSError, e:
            if e.errno != errno.EACCES:
                logging.exception('Error reading directory %r', dir_path)
            return

        for entry in entries:
            if entry.startswith('.'):
                continue
            self._pending_files.append(dir_path + '/' + entry)
        return


def _get_file_metadata(path, stat, fetch_preview=True):
    """Return the metadata from the corresponding file.

    Reads the metadata stored in the json file or create the
    metadata based on the file properties.

    """
    metadata = _get_file_metadata_from_json(path, fetch_preview)
    if metadata:
        if 'filesize' not in metadata:
            metadata['filesize'] = stat.st_size
        return metadata

    mime_type, uncertain_result_ = Gio.content_type_guess(filename=path,
                                                          data=None)
    return {'uid': path,
            'title': os.path.basename(path),
            'timestamp': stat.st_mtime,
            'filesize': stat.st_size,
            'mime_type': mime_type,
            'activity': '',
            'activity_id': '',
            'icon-color': '#000000,#ffffff',
            'description': path}


def _get_file_metadata_from_json(path, fetch_preview):
    """Read the metadata from the json file and the preview
    stored on the external device.

    If the metadata is corrupted we do remove it and the preview as well.

    """
    filename = os.path.basename(path)
    dir_path = os.path.dirname(path)

    metadata = None

    metadata_path = os.path.join(dir_path, JOURNAL_METADATA_DIR,
                                 filename + '.metadata')
    preview_path = os.path.join(dir_path, JOURNAL_METADATA_DIR,
                                filename + '.preview')

    if not os.path.exists(metadata_path):
        return None

    try:
        metadata = json.load(open(metadata_path))
    except (ValueError, EnvironmentError):
        os.unlink(metadata_path)
        if os.path.exists(preview_path):
            os.unlink(preview_path)
        logging.error('Could not read metadata for file %r on '
                      'external device.', filename)
        return None
    else:
        metadata['uid'] = path

    if not fetch_preview:
        if 'preview' in metadata:
            del(metadata['preview'])
    else:
        if os.path.exists(preview_path):
            try:
                metadata['preview'] = dbus.ByteArray(open(preview_path).read())
            except EnvironmentError:
                logging.debug('Could not read preview for file %r on '
                              'external device.', filename)
    return metadata


def find(query_, page_size):
    """Returns a ResultSet
    """
    query = query_.copy()

    mount_points = query.pop('mountpoints', ['/'])
    if mount_points is None or len(mount_points) != 1:
        raise ValueError('Exactly one mount point must be specified')

    return InplaceResultSet(query, page_size, mount_points[0])


def get(object_id):
    """Returns the metadata for an object
    """
    metadata = {}
    if os.path.exists(object_id):
        stat = os.stat(object_id)
        metadata = _get_file_metadata(object_id, stat)
        metadata['mountpoint'] = os.path.dirname(object_id)
    return metadata
