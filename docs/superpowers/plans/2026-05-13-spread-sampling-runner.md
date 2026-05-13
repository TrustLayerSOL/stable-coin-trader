# Spread Sampling Runner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a finite paper-only runner that repeatedly fetches public Kraken/Coinbase snapshots and appends spread observations for time-series measurement.

**Architecture:** Put orchestration in `src/stable_coin_trader/spread_sampling.py` so the CLI remains thin and the runner is testable with fake clients and a fake sleeper. Reuse `SpreadObservation`, JSON Lines persistence, and summary reporting from `spread_observations.py`.

**Tech Stack:** Python stdlib, Decimal math, Pydantic models, Typer CLI, pytest.

---

### Task 1: Sampling Orchestration

**Files:**
- Create: `src/stable_coin_trader/spread_sampling.py`
- Create: `tests/unit/test_spread_sampling.py`

- [x] **Step 1: Write failing tests**

Add tests for:

- two successful samples append four directional observations and sleep once;
- a failed sample is counted and the next sample continues;
- no partial observations are written for failed samples;
- invalid `samples`, `interval_seconds`, `size`, or empty mappings raise `ValueError`.

- [x] **Step 2: Verify red**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_spread_sampling.py -v
```

Expected result: import failure because `spread_sampling.py` does not exist.

- [x] **Step 3: Implement the minimal runner**

Create `SpreadSampleFailure`, `SpreadSamplingResult`, and `sample_spreads`.
The function should accept public clients and an injectable sleeper so tests do
not wait.

- [x] **Step 4: Verify green**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_spread_sampling.py -v
```

Expected result: all sampling unit tests pass.

### Task 2: CLI Command

**Files:**
- Modify: `src/stable_coin_trader/cli.py`
- Modify: `tests/unit/test_cli.py`

- [x] **Step 1: Write failing CLI tests**

Add a `sample-spreads` CLI test that monkeypatches public clients, runs two
samples with `--interval-seconds 0`, writes JSON Lines, and prints
sample/failure/observation summary counts.

- [x] **Step 2: Verify red**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_cli.py -v
```

Expected result: Typer command not found.

- [x] **Step 3: Add CLI wiring**

Parse mappings and Decimal options, instantiate public clients, call
`sample_spreads`, and print a concise summary. Convert validation/fetch failures
to exit code 1 only for command-level validation; per-sample failures are part
of the result.

- [x] **Step 4: Verify green**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_cli.py tests/unit/test_spread_sampling.py -v
```

Expected result: all focused tests pass.

### Task 3: Docs, Smoke Test, and Publish

**Files:**
- Modify: `README.md`
- Modify: `PROJECT.md`
- Modify: `PROJECT_LOG.md`

- [x] Document `sample-spreads`.
- [x] Update current status and next steps.
- [x] Run `.venv/bin/python -m pytest -v`.
- [x] Run `git diff --check`.
- [x] Run a real public smoke sample with `--samples 1 --interval-seconds 0`.
- [x] Run a committed-file secret scan.
- [ ] Commit, push, and open a draft PR stacked on `feature/spread-observation-reporting`.
