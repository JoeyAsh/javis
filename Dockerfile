FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    portaudio19-dev libsndfile1 ffmpeg alsa-utils pulseaudio-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN python -c "from faster_whisper import WhisperModel; WhisperModel('small')"

COPY . .

CMD ["python", "src/main.py"]
