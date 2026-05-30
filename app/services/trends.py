def load_source_topics() -> list[dict[str, object]]:
    return [
        {
            "topic": "AI search replacing blue links",
            "pillar": "Technology and AI shifts",
            "trend_reason": "search engines and chat assistants are changing how people find answers",
            "curiosity_trigger": "why the familiar search page is being redesigned so quickly",
            "target_viewer": "curious professionals and creators tracking AI platform shifts",
            "signals": ["ai search", "answer engines", "publisher traffic"],
        },
        {
            "topic": "The resale economy for everyday electronics",
            "pillar": "Money/business curiosity",
            "trend_reason": "people are searching for cheaper devices, trade-in values, and repair economics",
            "curiosity_trigger": "the hidden money flow after a device leaves its first owner",
            "target_viewer": "viewers curious about consumer money systems",
            "signals": ["used phones", "trade in", "repair market"],
        },
        {
            "topic": "Why old internet aesthetics are back",
            "pillar": "Internet trends explained",
            "trend_reason": "younger audiences are reviving early web visuals as a reaction to polished feeds",
            "curiosity_trigger": "why rougher design suddenly feels more authentic",
            "target_viewer": "internet culture watchers and creators",
            "signals": ["y2k web", "digital nostalgia", "creator culture"],
        },
        {
            "topic": "Private space companies racing for lunar infrastructure",
            "pillar": "Science/future discoveries",
            "trend_reason": "new missions are making the moon look like infrastructure, not just exploration",
            "curiosity_trigger": "the business system forming around future lunar logistics",
            "target_viewer": "science and future-curious viewers",
            "signals": ["lunar economy", "space startups", "moon missions"],
        },
        {
            "topic": "The hidden logistics of same-day delivery",
            "pillar": "Hidden systems behind everyday things",
            "trend_reason": "customers expect instant delivery while retailers rebuild local fulfillment networks",
            "curiosity_trigger": "how many invisible systems move before a package arrives",
            "target_viewer": "viewers who like everyday systems explained",
            "signals": ["same day delivery", "micro fulfillment", "logistics"],
        },
        {
            "topic": "Unexpected tourism spikes in small countries",
            "pillar": "Strange global stories",
            "trend_reason": "short videos and cheaper travel routes can redirect attention to overlooked places",
            "curiosity_trigger": "how a small place becomes globally visible almost overnight",
            "target_viewer": "global trend and travel-curious viewers",
            "signals": ["viral tourism", "travel trends", "small countries"],
        },
    ]


def normalize_topics(topics: list[dict[str, object]]) -> list[dict[str, object]]:
    seen: set[str] = set()
    normalized: list[dict[str, object]] = []
    for topic in topics:
        name = str(topic["topic"]).strip()
        key = name.lower()
        if not name or key in seen:
            continue
        seen.add(key)
        normalized.append({**topic, "topic": name})
    return normalized

