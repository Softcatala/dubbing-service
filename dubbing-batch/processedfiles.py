# -*- encoding: utf-8 -*-
#
# Copyright (c) 2022 Jordi Mas i Hernandez <jmas@softcatala.org>
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
import logging
import shutil
import uuid
import time
import fnmatch

PROCESSED = "/srv/data/processed"


class ProcessedFiles:
    def __init__(self, uuid):
        self.uuid = uuid

    @staticmethod
    def get_processed_directory():
        return PROCESSED

    @staticmethod
    def is_valid_uuid(id: str):
        try:
            uuid.UUID(str(id))
            return True
        except ValueError:
            return False

    @staticmethod
    def do_files_exists(id: str):
        extensions = [
            "mp4",
            "dbrecord",
            "dub",
        ]  # , "log", "json"] May be add str in the future
        for extension in extensions:
            fullname = os.path.join(PROCESSED, id)
            fullname = f"{fullname}.{extension}"

            if not os.path.exists(fullname):
                message = f"file {extension} does not exist"
                return False, message

        return True, ""

    @staticmethod
    def output_dir_exists(id: str):
        fullname = os.path.join(PROCESSED, f"{id}_output")
        return os.path.exists(fullname)

    @staticmethod
    def ensure_dir():
        if not os.path.exists(PROCESSED):
            os.makedirs(PROCESSED)

    def _get_extension(self, filename):
        split_tup = os.path.splitext(filename)
        file_extension = split_tup[1]
        return file_extension

    def copy_file(self, full_filename):
        filename = os.path.basename(full_filename)
        target = os.path.join(PROCESSED, filename)
        shutil.copy(full_filename, target)
        logging.debug(f"Copy file {full_filename} to {target}")

    def copy_file_bin(self, full_filename, extension):
        target = os.path.join(PROCESSED, f"{self.uuid}{extension}")
        shutil.copy(full_filename, target)

        logging.debug(f"Copied file {full_filename} to {target}")

    def move_file(self, full_filename):
        filename = os.path.basename(full_filename)
        ext = self._get_extension(filename)
        target = os.path.join(PROCESSED, f"{self.uuid}{ext}")
        shutil.move(full_filename, target)
        logging.debug(f"Moved file {full_filename} to {target}")

    def move_file_bin(self, full_filename, extension):
        target = os.path.join(PROCESSED, f"{self.uuid}{extension}")
        shutil.move(full_filename, target)

        logging.debug(f"Moved file {full_filename} to {target}")

    def move_output_dir(self, full_dir):
        target = os.path.join(PROCESSED, f"{self.uuid}_output")

        if os.path.exists(target):
            shutil.rmtree(target)

        shutil.move(full_dir, target)

        logging.debug(f"Moved directory {full_dir} to {target}")

    def copy_file_to(self, source, target):
        filename = os.path.basename(source)
        source = os.path.join(PROCESSED, filename)
        shutil.copy(source, target)
        logging.info(f"Copy file {source} to {target}")

    def copy_output_dir_to(self, target):
        source = os.path.join(PROCESSED, f"{self.uuid}_output")
        os.makedirs(os.path.dirname(target), exist_ok=True)
        shutil.copytree(
            source, target, dirs_exist_ok=True
        )  # Set `dirs_exist_ok` to True for overwriting if necessary

        logging.info(f"Copy directory {source} to {target}")

    def _find_files(directory, pattern):
        filelist = []

        for root, dirs, files in os.walk(directory):
            for basename in files:
                if fnmatch.fnmatch(basename, pattern):
                    filename = os.path.join(root, basename)
                    filelist.append(filename)

        return filelist

    def _find_dirs(directory):
        return [
            os.path.abspath(os.path.join(directory, name))
            for name in os.listdir(directory)
            if os.path.isdir(os.path.join(directory, name))
        ]

    def get_num_of_files_stored(directory=PROCESSED):
        files = ProcessedFiles._find_files(directory, "*")
        return len(files)

    def _get_human_readable_size(size):
        GB_IN_BYTES = 1024**3
        if size > GB_IN_BYTES:
            gbs = size / GB_IN_BYTES
            text = f"{gbs:.2f} GB"
        else:
            text = f"{size} bytes"

        return text

    def get_num_of_files_stored_size(directory=PROCESSED):
        files = ProcessedFiles._find_files(directory, "*")
        total_size = 0
        for _file in files:
            total_size += os.stat(_file).st_size

        return ProcessedFiles._get_human_readable_size(total_size)

    def get_free_space_in_directory(directory=PROCESSED):
        statvfs = os.statvfs(directory)

        # Available blocks * block size gives the available space in bytes
        free_space_bytes = statvfs.f_frsize * statvfs.f_bavail
        return ProcessedFiles._get_human_readable_size(free_space_bytes)

    def purge_files(days, directory=PROCESSED):
        HOURS_DAY = 24
        MINUTES_HOUR = 60
        MINUTES_SEC = 60
        deleted = 0

        files = ProcessedFiles._find_files(directory, "*")
        time_limit = time.time() - (HOURS_DAY * MINUTES_HOUR * MINUTES_SEC * days)
        for file in files:
            try:
                file_time = os.stat(file).st_mtime
                if file_time < time_limit:
                    os.remove(file)
                    logging.debug(f"Deleted file: {file}")
                    deleted += 1
            except Exception as e:
                logging.error(f"purge_files. Error deleting file {file}: {e}")

        for dir in ProcessedFiles._find_dirs(directory):
            try:
                dir_time = os.stat(dir).st_mtime
                if dir_time < time_limit:
                    shutil.rmtree(dir)
                    logging.debug(f"Deleted dir: {dir}")
                    deleted += 1
            except Exception as e:
                logging.error(f"purge_files. Error deleting file {dir}: {e}")

        return deleted
