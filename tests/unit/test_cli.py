from typer.testing import CliRunner

from stable_coin_trader.cli import app


def test_cli_without_args_shows_help() -> None:
    result = CliRunner().invoke(app)

    assert result.exit_code == 0
    assert "Risk-aware stablecoin paper trading bot." in result.output
