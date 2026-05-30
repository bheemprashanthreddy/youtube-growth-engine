import re


QUESTION_PREFIXES = ("Why", "How", "What")
WRAP_SUFFIX = "Is Suddenly Everywhere"


def normalize_title(title: str) -> str:
    cleaned = _clean_spacing(title)
    cleaned = _collapse_duplicate_prefix(cleaned)
    return cleaned


def choose_video_job_title(title_options: list[str], fallback_topic: str) -> str:
    fallback = normalize_title(fallback_topic)
    for option in title_options:
        candidate = normalize_title(option)
        if not candidate:
            continue
        if _wraps_complete_title(candidate, fallback):
            return fallback
        return candidate
    return fallback


def build_title_from_topic(topic: str) -> str:
    cleaned = normalize_title(topic)
    if _is_complete_title(cleaned):
        return cleaned
    return f"Why {cleaned} {WRAP_SUFFIX}"


def _collapse_duplicate_prefix(value: str) -> str:
    for prefix in QUESTION_PREFIXES:
        value = re.sub(rf"^{prefix}\s+{prefix}\s+", f"{prefix} ", value, flags=re.IGNORECASE)
    return _clean_spacing(value)


def _wraps_complete_title(candidate: str, fallback: str) -> bool:
    if not _is_complete_title(fallback):
        return False
    candidate_key = _key(candidate)
    fallback_key = _key(fallback)
    suffix_key = _key(WRAP_SUFFIX)
    return candidate_key == f"{fallback_key} {suffix_key}" or candidate_key == f"why {fallback_key} {suffix_key}"


def _is_complete_title(value: str) -> bool:
    return value.endswith("?") or value.lower().startswith(("why ", "how ", "what "))


def _clean_spacing(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def _key(value: str) -> str:
    text = normalize_title(value).lower()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()
