"""
OpenStack VM Lifecycle Management API
FastAPI-based REST API for managing OpenStack VM operations.
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time
import uuid
import logging

from app.api.v1 import vms, flavors, images
from app.core.config import settings
from app.core.exceptions import OpenStackAPIError

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting OpenStack VM Lifecycle API")
    yield
    logger.info("Shutting down OpenStack VM Lifecycle API")


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="""
## OpenStack VM Lifecycle Management API

A production-ready REST API for managing OpenStack Virtual Machine lifecycle operations.

### Features
- **VM Lifecycle**: Create, list, get, start, stop, reboot, resize, and delete VMs
- **Flavors**: List and retrieve available VM flavors
- **Images**: List and retrieve available OS images
- **Health Checks**: Monitor API and OpenStack connectivity

### Authentication
All endpoints require a valid OpenStack token passed via the `X-Auth-Token` header.
    """,
    version=settings.VERSION,
    contact={
        "name": "Platform Engineering Team",
        "email": "platform@example.com",
    },
    license_info={"name": "MIT"},
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request ID + timing middleware
@app.middleware("http")
async def add_request_metadata(request: Request, call_next):
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    start_time = time.time()

    response = await call_next(request)

    process_time = (time.time() - start_time) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = f"{process_time:.2f}ms"

    logger.info(
        f"method={request.method} path={request.url.path} "
        f"status={response.status_code} duration={process_time:.2f}ms "
        f"request_id={request_id}"
    )
    return response


# Global exception handler
@app.exception_handler(OpenStackAPIError)
async def openstack_exception_handler(request: Request, exc: OpenStackAPIError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.error_code,
            "message": exc.message,
            "request_id": getattr(request.state, "request_id", None),
        },
    )


# Routers
app.include_router(vms.router, prefix=f"{settings.API_V1_PREFIX}/vms", tags=["VMs"])
app.include_router(flavors.router, prefix=f"{settings.API_V1_PREFIX}/flavors", tags=["Flavors"])
app.include_router(images.router, prefix=f"{settings.API_V1_PREFIX}/images", tags=["Images"])


@app.get("/health", tags=["Health"])
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "version": settings.VERSION,
        "service": settings.PROJECT_NAME,
    }


@app.get("/health/openstack", tags=["Health"])
async def openstack_health_check():
    """Check OpenStack connectivity."""
    from app.services.openstack_client import openstack_client
    try:
        connected = await openstack_client.check_connectivity()
        return {
            "status": "healthy" if connected else "degraded",
            "openstack_reachable": connected,
            "auth_url": settings.OS_AUTH_URL,
        }
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "openstack_reachable": False,
                "error": str(e),
            },
        )


@app.get("/", tags=["Root"])
async def root():
    """API root - redirect info."""
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
    }
