"""Conjuntos de cotações de arranque rápido (exemplos do caderno).

Partilhados pela TUI e pela web. Cada tuplo é ``(base, cotada, bid, ask[, fonte])``,
pronto a passar a ``Cotacao(*args)``.
"""

from __future__ import annotations

# Ex. 12 — sem arbitragem, ilustra cross direto/indireto.
EXEMPLOS_CROSS: list[tuple[str, ...]] = [
    ("GBP", "CAD", "1.8091", "1.8096"),
    ("CHF", "CAD", "1.7029", "1.7035"),
    ("CAD", "SEK", "6.5499", "6.5533"),
]

# Ex. 17 — triângulo GBP/JPY/EUR com arbitragem.
EXEMPLOS_ARBITRAGEM: list[tuple[str, ...]] = [
    ("GBP", "JPY", "212.646", "212.689"),
    ("EUR", "JPY", "183.618", "183.646"),
    ("GBP", "EUR", "1.1559", "1.1561"),
]

# Ex. 15 — EUR/USD em duas praças (arbitragem geográfica).
EXEMPLOS_GEOGRAFICA: list[tuple[str, ...]] = [
    ("EUR", "USD", "1.1574", "1.1576", "Paris"),
    ("EUR", "USD", "1.1583", "1.1585", "Londres"),
]

# Ex. 27 — spot CHF/USD para o exemplo de forward.
EXEMPLOS_FORWARD_SPOT: tuple[str, ...] = ("CHF", "USD", "1.2745", "1.2748")

# Forward CHF/USD a 180d + forward de mercado 1,3076–1,3079 (tem arbitragem a prazo).
EXEMPLO_FORWARD_INPUT: str = "CHF USD 180 0.1072 0.1144 4.9379 4.9438 1.3076 1.3079"
