"""
Unit tests for the AccountManager service.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime

from services.account_manager import AccountManager, AccountInfo
from app.core.exceptions import (
    AccountNotFoundError,
    AccountAlreadyExistsError,
    DatabaseError
)


@pytest.mark.asyncio
@pytest.mark.unit
class TestAccountManager:
    """Test cases for AccountManager service."""
    
    async def test_add_account_success(self, test_account_manager, sample_user_account, mock_credentials):
        """Test successfully adding a new account."""
        # Mock the connector factory
        with patch.object(test_account_manager.connector_factory, 'create_connector') as mock_create_connector:
            mock_connector = AsyncMock()
            mock_connector.get_account_info = AsyncMock(return_value={'balance': 5000.0})
            mock_create_connector.return_value = mock_connector
            
            # Add account
            account_info = await test_account_manager.add_account(
                user_id=sample_user_account.id,
                dex="mock",
                name="new_account",
                credentials=mock_credentials,
                is_testnet=True
            )
            
            # Assertions
            assert account_info is not None
            assert account_info.dex == "mock"
            assert account_info.name == "new_account"
            assert account_info.balance == 5000.0
            assert account_info.is_testnet == True
            
            # Verify connector was called
            mock_create_connector.assert_called_once()
            mock_connector.get_account_info.assert_called_once()
    
    async def test_add_duplicate_account_fails(self, test_account_manager, sample_user_account, sample_dex_account, mock_credentials):
        """Test that adding a duplicate account raises an error."""
        with patch.object(test_account_manager.connector_factory, 'create_connector'):
            with pytest.raises(AccountAlreadyExistsError) as exc_info:
                await test_account_manager.add_account(
                    user_id=sample_user_account.id,
                    dex="mock",
                    name="test_account",  # Same as sample_dex_account
                    credentials=mock_credentials,
                    is_testnet=True
                )
            
            assert "already exists" in str(exc_info.value)
    
    async def test_get_account_existing(self, test_account_manager, sample_user_account, sample_dex_account):
        """Test retrieving an existing account."""
        account = await test_account_manager.get_account(
            user_id=sample_user_account.id,
            dex="mock",
            name="test_account"
        )
        
        assert account is not None
        assert account.account_id == sample_dex_account.id
        assert account.dex == "mock"
        assert account.name == "test_account"
        assert account.balance == 10000.0
    
    async def test_get_account_not_found(self, test_account_manager, sample_user_account):
        """Test retrieving a non-existent account returns None."""
        account = await test_account_manager.get_account(
            user_id=sample_user_account.id,
            dex="mock",
            name="nonexistent"
        )
        
        assert account is None
    
    async def test_get_account_with_cache(self, test_account_manager, sample_user_account, sample_dex_account):
        """Test that account retrieval uses cache on second call."""
        # First call - loads from database
        account1 = await test_account_manager.get_account(
            user_id=sample_user_account.id,
            dex="mock",
            name="test_account"
        )
        
        # Second call - should use cache
        account2 = await test_account_manager.get_account(
            user_id=sample_user_account.id,
            dex="mock",
            name="test_account"
        )
        
        assert account1.account_id == account2.account_id
        assert len(test_account_manager._cache) == 1
    
    async def test_list_accounts_all(self, test_account_manager, sample_user_account, sample_dex_account):
        """Test listing all accounts for a user."""
        accounts = await test_account_manager.list_accounts(
            user_id=sample_user_account.id
        )
        
        assert len(accounts) == 1
        assert accounts[0].dex == "mock"
        assert accounts[0].name == "test_account"
    
    async def test_list_accounts_by_dex(self, test_account_manager, sample_user_account, sample_dex_account):
        """Test listing accounts filtered by DEX."""
        accounts = await test_account_manager.list_accounts(
            user_id=sample_user_account.id,
            dex="mock"
        )
        
        assert len(accounts) == 1
        assert accounts[0].dex == "mock"
        
        # Test with non-existent DEX
        accounts = await test_account_manager.list_accounts(
            user_id=sample_user_account.id,
            dex="nonexistent"
        )
        
        assert len(accounts) == 0
    
    async def test_list_accounts_filter_active(self, test_account_manager, sample_user_account, sample_dex_account):
        """Test listing accounts filtered by active status."""
        # List active accounts
        accounts = await test_account_manager.list_accounts(
            user_id=sample_user_account.id,
            is_active=True
        )
        
        assert len(accounts) == 1
        assert accounts[0].is_active == True
        
        # List inactive accounts
        accounts = await test_account_manager.list_accounts(
            user_id=sample_user_account.id,
            is_active=False
        )
        
        assert len(accounts) == 0
    
    async def test_deactivate_account_success(self, test_account_manager, sample_user_account, sample_dex_account):
        """Test deactivating an account."""
        result = await test_account_manager.deactivate_account(
            user_id=sample_user_account.id,
            dex="mock",
            name="test_account"
        )
        
        assert result == True
        
        # Verify account is deactivated
        accounts = await test_account_manager.list_accounts(
            user_id=sample_user_account.id,
            is_active=True
        )
        assert len(accounts) == 0
    
    async def test_deactivate_nonexistent_account(self, test_account_manager, sample_user_account):
        """Test deactivating a non-existent account raises error."""
        with pytest.raises(AccountNotFoundError):
            await test_account_manager.deactivate_account(
                user_id=sample_user_account.id,
                dex="mock",
                name="nonexistent"
            )
    
    async def test_update_balance(self, test_account_manager, sample_user_account, sample_dex_account):
        """Test updating account balance."""
        result = await test_account_manager.update_balance(
            user_id=sample_user_account.id,
            dex="mock",
            name="test_account",
            new_balance=15000.0
        )
        
        assert result == True
        
        # Verify balance was updated
        account = await test_account_manager.get_account(
            user_id=sample_user_account.id,
            dex="mock",
            name="test_account"
        )
        
        # Clear cache to force database read
        test_account_manager.clear_cache()
        account = await test_account_manager.get_account(
            user_id=sample_user_account.id,
            dex="mock",
            name="test_account"
        )
        
        assert account.balance == 15000.0
    
    async def test_get_credentials(self, test_account_manager, sample_user_account, sample_dex_account, sample_api_keys):
        """Test retrieving decrypted credentials."""
        credentials = await test_account_manager.get_credentials(
            user_id=sample_user_account.id,
            dex="mock",
            name="test_account"
        )
        
        assert "api_key" in credentials
        assert "api_secret" in credentials
        assert credentials["api_key"] == "test-api-key"
        assert credentials["api_secret"] == "test-api-secret"
    
    async def test_get_credentials_nonexistent_account(self, test_account_manager, sample_user_account):
        """Test getting credentials for non-existent account raises error."""
        with pytest.raises(AccountNotFoundError):
            await test_account_manager.get_credentials(
                user_id=sample_user_account.id,
                dex="mock",
                name="nonexistent"
            )
    
    async def test_validate_credentials_success(self, test_account_manager, mock_credentials):
        """Test successful credential validation."""
        with patch.object(test_account_manager.connector_factory, 'create_connector') as mock_create_connector:
            mock_connector = AsyncMock()
            mock_connector.get_account_info = AsyncMock(return_value={'balance': 1000.0})
            mock_create_connector.return_value = mock_connector
            
            is_valid, message = await test_account_manager.validate_credentials(
                dex="mock",
                credentials=mock_credentials,
                is_testnet=True
            )
            
            assert is_valid == True
            assert message == "Credentials valid"
    
    async def test_validate_credentials_failure(self, test_account_manager, mock_credentials):
        """Test failed credential validation."""
        with patch.object(test_account_manager.connector_factory, 'create_connector') as mock_create_connector:
            mock_connector = AsyncMock()
            mock_connector.get_account_info = AsyncMock(side_effect=Exception("Invalid API key"))
            mock_create_connector.return_value = mock_connector
            
            is_valid, message = await test_account_manager.validate_credentials(
                dex="mock",
                credentials=mock_credentials,
                is_testnet=True
            )
            
            assert is_valid == False
            assert "Invalid API key" in message
    
    async def test_get_total_balance(self, test_account_manager, sample_user_account, sample_dex_account):
        """Test calculating total balance across accounts."""
        # Add another account
        with patch.object(test_account_manager.connector_factory, 'create_connector') as mock_create_connector:
            mock_connector = AsyncMock()
            mock_connector.get_account_info = AsyncMock(return_value={'balance': 5000.0})
            mock_create_connector.return_value = mock_connector
            
            await test_account_manager.add_account(
                user_id=sample_user_account.id,
                dex="hyperliquid",
                name="hl_account",
                credentials={"api_key": "test"},
                is_testnet=True
            )
        
        # Get total balance
        balances = await test_account_manager.get_total_balance(
            user_id=sample_user_account.id
        )
        
        assert balances['total'] == 15000.0  # 10000 + 5000
        assert balances['by_dex']['mock'] == 10000.0
        assert balances['by_dex']['hyperliquid'] == 5000.0
    
    async def test_encrypt_decrypt_credentials(self, test_account_manager):
        """Test credential encryption and decryption."""
        original = {
            "api_key": "my-secret-key",
            "api_secret": "my-secret-secret",
            "extra": {"nested": "value"}
        }
        
        # Encrypt
        encrypted = test_account_manager._encrypt_credentials(original)
        
        assert encrypted["api_key"] != original["api_key"]
        assert encrypted["api_secret"] != original["api_secret"]
        assert encrypted["extra"] != original["extra"]
        
        # Decrypt
        decrypted_key = test_account_manager._decrypt_value(encrypted["api_key"])
        decrypted_secret = test_account_manager._decrypt_value(encrypted["api_secret"])
        
        assert decrypted_key == original["api_key"]
        assert decrypted_secret == original["api_secret"]
    
    async def test_clear_cache(self, test_account_manager, sample_user_account, sample_dex_account):
        """Test clearing the account cache."""
        # Load account into cache
        await test_account_manager.get_account(
            user_id=sample_user_account.id,
            dex="mock",
            name="test_account"
        )
        
        assert len(test_account_manager._cache) == 1
        
        # Clear cache
        test_account_manager.clear_cache()
        
        assert len(test_account_manager._cache) == 0