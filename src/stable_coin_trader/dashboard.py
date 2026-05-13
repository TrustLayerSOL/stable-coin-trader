from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from stable_coin_trader.models import parse_dt
from stable_coin_trader.spread_observations import (
    SpreadObservation,
    load_spread_observations,
    summarize_spread_observations,
)

_SAMPLE_LINE_RE = re.compile(
    r"sample=(?P<sample>\d+) status=(?P<status>successful|failed)"
)


def build_dashboard_snapshot(
    observations_path: Path,
    log_path: Path,
    expected_samples: int | None,
) -> dict[str, Any]:
    observations = _load_observations_if_present(observations_path)
    summary = summarize_spread_observations(observations)
    log_lines = _read_log_lines(log_path)
    successful_samples, failed_samples = _sample_counts(log_lines)
    completed_samples = successful_samples + failed_samples

    return {
        "generated_at": _format_datetime(datetime.now(timezone.utc)),
        "observations_path": str(observations_path),
        "log_path": str(log_path),
        "observation_count": summary.observation_count,
        "profitable_count": summary.profitable_count,
        "profitable_pct": _pct(summary.profitable_count, summary.observation_count),
        "best_route": summary.best_route,
        "best_edge_bps": _format_decimal(summary.best_net_edge_bps),
        "average_edge_bps": _format_decimal(summary.average_net_edge_bps),
        "first_observed_at": _format_optional_datetime(summary.first_observed_at),
        "last_observed_at": _format_optional_datetime(summary.last_observed_at),
        "sample_success_count": successful_samples,
        "sample_failure_count": failed_samples,
        "completed_samples": completed_samples,
        "expected_samples": expected_samples,
        "completion_pct": _pct(completed_samples, expected_samples),
        "route_stats": _route_stats(observations),
        "edge_series": _edge_series(observations),
        "recent_observations": _recent_observations(observations, limit=24),
        "log_tail": log_lines[-30:],
        "files": {
            "observations": _file_status(observations_path),
            "log": _file_status(log_path),
        },
    }


def run_dashboard_server(
    observations_path: Path,
    log_path: Path,
    expected_samples: int | None,
    host: str,
    port: int,
) -> None:
    handler = _handler_factory(
        observations_path=observations_path,
        log_path=log_path,
        expected_samples=expected_samples,
    )
    server = ThreadingHTTPServer((host, port), handler)
    try:
        server.serve_forever()
    finally:
        server.server_close()


def _load_observations_if_present(path: Path) -> list[SpreadObservation]:
    if not path.exists():
        return []
    return load_spread_observations(path)


def _read_log_lines(path: Path) -> list[str]:
    if not path.exists():
        return []
    return path.read_text(encoding="utf-8").splitlines()


def _sample_counts(log_lines: list[str]) -> tuple[int, int]:
    successful = 0
    failed = 0
    for line in log_lines:
        match = _SAMPLE_LINE_RE.search(line)
        if match is None:
            continue
        if match.group("status") == "successful":
            successful += 1
        else:
            failed += 1
    return successful, failed


def _route_stats(observations: list[SpreadObservation]) -> list[dict[str, Any]]:
    by_route: dict[str, list[SpreadObservation]] = defaultdict(list)
    for observation in observations:
        by_route[observation.route].append(observation)

    stats = []
    for route, route_observations in sorted(by_route.items()):
        edges = [observation.net_edge_bps for observation in route_observations]
        profits = [observation.net_profit for observation in route_observations]
        count = len(route_observations)
        profitable_count = sum(
            1 for observation in route_observations if observation.is_profitable
        )
        stats.append(
            {
                "route": route,
                "count": count,
                "profitable_count": profitable_count,
                "profitable_pct": _pct(profitable_count, count),
                "best_edge_bps": _format_decimal(max(edges)),
                "worst_edge_bps": _format_decimal(min(edges)),
                "average_edge_bps": _format_decimal(sum(edges, Decimal("0")) / count),
                "average_net_profit": _format_decimal(
                    sum(profits, Decimal("0")) / count
                ),
            }
        )
    return stats


def _edge_series(observations: list[SpreadObservation]) -> list[dict[str, str]]:
    return [
        {
            "route": observation.route,
            "edge_bps": _format_decimal(observation.net_edge_bps),
            "observed_at": _format_datetime(observation.observed_at),
        }
        for observation in sorted(observations, key=lambda item: item.observed_at)[-120:]
    ]


def _recent_observations(
    observations: list[SpreadObservation],
    limit: int,
) -> list[dict[str, Any]]:
    recent = sorted(observations, key=lambda item: item.observed_at, reverse=True)
    return [
        {
            "observed_at": _format_datetime(observation.observed_at),
            "route": observation.route,
            "net_edge_bps": _format_decimal(observation.net_edge_bps),
            "net_profit": _format_decimal(observation.net_profit),
            "buy_price": _format_decimal(observation.buy_price),
            "sell_price": _format_decimal(observation.sell_price),
            "size": _format_decimal(observation.size),
            "profitable": observation.is_profitable,
        }
        for observation in recent[:limit]
    ]


def _file_status(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "size_bytes": 0, "modified_at": None}
    stat = path.stat()
    return {
        "exists": True,
        "size_bytes": stat.st_size,
        "modified_at": _format_datetime(
            datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
        ),
    }


def _pct(numerator: int, denominator: int | None) -> str | None:
    if denominator in (None, 0):
        return None
    value = (Decimal(numerator) / Decimal(denominator)) * Decimal("100")
    rounded = value.quantize(Decimal("0.01"))
    formatted = format(rounded, "f").rstrip("0").rstrip(".")
    return formatted or "0"


def _format_decimal(value: Decimal | None) -> str | None:
    if value is None:
        return None
    rounded = value.quantize(Decimal("0.00000001"))
    formatted = format(rounded, "f").rstrip("0").rstrip(".")
    return formatted or "0"


def _format_optional_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    return _format_datetime(value)


def _format_datetime(value: datetime) -> str:
    return parse_dt(value).isoformat().replace("+00:00", "Z")


def _handler_factory(
    observations_path: Path,
    log_path: Path,
    expected_samples: int | None,
) -> type[BaseHTTPRequestHandler]:
    class DashboardHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            parsed = urlparse(self.path)
            if parsed.path == "/":
                self._send_html(_DASHBOARD_HTML)
                return
            if parsed.path == "/api/status":
                self._send_json(
                    build_dashboard_snapshot(
                        observations_path=observations_path,
                        log_path=log_path,
                        expected_samples=expected_samples,
                    )
                )
                return
            self.send_error(HTTPStatus.NOT_FOUND)

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _send_html(self, body: str) -> None:
            encoded = body.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def _send_json(self, body: dict[str, Any]) -> None:
            encoded = json.dumps(body).encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    return DashboardHandler


_DASHBOARD_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Stablecoin Spread Observer</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f4f7fb;
      --panel: #ffffff;
      --panel-2: #edf3f9;
      --line: #d6e0ea;
      --text: #172033;
      --muted: #607086;
      --accent: #0fbaa8;
      --amber: #c98516;
      --red: #c43f4a;
      --green: #137a46;
      --blue: #2f6fd6;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      letter-spacing: 0;
    }
    .topbar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 20px;
      padding: 18px 24px;
      border-bottom: 1px solid var(--line);
      background: #ffffff;
      position: sticky;
      top: 0;
      z-index: 10;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
      min-width: 0;
    }
    .mark {
      width: 34px;
      height: 34px;
      border-radius: 8px;
      background:
        linear-gradient(135deg, #29d4bf, var(--blue) 62%, #f6c15c);
    }
    h1 {
      margin: 0;
      font-size: 18px;
      line-height: 1.2;
      font-weight: 750;
    }
    .subtle {
      color: var(--muted);
      font-size: 12px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .status {
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--muted);
      font-size: 13px;
    }
    .dot {
      width: 9px;
      height: 9px;
      border-radius: 999px;
      background: var(--amber);
      box-shadow: 0 0 12px color-mix(in srgb, var(--amber), transparent 35%);
    }
    main {
      width: min(1440px, 100%);
      margin: 0 auto;
      padding: 22px 24px 32px;
    }
    .metrics {
      display: grid;
      grid-template-columns: repeat(6, minmax(140px, 1fr));
      gap: 12px;
      margin-bottom: 18px;
    }
    .metric,
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
    }
    .metric {
      min-height: 94px;
      padding: 14px;
    }
    .label {
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: .04em;
      margin-bottom: 8px;
    }
    .value {
      font-size: 28px;
      line-height: 1.1;
      font-weight: 760;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
    .value.small { font-size: 20px; }
    .negative { color: var(--red); }
    .positive { color: var(--green); }
    .neutral { color: var(--text); }
    .grid {
      display: grid;
      grid-template-columns: minmax(0, 1.35fr) minmax(360px, .65fr);
      gap: 16px;
      align-items: start;
    }
    .panel {
      overflow: hidden;
      margin-bottom: 16px;
    }
    .panel-head {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      padding: 14px 16px;
      border-bottom: 1px solid var(--line);
      background: var(--panel-2);
    }
    h2 {
      margin: 0;
      font-size: 15px;
      line-height: 1.2;
      font-weight: 730;
    }
    canvas {
      width: 100%;
      height: 260px;
      display: block;
      background: #f8fbff;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      table-layout: fixed;
    }
    th,
    td {
      padding: 11px 14px;
      text-align: left;
      border-bottom: 1px solid var(--line);
      font-size: 13px;
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }
    th {
      color: var(--muted);
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: .04em;
      background: #f4f8fc;
    }
    .log {
      margin: 0;
      padding: 14px 16px;
      min-height: 240px;
      max-height: 360px;
      overflow: auto;
      color: #263447;
      background: #f8fbff;
      font: 12px/1.55 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
      white-space: pre-wrap;
    }
    .footer {
      color: var(--muted);
      font-size: 12px;
      margin-top: 4px;
    }
    @media (max-width: 1100px) {
      .metrics { grid-template-columns: repeat(3, minmax(140px, 1fr)); }
      .grid { grid-template-columns: 1fr; }
    }
    @media (max-width: 680px) {
      .topbar { align-items: flex-start; flex-direction: column; }
      main { padding: 16px; }
      .metrics { grid-template-columns: repeat(2, minmax(0, 1fr)); }
      .value { font-size: 23px; }
    }
  </style>
</head>
<body>
  <header class="topbar">
    <div class="brand">
      <div class="mark" aria-hidden="true"></div>
      <div>
        <h1>Stablecoin Spread Observer</h1>
        <div class="subtle" id="paths">loading...</div>
      </div>
    </div>
    <div class="status"><span class="dot"></span><span id="updated">waiting</span></div>
  </header>
  <main>
    <section class="metrics">
      <div class="metric"><div class="label">Samples</div><div class="value" id="samples">0</div><div class="subtle" id="sampleDetail">0% complete</div></div>
      <div class="metric"><div class="label">Observations</div><div class="value" id="observations">0</div><div class="subtle" id="failures">0 failures</div></div>
      <div class="metric"><div class="label">Profitable</div><div class="value" id="profitable">0</div><div class="subtle" id="profitablePct">n/a</div></div>
      <div class="metric"><div class="label">Best Edge</div><div class="value" id="bestEdge">n/a</div><div class="subtle" id="bestRoute">none</div></div>
      <div class="metric"><div class="label">Average Edge</div><div class="value" id="averageEdge">n/a</div><div class="subtle">basis points</div></div>
      <div class="metric"><div class="label">Last Tick</div><div class="value small" id="lastObserved">n/a</div><div class="subtle" id="firstObserved">first n/a</div></div>
    </section>

    <section class="grid">
      <div>
        <section class="panel">
          <div class="panel-head"><h2>Net Edge</h2><div class="subtle">latest 120 observations</div></div>
          <canvas id="edgeCanvas" width="1200" height="320"></canvas>
        </section>
        <section class="panel">
          <div class="panel-head"><h2>Routes</h2><div class="subtle" id="routeCount">0 routes</div></div>
          <table>
            <thead><tr><th>Route</th><th>Count</th><th>Hit Rate</th><th>Best bps</th><th>Avg bps</th><th>Worst bps</th></tr></thead>
            <tbody id="routes"></tbody>
          </table>
        </section>
        <section class="panel">
          <div class="panel-head"><h2>Latest Observations</h2><div class="subtle">most recent first</div></div>
          <table>
            <thead><tr><th>Time</th><th>Route</th><th>Edge bps</th><th>Net</th><th>Buy</th><th>Sell</th><th>Size</th></tr></thead>
            <tbody id="recent"></tbody>
          </table>
        </section>
      </div>
      <aside>
        <section class="panel">
          <div class="panel-head"><h2>Sampler Log</h2><div class="subtle" id="logState">0 lines</div></div>
          <pre class="log" id="log"></pre>
        </section>
        <div class="footer" id="files"></div>
      </aside>
    </section>
  </main>
  <script>
    const $ = (id) => document.getElementById(id);
    const edgeClass = (value) => {
      const numeric = Number(value);
      if (!Number.isFinite(numeric)) return "neutral";
      return numeric > 0 ? "positive" : numeric < 0 ? "negative" : "neutral";
    };
    const fmt = (value, suffix = "") => value === null || value === undefined ? "n/a" : `${value}${suffix}`;
    const shortTime = (value) => value ? value.replace("T", " ").replace("Z", "") : "n/a";

    async function refresh() {
      const response = await fetch("/api/status", { cache: "no-store" });
      const data = await response.json();
      $("updated").textContent = `updated ${shortTime(data.generated_at)}`;
      $("paths").textContent = data.observations_path;
      $("samples").textContent = data.expected_samples ? `${data.completed_samples}/${data.expected_samples}` : `${data.completed_samples}`;
      $("sampleDetail").textContent = data.completion_pct ? `${data.completion_pct}% complete` : "running";
      $("observations").textContent = data.observation_count;
      $("failures").textContent = `${data.sample_failure_count} failures`;
      $("profitable").textContent = data.profitable_count;
      $("profitablePct").textContent = data.profitable_pct ? `${data.profitable_pct}% hit rate` : "n/a";
      $("bestEdge").textContent = fmt(data.best_edge_bps, " bps");
      $("bestEdge").className = `value ${edgeClass(data.best_edge_bps)}`;
      $("bestRoute").textContent = data.best_route || "none";
      $("averageEdge").textContent = fmt(data.average_edge_bps, " bps");
      $("averageEdge").className = `value ${edgeClass(data.average_edge_bps)}`;
      $("lastObserved").textContent = shortTime(data.last_observed_at);
      $("firstObserved").textContent = `first ${shortTime(data.first_observed_at)}`;
      $("routeCount").textContent = `${data.route_stats.length} routes`;
      $("routes").innerHTML = data.route_stats.map((route) => `
        <tr>
          <td title="${route.route}">${route.route}</td>
          <td>${route.count}</td>
          <td>${fmt(route.profitable_pct, "%")}</td>
          <td class="${edgeClass(route.best_edge_bps)}">${fmt(route.best_edge_bps)}</td>
          <td class="${edgeClass(route.average_edge_bps)}">${fmt(route.average_edge_bps)}</td>
          <td class="${edgeClass(route.worst_edge_bps)}">${fmt(route.worst_edge_bps)}</td>
        </tr>`).join("");
      $("recent").innerHTML = data.recent_observations.map((item) => `
        <tr>
          <td>${shortTime(item.observed_at)}</td>
          <td title="${item.route}">${item.route}</td>
          <td class="${edgeClass(item.net_edge_bps)}">${item.net_edge_bps}</td>
          <td>${item.net_profit}</td>
          <td>${item.buy_price}</td>
          <td>${item.sell_price}</td>
          <td>${item.size}</td>
        </tr>`).join("");
      $("log").textContent = data.log_tail.join("\\n");
      $("logState").textContent = `${data.log_tail.length} lines`;
      $("files").textContent = `log: ${data.files.log.size_bytes} bytes | observations: ${data.files.observations.size_bytes} bytes`;
      drawEdge(data.edge_series);
    }

    function drawEdge(series) {
      const canvas = $("edgeCanvas");
      const ctx = canvas.getContext("2d");
      const width = canvas.width;
      const height = canvas.height;
      ctx.clearRect(0, 0, width, height);
      ctx.fillStyle = "#f8fbff";
      ctx.fillRect(0, 0, width, height);
      ctx.strokeStyle = "#d6e0ea";
      ctx.lineWidth = 1;
      for (let i = 1; i < 5; i++) {
        const y = (height / 5) * i;
        ctx.beginPath();
        ctx.moveTo(0, y);
        ctx.lineTo(width, y);
        ctx.stroke();
      }
      const values = series.map((item) => Number(item.edge_bps)).filter(Number.isFinite);
      if (!values.length) return;
      const min = Math.min(...values, -0.1);
      const max = Math.max(...values, 0.1);
      const span = max - min || 1;
      const yFor = (value) => height - ((value - min) / span) * (height - 28) - 14;
      const zeroY = yFor(0);
      ctx.strokeStyle = "#c43f4a";
      ctx.setLineDash([6, 6]);
      ctx.beginPath();
      ctx.moveTo(0, zeroY);
      ctx.lineTo(width, zeroY);
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.lineWidth = 2;
      values.forEach((value, index) => {
        const x = values.length === 1 ? width / 2 : (index / (values.length - 1)) * (width - 36) + 18;
        const y = yFor(value);
        ctx.strokeStyle = value >= 0 ? "#137a46" : "#c98516";
        ctx.beginPath();
        ctx.arc(x, y, 3, 0, Math.PI * 2);
        ctx.stroke();
      });
    }

    refresh();
    setInterval(refresh, 5000);
  </script>
</body>
</html>
"""
