"""
Client for the Gnani Prisma speech-to-text API.

Endpoint: POST https://api.vachana.ai/stt/v3
"""
import logging
import os

import requests

logger = logging.getLogger(__name__)

PRISMA_URL = os.environ.get("VOICE2FLOW_PRISMA_URL") or os.environ.get("GNANI_PRISMA_URL", "https://api.vachana.ai/stt/v3")


def transcribe(
    audio_bytes: bytes,
    filename: str = "audio.m4a",
    language_code: str = "en-IN",
) -> str:
    """Send audio bytes to Prisma and return the transcribed text."""
    api_key = os.environ.get("GNANI_API_KEY")
    if not api_key:
        raise RuntimeError("Speech-to-text API key not set in environment (VOICE2FLOW_API_KEY or GNANI_API_KEY)")

    try:
        response = requests.post(
            PRISMA_URL,
            headers={"X-API-Key-ID": api_key},
            files={"audio_file": (filename, audio_bytes)},
            data={
                "model": "prisma-v3.0",
                "language_code": language_code,
                "format": "transcribe",
            },
            timeout=60,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise RuntimeError(f"Prisma API call failed: {exc}") from exc

    result = response.json()
    logger.debug("Prisma response received")
    if isinstance(result, dict):
        return (
            result.get("transcript")
            or result.get("text")
            or result.get("result", {}).get("transcript", "")
        ).strip()
    return str(result)
