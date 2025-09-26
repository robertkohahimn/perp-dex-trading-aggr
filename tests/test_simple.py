"""Simple test to verify database setup."""
import pytest


@pytest.mark.asyncio
async def test_database_tables_created(test_engine, test_session):
    """Test that database tables are created."""
    # Import all models to ensure they're registered with Base
    from models import Base, Account, DexAccount, ApiKey, Order, Trade, Position, PositionHistory
    
    # Check that tables exist
    from sqlalchemy import text
    
    # Get table names from metadata
    tables = Base.metadata.tables.keys()
    print(f"Tables in metadata: {tables}")
    
    # Check tables in database using the same connection
    async with test_engine.connect() as conn:
        result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        existing_tables = [row[0] for row in result]
        print(f"Tables in database: {existing_tables}")
    
    # Verify tables in metadata
    assert 'accounts' in Base.metadata.tables
    assert 'dex_accounts' in Base.metadata.tables
    assert 'orders' in Base.metadata.tables
    assert 'positions' in Base.metadata.tables
    
    # Tables should have been created by test_engine fixture
    assert len(existing_tables) > 0, "No tables were created in the database"


@pytest.mark.asyncio  
async def test_can_create_account(test_session):
    """Test creating an account."""
    from models.accounts import Account
    
    account = Account(
        user_id="test-123",
        name="Test",
        email="test@test.com",
        is_active=True
    )
    test_session.add(account)
    await test_session.commit()
    
    assert account.id is not None