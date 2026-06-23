"""Vehicle Service Upsell Studio — FastAPI entrypoint.

Serves the JSON API under /api and the prebuilt React SPA (frontend/dist) for everything
else. No database pool: all state lives in Delta, reached via the SQL Statement Execution
API (see server/sql.py).
"""
import os

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from server.routes import (
    components, configs, deploy, models, prompt, runs, sample, settings_route,
)

app = FastAPI(title="Vehicle Service Upsell Studio")

for r in (models, components, configs, prompt, runs, sample, deploy, settings_route):
    app.include_router(r.router, prefix="/api")


@app.get("/api/health")
def health():
    return {"ok": True}


# Surface backend errors to the UI as JSON instead of opaque 500s.
@app.exception_handler(Exception)
async def all_errors(request, exc):
    return JSONResponse(status_code=500, content={"error": str(exc)})


_FRONTEND = os.path.join(os.path.dirname(__file__), "frontend", "dist")
if os.path.isdir(_FRONTEND):
    _ASSETS = os.path.join(_FRONTEND, "assets")
    if os.path.isdir(_ASSETS):
        app.mount("/assets", StaticFiles(directory=_ASSETS), name="assets")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        candidate = os.path.join(_FRONTEND, full_path)
        if full_path and os.path.isfile(candidate):
            return FileResponse(candidate)
        return FileResponse(os.path.join(_FRONTEND, "index.html"))
