from app.services.review import serialize_review_item


def create_short_scene_plan(review_item) -> dict[str, object]:
    item = serialize_review_item(review_item)
    script_lines = [line.strip() for line in item["short_script"].splitlines() if line.strip()]
    scene_count = max(6, min(10, len(script_lines) or 6))
    duration = 54
    per_scene = max(5, round(duration / scene_count))
    beats = _short_visual_beats(item)
    scenes = []
    for index in range(scene_count):
        voiceover = script_lines[index % len(script_lines)] if script_lines else item["topic"]
        beat = beats[index % len(beats)]
        scenes.append(
            {
                "scene_number": index + 1,
                "duration_seconds": per_scene,
                "voiceover": voiceover,
                "visual_type": beat["visual_type"],
                "layout": beat["layout"],
                "visual_prompt": beat["visual_prompt"],
                "on_screen_text": beat["on_screen_text"],
                "broll_keywords": _keywords(item),
                "caption_emphasis": beat["caption_emphasis"],
                "transition_style": "quick cut" if index < scene_count - 1 else "clean outro",
                "retention_note": beat["retention_note"],
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
    return _short_visual_beats(item)[index % 6]["on_screen_text"]


def _caption_emphasis(index: int) -> str:
    return ["hook", "contrast", "proof", "payoff"][index % 4]


def _short_visual_beats(item: dict[str, object]) -> list[dict[str, str]]:
    topic = item.get("expanded_topic") or item["topic"]
    text = str(topic).lower()
    if "ai" in text and "search" in text:
        lines = [
            ("hook", "Search is moving\nfrom links to answers", "search bar transforms into AI answer box"),
            ("split_metaphor", "Blue links are\nbecoming invisible", "browser results fade behind a glowing answer panel"),
            ("claim_card", "Publishers lose\nthe click", "attention arrows route away from link cards"),
            ("timeline", "One habit is\nbeing rewritten", "timeline from keyword search to answer engine"),
            ("process", "Answers now choose\nwhat matters", "ranking cards flow into a single AI summary"),
            ("payoff", "Search just became\nan attention gatekeeper", "network nodes converge into one highlighted answer"),
        ]
    else:
        short_topic = _compact_topic(str(topic))
        lines = [
            ("hook", f"{short_topic}\nis the signal", "topic card breaks into system layers"),
            ("split_metaphor", "The visible trend\nis only the surface", "two-layer diagram with surface and hidden system"),
            ("claim_card", "Follow the incentives\nunderneath", "money, platform, behavior cards connected by arrows"),
            ("timeline", "The timing\nchanged first", "timeline with one highlighted acceleration point"),
            ("process", "Small defaults\nshape behavior", "phone frame and data cards flowing into decision path"),
            ("payoff", "The question is\nwhat changed", "question mark resolves into signal dashboard"),
        ]
    return [
        {
            "layout": layout,
            "on_screen_text": line,
            "visual_type": layout.replace("_", " "),
            "visual_prompt": f"Original abstract motion graphic: {prompt}. Dark premium tech explainer style, cyan accents, no copyrighted media.",
            "caption_emphasis": _caption_emphasis(index),
            "retention_note": "Reveal one concrete mechanism and move before the viewer can predict the next beat.",
        }
        for index, (layout, line, prompt) in enumerate(lines)
    ]


def _compact_topic(topic: str) -> str:
    words = [word for word in topic.replace("Why ", "").split() if len(word) > 2]
    return " ".join(words[:4]) or topic[:28]
