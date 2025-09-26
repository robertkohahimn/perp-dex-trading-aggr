"""
Pytest configuration and shared fixtures for all tests.
"""
import asyncio
import os
from typing import Generator, AsyncGenerator
from datetime import datetime
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool

from models.base import Base
# Import all models explicitly to register them with Base
from models.accounts import Account, DexAccount, ApiKey
from models.orders import Order, Trade
from models.positions import Position, PositionHistory
from app.config import Settings, AppSettings, DatabaseSettings, SecuritySettings
from database.session import get_session
from services.account_manager import AccountManager
from services.order_executor import OrderExecutor
from services.position_tracker import PositionTracker


# Test database URL - use temporary file instead of in-memory
import tempfile
test_db_fd, test_db_path = tempfile.mkstemp(suffix='.db')
TEST_DATABASE_URL = f"sqlite+aiosqlite:///{test_db_path}"


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_settings():
    """Create test settings."""
    # Generate a valid Fernet key for testing
    from cryptography.fernet import Fernet
    test_key = Fernet.generate_key().decode()
    
    # Create a test Settings object with test values
    class TestSettings:
        """Test settings object."""
        def __init__(self):
            self.app = type('obj', (object,), {
                'app_name': 'Test App',
                'app_env': 'test',
                'debug': True,
                'is_production': lambda: False
            })()
            self.database = type('obj', (object,), {
                'url': TEST_DATABASE_URL,
                'pool_size': 5,
                'max_overflow': 10,
                'redis_url': 'redis://localhost:6379/0'
            })()
            self.security = type('obj', (object,), {
                'secret_key': 'test-secret-key-for-jwt-tokens-minimum-32-chars',
                'encryption_key': test_key,
                'jwt_algorithm': 'HS256',
                'access_token_expire_minutes': 30,
                'refresh_token_expire_days': 7
            })()
            
        def is_production(self):
            return False
    
    return TestSettings()


@pytest_asyncio.fixture
async def test_engine():
    """Create a test database engine."""
    # Import all models to ensure they're registered with Base
    from models import Account, DexAccount, ApiKey, Order, Trade, Position, PositionHistory
    
    engine = create_async_engine(
        TEST_DATABASE_URL,
        poolclass=NullPool,
        echo=False
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()
    
    # Clean up the temporary database file
    try:
        if test_db_fd is not None:
            try:
                os.close(test_db_fd)
            except OSError:
                pass  # Already closed
        if test_db_path and os.path.exists(test_db_path):
            os.unlink(test_db_path)
    except Exception:
        pass


@pytest_asyncio.fixture
async def test_session(test_engine):
    """Create a test database session."""
    async_session_maker = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False
    )
    
    async with async_session_maker() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture
async def test_account_manager(test_session, test_settings):
    """Create an AccountManager instance for testing."""
    # Patch settings to use test settings
    import services.account_manager
    original_settings = services.account_manager.settings
    services.account_manager.settings = test_settings
    
    manager = AccountManager(session=test_session)
    
    yield manager
    
    # Restore original settings
    services.account_manager.settings = original_settings


@pytest_asyncio.fixture
async def test_order_executor(test_session):
    """Create an OrderExecutor instance for testing."""
    return OrderExecutor(session=test_session)


@pytest_asyncio.fixture
async def test_position_tracker(test_session):
    """Create a PositionTracker instance for testing."""
    return PositionTracker(session=test_session)


@pytest_asyncio.fixture
async def sample_user_account(test_session):
    """Create a sample user account in the database."""
    from models.accounts import Account
    
    account = Account(
        user_id="test-user-001",
        name="Test User",
        email="test@example.com",
        is_active=True
    )
    test_session.add(account)
    await test_session.commit()
    await test_session.refresh(account)
    return account


@pytest_asyncio.fixture
async def sample_dex_account(test_session, sample_user_account):
    """Create a sample DEX account in the database."""
    from models.accounts import DexAccount
    
    dex_account = DexAccount(
        account_id=sample_user_account.id,
        dex_name="mock",  # Changed from 'dex' to 'dex_name'
        account_name="test_account",
        is_testnet=True,
        is_active=True,
        total_balance=10000.0,  # Changed from 'balance' to 'total_balance'
        available_balance=10000.0,
        margin_balance=0.0
    )
    test_session.add(dex_account)
    await test_session.commit()
    await test_session.refresh(dex_account)
    return dex_account


@pytest_asyncio.fixture
async def sample_api_keys(test_session, sample_dex_account, test_settings):
    """Store encrypted API keys directly in DexAccount."""
    from cryptography.fernet import Fernet
    
    # Use the same key from test_settings
    key = test_settings.security.encryption_key
    if hasattr(key, 'get_secret_value'):
        key = key.get_secret_value()
    cipher = Fernet(key.encode() if isinstance(key, str) else key)
    
    # Update DexAccount with encrypted credentials
    sample_dex_account.encrypted_api_key = cipher.encrypt(b"test-api-key").decode()
    sample_dex_account.encrypted_api_secret = cipher.encrypt(b"test-api-secret").decode()
    
    test_session.add(sample_dex_account)
    await test_session.commit()
    
    return {"api_key": "test-api-key", "api_secret": "test-api-secret"}


@pytest_asyncio.fixture
async def sample_order(test_session, sample_dex_account):
    """Create a sample order in the database."""
    from models.orders import Order, OrderSide, OrderType, OrderStatus, TimeInForce
    
    order = Order(
        account_id=sample_dex_account.account_id,  # Added account_id
        dex_account_id=sample_dex_account.id,
        exchange_order_id="TEST-ORDER-001",
        symbol="BTC-PERP",
        side="BUY",  # Use string value
        order_type="LIMIT",  # Use string value
        quantity=0.1,
        price=50000.0,
        time_in_force="GTC",  # Use string value
        status="NEW",  # Use string value
        reduce_only=False,
        post_only=False
    )
    test_session.add(order)
    await test_session.commit()
    await test_session.refresh(order)
    return order


@pytest_asyncio.fixture
async def sample_position(test_session, sample_dex_account):
    """Create a sample position in the database."""
    from models.positions import Position, PositionSide, PositionStatus
    
    position = Position(
        account_id=sample_dex_account.account_id,  # Added account_id
        dex_account_id=sample_dex_account.id,
        symbol="BTC-PERP",
        side="LONG",  # Use string value
        quantity=0.1,  # Changed from 'size' to 'quantity'
        initial_quantity=0.1,  # Added initial_quantity
        entry_price=50000.0,
        mark_price=51000.0,
        unrealized_pnl=100.0,
        realized_pnl=0.0,
        margin=1000.0,
        leverage=5,
        status="OPEN",  # Use string value (PositionStatus.OPEN)
        opened_at=datetime.utcnow()  # Added required field
    )
    test_session.add(position)
    await test_session.commit()
    await test_session.refresh(position)
    return position


@pytest.fixture
def mock_connector_response():
    """Mock responses from DEX connectors."""
    return {
        "account_info": {
            "balance": 10000.0,
            "equity": 10500.0,
            "margin": 1000.0,
            "free_margin": 9000.0
        },
        "place_order": {
            "orderId": "MOCK-ORDER-123",
            "status": "NEW",
            "executedQty": 0,
            "avgPrice": 0
        },
        "cancel_order": True,
        "get_orders": [
            {
                "orderId": "MOCK-ORDER-123",
                "symbol": "BTC-PERP",
                "side": "BUY",
                "type": "LIMIT",
                "quantity": 0.1,
                "price": 50000.0,
                "status": "NEW",
                "executedQty": 0,
                "avgPrice": 0
            }
        ],
        "get_positions": [
            {
                "symbol": "BTC-PERP",
                "side": "LONG",
                "size": 0.1,
                "entryPrice": 50000.0,
                "markPrice": 51000.0,
                "unrealizedPnl": 100.0,
                "realizedPnl": 0.0,
                "margin": 1000.0,
                "leverage": 5,
                "liquidationPrice": 45000.0
            }
        ]
    }


@pytest.fixture
def mock_credentials():
    """Mock credentials for testing."""
    return {
        "api_key": "test-api-key",
        "api_secret": "test-api-secret"
    }


# Markers for different test types
def pytest_configure(config):
    """Configure custom markers."""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "asyncio: mark test as async"
    )