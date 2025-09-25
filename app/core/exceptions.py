"""
Custom exceptions and error handling for the application.
"""
from typing import Optional, Dict, Any
from fastapi import HTTPException, status


class BaseAPIException(HTTPException):
    """Base exception for API errors"""
    
    def __init__(
        self,
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail: str = "An error occurred",
        headers: Optional[Dict[str, str]] = None,
        error_code: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.error_code = error_code or self.__class__.__name__
        self.context = context or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API response"""
        return {
            "error": self.error_code,
            "detail": self.detail,
            "status_code": self.status_code,
            "context": self.context
        }


# Authentication Exceptions
class AuthenticationException(BaseAPIException):
    """Authentication failed"""
    def __init__(self, detail: str = "Authentication failed", **kwargs):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail,
            error_code="AUTHENTICATION_FAILED",
            **kwargs
        )


class InvalidCredentialsException(AuthenticationException):
    """Invalid credentials provided"""
    def __init__(self, detail: str = "Invalid credentials", **kwargs):
        super().__init__(
            detail=detail,
            error_code="INVALID_CREDENTIALS",
            **kwargs
        )


class TokenExpiredException(AuthenticationException):
    """Token has expired"""
    def __init__(self, detail: str = "Token has expired", **kwargs):
        super().__init__(
            detail=detail,
            error_code="TOKEN_EXPIRED",
            **kwargs
        )


# Authorization Exceptions
class AuthorizationException(BaseAPIException):
    """Authorization failed"""
    def __init__(self, detail: str = "Not authorized", **kwargs):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=detail,
            error_code="NOT_AUTHORIZED",
            **kwargs
        )


class InsufficientPermissionsException(AuthorizationException):
    """Insufficient permissions"""
    def __init__(self, detail: str = "Insufficient permissions", **kwargs):
        super().__init__(
            detail=detail,
            error_code="INSUFFICIENT_PERMISSIONS",
            **kwargs
        )


# Resource Exceptions
class ResourceNotFoundException(BaseAPIException):
    """Resource not found"""
    def __init__(self, resource: str, detail: Optional[str] = None, **kwargs):
        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=detail or f"{resource} not found",
            error_code="RESOURCE_NOT_FOUND",
            context={"resource": resource},
            **kwargs
        )


class ResourceAlreadyExistsException(BaseAPIException):
    """Resource already exists"""
    def __init__(self, resource: str, detail: Optional[str] = None, **kwargs):
        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=detail or f"{resource} already exists",
            error_code="RESOURCE_ALREADY_EXISTS",
            context={"resource": resource},
            **kwargs
        )


# Validation Exceptions
class ValidationException(BaseAPIException):
    """Validation error"""
    def __init__(self, detail: str = "Validation failed", errors: Optional[Dict] = None, **kwargs):
        super().__init__(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail,
            error_code="VALIDATION_ERROR",
            context={"errors": errors or {}},
            **kwargs
        )


class InvalidRequestException(ValidationException):
    """Invalid request"""
    def __init__(self, detail: str = "Invalid request", **kwargs):
        super().__init__(
            detail=detail,
            error_code="INVALID_REQUEST",
            **kwargs
        )


# Trading Exceptions
class TradingException(BaseAPIException):
    """Base trading exception"""
    def __init__(self, detail: str = "Trading error", **kwargs):
        super().__init__(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=detail,
            error_code="TRADING_ERROR",
            **kwargs
        )


class InsufficientBalanceException(TradingException):
    """Insufficient balance for trade"""
    def __init__(self, required: float, available: float, **kwargs):
        super().__init__(
            detail=f"Insufficient balance. Required: {required}, Available: {available}",
            error_code="INSUFFICIENT_BALANCE",
            context={"required": required, "available": available},
            **kwargs
        )


class OrderNotFoundException(TradingException):
    """Order not found"""
    def __init__(self, order_id: str, **kwargs):
        super().__init__(
            detail=f"Order {order_id} not found",
            error_code="ORDER_NOT_FOUND",
            context={"order_id": order_id},
            **kwargs
        )


class OrderRejectedException(TradingException):
    """Order rejected by exchange"""
    def __init__(self, reason: str, order_details: Optional[Dict] = None, **kwargs):
        super().__init__(
            detail=f"Order rejected: {reason}",
            error_code="ORDER_REJECTED",
            context={"reason": reason, "order_details": order_details or {}},
            **kwargs
        )


class PositionNotFoundException(TradingException):
    """Position not found"""
    def __init__(self, symbol: str, **kwargs):
        super().__init__(
            detail=f"Position for {symbol} not found",
            error_code="POSITION_NOT_FOUND",
            context={"symbol": symbol},
            **kwargs
        )


class RiskLimitExceededException(TradingException):
    """Risk limit exceeded"""
    def __init__(self, limit_type: str, value: float, limit: float, **kwargs):
        super().__init__(
            detail=f"{limit_type} limit exceeded. Value: {value}, Limit: {limit}",
            error_code="RISK_LIMIT_EXCEEDED",
            context={"limit_type": limit_type, "value": value, "limit": limit},
            **kwargs
        )


# DEX Exceptions
class DEXException(BaseAPIException):
    """Base DEX exception"""
    def __init__(self, dex: str, detail: str = "DEX error", **kwargs):
        super().__init__(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=detail,
            error_code="DEX_ERROR",
            context={"dex": dex},
            **kwargs
        )


class DEXConnectionException(DEXException):
    """DEX connection error"""
    def __init__(self, dex: str, detail: Optional[str] = None, **kwargs):
        super().__init__(
            dex=dex,
            detail=detail or f"Failed to connect to {dex}",
            error_code="DEX_CONNECTION_ERROR",
            **kwargs
        )


class DEXRateLimitException(DEXException):
    """DEX rate limit exceeded"""
    def __init__(self, dex: str, retry_after: Optional[int] = None, **kwargs):
        headers = {"Retry-After": str(retry_after)} if retry_after else None
        super().__init__(
            dex=dex,
            detail=f"Rate limit exceeded for {dex}",
            error_code="DEX_RATE_LIMIT",
            headers=headers,
            **kwargs
        )


# System Exceptions
class SystemException(BaseAPIException):
    """System error"""
    def __init__(self, detail: str = "System error", **kwargs):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail,
            error_code="SYSTEM_ERROR",
            **kwargs
        )


class DatabaseException(SystemException):
    """Database error"""
    def __init__(self, detail: str = "Database error", **kwargs):
        super().__init__(
            detail=detail,
            error_code="DATABASE_ERROR",
            **kwargs
        )


class ExternalServiceException(SystemException):
    """External service error"""
    def __init__(self, service: str, detail: Optional[str] = None, **kwargs):
        super().__init__(
            detail=detail or f"External service {service} error",
            error_code="EXTERNAL_SERVICE_ERROR",
            context={"service": service},
            **kwargs
        )


# Rate Limiting Exception
class RateLimitException(BaseAPIException):
    """Rate limit exceeded"""
    def __init__(self, retry_after: int = 60, **kwargs):
        super().__init__(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            error_code="RATE_LIMIT_EXCEEDED",
            headers={"Retry-After": str(retry_after)},
            context={"retry_after": retry_after},
            **kwargs
        )