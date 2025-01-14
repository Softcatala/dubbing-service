#!/usr/bin/env python3
# -*- encoding: utf-8 -*-
#
# Copyright (c) 2024 Jordi Mas i Hernandez <jmas@softcatala.org>
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

from flask import Flask, request, jsonify
import requests
import logging
import logging.handlers
import os


def init_logging():
    LOGDIR = os.environ.get("LOGDIR", "")
    LOGLEVEL = os.environ.get("LOGLEVEL", "INFO").upper()
    logger = logging.getLogger()
    logfile = os.path.join(LOGDIR, "dubbing-translator-proxy.log")
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


app = Flask(__name__)

APERTIUM_URL = "https://www.softcatala.org/api/traductor"
NMT_URL = "https://api.softcatala.org/sc/v2/api/nmt-engcat"


@app.route("/translate", methods=["GET"])
def translate():
    langpair = request.args["langpair"]

    if langpair == "spa|cat":
        service_url = APERTIUM_URL
    else:
        service_url = NMT_URL

    logging.debug(f"url: {service_url}")

    # Forward the request to the chosen service
    try:
        response = requests.get(service_url + "/translate", params=request.args)
        return jsonify(response.json())
    except requests.exceptions.RequestException as e:
        logging.error(f"/translate method - {service_url} - {langpair} - error: {e}")
        return jsonify({"error": str(e)}), 500


def _add_spa_cat_pair(pairs):
    pair = {"sourceLanguage": "spa", "targetLanguage": "cat"}

    if pair not in pairs:
        pairs.append(pair)

    return pairs


@app.route("/listPairs", methods=["GET"])
def list_pairs():

    try:
        response = requests.get(NMT_URL + "/listPairs", params=request.args)
        data = response.json()
        data["responseData"] = _add_spa_cat_pair(data["responseData"])
        logging.info("/listPairs")
        return jsonify(data)
    except requests.exceptions.RequestException as e:
        logging.error(f"/listPairs method. Error {e}")
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    #    app.debug = True
    init_logging()
    app.run()

if __name__ != "__main__":
    init_logging()
