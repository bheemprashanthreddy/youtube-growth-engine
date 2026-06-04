from app.services.rendering.captions import caption_from_scene

GENERIC_SCENE_TEXT = {
    "why now",
    "why now?",
    "the trend",
    "here's why",
    "heres why",
    "the hidden signal",
    "sudden spike",
}


def render_quality_warnings(scenes: list[dict[str, object]], *, thumbnail_text: str, short: bool) -> list[str]:
    warnings: list[str] = []
    if not scenes:
        return ["empty_scene_plan"]
    for scene in scenes:
        number = scene.get("scene_number", "?")
        main_text = str(scene.get("on_screen_text") or "").strip()
        normalized = " ".join(main_text.lower().replace("\n", " ").split())
        if not main_text:
            warnings.append(f"scene_{number}_empty_main_text")
        if normalized in GENERIC_SCENE_TEXT:
            warnings.append(f"scene_{number}_generic_main_text")
        if len(main_text.split()) <= 1:
            warnings.append(f"scene_{number}_main_text_too_short")
        if "\n" not in main_text and len(main_text) > (34 if short else 54):
            warnings.append(f"scene_{number}_main_text_may_leave_poor_layout")
        caption = caption_from_scene(scene, short=short)
        if len(caption.split()) > (8 if short else 12):
            warnings.append(f"scene_{number}_caption_too_long")
    if len(thumbnail_text.split()) > 6 or len(thumbnail_text) > 42:
        warnings.append("thumbnail_text_too_long")
    return warnings
