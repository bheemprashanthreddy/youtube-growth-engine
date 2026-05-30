from app.services.review import serialize_review_item


def create_short_scene_plan(review_item) -> dict[str, object]:
    item = serialize_review_item(review_item)
    script_lines = [line.strip() for line in item["short_script"].splitlines() if line.strip()]
    scene_count = max(6, min(10, len(script_lines) or 6))
    duration = 54
    per_scene = max(5, round(duration / scene_count))
    scenes = []
    for index in range(scene_count):
        voiceover = script_lines[index % len(script_lines)] if script_lines else item["topic"]
        scenes.append(
            {
                "scene_number": index + 1,
                "duration_seconds": per_scene,
                "voiceover": voiceover,
                "visual_type": _visual_type(index),
                "visual_prompt": f"Vertical documentary-style visual explaining {item['topic']}; scene {index + 1}; clean, source-neutral, no copyrighted media.",
                "on_screen_text": _short_text(item, index),
                "broll_keywords": _keywords(item),
                "caption_emphasis": _caption_emphasis(index),
                "transition_style": "quick cut" if index < scene_count - 1 else "clean outro",
                "retention_note": "Keep the question moving; reveal one new piece of context before the next cut.",
            }
        )
    return {
        "format_type": "short",
        "target_duration_seconds": duration,
        "aspect_ratio": "9:16",
        "pacing": "fast, curiosity-driven",
        "scenes": scenes,
    }


def create_long_scene_plan(review_item) -> dict[str, object]:
    item = serialize_review_item(review_item)
    outline = item["long_outline"] or [item["topic"]]
    scene_count = max(8, min(15, len(outline) + 2))
    duration = 480
    per_scene = max(35, round(duration / scene_count))
    scenes = []
    for index in range(scene_count):
        section = outline[index % len(outline)]
        scenes.append(
            {
                "scene_number": index + 1,
                "section_title": section,
                "estimated_duration_seconds": per_scene,
                "narration_goal": f"Explain {section.lower()} with clear context and avoid unsupported claims.",
                "visual_type": _visual_type(index),
                "visual_prompt": f"Horizontal documentary explainer visual for {item['topic']}: {section}; clean editorial style, original or licensed assets only.",
                "broll_keywords": _keywords(item) + [section],
                "on_screen_text": section[:70],
                "retention_note": "End the section with a specific question or consequence that pulls into the next section.",
            }
        )
    return {
        "format_type": "long",
        "target_duration_seconds": duration,
        "aspect_ratio": "16:9",
        "pacing": "structured, evidence-led explainer",
        "scenes": scenes,
    }


def _keywords(item: dict[str, object]) -> list[str]:
    words = [word.strip(".,:;!?").lower() for word in item["topic"].split()]
    return [word for word in words if len(word) > 3][:8]


def _visual_type(index: int) -> str:
    return ["animated text", "data graphic", "b-roll montage", "system diagram"][index % 4]


def _short_text(item: dict[str, object], index: int) -> str:
    ideas = item["thumbnail_ideas"] or ["WHY NOW?"]
    if index == 0:
        return ideas[0]
    if index == 1:
        return "THE HIDDEN SIGNAL"
    return item["topic"][:48]


def _caption_emphasis(index: int) -> str:
    return ["hook", "contrast", "proof", "payoff"][index % 4]
