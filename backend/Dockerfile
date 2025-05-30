# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies for PyAudio, pydub, and google-cloud-speech
RUN apt-get update && apt-get install -y \
    portaudio19-dev \
    ffmpeg \
    libavcodec-dev \
    libavformat-dev \
    libswresample-dev \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --upgrade pip

# Copy requirements.txt from fastapi_server directory
COPY fastapi_server/requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the backend application code
COPY . .

# Expose the port
EXPOSE 8000

# Command to run the FastAPI application
CMD ["uvicorn", "fastapi_server.app:app", "--host", "0.0.0.0", "--port", "8000"]