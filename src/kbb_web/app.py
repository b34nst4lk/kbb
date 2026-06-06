"""FastAPI application factory for Knowledge Base Builder web adapter.

Creates the app with lifespan-managed engine, template engine,
static files, and route registration.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader
from markdown_it import MarkdownIt

from kbb.engine import KBPEngine
from kbb_web.config import load_config

# Shared markdown renderer — used by the Jinja2 | markdown filter
_md = MarkdownIt()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize engine on startup, tear down on shutdown."""
    config = load_config()
    app.state.web_config = config
    app.state.engine = KBPEngine(config.to_kbb_config())
    yield


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Knowledge Base Builder",
        lifespan=lifespan,
    )

    # Template engine — resolves from package directory
    templates_dir = Path(__file__).parent / "templates"
    app.state.templates = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=True,
    )
    app.state.templates.filters["markdown"] = lambda text: _md.render(text or "")

    # Static files
    static_dir = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Register route modules
    from kbb_web.routes.pages import router as pages_router
    from kbb_web.routes.partials import router as partials_router
    from kbb_web.routes.api import router as api_router

    app.include_router(pages_router)
    app.include_router(partials_router, prefix="/partials")
    app.include_router(api_router, prefix="/api")

    # Global exception handler — returns partial for HTMX, full page otherwise
    # For HTMX requests, returns 200 so HTMX performs the swap (error responses
    # are silently ignored by default HTMX behavior)
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        env: Environment = request.app.state.templates
        if request.headers.get("HX-Request") == "true":
            template = env.get_template("partials/error_alert.html")
            html = template.render(error=str(exc))
            return HTMLResponse(content=html)
        template = env.get_template("pages/error.html")
        html = template.render(error=str(exc))
        return HTMLResponse(content=html, status_code=500)

    return app


app = create_app()