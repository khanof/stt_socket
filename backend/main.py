from fastapi import FastAPI, WebSocket
from starlette.websockets import WebSocketState
import asyncio
import numpy as np
from faster_whisper import WhisperModel
import logging
import os
from datetime import datetime
import soundfile as sf

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("logs/app.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI()
model = WhisperModel(
    os.getenv("WHISPER_MODEL", "base"),
    device="cpu",
    compute_type="int8"
)

@app.on_event("startup")
async def startup_event():
    logger.info("Backend started. Whisper model loaded: %s", os.getenv("WHISPER_MODEL", "tiny"))

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("New WebSocket connection established")
    
    try:
        while True:
            start_time = datetime.now()
            audio_data = await websocket.receive_bytes()
            logger.info("Received audio chunk of size: %d bytes", len(audio_data))

            if len(audio_data) < 1000:
                logger.warning("Audio chunk too small, skipping")
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_text("Audio chunk too small")
                continue

            # Process raw PCM audio (16-bit, 16kHz)
            try:
                audio_np = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32768.0
                logger.info("Audio processed: duration=%.2fs, sample_rate=16000, array_length=%d",
                            len(audio_np) / 16000, len(audio_np))

                # Save WAV for debugging
                wav_filename = f"logs/chunk_{start_time.strftime('%Y%m%d_%H%M%S')}.wav"
                sf.write(wav_filename, audio_np, 16000)
                logger.debug("Saved WAV audio to %s", wav_filename)

                # Check audio energy (RMS)
                rms = np.sqrt(np.mean(audio_np ** 2))
                logger.info("Audio RMS: %.4f", rms)
                if rms < 0.01:
                    logger.warning("Audio appears silent (RMS=%.4f), skipping transcription", rms)
                    if websocket.client_state == WebSocketState.CONNECTED:
                        await websocket.send_text(".")
                    continue

            except Exception as e:
                logger.error("Failed to process audio data: %s", str(e))
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_text("Error processing audio")
                continue

            # Transcribe with Faster-Whisper
            try:
                segments, info = model.transcribe(audio_np, beam_size=5, language="en")
                text = " ".join(segment.text for segment in segments).strip()
                logger.info("Transcription completed: '%s' (language=%s, probability=%.2f)",
                            text, info.language, info.language_probability)
                if not text:
                    logger.warning("Transcription empty - audio may be unclear")
            except Exception as e:
                logger.error("Transcription failed: %s", str(e))
                if websocket.client_state == WebSocketState.CONNECTED:
                    await websocket.send_text("Error during transcription")
                continue

            # Send result back if connection is still open
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.send_text(text)
                end_time = datetime.now()
                latency = (end_time - start_time).total_seconds() * 1000
                logger.info("Sent transcription back, latency: %.2f ms", latency)
            else:
                logger.warning("WebSocket closed before sending transcription")
                break

    except Exception as e:
        logger.error("WebSocket error: %s", str(e))
    finally:
        if websocket.client_state == WebSocketState.CONNECTED:
            await websocket.close()
        logger.info("WebSocket connection closed")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Backend shutting down")