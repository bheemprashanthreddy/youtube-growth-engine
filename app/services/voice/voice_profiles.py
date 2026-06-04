from app.core.config import get_settings


VOICE_PROFILES = {
    "curious_signal_default": {
        "style": "clear, paced, curious explainer",
        "pause_seconds": 0.18,
    },
    "curious_signal_fast": {
        "style": "faster short-form explainer",
        "pause_seconds": 0.12,
    },
}


def current_voice_profile() -> dict[str, object]:
    return VOICE_PROFILES.get(get_settings().voice_profile, VOICE_PROFILES["curious_signal_default"])
