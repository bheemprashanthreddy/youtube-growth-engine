import hashlib
import re
from pathlib import Path
from urllib import request

from app.core.config import get_settings


def cache_root() -> Path:
    root = get_settings().visual_asset_cache_dir
    if not root.is_absolute():
        root = Path.cwd() / root
    root.mkdir(parents=True, exist_ok=True)
    return root


def safe_cache_path(provider: str, query: str, suffix: str) -> Path:
    safe_provider = re.sub(r"[^a-zA-Z0-9_-]+", "-", provider).strip("-").lower() or "asset"
    digest = hashlib.sha256(query.encode("utf-8")).hexdigest()[:16]
    extension = suffix if suffix.startswith(".") else f".{suffix}"
    return cache_root() / safe_provider / f"{digest}{extension}"


def download_to_cache(url: str, provider: str, query: str, suffix: str) -> str:
    path = safe_cache_path(provider, query, suffix)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.stat().st_size > 0:
        return str(path)
    req = request.Request(url, headers={"User-Agent": "CuriousSignalVisualAssetFetcher/0.1"})
    with request.urlopen(req, timeout=20) as response:
        path.write_bytes(response.read())
    return str(path)
