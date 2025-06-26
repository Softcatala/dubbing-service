FROM python:3.12.7-slim-bullseye AS copied_files

COPY dubbing-batch/*.py /srv/
COPY dubbing-batch/docker/entry-point.sh /srv/
COPY dubbing-batch/requirements.txt /srv/

FROM dubbing-models AS models
FROM nvidia/cuda:12.3.1-base-ubuntu22.04
RUN apt-get update -y && apt-get upgrade -y && apt-get install ffmpeg  git -y
RUN apt-get install python3-pip python3-dev -y --no-install-recommends

# Solve errors:
# - Error: Unable to load any of {libcudnn_ops.so.9.1.0, libcudnn_ops.so.9.1, libcudnn_ops.so.9, libcudnn_ops.so}
# - Error: RuntimeError: Library libcublas.so.12 is not found or cannot be loaded

RUN apt-get install libcudnn9-cuda-12 libcublas-12-3 -y

COPY --from=models /srv/models/huggingface/ /root/.cache/huggingface/
COPY --from=models /srv/models/torch/ /root/.cache/torch/

WORKDIR /srv

COPY --from=copied_files /srv/ /srv/
RUN pip3 install -r /srv/requirements.txt

WORKDIR /srv
ENTRYPOINT /srv/entry-point.sh
