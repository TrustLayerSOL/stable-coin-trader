# Stable Coin Trader

Risk-aware stablecoin paper trading bot for proprietary capital.

Current phase: core skeleton and deterministic paper loop. The project does not contain live trading code yet.

Safety rules:

- No secrets in git.
- Paper mode first.
- Risk engine approves every proposed trade.
- Research signals can reduce risk, pause trading, or require review, but cannot originate trades.
