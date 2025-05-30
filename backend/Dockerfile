FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y \
    build-essential \
    portaudio19-dev \
    libasound-dev \
    ffmpeg \
    libavcodec-dev \
    libavformat-dev \
    libswresample-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip

COPY fastapi_server/requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "fastapi_server.app:app", "--host", "0.0.0.0", "--port", "8000"]
