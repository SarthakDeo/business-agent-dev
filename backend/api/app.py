"""FastAPI ASGI Application for Voice2Flow Business Agent."""

import logging
from uuid import uuid4
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Load environment configuration on startup
load_dotenv()

from .routes import (
    activity_router,
    agent_router,
    automations_router,
    dashboard_router,
    executions_router,
    integrations_router,
)
from ..agent.automation_manager import (
    AutomationAmbiguousError,
    AutomationCreationError,
    AutomationNotFoundError,
)
from ..agent.confirmation_manager import HighRiskBlockedError
from ..agent.permission_manager import PermissionDeniedError
from ..agent.validator import ValidationError
from ..integrations.postgres_persistence import PostgresPersistenceError

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Voice2Flow AI Business Agent API",
    description="HTTP API Boundary for Voice2Flow Orchestrator, Next.js Dashboard & Automations",
    version="1.0.0",
)

# CORS configuration for Next.js development server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── EXCEPTION HANDLERS ───────────────────────────────────────────────────────

@app.exception_handler(PermissionDeniedError)
async def permission_denied_handler(request: Request, exc: PermissionDeniedError):
    req_id = getattr(request.state, "request_id", str(uuid4()))
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={
            "error": str(exc),
            "error_code": "PERMISSION_DENIED",
            "status": "blocked",
            "request_id": req_id,
        },
    )


@app.exception_handler(HighRiskBlockedError)
async def high_risk_blocked_handler(request: Request, exc: HighRiskBlockedError):
    req_id = getattr(request.state, "request_id", str(uuid4()))
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={
            "error": str(exc),
            "error_code": "HIGH_RISK_BLOCKED",
            "status": "blocked",
            "request_id": req_id,
        },
    )


@app.exception_handler(AutomationNotFoundError)
async def automation_not_found_handler(request: Request, exc: AutomationNotFoundError):
    req_id = getattr(request.state, "request_id", str(uuid4()))
    return JSONResponse(
        status_code=status.HTTP_404_NOT_FOUND,
        content={
            "error": str(exc),
            "error_code": exc.code or "AUTOMATION_NOT_FOUND",
            "status": "error",
            "request_id": req_id,
        },
    )


@app.exception_handler(AutomationAmbiguousError)
async def automation_ambiguous_handler(request: Request, exc: AutomationAmbiguousError):
    req_id = getattr(request.state, "request_id", str(uuid4()))
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": str(exc),
            "error_code": exc.code or "AUTOMATION_AMBIGUOUS",
            "status": "error",
            "request_id": req_id,
        },
    )


@app.exception_handler(AutomationCreationError)
async def automation_creation_handler(request: Request, exc: AutomationCreationError):
    req_id = getattr(request.state, "request_id", str(uuid4()))
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": exc.message,
            "error_code": exc.code or "AUTOMATION_CREATION_FAILED",
            "status": "error",
            "request_id": req_id,
        },
    )


@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError):
    req_id = getattr(request.state, "request_id", str(uuid4()))
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "error": str(exc),
            "error_code": "VALIDATION_FAILED",
            "status": "error",
            "request_id": req_id,
        },
    )


@app.exception_handler(PostgresPersistenceError)
async def postgres_error_handler(request: Request, exc: PostgresPersistenceError):
    req_id = getattr(request.state, "request_id", str(uuid4()))
    logger.error(f"[req={req_id}] Database operation failed: {exc}")
    return JSONResponse(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "error": "Persistence operation failed",
            "error_code": "DATABASE_UNAVAILABLE",
            "status": "error",
            "request_id": req_id,
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    req_id = getattr(request.state, "request_id", str(uuid4()))
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "error_code": f"HTTP_{exc.status_code}",
            "status": "error",
            "request_id": req_id,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    req_id = getattr(request.state, "request_id", str(uuid4()))
    logger.exception(f"[req={req_id}] Unexpected server error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "An internal server error occurred.",
            "error_code": "INTERNAL_SERVER_ERROR",
            "status": "error",
            "request_id": req_id,
        },
    )


# ─── ROUTES INCLUSION ─────────────────────────────────────────────────────────

app.include_router(agent_router)
app.include_router(automations_router)
app.include_router(integrations_router)
app.include_router(dashboard_router)
app.include_router(activity_router)
app.include_router(executions_router)


@app.get("/api/healthz", tags=["Health"])
def health_check():
    """Health check endpoint for container and gateway liveness."""
    return {"status": "ok", "service": "voice2flow-api"}
