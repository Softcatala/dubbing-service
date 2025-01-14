# -*- encoding: utf-8 -*-
#
# Copyright (c) 2021 Jordi Mas i Hernandez <jmas@softcatala.org>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this program; if not, write to the
# Free Software Foundation, Inc., 59 Temple Place - Suite 330,
# Boston, MA 02111-1307, USA.

import os
import uuid
import fnmatch
import logging


class BatchFile:
    def __init__(
        self,
        filename_dbrecord: str,
        filename: str,
        email: str,
        variant: str,
        original_filename: str,
        video_lang: str,
        operation: str,
        revision: int,
        original_subtitles: bool,
        dubbed_subtitles: bool,
    ):
        self.filename_dbrecord = filename_dbrecord
        self.filename = filename
        self.email = email
        self.variant = variant
        self.original_filename = original_filename
        self.video_lang = video_lang
        self.operation = operation
        self.revision = revision
        self.original_subtitles = original_subtitles
        self.dubbed_subtitles = dubbed_subtitles


# This is a disk based priority queue with works as filenames
# as items to store
class Queue:  # works with filenames
    g_check_directory = True

    def __init__(self, entries="/srv/data/entries"):
        self.ENTRIES = entries

    def _find(self, directory, pattern):
        filelist = []

        for root, dirs, files in os.walk(directory):
            for basename in files:
                if fnmatch.fnmatch(basename, pattern):
                    filename = os.path.join(root, basename)
                    filelist.append(filename)

        filelist.sort(key=lambda filename: os.path.getmtime(filename))
        return filelist

    def count(self):
        filenames = self._find(self.ENTRIES, "*.dbrecord")
        return len(filenames)

    def get_all(self):
        return self._find(self.ENTRIES, "*.dbrecord")

    def put(self, filename_dbrecord, content):
        if self.g_check_directory:
            self.g_check_directory = False
        if not os.path.exists(self.ENTRIES):
            os.makedirs(self.ENTRIES)

        with open(filename_dbrecord, "w") as fh:
            fh.write(content)

    def delete(self, filename):
        os.remove(filename)


class BatchFilesDB(Queue):
    SEPARATOR = "\t"

    def get_record_file_from_uuid(self, _uuid):
        return os.path.join(self.ENTRIES, _uuid + ".dbrecord")

    def get_new_uuid(self):
        return str(uuid.uuid4())

    def _int_to_bool(self, string):
        return True if int(string) == 1 else False

    def _bool_to_int(self, value):
        return 1 if value else 0

    def create(
        self,
        filename,
        email,
        variant,
        original_filename,
        video_lang="",
        operation="create",
        record_uuid=None,
        revision=1,
        original_subtitles=False,
        dubbed_subtitles=False,
    ):
        if not record_uuid:
            record_uuid = self.get_new_uuid()

        filename_dbrecord = self.get_record_file_from_uuid(record_uuid)
        line = f"v1{self.SEPARATOR}{filename}{self.SEPARATOR}{email}{self.SEPARATOR}{variant}{self.SEPARATOR}{original_filename}"
        line += f"{self.SEPARATOR}{video_lang}{self.SEPARATOR}{operation}{self.SEPARATOR}{revision}{self.SEPARATOR}"
        line += f"{self._bool_to_int(original_subtitles)}{self.SEPARATOR}{self._bool_to_int(dubbed_subtitles)}"
        self.put(filename_dbrecord, line)
        return record_uuid

    def select(self, email=None):
        filenames = self.get_all()
        records = []
        for filename in filenames:
            record = self._read_record(filename)

            if email and record.email.lower() != email.lower():
                continue

            records.append(record)

        return records

    def _read_record_from_uuid(self, _uuid):
        record_fullpath = os.path.join(self.ENTRIES, _uuid + ".dbrecord")
        record = self._read_record(record_fullpath)
        return record

    def _read_record(self, filename_dbrecord):
        try:
            with open(filename_dbrecord, "r") as fh:
                line = fh.readline()
                components = line.split(self.SEPARATOR)
                if components[0] == "v1":
                    return BatchFile(
                        filename_dbrecord=filename_dbrecord,
                        filename=components[1],
                        email=components[2],
                        variant=components[3],
                        original_filename=components[4],
                        video_lang=components[5],
                        operation=components[6],
                        revision=int(components[7]),
                        original_subtitles=self._int_to_bool(components[8]),
                        dubbed_subtitles=self._int_to_bool(components[9]),
                    )
                else:
                    raise RuntimeError("dbrecord version not supported")

        except Exception as exception:
            logging.error(
                f"_read_record. Unable to read {filename_dbrecord}. Error: {exception}"
            )
            return None
