"""Cálculo de cross-rates (taxas cruzadas) com bid/ask, sobre o grafo cambial.

Dada a moeda BASE e a moeda COTADA, o cross deriva-se de dois percursos:

* **bid** (a empresa/cliente *vende* a base) = taxa do percurso ``BASE -> COTADA``.
* **ask** (a empresa/cliente *compra* a base) = ``1 / (taxa de COTADA -> BASE)``.

Cada conversão consome a ponta desfavorável ao cliente — exatamente o
princípio do caderno ("o cliente perde sempre em cada conversão"). O
resultado vem rotulado (``direta``, ``inversa``, ``cross direto (÷)``,
``cross indireto (×)`` ou ``cadeia``) e acompanhado das fórmulas bid/ask
explícitas e de uma nota metodológica, gerados a partir do percurso real.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .grafo import GrafoCambial


@dataclass(frozen=True)
class ResultadoCross:
    """Resultado de um cross-rate, com percurso, classificação e explicação."""

    base: str
    cotada: str
    bid: Decimal
    ask: Decimal
    percurso: list[str]  # BASE -> ... -> COTADA (percurso de moedas)
    tipo: str
    bid_formula: str
    ask_formula: str
    nota: str

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
    bid_formula, ask_formula = _formulas(grafo, p_venda)
    nota = _nota(tipo, p_venda)
    return ResultadoCross(
        base_norm, cotada_norm, bid, ask, p_venda, tipo, bid_formula, ask_formula, nota
    )


def _classifica(grafo: GrafoCambial, percurso: list[str]) -> str:
    """Rotula o cross conforme a posição da moeda comum (regra do caderno)."""
    if len(percurso) == 2:
        c = grafo.cotacao_do_par(percurso[0], percurso[1])
        if c is not None and c.base == percurso[0]:
            return "direta"
        return "inversa"
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
        # Inalcançável: toda a aresta do percurso (BFS) provém de uma cotação,
        # logo c1/c2 nunca são None; mantido por robustez/narrowing.
        return f"cross via {pivo}"  # pragma: no cover
    return f"cadeia ({len(percurso) - 1} saltos)"


def _formulas(grafo: GrafoCambial, percurso: list[str]) -> tuple[str, str]:
    """Fórmulas bid/ask explícitas, com as pontas certas, a partir do percurso.

    Em cada passo da venda da base aplica-se: ``× bid(par)`` se se vende a base
    desse par, ``÷ ask(par)`` se se compra a base desse par. O ask obtém-se da
    mesma estrutura trocando bid <-> ask (princípio de simetria do spread).
    """
    numerador: list[str] = []  # pares onde se *vende* a base (multiplicam)
    denominador: list[str] = []  # pares onde se *compra* a base (dividem)
    for de, para in zip(percurso, percurso[1:], strict=False):
        c = grafo.cotacao_do_par(de, para)
        par = c.par if c is not None else f"{de}/{para}"
        if c is not None and c.base == de:  # vende-se a base 'de'
            numerador.append(par)
        else:  # compra-se a base (o par está em sentido inverso)
            denominador.append(par)

    def render(lado_num: str, lado_den: str) -> str:
        n = " × ".join(f"{lado_num}({p})" for p in numerador)
        d = " × ".join(f"{lado_den}({p})" for p in denominador)
        if not denominador:
            return n
        if not numerador:
            return f"1 ÷ {d}" if len(denominador) == 1 else f"1 ÷ ({d})"
        esq = n if len(numerador) == 1 else f"({n})"
        dir_ = d if len(denominador) == 1 else f"({d})"
        return f"{esq} ÷ {dir_}"

    return f"bid = {render('bid', 'ask')}", f"ask = {render('ask', 'bid')}"


def _nota(tipo: str, percurso: list[str]) -> str:
    """Nota metodológica curta, conforme o tipo de cross."""
    principio = "Cada conversão aplica a ponta desfavorável ao cliente."
    if tipo == "direta":
        return f"Cotação direta — lida diretamente da tabela. {principio}"
    if tipo == "inversa":
        par = f"{percurso[1]}/{percurso[0]}"
        return (
            f"Cotação inversa de {par}: bid = 1/ask, ask = 1/bid. {principio}"
        )
    if tipo.startswith("cross direto"):
        pivo = percurso[1]
        return (
            f"A moeda comum {pivo} está do mesmo lado (ao certo ou ao incerto) "
            f"nos dois pares → cross direto (÷). {principio}"
        )
    if tipo.startswith("cross indireto"):
        pivo = percurso[1]
        return (
            f"A moeda comum {pivo} está em lados opostos (base num par, cotada "
            f"noutro) → cross indireto (×). {principio}"
        )
    return (
        f"Conversão em cadeia ({len(percurso) - 1} saltos): taxa cruzada "
        f"implícita, não cotada diretamente. {principio}"
    )
