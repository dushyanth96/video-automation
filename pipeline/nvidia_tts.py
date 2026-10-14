"""NVIDIA Magpie TTS (free tier) — Leo & Alex voices.
Uses the hosted NVCF function endpoint with the same NVIDIA_NIM_API_KEY.
No extra deps (urllib only). Output: 44.1kHz LINEAR_PCM WAV.
"""
import os
import uuid
import urllib.request
import urllib.error

from pipeline.env import load_project_env
load_project_env()

TTS_URL = os.getenv(
    "NVIDIA_TTS_URL",
    "https://877104f7-e885-42b9-8de8-f6e4c6303969.invocation.api.nvcf.nvidia.com/v1/audio/synthesize",
)
VOICE_LEO = os.getenv("NVIDIA_TTS_VOICE_LEO", "Magpie-Multilingual.EN-US.Jason.Happy")
VOICE_ALEX = os.getenv("NVIDIA_TTS_VOICE_ALEX", "Magpie-Multilingual.EN-US.Jason")
TEMPO_LEO = float(os.getenv("NVIDIA_TTS_TEMPO_LEO", "1.05"))
TEMPO_ALEX = float(os.getenv("NVIDIA_TTS_TEMPO_ALEX", "1.12"))
# PITCH > 1.0 = higher cartoon voice (asetrate). 1.0 = natural.
PITCH_LEO = float(os.getenv("NVIDIA_TTS_PITCH_LEO", "1.0"))
PITCH_ALEX = float(os.getenv("NVIDIA_TTS_PITCH_ALEX", "1.0"))

def synth(text: str, voice: str, out_path: str, sample_rate: int = 44100,
          retries: int = 3) -> str:
    import time
    last_err: Exception | None = None
    for attempt in range(retries):
        try:
            return _synth_once(text, voice, out_path, sample_rate)
        except Exception as e:
            last_err = e
            print(f"  [nvidia-tts retry {attempt + 1}/{retries}] {type(e).__name__}")
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"NVIDIA TTS failed after {retries} tries: {last_err}")

def _synth_once(text: str, voice: str, out_path: str, sample_rate: int = 44100) -> str:
    api_key = os.getenv("NVIDIA_NIM_API_KEY", "")
    if not api_key:
        raise RuntimeError("NVIDIA_NIM_API_KEY missing (needed for NVIDIA TTS too).")
    boundary = uuid.uuid4().hex
    fields = {"text": text, "language": "en-US", "voice": voice,
              "encoding": "LINEAR_PCM", "sample_rate_hz": str(sample_rate)}
    body = b""
    for k, v in fields.items():
        body += (f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n').encode()
    body += f"--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        TTS_URL, data=body, method="POST",
        headers={"Authorization": f"Bearer {api_key}",
                 "Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            raw = r.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"NVIDIA TTS HTTP {e.code}: {e.read().decode()[:300]}")
    if len(raw) < 5000:
        raise RuntimeError(f"NVIDIA TTS returned suspiciously small audio ({len(raw)}B)")
    with open(out_path, "wb") as f:
        f.write(raw)
    return out_path
