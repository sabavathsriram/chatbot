FROM python:3.11-slim

# Install system dependencies for PyAudio and audio processing
RUN apt-get update && apt-get install -y \
    build-essential \
    portaudio19-dev \
    libasound-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY fastapi_server/requirements.txt ./fastapi_server/requirements.txt

RUN pip install --no-cache-dir -r fastapi_server/requirements.txt

COPY . .

# Now set working directory to fastapi_server
WORKDIR /app/fastapi_server

EXPOSE 8001

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]
