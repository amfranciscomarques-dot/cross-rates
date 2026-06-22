# Plan

Phased roadmap for cross-rates. Each phase is self-contained and shippable.
Phases are ordered by portfolio impact: the first two convert the project from
"motor de cálculo" to "ferramenta operacional" visible to a recruiter without
a local install.

---

## Phase 1 — Live price feed

**Goal:** seed the `GrafoCambial` with real market quotes so the web UI opens
with live data, not an empty table.

**Rationale:** the financial core is already correct and tested. The missing
signal for Quant/FX roles is that the math runs on real inputs, not
hand-typed classroom numbers. A live feed closes that gap with minimal new
code.

**Scope:**

- Add `cross_rates/feeds/` package with a `FonteCotacoes` protocol:
  ```python
  class FonteCotacoes(Protocol):
      def cotacoes(self) -> list[Cotacao]: ...
  ```
- Implement `FrankfurterFeed` — free, no API key required, returns latest ECB
  rates. Covers ~30 currency pairs. Mid rates only (the ECB publishes no
  spreads), so the feed adds a configurable synthetic spread to produce bid/ask.
- Wire into the web UI: on `GET /`, if a feed is configured, pre-populate the
  graph before rendering. The existing stateless architecture does not change —
  the feed is just the initial seeding call.
- Add `cross_rates/feeds/simulado.py` with a `FeedSimulado` (static fixture)
  so tests remain deterministic and offline.

**Out of scope:** WebSocket streaming, tick data, any paid provider.

---

## Phase 2 — Public deployment

**Goal:** a live URL in the README so the web UI is usable without a local
install.

**Rationale:** a recruiter who clicks a link and sees the tool working is
categorically different from one who reads about it. This phase has near-zero
new code; the work is infrastructure.

**Scope:**

- Add `Dockerfile` (multi-stage: builder + slim runtime) for the web UI.
- Add `fly.toml` for Fly.io free-tier deploy (512 MB, shared CPU).
- CI step: on push to `main`, deploy to Fly.io if tests pass.
- Update README with the live URL and a screenshot.

**Dependency:** Phase 1 (the live feed makes the deployed demo non-trivial to
use; without it the demo opens to an empty table).

**Progress:** container image (`Dockerfile`) + `DEPLOYMENT.md` shipped; CI builds
and smoke-tests the image. As an interim stand-in for the live URL, the README
now embeds web-UI screenshots (`docs/screenshots/`) captured against the app
running on the live Frankfurter feed — hero (seeded table), a cross-rate, and
the hedging panel with the option hedge. **Still open:** `fly.toml` (or another
host), a CI deploy step, and a clickable live URL in the README.

---

## Phase 3 — FX options (Garman-Kohlhagen) ✅ shipped

**Goal:** extend the hedging module with vanilla FX option pricing and basic
Greeks, completing the "full exposure lifecycle" story.

**Rationale:** a recruiter reading cross-rates + CIP + arbitrage + hedging
naturally asks "and delta hedging?". Options close the loop and demonstrate
the stochastic layer on top of the deterministic CIP model already built.

**Scope:**

- Add `cross_rates/nucleo/opcoes.py`:
  - `OpcaoVanilla` dataclass (call/put, strike, notional, tenor, currency pair).
  - `garman_kohlhagen(opcao, spot, vol, juro_base, juro_cotada)` returning
    price, delta, gamma, vega, theta, rho.
  - `Decimal`-based implementation; volatility input as annualised `%`.
  - Both `mypy --strict` and 100%-coverage requirements apply.
- Add hedging comparison: forward hedge vs. option hedge (pay premium, keep
  upside) as a third strategy in `analisa_hedging`.
- Tests pinned to textbook examples (Madura ch. 5 / Hull ch. 17).
- Expose in both UIs: new `/opcao` route in the web UI; new panel in the TUI.

**Dependency:** none (purely additive to `nucleo/`).

**Delivered:** `garman_kohlhagen()` + Greeks, the `/opcao` web route and the TUI
options panel (key `k`). The option hedge is wired into `analisa_hedging` via
optional `opcao_strike`/`vol` — a Madura-style contingent strategy fixing the
maximum cost (put on the base, payment) or minimum proceeds (call, receipt).
Design choice: it is **contingent**, so it does not re-rank `melhor_estrategia`
(still forward-vs-MMH). The exercise leg `montante / strike` is exact; the
option leg is mid-based (the GK price is itself a mid) and labelled as such, so
the existing exact bid/ask forward and MMH rows are unaffected and the change
is backward-compatible (new fields default to `None`).

---

## Deferred

**Bilingual codebase.** The Portuguese naming in `nucleo/` is a deliberate
choice: the tests are pinned to a PT-PT coursework, and the terminology maps
exactly (no translation layer). For international roles the README explains the
vocabulary mapping. Renaming would decouple the code from its test anchors
and add maintenance surface for no mathematical gain. Revisit only if
targeting roles where source-code readability by the recruiter is a specific
requirement.

**Tick streaming / order book.** Out of scope until a use-case beyond
"detect arbitrage in real time" is defined. The `FonteCotacoes` protocol in
Phase 1 leaves the door open without committing to a specific feed mechanism.
