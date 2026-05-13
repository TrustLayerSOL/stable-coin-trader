from decimal import Decimal
from decimal import InvalidOperation
from datetime import datetime
from pathlib import Path

from rich.console import Console
import typer

from stable_coin_trader.coinbase import (
    CoinbasePublicMarketDataClient,
    parse_product_mapping,
)
from stable_coin_trader.config import load_config
from stable_coin_trader.engine import run_once
from stable_coin_trader.kraken import (
    KrakenPublicMarketDataClient,
    parse_pair_mapping,
)
from stable_coin_trader.market_data import (
    load_all_market_snapshots,
    write_market_snapshots,
)
from stable_coin_trader.models import parse_dt
from stable_coin_trader.spread_observations import (
    SpreadObservationSummary,
    append_spread_observations,
    build_spread_observations,
    load_spread_observations,
    summarize_spread_observations,
)
from stable_coin_trader.spread_sampling import SpreadSamplingResult, sample_spreads

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


@app.command("fetch-public-snapshots")
def fetch_public_snapshots_command(
    output: Path = typer.Option(..., "--output", help="Output market snapshot JSON."),
    kraken_pair: list[str] = typer.Option(
        [],
        "--kraken-pair",
        help="Kraken pair mapping as KRAKEN_PAIR:BOT_SYMBOL.",
    ),
    coinbase_product: list[str] = typer.Option(
        [],
        "--coinbase-product",
        help="Coinbase product mapping as PRODUCT_ID:BOT_SYMBOL.",
    ),
) -> None:
    try:
        kraken_mappings = [parse_pair_mapping(raw_pair) for raw_pair in kraken_pair]
        coinbase_mappings = [
            parse_product_mapping(raw_product)
            for raw_product in coinbase_product
        ]
        if not kraken_mappings and not coinbase_mappings:
            raise ValueError("at least one public market-data mapping is required")

        kraken_client = KrakenPublicMarketDataClient()
        coinbase_client = CoinbasePublicMarketDataClient()
        snapshots = [
            kraken_client.fetch_order_book_snapshot(mapping)
            for mapping in kraken_mappings
        ]
        snapshots.extend(
            coinbase_client.fetch_order_book_snapshot(mapping)
            for mapping in coinbase_mappings
        )
        write_market_snapshots(output, snapshots)
    except (ConnectionError, ValueError) as exc:
        console.print(f"public snapshot fetch failed: {exc}")
        raise typer.Exit(code=1) from exc

    console.print(
        f"public snapshots written path={output} count={len(snapshots)}"
    )


@app.command("observe-spreads")
def observe_spreads_command(
    market_data: Path = typer.Option(
        ...,
        "--market-data",
        help="Input public market snapshot JSON.",
    ),
    output: Path = typer.Option(
        Path("runtime/spread_observations.jsonl"),
        "--output",
        help="Append-only spread observation JSONL output.",
    ),
    size: str = typer.Option(
        "1000",
        "--size",
        help="Requested stablecoin size for each directional observation.",
    ),
    fee_bps: str = typer.Option(
        "0",
        "--fee-bps",
        help="Estimated fee basis points charged on both legs.",
    ),
    slippage_bps: str = typer.Option(
        "0.5",
        "--slippage-bps",
        help="Estimated slippage basis points charged on both legs.",
    ),
    max_snapshot_lag_seconds: str = typer.Option(
        "5",
        "--max-snapshot-lag-seconds",
        help="Maximum allowed time gap between buy and sell snapshots.",
    ),
) -> None:
    try:
        size_value = _parse_decimal_option("size", size)
        fee_bps_value = _parse_decimal_option("fee_bps", fee_bps)
        slippage_bps_value = _parse_decimal_option("slippage_bps", slippage_bps)
        max_snapshot_lag_seconds_value = _parse_decimal_option(
            "max_snapshot_lag_seconds",
            max_snapshot_lag_seconds,
        )
        snapshots = load_all_market_snapshots(market_data)
        observations = build_spread_observations(
            snapshots=snapshots,
            size=size_value,
            fee_bps=fee_bps_value,
            slippage_bps=slippage_bps_value,
            max_snapshot_lag_seconds=max_snapshot_lag_seconds_value,
        )
        append_spread_observations(output, observations)
        summary = summarize_spread_observations(observations)
    except (OSError, ValueError) as exc:
        console.print(f"spread observation failed: {exc}")
        raise typer.Exit(code=1) from exc

    _print_spread_summary(
        prefix=f"spread observations recorded path={output}",
        summary=summary,
    )


@app.command("report-spreads")
def report_spreads_command(
    input: Path = typer.Option(
        ...,
        "--input",
        help="Input spread observation JSONL history.",
    ),
) -> None:
    try:
        observations = load_spread_observations(input)
        summary = summarize_spread_observations(observations)
    except (OSError, ValueError) as exc:
        console.print(f"spread report failed: {exc}")
        raise typer.Exit(code=1) from exc

    _print_spread_summary(
        prefix=f"spread observation report path={input}",
        summary=summary,
    )


@app.command("sample-spreads")
def sample_spreads_command(
    output: Path = typer.Option(
        Path("runtime/spread_observations.jsonl"),
        "--output",
        help="Append-only spread observation JSONL output.",
    ),
    kraken_pair: list[str] = typer.Option(
        [],
        "--kraken-pair",
        help="Kraken pair mapping as KRAKEN_PAIR:BOT_SYMBOL.",
    ),
    coinbase_product: list[str] = typer.Option(
        [],
        "--coinbase-product",
        help="Coinbase product mapping as PRODUCT_ID:BOT_SYMBOL.",
    ),
    samples: int = typer.Option(
        120,
        "--samples",
        help="Number of public market-data samples to collect.",
    ),
    interval_seconds: str = typer.Option(
        "30",
        "--interval-seconds",
        help="Seconds to wait between samples.",
    ),
    size: str = typer.Option(
        "1000",
        "--size",
        help="Requested stablecoin size for each directional observation.",
    ),
    fee_bps: str = typer.Option(
        "0",
        "--fee-bps",
        help="Estimated fee basis points charged on both legs.",
    ),
    slippage_bps: str = typer.Option(
        "0.5",
        "--slippage-bps",
        help="Estimated slippage basis points charged on both legs.",
    ),
    max_snapshot_lag_seconds: str = typer.Option(
        "5",
        "--max-snapshot-lag-seconds",
        help="Maximum allowed time gap between buy and sell snapshots.",
    ),
) -> None:
    try:
        kraken_mappings = [parse_pair_mapping(raw_pair) for raw_pair in kraken_pair]
        coinbase_mappings = [
            parse_product_mapping(raw_product)
            for raw_product in coinbase_product
        ]
        result = sample_spreads(
            kraken_mappings=kraken_mappings,
            coinbase_mappings=coinbase_mappings,
            output_path=output,
            samples=samples,
            interval_seconds=_parse_decimal_option(
                "interval_seconds",
                interval_seconds,
            ),
            size=_parse_decimal_option("size", size),
            fee_bps=_parse_decimal_option("fee_bps", fee_bps),
            slippage_bps=_parse_decimal_option("slippage_bps", slippage_bps),
            max_snapshot_lag_seconds=_parse_decimal_option(
                "max_snapshot_lag_seconds",
                max_snapshot_lag_seconds,
            ),
            kraken_client=KrakenPublicMarketDataClient(),
            coinbase_client=CoinbasePublicMarketDataClient(),
            on_sample_result=_print_sample_result,
        )
    except (OSError, OverflowError, ValueError) as exc:
        console.print(f"spread sampling failed: {exc}")
        raise typer.Exit(code=1) from exc

    _print_sampling_result(output=output, result=result)


def _parse_decimal_option(name: str, raw_value: str) -> Decimal:
    try:
        return Decimal(raw_value)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{name} must be a decimal") from exc


def _print_spread_summary(prefix: str, summary: SpreadObservationSummary) -> None:
    best_route = summary.best_route or "none"
    best_edge = _format_optional_decimal(summary.best_net_edge_bps)
    avg_edge = _format_optional_decimal(summary.average_net_edge_bps)
    first_observed = _format_optional_datetime(summary.first_observed_at)
    last_observed = _format_optional_datetime(summary.last_observed_at)
    console.print(
        f"{prefix} "
        f"count={summary.observation_count} "
        f"profitable={summary.profitable_count} "
        f"best={best_route} "
        f"best_edge_bps={best_edge} "
        f"avg_edge_bps={avg_edge} "
        f"first={first_observed} "
        f"last={last_observed}"
    )


def _format_optional_decimal(value: Decimal | None) -> str:
    if value is None:
        return "n/a"
    rounded = value.quantize(Decimal("0.00000001"))
    formatted = format(rounded, "f").rstrip("0").rstrip(".")
    return formatted or "0"


def _format_optional_datetime(value: datetime | None) -> str:
    if value is None:
        return "n/a"
    return parse_dt(value).isoformat().replace("+00:00", "Z")


def _print_sampling_result(output: Path, result: SpreadSamplingResult) -> None:
    console.print(
        f"spread sampling complete path={output} "
        f"samples={result.samples_requested} "
        f"successful={result.samples_successful} "
        f"failed={result.samples_failed} "
        f"observations={result.observations_written}"
    )
    _print_spread_summary(prefix="spread sampling summary", summary=result.summary)


def _print_sample_result(
    sample_number: int,
    successful: bool,
    observations_written: int,
    reason: str | None,
) -> None:
    if successful:
        console.print(
            f"sample={sample_number} status=successful "
            f"observations={observations_written}"
        )
        return

    console.print(
        f"sample={sample_number} status=failed "
        f"observations={observations_written} reason={reason}"
    )
