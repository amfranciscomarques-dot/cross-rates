# Changelog

All notable changes to cross-rates are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

### Added

**Price feeds (`feeds/`)**

- `FonteCotacoes` protocol — interface for any quote source returning
  `Cotacao` objects, so the frontends can seed the graph without depending on
  a concrete feed.
- `FrankfurterFeed` — live ECB reference rates via the free, key-less
  Frankfurter API (~30 `EUR/X` pairs). The ECB publishes mid rates only, so the
  feed applies a configurable synthetic spread (`spread_bps`) to derive
  bid/ask. HTTP access is injectable, keeping tests offline and deterministic.
- `FeedSimulado` — static fixture feed (no network) for deterministic tests
  and offline demos.
- `feed_por_nome()` — factory resolving a config name
  (`frankfurter` | `simulado` | `none`) to a feed.

**Web UI (`web/`)**

- `GET /` seeds the quote table from a feed when the `CROSS_RATES_FEED`
  environment variable is set (`frankfurter` or `simulado`), so the page opens
  with live data instead of an empty table. Unset by default. Degrades
  gracefully (empty table + note) if the feed is unavailable.

**Containerisation (`Dockerfile`)**

- Multi-stage `Dockerfile` for the web UI: a builder stage installs the package
  with the `web` extra into an isolated virtualenv, copied into a slim,
  non-root runtime image. Host-agnostic — no provider-specific config.
- `serve()` now reads host/port from the environment (`CROSS_RATES_HOST`,
  `CROSS_RATES_PORT`, falling back to the generic `PORT`), defaulting to
  `127.0.0.1:8000` locally. The container binds `0.0.0.0` and seeds from the
  live feed (`CROSS_RATES_FEED=frankfurter`) via image defaults.
- `DEPLOYMENT.md` documents building and running the container.

**Quality**

- `mypy --strict` and the 100% line-coverage gate now extend to `feeds/`.
- CI now installs the `web` extra (so the web tests actually run) and builds +
  smoke-tests the Docker image on every push/PR (build only, no deploy).

---

## [0.1.0] — 2025

### Added

**Financial core (`nucleo/`)**

- `Cotacao` — immutable, validated `BASE/QUOTE` pair with `bid`, `ask`, and
  optional source venue (`fonte`). `Numerico` type alias accepts `Decimal`,
  `int`, `float`, or `str`; all normalised to `Decimal` internally.
- `GrafoCambial` — directed currency graph. Each `Cotacao` adds two edges:
  `BASE → QUOTE` at `bid`, `QUOTE → BASE` at `1/ask`. BFS path-finding
  (`percurso`) resolves multi-hop chains automatically.
- `cross()` — synthetic cross-rate with correct bid/ask microstructure.
  Results carry the traversal path, a textbook-style label (direct, inverse,
  cross direct ÷, cross indirect ×, chain), explicit bid/ask formulas, and a
  methodological note.
- `arbitragens_triangulares()` — detects profitable 3-currency cycles; returns
  results sorted by factor descending. Accepts a minimum threshold (`limiar`)
  to filter sub-cost opportunities. Each `Arbitragem` exposes `lucro()` and
  `simulacao()` for step-by-step amounts.
- `arbitragens_geograficas()` — detects same-pair mispricings across venues;
  same threshold and output API.
- `TaxaJuro` — annual interest rate with `bid`/`ask` (in %) and
  `ConvencaoDia` (Act/360 or Act/365). Convention inferred from currency by
  default (GBP/AUD/NZD → Act/365; all others → Act/360).
- `forward()` — CIP forward rate (`F = S × factor_quote / factor_base`) with
  full bid/ask microstructure. Returns `ResultadoForward` with swap points,
  premium/discount signal, and explicit formulas.
- `arbitragem_a_prazo()` — detects covered interest arbitrage when the
  market-quoted forward falls outside the parity band.
- `outright_de_pontos()` — FX swap outright from spot + swap points.
  Premium/discount inferred from the relative size of bid and ask points.
- `analisa_hedging()` — compares forward hedge against money-market hedge for
  a future payment or receipt; selects the cheaper strategy.

**Service layer (`servico/`)**

- Shared operation functions (`calcular_cross`, `calcular_forward`,
  `calcular_swap`, `calcular_hedge`, `analisar_arbitragem`) called by both UIs.
- Serialisation helpers (`serial.py`) converting domain objects to plain dicts
  for template rendering.
- Formatting helpers and pre-built example fixtures (`exemplos.py`).

**Textual TUI (`tui/`)**

- Full-featured terminal interface: quote management, cross-rate calculation,
  triangular + geographical + term arbitrage, forward pricing, swap outrights,
  hedging analysis, and a theory panel.
- Integration-tested via `test_tui.py` and `test_pratica.py`.

**FastAPI web UI (`web/`)**

- Stateless server: browser holds quote state in hidden form fields; each
  request rebuilds the graph and returns an htmx HTML fragment.
- Routes: `/`, `/cotacoes`, `/exemplos/{conjunto}`, `/limpar`, `/cross`,
  `/arbitragem`, `/forward`, `/swap`, `/hedge`.
- Entry point `cross-rates-web` starts uvicorn on `127.0.0.1:8000`.

**Quality**

- `mypy --strict` clean on `nucleo/` and `servico/`.
- 100% line-coverage gate on `nucleo/` and `servico/` (TUI excluded).
- Ruff (E/F/I/UP/B rule sets) for lint and import sorting.
- CI via GitHub Actions on every push and pull request.
- All tests in `testes/` pinned to solved textbook exercises with 0.01%
  relative tolerance on computed results.
