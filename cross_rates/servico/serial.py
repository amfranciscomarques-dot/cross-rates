"""View-model: converte resultados do núcleo em dicts serializáveis (JSON-safe).

Ponto **único** onde se formata ``Decimal`` → ``str`` (via :func:`fmt`, preservando
precisão) e se escolhem os campos para apresentação. Os templates da web (e um
eventual endpoint JSON) consomem estes dicts em vez de tocarem em ``Decimal``; a
TUI mantém a sua própria renderização Rich a partir dos mesmos objetos do núcleo.

As casas decimais usadas aqui espelham as dos ``_mostrar_*`` da TUI, para que as
duas interfaces apresentem exatamente os mesmos números.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from cross_rates.nucleo import (
    AnaliseHedging,
    Arbitragem,
    ArbitragemGeografica,
    ArbitragemPrazo,
    Cotacao,
    ResultadoCross,
    ResultadoForward,
    SwapOutright,
)

from .formato import fmt

Montante = Decimal | None

# Algumas notas do núcleo trazem markup Rich (ex.: "[b]prémio[/b]") destinado à
# TUI. Removemo-lo aqui para que os templates web mostrem texto limpo.
_MARKUP = re.compile(r"\[/?[a-z ]+\]")


def _sem_markup(texto: str) -> str:
    return _MARKUP.sub("", texto)


def cotacao_dict(c: Cotacao) -> dict[str, str]:
    return {
        "par": c.par,
        "bid": fmt(c.bid),
        "ask": fmt(c.ask),
        "spread": fmt(c.spread),
        "fonte": c.fonte or "—",
    }


def cross_dict(r: ResultadoCross) -> dict[str, str]:
    return {
        "par": r.par,
        "bid": fmt(r.bid),
        "ask": fmt(r.ask),
        "spread": fmt(r.spread),
        "tipo": r.tipo,
        "percurso": r.percurso_texto,
        "bid_formula": r.bid_formula,
        "ask_formula": r.ask_formula,
        "nota": _sem_markup(r.nota),
    }


def triangular_dict(arb: Arbitragem, montante: Montante = None) -> dict[str, Any]:
    d: dict[str, Any] = {
        "ciclo": arb.ciclo_texto,
        "fator": fmt(arb.fator, 6),
        "ganho_pct": fmt(arb.ganho_pct, 4),
        "passos": [
            {"descricao": p.descricao, "taxa": fmt(p.taxa, 6)} for p in arb.passos
        ],
    }
    if montante is not None:
        d["simulacao"] = [
            {"moeda": m, "valor": fmt(v, 2)} for m, v in arb.simulacao(montante)
        ]
        d["lucro"] = fmt(arb.lucro(montante), 2)
        d["moeda_lucro"] = arb.ciclo[0]
    return d


def geografica_dict(arb: ArbitragemGeografica, montante: Montante = None) -> dict[str, Any]:
    d: dict[str, Any] = {
        "par": arb.par,
        "fonte_compra": arb.fonte_compra,
        "ask_compra": fmt(arb.ask_compra),
        "fonte_venda": arb.fonte_venda,
        "bid_venda": fmt(arb.bid_venda),
        "ganho_pct": fmt(arb.ganho_pct, 4),
    }
    if montante is not None:
        d["simulacao"] = list(arb.simulacao(montante))
    return d


def forward_dict(r: ResultadoForward) -> dict[str, str]:
    return {
        "par": r.par,
        "dias": str(r.dias),
        "bid": fmt(r.bid, 4),
        "ask": fmt(r.ask, 4),
        "spread": fmt(r.spread, 4),
        "spot_bid": fmt(r.spot_bid),
        "spot_ask": fmt(r.spot_ask),
        "pontos_bid": fmt(r.pontos_bid, 4),
        "pontos_ask": fmt(r.pontos_ask, 4),
        "sinal": r.sinal,
        "bid_formula": r.bid_formula,
        "ask_formula": r.ask_formula,
        "nota": _sem_markup(r.nota),
    }


def arbitragem_prazo_dict(arb: ArbitragemPrazo, montante: Montante = None) -> dict[str, Any]:
    d: dict[str, Any] = {
        "par": arb.par,
        "base": arb.base,
        "cotada": arb.cotada,
        "sentido": arb.sentido,
        "mercado_bid": fmt(arb.mercado_bid, 4),
        "mercado_ask": fmt(arb.mercado_ask, 4),
        "equilibrio_bid": fmt(arb.equilibrio_bid, 4),
        "equilibrio_ask": fmt(arb.equilibrio_ask, 4),
        "taxa_mercado": fmt(arb.taxa_mercado, 4),
        "sintetico": fmt(arb.sintetico, 6),
        "ganho_pct": fmt(arb.ganho_pct, 4),
    }
    if montante is not None:
        d["lucro"] = fmt(arb.lucro(montante), 2)
        d["montante"] = fmt(montante)
    return d


def swap_dict(r: SwapOutright) -> dict[str, str]:
    cd = r.casas_decimais_pontos
    return {
        "par": r.par,
        "fwd_bid": fmt(r.fwd_bid, cd),
        "fwd_ask": fmt(r.fwd_ask, cd),
        "spot_bid": fmt(r.spot_bid),
        "spot_ask": fmt(r.spot_ask),
        "pontos_bid": fmt(r.pontos_bid),
        "pontos_ask": fmt(r.pontos_ask),
        "sinal": r.sinal,
        "forward_formula_bid": r.forward_formula_bid,
        "forward_formula_ask": r.forward_formula_ask,
    }


def hedge_dict(r: AnaliseHedging) -> dict[str, str]:
    return {
        "tipo_exposicao": r.tipo_exposicao,
        "moeda_estrangeira": r.moeda_estrangeira,
        "moeda_base": r.moeda_base,
        "montante_me": fmt(r.montante_me),
        "dias": str(r.dias),
        "acao": "Custo" if r.tipo_exposicao == "pagamento" else "Receita",
        "fwd_taxa": fmt(r.fwd_taxa, 6),
        "fwd_resultado_base": fmt(r.fwd_resultado_base, 2),
        "mmh_me_presente": fmt(r.mmh_me_presente, 2),
        "mmh_taxa_juro_base": fmt(r.mmh_taxa_juro_base, 4),
        "mmh_spot_taxa": fmt(r.mmh_spot_taxa, 6),
        "mmh_base_presente": fmt(r.mmh_base_presente, 2),
        "mmh_resultado_base": fmt(r.mmh_resultado_base, 2),
        "melhor_estrategia": r.melhor_estrategia,
    }


def para_dict(obj: Any, montante: Montante = None) -> dict[str, Any]:
    """Despacha para o conversor adequado ao tipo do resultado do núcleo."""
    if isinstance(obj, Cotacao):
        return cotacao_dict(obj)
    if isinstance(obj, ResultadoCross):
        return cross_dict(obj)
    if isinstance(obj, Arbitragem):
        return triangular_dict(obj, montante)
    if isinstance(obj, ArbitragemGeografica):
        return geografica_dict(obj, montante)
    if isinstance(obj, ResultadoForward):
        return forward_dict(obj)
    if isinstance(obj, ArbitragemPrazo):
        return arbitragem_prazo_dict(obj, montante)
    if isinstance(obj, SwapOutright):
        return swap_dict(obj)
    if isinstance(obj, AnaliseHedging):
        return hedge_dict(obj)
    raise TypeError(f"Tipo sem serializador: {type(obj).__name__}")
