from pathlib import Path

from PIL import Image, ImageDraw

from app.services.ai_visuals.base import AIVisualProvider


class FallbackAIVisualProvider(AIVisualProvider):
    name = "fallback"

    def generate_image(self, prompt: str, output_path: str) -> bool:
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        image = Image.new("RGB", (1080, 1920), "#050b18")
        draw = ImageDraw.Draw(image)
        for y in range(1920):
            tone = int(8 + (y / 1920) * 42)
            draw.line((0, y, 1080, y), fill=(tone, 20 + tone // 2, 40 + tone))
        for index in range(12):
            x = 120 + (index * 83) % 840
            y = 260 + (index * 137) % 1180
            draw.ellipse((x - 42, y - 42, x + 42, y + 42), outline="#22d3ee", width=4)
            draw.line((x, y, 540, 960), fill="#334155", width=3)
        draw.rounded_rectangle((140, 720, 940, 1180), radius=42, outline="#8b5cf6", width=6)
        draw.text((180, 780), "AI VISUAL", fill="#22d3ee")
        draw.text((180, 830), prompt[:120], fill="#f8fafc")
        image.save(path)
        return True
