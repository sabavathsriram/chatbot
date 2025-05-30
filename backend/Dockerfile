FROM python:3.11-slim

# Install system dependencies for PyAudio and audio processing
RUN apt-get update && apt-get install -y \
    build-essential \
    portaudio19-dev \
    libasound-dev \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements.txt (adjust path if needed)
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy all application code (adjust as needed)
COPY . .

# Expose port (match your CMD)
EXPOSE 8001

# Command to run the FastAPI application (adjust path if needed)
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8001"]
