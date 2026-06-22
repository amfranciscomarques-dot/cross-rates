"""Feed determinístico (fixture estática) — para testes e demos offline.

Um instantâneo fixo de cotações EUR/X (mids do BCE com um pequeno spread já
embutido). Não toca na rede, pelo que os testes ficam determinísticos e a web
abre com dados mesmo sem ligação. Implementa o mesmo ``cotacoes()`` que o
:class:`cross_rates.feeds.frankfurter.FrankfurterFeed`.
"""

from __future__ import annotations

from cross_rates.nucleo import Cotacao, para_decimal

# (base, cotada, bid, ask) — snapshot estável de pares EUR/X.
_FIXTURE: list[tuple[str, str, str, str]] = [
    ("EUR", "USD", "1.08510", "1.08530"),
    ("EUR", "GBP", "0.84140", "0.84160"),
    ("EUR", "JPY", "170.440", "170.480"),
    ("EUR", "CHF", "0.95280", "0.95320"),
    ("EUR", "CAD", "1.47550", "1.47590"),
    ("EUR", "AUD", "1.63080", "1.63120"),
    ("EUR", "SEK", "11.3120", "11.3160"),
    ("EUR", "NOK", "11.7200", "11.7240"),
    ("EUR", "DKK", "7.45600", "7.45700"),
    ("EUR", "PLN", "4.27300", "4.27500"),
]


class FeedSimulado:
    """Fonte de cotações estática (sem rede), determinística para testes."""

    def __init__(self, fonte: str = "Simulado") -> None:
        self._fonte = fonte

    def cotacoes(self) -> list[Cotacao]:
        return [
            Cotacao(base, cotada, para_decimal(bid), para_decimal(ask), self._fonte)
            for base, cotada, bid, ask in _FIXTURE
        ]
