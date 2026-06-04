import asyncio
import wave
from pathlib import Path


DEFAULT_SAMPLE_RATE = 44100
DEFAULT_CHANNELS = 1
DEFAULT_SAMPLE_WIDTH = 2
MAX_WAV_DATA_BYTES = 4_000_000_000


def build_narration_text(video_job) -> str:
    scene_plan = video_job.scene_plan
    lines: list[str] = []
    for scene in scene_plan.get("scenes", []):
        lines.append(str(scene.get("voiceover") or scene.get("narration_goal") or scene.get("section_title") or ""))
    return "\n".join(line for line in lines if line.strip())


def generate_tts_audio(text: str, output_path: str) -> bool:
    try:
        import edge_tts
    except Exception:
        return False
    try:
        async def _run() -> None:
            communicate = edge_tts.Communicate(text, "en-US-GuyNeural")
            await communicate.save(output_path)

        asyncio.run(_run())
        return Path(output_path).exists()
    except Exception:
        return False


def generate_silent_audio(duration_seconds: float, output_path: str) -> str:
    if Path(output_path).suffix.lower() != ".wav":
        output_path = str(Path(output_path).with_suffix(".wav"))
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    sample_rate = DEFAULT_SAMPLE_RATE
    channels = DEFAULT_CHANNELS
    sample_width = DEFAULT_SAMPLE_WIDTH
    frame_count = int(max(0.25, float(duration_seconds)) * sample_rate)
    max_frames = MAX_WAV_DATA_BYTES // max(1, channels * sample_width)
    frame_count = min(frame_count, max_frames)
    chunk_frames = sample_rate
    silence_chunk = b"\x00" * (chunk_frames * channels * sample_width)
    try:
        with wave.open(output_path, "wb") as wav:
            wav.setnchannels(channels)
            wav.setsampwidth(sample_width)
            wav.setframerate(sample_rate)
            remaining = frame_count
            while remaining > 0:
                frames_to_write = min(chunk_frames, remaining)
                wav.writeframes(silence_chunk[: frames_to_write * channels * sample_width])
                remaining -= frames_to_write
    except Exception:
        Path(output_path).unlink(missing_ok=True)
        raise
    return output_path
