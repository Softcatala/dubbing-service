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

import logging
import os
from open_dubbing.utterance import Utterance
from pydantic import BaseModel, field_validator
from flask import request, make_response, Blueprint, send_file, jsonify
from processedfiles import ProcessedFiles
from batchfilesdb import BatchFilesDB
from typing import List, Dict, Any
from usage import Usage

UPLOAD_FOLDER = "/srv/data/files/"

bp = Blueprint("utterances_routes", __name__)


def _get_record(_uuid):
    processed_dir = ProcessedFiles.get_processed_directory()
    db = BatchFilesDB(processed_dir)
    return db._read_record_from_uuid(_uuid)


def _update_json(uuid, utterance_update):
    directory = os.path.join(ProcessedFiles.get_processed_directory(), uuid + "_output")
    utterance = Utterance(target_language="cat", output_directory=directory)
    utterance_master, preprocessing_output, metadata = utterance.load_utterances()
    utterance_update = utterance_update
    logging.debug(f"Update json: {utterance_update}")

    updated = utterance.update_utterances(utterance_master, utterance_update)

    utterance.save_utterances(
        utterance_metadata=updated,
        preprocessing_output=preprocessing_output,
        metadata=metadata,
        do_hash=False,
        unique_id=False,
    )


def _copy_files_to_upload_directory(uuid, video_file):
    processedfiles = ProcessedFiles(uuid)

    filename = uuid + ".mp4"
    processedfiles.copy_file_to(filename, video_file)

    # Copy output directory for reprocessing
    target = os.path.join(UPLOAD_FOLDER, f"{uuid}_output")
    processedfiles.copy_output_dir_to(target)


def _load_utterances(uuid):
    record = _get_record(uuid)
    if not record:
        raise ValueError(f"Cannot not find {uuid}")

    directory = os.path.join(ProcessedFiles.get_processed_directory(), uuid + "_output")
    utterance = Utterance(target_language="cat", output_directory=directory)
    utterance_data, _, metadata = utterance.load_utterances()
    return utterance_data, metadata


class Utterances(BaseModel):
    uuid: str

    @field_validator("uuid")
    def uuid_exists(cls, value: str):
        if not ProcessedFiles.is_valid_uuid(value):
            raise ValueError("uuid no vàlid")
        return value


@bp.route("/get_utterances", methods=["GET"])
def get_utterances():
    try:
        query_params = request.args.to_dict()
        utterances = Utterances(**query_params)
        utterance_data, _ = _load_utterances(utterances.uuid)

        Usage().log("get_utterances")
        return jsonify(utterance_data), 200

    except ValueError as e:
        logging.error(e)
        return jsonify({"error": f"{e}"}), 400


class UtteranceModel(BaseModel):
    uuid: str
    id: int

    @field_validator("uuid")
    def uuid_exists(cls, value: str):
        if not ProcessedFiles.is_valid_uuid(value):
            raise ValueError("uuid no vàlid")
        return value


@bp.route("/get_dubbed_utterance/", methods=["GET"])
def get_dubbed_utterance():
    try:
        logging.debug(f"/get_dubbed_utterance/ - {request.args.to_dict()}")
        query = UtteranceModel.model_validate(request.args.to_dict())

        utterance_data, _ = _load_utterances(query.uuid)

        utterance = None
        for u in utterance_data:
            if u["id"] == query.id:
                utterance = u
                break

        if not utterance:
            raise ValueError("id not found")

        fullname = utterance["dubbed_path"]
        target_path = ProcessedFiles.get_processed_directory()
        if not target_path.endswith("/"):
            target_path += "/"

        fullname = fullname.replace(UPLOAD_FOLDER, target_path)
        if not os.path.exists(fullname):
            result = {}
            result["error"] = "No existeix aquest fitxer. Potser ja s'esborrat."
            return jsonify(result), 404

        resp = make_response(
            send_file(fullname, as_attachment=True, mimetype="application/octet-stream")
        )
        resp.headers["Accept-Ranges"] = "bytes"
        resp.headers["Cross-Origin-Resource-Policy"] = "cross-origin"

        Usage().log("get_dubbed_utterance")
        return resp
    except ValueError as e:
        return jsonify({"error": f"{e}"}), 404


class Regenerate(BaseModel):
    uuid: str
    utterance_update: List[Dict[str, Any]]

    @field_validator("uuid")
    def uuid_exists(cls, value: str):
        if not ProcessedFiles.is_valid_uuid(value):
            raise ValueError("uuid no vàlid")
        return value


@bp.route("/regenerate_video", methods=["POST"])
def regenerate_video():
    try:
        _dict = request.get_json()
        regenerate = Regenerate.model_validate(_dict)
        logging.debug(f"/regenerate_video: {regenerate}")
        uuid = regenerate.uuid

        record = _get_record(uuid)
        if not record:
            raise ValueError(f"Cannot not find {uuid}")

        db = BatchFilesDB()
        queued_record = db.get_record_file_from_uuid(uuid)
        logging.debug(f"queued_record: {queued_record}")
        if os.path.exists(queued_record):
            raise ValueError(
                "Heu d'esperar que la generació que heu demanat finalitzi abans de poder demanar-ne un altre."
            )

        waiting_queue = len(db.select())
        _update_json(uuid, regenerate.utterance_update)

        fullname = os.path.join(UPLOAD_FOLDER, uuid)
        _copy_files_to_upload_directory(uuid, fullname)

        db.create(
            filename=fullname,
            email=record.email,
            variant=record.variant,
            original_filename=record.original_filename,
            video_lang=record.video_lang,
            record_uuid=uuid,
            operation="update",
            revision=record.revision + 1,
            original_subtitles=record.original_subtitles,
            dubbed_subtitles=record.dubbed_subtitles,
        )

        Usage().log("regenerate_video")
        result = {"waiting_queue": waiting_queue}
        return jsonify(result), 200

    except ValueError as e:
        logging.error(e)
        return jsonify({"error": f"{e}"}), 400


NAME_TO_FILENAME = {
    "original_video": "original_video.mp4",
    "vocals": "htdemucs/original_audio/vocals.mp3",
    "dubbed_vocals": "dubbed_vocals.mp3",
    "no_vocals": "htdemucs/original_audio/no_vocals.mp3",
}


class GetRegenerateFileQuery(BaseModel):
    uuid: str
    name: str

    @field_validator("uuid")
    def uuid_exists(cls, value: str):
        if not ProcessedFiles.is_valid_uuid(value):
            raise ValueError("uuid no vàlid")
        if not ProcessedFiles.output_dir_exists(value):
            raise ValueError("uuid no existeix")
        return value

    @field_validator("name")
    def name_is_valid(cls, value: str):
        if value not in NAME_TO_FILENAME:
            raise ValueError(f"Invalid name: {value}")
        return value

    def get_filename(self):
        return NAME_TO_FILENAME[self.name]


@bp.route("/get_regenerate_file/", methods=["GET"])
def get_regenerate_file():
    try:
        logging.debug(f"/get_regenerate_file/: {request.args.to_dict()}")
        query = GetRegenerateFileQuery.model_validate(request.args.to_dict())

        fullname = os.path.join(
            ProcessedFiles.get_processed_directory(),
            f"{query.uuid}_output",
            query.get_filename(),
        )

        if not os.path.exists(fullname):
            return (
                jsonify({"error": "No existeix aquest fitxer. Potser ja s'esborrat."}),
                400,
            )

        resp = make_response(
            send_file(fullname, as_attachment=True, mimetype="application/octet-stream")
        )
        resp.headers["Accept-Ranges"] = "bytes"
        resp.headers["Cross-Origin-Resource-Policy"] = "cross-origin"

        Usage().log("get_regenerate_file")
        return resp
    except ValueError as e:
        return jsonify({"error": f"{e}"}), 400


class Metadata(BaseModel):
    uuid: str

    @field_validator("uuid")
    def uuid_exists(cls, value: str):
        if not ProcessedFiles.is_valid_uuid(value):
            raise ValueError("uuid no vàlid")
        return value


@bp.route("/get_metadata", methods=["GET"])
def get_metadata():
    try:
        query_params = request.args.to_dict()
        utterances = Metadata(**query_params)
        _, metadata = _load_utterances(utterances.uuid)

        Usage().log("get_metadata")
        metadata = {"metadata": metadata}
        return jsonify(metadata), 200

    except ValueError as e:
        logging.error(e)
        return jsonify({"error": f"{e}"}), 400
