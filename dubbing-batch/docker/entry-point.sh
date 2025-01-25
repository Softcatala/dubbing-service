if [ ! -z "$LOGDIR" ]
then
    mkdir -p $LOGDIR
fi
ffmpeg -version
python3 process-batch.py
