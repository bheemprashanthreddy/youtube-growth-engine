from app.services.rendering.engines.base import RenderEngine
from app.services.rendering.renderer import render_job as native_render_job
from app.services.rendering.renderer import render_preview as native_render_preview
from app.services.rendering.reports import RenderResult


class NativeRenderEngine(RenderEngine):
    name = "native"

    def render_job(self, job_id: int, preview: bool = False) -> RenderResult:
        return native_render_preview(job_id) if preview else native_render_job(job_id)

    def get_status(self) -> dict[str, object]:
        return {
            "engine": self.name,
            "available": True,
            "external_service_used": False,
            "warnings": [],
        }
