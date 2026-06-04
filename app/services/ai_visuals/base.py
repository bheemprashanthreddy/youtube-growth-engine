from dataclasses import asdict, dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class AIVisualStatus:
    enabled: bool
    provider: str
    image_model: str
    video_model: str
    scene_images_enabled: bool
    thumbnails_enabled: bool
    cache_dir: str
    fallback_mode: bool
    detail: str


@dataclass
class AIVisualAsset:
    provider: str
    asset_type: str
    prompt: str
    model: str
    local_path: str
    safety_status: str
    source: str = "ai_generated"
    created_at: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = datetime.now(UTC).isoformat()

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class AIVisualProvider:
    name = "base"

    def generate_image(self, prompt: str, output_path: str) -> bool:
        raise NotImplementedError
