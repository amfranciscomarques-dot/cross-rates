"""Deteção de arbitragem triangular sobre o grafo cambial.

Enquadramento (caderno, Ex. 17–18): a arbitragem triangular explora a
inconsistência entre três pares cotados em simultâneo. No grafo cambial, isso
traduz-se de forma direta: percorrer um **ciclo de três moedas** e regressar à
de partida. Se o **produto das taxas das arestas** (cada uma já na ponta
bid/ask correta) for **> 1**, fecha-se o ciclo com mais do que se partiu —
lucro certo e sem risco, porque todas as pernas são simultâneas.

    fator = taxa(A→B) × taxa(B→C) × taxa(C→A)
    fator > 1  ⇒  existe arbitragem;  ganho = (fator − 1) × montante inicial

É exatamente a comparação "cross implícito vs. cotação direta" do caderno,
mas expressa de uma só forma que dispensa decorar regras.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from decimal import Decimal

from .grafo import GrafoCambial


@dataclass(frozen=True)
class Passo:
    """Uma conversão (perna) de um ciclo de arbitragem."""

    de: str
    para: str
    par: str
    ponta: str  # "bid" ou "ask"
    taxa: Decimal

    @property
    def descricao(self) -> str:
        return f"vende {self.de} / compra {self.para} — {self.par} @ {self.ponta}"


@dataclass(frozen=True)
class Arbitragem:
    """Oportunidade de arbitragem triangular (ciclo com fator > 1)."""

    ciclo: list[str]  # ex.: ["EUR", "GBP", "JPY", "EUR"] (fechado)
    fator: Decimal
    passos: list[Passo]

    @property
    def ganho_pct(self) -> Decimal:
        return (self.fator - Decimal(1)) * Decimal(100)

    @property
    def ciclo_texto(self) -> str:
        return " → ".join(self.ciclo)

    def lucro(self, montante) -> Decimal:
        """Lucro absoluto para um dado montante da moeda inicial."""
        return Decimal(str(montante)) * (self.fator - Decimal(1))

    def simulacao(self, montante) -> list[tuple[str, Decimal]]:
        """Montante em cada moeda ao percorrer o ciclo (perna a perna)."""
        valor = Decimal(str(montante))
        linhas = [(self.ciclo[0], valor)]
        for passo in self.passos:
            valor = valor * passo.taxa
            linhas.append((passo.para, valor))
        return linhas


def _passo(grafo: GrafoCambial, de: str, para: str) -> Passo | None:
    """Constrói a perna ``de -> para`` (ou ``None`` se não houver cotação)."""
    c = grafo.cotacao_do_par(de, para)
    if c is None:
        return None
    if c.base == de:  # vende-se a base do par -> recebe-se ao bid
        return Passo(de, para, c.par, "bid", c.bid)
    # 'de' é a cotada: converter de->para compra a base 'para' ao ask (taxa 1/ask)
    return Passo(de, para, c.par, "ask", Decimal(1) / c.ask)


def _ciclo(grafo: GrafoCambial, ordem: tuple[str, ...]) -> Arbitragem | None:
    """Avalia o ciclo fechado ``ordem -> ordem[0]``; ``None`` se incompleto."""
    passos: list[Passo] = []
    fator = Decimal(1)
    for de, para in zip(ordem, ordem[1:] + ordem[:1]):
        passo = _passo(grafo, de, para)
        if passo is None:
            return None
        passos.append(passo)
        fator *= passo.taxa
    return Arbitragem(list(ordem) + [ordem[0]], fator, passos)


def arbitragens_triangulares(
    grafo: GrafoCambial, limiar: Decimal = Decimal("0")
) -> list[Arbitragem]:
    """Lista as arbitragens triangulares (fator > 1 + ``limiar``), as melhores primeiro.

    ``limiar`` permite exigir um ganho mínimo (ex.: ``Decimal("0.0001")`` para
    0,01%), filtrando ruído ou oportunidades não cobrem custos de transação.
    """
    moedas = sorted(grafo.moedas())
    oportunidades: list[Arbitragem] = []
    minimo = Decimal(1) + limiar
    for tripla in itertools.combinations(moedas, 3):
        a, b, c = tripla
        # As duas orientações do triângulo (em geral só uma é lucrativa).
        for ordem in ((a, b, c), (a, c, b)):
            arb = _ciclo(grafo, ordem)
            if arb is not None and arb.fator > minimo:
                oportunidades.append(arb)
    oportunidades.sort(key=lambda x: x.fator, reverse=True)
    return oportunidades
