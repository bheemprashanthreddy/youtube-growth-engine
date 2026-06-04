import json
from pathlib import Path
from urllib import request

from app.core.config import get_settings
from app.services.voice.base import VoiceProvider


class OpenAITTSVoiceProvider(VoiceProvider):
    name = "openai"

    def generate(self, text: str, output_path: str) -> bool:
        settings = get_settings()
        if not settings.openai_api_key or not settings.openai_tts_model or not settings.openai_tts_voice:
            return False
        try:
            payload = {
                "model": settings.openai_tts_model,
                "voice": settings.openai_tts_voice,
                "input": text,
                "response_format": "wav",
            }
            req = request.Request(
                "https://api.openai.com/v1/audio/speech",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Authorization": f"Bearer {settings.openai_api_key}", "Content-Type": "application/json"},
                method="POST",
            )
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with request.urlopen(req, timeout=45) as response:
                Path(output_path).write_bytes(response.read())
            return Path(output_path).exists() and Path(output_path).stat().st_size > 0
        except Exception:
            return False
