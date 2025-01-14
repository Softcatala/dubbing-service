#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#
# Copyright (c) 2020-2023 Jordi Mas i Hernandez <jmas@softcatala.org>
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

from __future__ import print_function
import time
import logging
import logging.handlers
import os
from batchfilesdb import BatchFilesDB
from processedfiles import ProcessedFiles
from sendmail import Sendmail
from execution import Execution, Command
from lockfile import LockFile
import datetime

from usage import Usage


def init_logging():
    LOGDIR = os.environ.get("LOGDIR", "")
    LOGID = os.environ.get("LOGID", "0")
    LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
    logfile = os.path.join(LOGDIR, f"process-batch-{LOGID}.log")
    logger = logging.getLogger()
    hdlr = logging.handlers.RotatingFileHandler(
        logfile, maxBytes=1024 * 1024, backupCount=1
    )
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    hdlr.setFormatter(formatter)
    logger.addHandler(hdlr)
    logger.setLevel(LOGLEVEL)

    console = logging.StreamHandler()
    console.setLevel(LOGLEVEL)
    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
    console.setFormatter(formatter)
    logger.addHandler(console)


def _get_extension(original_filename):
    split_tup = os.path.splitext(original_filename)

    file_extension = split_tup[1]
    if file_extension == "":
        file_extension = ".bin"

    return file_extension


def _get_threads():
    return os.environ.get("THREADS", 4)


def _get_timeout() -> int:
    return int(os.environ.get("TIMEOUT_CMD", 60 * 90))


def _send_mail_create(batchfile, inference_time, variant, source_file_base):

    text = f"Ja tenim el vostre fitxer '{batchfile.original_filename}' doblat amb la variant '{variant}'.\n"
    text += f"El podeu baixar des de https://www.softcatala.org/doblatge/resultats/?uuid={source_file_base}&revision={batchfile.revision}\n"
    text += "No compartiu aquesta adreça amb altres persones si no voleu que tinguin accés al fitxer."

    if "@softcatala" in batchfile.email:
        text += f"\nL'execució ha trigat {inference_time}."

    Sendmail().send(text, batchfile.email)


def _send_mail_update(batchfile, inference_time, variant, source_file_base):

    text = f"Ja tenim actualizat amb els darrers canvis el vostre fitxer '{batchfile.original_filename}' doblat amb la variant '{variant}'.\n"
    text += f"El podeu baixar des de https://www.softcatala.org/doblatge/resultats/?uuid={source_file_base}&revision={batchfile.revision}\n"
    text += "No compartiu aquesta adreça amb altres persones si no voleu que tinguin accés al fitxer."

    if "@softcatala" in batchfile.email:
        text += f"\nL'execució ha trigat {inference_time}."

    Sendmail().send(text, batchfile.email)


def _send_mail_error(batchfile, inference_time, source_file_base, message):
    text = f"No hem pogut processar el vostre fitxer '{batchfile.original_filename}'.\n"
    text += message

    logging.info(f"_send_mail_error: {message} to {batchfile.email}")
    Sendmail().send(text, batchfile.email)


def _delete_record(db, batchfile, converted_audio):
    db.delete(batchfile.filename_dbrecord)

    if os.path.isfile(batchfile.filename):
        os.remove(batchfile.filename)
        logging.debug(f"Deleted {batchfile.filename}")

    if os.path.exists(converted_audio):
        os.remove(converted_audio)
        logging.debug(f"Deleted {converted_audio}")

    LockFile(batchfile.filename_dbrecord).delete()


def _delete_record_keep_file(db, batchfile, converted_audio, processed):
    db.delete(batchfile.filename_dbrecord)

    source_file = batchfile.filename
    extension = _get_extension(batchfile.original_filename)
    processed.move_file_bin(source_file, extension)
    logging.info(f"Kept file with error '{processed.uuid}{extension}'")
    LockFile(batchfile.filename_dbrecord).delete()


def main():
    print("Process batch files to dubbing")
    init_logging()
    db = BatchFilesDB()
    ProcessedFiles.ensure_dir()
    purge_last_time = time.time()
    PURGE_INTERVAL_SECONDS = 60 * 60 * 6  # For times per day
    PURGE_OLDER_THAN_DAYS = 3
    execution = Execution(_get_threads())

    while True:
        batchfiles = db.select()
        for idx in range(len(batchfiles) - 1, -1, -1):
            batchfile = batchfiles[idx]
            if LockFile(batchfile.filename_dbrecord).has_lock():
                batchfiles.remove(batchfile)

        if len(batchfiles) > 0:
            batchfile = batchfiles[0]
            if not LockFile(batchfile.filename_dbrecord).create():
                time.sleep(5)
                continue

            source_file = batchfile.filename

            logging.info(
                f"Processing: {source_file} - for {batchfile.email} - pending {len(batchfiles)}"
            )

            source_file_base = os.path.basename(source_file)
            processed = ProcessedFiles(source_file_base)

            timeout = _get_timeout()

            source_file = batchfile.filename

            (
                inference_time,
                result,
                output_filename,
                output_directory,
                cat_subtitles,
                log_filename,
            ) = execution.run_inference(
                source_file,
                timeout,
                batchfile.variant,
                batchfile.video_lang,
                batchfile.operation,
                batchfile.original_subtitles,
                batchfile.dubbed_subtitles,
            )

            if result == Command.TIMEOUT_ERROR:
                _delete_record_keep_file(db, batchfile, output_filename, processed)
                minutes = int(timeout / 60)
                msg = f"Ha trigat massa temps en processar-se. Aturem l'operació després de {minutes} minuts de processament."
                Usage().log("dubbing_timeout")
                _send_mail_error(batchfile, inference_time, source_file_base, msg)
                continue

            if batchfile.video_lang == "auto":
                if result > 100 and result < 105:
                    _delete_record(db, batchfile, output_filename)
                    _send_mail_error(
                        batchfile,
                        inference_time,
                        source_file_base,
                        "Heu escollit detecció automàtica de l'idioma però l'idioma identificat no està suportat. Torneu a enviar el vídeo i indiqueu si està en anglès o castellà.",
                    )
                    Usage().log("dubbing_not_supported_language")
                    continue

            if result != Command.NO_ERROR:
                _delete_record_keep_file(db, batchfile, output_filename, processed)
                _send_mail_error(
                    batchfile,
                    inference_time,
                    source_file_base,
                    "Reviseu que sigui un vídeo vàlid.",
                )
                Usage().log("dubbing_returns_error")
                continue

            extension = _get_extension(batchfile.original_filename)
            variant = execution.get_full_variant(batchfile.variant)

            if batchfile.operation == "update":
                _send_mail_update(batchfile, inference_time, variant, source_file_base)
            else:
                _send_mail_create(batchfile, inference_time, variant, source_file_base)

            logging.info(f"File for {batchfile.email} completed in {inference_time}")

            processed.move_file(batchfile.filename_dbrecord)
            processed.move_file_bin(output_filename, ".dub")
            processed.copy_file_bin(
                cat_subtitles, ".srt"
            )  # to be remove when API moves to the new endpoint
            processed.move_file_bin(log_filename, ".log")
            processed.move_file_bin(source_file, extension)

            if batchfile.operation == "create":
                files = ProcessedFiles._find_files(output_directory, "chunk*")
                for file in files:
                    os.remove(file)

                logging.info(
                    f"Deleted unnecessary {len(files)} files in output directory"
                )

            processed.move_output_dir(output_directory)
            LockFile(batchfile.filename_dbrecord).delete()

        now = time.time()
        if now > purge_last_time + PURGE_INTERVAL_SECONDS:
            purge_last_time = now
            purged = ProcessedFiles.purge_files(PURGE_OLDER_THAN_DAYS)
            logging.info(f"Purging {datetime.datetime.now()}, {purged} files deleted")

        time.sleep(30)


if __name__ == "__main__":
    main()
