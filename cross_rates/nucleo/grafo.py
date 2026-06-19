"""Grafo dirigido de conversões cambiais.

A ideia central: em vez de codificar à mão os casos "cross direto (÷)" e
"cross indireto (×)", modela-se cada cotação como **duas arestas dirigidas**.
As regras do caderno passam a emergir do produto das taxas ao longo de um
percurso — e o mesmo grafo serve depois para detetar arbitragem (um ciclo
cujo produto de taxas seja > 1).

Para um par ``BASE/COTADA`` com ``bid b`` e ``ask a``:

* ``BASE -> COTADA`` à taxa ``b``     — vender 1 BASE rende ``b`` COTADA.
* ``COTADA -> BASE`` à taxa ``1/a``   — 1 COTADA compra ``1/a`` BASE.

A taxa de um percurso é o produto das taxas das arestas: unidades da moeda
de destino por 1 unidade da moeda de origem.
"""

from __future__ import annotations

from collections import deque
from decimal import Decimal

from .cotacao import Cotacao, normaliza_moeda


class SemPercurso(LookupError):
    """Não existe percurso entre as duas moedas no grafo de cotações."""


class GrafoCambial:
    """Conjunto de cotações visto como grafo dirigido de conversões."""

    def __init__(self) -> None:
        # _adjacencia[de][para] = taxa (destino por 1 unidade de origem)
        self._adjacencia: dict[str, dict[str, Decimal]] = {}
        self._cotacoes: list[Cotacao] = []

    def adicionar(self, cotacao: Cotacao) -> None:
        """Acrescenta uma cotação (e as suas duas arestas dirigidas)."""
        self._cotacoes.append(cotacao)
        self._liga(cotacao.base, cotacao.cotada, cotacao.bid)
        self._liga(cotacao.cotada, cotacao.base, Decimal(1) / cotacao.ask)

    def _liga(self, de: str, para: str, taxa: Decimal) -> None:
        self._adjacencia.setdefault(de, {})[para] = taxa
        self._adjacencia.setdefault(para, {})

    @property
    def cotacoes(self) -> list[Cotacao]:
        return list(self._cotacoes)

    def moedas(self) -> set[str]:
        return set(self._adjacencia)

    def limpar(self) -> None:
        self._adjacencia.clear()
        self._cotacoes.clear()

    def percurso(self, origem: str, destino: str) -> list[str]:
        """Percurso com menos saltos de ``origem`` a ``destino`` (BFS)."""
        origem = normaliza_moeda(origem)
        destino = normaliza_moeda(destino)
        if origem not in self._adjacencia:
            raise SemPercurso(f"Moeda desconhecida: {origem}.")
        if destino not in self._adjacencia:
            raise SemPercurso(f"Moeda desconhecida: {destino}.")
        if origem == destino:
            return [origem]

        anterior: dict[str, str | None] = {origem: None}
        fila: deque[str] = deque([origem])
        while fila:
            atual = fila.popleft()
            for vizinho in self._adjacencia[atual]:
                if vizinho in anterior:
                    continue
                anterior[vizinho] = atual
                if vizinho == destino:
                    return self._reconstroi(anterior, destino)
                fila.append(vizinho)
        raise SemPercurso(
            f"Não há percurso de {origem} para {destino} com as cotações dadas."
        )

    @staticmethod
    def _reconstroi(anterior: dict[str, str | None], destino: str) -> list[str]:
        caminho = [destino]
        passo = anterior[destino]
        while passo is not None:
            caminho.append(passo)
            passo = anterior[passo]
        caminho.reverse()
        return caminho

    def taxa_percurso(self, percurso: list[str]) -> Decimal:
        """Produto das taxas das arestas ao longo de um percurso de moedas."""
        taxa = Decimal(1)
        for de, para in zip(percurso, percurso[1:], strict=False):
            try:
                taxa *= self._adjacencia[de][para]
            except KeyError as exc:
                raise SemPercurso(f"Sem aresta {de} -> {para}.") from exc
        return taxa

    def cotacao_do_par(self, x: str, y: str) -> Cotacao | None:
        """Cotação original que liga ``x`` e ``y`` (em qualquer sentido)."""
        x, y = normaliza_moeda(x), normaliza_moeda(y)
        for c in self._cotacoes:
            if {c.base, c.cotada} == {x, y}:
                return c
        return None
