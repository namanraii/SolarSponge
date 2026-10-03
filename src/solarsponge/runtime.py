"""Process-wide app state (modular monolith)."""

from __future__ import annotations

from dataclasses import dataclass

from solarsponge.config import Settings, load_config
from solarsponge.copilot.agents import Copilot
from solarsponge.copilot.tools import ToolLayer
from solarsponge.forecasting.service import ForecastService
from solarsponge.store import Store


@dataclass
class AppContext:
    settings: Settings
    store: Store
    forecast: ForecastService
    copilot: Copilot
    tools: ToolLayer
    ready: bool = False


_CTX: AppContext | None = None


def get_ctx() -> AppContext:
    global _CTX
    if _CTX is None:
        _CTX = bootstrap()
    return _CTX


def bootstrap(settings: Settings | None = None) -> AppContext:
    global _CTX
    settings = settings or load_config()
    store = Store(settings)
    fc = ForecastService(settings)
    tools = ToolLayer(settings, store, fc)
    copilot = Copilot(settings, tools)
    _CTX = AppContext(settings=settings, store=store, forecast=fc, copilot=copilot, tools=tools, ready=False)
    if settings.ops.demo_mode:
        from solarsponge.loop import build_demo

        build_demo(settings, store)
        _CTX.ready = True
    return _CTX
