# Coinbase Public Market Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Coinbase public market data and a combined public snapshot fetch command for two-venue paper spread checks.

**Architecture:** Put Coinbase-specific REST parsing in `src/stable_coin_trader/coinbase.py`. Keep shared snapshot JSON writing in `src/stable_coin_trader/market_data.py`. The CLI orchestrates public fetches and writes one JSON list consumed by the existing paper engine.

**Tech Stack:** Python stdlib `urllib`, Typer CLI, Pydantic models, pytest.

---

### Task 1: Shared Snapshot Writer

**Files:**
- Modify: `src/stable_coin_trader/market_data.py`
- Modify: `src/stable_coin_trader/kraken.py`
- Modify: `tests/unit/test_kraken.py`

- [ ] Move `write_market_snapshots` to `market_data.py`.
- [ ] Keep Kraken using the shared writer.
- [ ] Verify Kraken tests still pass.

### Task 2: Coinbase Public Client

**Files:**
- Create: `src/stable_coin_trader/coinbase.py`
- Test: `tests/unit/test_coinbase.py`

- [ ] Write tests for product mapping parsing, level-1 book parsing, malformed book rejection, and API/network errors.
- [ ] Run focused tests and verify they fail because the module does not exist.
- [ ] Implement the minimal public client.
- [ ] Run focused tests and verify they pass.

### Task 3: Combined Public Fetch CLI

**Files:**
- Modify: `src/stable_coin_trader/cli.py`
- Test: `tests/unit/test_cli.py`

- [ ] Write tests for `fetch-public-snapshots` with one Kraken and one Coinbase mapping.
- [ ] Add user-facing error handling.
- [ ] Run focused tests and verify they pass.

### Task 4: Docs and Verification

**Files:**
- Modify: `README.md`
- Modify: `PROJECT.md`
- Modify: `PROJECT_LOG.md`

- [ ] Document the two-venue public snapshot workflow.
- [ ] Run `.venv/bin/python -m pytest -v`.
- [ ] Run `git diff --check`.
- [ ] Run a real public fetch for Kraken and Coinbase into `runtime/public_snapshots.json`.
- [ ] Commit, push, and open a draft PR.
