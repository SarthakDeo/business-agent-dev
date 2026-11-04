import os, requests
from dotenv import load_dotenv

load_dotenv("../../.env")   # .env is two folders up

API_KEY = os.environ["GNANI_API_KEY"]

with open("test.m4a", "rb") as f:
    r = requests.post(
        "https://api.vachana.ai/stt/v3",
        headers={"X-API-Key-ID": API_KEY},
        files={"audio_file": ("test1.m4a", f)},
        data={
            "model": "prisma-v3.0",
            "language_code": "en-IN",
            "format": "transcribe",
        },
        timeout=60,
    )

print(r.status_code)
print(r.json())