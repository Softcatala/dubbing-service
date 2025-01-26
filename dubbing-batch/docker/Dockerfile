FROM python:3.12.7-slim-bullseye AS copied_files

COPY dubbing-batch/*.py /srv/
COPY dubbing-batch/docker/entry-point.sh /srv/
COPY dubbing-batch/requirements.txt /srv/

FROM dubbing-models AS models
FROM nvidia/cuda:12.3.1-base-ubuntu22.04
RUN apt-get update -y && apt-get upgrade -y && apt-get install ffmpeg  git -y
RUN apt-get install python3-pip python3-dev -y --no-install-recommends

# Solve errors:
# - Error: libcudnn_ops_infer.so.8: cannot open shared object file: No such file or directory
# - Error: libcublasLt.so.11: cannot open shared object file: No such file or directory
RUN apt-get install libcudnn8=8.8.1.3-1+cuda11.8 && apt-get install libcublas-12-3 &&  apt-get install libcublas-11-8 -y

COPY --from=models /srv/models/huggingface/ /root/.cache/huggingface/
COPY --from=models /srv/models/torch/ /root/.cache/torch/

WORKDIR /srv

COPY --from=copied_files /srv/ /srv/
RUN pip3 install -r /srv/requirements.txt

# Temporary fix until moviepy 2.13 is released
RUN pip3 uninstall -y moviepy
RUN git clone https://github.com/Zulko/moviepy.git moviepy
RUN cd moviepy && pip install -e .
RUN python3 -c "import moviepy; print(moviepy.__version__)"

WORKDIR /srv
ENTRYPOINT /srv/entry-point.sh
