"""Cálculos de Swaps Cambiais e pontos forward.

Um swap cambial (FX Swap) combina uma operação à vista (spot) e uma a prazo
(forward) em sentidos opostos, com a mesma contraparte.

A cotação de swaps no mercado é frequentemente feita em "pontos forward"
(swap points). A regra para calcular a taxa outright (F) a partir do Spot (S):
- Se pontos_bid < pontos_ask: a base está a prémio → F = S + pontos
- Se pontos_bid > pontos_ask: a base está a desconto → F = S - pontos
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .cotacao import Cotacao, CotacaoInvalida, Numerico, _para_decimal


@dataclass(frozen=True)
class SwapOutright:
    """Taxa forward outright construída a partir do spot e dos pontos de swap."""

    base: str
    cotada: str
    spot_bid: Decimal
    spot_ask: Decimal
    pontos_bid: Decimal
    pontos_ask: Decimal
    casas_decimais_pontos: int
    sinal: str  # "prémio" ou "desconto"
    fwd_bid: Decimal
    fwd_ask: Decimal

    @property
    def par(self) -> str:
        return f"{self.base}/{self.cotada}"

    @property
    def forward_formula_bid(self) -> str:
        op = "+" if self.sinal == "prémio" else "-"
        # Escala os pontos de volta ao formato decimal da cotação
        p = self.pontos_bid / Decimal(10 ** self.casas_decimais_pontos)
        return f"F_bid = {self.spot_bid} {op} {p} = {self.fwd_bid}"

    @property
    def forward_formula_ask(self) -> str:
        op = "+" if self.sinal == "prémio" else "-"
        p = self.pontos_ask / Decimal(10 ** self.casas_decimais_pontos)
        return f"F_ask = {self.spot_ask} {op} {p} = {self.fwd_ask}"


def outright_de_pontos(
    spot: Cotacao,
    pontos_bid: Numerico,
    pontos_ask: Numerico,
    casas_decimais_pontos: int = 4,
) -> SwapOutright:
    """Calcula a taxa forward a partir dos pontos de swap.
    
    Os pontos são dados geralmente como inteiros (ex: 20 30 para 0.0020 0.0030).
    A regra:
    - pontos_bid < pontos_ask: soma-se (base a prémio)
    - pontos_bid > pontos_ask: subtrai-se (base a desconto)
    """
    pb, pa = _para_decimal(pontos_bid), _para_decimal(pontos_ask)
    
    if pb < 0 or pa < 0:
        raise CotacaoInvalida(
            "Os pontos de swap devem ser fornecidos como valores positivos absolutos."
        )

    escala = Decimal(10) ** casas_decimais_pontos
    
    if pb < pa:
        sinal = "prémio"
        f_bid = spot.bid + (pb / escala)
        f_ask = spot.ask + (pa / escala)
    elif pb > pa:
        sinal = "desconto"
        f_bid = spot.bid - (pb / escala)
        f_ask = spot.ask - (pa / escala)
    else:
        sinal = "neutro"
        f_bid = spot.bid
        f_ask = spot.ask

    if f_bid > f_ask:
        raise CotacaoInvalida(
            "O outright calculado resultou em bid > ask. "
            "Verifique os pontos e as casas decimais."
        )

    return SwapOutright(
        base=spot.base,
        cotada=spot.cotada,
        spot_bid=spot.bid,
        spot_ask=spot.ask,
        pontos_bid=pb,
        pontos_ask=pa,
        casas_decimais_pontos=casas_decimais_pontos,
        sinal=sinal,
        fwd_bid=f_bid,
        fwd_ask=f_ask,
    )
