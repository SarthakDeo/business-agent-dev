"""
prisma_client.py
Client for Gnani Prisma speech-to-text API.
Endpoint: POST https://api.vachana.ai/stt/v3
"""
import os
import logging
import requests

logger = logging.getLogger(__name__)

PRISMA_URL = os.environ.get("GNANI_PRISMA_URL", "https://api.vachana.ai/stt/v3")


def transcribe(audio_bytes: bytes, filename: str = "audio.m4a", language_code: str = "en-IN") -> str:
    """
    Send audio bytes to Gnani Prisma for speech-to-text transcription.
    
    Args:
        audio_bytes: Raw audio file bytes.
        filename: Original filename (used for content-type detection).
        language_code: Language code (default: en-IN).
    
    Returns:
        Transcribed text string.
    
    Raises:
        RuntimeError: If Prisma API call fails.
    """
    api_key = os.environ.get("GNANI_API_KEY")
    if not api_key:
        raise RuntimeError("GNANI_API_KEY not set in environment")

    headers = {"X-API-Key-ID": api_key}

    files = {"audio_file": (filename, audio_bytes)}
    data = {
        "model": "prisma-v3.0",
        "language_code": language_code,
        "format": "transcribe",
    }

    try:
        resp = requests.post(PRISMA_URL, headers=headers, files=files, data=data, timeout=60)
        resp.raise_for_status()
    except requests.RequestException as e:
        raise RuntimeError(f"Prisma API call failed: {e}") from e

    result = resp.json()
    logger.debug(f"Prisma response: {result}")

    # Extract transcript text — handle common Gnani response shapes
    if isinstance(result, dict):
        transcript = (
            result.get("transcript")
            or result.get("text")
            or result.get("result", {}).get("transcript", "")
        )
        return transcript.strip()
    
    return str(result)
