from pathlib import Path
from typing import Any

import yaml

from app.core.config import get_settings


def load_yaml_config(name: str) -> dict[str, Any]:
    path = get_settings().config_root / name
    with Path(path).open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    return data

