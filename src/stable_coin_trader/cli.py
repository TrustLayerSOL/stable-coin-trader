from pathlib import Path

from rich.console import Console
import typer

from stable_coin_trader.config import load_config
from stable_coin_trader.engine import run_once
from stable_coin_trader.kraken import (
    KrakenPublicMarketDataClient,
    parse_pair_mapping,
    write_market_snapshots,
)

app = typer.Typer(
    help="Risk-aware stablecoin paper trading bot.",
    invoke_without_command=True,
)
console = Console()


@app.callback(no_args_is_help=False)
def main(ctx: typer.Context) -> None:
    """Stable Coin Trader command line interface."""
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@app.command("run-once")
def run_once_command(
    config: Path = typer.Option(..., "--config", help="Path to paper config JSON."),
) -> None:
    bot_config = load_config(config)
    result = run_once(bot_config)
    console.print(
        "paper run complete "
        f"opportunities={result.opportunities_seen} "
        f"approved={result.approved_trades} "
        f"rejected={result.rejected_trades} "
        f"fills={result.paper_fills}"
    )


@app.command("fetch-kraken-snapshots")
def fetch_kraken_snapshots_command(
    output: Path = typer.Option(..., "--output", help="Output market snapshot JSON."),
    pair: list[str] = typer.Option(
        ["USDCUSD:USDC/USD"],
        "--pair",
        help="Kraken pair mapping as KRAKEN_PAIR:BOT_SYMBOL.",
    ),
) -> None:
    try:
        mappings = [parse_pair_mapping(raw_pair) for raw_pair in pair]
        client = KrakenPublicMarketDataClient()
        snapshots = [
            client.fetch_order_book_snapshot(mapping)
            for mapping in mappings
        ]
        write_market_snapshots(output, snapshots)
    except (ConnectionError, ValueError) as exc:
        console.print(f"kraken snapshot fetch failed: {exc}")
        raise typer.Exit(code=1) from exc

    console.print(
        f"kraken snapshots written path={output} count={len(snapshots)}"
    )
