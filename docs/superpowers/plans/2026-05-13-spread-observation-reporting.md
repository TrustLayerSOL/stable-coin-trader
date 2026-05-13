# Spread Observation Reporting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a paper-only spread observation and reporting layer for real public Kraken/Coinbase snapshots.

**Architecture:** Keep observation math in a new pure module, `src/stable_coin_trader/spread_observations.py`, so it is separate from the trade-generating opportunity engine. Use append-only JSON Lines for repeated measurement history, and add two CLI commands: one to record observations from a snapshot file and one to summarize the stored history.

**Tech Stack:** Python stdlib JSON/path handling, Decimal math, Pydantic models, Typer CLI, pytest.

---

### Task 1: Observation Math and JSON Lines Persistence

**Files:**
- Create: `src/stable_coin_trader/spread_observations.py`
- Create: `tests/unit/test_spread_observations.py`

- [x] **Step 1: Write failing tests**

Add tests that call:

```python
build_spread_observations(
    snapshots=snapshots,
    size=Decimal("1000"),
    fee_bps=Decimal("1"),
    slippage_bps=Decimal("0.5"),
    max_snapshot_lag_seconds=Decimal("5"),
)
```

The tests must assert that both venue directions are recorded, unprofitable
routes are preserved, executable size is capped by top-of-book depth, stale
snapshot pairs are skipped, and invalid numeric inputs raise `ValueError`.

- [x] **Step 2: Verify red**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_spread_observations.py -v
```

Expected result: import or attribute failures because the module does not exist.

- [x] **Step 3: Implement minimal observation module**

Create `SpreadObservation`, `SpreadObservationSummary`,
`build_spread_observations`, `append_spread_observations`,
`load_spread_observations`, and `summarize_spread_observations`.

- [x] **Step 4: Verify green**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_spread_observations.py -v
```

Expected result: all spread observation unit tests pass.

### Task 2: CLI Commands

**Files:**
- Modify: `src/stable_coin_trader/cli.py`
- Modify: `tests/unit/test_cli.py`

- [x] **Step 1: Write failing CLI tests**

Add tests for:

- `observe-spreads` reading a snapshot JSON file, appending JSON Lines, and
  printing observation/profitable/best-edge counts.
- `report-spreads` reading JSON Lines history and printing the same summary.

- [x] **Step 2: Verify red**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_cli.py -v
```

Expected result: Typer command not found.

- [x] **Step 3: Add CLI wiring**

Import the observation functions, parse Decimal options, convert command
failures to exit code 1, and keep commands paper-only.

- [x] **Step 4: Verify green**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_cli.py tests/unit/test_spread_observations.py -v
```

Expected result: all focused tests pass.

### Task 3: Docs, Real Smoke Test, and Publish

**Files:**
- Modify: `README.md`
- Modify: `PROJECT.md`
- Modify: `PROJECT_LOG.md`

- [x] Document the snapshot -> observation -> report workflow.
- [x] Update current status and next steps.
- [x] Run `.venv/bin/python -m pytest -v`.
- [x] Run `git diff --check`.
- [x] Run a real public snapshot fetch, `observe-spreads`, and `report-spreads`
  against ignored `runtime/` files.
- [x] Run a committed-file secret scan.
- [x] Commit, push, and open a draft PR stacked on `feature/coinbase-public-market-data`.
