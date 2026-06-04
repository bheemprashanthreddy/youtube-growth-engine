from pathlib import Path

from PIL import Image, ImageDraw

from app.services.rendering.visual_templates import CYAN, MUTED, VIOLET, WHITE, _font, _wrap


def generate_thumbnail(video_job, output_path: str) -> str:
    size = (1080, 1920) if video_job.format_type == "short" else (1280, 720)
    image = _thumbnail_image(video_job, size, variant="a")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path)
    return output_path


def generate_thumbnail_variants(video_job, output_dir: str = "renders/thumbnails", assets: list[dict[str, object]] | None = None) -> list[str]:
    size = (1080, 1920) if video_job.format_type == "short" else (1280, 720)
    root = Path(output_dir)
    root.mkdir(parents=True, exist_ok=True)
    paths: list[str] = []
    for variant in ["a", "b", "c"]:
        path = root / f"{video_job.id}_{variant}.png"
        image = _thumbnail_image(video_job, size, variant=variant, assets=assets or [])
        image.save(path)
        paths.append(str(path))
    return paths


def _thumbnail_image(video_job, size: tuple[int, int], *, variant: str, assets: list[dict[str, object]] | None = None) -> Image.Image:
    width, height = size
    short = video_job.format_type == "short"
    image = _asset_image_background(size, assets) if variant == "b" else None
    if image is None:
        image = Image.new("RGB", size, "#050b18")
    draw = ImageDraw.Draw(image)
    if variant != "b":
        for y in range(height):
            ratio = y / max(1, height)
            draw.line((0, y, width, y), fill=(5 + int(ratio * 20), 12 + int(ratio * 24), 27 + int(ratio * 42)))
    else:
        overlay = Image.new("RGB", size, "#020617")
        image = Image.blend(image, overlay, 0.5)
        draw = ImageDraw.Draw(image)
    margin = int(width * (0.07 if short else 0.055))
    draw.text((margin, margin), "CuriousSignal", fill=CYAN, font=_font(42 if short else 34))
    hook = _thumbnail_hook(video_job)
    if variant != "c":
        _draw_visual_metaphor(draw, width, height, margin, short, video_job.title)
    font = _font(100 if short else 86)
    top = int(height * (0.34 if short else 0.20)) if variant != "c" else int(height * (0.40 if short else 0.28))
    max_width = 13 if short else 18
    for idx, line in enumerate(_wrap(hook.upper(), max_width)[:3]):
        fill = WHITE if idx != 1 else CYAN
        draw.text((margin, top + idx * int(font.size * 1.05)), line, fill=fill, font=font)
    label_font = _font(28 if short else 24)
    pill = (margin, height - margin - 72, margin + (430 if short else 350), height - margin - 18)
    draw.rounded_rectangle(pill, radius=24, fill="#020617", outline=VIOLET, width=3)
    draw.text((pill[0] + 24, pill[1] + 13), "HIDDEN SYSTEMS EXPLAINED", fill=MUTED, font=label_font)
    return image


def _asset_image_background(size: tuple[int, int], assets: list[dict[str, object]] | None) -> Image.Image | None:
    for asset in assets or []:
        if asset.get("asset_type") != "image" or not asset.get("local_path"):
            continue
        path = Path(str(asset["local_path"]))
        if not path.exists():
            continue
        try:
            source = Image.open(path).convert("RGB")
        except Exception:
            continue
        return source.resize(size)
    return None


def _thumbnail_hook(video_job) -> str:
    ideas = []
    raw = getattr(video_job, "thumbnail_ideas", "") or ""
    if raw.startswith("["):
        import json

        try:
            ideas = [str(item) for item in json.loads(raw)]
        except Exception:
            ideas = []
    elif raw:
        ideas = [raw]
    candidates = [getattr(video_job, "thumbnail_text", ""), *ideas, getattr(video_job, "title", "")]
    for candidate in candidates:
        hook = _clean_hook(str(candidate))
        if 2 <= len(hook.split()) <= 5:
            return hook
    return "SEARCH JUST SHIFTED" if "search" in getattr(video_job, "title", "").lower() else "WHAT CHANGED?"


def _clean_hook(text: str) -> str:
    text = text.replace("?", "").replace("!", "").strip()
    words = [word for word in text.split() if word.lower() not in {"why", "how", "the", "is", "are", "a", "an"}]
    return " ".join(words[:5])


def _draw_visual_metaphor(draw: ImageDraw.ImageDraw, width: int, height: int, margin: int, short: bool, title: str) -> None:
    area_top = int(height * (0.56 if short else 0.52))
    area_left = margin
    area_right = width - margin
    if "search" in title.lower() or "ai" in title.lower():
        draw.rounded_rectangle((area_left, area_top, area_right, area_top + int(height * 0.13)), radius=28, fill="#0f172a", outline=CYAN, width=4)
        draw.text((area_left + 34, area_top + 30), "AI ANSWER", fill=CYAN, font=_font(36 if short else 30))
        for idx in range(3):
            y = area_top + 88 + idx * (34 if short else 24)
            draw.line((area_left + 34, y, area_right - 34, y), fill=WHITE if idx == 0 else "#64748b", width=5)
        for idx in range(3):
            y = area_top + int(height * 0.19) + idx * (52 if short else 32)
            draw.rounded_rectangle((area_left + 20, y, area_right - 110, y + (24 if short else 18)), radius=10, fill="#334155")
            draw.line((area_right - 90, y + 10, area_right - 18, area_top + 65), fill=VIOLET, width=4)
    else:
        center_x = (area_left + area_right) // 2
        center_y = area_top + int(height * 0.13)
        for radius, color in [(170 if short else 110, "#1e293b"), (105 if short else 74, "#172554"), (46 if short else 34, CYAN)]:
            draw.ellipse((center_x - radius, center_y - radius, center_x + radius, center_y + radius), outline=color, width=5)
        for idx in range(6):
            x = area_left + idx * ((area_right - area_left) // 5)
            draw.line((x, center_y + 150 if short else center_y + 95, center_x, center_y), fill="#334155", width=3)
