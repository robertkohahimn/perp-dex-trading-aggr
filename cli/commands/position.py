"""
Position management CLI commands.
"""
import asyncio
from typing import Optional
import typer
from rich.console import Console
from rich.table import Table
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from cli.config import load_config, get_account_credentials
from connectors.factory import ConnectorFactory

app = typer.Typer(help="Position management commands")
console = Console()


@app.command("list")
def list_positions(
    dex: Optional[str] = typer.Option(None, "--dex", "-d", help="DEX to query"),
    account: Optional[str] = typer.Option(None, "--account", "-a", help="Account to use"),
    all: bool = typer.Option(False, "--all", help="Show positions from all accounts"),
):
    """List all open positions."""
    config = load_config()
    
    dex = dex or config.default_dex
    account = account or config.default_account
    
    if not all and (not dex or not account):
        console.print("[red]Please specify --dex and --account, use --all, or set defaults in config[/red]")
        return
    
    async def get_positions():
        try:
            positions_data = []
            
            if all:
                # Get positions from all accounts
                for dex_name, accounts in config.accounts.items():
                    for acc in accounts:
                        try:
                            credentials = get_account_credentials(dex_name, acc.name)
                            connector = await ConnectorFactory.create(dex_name, credentials)
                            
                            if await connector.authenticate(credentials):
                                positions = await connector.get_positions()
                                for pos in positions:
                                    positions_data.append((dex_name, acc.name, pos))
                        except Exception as e:
                            console.print(f"[yellow]Warning: Failed to get positions from {acc.name} on {dex_name}: {str(e)}[/yellow]")
            else:
                # Get positions from single account
                credentials = get_account_credentials(dex, account)
                connector = await ConnectorFactory.create(dex, credentials)
                
                if not await connector.authenticate(credentials):
                    console.print("[red]Authentication failed[/red]")
                    return
                
                positions = await connector.get_positions()
                positions_data = [(dex, account, pos) for pos in positions]
            
            if not positions_data:
                console.print("[yellow]No open positions[/yellow]")
                return
            
            # Display positions
            table = Table(title="Open Positions")
            if all:
                table.add_column("DEX", style="cyan")
                table.add_column("Account", style="blue")
            table.add_column("Symbol", style="yellow")
            table.add_column("Side", style="green")
            table.add_column("Size")
            table.add_column("Entry Price")
            table.add_column("Mark Price")
            table.add_column("PnL", style="green")
            table.add_column("PnL %")
            
            total_pnl = 0.0
            
            for data in positions_data:
                if all:
                    dex_name, acc_name, pos = data
                else:
                    _, _, pos = data
                
                pnl_color = "green" if pos.unrealized_pnl >= 0 else "red"
                pnl_pct = (pos.unrealized_pnl / (pos.size * pos.entry_price)) * 100 if pos.entry_price else 0
                
                row = []
                if all:
                    row.extend([dex_name, acc_name])
                
                row.extend([
                    pos.symbol,
                    f"[green]LONG[/green]" if pos.side == "long" else "[red]SHORT[/red]",
                    f"{pos.size:.4f}",
                    f"{pos.entry_price:.2f}" if pos.entry_price else "N/A",
                    f"{pos.mark_price:.2f}" if pos.mark_price else "N/A",
                    f"[{pnl_color}]{pos.unrealized_pnl:+.2f}[/{pnl_color}]",
                    f"[{pnl_color}]{pnl_pct:+.2f}%[/{pnl_color}]",
                ])
                
                table.add_row(*row)
                total_pnl += pos.unrealized_pnl
            
            console.print(table)
            
            # Show total PnL
            total_color = "green" if total_pnl >= 0 else "red"
            console.print(f"\n[bold]Total Unrealized PnL: [{total_color}]{total_pnl:+.2f}[/{total_color}][/bold]")
            
        except Exception as e:
            console.print(f"[red]Error: {str(e)}[/red]")
    
    asyncio.run(get_positions())


@app.command("close")
def close_position(
    symbol: str = typer.Argument(..., help="Symbol of position to close"),
    size: Optional[float] = typer.Option(None, "--size", "-s", help="Size to close (partial close)"),
    dex: Optional[str] = typer.Option(None, "--dex", "-d", help="DEX to use"),
    account: Optional[str] = typer.Option(None, "--account", "-a", help="Account to use"),
):
    """Close a position."""
    console.print(f"[cyan]Closing position for {symbol}[/cyan]")
    console.print("[yellow]Position closing coming soon...[/yellow]")