"""
Interactive trading shell.
"""
import asyncio
from typing import Optional
from rich.console import Console
from rich.prompt import Prompt
from cli.config import CLIConfig


class InteractiveShell:
    """Interactive trading shell."""
    
    def __init__(self, config: CLIConfig, console: Console):
        self.config = config
        self.console = console
        self.running = True
        self.current_dex = config.default_dex
        self.current_account = config.default_account
    
    async def run(self):
        """Run the interactive shell."""
        self.console.print("\n[bold cyan]Perp DEX Interactive Trading Shell[/bold cyan]")
        self.console.print("Type 'help' for commands, 'exit' to quit\n")
        
        if self.current_dex and self.current_account:
            self.console.print(f"[dim]Using {self.current_dex}:{self.current_account}[/dim]")
        
        while self.running:
            try:
                # Get command
                prompt = f"[{self.current_dex or 'no-dex'}] > " if self.current_dex else "> "
                command = Prompt.ask(prompt)
                
                if not command:
                    continue
                
                # Parse and execute command
                await self.execute_command(command)
                
            except KeyboardInterrupt:
                self.console.print("\n[yellow]Use 'exit' to quit[/yellow]")
            except Exception as e:
                self.console.print(f"[red]Error: {str(e)}[/red]")
    
    async def execute_command(self, command: str):
        """Execute a shell command."""
        parts = command.strip().split()
        if not parts:
            return
        
        cmd = parts[0].lower()
        
        if cmd == "exit" or cmd == "quit":
            self.running = False
            self.console.print("[cyan]Goodbye![/cyan]")
        
        elif cmd == "help":
            self.show_help()
        
        elif cmd == "use":
            if len(parts) >= 2:
                self.current_dex = parts[1]
                if len(parts) >= 3:
                    self.current_account = parts[2]
                self.console.print(f"[green]Using {self.current_dex}:{self.current_account or 'default'}[/green]")
            else:
                self.console.print("[yellow]Usage: use <dex> [account][/yellow]")
        
        elif cmd == "buy" or cmd == "sell":
            # Parse trading command
            if len(parts) >= 3:
                size = parts[1]
                symbol = parts[2]
                price = None
                
                if len(parts) >= 5 and parts[3] == "@":
                    price = parts[4]
                
                self.console.print(f"[cyan]Would place {cmd} order: {size} {symbol} @ {price or 'market'}[/cyan]")
                self.console.print("[yellow]Trading execution coming soon...[/yellow]")
            else:
                self.console.print(f"[yellow]Usage: {cmd} <size> <symbol> [@ price][/yellow]")
        
        elif cmd == "positions":
            self.console.print("[cyan]Fetching positions...[/cyan]")
            self.console.print("[yellow]Position display coming soon...[/yellow]")
        
        elif cmd == "balance":
            self.console.print("[cyan]Fetching balance...[/cyan]")
            self.console.print("[yellow]Balance display coming soon...[/yellow]")
        
        elif cmd == "orders":
            self.console.print("[cyan]Fetching orders...[/cyan]")
            self.console.print("[yellow]Order display coming soon...[/yellow]")
        
        elif cmd == "cancel":
            if len(parts) >= 2 and parts[1] == "all":
                self.console.print("[cyan]Would cancel all orders[/cyan]")
                self.console.print("[yellow]Order cancellation coming soon...[/yellow]")
            else:
                self.console.print("[yellow]Usage: cancel <order_id> or cancel all[/yellow]")
        
        else:
            self.console.print(f"[red]Unknown command: {cmd}[/red]")
            self.console.print("[dim]Type 'help' for available commands[/dim]")
    
    def show_help(self):
        """Show help information."""
        help_text = """
[bold cyan]Available Commands:[/bold cyan]

[yellow]Session Control:[/yellow]
  use <dex> [account]  - Select DEX and account
  help                 - Show this help
  exit/quit           - Exit the shell

[yellow]Trading:[/yellow]
  buy <size> <symbol> [@ price]   - Place buy order
  sell <size> <symbol> [@ price]  - Place sell order
  cancel <order_id>               - Cancel specific order
  cancel all                      - Cancel all orders

[yellow]Information:[/yellow]
  positions  - Show open positions
  balance    - Show account balance
  orders     - Show open orders

[yellow]Examples:[/yellow]
  use hyperliquid main-account
  buy 0.1 BTC-PERP @ 50000
  sell 0.05 ETH-PERP @ market
  cancel all
"""
        self.console.print(help_text)