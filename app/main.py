import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.routes.documents import router as documents_router
from app.infrastructure.database.session import SessionLocal, engine
from app.composition_root import fail_stuck_documents

logger = logging.getLogger(__name__)

_STUCK_PROCESSING_MESSAGE = (
    "Document processing was interrupted by a server restart. "
    "Please re-upload the document to retry."
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --------------- startup ---------------
    # Any document left in PROCESSING status when the server last stopped
    # will never transition on its own — the background task that owned it
    # died with the process.  Reset them all to FAILED immediately so users
    # can see a clear error and retry, rather than waiting forever.
    session = SessionLocal()
    try:
        recovered = fail_stuck_documents(session, _STUCK_PROCESSING_MESSAGE)
        if recovered:
            logger.warning(
                "Startup recovery: marked %d stuck PROCESSING/INDEXING document(s) as FAILED.",
                recovered,
            )
        else:
            logger.info("Startup recovery: no stuck documents found.")
    except Exception:
        logger.exception("Startup recovery failed — stuck documents may remain in PROCESSING.")
    finally:
        session.close()

    yield  # application runs here

    # --------------- shutdown ---------------
    # Nothing to clean up for now.


app = FastAPI(lifespan=lifespan)

# ---------------------------------------------------------------------------
# CORS  — configured via ALLOWED_ORIGINS env var (comma-separated list).
# Falls back to localhost:4200 for local Angular development.
# Example production value: ALLOWED_ORIGINS=https://app.example.com
# ---------------------------------------------------------------------------
_raw_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:4200")
allowed_origins = [o.strip() for o in _raw_origins.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents_router)


# ---------------------------------------------------------------------------
# Liveness probe — no dependencies checked, always 200 when the process is up.
# ---------------------------------------------------------------------------
@app.get("/health", tags=["ops"])
def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Readiness probe — checks real connectivity to Postgres and MinIO.
# Returns 200 only when both are reachable; 503 with a sanitised error
# message (no passwords, no full connection strings) when either fails.
# No authentication required — probes must work before any user context.
# ---------------------------------------------------------------------------
@app.get("/ready", tags=["ops"])
def ready():
    results = {}
    failed = {}

    # --- Postgres check ---
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        results["postgres"] = "ok"
    except Exception as exc:
        # Surface the exception *type* only — never the connection URL or creds.
        failed["postgres"] = f"{type(exc).__name__}: unable to reach database"

    # --- MinIO check ---
    try:
        from app.composition_root import get_file_storage
        storage = get_file_storage()
        # head_bucket is a lightweight metadata call — no data transfer.
        storage._client.head_bucket(Bucket=storage._bucket_name)
        results["minio"] = "ok"
    except Exception as exc:
        failed["minio"] = f"{type(exc).__name__}: unable to reach object storage"

    if failed:
        return JSONResponse(
            status_code=503,
            content={"status": "not ready", **results, **failed},
        )

    return {"status": "ready", **results}
