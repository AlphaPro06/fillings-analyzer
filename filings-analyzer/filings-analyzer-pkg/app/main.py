import logging

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.api import analyses, auth, documents

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("filings-analyzer")

app = FastAPI(
    title="Financial Filings Analyzer",
    description="Upload financial filings and ask questions about them via an LLM.",
    version="1.0.0",
)

from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(documents.router)
app.include_router(analyses.router)


@app.get("/health", tags=["health"])
def health_check():
    return {"status": "ok"}


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Catch-all so unexpected errors return clean JSON, not a stack trace.

    Known/expected errors are already handled as HTTPExceptions in the routers;
    this is the safety net for the truly unexpected.
    """
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )
