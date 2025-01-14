#!/usr/bin/env python
# -*- encoding: utf-8 -*-
#
# Copyright (c) 2016 Jordi Mas i Hernandez <jmas@softcatala.org>
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


from flask import Flask, request, Response, send_file, jsonify
import tempfile
import sys
import torch
import logging
import logging.handlers
import os
import json
from functools import lru_cache

sys.path.append("Matcha-TTS/")

from matcha_core import (
    load_models,
    get_cleaner_for_speaker_id,
    tts,
)

app = Flask(__name__)


# Load model
MULTIACCENT_MODEL = "projecte-aina/matxa-tts-cat-multiaccent"
DEFAULT_CLEANER = "catalan_cleaners"

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
threads = torch.get_num_threads()
torch.set_num_threads(8)
threads = torch.get_num_threads()

model, vocos_vocoder = load_models()


def init_logging():
    LOGDIR = os.environ.get("LOGDIR", "")
    LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
    logger = logging.getLogger()
    logfile = os.path.join(LOGDIR, "matcha-service.log")
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


@app.route("/speak/", methods=["GET"])
def voice_api():

    text = request.args.get("text")
    voice = request.args.get("voice")

    if not text:
        result = {}
        result["error"] = "cal el paràmetre 'text'"
        return json_answer(result, 400)

    if not voice:
        result = {}
        result["error"] = "cal el paràmetre 'voice'"
        return json_answer(result, 400)

    if str(voice) not in get_voice_ids():
        result = {}
        result["error"] = f"paràmetre voice '{voice}' no conegut"
        return json_answer(result, 400)

    cleaner = ""
    spk_id = None

    try:
        with tempfile.NamedTemporaryFile(suffix=".wav") as temp_file:

            # Get the name of the file for later use
            filename = temp_file.name

            spk_id = int(voice)
            cleaner = get_cleaner_for_speaker_id(spk_id)
            logging.debug(f"Speak {text} - {spk_id} - {cleaner}")
            tts(
                text,
                spk_id,
                output_filename=filename,
                cleaner=cleaner,
                model=model,
                vocos_vocoder=vocos_vocoder,
            )

            return send_file(
                filename,
                mimetype="audio/wav",
                as_attachment=False,
                download_name=filename,
            )

    except Exception as e:
        logging.error(f"Speak {text} - {spk_id} - {cleaner}")
        logging.error(e)
        return json_answer({"error": str(e)}, status=500)


def json_answer(data, status=200):
    json_data = json.dumps(data, indent=4, separators=(",", ": "))
    resp = Response(json_data, mimetype="application/json", status=status)
    resp.headers["Access-Control-Allow-Origin"] = "*"
    return resp


@lru_cache(maxsize=1)
def get_voice_ids():
    return {voice["id"] for voice in _get_voice_data()}


def _get_voice_data():
    return [
        {
            "name": "quim-balear",
            "id": "0",
            "gender": "male",
            "language": "cat",
            "region": "balear",
        },
        {
            "name": "olga-balear",
            "id": "1",
            "gender": "female",
            "language": "cat",
            "region": "balear",
        },
        {
            "name": "grau-central",
            "id": "2",
            "gender": "male",
            "language": "cat",
            "region": "central",
        },
        {
            "name": "elia-central",
            "id": "3",
            "gender": "female",
            "language": "cat",
            "region": "central",
        },
        {
            "name": "pere-nord",
            "id": "4",
            "gender": "male",
            "language": "cat",
            "region": "nord",
        },
        {
            "name": "emma-nord",
            "id": "5",
            "gender": "female",
            "language": "cat",
            "region": "nord",
        },
        {
            "name": "lluc-valencia",
            "id": "6",
            "gender": "male",
            "language": "cat",
            "region": "valencia",
        },
        {
            "name": "gina-valencia",
            "id": "7",
            "gender": "female",
            "language": "cat",
            "region": "valencia",
        },
    ]


@app.route("/voices/", methods=["GET"])
def list_voices_api():
    voices = _get_voice_data()
    logging.debug(f"voices: {voices}")
    return jsonify(voices)


if __name__ == "__main__":
    #    app.debug = True
    init_logging()
    app.run()

if __name__ != "__main__":
    init_logging()
