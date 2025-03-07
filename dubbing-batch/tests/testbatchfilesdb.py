# -*- coding: utf-8 -*-
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

from batchfilesdb import BatchFilesDB
import unittest
import os
import tempfile
import time


class TestBatchFilesDB(unittest.TestCase):
    FILENAME = "fitxer.txt"
    EMAIL = "jmas@softcatala.org"
    EMAIL2 = "jordi@softcatala.org"
    EMAIL3 = "JMAS@softcatala.org"
    VARIANT = "eng-cat"

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.ENTRIES = self.temp_dir.name

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_db_object(self):
        db = BatchFilesDB()
        db.ENTRIES = self.ENTRIES
        return db

    def test_create(self):
        db = self._create_db_object()
        _uuid = db.create(
            self.FILENAME, self.EMAIL, self.VARIANT, "original_filename.mp3"
        )
        filename_dbrecord = db.get_record_file_from_uuid(_uuid)

        record = db._read_record(filename_dbrecord)
        self.assertEquals(self.FILENAME, record.filename)
        self.assertEquals(self.EMAIL, record.email)
        self.assertEquals(self.VARIANT, record.variant)

    def test_select(self):
        db = self._create_db_object()
        db.create(self.FILENAME, self.EMAIL, self.VARIANT, "original_filename.mp3")

        records = db.select()
        self.assertEquals(1, len(records))

        record = records[0]
        self.assertEquals(self.FILENAME, record.filename)
        self.assertEquals(self.EMAIL, record.email)
        self.assertEquals(self.VARIANT, record.variant)

    def test_select_email(self):
        db = self._create_db_object()
        db.create(self.FILENAME, self.EMAIL, self.VARIANT, "original_filename.mp3")
        db.create(self.FILENAME, self.EMAIL2, self.VARIANT, "original_filename.mp3")

        records = db.select(email=self.EMAIL)
        self.assertEquals(1, len(records))

        record = records[0]
        self.assertEquals(self.FILENAME, record.filename)
        self.assertEquals(self.EMAIL, record.email)
        self.assertEquals(self.VARIANT, record.variant)

    def test_select_email_uppercase(self):
        db = self._create_db_object()
        db.create(self.FILENAME, self.EMAIL, self.VARIANT, "original_filename.mp3")
        db.create(self.FILENAME, self.EMAIL2, self.VARIANT, "original_filename.mp3")
        db.create(self.FILENAME, self.EMAIL3, self.VARIANT, "original_filename.mp3")

        records = db.select(email=self.EMAIL)
        self.assertEquals(2, len(records))

        record = records[0]
        self.assertEquals(self.FILENAME, record.filename)
        self.assertEquals(self.EMAIL.lower(), record.email.lower())
        self.assertEquals(self.VARIANT, record.variant)

    def test_selected_expected_order(self):
        db = self._create_db_object()
        MINUTES_SEC = 60
        MAX_FILES_IN_QUEUE = 20

        for _id in range(0, MAX_FILES_IN_QUEUE):
            _uuid = db.create(_id, self.EMAIL, self.VARIANT, "original_filename.mp3")
            filename_dbrecord = db.get_record_file_from_uuid(_uuid)
            future_time = time.time() + (MINUTES_SEC * _id)
            os.utime(filename_dbrecord, (future_time, future_time))

        records = db.select()
        for id in range(0, MAX_FILES_IN_QUEUE):
            self.assertEquals(str(id), records[id].filename)

    def test_delete(self):
        db = self._create_db_object()
        _uuid = db.create(
            self.FILENAME, self.EMAIL, self.VARIANT, "original_filename.mp3"
        )
        filename_dbrecord = db.get_record_file_from_uuid(_uuid)

        records_org = db.select()
        db.delete(filename_dbrecord)

        records = len(records_org) - len(db.select())
        self.assertEquals(1, records)


if __name__ == "__main__":
    unittest.main()
