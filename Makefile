.PHONY: docker-build-dubbing-models docker-build-dubbing-service docker-build-dubbing-batch docker-run test get-models benchmark-run install-dev-tools run-check-code docker-build-dubbing-translator-proxy matcha-service

build-all: docker-build-dubbing-models docker-build-dubbing-service docker-build-dubbing-batch docker-build-dubbing-translator-proxy docker-build-matcha-service
	docker image ls | grep dubbing

docker-build-dubbing-models:
	docker build --rm --build-arg HF_TOKEN=$(HF_TOKEN) -t dubbing-models . -f dubbing-batch/docker/Dockerfile-models;
	
docker-build-dubbing-service:
	docker build --rm -t dubbing-service . -f dubbing-service/docker/Dockerfile;

docker-build-dubbing-batch: docker-build-dubbing-models
	docker build --rm -t dubbing-batch . -f dubbing-batch/docker/Dockerfile;
	docker image ls | grep dubbing

docker-build-dubbing-translator-proxy:
	docker build --rm -t dubbing-translator-proxy . -f dubbing-translator-proxy/docker/Dockerfile;

docker-build-matcha-service:
	docker build --rm -t matcha-service . -f matcha-service/docker/Dockerfile;

docker-run:
	docker-compose -f local.yml up;

test:
	cd dubbing-batch && python -m nose2

get-models:
	@if [ -z "$(HF_TOKEN)" ]; then \
		echo "HF_TOKEN is not defined. Please set it before running this Makefile."; \
		exit 1; \
  fi
	python3 -c 'from faster_whisper import WhisperModel; WhisperModel("medium")'
	python3 -c 'from open_dubbing.voice_gender_classifier import VoiceGenderClassifier; VoiceGenderClassifier();'
	python3 -c 'from pyannote.audio import Pipeline; import os; Pipeline.from_pretrained("pyannote/speaker-diarization-3.1", use_auth_token=os.environ["HF_TOKEN"])'

install-dev-tools:
	pip install -r requirements-dev.txt

run-format-code:
	python -m black dubbing-batch/ dubbing-service/ dubbing-translator-proxy/  matcha-service/*.py
	python -m flake8 --ignore E501,W503 dubbing-batch/ dubbing-service/ dubbing-translator-proxy/  matcha-service/*.py
