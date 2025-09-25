"""
Account management CLI commands.
"""
import asyncio
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table
from rich.prompt import Prompt, Confirm
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cli.config import (
    load_config, save_config, CredentialManager,
    AccountConfig, get_account_credentials
)
from services.account_manager import AccountManager
from connectors.factory import ConnectorFactory

app = typer.Typer(help="Account management commands")
console = Console()


@app.command("list")
def list_accounts(
    dex: Optional[str] = typer.Option(None, "--dex", "-d", help="Filter by DEX"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed information"),
):
    """List all configured accounts."""
    config = load_config()
    
    if dex:
        # Filter for specific DEX
        if dex not in config.accounts:
            console.print(f"[yellow]No accounts configured for {dex}[/yellow]")
            return
        dexes = {dex: config.accounts[dex]}
    else:
        dexes = config.accounts
    
    if not dexes:
        console.print("[yellow]No accounts configured. Use 'perp-dex account add' to add an account.[/yellow]")
        return
    
    table = Table(title="Configured Accounts")
    table.add_column("DEX", style="cyan")
    table.add_column("Account Name", style="green")
    table.add_column("Testnet", style="yellow")
    
    if verbose:
        table.add_column("API Key", style="dim")
        table.add_column("Wallet", style="dim")
    
    for dex_name, accounts in dexes.items():
        for account in accounts:
            row = [dex_name, account.name, "Yes" if account.testnet else "No"]
            
            if verbose:
                # Show partial API key
                api_key = account.api_key or CredentialManager.get_account_credential(
                    dex_name, account.name, "api_key"
                )
                if api_key:
                    api_key = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "***"
                else:
                    api_key = "Not set"
                
                row.append(api_key)
                row.append(account.wallet[:10] + "..." if account.wallet else "N/A")
            
            table.add_row(*row)
    
    console.print(table)


@app.command("add")
def add_account(
    dex: str = typer.Argument(..., help="DEX name (hyperliquid, lighter, extended, edgex, vest)"),
    name: str = typer.Option(..., "--name", "-n", help="Account name"),
    testnet: bool = typer.Option(False, "--testnet", help="Use testnet"),
    interactive: bool = typer.Option(True, "--interactive", "-i", help="Interactive mode for credentials"),
):
    """Add a new account."""
    config = load_config()
    
    # Check if DEX is supported
    supported_dexes = ["hyperliquid", "lighter", "extended", "edgex", "vest"]
    if dex.lower() not in supported_dexes:
        console.print(f"[red]Unsupported DEX: {dex}[/red]")
        console.print(f"Supported DEXes: {', '.join(supported_dexes)}")
        return
    
    dex = dex.lower()
    
    # Check if account already exists
    if dex in config.accounts:
        for account in config.accounts[dex]:
            if account.name == name:
                console.print(f"[red]Account '{name}' already exists for {dex}[/red]")
                return
    
    # Create account config
    account = AccountConfig(name=name, testnet=testnet)
    
    if interactive:
        console.print(f"[cyan]Setting up account '{name}' for {dex}[/cyan]")
        
        # Get API key
        api_key = Prompt.ask("API Key", password=True)
        if api_key:
            # Store securely
            CredentialManager.store_account_credential(dex, name, "api_key", api_key)
        
        # Get API secret if needed
        if dex in ["hyperliquid", "lighter", "extended"]:
            api_secret = Prompt.ask("API Secret", password=True, default="")
            if api_secret:
                CredentialManager.store_account_credential(dex, name, "api_secret", api_secret)
        
        # Get wallet address if applicable
        if dex in ["hyperliquid"]:
            wallet = Prompt.ask("Wallet Address", default="")
            if wallet:
                account.wallet = wallet
    
    # Add account to config
    if dex not in config.accounts:
        config.accounts[dex] = []
    config.accounts[dex].append(account)
    
    # Save config
    save_config(config)
    
    console.print(f"[green]✓ Account '{name}' added for {dex}[/green]")
    
    # Test connection if requested
    if Confirm.ask("Test connection?", default=True):
        test_account_connection(dex, name)


@app.command("remove")
def remove_account(
    dex: str = typer.Argument(..., help="DEX name"),
    name: str = typer.Argument(..., help="Account name"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
):
    """Remove an account."""
    config = load_config()
    
    if dex not in config.accounts:
        console.print(f"[red]No accounts configured for {dex}[/red]")
        return
    
    # Find account
    account_found = False
    for i, account in enumerate(config.accounts[dex]):
        if account.name == name:
            account_found = True
            
            if not force:
                if not Confirm.ask(f"Remove account '{name}' from {dex}?", default=False):
                    return
            
            # Remove from config
            config.accounts[dex].pop(i)
            
            # Remove credentials
            CredentialManager.delete_account_credential(dex, name, "api_key")
            CredentialManager.delete_account_credential(dex, name, "api_secret")
            
            # Clean up empty DEX entry
            if not config.accounts[dex]:
                del config.accounts[dex]
            
            save_config(config)
            console.print(f"[green]✓ Account '{name}' removed from {dex}[/green]")
            break
    
    if not account_found:
        console.print(f"[red]Account '{name}' not found for {dex}[/red]")


@app.command("balance")
def show_balance(
    dex: Optional[str] = typer.Option(None, "--dex", "-d", help="DEX name"),
    account: Optional[str] = typer.Option(None, "--account", "-a", help="Account name"),
    all: bool = typer.Option(False, "--all", help="Show all accounts"),
):
    """Show account balance."""
    config = load_config()
    
    async def get_balance(dex_name: str, account_name: str):
        try:
            # Get credentials
            credentials = get_account_credentials(dex_name, account_name)
            
            # Create connector
            connector = await ConnectorFactory.create(dex_name, credentials)
            
            # Authenticate
            if not await connector.authenticate(credentials):
                return None, "Authentication failed"
            
            # Get account info
            info = await connector.get_account_info()
            return info, None
            
        except Exception as e:
            return None, str(e)
    
    async def show_balances():
        table = Table(title="Account Balances")
        table.add_column("DEX", style="cyan")
        table.add_column("Account", style="green")
        table.add_column("Balance", style="yellow")
        table.add_column("Currency", style="blue")
        table.add_column("Status", style="dim")
        
        accounts_to_check = []
        
        if all:
            # Check all accounts
            for dex_name, accounts in config.accounts.items():
                for acc in accounts:
                    accounts_to_check.append((dex_name, acc.name))
        elif dex and account:
            accounts_to_check.append((dex, account))
        elif dex:
            # All accounts for specific DEX
            if dex in config.accounts:
                for acc in config.accounts[dex]:
                    accounts_to_check.append((dex, acc.name))
        else:
            # Use default
            if config.default_dex and config.default_account:
                accounts_to_check.append((config.default_dex, config.default_account))
            else:
                console.print("[yellow]No account specified. Use --dex and --account or --all[/yellow]")
                return
        
        # Fetch balances
        with console.status("Fetching balances..."):
            tasks = [get_balance(d, a) for d, a in accounts_to_check]
            results = await asyncio.gather(*tasks)
        
        # Display results
        for (dex_name, account_name), (info, error) in zip(accounts_to_check, results):
            if info:
                table.add_row(
                    dex_name,
                    account_name,
                    f"{info.balance:,.2f}",
                    info.currency,
                    "[green]Connected[/green]"
                )
            else:
                table.add_row(
                    dex_name,
                    account_name,
                    "N/A",
                    "N/A",
                    f"[red]{error}[/red]"
                )
        
        console.print(table)
    
    asyncio.run(show_balances())


def test_account_connection(dex: str, name: str):
    """Test connection for an account."""
    async def test():
        try:
            console.print(f"[cyan]Testing connection for {name} on {dex}...[/cyan]")
            
            # Get credentials
            credentials = get_account_credentials(dex, name)
            
            # Create connector
            connector = await ConnectorFactory.create(dex, credentials)
            
            # Test authentication
            authenticated = await connector.authenticate(credentials)
            
            if authenticated:
                console.print(f"[green]✓ Successfully connected[/green]")
                
                # Try to get account info
                info = await connector.get_account_info()
                console.print(f"[green]Balance: {info.balance} {info.currency}[/green]")
            else:
                console.print(f"[red]✗ Authentication failed[/red]")
                
        except Exception as e:
            console.print(f"[red]✗ Connection failed: {str(e)}[/red]")
    
    asyncio.run(test())