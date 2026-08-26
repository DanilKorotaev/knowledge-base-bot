"""
Точка входа KB App API (iOS).

Запуск локально из корня репозитория knowledge-base-bot::

    export KB_APP_API_TOKEN=secret
    export DB_TYPE=sqlite DB_FILE=/tmp/kb_test.db
    PYTHONPATH=. uvicorn kb_app_api.main:app --host 0.0.0.0 --port 8091

Docker: ``docker compose up kb-app-api`` (см. ``kb-app-api/README.md``).

Опционально ``POST /api/auth/token`` — переменные ``KB_APP_API_TOKEN_ENDPOINT_ENABLED``,
``KB_APP_API_TOKEN_ISSUE_SECRET`` (см. ``kb-app-api/env.example``).
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from kb_app_api.client_metadata_middleware import ClientMetadataMiddleware
from kb_app_api.errors import APIError, api_error_handler, validation_error_handler
from kb_app_api.routes import attachments, auth, devices, files, health, messages, sessions, voice

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("kb_app_api")


@asynccontextmanager
async def lifespan(_: FastAPI):
    from utils.db_helpers import close_db, get_db

    await get_db()
    logger.info("KB App API: база данных готова")
    yield
    await close_db()


app = FastAPI(
    title="KB App API",
    description="Бэкенд для iOS (контракт KB_APP_API_CONTRACT.md)",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(ClientMetadataMiddleware)

app.add_exception_handler(APIError, api_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)

app.include_router(health.router)
app.include_router(auth.router, prefix="/api")
app.include_router(sessions.router, prefix="/api")
app.include_router(messages.router, prefix="/api")
app.include_router(attachments.router, prefix="/api")
app.include_router(voice.router, prefix="/api")
app.include_router(files.router, prefix="/api")
app.include_router(devices.router, prefix="/api")


if __name__ == "__main__":
    import os

    import uvicorn

    port = int(os.getenv("PORT", "8091"))
    host = os.getenv("HOST", "0.0.0.0")
    uvicorn.run("kb_app_api.main:app", host=host, port=port, reload=False)
