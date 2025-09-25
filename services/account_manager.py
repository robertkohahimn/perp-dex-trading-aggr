"""
Account management service.
"""
from typing import List, Dict, Optional, Any
from dataclasses import dataclass


@dataclass
class DexAccount:
    """Account information."""
    dex: str
    name: str
    credentials: Dict[str, Any]
    testnet: bool = False


class AccountManager:
    """Manages trading accounts across DEXes."""
    
    def __init__(self):
        self.accounts: Dict[str, List[DexAccount]] = {}
    
    async def add_account(self, dex: str, name: str, credentials: Dict[str, Any], testnet: bool = False) -> DexAccount:
        """Add a new account."""
        account = DexAccount(dex=dex, name=name, credentials=credentials, testnet=testnet)
        
        if dex not in self.accounts:
            self.accounts[dex] = []
        
        self.accounts[dex].append(account)
        return account
    
    async def get_account(self, dex: str, name: str) -> Optional[DexAccount]:
        """Get a specific account."""
        if dex not in self.accounts:
            return None
        
        for account in self.accounts[dex]:
            if account.name == name:
                return account
        
        return None
    
    async def list_accounts(self, dex: Optional[str] = None) -> List[DexAccount]:
        """List accounts, optionally filtered by DEX."""
        if dex:
            return self.accounts.get(dex, [])
        
        all_accounts = []
        for accounts in self.accounts.values():
            all_accounts.extend(accounts)
        
        return all_accounts
    
    async def remove_account(self, dex: str, name: str) -> bool:
        """Remove an account."""
        if dex not in self.accounts:
            return False
        
        for i, account in enumerate(self.accounts[dex]):
            if account.name == name:
                self.accounts[dex].pop(i)
                return True
        
        return False
    
    async def get_active_account(self, dex: str) -> Optional[DexAccount]:
        """Get the active account for a DEX."""
        if dex not in self.accounts or not self.accounts[dex]:
            return None
        
        # Return first account as active for now
        return self.accounts[dex][0]