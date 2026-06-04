UNSAFE_VISUAL_TERMS = {
    "real person",
    "public figure",
    "politician",
    "president",
    "minor",
    "child",
    "weapon",
    "gun",
    "gore",
    "blood",
    "violence",
    "disaster",
    "medical",
    "explicit",
    "logo",
    "brand logo",
    "news footage",
}


def sanitize_visual_prompt(prompt: str) -> str:
    cleaned = prompt.strip()
    lower = cleaned.lower()
    for term in UNSAFE_VISUAL_TERMS:
        if term in lower:
            cleaned = cleaned.replace(term, "abstract visual")
            cleaned = cleaned.replace(term.title(), "Abstract visual")
    guardrail = "No real people, no public figures, no minors, no logos, no weapons, no gore, no misleading news scene."
    if guardrail.lower() not in cleaned.lower():
        cleaned = f"{cleaned}. {guardrail}"
    return cleaned


def visual_prompt_safety_status(prompt: str) -> str:
    lower = prompt.lower()
    return "needs_sanitization" if any(term in lower for term in UNSAFE_VISUAL_TERMS) else "safe"
