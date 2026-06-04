def caption_from_scene(scene: dict[str, object], *, short: bool) -> str:
    text = str(scene.get("on_screen_text") or scene.get("voiceover") or scene.get("section_title") or "")
    text = text.replace("\n", " ")
    for prefix in ["0-3 sec hook:", "3-8 sec curiosity gap:", "concrete example:", "hidden system insight:", "payoff:", "soft cta:"]:
        if text.lower().startswith(prefix):
            text = text[len(prefix) :].strip()
    words = [word.strip(".,:;!?") for word in text.split() if word.strip(".,:;!?")]
    limit = 8 if short else 12
    return " ".join(words[:limit])
