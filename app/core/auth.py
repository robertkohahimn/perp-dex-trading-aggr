"""
Authentication and authorization module.
"""
from typing import Optional, Dict, Any
from datetime import datetime, timedelta
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.config import settings
from models.accounts import Account
from database.session import get_session
from app.core.exceptions import (
    UnauthorizedException,
    InvalidCredentialsError,
    TokenExpiredError
)
import logging

logger = logging.getLogger(__name__)

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")


class AuthService:
    """Authentication service for user management."""
    
    def __init__(self):
        self.secret_key = settings.security.secret_key.get_secret_value()
        self.algorithm = settings.security.jwt_algorithm
        self.access_token_expire_minutes = settings.security.access_token_expire_minutes
    
    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return pwd_context.verify(plain_password, hashed_password)
    
    def get_password_hash(self, password: str) -> str:
        """Hash a password."""
        return pwd_context.hash(password)
    
    def create_access_token(self, data: Dict[str, Any]) -> str:
        """Create a JWT access token."""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def create_refresh_token(self, data: Dict[str, Any]) -> str:
        """Create a JWT refresh token."""
        to_encode = data.copy()
        expire = datetime.utcnow() + timedelta(days=7)  # Refresh token valid for 7 days
        to_encode.update({"exp": expire, "type": "refresh"})
        encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
        return encoded_jwt
    
    def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify and decode a JWT token."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return payload
        except JWTError as e:
            logger.error(f"JWT verification failed: {e}")
            raise UnauthorizedException("Invalid token")
    
    async def authenticate_user(
        self, 
        session: AsyncSession, 
        email: str, 
        password: str
    ) -> Optional[Account]:
        """Authenticate a user."""
        # Get user by email
        stmt = select(Account).where(Account.email == email)
        result = await session.execute(stmt)
        user = result.scalar_one_or_none()
        
        if not user:
            return None
        
        if not self.verify_password(password, user.password_hash):
            return None
        
        if not user.is_active:
            raise UnauthorizedException("Account is disabled")
        
        return user
    
    async def register_user(
        self,
        session: AsyncSession,
        email: str,
        password: str,
        name: str
    ) -> Account:
        """Register a new user."""
        # Check if user already exists
        stmt = select(Account).where(Account.email == email)
        result = await session.execute(stmt)
        existing_user = result.scalar_one_or_none()
        
        if existing_user:
            raise ValueError("User with this email already exists")
        
        # Create new user
        hashed_password = self.get_password_hash(password)
        user = Account(
            email=email,
            name=name,
            password_hash=hashed_password,
            is_active=True,
            user_id=f"user_{email.split('@')[0]}_{datetime.utcnow().timestamp()}"
        )
        
        session.add(user)
        await session.commit()
        await session.refresh(user)
        
        return user


# Singleton instance
auth_service = AuthService()


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_session)
) -> Account:
    """Get the current authenticated user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = auth_service.verify_token(token)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except UnauthorizedException:
        raise credentials_exception
    
    # Get user from database
    stmt = select(Account).where(Account.user_id == user_id)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()
    
    if user is None:
        raise credentials_exception
    
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user"
        )
    
    return user


async def get_current_active_user(
    current_user: Account = Depends(get_current_user)
) -> Account:
    """Get the current active user."""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


def require_permission(permission: str):
    """Decorator to require specific permission."""
    async def permission_checker(
        current_user: Account = Depends(get_current_active_user)
    ):
        # Check if user has required permission
        # This is a simplified version - you might want to implement
        # a more complex permission system with roles
        if not getattr(current_user, f"can_{permission}", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Not enough permissions to {permission}"
            )
        return current_user
    return permission_checker