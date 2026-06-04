from dataclasses import asdict, dataclass
from datetime import UTC, datetime


@dataclass
class VisualAsset:
    provider: str
    asset_type: str
    query: str
    title: str
    source_url: str
    local_path: str
    license_note: str
    attribution_required: bool
    width: int
    height: int
    duration: float
    relevance_score: float
    safety_status: str
    created_at: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class VisualProviderStatus:
    selected_provider: str
    configured: bool
    active: bool
    cache_directory: str
    fallback_mode: bool
    detail: str


class VisualAssetProvider:
    name = "base"

    def search(self, query: str, *, asset_type: str = "image") -> VisualAsset | None:
        raise NotImplementedError


def generated_asset(query: str, *, provider: str = "generated", title: str = "Generated motion graphic fallback") -> VisualAsset:
    return VisualAsset(
        provider=provider,
        asset_type="generated",
        query=query,
        title=title,
        source_url="",
        local_path="",
        license_note="Generated locally by CuriousSignal renderer; no external media used.",
        attribution_required=False,
        width=0,
        height=0,
        duration=0,
        relevance_score=0.5,
        safety_status="safe",
        created_at=datetime.now(UTC).isoformat(),
    )
