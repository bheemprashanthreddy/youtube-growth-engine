from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from app.services.rendering.captions import caption_from_scene

CYAN = "#22d3ee"
VIOLET = "#8b5cf6"
WHITE = "#f8fafc"
MUTED = "#94a3b8"
NAVY = "#050b18"


def create_short_scene_clip(scene: dict[str, object], size: tuple[int, int], duration: float, asset: dict[str, object] | None = None):
    return _create_scene_clip(scene, size, duration, short=True, asset=asset)


def create_long_scene_clip(scene: dict[str, object], size: tuple[int, int], duration: float, asset: dict[str, object] | None = None):
    return _create_scene_clip(scene, size, duration, short=False, asset=asset)


def create_short_scene_image(scene: dict[str, object], size: tuple[int, int], asset: dict[str, object] | None = None) -> Image.Image:
    return _scene_image(scene, size, short=True, asset=asset)


def create_long_scene_image(scene: dict[str, object], size: tuple[int, int], asset: dict[str, object] | None = None) -> Image.Image:
    return _scene_image(scene, size, short=False, asset=asset)


def _create_scene_clip(scene: dict[str, object], size: tuple[int, int], duration: float, *, short: bool, asset: dict[str, object] | None = None):
    try:
        from moviepy import ImageClip
    except Exception as exc:
        raise RuntimeError("MoviePy is required for rendering. Install dependencies and ensure FFmpeg is available.") from exc
    image = _scene_image(scene, size, short=short, asset=asset)
    return ImageClip(np.array(image)).with_duration(max(0.25, duration))


def _scene_image(scene: dict[str, object], size: tuple[int, int], *, short: bool, asset: dict[str, object] | None = None) -> Image.Image:
    image = _asset_background(size, asset) or _background(size)
    draw = ImageDraw.Draw(image)
    width, height = size
    margin = int(width * (0.075 if short else 0.06))
    layout = str(scene.get("layout") or "hook")
    scene_number = int(scene.get("scene_number") or 1)
    total_hint = "SHORTS" if short else "EXPLAINER"
    _draw_brand(draw, margin, scene_number, total_hint, short)
    if layout == "split_metaphor":
        _draw_split_layout(draw, image, scene, margin, short)
    elif layout == "claim_card":
        _draw_claim_layout(draw, image, scene, margin, short)
    elif layout == "timeline":
        _draw_timeline_layout(draw, image, scene, margin, short)
    elif layout == "process":
        _draw_process_layout(draw, image, scene, margin, short)
    elif layout == "payoff":
        _draw_payoff_layout(draw, image, scene, margin, short)
    else:
        _draw_hook_layout(draw, image, scene, margin, short)
    _draw_caption(draw, scene, margin, short, width, height)
    _draw_progress(draw, scene_number, width, height, short)
    return image


def _asset_background(size: tuple[int, int], asset: dict[str, object] | None) -> Image.Image | None:
    if not asset or asset.get("asset_type") != "image" or not asset.get("local_path"):
        return None
    path = Path(str(asset["local_path"]))
    if not path.exists():
        return None
    try:
        source = Image.open(path).convert("RGB")
    except Exception:
        return None
    source_ratio = source.width / max(1, source.height)
    target_ratio = size[0] / max(1, size[1])
    if source_ratio > target_ratio:
        new_width = int(source.height * target_ratio)
        left = (source.width - new_width) // 2
        source = source.crop((left, 0, left + new_width, source.height))
    else:
        new_height = int(source.width / target_ratio)
        top = (source.height - new_height) // 2
        source = source.crop((0, top, source.width, top + new_height))
    source = source.resize(size)
    overlay = Image.new("RGB", size, "#020617")
    return Image.blend(source, overlay, 0.58)


def _background(size: tuple[int, int]) -> Image.Image:
    width, height = size
    image = Image.new("RGB", size, NAVY)
    draw = ImageDraw.Draw(image)
    for y in range(height):
        ratio = y / max(1, height)
        draw.line((0, y, width, y), fill=(4 + int(ratio * 16), 11 + int(ratio * 28), 24 + int(ratio * 38)))
    for x in range(0, width, max(18, width // 36)):
        draw.line((x, 0, x + width // 4, height), fill=(10, 27, 45), width=1)
    for idx in range(26):
        x = (idx * 97) % width
        y = (idx * 157) % height
        r = 2 + (idx % 4)
        draw.ellipse((x, y, x + r, y + r), fill=(28, 68, 91))
    return image


def _draw_brand(draw: ImageDraw.ImageDraw, margin: int, scene_number: int, label: str, short: bool) -> None:
    brand_font = _font(42 if short else 32)
    meta_font = _font(24 if short else 20)
    draw.text((margin, margin), "CuriousSignal", fill=CYAN, font=brand_font)
    draw.text((margin, margin + brand_font.size + 8), f"{label} / SCENE {scene_number:02d}", fill=MUTED, font=meta_font)


def _draw_hook_layout(draw: ImageDraw.ImageDraw, image: Image.Image, scene: dict[str, object], margin: int, short: bool) -> None:
    width, height = image.size
    _draw_search_metaphor(draw, margin, int(height * 0.25), width - margin * 2, short)
    _draw_main_text(draw, scene, margin, int(height * 0.40), short, max_lines=2)


def _draw_split_layout(draw: ImageDraw.ImageDraw, image: Image.Image, scene: dict[str, object], margin: int, short: bool) -> None:
    width, height = image.size
    card_w = (width - margin * 3) // 2
    top = int(height * 0.26)
    _rounded(draw, (margin, top, margin + card_w, top + int(height * 0.22)), "#0f172a", CYAN)
    _rounded(draw, (margin * 2 + card_w, top, margin * 2 + card_w * 2, top + int(height * 0.22)), "#111827", VIOLET)
    _link_cards(draw, margin + 28, top + 32, card_w - 56, short)
    _answer_box(draw, margin * 2 + card_w + 28, top + 38, card_w - 56, short)
    _draw_main_text(draw, scene, margin, int(height * 0.55), short, max_lines=2)


def _draw_claim_layout(draw: ImageDraw.ImageDraw, image: Image.Image, scene: dict[str, object], margin: int, short: bool) -> None:
    width, height = image.size
    top = int(height * 0.27)
    _rounded(draw, (margin, top, width - margin, top + int(height * 0.25)), "#0b1220", CYAN)
    _draw_main_text(draw, scene, margin + 38, top + 46, short, max_lines=2)
    _attention_arrows(draw, margin, top + int(height * 0.31), width - margin * 2)


def _draw_timeline_layout(draw: ImageDraw.ImageDraw, image: Image.Image, scene: dict[str, object], margin: int, short: bool) -> None:
    width, height = image.size
    y = int(height * 0.37)
    draw.line((margin, y, width - margin, y), fill=CYAN, width=6 if short else 4)
    for idx, label in enumerate(["OLD", "SHIFT", "NOW"]):
        x = margin + idx * ((width - margin * 2) // 2)
        draw.ellipse((x - 20, y - 20, x + 20, y + 20), fill=VIOLET if idx == 1 else CYAN)
        draw.text((x - 34, y + 34), label, fill=WHITE, font=_font(28 if short else 22))
    _draw_main_text(draw, scene, margin, int(height * 0.52), short, max_lines=2)


def _draw_process_layout(draw: ImageDraw.ImageDraw, image: Image.Image, scene: dict[str, object], margin: int, short: bool) -> None:
    width, height = image.size
    top = int(height * 0.25)
    card_w = int((width - margin * 2) / 3.4)
    for idx in range(3):
        left = margin + idx * int(card_w * 1.18)
        _rounded(draw, (left, top + idx * 28, left + card_w, top + int(height * 0.16) + idx * 28), "#0f172a", CYAN if idx == 2 else "#334155")
        draw.text((left + 22, top + 28 + idx * 28), ["QUERY", "MODEL", "ANSWER"][idx], fill=WHITE, font=_font(28 if short else 22))
        if idx < 2:
            draw.line((left + card_w + 8, top + 75 + idx * 28, left + card_w + 52, top + 75 + idx * 28), fill=CYAN, width=5)
    _draw_main_text(draw, scene, margin, int(height * 0.55), short, max_lines=2)


def _draw_payoff_layout(draw: ImageDraw.ImageDraw, image: Image.Image, scene: dict[str, object], margin: int, short: bool) -> None:
    width, height = image.size
    center = (width // 2, int(height * 0.34))
    for radius, color in [(170 if short else 115, "#1e293b"), (116 if short else 82, "#0f172a"), (60 if short else 44, CYAN)]:
        draw.ellipse((center[0] - radius, center[1] - radius, center[0] + radius, center[1] + radius), outline=color, width=5)
    _draw_main_text(draw, scene, margin, int(height * 0.52), short, max_lines=2)


def _draw_main_text(draw: ImageDraw.ImageDraw, scene: dict[str, object], x: int, y: int, short: bool, max_lines: int) -> None:
    font = _font(84 if short else 58)
    text = str(scene.get("on_screen_text") or "").upper()
    lines = []
    for part in text.split("\n"):
        lines.extend(_wrap(part, 15 if short else 28))
    for idx, line in enumerate(lines[:max_lines]):
        fill = CYAN if idx == 1 else WHITE
        draw.text((x, y + idx * int(font.size * 1.12)), line, fill=fill, font=font)


def _draw_caption(draw: ImageDraw.ImageDraw, scene: dict[str, object], margin: int, short: bool, width: int, height: int) -> None:
    caption = caption_from_scene(scene, short=short).upper()
    font = _font(44 if short else 30)
    top = int(height * (0.78 if short else 0.82))
    _rounded(draw, (margin, top - 22, width - margin, top + font.size + 34), "#020617", "#1e293b")
    words = caption.split()
    if words:
        key = words[-1]
        normal = " ".join(words[:-1])
        draw.text((margin + 28, top), normal + (" " if normal else ""), fill=WHITE, font=font)
        offset = draw.textlength(normal + (" " if normal else ""), font=font)
        draw.text((margin + 28 + offset, top), key, fill=CYAN, font=font)


def _draw_progress(draw: ImageDraw.ImageDraw, scene_number: int, width: int, height: int, short: bool) -> None:
    y = height - (48 if short else 30)
    margin = int(width * 0.075)
    total = 6
    progress = min(1.0, scene_number / total)
    draw.rounded_rectangle((margin, y, width - margin, y + 8), radius=4, fill="#1e293b")
    draw.rounded_rectangle((margin, y, margin + int((width - margin * 2) * progress), y + 8), radius=4, fill=CYAN)


def _draw_search_metaphor(draw: ImageDraw.ImageDraw, x: int, y: int, width: int, short: bool) -> None:
    h = 110 if short else 72
    _rounded(draw, (x, y, x + width, y + h), "#0f172a", CYAN)
    draw.ellipse((x + 32, y + 34, x + 66, y + 68), outline=CYAN, width=4)
    draw.line((x + 60, y + 63, x + 82, y + 85), fill=CYAN, width=4)
    draw.text((x + 110, y + 34), "ask anything...", fill=MUTED, font=_font(34 if short else 26))


def _link_cards(draw: ImageDraw.ImageDraw, x: int, y: int, width: int, short: bool) -> None:
    for idx in range(3):
        top = y + idx * (48 if short else 34)
        draw.rounded_rectangle((x, top, x + width, top + (28 if short else 22)), radius=10, fill="#334155")


def _answer_box(draw: ImageDraw.ImageDraw, x: int, y: int, width: int, short: bool) -> None:
    _rounded(draw, (x, y, x + width, y + (128 if short else 86)), "#172554", CYAN)
    draw.text((x + 18, y + 20), "AI ANSWER", fill=CYAN, font=_font(24 if short else 18))
    for idx in range(3):
        draw.line((x + 18, y + 58 + idx * 22, x + width - 20, y + 58 + idx * 22), fill=WHITE, width=3)


def _attention_arrows(draw: ImageDraw.ImageDraw, x: int, y: int, width: int) -> None:
    for idx in range(3):
        y2 = y + idx * 40
        draw.line((x + 40, y2, x + width - 50, y2), fill=CYAN if idx == 1 else "#475569", width=5)
        draw.polygon([(x + width - 50, y2 - 12), (x + width - 22, y2), (x + width - 50, y2 + 12)], fill=CYAN if idx == 1 else "#475569")


def _rounded(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], fill: str, outline: str) -> None:
    draw.rounded_rectangle(box, radius=24, fill=fill, outline=outline, width=3)


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def _wrap(text: str, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        if sum(len(part) + 1 for part in current) + len(word) > width and current:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines or [text]
