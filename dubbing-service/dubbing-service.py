#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
#
# Copyright (c) 2022-2024 Jordi Mas i Hernandez <jmas@softcatala.org>
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
from flask import Flask, request, Response, send_file, make_response, jsonify
from flask_cors import CORS
import json
from batchfilesdb import BatchFilesDB
from processedfiles import ProcessedFiles
import os
import logging
import logging.handlers
from usage import Usage
import datetime
from urllib.parse import quote
import unicodedata
from sendmail import Sendmail
from pydub import AudioSegment
import requests
from urllib.parse import urljoin
from utterances import bp

app = Flask(__name__)

# Access-Control-Allow-Origin header is defined here for all endpoints
CORS(app, resources={r"/*": {"origins": "*"}})

UPLOAD_FOLDER = "/srv/data/files/"


app.register_blueprint(bp)


@app.route("/hello", methods=["GET"])
def hello_word():
    return "Hello dubbing-service!"


def _hide_emails(records):
    who = {
        record.email: sum(1 for r in records if r.email == record.email)
        for record in records
    }

    print_who = {
        "".join(list(map(lambda c: "-" if c in ["a"] else c, key))): value
        for key, value in who.items()
    }
    return print_who


@app.route("/stats/", methods=["GET"])
def stats():
    requested = request.args.get("date", datetime.datetime.today().strftime("%Y-%m-%d"))
    try:
        date_requested = datetime.datetime.strptime(requested, "%Y-%m-%d")
    except Exception:
        return json_answer({}, 400)

    usage = Usage()
    result = usage.get_stats(date_requested)

    records = BatchFilesDB().select()
    queue = {}

    print_who = _hide_emails(records)
    result["files_stored"] = ProcessedFiles.get_num_of_files_stored()
    result["files_stored_size"] = ProcessedFiles.get_num_of_files_stored_size()
    result["free_storage_space"] = ProcessedFiles.get_free_space_in_directory()
    queue["items"] = len(records)
    queue["who"] = print_who
    result["queue"] = queue

    stored = {}
    db = BatchFilesDB()
    db.ENTRIES = ProcessedFiles.get_processed_directory()
    records = db.select()
    print_who = _hide_emails(records)
    stored["items"] = len(records)
    stored["who"] = print_who
    result["stored"] = stored

    return json_answer(result)


def init_logging():
    LOGDIR = os.environ.get("LOGDIR", "")
    LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
    logger = logging.getLogger()
    logfile = os.path.join(LOGDIR, "dubbing-service.log")
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


@app.route("/uuid_exists/", methods=["GET"])
def uuid_exists():
    uuid = request.args.get("uuid", "")

    if uuid == "":
        result = {}
        result["error"] = "No s'ha especificat el uuid"
        return json_answer(result, 404)

    if not ProcessedFiles.is_valid_uuid(uuid):
        result = {}
        result["error"] = "uuid no vàlid"
        return json_answer(result, 400)

    exists, result_msg = ProcessedFiles.do_files_exists(uuid)
    result_code = 200 if exists else 404
    return json_answer(result_msg, result_code)


ALLOWED_MIMEYPES = {"mp4": "video/mp4"}


def _allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_MIMEYPES.keys()
    )


def _get_mimetype(extension):
    mimetype = ALLOWED_MIMEYPES.get(extension)

    if not mimetype:
        if extension == "txt":
            mimetype = "text/plain"
        elif extension == "json":
            mimetype = "application/json"
        else:
            mimetype = "application/octet-stream"

    return mimetype


def _get_record(_uuid):
    processed_dir = ProcessedFiles.get_processed_directory()
    db = BatchFilesDB(processed_dir)
    return db._read_record_from_uuid(_uuid)


# Reference: https://github.com/pallets/werkzeug/blob/main/src/werkzeug/utils.py#L454
def _get_download_names(download_name, ext):
    simple = unicodedata.normalize("NFKD", download_name)
    simple = simple.encode("ascii", "ignore").decode("ascii")
    # safe = RFC 5987 attr-char
    quoted = quote(download_name, safe="!#$&+-.^_`|~")
    names = f"filename=\"{simple}.{ext}\"; filename*=UTF-8''{quoted}.{ext}"
    logging.info(f"_get_download_names: {download_name}, {ext} -  {names}")
    return names


@app.route("/get_file/", methods=["GET"])
def get_file():
    uuid = request.args.get("uuid", "")
    ext = request.args.get("ext", "")

    if ext == "":
        result = {}
        result["error"] = "No s'ha especificat l'extensió"
        logging.debug(f"/get_file/ {result['error']}")
        return json_answer(result, 404)

    if uuid == "":
        result = {}
        result["error"] = "No s'ha especificat el uuid"
        logging.debug(f"/get_file/ {result['error']}")
        return json_answer(result, 404)

    if not ProcessedFiles.is_valid_uuid(uuid):
        result = {}
        result["error"] = "uuid no vàlid"
        logging.debug(f"/get_file/ {result['error']} - uuid: '{uuid}'")
        return json_answer(result, 400)

    exists, _ = ProcessedFiles.do_files_exists(uuid)
    if not exists:
        result = {"error": "uuid no existeix"}
        logging.debug(f"/get_file/ {result['error']} - uuid: '{uuid}'")
        return json_answer(result, 404)

    record = _get_record(uuid)
    original_name, original_ext = os.path.splitext(record.original_filename)

    if ext == "bin":
        ext = original_ext[1:]

    fullname = os.path.join(ProcessedFiles.get_processed_directory(), uuid)
    fullname = f"{fullname}.{ext}"

    if not os.path.exists(fullname):
        result = {}
        result["error"] = "No existeix aquest fitxer. Potser ja s'esborrat."
        return json_answer(result, 404)

    if ext == "dub":
        ext = original_ext[1:]

    filenames = _get_download_names(original_name, ext)
    mime_type = _get_mimetype(ext)
    resp = make_response(send_file(fullname, as_attachment=True, mimetype=mime_type))
    resp.headers["Content-Disposition"] = f"attachment; {filenames}"
    resp.headers["Accept-Ranges"] = "bytes"
    resp.headers["Access-Control-Expose-Headers"] = "Content-Disposition"
    resp.headers["Cross-Origin-Resource-Policy"] = "cross-origin"

    Usage().log("get_file")
    return resp


QUEUE_CAPACITY = int(os.environ.get("QUEUE_CAPACITY", "150"))
MAX_SIZE = int(os.environ.get("MAX_SIZE", 1024 * 1024 * 1024))  # 1GB by default
MAX_PER_EMAIL = int(os.environ.get("MAX_PER_EMAIL", "3"))


@app.route("/feedback_form/", methods=["POST"])
def feedback_form():
    if len(request.values) == 0:
        result = {"error": "No s'han especificat els camps"}
        return json_answer(result, 404)

    uuid = request.values.get("uuid", "")

    if uuid == "":
        result = {}
        result["error"] = "No s'ha especificat el uuid"
        return json_answer(result, 404)

    message = ""

    record = _get_record(uuid)
    email = record.email
    message += f"email: {email}\n"

    for key in request.values.keys():
        value = request.values[key]
        message += f"{key}: {value}\n"

    Sendmail().send(
        message, "jmas@softcatala.org", "Comentari del servei de doblatge de Softcatalà"
    )
    logging.info(f"Sent feedback from '{email}'")
    return json_answer([])


def get_video_duration_ms(video_file):
    try:
        audio = AudioSegment.from_file(video_file)
        duration = len(audio)
        return duration

    except Exception as e:
        logging.error(f"Could not get video duration for '{video_file}'")
        logging.error(e)
        return 0


@app.route("/dubbing_file/", methods=["POST"])
def upload_file():
    file = request.files["file"] if "file" in request.files else ""
    email = request.values["email"] if "email" in request.values else ""
    variant = request.values["variant"] if "variant" in request.values else ""
    video_lang = request.values["video_lang"] if "video_lang" in request.values else ""
    original_subtitles = request.values.get("original_subtitles") == "on"
    dubbed_subtitles = request.values.get("dubbed_subtitles") == "on"

    if file == "" or file.filename == "":
        result = {"error": "No s'ha especificat el fitxer"}
        return json_answer(result, 404)

    if email == "":
        result = {"error": "No s'ha especificat el correu"}
        return json_answer(result, 404)

    if not _allowed_file(file.filename):
        result = {"error": "Tipus de fitxer no vàlid"}
        return json_answer(result, 415)

    if request.content_length and request.content_length > MAX_SIZE:
        result = {"error": "El fitxer és massa gran"}
        logging.info(f"/dubbing_file/ {result['error']} - {email}")
        return json_answer(result, 413)

    db = BatchFilesDB()
    if db.count() >= QUEUE_CAPACITY:
        result = {
            "error": "Hi ha massa fitxers a la cua de processament. Proveu-ho en una estona"
        }
        logging.info(f"/dubbing_file/ {result['error']} - {email}")
        Usage().log("queue_full_response")
        return json_answer(result, 429)

    if len(db.select(email=email)) >= MAX_PER_EMAIL:
        result = {
            "error": f"Ja teniu {MAX_PER_EMAIL} fitxers a la cua. Espereu-vos que es processin per enviar-ne de nous."
        }
        logging.info(f"/dubbing_file/ {result['error']} - {email}")
        Usage().log("queue_max_per_mail")
        return json_answer(result, 429)

    waiting_queue = len(db.select())
    _uuid = db.get_new_uuid()
    fullname = os.path.join(UPLOAD_FOLDER, _uuid)
    file.save(fullname)

    MAX_TIME_MIN = 70
    video_len_ms = get_video_duration_ms(fullname)
    if video_len_ms >= MAX_TIME_MIN * 60 * 1000:
        result = {
            "error": f"No s'ha acceptat el vídeo, ja que dura més de {MAX_TIME_MIN} minuts que és el màxim permès"
        }
        logging.info(f"/dubbing_file/ {result['error']} - {email}")
        Usage().log("max_time")
        os.remove(fullname)
        return json_answer(result, 429)

    db.create(
        fullname,
        email=email,
        variant=variant,
        original_filename=file.filename,
        video_lang=video_lang,
        record_uuid=_uuid,
        original_subtitles=original_subtitles,
        dubbed_subtitles=dubbed_subtitles,
    )

    size_mb = os.path.getsize(fullname) / 1024 / 1024
    logging.info(
        f"Saved file {file.filename} to {fullname} (size: {size_mb:.2f}MB) for user {email}, waiting_queue: {waiting_queue}"
    )
    Usage().log("dubbing_file")
    result = {"waiting_queue": str(waiting_queue), "filename": file.filename, "uuid": _uuid}
    return json_answer(result)


TTS_URL = "http://matcha-service:8100/"


@app.route("/speak/", methods=["GET"])
def voice_api():
    try:
        url = urljoin(TTS_URL, "speak/")
        response = requests.get(url, params=request.args)
        mimetype = response.headers.get("Content-Type", "audio/wav")

        return Response(
            response.content, status=response.status_code, mimetype=mimetype
        )

    except requests.exceptions.RequestException as e:
        logging.error(e)
        return jsonify({"error": str(e)}), 500


@app.route("/voices/", methods=["GET"])
def list_voices_api():
    try:
        url = urljoin(TTS_URL, "voices/")
        response = requests.get(url, params=request.args)
        mimetype = response.headers.get("Content-Type", "audio/json")

        return Response(
            response.content, status=response.status_code, mimetype=mimetype
        )

    except requests.exceptions.RequestException as e:
        logging.error(e)
        return jsonify({"error": str(e)}), 500


def json_answer(data, status=200):
    json_data = json.dumps(data, indent=4, separators=(",", ": "))
    resp = Response(json_data, mimetype="application/json", status=status)
    return resp


if __name__ == "__main__":
    #    app.debug = True
    init_logging()
    app.run()

if __name__ != "__main__":
    init_logging()
