FROM python:3.12.7-slim-bullseye AS copied_files

COPY dubbing-translator-proxy/*.py /srv/
COPY dubbing-translator-proxy/docker/entry-point.sh /srv/


FROM python:3.12.7-slim-bullseye

RUN apt-get update -y && apt-get upgrade -y

COPY dubbing-translator-proxy/requirements.txt /srv/
WORKDIR /srv
RUN pip3 install -r requirements.txt

COPY --from=copied_files /srv/ /srv/

EXPOSE 8700

ENTRYPOINT /srv/entry-point.sh

