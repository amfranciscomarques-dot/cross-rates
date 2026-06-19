# cross-rates — FX Microstructure, CIP & Arbitrage Toolkit

A terminal toolkit for **foreign-exchange mathematics**: cross-rates with full
**bid/ask** microstructure, **covered interest parity** (CIP) forwards with
real day-count conventions, and **triangular / geographical / term arbitrage**
detection. Built to be read as a portfolio piece for Quant/FX roles — every
formula is anchored to a textbook result and locked by unit tests.

> The core thesis: FX math is *graph traversal over a directed currency graph
> where every edge carries a two-sided quote*, and arbitrage is simply a cycle
> whose product of edge weights exceeds 1. This project makes that thesis
> executable.

---

## Why this exists

Most "currency converter" toys take a single mid rate and divide. Real FX is
two-sided (`bid`/`ask`), the side you transact is always the one *unfavourable
to you*, and the cross-rate between two minor currencies is derived through a
vehicle currency (usually USD) — multiplying the spreads at every hop. This
repository models that faithfully, then layers the no-arbitrage theory on top:

- **Bid/ask microstructure** — every conversion applies the correct leg of the
  quote (Section 1).
- **Covered Interest Parity** — forward rates derived from money-market rates,
  with **Act/360 and Act/365** day counts (Section 3).
- **Triangular arbitrage** — detected as a profitable cycle in the currency
  graph (Section 2).

All math runs on `Decimal` (no binary float drift) and the financial core is
100% type-checked (`mypy --strict`) and unit-tested against solved textbook
exercises.

---

## 1. Bid/ask microstructure & cross-rates

In the notation `BASE/QUOTE`, the **base** is *certain* (the "1") and the
**quote** is *uncertain* (the price). The quote says how many units of QUOTE
buy one unit of BASE, and always satisfies `bid <= ask`:

| Party            | Buys the base | Sells the base |
| ---------------- | ------------- | -------------- |
| Market maker     | at the `bid`  | at the `ask`   |
| Customer         | at the `ask`  | at the `bid`   |

Each quote `BASE/QUOTE (bid b, ask a)` produces **two directed conversions**:

- `BASE → QUOTE` at rate `b`  (sell 1 base, receive `b` quote)
- `QUOTE → BASE` at rate `1/a` (1 quote buys `1/a` base)

So a cross-rate is just a path in the directed currency graph, and the two sides
of the cross use *different* paths — the one unfavourable to the customer each
time:

```python
from cross_rates.nucleo import Cotacao, GrafoCambial, cross

g = GrafoCambial()
g.adicionar(Cotacao("EUR", "USD", "1.1574", "1.1576", "Paris"))
g.adicionar(Cotacao("GBP", "USD", "1.2500", "1.2510", "London"))

r = cross(g, "GBP", "EUR")
print(r.bid, "/", r.ask)   # 1.0798 / 1.0809  (GBP/EUR via USD)
print(r.bid_formula)       # bid = bid(GBP/USD) ÷ ask(EUR/USD)
```

The bid path `GBP→USD→EUR` sells the base (GBP) and collects the worst leg at
each hop; the ask path `EUR→USD→GBP` is its inverse. This single model reproduces
the textbook "direct cross (÷)" and "indirect cross (×)" rules automatically,
and — critically — preserves the spread: the synthetic cross is always wider
than either component quote.

---

## 2. Triangular & geographical arbitrage

**Triangular arbitrage.** A 3-currency cycle `A→B→C→A` whose product of edge
rates (each already on the correct bid/ask leg) **exceeds 1** is risk-free
profit. The legs are simultaneous, so there is no market risk:

```
factor = ∏ rates(cycle) > 1   ⟹   profit = (factor − 1) × notional
```

This is the unified form of the textbook rule "implied cross vs. direct quote":
if the implied cross (from the cycle) differs from the directly quoted rate, a
cycle exists whose product departs from 1.

```python
from cross_rates.nucleo import Cotacao, GrafoCambial, arbitragens_triangulares

g = GrafoCambial()
g.adicionar(Cotacao("EUR", "USD", "1.1574", "1.1576"))
g.adicionar(Cotacao("GBP", "USD", "1.2500", "1.2510"))
g.adicionar(Cotacao("GBP", "EUR", "1.1600", "1.1610"))  # mispriced

for a in arbitragens_triangulares(g):
    print(a.ciclo, "factor =", a.fator, "P&L on 1m =", a.lucro(1_000_000))
```

**Geographical arbitrage.** The same pair quoted in different venues (the
optional `fonte` field on each `Cotacao`): profit exists iff the lowest `ask`
(buy the base) is below the highest `bid` (sell it): `ask(A) < bid(B)` → buy in
A, sell in B. See `arbitragens_geograficas()`.

---

## 3. Covered Interest Parity (CIP) forwards

The **forward** rate is *not* a forecast of the future spot. It is the rate that
**prevents arbitrage** between transacting the forward directly and replicating
it in the money market (borrow one currency, convert spot, lend the other). For
pair `BASE/QUOTE` over `n` days:

```
F = S × (1 + i_quote · n / n_q) / (1 + i_base · n / n_b)
```

where `n_b`, `n_q` are the **day-count bases** of each currency. This is the
economic content of **Covered Interest Parity** (a.k.a. interest rate parity).

### Day-count conventions

The base of the year is a **property of the currency**, not of the calculation.
`ConvencaoDia` encodes the two conventions that dominate FX money markets:

- **Act/360** ("Eurobasis") — USD, EUR, JPY, CHF, CAD, SEK, …
- **Act/365** ("Sterling basis") — GBP, AUD, NZD

Picking the wrong convention introduces a systematic ~1.4% bias in the prorated
rate — exactly the kind of silent error that sinks a desk P&L. The convention is
attached to each `TaxaJuro` and inferred from the currency by default:

```python
from cross_rates.nucleo import TaxaJuro

TaxaJuro.de_moeda("GBP", "5.0", "5.1").convencao   # Act/365 (auto)
TaxaJuro.de_moeda("USD", "4.9", "5.0").convencao   # Act/360 (auto)
```

### Premium / discount & bid/ask

- If `i_quote > i_base` then `F > S`: the base trades at a **forward premium**.
- If `i_quote < i_base` then `F < S`: the base trades at a **forward discount**.

With two-sided rates, each side of the forward combines the legs that are
unfavourable to the customer in the money-market replication:

```
F_bid = S_bid · (1 + i_bid,quote · n/n_q) / (1 + i_ask,base · n/n_b)
F_ask = S_ask · (1 + i_ask,quote · n/n_q) / (1 + i_bid,base · n/n_b)
```

```python
from cross_rates.nucleo import Cotacao, TaxaJuro, forward

spot = Cotacao("CHF", "USD", "1.2700", "1.2705")
f = forward(spot,
            TaxaJuro("CHF", "0.1072", "0.1144"),
            TaxaJuro("USD", "4.9379", "4.9438"),
            180)
print(f.bid, "/", f.ask, f.sinal)   # 1.3006 / 1.3012  premium
```

### Covered interest arbitrage

When the market-quoted forward falls outside the parity band, term arbitrage is
available: sell the expensive leg, replicate the cheap one through the money
market. See `arbitragem_a_prazo()`.

### FX swaps (spot + forward)

A swap outright is reconstructed from the spot and the swap points, respecting
the premium/discount rule (`points_bid < points_ask` → premium, add; the reverse
→ discount, subtract). The point scale is currency-specific (e.g. JPY quotes on
2 decimals):

```python
from cross_rates.nucleo import Cotacao, outright_de_pontos

sw = outright_de_pontos(Cotacao("EUR", "USD", "1.1500", "1.1510"), "20", "30")
print(sw.fwd_bid, sw.fwd_ask, sw.sinal)   # 1.1520 1.1540 premium
```

---

## 4. Hedging foreign-currency exposure

For a future payment or receipt in a foreign (quote) currency, two hedges
replicate each other — and the **theorem is that they must**:

- **Forward hedge** — lock the forward rate today.
- **Money-market hedge (MMH)** — borrow/lend, convert spot, lend/borrow to
  replicate the forward synthetically.

In a frictionless market they are *mathematically identical*; this identity
**is** covered interest parity. With bid/ask spreads they diverge by a few
basis points, and the cheaper one (cost for a payment, higher for a receipt) is
chosen:

```python
from cross_rates.nucleo import Cotacao, TaxaJuro, analisa_hedging

spot = Cotacao("EUR", "USD", "1.0850", "1.0852")
h = analisa_hedging(
    "pagamento", 1_000_000, spot,                      # owe USD 1m in 90 days
    TaxaJuro("EUR", "2.0", "2.1"), TaxaJuro("USD", "4.2", "4.3"), 90,
)
print(h.fwd_resultado_base, h.mmh_resultado_base, h.melhor_estrategia)
# forward cost ≈ MMH cost ≈ EUR 916,870.55  (CIP holds)
```

Each leg of the MMH uses the correct bid/ask side: for a payment you *invest*
the quote currency at `i_bid`, convert at `S_bid`, and *borrow* the base at
`i_ask`; for a receipt the roles and sides invert.

---

## Install

```bash
pip install -e ".[dev]"          # core + textual TUI + dev tooling
```

Requires Python ≥ 3.11.

## Terminal UI

```bash
python -m cross_rates            # or: cross-rates
```

A Textual interface driving every feature above: add quotes (`EUR USD 1.1574
1.1576 Paris`), compute crosses, run triangular/geographical/term arbitrage,
price forwards with day-count-aware rates, and inspect a theory panel (`t`).
Shortcuts: `e` cross examples, `x`/`g`/`f` arbitrage & forward examples, `l`
clear, `q` quit.

## Tests, types, lint

```bash
pytest                  # full suite, with coverage
ruff check .            # lint + import sorting
mypy cross_rates/nucleo # strict types on the financial core
```

The financial core is held to a strict bar: `mypy --strict` clean, and every
test is anchored to a solved textbook exercise (Madura, Shapiro, Eun & Resnick)
so the math is validated against an independent source — not just internally
consistent.

---

## Architecture

```
cross_rates/
  nucleo/             # pure FX math, no I/O — the type-checked, tested core
    cotacao.py        # Cotacao: pair, bid, ask (+ validation, Numerico alias)
    grafo.py          # GrafoCambial: currencies (nodes) + conversions (edges)
    cross.py          # cross(): cross-rate, path, type, formulas, note
    arbitragem.py     # triangular + geographical arbitrage as graph cycles
    forward.py        # CIP forward, ConvencaoDia (Act/360, Act/365), term arb
    swaps.py          # FX swap outright from spot + swap points
    hedging.py        # forward hedge vs money-market hedge (CIP replication)
  tui/
    app.py            # Textual UI (cross, arbitrage, forward, hedge, theory)
testes/               # pinned to solved exercises + property tests
```

The design rule: **all FX math is pure and Decimal-based in `nucleo/`**, with
zero I/O, so it is fully testable and type-checkable. The TUI is a thin adapter.

## Roadmap

The same `GrafoCambial` backbone supports everything above. Remaining phases:

- **Real-time feeds** — pluggable price source (broker/exchange).
- **Optionality** — vanilla FX options (Garman-Kohlhagen) on top of the forward
  curve, for delta hedging of the exposures already modelled.

## References

- Madura, *International Financial Management* — money-market hedge, arbitrage.
- Shapiro, *Multinational Financial Management* — CIP, covered arbitrage.
- Eun & Resnick, *International Financial Management* — day-count conventions,
  cross-rate microstructure.
