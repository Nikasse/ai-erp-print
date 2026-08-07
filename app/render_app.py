from pathlib import Path

from fastapi import HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import app

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="static-assets")


@app.get("/{full_path:path}")
async def spa_fallback(full_path: str) -> FileResponse:
    """SPA fallback: усе, що не /api і не /health, віддає index.html.

    React-роутинг живе на клієнті, тому пряме відкриття URL на кшталт
    /transactions має повернути index.html, а не 404 — інакше перезавантаження
    сторінки в адмінці ламається.
    """
    if full_path.startswith("api/") or full_path == "health":
        raise HTTPException(status_code=404)

    candidate = STATIC_DIR / full_path
    if full_path and candidate.is_file():
        return FileResponse(candidate)

    return FileResponse(STATIC_DIR / "index.html")
