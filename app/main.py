"""FastAPI application factory for TradersHub Market Flow."""
from __future__ import annotations

from fastapi import FastAPI

from app.api.v1 import routes_health, routes_pulse
from app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="TradersHub Market Flow",
        version="0.1.0",
        description=(
            "Daily market-intelligence service. Provides regime, drivers, "
            "cross-asset confirmation, and invalidation for the Market Pulse."
        ),
    )
    app.state.settings = settings

    app.include_router(routes_health.router, prefix="/v1")
    app.include_router(routes_pulse.router, prefix="/v1")

    return app


app = create_app()
