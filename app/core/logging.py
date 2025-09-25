"""
Logging configuration for the application.
"""
import logging
import sys
from typing import Any, Dict, Optional
import structlog
from structlog.stdlib import LoggerFactory
from pythonjsonlogger import jsonlogger
from app.config import settings


def setup_logging() -> None:
    """
    Configure logging for the application.
    Uses structlog for structured logging with JSON output in production.
    """
    # Set the logging level
    log_level = getattr(logging, settings.app.log_level.upper(), logging.INFO)
    
    # Configure Python standard logging
    logging.basicConfig(
        level=log_level,
        stream=sys.stdout,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s" if settings.app.debug else None
    )
    
    # Configure JSON logging for production
    if settings.is_production():
        # Create JSON formatter
        json_formatter = jsonlogger.JsonFormatter(
            fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )
        
        # Update all handlers to use JSON formatter
        for handler in logging.root.handlers:
            handler.setFormatter(json_formatter)
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.dict_tracebacks,
            # Use JSON renderer in production, console in development
            structlog.dev.ConsoleRenderer() if settings.app.debug else structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    
    # Suppress noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    
    # Set specific log levels for our modules
    logging.getLogger("app").setLevel(log_level)
    logging.getLogger("connectors").setLevel(log_level)
    logging.getLogger("services").setLevel(log_level)


def get_logger(name: Optional[str] = None) -> structlog.BoundLogger:
    """
    Get a structured logger instance.
    
    Args:
        name: Logger name (usually __name__ from the calling module)
    
    Returns:
        Structured logger instance
    """
    return structlog.get_logger(name)


class LoggingContext:
    """Context manager for adding temporary logging context"""
    
    def __init__(self, logger: structlog.BoundLogger, **kwargs):
        self.logger = logger
        self.context = kwargs
        self.token = None
    
    def __enter__(self):
        self.token = structlog.contextvars.bind_contextvars(**self.context)
        return self.logger
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.token:
            structlog.contextvars.unbind_contextvars(*self.context.keys())


def log_request(request_id: str, method: str, path: str, **kwargs) -> Dict[str, Any]:
    """
    Create a log entry for an HTTP request.
    
    Args:
        request_id: Unique request ID
        method: HTTP method
        path: Request path
        **kwargs: Additional context
    
    Returns:
        Log entry dictionary
    """
    return {
        "event": "http_request",
        "request_id": request_id,
        "method": method,
        "path": path,
        **kwargs
    }


def log_response(request_id: str, status_code: int, duration_ms: float, **kwargs) -> Dict[str, Any]:
    """
    Create a log entry for an HTTP response.
    
    Args:
        request_id: Unique request ID
        status_code: HTTP status code
        duration_ms: Request duration in milliseconds
        **kwargs: Additional context
    
    Returns:
        Log entry dictionary
    """
    return {
        "event": "http_response",
        "request_id": request_id,
        "status_code": status_code,
        "duration_ms": duration_ms,
        **kwargs
    }


def log_error(error: Exception, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Create a log entry for an error.
    
    Args:
        error: Exception instance
        context: Additional context
    
    Returns:
        Log entry dictionary
    """
    return {
        "event": "error",
        "error_type": type(error).__name__,
        "error_message": str(error),
        "context": context or {}
    }


def log_trade_event(
    event_type: str,
    symbol: str,
    dex: str,
    account_id: int,
    **kwargs
) -> Dict[str, Any]:
    """
    Create a log entry for a trading event.
    
    Args:
        event_type: Type of event (order_placed, order_filled, etc.)
        symbol: Trading symbol
        dex: DEX name
        account_id: Account ID
        **kwargs: Additional event data
    
    Returns:
        Log entry dictionary
    """
    return {
        "event": f"trade_{event_type}",
        "symbol": symbol,
        "dex": dex,
        "account_id": account_id,
        **kwargs
    }