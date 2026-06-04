from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class VoiceProviderStatus:
    selected_provider: str
    configured: bool
    active: bool
    fallback_mode: bool
    cache_dir: str
    voice_profile: str
    selected_voice: str
    detail: str


@dataclass
class VoiceResult:
    provider: str
    voice_profile: str
    combined_audio_path: str
    voice_files: list[str]
    fallback_used: bool
    total_audio_duration: float
    warnings: list[str]
    capped: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class VoiceProvider:
    name = "base"

    def generate(self, text: str, output_path: str) -> bool:
        raise NotImplementedError
