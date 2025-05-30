import pyaudio
import wave
from pydub import AudioSegment
from google.cloud import speech
import logging
import os
import json
from google.api_core.exceptions import GoogleAPIError
from dotenv import load_dotenv

# Load environment variables from .env file (for local development)
load_dotenv(dotenv_path=r"D:\OneDrive\Desktop\projects\chatbot\backend\.env")

# Configuration
SERVICE_ACCOUNT_KEY = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
RAW_AUDIO_FILE = os.getenv("RAW_AUDIO_FILE", "raw_audio.wav")
CONVERTED_AUDIO_FILE = os.getenv("CONVERTED_AUDIO_FILE", "converted.wav")
RECORD_SECONDS = 4

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Handle Google Cloud credentials for Render
if os.getenv("GOOGLE_CREDENTIALS"):
    # Render provides credentials as an environment variable
    credentials_path = "/app/kmitstt-34483a53f9e8.json"
    try:
        with open(credentials_path, "w") as f:
            json.dump(json.loads(os.getenv("GOOGLE_CREDENTIALS")), f)
        SERVICE_ACCOUNT_KEY = credentials_path
        logger.info(f"Wrote Google Cloud credentials to {credentials_path}")
    except Exception as e:
        logger.error(f"Failed to write Google Cloud credentials: {str(e)}")
        raise

# Verify Google Cloud credentials
if not SERVICE_ACCOUNT_KEY:
    logger.error("GOOGLE_APPLICATION_CREDENTIALS not found in environment variables")
    raise ValueError("GOOGLE_APPLICATION_CREDENTIALS must be set")
if not os.path.isfile(SERVICE_ACCOUNT_KEY):
    logger.error(f"Service account key file not found at: {SERVICE_ACCOUNT_KEY}")
    raise FileNotFoundError(f"Service account key file not found at: {SERVICE_ACCOUNT_KEY}")

# Set Google Cloud credentials
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = SERVICE_ACCOUNT_KEY
logger.info(f"Set GOOGLE_APPLICATION_CREDENTIALS to: {SERVICE_ACCOUNT_KEY}")

def record_audio(output_filename=RAW_AUDIO_FILE, record_seconds=RECORD_SECONDS):
    chunk = 1024
    sample_format = pyaudio.paInt16
    channels = 1
    rate = 44100

    p = pyaudio.PyAudio()
    logger.info("🎤 Recording...")
    stream = p.open(
        format=sample_format,
        channels=channels,
        rate=rate,
        frames_per_buffer=chunk,
        input=True
    )

    frames = []
    for _ in range(0, int(rate / chunk * record_seconds)):
        data = stream.read(chunk, exception_on_overflow=False)
        frames.append(data)

    stream.stop_stream()
    stream.close()
    p.terminate()

    wf = wave.open(output_filename, 'wb')
    wf.setnchannels(channels)
    wf.setsampwidth(p.get_sample_size(sample_format))
    wf.setframerate(rate)
    wf.writeframes(b''.join(frames))
    wf.close()
    logger.info(f"✅ Recording saved as: {output_filename}")
    return output_filename

def convert_to_16khz_mono(input_wav=RAW_AUDIO_FILE, output_wav=CONVERTED_AUDIO_FILE):
    logger.info("🔄 Converting to 16kHz mono WAV...")
    audio = AudioSegment.from_wav(input_wav)
    converted = audio.set_frame_rate(16000).set_channels(1)
    converted.export(output_wav, format="wav")
    logger.info(f"✅ Converted audio saved as: {output_wav}")
    return output_wav

def transcribe_with_google(wav_file=CONVERTED_AUDIO_FILE):
    logger.info("🧠 Transcribing using Google Speech-to-Text API...")
    try:
        client = speech.SpeechClient()
        with open(wav_file, "rb") as f:
            content = f.read()
        audio = speech.RecognitionAudio(content=content)
        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=16000,
            language_code="en-US"
        )
        response = client.recognize(config=config, audio=audio)
        transcriptions = []
        for result in response.results:
            for alternative in result.alternatives:
                transcriptions.append(alternative.transcript)
                logger.info(f"👉 {alternative.transcript}")
        transcription = " ".join(transcriptions)
        logger.info(f"📝 Transcription result: {transcription}")
        return transcription if transcription else "No speech detected"
    except GoogleAPIError as e:
        logger.error(f"Google API error: {str(e)}", exc_info=True)
        return f"Transcription failed: {str(e)}"
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        return "No speech detected"

if __name__ == "__main__":
    recorded_file = record_audio()
    converted_file = convert_to_16khz_mono(recorded_file)
    transcription = transcribe_with_google(converted_file)
    print(f"Transcription: {transcription}")
