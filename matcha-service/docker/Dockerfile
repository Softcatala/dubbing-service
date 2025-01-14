FROM python:3.12.7-slim-bullseye AS copied_files
COPY matcha-service/*.py /srv/
COPY matcha-service/requirements.txt  /srv/
COPY matcha-service/Matcha-TTS/ /srv/Matcha-TTS
COPY matcha-service/docker/entry-point.sh /srv/


FROM dubbing-models AS models
FROM python:3.11.7-slim-bullseye

RUN apt-get update -y && apt-get upgrade -y && apt-get install ffmpeg git -y

RUN git clone https://github.com/espeak-ng/espeak-ng 
WORKDIR espeak-ng 
RUN git checkout 21ac2203a0b22f3816e21932feff8ae9c12eb78a
RUN apt-get install automake autoconf automake libtool pkg-config gcc make g++ virtualenv -y
RUN ./autogen.sh 
RUN ./configure --prefix=/usr
RUN make && make install

COPY --from=copied_files /srv/ /srv/
WORKDIR /srv

RUN cd Matcha-TTS && pip install -e .
RUN pip install -r requirements.txt 
RUN python -c 'from matcha_core import load_models; load_models()'

ENTRYPOINT /srv/entry-point.sh
