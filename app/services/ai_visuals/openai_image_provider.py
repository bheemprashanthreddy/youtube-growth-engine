import base64
import json
from pathlib import Path
from urllib import request

from app.core.config import get_settings
from app.services.ai_visuals.base import AIVisualProvider


class OpenAIImageProvider(AIVisualProvider):
    name = "openai"

    def generate_image(self, prompt: str, output_path: str) -> bool:
        settings = get_settings()
        if not settings.openai_api_key:
            return False
        payload = {"model": settings.openai_image_model or settings.ai_image_model or "gpt-image-1", "prompt": prompt, "size": "1024x1536"}
        try:
            req = request.Request(
                "https://api.openai.com/v1/images/generations",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Authorization": f"Bearer {settings.openai_api_key}", "Content-Type": "application/json"},
                method="POST",
            )
            with request.urlopen(req, timeout=90) as response:
                body = json.loads(response.read().decode("utf-8"))
            b64 = body["data"][0].get("b64_json")
            if not b64:
                return False
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            Path(output_path).write_bytes(base64.b64decode(b64))
            return True
        except Exception:
            return False
