from app.services.ai_visuals.base import AIVisualProvider


class ReplicateVisualProvider(AIVisualProvider):
    name = "replicate"

    def generate_image(self, prompt: str, output_path: str) -> bool:
        return False
