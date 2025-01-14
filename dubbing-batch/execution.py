#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
#
# Copyright (c) 2023 Jordi Mas i Hernandez <jmas@softcatala.org>
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

import datetime
import logging
import os
import subprocess
import threading
import signal
import psutil
import shutil

OUTPUT_DIR = "output"


class Command(object):
    TIMEOUT_ERROR = -1
    NO_ERROR = 0

    def __init__(self, cmd):
        self.cmd = cmd
        self.process = None

    # Make sure that you kill also the process started in the Shell
    def _kill_child_processes(self, parent_pid, sig=signal.SIGTERM):
        try:
            parent = psutil.Process(parent_pid)
        except psutil.NoSuchProcess:
            logging.error(f"_kill_child_processes.Cannot kill process {parent_pid}")
            return

        children = parent.children(recursive=True)
        for process in children:
            process.send_signal(sig)

    def run(self, timeout):
        def target():
            self.process = subprocess.Popen(self.cmd, shell=True)
            self.process.communicate()

        thread = threading.Thread(target=target)
        thread.start()

        thread.join(timeout)
        if thread.is_alive():
            self._kill_child_processes(self.process.pid)
            return self.TIMEOUT_ERROR

        return self.process.returncode

    def run_log(self, timeout):
        def target():
            #            self.process = subprocess.Popen(self.cmd, shell=True)
            self.process = subprocess.Popen(
                self.cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )

        thread = threading.Thread(target=target)
        thread.start()

        thread.join(timeout)
        if thread.is_alive():
            self._kill_child_processes(self.process.pid)
            return self.TIMEOUT_ERROR

        stdout, stderr = self.process.communicate()

        # Print the output and error (if any)
        logging.info("Output:")
        logging.info(stdout.decode())  # Decode byte string to normal string

        if stderr:
            logging.error("Error:")
            logging.error(stderr.decode())

        return self.process.returncode


class Execution(object):
    def __init__(self, threads):
        self.threads = threads

    def _ffmpeg_errors(self, ffmpeg_errfile):
        return_code = Command.NO_ERROR
        try:
            if os.path.getsize(ffmpeg_errfile) == 0:
                return return_code

            return_code = -1
            cnt = 0
            with open(ffmpeg_errfile, "r") as fh:
                for line in fh.readlines():
                    logging.debug(f"_ffmpeg_errors: {line.rstrip()}")
                    if cnt > 5:
                        break

                    cnt += 1

            return return_code
        except Exception as exception:
            logging.error(f"_ffmpeg_errors. Error: {exception}")
            return return_code

    def _get_extension(self, filename):
        extension = "mp4"
        split_tup = os.path.splitext(filename)
        if len(split_tup) > 0 and len(split_tup[1]) > 0:
            extension = split_tup[1]
            extension = extension[1:]

        return extension

    def get_full_variant(self, variant):
        short_long_mapping = {
            "bal": "balear",
            "cen": "central",
            "val": "valencia",
            "nor": "nord",
        }
        return short_long_mapping.get(variant, "central")

    def run_inference(
        self,
        filename: str,  # e.g. fa05aee-79b9-4d0e-8683-e11b85dfe1a2
        timeout: int,
        variant: str,
        video_lang: str,
        operation: str,
        original_subtitles: bool,
        dubbed_subtitles: bool,
    ):
        logging.info(f"run_inference: {filename}")
        output_directory = OUTPUT_DIR
        filename_dir = os.path.dirname(filename)
        filename_uuid = os.path.basename(filename)
        output_dir_name = f"{filename_uuid}_output"

        update_operation = operation == "update"
        try:
            output_directory = os.path.join(filename_dir, output_dir_name)
            if not os.path.exists(output_directory):
                os.mkdir(output_directory)
        except Exception as exception:
            logging.error(
                f"run_inference. Error: Could not create output dir {exception}"
            )
        full_variant = self.get_full_variant(variant)

        if variant and len(video_lang) > 0 and video_lang != "auto":
            source_param = f"--source_language {video_lang}"
        else:
            source_param = ""

        temp_file_name = f"{output_directory}/original.mp4"
        shutil.copyfile(filename, temp_file_name)
        input_file = temp_file_name

        start_time = datetime.datetime.now()
        device = os.environ.get("DEVICE", "cpu")
        APERTIUM_SERVER = "http://dubbing-translator-proxy:8700/"
        TTS_URL = "http://matcha-service:8100/"
        # To control CPU usage "set OMP_NUM_THREADS=8 && set MKL_NUM_THREADS=8"
        original_subtitles = "--original_subtitles" if original_subtitles else ""
        # Hardcoded since we always offer the option to download them
        dubbed_subtitles = "--dubbed_subtitles"  # if dubbed_subtitles else ""
        update = "--update" if update_operation else ""
        cmd = f'set OMP_NUM_THREADS=8 && set MKL_NUM_THREADS=8 && open-dubbing --whisper_model medium --input_file "{input_file}" --output_directory="{output_directory}" --device={device} --translator=apertium --apertium_server={APERTIUM_SERVER} --target_language cat {source_param} --hugging_face_token NONE --tts_api_server {TTS_URL} --tts api --target_language_region {full_variant} {update} {original_subtitles} {dubbed_subtitles} --vad'
        result = Command(cmd).run(timeout=timeout)
        end_time = datetime.datetime.now() - start_time
        logging.debug(f"Run {cmd} in {end_time} with result {result}")

        output_filename = os.path.abspath(
            os.path.join(output_directory, "dubbed_video_cat.mp4")
        )

        cat_subtitles = os.path.abspath(os.path.join(output_directory, "cat.srt"))

        exec_dir = os.path.dirname(os.path.realpath(__file__))
        log_filename = os.path.abspath(os.path.join(exec_dir, "open_dubbing.log"))

        if os.path.exists(temp_file_name):
            os.remove(temp_file_name)

        return (
            end_time,
            result,
            output_filename,
            output_directory,
            cat_subtitles,
            log_filename,
        )
