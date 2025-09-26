"""
Authentication API routes.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Dict, Any

from app.core.auth import auth_service, get_current_active_user
from app.api.v1.schemas.auth import (
    UserRegister,
    UserLogin,
    Token,
    UserResponse
)
from database.session import get_session
from models.accounts import Account

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post("/register", response_model=UserResponse)
async def register(
    user_data: UserRegister,
    session: AsyncSession = Depends(get_session)
):
    """Register a new user."""
    try:
        user = await auth_service.register_user(
            session=session,
            email=user_data.email,
            password=user_data.password,
            name=user_data.name
        )
        
        return UserResponse(
            id=user.id,
            user_id=user.user_id,
            email=user.email,
            name=user.name,
            is_active=user.is_active
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post("/token", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_session)
):
    """Login and get access token."""
    user = await auth_service.authenticate_user(
        session=session,
        email=form_data.username,  # OAuth2 spec uses 'username' field
        password=form_data.password
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = auth_service.create_access_token(
        data={"sub": user.user_id}
    )
    
    refresh_token = auth_service.create_refresh_token(
        data={"sub": user.user_id}
    )
    
    return Token(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer"
    )


@router.post("/refresh", response_model=Token)
async def refresh_token(
    refresh_token: str,
    session: AsyncSession = Depends(get_session)
):
    """Refresh access token."""
    try:
        payload = auth_service.verify_token(refresh_token)
        
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        
        user_id = payload.get("sub")
        
        # Create new tokens
        access_token = auth_service.create_access_token(
            data={"sub": user_id}
        )
        
        new_refresh_token = auth_service.create_refresh_token(
            data={"sub": user_id}
        )
        
        return Token(
            access_token=access_token,
            refresh_token=new_refresh_token,
            token_type="bearer"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user(
    current_user: Account = Depends(get_current_active_user)
):
    """Get current user information."""
    return UserResponse(
        id=current_user.id,
        user_id=current_user.user_id,
        email=current_user.email,
        name=current_user.name,
        is_active=current_user.is_active
    )


@router.post("/logout")
async def logout(
    current_user: Account = Depends(get_current_active_user)
):
    """Logout user (client should discard tokens)."""
    # In a more complex implementation, you might want to:
    # - Add the token to a blacklist in Redis
    # - Clear server-side sessions
    # - Log the logout event
    
    return {"message": "Successfully logged out"}