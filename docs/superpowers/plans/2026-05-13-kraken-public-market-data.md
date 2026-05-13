# Kraken Public Market Data Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a paper-only Kraken public market-data adapter that writes real order-book snapshots into the existing fixture format.

**Architecture:** Keep exchange-specific code in `src/stable_coin_trader/kraken.py`. The CLI calls that adapter and writes JSON snapshots; the trading engine remains unchanged except for consuming the generated file through the existing loader.

**Tech Stack:** Python stdlib `urllib`, Typer CLI, Pydantic models, pytest.

---

### Task 1: Kraken Public Client

**Files:**
- Create: `src/stable_coin_trader/kraken.py`
- Test: `tests/unit/test_kraken.py`

- [ ] Write tests for pair mapping parsing, public depth parsing, Kraken API error handling, malformed depth rejection, and JSON snapshot serialization.
- [ ] Run focused tests and verify they fail because the module does not exist.
- [ ] Implement the minimal public client and writer.
- [ ] Run focused tests and verify they pass.

### Task 2: CLI Fetch Command

**Files:**
- Modify: `src/stable_coin_trader/cli.py`
- Test: `tests/unit/test_cli.py`

- [ ] Write a CLI test that monkeypatches the Kraken client and verifies `fetch-kraken-snapshots` writes fixture-shaped JSON.
- [ ] Run the CLI test and verify it fails because the command does not exist.
- [ ] Add the Typer command.
- [ ] Run the CLI test and verify it passes.

### Task 3: Safe Secret Placeholders and Docs

**Files:**
- Create: `.env.example`
- Modify: `README.md`
- Modify: `PROJECT.md`
- Modify: `PROJECT_LOG.md`

- [ ] Add empty placeholder names for future Kraken private credentials.
- [ ] Document that this feature does not use private credentials.
- [ ] Update project status and log.

### Task 4: Verification

**Files:**
- All changed files

- [ ] Run `.venv/bin/python -m pytest -v`.
- [ ] Run `git diff --check`.
- [ ] Commit the feature.
- [ ] Push the feature branch and open a draft PR.
