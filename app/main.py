"""
Main FastAPI application entry point.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import time
import uuid

from app.config import settings
from app.core.logging import setup_logging, get_logger
from app.core.exceptions import BaseAPIException
from database.session import init_database, close_database

# Set up logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info(
        "Starting application",
        app_name=settings.app.app_name,
        environment=settings.app.app_env,
        debug=settings.app.debug
    )
    
    # Initialize database
    try:
        await init_database()
        logger.info("Database initialized")
    except Exception as e:
        logger.error("Failed to initialize database", error=str(e))
        # Continue anyway in development, fail in production
        if settings.is_production():
            raise
    
    # Initialize other services here
    # await init_redis()
    # await init_connectors()
    
    yield
    
    # Shutdown
    logger.info("Shutting down application")
    
    # Clean up resources
    await close_database()
    # await close_redis()
    # await close_connectors()
    
    logger.info("Application shutdown complete")


# Create FastAPI application
app = FastAPI(
    title=settings.app.app_name,
    version=settings.app.api_version,
    debug=settings.app.debug,
    lifespan=lifespan,
    docs_url="/docs" if settings.app.debug else None,  # Disable in production
    redoc_url="/redoc" if settings.app.debug else None,
    openapi_url=f"{settings.app.api_prefix}/openapi.json" if settings.app.debug else None,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.app.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add trusted host middleware for production
if settings.is_production():
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*.vestmarkets.com", "localhost"]  # Adjust as needed
    )


# Request ID middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add unique request ID to each request"""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id
    
    # Log request
    logger.info(
        "Request received",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        client=request.client.host if request.client else None
    )
    
    # Process request
    start_time = time.time()
    response = await call_next(request)
    duration = (time.time() - start_time) * 1000  # Convert to milliseconds
    
    # Add request ID to response headers
    response.headers["X-Request-ID"] = request_id
    
    # Log response
    logger.info(
        "Request completed",
        request_id=request_id,
        status_code=response.status_code,
        duration_ms=round(duration, 2)
    )
    
    return response


# Exception handlers
@app.exception_handler(BaseAPIException)
async def base_api_exception_handler(request: Request, exc: BaseAPIException):
    """Handle custom API exceptions"""
    logger.warning(
        "API exception",
        request_id=getattr(request.state, "request_id", None),
        error_code=exc.error_code,
        detail=exc.detail,
        context=exc.context
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict()
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle request validation errors"""
    logger.warning(
        "Validation error",
        request_id=getattr(request.state, "request_id", None),
        errors=exc.errors()
    )
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "VALIDATION_ERROR",
            "detail": "Request validation failed",
            "errors": exc.errors()
        }
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle Starlette HTTP exceptions"""
    logger.warning(
        "HTTP exception",
        request_id=getattr(request.state, "request_id", None),
        status_code=exc.status_code,
        detail=exc.detail
    )
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTP_ERROR",
            "detail": exc.detail,
            "status_code": exc.status_code
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions"""
    logger.error(
        "Unexpected error",
        request_id=getattr(request.state, "request_id", None),
        error=str(exc),
        exc_info=True
    )
    
    # Don't expose internal errors in production
    if settings.is_production():
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "INTERNAL_SERVER_ERROR",
                "detail": "An unexpected error occurred"
            }
        )
    else:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": "INTERNAL_SERVER_ERROR",
                "detail": str(exc),
                "type": type(exc).__name__
            }
        )


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": settings.app.app_name,
        "version": settings.app.api_version,
        "status": "running",
        "environment": settings.app.app_env
    }


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    # TODO: Add actual health checks (database, redis, etc.)
    return {
        "status": "healthy",
        "timestamp": time.time()
    }


# Include API routers
# TODO: Import and include routers
# from app.api.v1.routes import trading, accounts, positions, markets
# app.include_router(trading.router, prefix=f"{settings.app.api_prefix}/v1/trading", tags=["trading"])
# app.include_router(accounts.router, prefix=f"{settings.app.api_prefix}/v1/accounts", tags=["accounts"])
# app.include_router(positions.router, prefix=f"{settings.app.api_prefix}/v1/positions", tags=["positions"])
# app.include_router(markets.router, prefix=f"{settings.app.api_prefix}/v1/markets", tags=["markets"])


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.app.host,
        port=settings.app.port,
        reload=settings.app.debug,
        workers=1 if settings.app.debug else settings.app.workers,
        log_level=settings.app.log_level.lower(),
    )