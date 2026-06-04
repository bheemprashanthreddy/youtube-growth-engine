import wave
from pathlib import Path

from app.core.config import get_settings
from app.models.content import VideoJob
from app.services.rendering.audio import generate_silent_audio
from app.services.voice.base import VoiceProviderStatus, VoiceResult
from app.services.voice.edge_tts_provider import EdgeTTSVoiceProvider
from app.services.voice.openai_tts_provider import OpenAITTSVoiceProvider
from app.services.voice.silent_provider import SilentVoiceProvider
from app.services.voice.voice_cache import combined_voice_path, voice_cache_dir, voice_cache_path
from app.services.voice.voice_profiles import current_voice_profile


DEFAULT_SAMPLE_RATE = 44100
DEFAULT_CHANNELS = 1
DEFAULT_SAMPLE_WIDTH = 2
MAX_WAV_DATA_BYTES = 4_000_000_000


def voice_provider_status() -> VoiceProviderStatus:
    settings = get_settings()
    provider = settings.voice_provider.lower()
    configured = provider == "silent" or provider == "edge" or (
        provider == "openai" and bool(settings.openai_api_key and settings.openai_tts_model and settings.openai_tts_voice)
    )
    selected_voice = settings.edge_tts_voice if provider == "edge" else settings.openai_tts_voice or "silent"
    active = configured
    fallback = not configured or provider == "silent"
    detail = "Voice provider configured."
    if provider == "openai" and not configured:
        detail = "OpenAI TTS selected but OPENAI_API_KEY, OPENAI_TTS_MODEL, or OPENAI_TTS_VOICE is missing; silent fallback will be used."
    elif provider == "silent":
        detail = "Silent voice provider selected."
    return VoiceProviderStatus(provider, configured, active, fallback, str(voice_cache_dir()), settings.voice_profile, selected_voice, detail)


def generate_voice_for_job(video_job: VideoJob, scenes: list[dict[str, object]], *, preview: bool = False) -> VoiceResult:
    settings = get_settings()
    provider = _provider(settings)
    profile = settings.voice_profile
    pause = float(current_voice_profile().get("pause_seconds", 0.18))
    warnings: list[str] = []
    voice_files: list[str] = []
    fallback_used = provider.name == "silent"
    raw_durations = [max(0.25, _scene_duration(scene, video_job.format_type)) for scene in scenes]
    safe_durations, capped, cap_warnings = _safe_scene_durations(video_job.format_type, raw_durations, preview=preview)
    warnings.extend(cap_warnings)

    for index, scene in enumerate(scenes):
        scene_number = int(scene.get("scene_number") or len(voice_files) + 1)
        text = _scene_voice_text(scene)
        duration = safe_durations[index] if index < len(safe_durations) else 0.25
        suffix = ".mp3" if provider.name == "edge" else ".wav"
        path = voice_cache_path(video_job.id, scene_number, text, provider.name, profile, suffix=suffix)
        if not settings.voice_force_regenerate and path.exists() and path.stat().st_size > 0:
            voice_files.append(str(path))
            continue
        ok = False if provider.name == "silent" else provider.generate(text, str(path))
        if not ok:
            fallback_used = True
            warnings.append(f"voice_scene_{scene_number}_fallback_silent")
            path = voice_cache_path(video_job.id, scene_number, text, "silent", profile, suffix=".wav")
            try:
                _write_silent_wav(path, max(0.25, duration + pause))
            except Exception:
                generate_silent_audio(0.25, str(path))
                warnings.append(f"voice_scene_{scene_number}_silent_write_recovered")
        voice_files.append(str(path))

    combined = combined_voice_path(video_job.id, provider.name if not fallback_used else "silent", profile, preview=preview)
    target_duration = sum(safe_durations)
    try:
        total_duration = _combine_or_silence(voice_files, combined, target_duration)
    except Exception as exc:
        fallback_used = True
        warnings.append(f"combined_voice_fallback_silent: {exc}")
        _write_silent_wav(combined, target_duration)
        total_duration = _wav_duration(combined)
    return VoiceResult(
        provider=provider.name,
        voice_profile=profile,
        combined_audio_path=str(combined),
        voice_files=voice_files,
        fallback_used=fallback_used,
        total_audio_duration=total_duration,
        warnings=warnings,
        capped=capped,
    )


def build_scene_narration(video_job: VideoJob, scenes: list[dict[str, object]]) -> list[str]:
    return [_scene_voice_text(scene) for scene in scenes]


def _provider(settings=None):
    settings = settings or get_settings()
    provider = settings.voice_provider.lower()
    if provider == "openai":
        return OpenAITTSVoiceProvider()
    if provider == "edge":
        return EdgeTTSVoiceProvider()
    return SilentVoiceProvider()


def _scene_voice_text(scene: dict[str, object]) -> str:
    return str(scene.get("voiceover") or scene.get("narration_goal") or scene.get("on_screen_text") or scene.get("section_title") or "").strip() or "CuriousSignal explains the hidden system behind this trend."


def _scene_duration(scene: dict[str, object], format_type: str) -> float:
    key = "duration_seconds" if format_type == "short" else "estimated_duration_seconds"
    return float(scene.get(key) or 5)


def _combine_or_silence(files: list[str], output_path: Path, fallback_duration: float) -> float:
    wav_files = [Path(path) for path in files if Path(path).suffix.lower() == ".wav" and Path(path).exists()]
    if len(wav_files) != len(files):
        _write_silent_wav(output_path, fallback_duration)
        return fallback_duration
    params = None
    target_frames = None
    for path in wav_files:
        with wave.open(str(path), "rb") as wav:
            if params is None:
                params = _validated_params(wav)
                target_frames = _safe_frame_count(fallback_duration, params.framerate, params.nchannels, params.sampwidth)
            else:
                _ensure_compatible(params, wav)
    if params is None:
        _write_silent_wav(output_path, fallback_duration)
        return fallback_duration
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with wave.open(str(output_path), "wb") as out:
            out.setnchannels(params.nchannels)
            out.setsampwidth(params.sampwidth)
            out.setframerate(params.framerate)
            remaining = int(target_frames or 0)
            for path in wav_files:
                if remaining <= 0:
                    break
                with wave.open(str(path), "rb") as wav:
                    _ensure_compatible(params, wav)
                    while remaining > 0:
                        frames_to_read = min(params.framerate, remaining)
                        chunk = wav.readframes(frames_to_read)
                        if not chunk:
                            break
                        frames_read = len(chunk) // (params.nchannels * params.sampwidth)
                        out.writeframes(chunk)
                        remaining -= frames_read
            if remaining > 0:
                _write_silence_frames(out, remaining, params.nchannels, params.sampwidth, params.framerate)
    except Exception:
        output_path.unlink(missing_ok=True)
        raise
    return _wav_duration(output_path)


def _safe_scene_durations(format_type: str, durations: list[float], *, preview: bool) -> tuple[list[float], bool, list[str]]:
    cap = _duration_cap(format_type, preview=preview)
    warnings: list[str] = []
    total = sum(max(0.25, duration) for duration in durations)
    if total <= cap:
        return durations, False, warnings
    scale = cap / total if total else 1.0
    capped = [max(0.25, round(duration * scale, 3)) for duration in durations]
    overflow = sum(capped) - cap
    if capped and overflow > 0:
        capped[-1] = max(0.25, round(capped[-1] - overflow, 3))
    warnings.append(f"voice_duration_capped_to_{cap:g}_seconds")
    if format_type == "long" and not preview:
        warnings.append("long_form_voice_capped_for_mvp")
    return capped, True, warnings


def _duration_cap(format_type: str, *, preview: bool) -> float:
    settings = get_settings()
    if preview:
        preview_cap = float(settings.voice_max_preview_seconds)
        return min(15.0, preview_cap) if format_type == "short" else preview_cap
    if format_type == "short":
        return float(settings.voice_max_short_seconds)
    return float(settings.voice_max_long_seconds)


def _write_silent_wav(output_path: Path, duration_seconds: float) -> None:
    sample_rate = DEFAULT_SAMPLE_RATE
    channels = DEFAULT_CHANNELS
    sample_width = DEFAULT_SAMPLE_WIDTH
    frame_count = _safe_frame_count(duration_seconds, sample_rate, channels, sample_width)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with wave.open(str(output_path), "wb") as wav:
            wav.setnchannels(channels)
            wav.setsampwidth(sample_width)
            wav.setframerate(sample_rate)
            _write_silence_frames(wav, frame_count, channels, sample_width, sample_rate)
    except Exception:
        output_path.unlink(missing_ok=True)
        raise


def _write_silence_frames(wav, frame_count: int, channels: int, sample_width: int, sample_rate: int) -> None:
    _validate_audio_params(sample_rate, channels, sample_width)
    chunk_frames = max(1, sample_rate)
    chunk = b"\x00" * (chunk_frames * channels * sample_width)
    remaining = int(frame_count)
    while remaining > 0:
        frames_to_write = min(chunk_frames, remaining)
        wav.writeframes(chunk[: frames_to_write * channels * sample_width])
        remaining -= frames_to_write


def _safe_frame_count(duration_seconds: float, sample_rate: int, channels: int, sample_width: int) -> int:
    _validate_audio_params(sample_rate, channels, sample_width)
    requested = int(max(0.25, float(duration_seconds)) * sample_rate)
    max_frames = MAX_WAV_DATA_BYTES // max(1, channels * sample_width)
    return min(requested, max_frames)


def _validate_audio_params(sample_rate: int, channels: int, sample_width: int) -> None:
    if sample_rate <= 0 or sample_rate > 192000:
        raise ValueError("Invalid WAV sample rate.")
    if channels <= 0 or channels > 8:
        raise ValueError("Invalid WAV channel count.")
    if sample_width not in {1, 2, 3, 4}:
        raise ValueError("Invalid WAV sample width.")


def _validated_params(wav) -> wave._wave_params:
    params = wav.getparams()
    _validate_audio_params(params.framerate, params.nchannels, params.sampwidth)
    return params


def _ensure_compatible(params: wave._wave_params, wav) -> None:
    other = _validated_params(wav)
    if (params.nchannels, params.sampwidth, params.framerate) != (other.nchannels, other.sampwidth, other.framerate):
        raise ValueError("Cannot combine WAV files with different audio parameters.")


def _wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as wav:
        return wav.getnframes() / float(wav.getframerate())
