"""
Enhanced account management service with database integration, encryption, and validation.
"""
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from cryptography.fernet import Fernet
import json
import logging

from models.accounts import Account, DexAccount as DexAccountModel
from database.session import get_session
from app.config import settings
from app.core.exceptions import (
    AccountNotFoundError, 
    AccountAlreadyExistsError,
    InvalidCredentialsError,
    DatabaseError
)
from connectors.factory import ConnectorFactory

logger = logging.getLogger(__name__)


class AccountInfo:
    """Account information with balance and status."""
    def __init__(self, account_id: int, dex: str, name: str, 
                 balance: float = 0.0, is_active: bool = True,
                 is_testnet: bool = False, created_at: datetime = None):
        self.account_id = account_id
        self.dex = dex
        self.name = name
        self.balance = balance
        self.is_active = is_active
        self.is_testnet = is_testnet
        self.created_at = created_at or datetime.utcnow()
        self.positions = []
        self.open_orders = []


class AccountManager:
    """Enhanced account management service with database persistence."""
    
    def __init__(self, session: Optional[AsyncSession] = None):
        self.session = session
        # Handle SecretStr from Pydantic settings
        encryption_key = settings.security.encryption_key
        if encryption_key:
            # Get the actual string value from SecretStr
            key_value = encryption_key.get_secret_value() if hasattr(encryption_key, 'get_secret_value') else str(encryption_key)
            self.cipher_suite = Fernet(key_value.encode())
        else:
            self.cipher_suite = None
        self.connector_factory = ConnectorFactory()
        self._cache: Dict[str, AccountInfo] = {}
    
    async def add_account(self, 
                         user_id: int,
                         dex: str, 
                         name: str, 
                         credentials: Dict[str, Any], 
                         is_testnet: bool = False) -> AccountInfo:
        """Add a new account with encrypted credentials."""
        async with (self.session or get_session()) as session:
            try:
                # Check if account already exists
                existing = await session.execute(
                    select(DexAccountModel).where(
                        and_(
                            DexAccountModel.account_id == user_id,
                            DexAccountModel.dex_name == dex,
                            DexAccountModel.account_name == name
                        )
                    )
                )
                if existing.scalar_one_or_none():
                    raise AccountAlreadyExistsError(f"Account {name} already exists for {dex}")
                
                # Validate credentials with connector
                connector = self.connector_factory.create_connector(dex, credentials, is_testnet)
                account_info = await connector.get_account_info()
                
                # Encrypt credentials
                encrypted_creds = self._encrypt_credentials(credentials)
                
                # Create database entry with encrypted credentials
                dex_account = DexAccountModel(
                    account_id=user_id,
                    dex_name=dex,
                    account_name=name,
                    is_testnet=is_testnet,
                    is_active=True,
                    total_balance=account_info.get('balance', 0.0),
                    encrypted_api_key=encrypted_creds.get('api_key'),
                    encrypted_api_secret=encrypted_creds.get('api_secret'),
                    encrypted_private_key=encrypted_creds.get('private_key')
                )
                session.add(dex_account)
                
                await session.commit()
                
                return AccountInfo(
                    account_id=dex_account.id,
                    dex=dex,
                    name=name,
                    balance=account_info.get('balance', 0.0),
                    is_testnet=is_testnet
                )
                
            except AccountAlreadyExistsError:
                await session.rollback()
                raise
            except Exception as e:
                await session.rollback()
                logger.error(f"Failed to add account: {e}")
                raise DatabaseError(f"Failed to add account: {str(e)}")
    
    async def get_account(self, 
                         user_id: int,
                         dex: str, 
                         name: str) -> Optional[AccountInfo]:
        """Get a specific account with decrypted credentials."""
        cache_key = f"{user_id}_{dex}_{name}"
        
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        async with (self.session or get_session()) as session:
            result = await session.execute(
                select(DexAccountModel).where(
                    and_(
                        DexAccountModel.account_id == user_id,
                        DexAccountModel.dex_name == dex,
                        DexAccountModel.account_name == name
                    )
                )
            )
            dex_account = result.scalar_one_or_none()
            
            if not dex_account:
                return None
            
            account_info = AccountInfo(
                account_id=dex_account.id,
                dex=dex_account.dex_name,
                name=dex_account.account_name,
                balance=dex_account.total_balance,
                is_active=dex_account.is_active,
                is_testnet=dex_account.is_testnet,
                created_at=dex_account.created_at
            )
            
            self._cache[cache_key] = account_info
            return account_info
    
    async def list_accounts(self, 
                           user_id: int,
                           dex: Optional[str] = None,
                           is_active: bool = True) -> List[AccountInfo]:
        """List accounts with optional filtering."""
        async with (self.session or get_session()) as session:
            query = select(DexAccountModel).where(
                DexAccountModel.account_id == user_id
            )
            
            if dex:
                query = query.where(DexAccountModel.dex_name == dex)
            
            if is_active is not None:
                query = query.where(DexAccountModel.is_active == is_active)
            
            result = await session.execute(query)
            dex_accounts = result.scalars().all()
            
            return [
                AccountInfo(
                    account_id=acc.id,
                    dex=acc.dex_name,
                    name=acc.account_name,
                    balance=acc.total_balance,
                    is_active=acc.is_active,
                    is_testnet=acc.is_testnet,
                    created_at=acc.created_at
                )
                for acc in dex_accounts
            ]
    
    async def deactivate_account(self, 
                                user_id: int,
                                dex: str, 
                                name: str) -> bool:
        """Deactivate an account (soft delete)."""
        async with (self.session or get_session()) as session:
            result = await session.execute(
                select(DexAccountModel).where(
                    and_(
                        DexAccountModel.account_id == user_id,
                        DexAccountModel.dex_name == dex,
                        DexAccountModel.account_name == name
                    )
                )
            )
            dex_account = result.scalar_one_or_none()
            
            if not dex_account:
                raise AccountNotFoundError(f"Account {name} not found for {dex}")
            
            dex_account.is_active = False
            await session.commit()
            
            # Clear cache
            cache_key = f"{user_id}_{dex}_{name}"
            self._cache.pop(cache_key, None)
            
            return True
    
    async def update_balance(self, 
                            user_id: int,
                            dex: str, 
                            name: str,
                            new_balance: float) -> bool:
        """Update account balance."""
        async with (self.session or get_session()) as session:
            result = await session.execute(
                select(DexAccountModel).where(
                    and_(
                        DexAccountModel.account_id == user_id,
                        DexAccountModel.dex_name == dex,
                        DexAccountModel.account_name == name
                    )
                )
            )
            dex_account = result.scalar_one_or_none()
            
            if not dex_account:
                return False
            
            dex_account.total_balance = new_balance
            await session.commit()
            
            # Update cache
            cache_key = f"{user_id}_{dex}_{name}"
            if cache_key in self._cache:
                self._cache[cache_key].balance = new_balance
            
            return True
    
    async def get_credentials(self, 
                            user_id: int,
                            dex: str, 
                            name: str) -> Dict[str, str]:
        """Get decrypted credentials for an account."""
        async with (self.session or get_session()) as session:
            result = await session.execute(
                select(DexAccountModel).where(
                    and_(
                        DexAccountModel.account_id == user_id,
                        DexAccountModel.dex_name == dex,
                        DexAccountModel.account_name == name
                    )
                )
            )
            dex_account = result.scalar_one_or_none()
            
            if not dex_account:
                raise AccountNotFoundError(f"Account {name} not found for {dex}")
            
            # Decrypt credentials from DexAccount fields
            credentials = {}
            if dex_account.encrypted_api_key:
                credentials['api_key'] = self._decrypt_value(dex_account.encrypted_api_key)
            if dex_account.encrypted_api_secret:
                credentials['api_secret'] = self._decrypt_value(dex_account.encrypted_api_secret)
            if dex_account.encrypted_private_key:
                credentials['private_key'] = self._decrypt_value(dex_account.encrypted_private_key)
            
            return credentials
    
    async def validate_credentials(self, 
                                  dex: str, 
                                  credentials: Dict[str, Any],
                                  is_testnet: bool = False) -> Tuple[bool, str]:
        """Validate credentials by attempting to connect to DEX."""
        try:
            connector = self.connector_factory.create_connector(dex, credentials, is_testnet)
            account_info = await connector.get_account_info()
            return True, "Credentials valid"
        except Exception as e:
            logger.error(f"Credential validation failed for {dex}: {e}")
            return False, str(e)
    
    def _encrypt_credentials(self, credentials: Dict[str, Any]) -> Dict[str, str]:
        """Encrypt credentials dictionary."""
        if not self.cipher_suite:
            raise ValueError("Encryption not configured")
        
        encrypted = {}
        for key, value in credentials.items():
            if isinstance(value, str):
                encrypted[key] = self.cipher_suite.encrypt(value.encode()).decode()
            else:
                encrypted[key] = self.cipher_suite.encrypt(json.dumps(value).encode()).decode()
        
        return encrypted
    
    def _decrypt_value(self, encrypted_value: str) -> str:
        """Decrypt a single value."""
        if not self.cipher_suite:
            raise ValueError("Encryption not configured")
        
        return self.cipher_suite.decrypt(encrypted_value.encode()).decode()
    
    async def get_total_balance(self, user_id: int) -> Dict[str, float]:
        """Get total balance across all accounts."""
        accounts = await self.list_accounts(user_id)
        
        total_by_dex = {}
        total_overall = 0.0
        
        for account in accounts:
            if account.dex not in total_by_dex:
                total_by_dex[account.dex] = 0.0
            
            total_by_dex[account.dex] += account.balance
            total_overall += account.balance
        
        return {
            'by_dex': total_by_dex,
            'total': total_overall
        }
    
    def clear_cache(self):
        """Clear the account cache."""
        self._cache.clear()