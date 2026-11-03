"""FastAPI entrypoint, compatible with local Uvicorn and Vercel's FastAPI preset."""
from __future__ import annotations
import logging
import sys
import types
from pathlib import Path

# Vercel imports app.py from server/ as a standalone project root. In local
# development, imports resolve under the parent project's server package.
HERE = Path(__file__).resolve().parent
if "server" not in sys.modules:
    package = types.ModuleType("server")
    package.__path__ = [str(HERE)]
    sys.modules["server"] = package

from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from server.core.config import Settings, load_settings
from server.core.guard import MemoryGuard
from server.services.email_service import EmailService
from server.api.contact import router


def create_app(settings: Settings | None = None, mailer=None, guard=None) -> FastAPI:
    settings = settings if settings is not None else load_settings()
    app = FastAPI(title="Mae Ann Laurel Portfolio Contact API", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.settings = settings
    app.state.guard = guard if guard is not None else MemoryGuard(settings)
    app.state.mailer = mailer if mailer is not None else EmailService(settings)

    @app.middleware("http")
    async def safety(request: Request, call_next):
        if request.method == "POST":
            if request.headers.get("content-type", "").split(";")[0].strip() != "application/json":
                return JSONResponse({"message": "Use a JSON request."}, status_code=415)
            size = 0
            parts = []
            async for chunk in request.stream():
                size += len(chunk)
                if size > 32768:
                    return JSONResponse({"message": "Your message is too large."}, status_code=413)
                parts.append(chunk)
            request._body = b"".join(parts)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    @app.exception_handler(RequestValidationError)
    async def invalid(request, exc):
        return JSONResponse({"message": "Please check your name, email, subject and message.",
                             "fields": sorted({str(x["loc"][-1]) for x in exc.errors()})}, status_code=422)

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        return JSONResponse({"message": str(exc.detail)}, status_code=exc.status_code, headers=exc.headers)

    @app.get("/api/health")
    def health():
        return {"status": "ok", "service": "portfolio-contact"}

    app.include_router(router)
    app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins,
                       allow_methods=["GET", "POST", "OPTIONS"],
                       allow_headers=["Content-Type", "Idempotency-Key"],
                       expose_headers=["Retry-After"], allow_credentials=False, max_age=600)
    if settings.readiness_error:
        logging.getLogger("portfolio").warning("Contact setup: %s", settings.readiness_error)
    return app


app = create_app()
