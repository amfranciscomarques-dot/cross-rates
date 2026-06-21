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
from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal

from .cotacao import Cotacao, Numerico, para_decimal
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

    def lucro(self, montante: Numerico) -> Decimal:
        """Lucro absoluto para um dado montante da moeda inicial."""
        return para_decimal(montante) * (self.fator - Decimal(1))

    def simulacao(self, montante: Numerico) -> list[tuple[str, Decimal]]:
        """Montante em cada moeda ao percorrer o ciclo (perna a perna)."""
        valor = para_decimal(montante)
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
    for de, para in zip(ordem, ordem[1:] + ordem[:1], strict=True):
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


# --------------------------------------------------------------------------- #
# Arbitragem geográfica (espacial)
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class ArbitragemGeografica:
    """Mesmo par cotado em duas praças: compra-se barato e vende-se caro.

    Existe se o ``ask`` mais baixo (onde se compra a base) for inferior ao
    ``bid`` mais alto (onde se vende a base), em praças diferentes.
    O ganho realiza-se na moeda cotada.
    """

    base: str
    cotada: str
    fonte_compra: str
    ask_compra: Decimal
    fonte_venda: str
    bid_venda: Decimal

    @property
    def par(self) -> str:
        return f"{self.base}/{self.cotada}"

    @property
    def margem(self) -> Decimal:
        """Margem por unidade da base (em moeda cotada)."""
        return self.bid_venda - self.ask_compra

    @property
    def fator(self) -> Decimal:
        return self.bid_venda / self.ask_compra

    @property
    def ganho_pct(self) -> Decimal:
        return (self.fator - Decimal(1)) * Decimal(100)

    def lucro(self, montante_base: Numerico) -> Decimal:
        """Lucro (em moeda cotada) ao arbitrar ``montante_base`` da base."""
        return para_decimal(montante_base) * self.margem

    def simulacao(self, montante_base: Numerico) -> list[str]:
        m = para_decimal(montante_base)
        paga = m * self.ask_compra
        recebe = m * self.bid_venda
        return [
            f"compra {m} {self.base} em {self.fonte_compra} @ ask "
            f"{self.ask_compra} → paga {paga} {self.cotada}",
            f"vende {m} {self.base} em {self.fonte_venda} @ bid "
            f"{self.bid_venda} → recebe {recebe} {self.cotada}",
            f"lucro = {recebe - paga} {self.cotada}",
        ]


def _orienta(c: Cotacao, base: str, cotada: str) -> tuple[Decimal, Decimal]:
    """Devolve (bid, ask) de ``c`` expressos na orientação ``base/cotada``."""
    if c.base == base and c.cotada == cotada:
        return c.bid, c.ask
    # cotação inversa: bid' = 1/ask, ask' = 1/bid
    return Decimal(1) / c.ask, Decimal(1) / c.bid


def arbitragens_geograficas(
    grafo: GrafoCambial, limiar: Decimal = Decimal("0")
) -> list[ArbitragemGeografica]:
    """Lista arbitragens geográficas (mesmo par em praças diferentes).

    Para cada par, encontra o ``ask`` mais baixo (compra) e o ``bid`` mais alto
    (venda); há arbitragem se ``bid_venda > ask_compra × (1 + limiar)``.
    """
    # Agrupa cotações por par não ordenado (junta orientações diretas e inversas).
    grupos: dict[frozenset[str], list[Cotacao]] = defaultdict(list)
    for c in grafo.cotacoes:
        grupos[frozenset((c.base, c.cotada))].append(c)

    oportunidades: list[ArbitragemGeografica] = []
    minimo = Decimal(1) + limiar
    for membros in grupos.values():
        if len(membros) < 2:
            continue
        # orientação canónica = a da primeira cotação do grupo
        base, cotada = membros[0].base, membros[0].cotada
        compra = None  # (fonte, ask) mais baixo
        venda = None  # (fonte, bid) mais alto
        for i, c in enumerate(membros):
            bid, ask = _orienta(c, base, cotada)
            fonte = c.fonte or f"praça {i + 1}"
            if compra is None or ask < compra[1]:
                compra = (fonte, ask)
            if venda is None or bid > venda[1]:
                venda = (fonte, bid)
        if compra is None or venda is None:
            continue
        if venda[1] > compra[1] * minimo and compra[0] != venda[0]:
            oportunidades.append(
                ArbitragemGeografica(
                    base, cotada, compra[0], compra[1], venda[0], venda[1]
                )
            )
    oportunidades.sort(key=lambda x: x.fator, reverse=True)
    return oportunidades
