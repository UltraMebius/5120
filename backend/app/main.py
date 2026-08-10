from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import router as routes_router
from .config import APP_DESCRIPTION, APP_TITLE, FRONTEND_ORIGINS

app = FastAPI(title=APP_TITLE, description=APP_DESCRIPTION)

app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(routes_router, prefix="/api")


@app.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    """Return liveness; database readiness is verified separately."""
    return {"status": "ok"}
