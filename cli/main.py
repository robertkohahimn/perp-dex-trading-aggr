#!/usr/bin/env python3
"""
Main CLI entry point for Perp DEX Trading.
"""
import sys
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table
import asyncio
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from cli.commands import account, trade, market, position, monitor, config_cmd
from cli.interactive.shell import InteractiveShell
from cli.config import CLIConfig, load_config
from app.config import get_settings

# Initialize Typer app
app = typer.Typer(
    name="perp-dex",
    help="Perp DEX Trading CLI - Trade across multiple perpetual DEX platforms",
    add_completion=True,
)

# Initialize console for rich output
console = Console()

# Add command groups
app.add_typer(account.app, name="account", help="Account management commands")
app.add_typer(trade.app, name="trade", help="Trading commands")
app.add_typer(market.app, name="market", help="Market data commands")
app.add_typer(position.app, name="position", help="Position management commands")
app.add_typer(monitor.app, name="monitor", help="Real-time monitoring commands")
app.add_typer(config_cmd.app, name="config", help="Configuration commands")


@app.command()
def shell(
    dex: Optional[str] = typer.Option(None, "--dex", "-d", help="Default DEX to use"),
    account: Optional[str] = typer.Option(None, "--account", "-a", help="Default account to use"),
):
    """Start interactive trading shell."""
    console.print("[bold cyan]Starting Perp DEX Interactive Shell...[/bold cyan]")
    
    # Load configuration
    config = load_config()
    
    # Override defaults if provided
    if dex:
        config.default_dex = dex
    if account:
        config.default_account = account
    
    # Start interactive shell
    shell = InteractiveShell(config, console)
    asyncio.run(shell.run())


@app.command()
def version():
    """Show version information."""
    from cli import __version__ as cli_version
    from app.config import get_settings
    
    settings = get_settings()
    
    table = Table(title="Version Information")
    table.add_column("Component", style="cyan")
    table.add_column("Version", style="green")
    
    table.add_row("CLI", cli_version)
    table.add_row("API", settings.app.api_version)
    table.add_row("Environment", settings.app.app_env)
    
    console.print(table)


@app.command()
def test(
    dex: str = typer.Argument(..., help="DEX to test connection"),
    account: Optional[str] = typer.Option(None, "--account", "-a", help="Account to use"),
):
    """Test connection to a DEX."""
    console.print(f"[cyan]Testing connection to {dex}...[/cyan]")
    
    async def test_connection():
        try:
            from connectors.factory import ConnectorFactory
            from services.account_manager import AccountManager
            
            # Initialize account manager
            account_mgr = AccountManager()
            
            # Get account
            if account:
                acc = await account_mgr.get_account(dex, account)
            else:
                accounts = await account_mgr.list_accounts(dex)
                if not accounts:
                    console.print(f"[red]No accounts configured for {dex}[/red]")
                    return False
                acc = accounts[0]
            
            # Create connector
            connector = await ConnectorFactory.create(dex, acc.credentials)
            
            # Test authentication
            authenticated = await connector.authenticate(acc.credentials)
            
            if authenticated:
                console.print(f"[green]✓ Successfully connected to {dex}[/green]")
                
                # Try to get account info
                info = await connector.get_account_info()
                console.print(f"[green]Account balance: {info.balance} {info.currency}[/green]")
                return True
            else:
                console.print(f"[red]✗ Failed to authenticate with {dex}[/red]")
                return False
                
        except Exception as e:
            console.print(f"[red]✗ Connection failed: {str(e)}[/red]")
            return False
    
    success = asyncio.run(test_connection())
    sys.exit(0 if success else 1)


@app.callback()
def main(
    ctx: typer.Context,
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose output"),
    debug: bool = typer.Option(False, "--debug", help="Enable debug mode"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Run in dry-run mode (no actual trades)"),
    config_file: Optional[Path] = typer.Option(
        None, "--config", "-c", help="Path to configuration file"
    ),
):
    """
    Perp DEX Trading CLI - Command line interface for perpetual DEX trading.
    """
    # Set global options
    if verbose:
        console.print("[dim]Verbose mode enabled[/dim]")
    if debug:
        console.print("[dim]Debug mode enabled[/dim]")
        import logging
        logging.basicConfig(level=logging.DEBUG)
    if dry_run:
        console.print("[yellow]DRY RUN MODE - No actual trades will be executed[/yellow]")
    
    # Store options in context for commands to access
    ctx.obj = {
        "verbose": verbose,
        "debug": debug,
        "dry_run": dry_run,
        "config_file": config_file,
    }


if __name__ == "__main__":
    app()