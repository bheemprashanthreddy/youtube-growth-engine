import asyncio
from pathlib import Path

from app.core.config import get_settings
from app.services.voice.base import VoiceProvider


class EdgeTTSVoiceProvider(VoiceProvider):
    name = "edge"

    def generate(self, text: str, output_path: str) -> bool:
        try:
            import edge_tts
        except Exception:
            return False
        settings = get_settings()
        try:
            async def _run() -> None:
                communicate = edge_tts.Communicate(
                    text,
                    settings.edge_tts_voice,
                    rate=settings.edge_tts_rate,
                    pitch=settings.edge_tts_pitch,
                )
                await communicate.save(output_path)

            asyncio.run(_run())
            return Path(output_path).exists() and Path(output_path).stat().st_size > 0
        except Exception:
            return False
