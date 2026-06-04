from app.services.rendering.audio import generate_silent_audio
from app.services.voice.base import VoiceProvider


class SilentVoiceProvider(VoiceProvider):
    name = "silent"

    def generate(self, text: str, output_path: str, duration_seconds: float = 1.0) -> bool:
        generate_silent_audio(duration_seconds, output_path)
        return True
