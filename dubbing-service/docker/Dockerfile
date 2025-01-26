FROM python:3.12.7-slim-bullseye AS copied_files

COPY dubbing-service/*.py /srv/
COPY dubbing-service/docker/entry-point.sh /srv/


FROM python:3.12.7-slim-bullseye

RUN apt-get update -y && apt-get upgrade -y && apt-get install ffmpeg git  -y
RUN pip3 install --upgrade pip && pip3 install --upgrade setuptools

COPY dubbing-service/requirements.txt /srv/
WORKDIR /srv
RUN pip3 install -r requirements.txt
RUN pip install git+https://github.com/softcatala/open-dubbing@main --no-deps 

COPY --from=copied_files /srv/ /srv/

EXPOSE 8700

ENTRYPOINT /srv/entry-point.sh

