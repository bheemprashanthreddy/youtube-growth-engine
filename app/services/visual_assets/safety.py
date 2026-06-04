UNSAFE_TERMS = {
    "weapon",
    "weapons",
    "gun",
    "guns",
    "blood",
    "dead",
    "deadly",
    "death",
    "violence",
    "violent",
    "disaster",
    "war",
    "politician",
    "president",
    "election",
    "medical",
    "minor",
    "child",
    "children",
    "explicit",
    "adult",
}


def is_safe_asset_query(query: str, risk_flags: list[str] | None = None) -> bool:
    text = query.lower()
    flags = {flag.lower() for flag in (risk_flags or [])}
    if any(term in text.split() for term in UNSAFE_TERMS):
        return False
    if {"political_context", "breaking_news_context", "current_event_source_support_needed"} & flags:
        return False
    return True


def safety_status(query: str, risk_flags: list[str] | None = None) -> str:
    return "safe" if is_safe_asset_query(query, risk_flags) else "rejected"
