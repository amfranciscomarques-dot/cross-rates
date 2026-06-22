"""Feeds de cotações: fontes de preços que semeiam o :class:`GrafoCambial`.

Assentam sobre o núcleo puro (devolvem :class:`cross_rates.nucleo.Cotacao`) e
são consumidos pelos frontends através do protocolo :class:`FonteCotacoes`,
sem que estes conheçam a implementação concreta. ``feed_por_nome`` é a fábrica
que a web usa para escolher o feed por configuração (variável de ambiente).
"""

from __future__ import annotations

from .base import FeedError, FeedIndisponivel, FonteCotacoes
from .frankfurter import FrankfurterFeed
from .simulado import FeedSimulado

# Nomes aceites na configuração que desligam a semeadura (tabela vazia).
_SEM_FEED = {"", "none", "nenhum"}


def feed_por_nome(nome: str | None) -> FonteCotacoes | None:
    """Resolve o nome de configuração para um feed (ou ``None`` se desligado).

    Aceita ``"frankfurter"`` (ao vivo), ``"simulado"`` (fixture offline) e
    ``""``/``"none"``/``None`` (sem feed). Qualquer outro valor é um erro de
    configuração e levanta :class:`FeedError`.
    """
    chave = (nome or "").strip().lower()
    if chave in _SEM_FEED:
        return None
    if chave == "frankfurter":
        return FrankfurterFeed()
    if chave == "simulado":
        return FeedSimulado()
    raise FeedError(f"Feed desconhecido: {nome!r} (use 'frankfurter', 'simulado' ou 'none').")


__all__ = [
    "FonteCotacoes",
    "FeedError",
    "FeedIndisponivel",
    "FrankfurterFeed",
    "FeedSimulado",
    "feed_por_nome",
]
