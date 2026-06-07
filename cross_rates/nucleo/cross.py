"""Cálculo de cross-rates (taxas cruzadas) com bid/ask, sobre o grafo cambial.

Dada a moeda BASE e a moeda COTADA, o cross deriva-se de dois percursos:

* **bid** (a empresa/cliente *vende* a base) = taxa do percurso ``BASE -> COTADA``.
* **ask** (a empresa/cliente *compra* a base) = ``1 / (taxa de COTADA -> BASE)``.

Cada conversão consome a ponta desfavorável ao cliente — exatamente o
princípio do caderno ("o cliente perde sempre em cada conversão"). O
resultado vem ainda rotulado como ``direta``, ``cross direto (÷)``,
``cross indireto (×)`` ou ``cadeia``, para fins pedagógicos.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .grafo import GrafoCambial


@dataclass(frozen=True)
class ResultadoCross:
    """Resultado de um cross-rate, com percurso e classificação."""

    base: str
    cotada: str
    bid: Decimal
    ask: Decimal
    percurso: list[str]  # BASE -> ... -> COTADA (percurso de moedas)
    tipo: str

    @property
    def par(self) -> str:
        return f"{self.base}/{self.cotada}"

    @property
    def spread(self) -> Decimal:
        return self.ask - self.bid

    @property
    def percurso_texto(self) -> str:
        return " → ".join(self.percurso)


def cross(grafo: GrafoCambial, base: str, cotada: str) -> ResultadoCross:
    """Calcula o cross-rate ``BASE/COTADA`` a partir das cotações do grafo."""
    p_venda = grafo.percurso(base, cotada)  # vender a base: BASE -> COTADA
    bid = grafo.taxa_percurso(p_venda)

    p_compra = grafo.percurso(cotada, base)  # comprar a base: COTADA -> BASE
    ask = Decimal(1) / grafo.taxa_percurso(p_compra)

    base_norm, cotada_norm = p_venda[0], p_venda[-1]
    tipo = _classifica(grafo, p_venda)
    return ResultadoCross(base_norm, cotada_norm, bid, ask, p_venda, tipo)


def _classifica(grafo: GrafoCambial, percurso: list[str]) -> str:
    """Rotula o cross conforme a posição da moeda comum (regra do caderno)."""
    if len(percurso) == 2:
        return "direta"
    if len(percurso) == 3:
        base, pivo, cotada = percurso
        c1 = grafo.cotacao_do_par(base, pivo)
        c2 = grafo.cotacao_do_par(pivo, cotada)
        if c1 is not None and c2 is not None:
            # Moeda comum do mesmo lado nos dois pares (ambas ao certo OU ambas
            # ao incerto) -> cross direto (÷). Em lados opostos -> indireto (×).
            mesmo_lado = (c1.base == pivo) == (c2.base == pivo)
            estilo = "direto (÷)" if mesmo_lado else "indireto (×)"
            return f"cross {estilo} via {pivo}"
        return f"cross via {pivo}"
    return f"cadeia ({len(percurso) - 1} saltos)"
