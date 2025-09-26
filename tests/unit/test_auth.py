"""
Unit tests for authentication service.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
from jose import jwt

from app.core.auth import AuthService, auth_service, get_current_user
from app.core.exceptions import UnauthorizedException, InvalidCredentialsError
from models.accounts import Account


@pytest.mark.asyncio
@pytest.mark.unit
class TestAuthService:
    """Test cases for AuthService."""
    
    @pytest.fixture
    def auth_svc(self):
        """Create auth service instance."""
        return AuthService()
    
    def test_password_hashing(self, auth_svc):
        """Test password hashing and verification."""
        password = "TestPassword123!"
        
        # Hash password
        hashed = auth_svc.get_password_hash(password)
        assert hashed != password
        assert len(hashed) > 50  # Bcrypt hashes are long
        
        # Verify correct password
        assert auth_svc.verify_password(password, hashed) is True
        
        # Verify incorrect password
        assert auth_svc.verify_password("WrongPassword", hashed) is False
    
    def test_create_access_token(self, auth_svc):
        """Test JWT access token creation."""
        user_data = {"sub": "user123", "email": "test@example.com"}
        
        token = auth_svc.create_access_token(user_data)
        
        # Verify token is a string
        assert isinstance(token, str)
        assert len(token) > 50
        
        # Decode and verify token contents
        payload = jwt.decode(
            token,
            auth_svc.secret_key,
            algorithms=[auth_svc.algorithm]
        )
        
        assert payload["sub"] == "user123"
        assert payload["email"] == "test@example.com"
        assert "exp" in payload
        
        # Check expiration is set correctly
        exp_time = datetime.utcfromtimestamp(payload["exp"])
        expected_exp = datetime.utcnow() + timedelta(minutes=auth_svc.access_token_expire_minutes)
        assert abs((exp_time - expected_exp).total_seconds()) < 5  # Allow 5 second difference
    
    def test_create_refresh_token(self, auth_svc):
        """Test JWT refresh token creation."""
        user_data = {"sub": "user123"}
        
        token = auth_svc.create_refresh_token(user_data)
        
        # Decode and verify token contents
        payload = jwt.decode(
            token,
            auth_svc.secret_key,
            algorithms=[auth_svc.algorithm]
        )
        
        assert payload["sub"] == "user123"
        assert payload["type"] == "refresh"
        assert "exp" in payload
        
        # Check expiration is set correctly (7 days)
        exp_time = datetime.utcfromtimestamp(payload["exp"])
        expected_exp = datetime.utcnow() + timedelta(days=7)
        assert abs((exp_time - expected_exp).total_seconds()) < 5
    
    def test_verify_token_valid(self, auth_svc):
        """Test verifying a valid token."""
        user_data = {"sub": "user123", "email": "test@example.com"}
        token = auth_svc.create_access_token(user_data)
        
        payload = auth_svc.verify_token(token)
        
        assert payload["sub"] == "user123"
        assert payload["email"] == "test@example.com"
    
    def test_verify_token_invalid(self, auth_svc):
        """Test verifying an invalid token."""
        invalid_token = "invalid.token.here"
        
        with pytest.raises(UnauthorizedException) as exc:
            auth_svc.verify_token(invalid_token)
        
        assert "Invalid token" in str(exc.value)
    
    def test_verify_token_expired(self, auth_svc):
        """Test verifying an expired token."""
        # Create token with past expiration
        past_time = datetime.utcnow() - timedelta(hours=1)
        expired_token = jwt.encode(
            {"sub": "user123", "exp": past_time},
            auth_svc.secret_key,
            algorithm=auth_svc.algorithm
        )
        
        with pytest.raises(UnauthorizedException):
            auth_svc.verify_token(expired_token)
    
    async def test_authenticate_user_success(self, auth_svc, test_session):
        """Test successful user authentication."""
        # Create a test user
        password = "TestPassword123"
        hashed_password = auth_svc.get_password_hash(password)
        
        user = Account(
            user_id="test_user",
            email="test@example.com",
            name="Test User",
            password_hash=hashed_password,
            is_active=True
        )
        test_session.add(user)
        await test_session.commit()
        
        # Authenticate
        result = await auth_svc.authenticate_user(
            test_session,
            "test@example.com",
            password
        )
        
        assert result is not None
        assert result.email == "test@example.com"
        assert result.user_id == "test_user"
    
    async def test_authenticate_user_wrong_password(self, auth_svc, test_session):
        """Test authentication with wrong password."""
        # Create a test user
        user = Account(
            user_id="test_user",
            email="test@example.com",
            name="Test User",
            password_hash=auth_svc.get_password_hash("CorrectPassword"),
            is_active=True
        )
        test_session.add(user)
        await test_session.commit()
        
        # Try to authenticate with wrong password
        result = await auth_svc.authenticate_user(
            test_session,
            "test@example.com",
            "WrongPassword"
        )
        
        assert result is None
    
    async def test_authenticate_user_not_found(self, auth_svc, test_session):
        """Test authentication with non-existent user."""
        result = await auth_svc.authenticate_user(
            test_session,
            "nonexistent@example.com",
            "password"
        )
        
        assert result is None
    
    async def test_authenticate_user_inactive(self, auth_svc, test_session):
        """Test authentication with inactive user."""
        # Create an inactive user
        password = "TestPassword123"
        user = Account(
            user_id="test_user",
            email="test@example.com",
            name="Test User",
            password_hash=auth_svc.get_password_hash(password),
            is_active=False
        )
        test_session.add(user)
        await test_session.commit()
        
        # Try to authenticate
        with pytest.raises(UnauthorizedException) as exc:
            await auth_svc.authenticate_user(
                test_session,
                "test@example.com",
                password
            )
        
        assert "Account is disabled" in str(exc.value)
    
    async def test_register_user_success(self, auth_svc, test_session):
        """Test successful user registration."""
        result = await auth_svc.register_user(
            test_session,
            email="newuser@example.com",
            password="SecurePassword123",
            name="New User"
        )
        
        assert result is not None
        assert result.email == "newuser@example.com"
        assert result.name == "New User"
        assert result.is_active is True
        assert result.user_id.startswith("user_newuser_")
        assert result.password_hash is not None
        
        # Verify password was hashed
        assert auth_svc.verify_password("SecurePassword123", result.password_hash)
    
    async def test_register_user_duplicate_email(self, auth_svc, test_session):
        """Test registration with duplicate email."""
        # Create first user
        await auth_svc.register_user(
            test_session,
            email="existing@example.com",
            password="Password123",
            name="First User"
        )
        
        # Try to create second user with same email
        with pytest.raises(ValueError) as exc:
            await auth_svc.register_user(
                test_session,
                email="existing@example.com",
                password="Password456",
                name="Second User"
            )
        
        assert "already exists" in str(exc.value)


@pytest.mark.asyncio
@pytest.mark.unit
class TestGetCurrentUser:
    """Test cases for get_current_user dependency."""
    
    async def test_get_current_user_valid_token(self, test_session):
        """Test getting current user with valid token."""
        # Create a test user
        user = Account(
            id=1,
            user_id="test_user_123",
            email="test@example.com",
            name="Test User",
            password_hash="hashed",
            is_active=True
        )
        test_session.add(user)
        await test_session.commit()
        
        # Create a valid token
        token = auth_service.create_access_token({"sub": "test_user_123"})
        
        # Mock the OAuth2 dependency
        from fastapi import HTTPException
        
        with patch('app.core.auth.oauth2_scheme') as mock_oauth:
            mock_oauth.return_value = token
            
            # Get current user
            current_user = await get_current_user(token, test_session)
            
            assert current_user is not None
            assert current_user.user_id == "test_user_123"
            assert current_user.email == "test@example.com"
    
    async def test_get_current_user_invalid_token(self, test_session):
        """Test getting current user with invalid token."""
        from fastapi import HTTPException
        
        invalid_token = "invalid.token.here"
        
        with pytest.raises(HTTPException) as exc:
            await get_current_user(invalid_token, test_session)
        
        assert exc.value.status_code == 401
        assert "Could not validate credentials" in exc.value.detail
    
    async def test_get_current_user_nonexistent_user(self, test_session):
        """Test getting current user when user doesn't exist."""
        from fastapi import HTTPException
        
        # Create token for non-existent user
        token = auth_service.create_access_token({"sub": "nonexistent_user"})
        
        with pytest.raises(HTTPException) as exc:
            await get_current_user(token, test_session)
        
        assert exc.value.status_code == 401
        assert "Could not validate credentials" in exc.value.detail
    
    async def test_get_current_user_inactive(self, test_session):
        """Test getting current user when user is inactive."""
        from fastapi import HTTPException
        
        # Create an inactive user
        user = Account(
            id=1,
            user_id="inactive_user",
            email="inactive@example.com",
            name="Inactive User",
            password_hash="hashed",
            is_active=False
        )
        test_session.add(user)
        await test_session.commit()
        
        # Create token for inactive user
        token = auth_service.create_access_token({"sub": "inactive_user"})
        
        with pytest.raises(HTTPException) as exc:
            await get_current_user(token, test_session)
        
        assert exc.value.status_code == 400
        assert "Inactive user" in exc.value.detail