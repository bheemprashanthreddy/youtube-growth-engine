from app.core.config import get_settings
from app.services.rendering.reports import RenderResult


class RenderEngine:
    name = "base"

    def render_job(self, job_id: int, preview: bool = False) -> RenderResult:
        raise NotImplementedError

    def get_status(self) -> dict[str, object]:
        raise NotImplementedError


def resolve_render_engine(engine: str | None = None) -> RenderEngine:
    from app.services.rendering.engines.moneyprinterturbo_engine import MoneyPrinterTurboEngine
    from app.services.rendering.engines.native_engine import NativeRenderEngine

    selected = (engine or get_settings().render_engine or "native").lower()
    if selected == "moneyprinterturbo":
        return MoneyPrinterTurboEngine()
    if selected == "native":
        return NativeRenderEngine()
    raise ValueError(f"Unknown render engine: {selected}")


def render_engine_status() -> dict[str, object]:
    from app.services.rendering.engines.moneyprinterturbo_engine import MoneyPrinterTurboEngine

    settings = get_settings()
    moneyprinterturbo = MoneyPrinterTurboEngine().get_status()
    warnings: list[str] = []
    if settings.moneyprinterturbo_use_background_music:
        warnings.append("MoneyPrinterTurbo background music is enabled. Confirm music licensing before rendering.")
    if settings.render_engine == "moneyprinterturbo" and not settings.moneyprinterturbo_enabled:
        warnings.append("MoneyPrinterTurbo is selected but disabled; native rendering remains available.")
    return {
        "selected_engine": settings.render_engine,
        "native_available": True,
        "moneyprinterturbo_enabled": settings.moneyprinterturbo_enabled,
        "moneyprinterturbo_base_url": settings.moneyprinterturbo_base_url,
        "moneyprinterturbo_reachable": moneyprinterturbo.get("reachable", False),
        "moneyprinterturbo_status": moneyprinterturbo,
        "warnings": warnings + list(moneyprinterturbo.get("warnings", [])),
    }
